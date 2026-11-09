"""
backend/core/risk_register.py

Risk register: Phase 1 of the linked data model (docs/refactors/Linked_Data_Model_refactor.md,
docs/refactors/Risk_Register_refactor.md).

  - entities: what a risk is about (process, application, asset, vendor, ...). The shared anchor
    later phases (controls, issues) attach to.
  - risks: the register. Editable, never deleted; closed with a reason.
  - risk_events: every change, append-only and hash-chained (in PROTECTED_TABLES; core/migrate.py
    installs the blockers and the chain trigger, and revokes DELETE on risks/entities).

Rules: scores, bands, status and review dates are computed here, never sent by the client
(core/risk_scoring.py holds the criteria). The risk OWNER accepts residual risk (ISO/IEC 27001:2022
6.1.3 f); an admin records that acceptance and may not be the one who proposed it.
"""
from __future__ import annotations

import csv
import enum
import io
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, Computed, Date, DateTime, Enum as SAEnum, ForeignKey,
    Identity, Integer, String, Text, UniqueConstraint, select, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from core import risk_scoring as rs
from core.auth import authorize, get_current_user, log_security_event
from core.database import get_db
from core.models import Base
from core.ws import manager

CAP_VIEW = "RISK_VIEW"        # viewer
CAP_EDIT = "RISK_EDIT"        # analyst
CAP_APPROVE = "RISK_APPROVE"  # admin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ───────────────────────────────────────────────────────────────────
class EntityType(str, enum.Enum):
    ORGANISATION = "organisation"
    BUSINESS_UNIT = "business_unit"
    PROCESS = "process"
    APPLICATION = "application"
    ASSET = "asset"
    VENDOR = "vendor"


class RiskCategory(str, enum.Enum):
    INFORMATION_SECURITY = "information_security"
    OPERATIONAL = "operational"
    COMPLIANCE = "compliance"
    THIRD_PARTY = "third_party"
    PRIVACY = "privacy"
    STRATEGIC = "strategic"


class Treatment(str, enum.Enum):
    UNDECIDED = "undecided"
    MITIGATE = "mitigate"
    ACCEPT = "accept"
    TRANSFER = "transfer"
    AVOID = "avoid"


class RiskStatus(str, enum.Enum):
    IDENTIFIED = "identified"
    ASSESSED = "assessed"
    TREATMENT_IN_PROGRESS = "treatment_in_progress"
    ACCEPTED = "accepted"
    CLOSED = "closed"


class RiskEventType(str, enum.Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    ACCEPTANCE_PROPOSED = "ACCEPTANCE_PROPOSED"
    ACCEPTED = "ACCEPTED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


def _enum(e, name):
    # Store the lowercase .value (not the member name) so the DB reads like the API.
    return SAEnum(e, name=name, values_callable=lambda x: [m.value for m in x])


# ── Models ──────────────────────────────────────────────────────────────────
class Entity(Base):
    __tablename__ = "entities"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    entity_type = Column(_enum(EntityType, "entitytype"), nullable=False)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True, unique=True)
    description = Column(Text)
    owner = Column(String(200))
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "name", name="uq_entity_type_name"),)


class Risk(Base):
    """Editable register row. Every change also writes a RiskEvent; DELETE is revoked."""
    __tablename__ = "risks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ref_no = Column(Integer, Identity(), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    statement = Column(Text, nullable=False)
    category = Column(_enum(RiskCategory, "riskcategory"), nullable=False)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    owner = Column(String(200), nullable=False)
    inherent_likelihood = Column(Integer, nullable=False)
    inherent_impact = Column(Integer, nullable=False)
    inherent_score = Column(Integer, Computed("inherent_likelihood * inherent_impact", persisted=True))
    existing_controls = Column(Text)
    residual_likelihood = Column(Integer)
    residual_impact = Column(Integer)
    residual_score = Column(Integer, Computed("residual_likelihood * residual_impact", persisted=True))
    treatment = Column(_enum(Treatment, "risktreatment"), nullable=False, default=Treatment.UNDECIDED)
    treatment_plan = Column(Text)
    target_date = Column(Date)
    status = Column(_enum(RiskStatus, "riskstatus"), nullable=False, default=RiskStatus.IDENTIFIED)
    accepted_by_owner = Column(String(200))
    acceptance_expires_at = Column(DateTime(timezone=True))
    pending_acceptance_by = Column(String(255))
    pending_acceptance_days = Column(Integer)
    review_due = Column(Date, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_by = Column(String(255))
    updated_at = Column(DateTime(timezone=True))
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        CheckConstraint("inherent_likelihood BETWEEN 1 AND 5 AND inherent_impact BETWEEN 1 AND 5",
                        name="ck_risk_inherent_range"),
        CheckConstraint("(residual_likelihood IS NULL AND residual_impact IS NULL) OR "
                        "(residual_likelihood BETWEEN 1 AND 5 AND residual_impact BETWEEN 1 AND 5)",
                        name="ck_risk_residual_range"),
        CheckConstraint("residual_likelihood IS NULL OR "
                        "residual_likelihood * residual_impact <= inherent_likelihood * inherent_impact",
                        name="ck_risk_residual_not_above_inherent"),
    )


class RiskEvent(Base):
    """Append-only, hash-chained history of every change to a risk (T1)."""
    __tablename__ = "risk_events"
    id = Column(BigInteger, Identity(), primary_key=True)
    risk_id = Column(UUID(as_uuid=True), ForeignKey("risks.id"), nullable=False, index=True)
    event_type = Column(_enum(RiskEventType, "riskeventtype"), nullable=False)
    changes = Column(JSONB, nullable=False, default=dict)
    reason = Column(Text)
    actor = Column(String(255), nullable=False)          # from the token, never the client
    accepted_by_owner = Column(String(200))
    expires_at = Column(DateTime(timezone=True))
    evidence_chain_id = Column(Integer, ForeignKey("evidence_chain.id"))
    at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ── Schemas ─────────────────────────────────────────────────────────────────
Rating = Field(ge=1, le=5)
Reason = Field(min_length=3, max_length=1000)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")   # a client-sent score or status is a 422 (T5)


class EntityIn(_In):
    name: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    vendor_id: Optional[uuid.UUID] = None
    description: Optional[str] = Field(None, max_length=2000)
    owner: Optional[str] = Field(None, max_length=200)


class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    entity_type: EntityType
    vendor_id: Optional[uuid.UUID]
    description: Optional[str]
    owner: Optional[str]


class RiskCreate(_In):
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=4000)
    category: RiskCategory
    entity_id: uuid.UUID
    owner: str = Field(min_length=1, max_length=200)
    inherent_likelihood: int = Rating
    inherent_impact: int = Rating
    existing_controls: Optional[str] = Field(None, max_length=4000)
    residual_likelihood: Optional[int] = Field(None, ge=1, le=5)
    residual_impact: Optional[int] = Field(None, ge=1, le=5)


class RiskUpdate(_In):
    version: int
    reason: str = Reason
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    statement: Optional[str] = Field(None, min_length=1, max_length=4000)
    category: Optional[RiskCategory] = None
    entity_id: Optional[uuid.UUID] = None
    owner: Optional[str] = Field(None, min_length=1, max_length=200)
    inherent_likelihood: Optional[int] = Field(None, ge=1, le=5)
    inherent_impact: Optional[int] = Field(None, ge=1, le=5)
    existing_controls: Optional[str] = Field(None, max_length=4000)
    residual_likelihood: Optional[int] = Field(None, ge=1, le=5)
    residual_impact: Optional[int] = Field(None, ge=1, le=5)
    treatment: Optional[Treatment] = None
    treatment_plan: Optional[str] = Field(None, max_length=4000)
    target_date: Optional[date] = None


class ProposeIn(_In):
    version: int
    days: int
    reason: str = Reason


class AcceptIn(_In):
    version: int
    accepted_by_owner: str = Field(min_length=1, max_length=200)
    reason: str = Reason
    evidence_chain_id: Optional[int] = None


class VersionReason(_In):
    version: int
    reason: str = Reason


# ── Helpers ─────────────────────────────────────────────────────────────────
VOIDING_FIELDS = {"owner", "inherent_likelihood", "inherent_impact",
                  "residual_likelihood", "residual_impact", "treatment"}
EDITABLE = ("title", "statement", "category", "entity_id", "owner", "inherent_likelihood",
            "inherent_impact", "existing_controls", "residual_likelihood", "residual_impact",
            "treatment", "treatment_plan", "target_date")


def _json(v: Any) -> Any:
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def _effective_band(r: Risk) -> str:
    if r.residual_likelihood is not None:
        return rs.band(r.residual_likelihood * r.residual_impact)
    return rs.band(r.inherent_likelihood * r.inherent_impact)


def _set_status(r: Risk) -> None:
    if r.status == RiskStatus.CLOSED:
        return
    r.status = RiskStatus(rs.derive_status(
        closed=False, accepted_until=r.acceptance_expires_at,
        treatment=Treatment(r.treatment).value, residual_rated=r.residual_likelihood is not None))


def _validate(r: Risk) -> None:
    """Whole-record rules after a change (T5)."""
    try:
        inherent = rs.score(r.inherent_likelihood, r.inherent_impact)
        if (r.residual_likelihood is None) != (r.residual_impact is None):
            raise HTTPException(422, "rate residual likelihood and impact together")
        if r.residual_likelihood is not None and rs.score(r.residual_likelihood, r.residual_impact) > inherent:
            raise HTTPException(422, "residual risk can't exceed inherent risk; controls don't raise risk")
    except ValueError as e:
        raise HTTPException(422, str(e))
    if r.treatment == Treatment.MITIGATE and not (r.treatment_plan and r.target_date):
        raise HTTPException(422, "a mitigation needs a treatment plan and a target date")


def _event(db, risk_id, etype, actor, changes=None, reason=None, **extra) -> None:
    db.add(RiskEvent(risk_id=risk_id, event_type=etype, actor=actor,
                     changes={k: {"before": _json(b), "after": _json(a)} for k, (b, a) in (changes or {}).items()},
                     reason=reason, **extra))


def _out(r: Risk, entity_name: Optional[str] = None) -> dict:
    now = _utcnow()
    expired = bool(r.acceptance_expires_at and r.acceptance_expires_at < now)
    inherent = r.inherent_likelihood * r.inherent_impact
    residual = (r.residual_likelihood * r.residual_impact) if r.residual_likelihood is not None else None
    return {
        "id": r.id, "ref": f"R-{r.ref_no:04d}", "title": r.title, "statement": r.statement,
        "category": _json(r.category), "entity_id": r.entity_id, "entity_name": entity_name,
        "owner": r.owner,
        "inherent_likelihood": r.inherent_likelihood, "inherent_impact": r.inherent_impact,
        "inherent_score": inherent, "inherent_band": rs.band(inherent),
        "existing_controls": r.existing_controls,
        "residual_likelihood": r.residual_likelihood, "residual_impact": r.residual_impact,
        "residual_score": residual, "residual_band": rs.band(residual),
        "treatment": _json(r.treatment), "treatment_plan": r.treatment_plan, "target_date": r.target_date,
        "status": _json(r.status), "accepted_by_owner": r.accepted_by_owner,
        "acceptance_expires_at": r.acceptance_expires_at, "acceptance_expired": expired,
        "pending_acceptance_by": r.pending_acceptance_by, "pending_acceptance_days": r.pending_acceptance_days,
        "review_due": r.review_due,
        "overdue": r.status != RiskStatus.CLOSED and (r.review_due < now.date() or expired),
        "version": r.version, "created_by": r.created_by, "created_at": r.created_at,
        "updated_by": r.updated_by, "updated_at": r.updated_at,
    }


async def _load(db: AsyncSession, risk_id: uuid.UUID) -> Risk:
    risk = await db.get(Risk, risk_id)
    if not risk:
        raise HTTPException(404, "Risk not found")
    return risk


async def _entity_name(db: AsyncSession, entity_id) -> Optional[str]:
    e = await db.get(Entity, entity_id)
    return e.name if e else None


def _check_version(risk: Risk, version: int) -> None:
    if version != risk.version:
        raise HTTPException(409, "This risk changed since you opened it; reload and try again")


async def _commit(db: AsyncSession, risk: Optional[Risk] = None) -> None:
    try:
        await db.commit()
    except StaleDataError:
        await db.rollback()
        raise HTTPException(409, "This risk changed since you opened it; reload and try again")
    if risk is not None:
        await db.refresh(risk)
    await manager.broadcast({"type": "RISK_REGISTER_CHANGED"})


# ── Router ──────────────────────────────────────────────────────────────────
router = APIRouter()


@router.get("/entities", response_model=List[EntityOut], dependencies=[Depends(authorize(CAP_VIEW))])
async def list_entities(db: AsyncSession = Depends(get_db)):
    return (await db.execute(select(Entity).order_by(Entity.entity_type, Entity.name))).scalars().all()


@router.post("/entities", response_model=EntityOut, dependencies=[Depends(authorize(CAP_EDIT))])
async def create_entity(payload: EntityIn, request: Request, db: AsyncSession = Depends(get_db)):
    if payload.vendor_id is not None:
        if payload.entity_type != EntityType.VENDOR:
            raise HTTPException(422, "only a vendor entity can reference a vendor")
        found = (await db.execute(text("SELECT 1 FROM vendors WHERE id = :v"),
                                  {"v": payload.vendor_id})).first()
        if not found:
            raise HTTPException(422, "vendor not found")
    dup = (await db.execute(select(Entity).where(Entity.entity_type == payload.entity_type,
                                                 Entity.name == payload.name))).first()
    if dup:
        raise HTTPException(409, "an entity of this type with this name already exists")
    entity = Entity(**payload.model_dump(), created_by=get_current_user(request)["username"])
    db.add(entity)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "entity already exists (name or vendor already registered)")
    await db.refresh(entity)
    await manager.broadcast({"type": "RISK_REGISTER_CHANGED"})
    return entity


@router.get("/risks", dependencies=[Depends(authorize(CAP_VIEW))])
async def list_risks(
    db: AsyncSession = Depends(get_db),
    status: Optional[RiskStatus] = None,
    entity_id: Optional[uuid.UUID] = None,
    band: Optional[str] = Query(None, pattern="^(low|medium|high|critical)$"),
    overdue: Optional[bool] = None,
):
    q = select(Risk, Entity.name).join(Entity, Entity.id == Risk.entity_id).order_by(Risk.ref_no)
    if status:
        q = q.where(Risk.status == status)
    if entity_id:
        q = q.where(Risk.entity_id == entity_id)
    rows = [_out(r, name) for r, name in (await db.execute(q)).all()]
    if band:
        rows = [x for x in rows if (x["residual_band"] or x["inherent_band"]) == band]
    if overdue is not None:
        rows = [x for x in rows if x["overdue"] == overdue]
    return rows


@router.get("/risks/heatmap", dependencies=[Depends(authorize(CAP_VIEW))])
async def risk_heatmap(basis: str = Query("residual", pattern="^(inherent|residual)$"),
                       db: AsyncSession = Depends(get_db)):
    grid = [[0] * 5 for _ in range(5)]   # grid[likelihood-1][impact-1]
    for r in (await db.execute(select(Risk).where(Risk.status != RiskStatus.CLOSED))).scalars():
        l, i = ((r.inherent_likelihood, r.inherent_impact) if basis == "inherent"
                else (r.residual_likelihood, r.residual_impact))
        if l is not None:
            grid[l - 1][i - 1] += 1
    return {"basis": basis, "grid": grid}


EXPORT_HEADER = ["Ref", "Title", "Entity", "Category", "Owner", "Statement", "Existing controls",
                 "Inherent L", "Inherent I", "Inherent score", "Inherent band",
                 "Residual L", "Residual I", "Residual score", "Residual band",
                 "Treatment", "Treatment plan", "Target date", "Status",
                 "Accepted by (owner)", "Acceptance expires", "Review due", "Overdue"]


@router.get("/risks/export", dependencies=[Depends(authorize("EVIDENCE_EXPORT"))])
async def export_risks(db: AsyncSession = Depends(get_db)):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(EXPORT_HEADER)
    q = select(Risk, Entity.name).join(Entity, Entity.id == Risk.entity_id).order_by(Risk.ref_no)
    for r, name in (await db.execute(q)).all():
        x = _out(r, name)
        w.writerow([rs.csv_safe(v) for v in (
            x["ref"], x["title"], name, x["category"], x["owner"], x["statement"], x["existing_controls"],
            x["inherent_likelihood"], x["inherent_impact"], x["inherent_score"], x["inherent_band"],
            x["residual_likelihood"], x["residual_impact"], x["residual_score"], x["residual_band"],
            x["treatment"], x["treatment_plan"], _json(x["target_date"]), x["status"],
            x["accepted_by_owner"], _json(x["acceptance_expires_at"]), _json(x["review_due"]), x["overdue"])])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=risk_register.csv"})


@router.get("/risks/{risk_id}", dependencies=[Depends(authorize(CAP_VIEW))])
async def get_risk(risk_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    risk = await _load(db, risk_id)
    events = (await db.execute(select(RiskEvent).where(RiskEvent.risk_id == risk_id)
                               .order_by(RiskEvent.id))).scalars().all()
    detail = _out(risk, await _entity_name(db, risk.entity_id))
    detail["events"] = [{
        "id": e.id, "event_type": _json(e.event_type), "changes": e.changes, "reason": e.reason,
        "actor": e.actor, "accepted_by_owner": e.accepted_by_owner, "expires_at": e.expires_at,
        "evidence_chain_id": e.evidence_chain_id, "at": e.at,
    } for e in events]
    return detail


@router.post("/risks", dependencies=[Depends(authorize(CAP_EDIT))])
async def create_risk(payload: RiskCreate, request: Request, db: AsyncSession = Depends(get_db)):
    actor = get_current_user(request)["username"]
    if not await db.get(Entity, payload.entity_id):
        raise HTTPException(422, "entity not found")
    risk = Risk(**payload.model_dump(), treatment=Treatment.UNDECIDED, created_by=actor,
                review_due=date.today())
    _validate(risk)
    risk.review_due = rs.review_due(date.today(), _effective_band(risk))
    _set_status(risk)
    db.add(risk)
    await db.flush()
    _event(db, risk.id, RiskEventType.CREATED, actor,
           changes={k: (None, getattr(risk, k)) for k in (*EDITABLE, "review_due", "status")
                    if getattr(risk, k) is not None})
    await _commit(db, risk)
    return _out(risk, await _entity_name(db, risk.entity_id))


@router.patch("/risks/{risk_id}", dependencies=[Depends(authorize(CAP_EDIT))])
async def update_risk(risk_id: uuid.UUID, payload: RiskUpdate, request: Request,
                      db: AsyncSession = Depends(get_db)):
    actor = get_current_user(request)["username"]
    risk = await _load(db, risk_id)
    _check_version(risk, payload.version)
    if risk.status == RiskStatus.CLOSED:
        raise HTTPException(409, "reopen a closed risk before editing it")
    if payload.treatment == Treatment.ACCEPT:
        raise HTTPException(422, "use propose-acceptance to accept a risk")
    if payload.entity_id is not None and not await db.get(Entity, payload.entity_id):
        raise HTTPException(422, "entity not found")

    before = {k: getattr(risk, k) for k in (*EDITABLE, "review_due", "status", "accepted_by_owner",
                                           "acceptance_expires_at", "pending_acceptance_by",
                                           "pending_acceptance_days")}
    sent = payload.model_dump(exclude_unset=True, exclude={"version", "reason"})
    for k, v in sent.items():
        setattr(risk, k, v)
    changed = {k for k in sent if before[k] != getattr(risk, k)}
    if not changed:
        raise HTTPException(422, "nothing changed")

    # R4: an acceptance given for the old facts no longer stands.
    if changed & VOIDING_FIELDS and (risk.acceptance_expires_at or risk.pending_acceptance_by):
        risk.acceptance_expires_at = risk.accepted_by_owner = None
        risk.pending_acceptance_by = risk.pending_acceptance_days = None
        if "treatment" not in changed and risk.treatment == Treatment.ACCEPT:
            risk.treatment = Treatment.UNDECIDED
    _validate(risk)
    if changed & {"inherent_likelihood", "inherent_impact", "residual_likelihood", "residual_impact"}:
        risk.review_due = rs.review_due(date.today(), _effective_band(risk))
    _set_status(risk)
    risk.updated_by, risk.updated_at = actor, _utcnow()

    diff = {k: (b, getattr(risk, k)) for k, b in before.items() if b != getattr(risk, k)}
    _event(db, risk.id, RiskEventType.UPDATED, actor, changes=diff, reason=payload.reason)
    await _commit(db, risk)
    return _out(risk, await _entity_name(db, risk.entity_id))


@router.post("/risks/{risk_id}/propose-acceptance", dependencies=[Depends(authorize(CAP_EDIT))])
async def propose_acceptance(risk_id: uuid.UUID, payload: ProposeIn, request: Request,
                             db: AsyncSession = Depends(get_db)):
    actor = get_current_user(request)["username"]
    risk = await _load(db, risk_id)
    _check_version(risk, payload.version)
    if risk.status == RiskStatus.CLOSED:
        raise HTTPException(409, "reopen a closed risk first")
    residual = (rs.band(risk.residual_likelihood * risk.residual_impact)
                if risk.residual_likelihood is not None else None)
    problem = rs.acceptance_problem(residual, payload.days)
    if problem:
        raise HTTPException(422, problem)
    before = (risk.treatment, risk.pending_acceptance_by, risk.pending_acceptance_days)
    risk.treatment = Treatment.ACCEPT
    risk.pending_acceptance_by, risk.pending_acceptance_days = actor, payload.days
    _set_status(risk)
    risk.updated_by, risk.updated_at = actor, _utcnow()
    _event(db, risk.id, RiskEventType.ACCEPTANCE_PROPOSED, actor, reason=payload.reason, changes={
        "treatment": (before[0], risk.treatment), "pending_acceptance_by": (before[1], actor),
        "pending_acceptance_days": (before[2], payload.days)})
    await _commit(db, risk)
    return _out(risk, await _entity_name(db, risk.entity_id))


@router.post("/risks/{risk_id}/accept", dependencies=[Depends(authorize(CAP_APPROVE))])
async def accept_risk(risk_id: uuid.UUID, payload: AcceptIn, request: Request,
                      db: AsyncSession = Depends(get_db)):
    actor = get_current_user(request)["username"]
    risk = await _load(db, risk_id)
    _check_version(risk, payload.version)
    if not risk.pending_acceptance_by:
        raise HTTPException(409, "no acceptance has been proposed for this risk")
    if actor == risk.pending_acceptance_by:
        raise HTTPException(403, "the person who proposed an acceptance can't record it (segregation of duties)")
    owner = payload.accepted_by_owner.strip()
    if owner.casefold() != risk.owner.strip().casefold():
        raise HTTPException(422, f"only the risk owner ({risk.owner}) can accept this risk (ISO/IEC 27001 6.1.3 f)")
    residual = (rs.band(risk.residual_likelihood * risk.residual_impact)
                if risk.residual_likelihood is not None else None)
    problem = rs.acceptance_problem(residual, risk.pending_acceptance_days or 0)
    if problem:
        raise HTTPException(422, problem)
    if payload.evidence_chain_id is not None:
        found = (await db.execute(text("SELECT 1 FROM evidence_chain WHERE id = :i"),
                                  {"i": payload.evidence_chain_id})).first()
        if not found:
            raise HTTPException(422, "evidence record not found")

    expires = _utcnow() + timedelta(days=risk.pending_acceptance_days)
    before = {k: getattr(risk, k) for k in ("accepted_by_owner", "acceptance_expires_at", "review_due",
                                           "pending_acceptance_by", "pending_acceptance_days", "status")}
    risk.accepted_by_owner, risk.acceptance_expires_at = owner, expires
    risk.review_due = min(risk.review_due, expires.date())
    risk.pending_acceptance_by = risk.pending_acceptance_days = None
    _set_status(risk)
    risk.updated_by, risk.updated_at = actor, _utcnow()
    _event(db, risk.id, RiskEventType.ACCEPTED, actor, reason=payload.reason,
           changes={k: (b, getattr(risk, k)) for k, b in before.items() if b != getattr(risk, k)},
           accepted_by_owner=owner, expires_at=expires, evidence_chain_id=payload.evidence_chain_id)
    await _commit(db, risk)
    log_security_event(request, "RISK_ACCEPTED",
                       f"Residual risk R-{risk.ref_no:04d} accepted by owner '{owner}', recorded by "
                       f"{actor}, expires {expires.date().isoformat()}")
    return _out(risk, await _entity_name(db, risk.entity_id))


async def _set_closed(risk_id, payload, request, db, closing: bool):
    actor = get_current_user(request)["username"]
    risk = await _load(db, risk_id)
    _check_version(risk, payload.version)
    if closing == (risk.status == RiskStatus.CLOSED):
        raise HTTPException(409, "risk is already closed" if closing else "risk is not closed")
    before = risk.status
    if closing:
        risk.status = RiskStatus.CLOSED
    else:
        risk.status = RiskStatus.IDENTIFIED
        _set_status(risk)
    risk.updated_by, risk.updated_at = actor, _utcnow()
    _event(db, risk.id, RiskEventType.CLOSED if closing else RiskEventType.REOPENED, actor,
           reason=payload.reason, changes={"status": (before, risk.status)})
    await _commit(db, risk)
    return _out(risk, await _entity_name(db, risk.entity_id))


@router.post("/risks/{risk_id}/close", dependencies=[Depends(authorize(CAP_EDIT))])
async def close_risk(risk_id: uuid.UUID, payload: VersionReason, request: Request,
                     db: AsyncSession = Depends(get_db)):
    return await _set_closed(risk_id, payload, request, db, closing=True)


@router.post("/risks/{risk_id}/reopen", dependencies=[Depends(authorize(CAP_EDIT))])
async def reopen_risk(risk_id: uuid.UUID, payload: VersionReason, request: Request,
                      db: AsyncSession = Depends(get_db)):
    return await _set_closed(risk_id, payload, request, db, closing=False)
