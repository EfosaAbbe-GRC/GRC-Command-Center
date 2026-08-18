"""
backend/core/interview_sim.py

TPRM Interview Simulator — practice mock TPRM/vendor-risk interviews grounded
in this platform's own real assessment content, not synthesized content.

Integration notes (same conventions as core/tprm.py):
  - RBAC via the capability policy engine: authorize("INTERVIEW_RUN").
    Capability is seeded in main.py lifespan.
  - Tables auto-create via Base.metadata.create_all in init_db().
    Import this router in main.py BEFORE lifespan runs so the models
    are registered on Base.metadata (same reason core.tprm is imported there).
  - Question content is drawn from the real seeded TPRM stages
    (AssessmentStage.review_questions/guidance/evidence_to_collect) and, for
    vendor-scoped sessions, from a vendor's real GAP/IN_REVIEW stage
    responses -- never synthesized. See Interview_Simulator_Roadmap.md.
  - status/grading_status are plain strings, not a SQLAlchemy Enum -- per the
    ALTER TYPE gotcha documented in MEMORY.md (a Postgres native enum can't be
    widened by create_all()). Same choice already made for AgentRun.status.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from core.models import Base
from core.database import get_db
from core.auth import authorize, get_current_user, log_security_event
from core.config import settings
from core.logger import logger
from core.rag import GROQ_MODEL
from core.tprm import (
    Direction, TransferMethod, StageStatus,
    AssessmentStage, Vendor, Integration, StageResponse,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Models ──────────────────────────────────────────────────────────────────
class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_vendor = Column(String(255), nullable=True)   # real vendor name, or null for method-scoped
    scenario_method = Column(String(50), nullable=True)    # "<direction>/<transfer_method>" when vendor is null
    status = Column(String(20), nullable=False, default="in_progress")  # in_progress | completed
    started_by = Column(String(255), nullable=False)
    started_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    overall_score = Column(Integer, nullable=True)  # mean of graded turns' scores; null until >=1 graded

    turns = relationship("InterviewTurn", back_populates="session",
                          cascade="all, delete-orphan", order_by="InterviewTurn.turn_number")


class InterviewTurn(Base):
    __tablename__ = "interview_turns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("interview_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    source_stage_id = Column(UUID(as_uuid=True), ForeignKey("assessment_stages.id"), nullable=True)
    question_category = Column(String(255), nullable=True)
    question_text = Column(Text, nullable=False)
    user_response_text = Column(Text, nullable=True)
    rubric_json = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)
    grading_status = Column(String(20), nullable=False, default="pending")  # pending | graded | grading_failed
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    graded_at = Column(DateTime(timezone=True), nullable=True)

    session = relationship("InterviewSession", back_populates="turns")


# ── Grading (honesty boundary is the point of this section) ─────────────────
GRADING_PROMPT = """You are a strict, senior Third-Party Risk Management (TPRM) auditor grilling a \
candidate in a mock interview. You asked the candidate the following question, grounded in a real \
TPRM assessment stage from this platform's own vendor risk methodology:

STAGE: {question_category}
QUESTION: {question_text}
REFERENCE GUIDANCE (what a strong answer should cover): {guidance}
REFERENCE EVIDENCE A STRONG ANSWER WOULD CITE: {evidence_to_collect}

CANDIDATE'S ANSWER:
{response_text}

Grade the candidate's answer against the reference guidance and evidence above. Respond with ONLY a \
JSON object, no markdown fences, no commentary outside the JSON, in exactly this shape:
{{"completeness": <0-100 int>, "technical_accuracy": <0-100 int>, "defensibility": <0-100 int>, \
"feedback": "<2-4 sentences of direct, specific feedback -- what was strong, what was missing, be \
honest and specific, do not pad with generic praise>"}}
"""

_grading_llm = None


def _get_grading_llm():
    global _grading_llm
    if _grading_llm is None:
        from langchain_groq import ChatGroq
        # Same max_retries/timeout hardening as core/rag.py's RAG chain -- an
        # unbounded SDK retry/backoff on a bad key blocked the whole
        # single-threaded backend for ~23 minutes once (2026-08-13). No
        # reason for a second LLM call site to be able to repeat that.
        _grading_llm = ChatGroq(model=GROQ_MODEL, groq_api_key=settings.GROQ_API_KEY,
                                 max_retries=2, timeout=30)
    return _grading_llm


async def grade_response(question_text: str, question_category: Optional[str], guidance: str,
                          evidence_to_collect: str, response_text: str) -> dict:
    """Grades a candidate's answer against real TPRM stage guidance.

    Returns {"ok": True, "score", "rubric", "feedback"} on success, or
    {"ok": False} on ANY failure (call error, unparseable output, out-of-range
    score). Callers must never fabricate a score when ok is False -- this
    mirrors the _is_engine_failure pattern in core/agent.py and the
    ExecutiveTerminal honesty fix, both of which exist because this project
    has a real, documented history of a failure state quietly reporting as a
    clean result.
    """
    if not settings.GROQ_API_KEY:
        logger.error("Interview Simulator: grading unavailable, GROQ_API_KEY not set")
        return {"ok": False}

    prompt = GRADING_PROMPT.format(
        question_category=question_category or "General TPRM",
        question_text=question_text,
        guidance=guidance,
        evidence_to_collect=evidence_to_collect,
        response_text=response_text,
    )
    try:
        llm = _get_grading_llm()
        raw = await llm.ainvoke(prompt)
        text = (raw.content if hasattr(raw, "content") else str(raw)).strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)

        sub_scores = {
            "completeness": int(parsed["completeness"]),
            "technical_accuracy": int(parsed["technical_accuracy"]),
            "defensibility": int(parsed["defensibility"]),
        }
        for v in sub_scores.values():
            if not (0 <= v <= 100):
                raise ValueError(f"sub-score out of 0-100 range: {v}")

        feedback = str(parsed["feedback"]).strip()
        if not feedback:
            raise ValueError("empty feedback")

        overall = round(sum(sub_scores.values()) / 3)
        return {"ok": True, "score": overall, "rubric": sub_scores, "feedback": feedback}
    except Exception as e:
        logger.error("Interview Simulator: grading call failed", error=str(e))
        return {"ok": False}


# ── Schemas ─────────────────────────────────────────────────────────────────
class InterviewSessionCreate(BaseModel):
    scenario_vendor: Optional[str] = None
    direction: Optional[Direction] = None
    transfer_method: Optional[TransferMethod] = None


class TurnResponseIn(BaseModel):
    response_text: str


class InterviewTurnOut(BaseModel):
    id: uuid.UUID
    turn_number: int
    question_category: Optional[str] = None
    question_text: str
    user_response_text: Optional[str] = None
    score: Optional[int] = None
    rubric_json: Optional[str] = None
    feedback_text: Optional[str] = None
    grading_status: str
    created_at: datetime
    graded_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InterviewSessionOut(BaseModel):
    id: uuid.UUID
    scenario_vendor: Optional[str] = None
    scenario_method: Optional[str] = None
    status: str
    started_by: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    overall_score: Optional[int] = None
    total_turns: int


class InterviewSessionDetail(InterviewSessionOut):
    turns: List[InterviewTurnOut]


# ── Router ──────────────────────────────────────────────────────────────────
router = APIRouter()

CAP_RUN = "INTERVIEW_RUN"


def _compose_vendor_question(vendor_name: str, integration_name: str, stage: AssessmentStage,
                              stage_status: StageStatus) -> str:
    return (f"Vendor '{vendor_name}', integration '{integration_name}' has an open "
            f"{stage_status.value.upper()} on Stage {stage.stage_number} — {stage.title}. "
            f"{stage.review_questions}")


def _compose_generic_question(stage: AssessmentStage) -> str:
    return f"Stage {stage.stage_number} — {stage.title}. {stage.review_questions}"


async def _load_session_detail(session_id: uuid.UUID, db: AsyncSession,
                                requesting_user: str) -> InterviewSessionDetail:
    session = await db.get(InterviewSession, session_id)
    if not session or session.started_by != requesting_user:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(InterviewTurn).where(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_number)
    )
    turns = result.scalars().all()

    # Never reveal a future question's text before its predecessor is
    # answered -- a practice interview where you can read ahead isn't
    # practice. Already-answered turns (including in a completed session)
    # always show in full.
    visible: List[InterviewTurnOut] = []
    current_shown = False
    for t in turns:
        answered = t.user_response_text is not None
        if answered or not current_shown:
            visible.append(InterviewTurnOut.model_validate(t))
            if not answered:
                current_shown = True
        else:
            visible.append(InterviewTurnOut(
                id=t.id, turn_number=t.turn_number, question_category=t.question_category,
                question_text="(not yet revealed)", grading_status="pending", created_at=t.created_at,
            ))

    return InterviewSessionDetail(
        id=session.id, scenario_vendor=session.scenario_vendor, scenario_method=session.scenario_method,
        status=session.status, started_by=session.started_by, started_at=session.started_at,
        completed_at=session.completed_at, overall_score=session.overall_score,
        total_turns=len(turns), turns=visible,
    )


@router.post("/sessions", response_model=InterviewSessionDetail, dependencies=[Depends(authorize(CAP_RUN))])
async def start_session(payload: InterviewSessionCreate, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = get_current_user(request)

    if payload.scenario_vendor and (payload.direction or payload.transfer_method):
        raise HTTPException(status_code=422,
            detail="Specify either scenario_vendor, or direction + transfer_method -- not both")
    if not payload.scenario_vendor and not (payload.direction and payload.transfer_method):
        raise HTTPException(status_code=422,
            detail="Specify scenario_vendor, or both direction and transfer_method")

    turns_source = []  # list of (source_stage_id, question_text, question_category)
    vendor_name = None
    scenario_method_label = None

    if payload.scenario_vendor:
        vendor_result = await db.execute(
            select(Vendor).where(func.lower(Vendor.name) == payload.scenario_vendor.lower())
        )
        vendor = vendor_result.scalar_one_or_none()
        if not vendor:
            raise HTTPException(status_code=404, detail=f"Vendor '{payload.scenario_vendor}' not found")
        vendor_name = vendor.name

        rows = await db.execute(
            select(StageResponse, AssessmentStage, Integration.name)
            .join(AssessmentStage, AssessmentStage.id == StageResponse.stage_id)
            .join(Integration, Integration.id == StageResponse.integration_id)
            .where(
                Integration.vendor_id == vendor.id,
                StageResponse.status.in_([StageStatus.GAP, StageStatus.IN_REVIEW]),
            )
            .order_by(Integration.name, AssessmentStage.stage_number)
        )
        pool = rows.all()
        if not pool:
            raise HTTPException(status_code=409,
                detail=f"'{vendor.name}' has no open findings (GAP/IN_REVIEW stages) to interview on")
        for stage_response, stage, integ_name in pool:
            q = _compose_vendor_question(vendor.name, integ_name, stage, stage_response.status)
            turns_source.append((stage.id, q, stage.title))
    else:
        rows = await db.execute(
            select(AssessmentStage)
            .where(
                AssessmentStage.direction == payload.direction,
                AssessmentStage.applies_to_methods.in_(["both", payload.transfer_method.value]),
            )
            .order_by(AssessmentStage.stage_number)
        )
        stages = rows.scalars().all()
        if not stages:
            raise HTTPException(status_code=409,
                detail="No TPRM stages match that direction/transfer_method combination")
        for stage in stages:
            turns_source.append((stage.id, _compose_generic_question(stage), stage.title))
        scenario_method_label = f"{payload.direction.value}/{payload.transfer_method.value}"

    session = InterviewSession(
        scenario_vendor=vendor_name, scenario_method=scenario_method_label,
        status="in_progress", started_by=current_user["username"],
    )
    db.add(session)
    await db.flush()  # assign session.id before creating turns

    for i, (stage_id, question_text, category) in enumerate(turns_source, start=1):
        db.add(InterviewTurn(
            session_id=session.id, turn_number=i, source_stage_id=stage_id,
            question_category=category, question_text=question_text, grading_status="pending",
        ))
    await db.commit()

    log_security_event(request, "INTERVIEW_SIM_SESSION_START",
        f"Session {session.id} started by {current_user['username']} "
        f"({'vendor=' + vendor_name if vendor_name else 'method=' + scenario_method_label}), "
        f"{len(turns_source)} turns")

    return await _load_session_detail(session.id, db, current_user["username"])


@router.get("/sessions", response_model=List[InterviewSessionOut], dependencies=[Depends(authorize(CAP_RUN))])
async def list_sessions(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = get_current_user(request)
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.started_by == current_user["username"])
        .order_by(InterviewSession.started_at.desc())
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        count_result = await db.execute(
            select(func.count()).select_from(InterviewTurn).where(InterviewTurn.session_id == s.id)
        )
        out.append(InterviewSessionOut(
            id=s.id, scenario_vendor=s.scenario_vendor, scenario_method=s.scenario_method,
            status=s.status, started_by=s.started_by, started_at=s.started_at,
            completed_at=s.completed_at, overall_score=s.overall_score,
            total_turns=count_result.scalar_one(),
        ))
    return out


@router.get("/sessions/{session_id}", response_model=InterviewSessionDetail,
            dependencies=[Depends(authorize(CAP_RUN))])
async def get_session(session_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = get_current_user(request)
    return await _load_session_detail(session_id, db, current_user["username"])


@router.post("/sessions/{session_id}/turns/{turn_id}/respond", response_model=dict,
             dependencies=[Depends(authorize(CAP_RUN))])
async def submit_turn_response(session_id: uuid.UUID, turn_id: uuid.UUID, payload: TurnResponseIn,
                                request: Request, db: AsyncSession = Depends(get_db)):
    current_user = get_current_user(request)
    session = await db.get(InterviewSession, session_id)
    if not session or session.started_by != current_user["username"]:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status == "completed":
        raise HTTPException(status_code=409, detail="Session already completed")

    turn = await db.get(InterviewTurn, turn_id)
    if not turn or turn.session_id != session_id:
        raise HTTPException(status_code=404, detail="Turn not found in this session")
    if turn.user_response_text is not None:
        raise HTTPException(status_code=409, detail="Turn already answered")
    if not payload.response_text.strip():
        raise HTTPException(status_code=422, detail="Response cannot be empty")

    stage = await db.get(AssessmentStage, turn.source_stage_id) if turn.source_stage_id else None
    guidance = stage.guidance if stage else "General TPRM diligence — evaluate on soundness alone."
    evidence = stage.evidence_to_collect if stage else "N/A"

    turn.user_response_text = payload.response_text
    result = await grade_response(turn.question_text, turn.question_category, guidance, evidence,
                                   payload.response_text)
    turn.graded_at = _utcnow()
    if result["ok"]:
        turn.grading_status = "graded"
        turn.score = result["score"]
        turn.rubric_json = json.dumps(result["rubric"])
        turn.feedback_text = result["feedback"]
    else:
        turn.grading_status = "grading_failed"
    await db.commit()
    await db.refresh(turn)

    all_turns_result = await db.execute(
        select(InterviewTurn).where(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_number)
    )
    all_turns = all_turns_result.scalars().all()
    next_turn = next((t for t in all_turns if t.user_response_text is None), None)

    if next_turn is None:
        session.status = "completed"
        session.completed_at = _utcnow()
        graded_scores = [t.score for t in all_turns if t.grading_status == "graded" and t.score is not None]
        session.overall_score = round(sum(graded_scores) / len(graded_scores)) if graded_scores else None
        await db.commit()

    log_security_event(request, "INTERVIEW_SIM_TURN_GRADED",
        f"Turn {turn.turn_number} on session {session_id} -> grading_status={turn.grading_status}")

    return {
        "turn": InterviewTurnOut.model_validate(turn).model_dump(mode="json"),
        "next_turn": InterviewTurnOut.model_validate(next_turn).model_dump(mode="json") if next_turn else None,
        "session_status": session.status,
        "overall_score": session.overall_score,
    }
