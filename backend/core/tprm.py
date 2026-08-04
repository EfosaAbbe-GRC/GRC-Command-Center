"""
backend/core/tprm.py

Third-Party Risk Management (TPRM) — Vendor Data Integration Assessment.
13-stage egress/ingress vendor risk framework.

Integration notes (reconciled to real code):
  - RBAC via the capability policy engine: authorize("TPRM_*").
    Capabilities are seeded in main.py lifespan.
  - Tables auto-create via Base.metadata.create_all in init_db().
    Import this router in main.py BEFORE lifespan runs so the models
    are registered on Base.metadata.
  - risk_acceptances immutability trigger is installed in init_db()
    using fn_prevent_immutability_violation().
"""

from __future__ import annotations

import csv
import enum
import hashlib
import io
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, String, Integer, Text, ForeignKey, DateTime, Enum as SAEnum,
    UniqueConstraint, select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from core.models import Base, EvidenceChain      # Base lives in core.models
from core.database import get_db, audit_logger
from core.auth import authorize, get_current_user, log_security_event
from core.ws import manager


MAX_EVIDENCE_UPLOAD_BYTES = 25 * 1024 * 1024  # 25MB
TPRM_EVIDENCE_DIR = os.path.join("data", "tprm_evidence")
os.makedirs(TPRM_EVIDENCE_DIR, exist_ok=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ───────────────────────────────────────────────────────────────────
class Direction(str, enum.Enum):
    EGRESS = "egress"
    INGRESS = "ingress"


class TransferMethod(str, enum.Enum):
    FILE = "file"
    API = "api"


class RiskTier(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNSCORED = "unscored"


class StageStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    PASS_ = "pass"
    GAP = "gap"
    NOT_APPLICABLE = "not_applicable"


class IntegrationStatus(str, enum.Enum):
    DRAFT = "draft"
    UNDER_ASSESSMENT = "under_assessment"
    APPROVED = "approved"
    APPROVED_WITH_EXCEPTIONS = "approved_with_exceptions"
    BLOCKED = "blocked"


# ── Models ──────────────────────────────────────────────────────────────────
class Vendor(Base):
    __tablename__ = "vendors"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    overall_risk_tier = Column(SAEnum(RiskTier), default=RiskTier.UNSCORED, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    integrations = relationship("Integration", back_populates="vendor", cascade="all, delete-orphan")


class Integration(Base):
    __tablename__ = "integrations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    name = Column(String(255), nullable=False)
    direction = Column(SAEnum(Direction), nullable=False)
    transfer_method = Column(SAEnum(TransferMethod), nullable=False)
    data_classification = Column(String(50))
    volume_per_transfer = Column(Integer)
    involves_regulated_data = Column(String(255))
    computed_risk_tier = Column(SAEnum(RiskTier), default=RiskTier.UNSCORED, nullable=False)
    status = Column(SAEnum(IntegrationStatus), default=IntegrationStatus.DRAFT, nullable=False)
    reassessment_due = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="integrations")
    stage_responses = relationship("StageResponse", back_populates="integration", cascade="all, delete-orphan")
    # NOTE: no delete-orphan — risk_acceptances is append-only; the DB trigger
    # would reject a cascade DELETE and raise. Deletion is not a supported op.
    risk_acceptances = relationship("RiskAcceptance", back_populates="integration")


class AssessmentStage(Base):
    __tablename__ = "assessment_stages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    direction = Column(SAEnum(Direction), nullable=False)
    stage_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    guidance = Column(Text, nullable=False)
    review_questions = Column(Text, nullable=False)
    evidence_to_collect = Column(Text, nullable=False)
    applies_to_methods = Column(String(50), default="both")
    __table_args__ = (UniqueConstraint("direction", "stage_number", name="uq_direction_stage"),)


class StageResponse(Base):
    __tablename__ = "stage_responses"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("assessment_stages.id"), nullable=False)
    status = Column(SAEnum(StageStatus), default=StageStatus.NOT_STARTED, nullable=False)
    evidence_notes = Column(Text)
    reviewed_by = Column(String(255))
    reviewed_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("integration_id", "stage_id", name="uq_integration_stage"),)
    integration = relationship("Integration", back_populates="stage_responses")


class RiskAcceptance(Base):
    """Append-only. init_db() installs UPDATE/DELETE-blocking triggers."""
    __tablename__ = "risk_acceptances"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("assessment_stages.id"), nullable=False)
    gap_description = Column(Text, nullable=False)
    compensating_control = Column(Text, nullable=False)
    accepted_by = Column(String(255), nullable=False)   # from token, not client
    accepted_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    integration = relationship("Integration", back_populates="risk_acceptances")


class StageEvidenceLink(Base):
    """Append-only. init_db() installs UPDATE/DELETE/TRUNCATE-blocking triggers."""
    __tablename__ = "stage_evidence_links"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    integration_id = Column(UUID(as_uuid=True), ForeignKey("integrations.id"), nullable=False)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("assessment_stages.id"), nullable=False)
    evidence_chain_id = Column(Integer, ForeignKey("evidence_chain.id"), nullable=False)
    linked_by = Column(String(255), nullable=False)
    linked_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)


# ── Risk tiering ────────────────────────────────────────────────────────────
REGULATED_KEYWORDS = {"hipaa", "phi", "gdpr", "pci", "pci-dss"}

# Per-tier reassessment cadence (industry standard: risk-proportionate recurrence).
REASSESSMENT_DAYS_BY_TIER = {
    RiskTier.CRITICAL: 90,
    RiskTier.HIGH: 180,
    RiskTier.MEDIUM: 365,
    RiskTier.LOW: 365,
}


def compute_risk_tier(data_classification: str, volume: int, regulated: str) -> RiskTier:
    regulated_l = (regulated or "").lower()
    is_regulated = any(k in regulated_l for k in REGULATED_KEYWORDS)
    classification_l = (data_classification or "").lower()
    high_sensitivity = classification_l in {"pii", "phi", "financial", "credentials"}
    high_volume = (volume or 0) >= 10000
    if is_regulated and high_sensitivity:
        return RiskTier.CRITICAL
    if high_sensitivity and high_volume:
        return RiskTier.HIGH
    if high_sensitivity or is_regulated:
        return RiskTier.MEDIUM
    return RiskTier.LOW


RISK_TIER_SEVERITY = {
    RiskTier.CRITICAL: 4,
    RiskTier.HIGH: 3,
    RiskTier.MEDIUM: 2,
    RiskTier.LOW: 1,
    RiskTier.UNSCORED: 0,
}


async def _recompute_vendor_tier(vendor_id: uuid.UUID, db: AsyncSession) -> None:
    """Vendor.overall_risk_tier = max(severity) across its integrations."""
    result = await db.execute(
        select(Integration.computed_risk_tier).where(Integration.vendor_id == vendor_id)
    )
    tiers = result.scalars().all()
    new_tier = max(tiers, key=lambda t: RISK_TIER_SEVERITY[t]) if tiers else RiskTier.UNSCORED

    vendor = await db.get(Vendor, vendor_id)
    if vendor and vendor.overall_risk_tier != new_tier:
        vendor.overall_risk_tier = new_tier
        await db.commit()


async def _broadcast_reassessment_status() -> None:
    """Nudge connected terminals to re-fetch /reassessments/due and
    /acceptances/expiring. No payload — GOVERNANCE bans setInterval polling
    on the frontend, not a WS-triggered single fetch; keeping the broadcast
    payload-free avoids duplicating those two routes' query logic here."""
    await manager.broadcast({"type": "TPRM_REASSESSMENT_STATUS"})


# ── Schemas ─────────────────────────────────────────────────────────────────
class VendorCreate(BaseModel):
    name: str
    contact_email: Optional[str] = None


class VendorOut(BaseModel):
    id: uuid.UUID
    name: str
    contact_email: Optional[str]
    overall_risk_tier: RiskTier

    class Config:
        from_attributes = True


class IntegrationCreate(BaseModel):
    vendor_id: uuid.UUID
    name: str
    direction: Direction
    transfer_method: TransferMethod
    data_classification: str = Field(..., description="e.g. PII, PHI, financial, public")
    volume_per_transfer: int = 0
    involves_regulated_data: str = "none"


class IntegrationOut(BaseModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    direction: Direction
    transfer_method: TransferMethod
    computed_risk_tier: RiskTier
    status: IntegrationStatus
    reassessment_due: Optional[datetime]

    class Config:
        from_attributes = True


class StageResponseIn(BaseModel):
    status: StageStatus
    evidence_notes: Optional[str] = None


class StageOut(BaseModel):
    stage_id: uuid.UUID
    stage_number: int
    title: str
    status: StageStatus
    evidence_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    guidance: str
    review_questions: str
    evidence_to_collect: str


class RiskAcceptanceIn(BaseModel):
    stage_id: uuid.UUID
    gap_description: str
    compensating_control: str
    expires_in_days: int = Field(365, ge=1, le=1095)
    # accepted_by intentionally absent — taken from the authenticated admin.


class RiskAcceptanceOut(BaseModel):
    id: uuid.UUID
    integration_id: uuid.UUID
    stage_id: uuid.UUID
    gap_description: str
    compensating_control: str
    accepted_by: str
    accepted_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True


class IntegrationSummary(BaseModel):
    integration_id: uuid.UUID
    risk_tier: RiskTier
    status: IntegrationStatus
    total_stages: int
    completed_stages: int
    open_gaps: int
    percent_complete: float


# ── Router ──────────────────────────────────────────────────────────────────
router = APIRouter()

CAP_VIEW = "TPRM_VIEW"
CAP_ASSESS = "TPRM_ASSESS"
CAP_SIGNOFF = "TPRM_SIGNOFF"


@router.post("/vendors", response_model=VendorOut, dependencies=[Depends(authorize(CAP_ASSESS))])
async def create_vendor(payload: VendorCreate, db: AsyncSession = Depends(get_db)):
    vendor = Vendor(name=payload.name, contact_email=payload.contact_email)
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    return vendor


@router.get("/vendors", response_model=List[VendorOut], dependencies=[Depends(authorize(CAP_VIEW))])
async def list_vendors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vendor).order_by(Vendor.created_at.desc()))
    return result.scalars().all()


@router.post("/integrations", response_model=IntegrationOut, dependencies=[Depends(authorize(CAP_ASSESS))])
async def create_integration(
    payload: IntegrationCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user(request)            # dict: {username, role}
    vendor = await db.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    tier = compute_risk_tier(
        payload.data_classification, payload.volume_per_transfer, payload.involves_regulated_data
    )
    integration = Integration(
        vendor_id=payload.vendor_id,
        name=payload.name,
        direction=payload.direction,
        transfer_method=payload.transfer_method,
        data_classification=payload.data_classification,
        volume_per_transfer=payload.volume_per_transfer,
        involves_regulated_data=payload.involves_regulated_data,
        computed_risk_tier=tier,
        status=IntegrationStatus.UNDER_ASSESSMENT,
        reassessment_due=_utcnow() + timedelta(days=REASSESSMENT_DAYS_BY_TIER.get(tier, 365)),
        created_by=current_user["username"],
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    stages_result = await db.execute(
        select(AssessmentStage).where(
            AssessmentStage.direction == payload.direction,
            AssessmentStage.applies_to_methods.in_(["both", payload.transfer_method.value]),
        )
    )
    for stage in stages_result.scalars().all():
        db.add(StageResponse(integration_id=integration.id, stage_id=stage.id))
    await db.commit()

    await _recompute_vendor_tier(integration.vendor_id, db)
    await _broadcast_reassessment_status()
    return integration


@router.get("/integrations", response_model=List[IntegrationOut], dependencies=[Depends(authorize(CAP_VIEW))])
async def list_integrations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Integration).order_by(Integration.created_at.desc()))
    return result.scalars().all()


@router.get(
    "/integrations/{integration_id}/stages",
    response_model=List[StageOut],
    dependencies=[Depends(authorize(CAP_VIEW))],
)
async def get_integration_stages(integration_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            AssessmentStage.id, AssessmentStage.stage_number,
            AssessmentStage.title, StageResponse.status,
            StageResponse.evidence_notes, StageResponse.reviewed_by, StageResponse.reviewed_at,
            AssessmentStage.guidance, AssessmentStage.review_questions, AssessmentStage.evidence_to_collect,
        )
        .join(StageResponse, StageResponse.stage_id == AssessmentStage.id)
        .where(StageResponse.integration_id == integration_id)
        .order_by(AssessmentStage.stage_number)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=404, detail="Integration not found or no stages")
    return [
        StageOut(stage_id=r.id, stage_number=r.stage_number, title=r.title, status=r.status,
                 evidence_notes=r.evidence_notes, reviewed_by=r.reviewed_by, reviewed_at=r.reviewed_at,
                 guidance=r.guidance, review_questions=r.review_questions,
                 evidence_to_collect=r.evidence_to_collect)
        for r in rows
    ]


@router.post(
    "/integrations/{integration_id}/stages/{stage_id}",
    dependencies=[Depends(authorize(CAP_ASSESS))],
)
async def submit_stage_response(
    integration_id: uuid.UUID,
    stage_id: uuid.UUID,
    payload: StageResponseIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user(request)
    result = await db.execute(
        select(StageResponse).where(
            StageResponse.integration_id == integration_id,
            StageResponse.stage_id == stage_id,
        )
    )
    stage_response = result.scalar_one_or_none()
    if not stage_response:
        raise HTTPException(status_code=404, detail="Stage response not found for this integration")

    if payload.status == StageStatus.NOT_APPLICABLE and not (payload.evidence_notes or "").strip():
        raise HTTPException(status_code=422,
            detail="A justification note is required to mark a stage Not Applicable")

    stage_response.status = payload.status
    stage_response.evidence_notes = payload.evidence_notes
    stage_response.reviewed_by = current_user["username"]
    stage_response.reviewed_at = _utcnow()
    await db.commit()

    if payload.status == StageStatus.NOT_APPLICABLE:
        log_security_event(request, "TPRM_STAGE_NOT_APPLICABLE",
            f"Stage {stage_id} on integration {integration_id} marked N/A by "
            f"{current_user['username']}: {payload.evidence_notes}")
    return {"status": "updated"}


@router.post(
    "/integrations/{integration_id}/stages/{stage_id}/evidence",
    dependencies=[Depends(authorize(CAP_ASSESS))],
)
async def upload_stage_evidence(
    integration_id: uuid.UUID,
    stage_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user(request)
    result = await db.execute(
        select(StageResponse).where(
            StageResponse.integration_id == integration_id,
            StageResponse.stage_id == stage_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Stage response not found for this integration")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(contents) > MAX_EVIDENCE_UPLOAD_BYTES:
        raise HTTPException(status_code=413,
            detail=f"File exceeds {MAX_EVIDENCE_UPLOAD_BYTES // (1024*1024)}MB limit")

    file_hash = hashlib.sha256(contents).hexdigest()
    disk_path = os.path.join(TPRM_EVIDENCE_DIR, uuid.uuid4().hex)  # server-generated name only
    with open(disk_path, "wb") as fh:
        fh.write(contents)

    evidence_id = audit_logger.log_evidence(
        filename=file.filename or "unnamed",
        file_hash=file_hash,
        file_size=len(contents),
        source_path=disk_path,
        ingested_by=current_user["username"],
    )

    link = StageEvidenceLink(
        integration_id=integration_id, stage_id=stage_id,
        evidence_chain_id=evidence_id, linked_by=current_user["username"],
    )
    db.add(link)
    await db.commit()

    log_security_event(request, "TPRM_EVIDENCE_LINKED",
        f"Evidence '{file.filename}' (sha256:{file_hash[:16]}...) linked to stage {stage_id} "
        f"on integration {integration_id} by {current_user['username']}")
    return {"status": "evidence linked", "evidence_chain_id": evidence_id, "file_hash": file_hash}


@router.get(
    "/integrations/{integration_id}/stages/{stage_id}/evidence",
    dependencies=[Depends(authorize(CAP_VIEW))],
)
async def list_stage_evidence(integration_id: uuid.UUID, stage_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StageEvidenceLink, EvidenceChain)
        .join(EvidenceChain, EvidenceChain.id == StageEvidenceLink.evidence_chain_id)
        .where(
            StageEvidenceLink.integration_id == integration_id,
            StageEvidenceLink.stage_id == stage_id,
        )
        .order_by(StageEvidenceLink.linked_at.desc())
    )
    return [
        {
            "link_id": str(link.id), "evidence_chain_id": ev.id, "filename": ev.filename,
            "file_hash": ev.file_hash, "file_size_bytes": ev.file_size_bytes,
            "linked_by": link.linked_by, "linked_at": link.linked_at,
        }
        for link, ev in result.all()
    ]


@router.post(
    "/integrations/{integration_id}/risk-acceptances",
    dependencies=[Depends(authorize(CAP_SIGNOFF))],   # admin capability
)
async def create_risk_acceptance(
    integration_id: uuid.UUID,
    payload: RiskAcceptanceIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user = get_current_user(request)
    integration = await db.get(Integration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Validate the target stage actually exists for this integration and is a GAP.
    sr = await db.execute(
        select(StageResponse).where(
            StageResponse.integration_id == integration_id,
            StageResponse.stage_id == payload.stage_id,
        )
    )
    stage_response = sr.scalar_one_or_none()
    if not stage_response:
        raise HTTPException(status_code=404, detail="Stage not part of this integration")
    if stage_response.status != StageStatus.GAP:
        raise HTTPException(status_code=409, detail="Risk acceptance only valid for a GAP stage")

    acceptance = RiskAcceptance(
        integration_id=integration_id,
        stage_id=payload.stage_id,
        gap_description=payload.gap_description,
        compensating_control=payload.compensating_control,
        accepted_by=current_user["username"],           # from token, not payload
        expires_at=_utcnow() + timedelta(days=payload.expires_in_days),
    )
    db.add(acceptance)
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    log_security_event(request, "TPRM_RISK_ACCEPTANCE",
        f"Risk acceptance signed for integration {integration_id}, stage {payload.stage_id}, "
        f"expires {acceptance.expires_at.isoformat()}")
    await _broadcast_reassessment_status()
    return {"status": "risk acceptance recorded", "integration_status": integration.status}


@router.get(
    "/integrations/{integration_id}/risk-acceptances",
    response_model=List[RiskAcceptanceOut],
    dependencies=[Depends(authorize(CAP_VIEW))],
)
async def list_risk_acceptances(integration_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RiskAcceptance)
        .where(RiskAcceptance.integration_id == integration_id)
        .order_by(RiskAcceptance.accepted_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/integrations/{integration_id}/summary",
    response_model=IntegrationSummary,
    dependencies=[Depends(authorize(CAP_VIEW))],
)
async def get_integration_summary(integration_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    integration = await db.get(Integration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    result = await db.execute(
        select(StageResponse).where(StageResponse.integration_id == integration_id)
    )
    responses = result.scalars().all()
    total = len(responses)
    completed = sum(1 for r in responses if r.status in (StageStatus.PASS_, StageStatus.GAP, StageStatus.NOT_APPLICABLE))
    open_gaps = sum(1 for r in responses if r.status == StageStatus.GAP)

    # READ ONLY. Approval is an explicit POST /approve (below).
    return IntegrationSummary(
        integration_id=integration.id,
        risk_tier=integration.computed_risk_tier,
        status=integration.status,
        total_stages=total,
        completed_stages=completed,
        open_gaps=open_gaps,
        percent_complete=round((completed / total * 100), 1) if total else 0.0,
    )


@router.post(
    "/integrations/{integration_id}/approve",
    response_model=IntegrationOut,
    dependencies=[Depends(authorize(CAP_SIGNOFF))],
)
async def approve_integration(integration_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    """Deny-by-default: clean pass -> APPROVED; gaps only if every GAP has a
    live risk acceptance -> APPROVED_WITH_EXCEPTIONS; otherwise 409 BLOCKED."""
    integration = await db.get(Integration, integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    result = await db.execute(
        select(StageResponse).where(StageResponse.integration_id == integration_id)
    )
    responses = result.scalars().all()
    if not responses:
        raise HTTPException(status_code=409, detail="No stage responses to approve")

    unresolved = [r for r in responses if r.status in (StageStatus.NOT_STARTED, StageStatus.IN_REVIEW)]
    if unresolved:
        raise HTTPException(status_code=409, detail=f"{len(unresolved)} stage(s) still not reviewed")

    gap_stage_ids = {r.stage_id for r in responses if r.status == StageStatus.GAP}
    if not gap_stage_ids:
        integration.status = IntegrationStatus.APPROVED
        await db.commit()
        await db.refresh(integration)
        await _recompute_vendor_tier(integration.vendor_id, db)
        await _broadcast_reassessment_status()
        log_security_event(request, "TPRM_APPROVE",
            f"Integration {integration.id} ('{integration.name}') approved clean")
        return integration

    # Every gap must be covered by a non-expired risk acceptance.
    acc_result = await db.execute(
        select(RiskAcceptance).where(RiskAcceptance.integration_id == integration_id)
    )
    now = _utcnow()
    covered = {a.stage_id for a in acc_result.scalars().all() if a.expires_at > now}
    if not gap_stage_ids.issubset(covered):
        integration.status = IntegrationStatus.BLOCKED
        await db.commit()
        log_security_event(request, "TPRM_APPROVE_BLOCKED",
            f"Integration {integration.id} ('{integration.name}') blocked — open gaps without valid risk acceptance")
        raise HTTPException(
            status_code=409,
            detail="Open gaps without a valid risk acceptance — cannot approve",
        )
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    await db.refresh(integration)
    await _recompute_vendor_tier(integration.vendor_id, db)
    await _broadcast_reassessment_status()
    log_security_event(request, "TPRM_APPROVE_WITH_EXCEPTIONS",
        f"Integration {integration.id} ('{integration.name}') approved with exceptions")
    return integration


@router.get("/reassessments/due", dependencies=[Depends(authorize(CAP_VIEW))])
async def get_due_reassessments(db: AsyncSession = Depends(get_db)):
    now = _utcnow()
    result = await db.execute(select(Integration).where(Integration.reassessment_due <= now))
    return [
        {
            "integration_id": str(i.id),
            "name": i.name,
            "vendor_id": str(i.vendor_id),
            "risk_tier": i.computed_risk_tier,
            "reassessment_due": i.reassessment_due,
            "days_overdue": (now - i.reassessment_due).days,
        }
        for i in result.scalars().all()
    ]


@router.get("/acceptances/expiring", dependencies=[Depends(authorize(CAP_VIEW))])
async def get_expiring_acceptances(db: AsyncSession = Depends(get_db)):
    """Read-only: flags APPROVED_WITH_EXCEPTIONS integrations whose covering risk
    acceptance has lapsed. Computed live, no stored-state mutation — mirrors
    the reassessments/due pattern."""
    now = _utcnow()
    result = await db.execute(
        select(Integration, RiskAcceptance)
        .join(RiskAcceptance, RiskAcceptance.integration_id == Integration.id)
        .where(
            Integration.status == IntegrationStatus.APPROVED_WITH_EXCEPTIONS,
            RiskAcceptance.expires_at <= now,
        )
    )
    return [
        {
            "integration_id": str(integration.id),
            "integration_name": integration.name,
            "vendor_id": str(integration.vendor_id),
            "stage_id": str(acceptance.stage_id),
            "acceptance_id": str(acceptance.id),
            "accepted_by": acceptance.accepted_by,
            "expired_at": acceptance.expires_at,
            "days_expired": (now - acceptance.expires_at).days,
        }
        for integration, acceptance in result.all()
    ]


@router.get("/export", dependencies=[Depends(authorize("EVIDENCE_EXPORT"))])
async def export_tprm_csv(db: AsyncSession = Depends(get_db)):
    """Streaming CSV export of the full TPRM assessment register: integrations,
    stage-level assessment detail, and risk acceptances. Mirrors main.py's
    export_compliance_csv (multi-section CSV, StreamingResponse)."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["--- INTEGRATIONS ---"])
    writer.writerow(["Vendor", "Integration", "Direction", "Transfer Method", "Risk Tier",
                      "Status", "Reassessment Due", "Created By", "Created At"])
    result = await db.execute(
        select(Integration, Vendor.name)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .order_by(Vendor.name, Integration.name)
    )
    for integration, vendor_name in result.all():
        writer.writerow([
            vendor_name, integration.name, integration.direction.value,
            integration.transfer_method.value, integration.computed_risk_tier.value,
            integration.status.value,
            integration.reassessment_due.isoformat() if integration.reassessment_due else "",
            integration.created_by, integration.created_at.isoformat(),
        ])

    writer.writerow([])
    writer.writerow(["--- STAGE ASSESSMENTS ---"])
    writer.writerow(["Vendor", "Integration", "Stage #", "Stage Title", "Status",
                      "Evidence Notes", "Reviewed By", "Reviewed At"])
    result = await db.execute(
        select(Vendor.name, Integration.name, AssessmentStage.stage_number,
               AssessmentStage.title, StageResponse.status, StageResponse.evidence_notes,
               StageResponse.reviewed_by, StageResponse.reviewed_at)
        .select_from(StageResponse)
        .join(Integration, Integration.id == StageResponse.integration_id)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .join(AssessmentStage, AssessmentStage.id == StageResponse.stage_id)
        .order_by(Vendor.name, Integration.name, AssessmentStage.stage_number)
    )
    for vendor_name, integ_name, stage_num, title, status, notes, reviewer, reviewed_at in result.all():
        writer.writerow([
            vendor_name, integ_name, stage_num, title, status.value, notes or "",
            reviewer or "", reviewed_at.isoformat() if reviewed_at else "",
        ])

    writer.writerow([])
    writer.writerow(["--- RISK ACCEPTANCES ---"])
    writer.writerow(["Vendor", "Integration", "Stage #", "Stage Title", "Gap Description",
                      "Compensating Control", "Accepted By", "Accepted At", "Expires At"])
    result = await db.execute(
        select(Vendor.name, Integration.name, AssessmentStage.stage_number, AssessmentStage.title,
               RiskAcceptance.gap_description, RiskAcceptance.compensating_control,
               RiskAcceptance.accepted_by, RiskAcceptance.accepted_at, RiskAcceptance.expires_at)
        .select_from(RiskAcceptance)
        .join(Integration, Integration.id == RiskAcceptance.integration_id)
        .join(Vendor, Vendor.id == Integration.vendor_id)
        .join(AssessmentStage, AssessmentStage.id == RiskAcceptance.stage_id)
        .order_by(Vendor.name, Integration.name, RiskAcceptance.accepted_at)
    )
    for vendor_name, integ_name, stage_num, title, gap, control, accepted_by, accepted_at, expires_at in result.all():
        writer.writerow([
            vendor_name, integ_name, stage_num, title, gap, control, accepted_by,
            accepted_at.isoformat(), expires_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tprm_assessment_report.csv"},
    )
