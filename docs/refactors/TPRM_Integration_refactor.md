# TPRM Module — Integration Refactor (DRAFT)

**Status:** ✅ APPLIED & LIVE-VERIFIED 2026-07-21. All §1–§5 changes + `TerminalSwitcher`/`App.jsx` registration in source. Static: `py_compile`/`eslint` clean, router imports (8 routes, 5 tables). **Runtime (docker compose v2, backend healthy, 26 stages seeded):** `smoke_test.py` **42/42** (was 27; +15 TPRM), `pytest tests/test_tprm.py` **10/10** — including the `risk_acceptances` UPDATE-blocked trigger firing live. No regression on the existing 27 checks.

**⚠️ Test-isolation caveat (found 2026-07-22):** the `pytest 10/10` and `smoke 42/42` are point-in-time facts about a **shared mutable admin account**. `test_iam_05`/`_07` reset the admin password/`must_change_password` flag and do **not** restore it on failure — a failed `iam_05` leaves admin locked (`mcp=True`), which then 403-cascades every admin-dependent test (all TPRM writes, `iam_09/10`) into a `11 failed / 4 passed` run. This is a **test-suite isolation defect**, not a TPRM or product bug: TPRM is `10/10` whenever admin is unlocked (verified 12/12 alongside `iam_09/10` post-unlock). **✅ RESOLVED 2026-07-22:** root cause was a real product bug — `database.py` wrote tz-aware datetimes into naive `TIMESTAMP` columns, 500-ing `change-password` (forced-reset recovery broken). Fixed via `_naive_utcnow()`; added `conftest.py` isolation guard + `force_reset_util --unlock`. Full suite now **15/15, stable across reruns**, admin ends unlocked. Details in `TPRM_Roadmap.md` §1.6. (Manual recovery, if ever needed again: `UPDATE users SET must_change_password=false WHERE username='admin';` — `users` is not immutable.)

**Enhancement (post-review):** stage seeding moved into `main.py` lifespan (idempotent, alongside user/policy seeding) — no manual `docker exec ... seed` step, even on a fresh DB volume. Verified live: boot log shows `Seed complete: 0 stage rows added` (idempotent), `SELECT count(*) FROM assessment_stages` = 26, tests still 42/42 + 10/10. Windows UTF-8 console fix added to `smoke_test.py`/`test_auth.py`.
**Author:** Claude (review + reconciliation pass)
**Date:** 2026-07-21
**Scope:** Reconcile the delivered TPRM deliverables against the *actual* `GRC_Command_Center` code (not `GOVERNANCE.md`/`CLAUDE.md`, which have drifted).

---

## 0. Why this refactor exists

The delivered files were written against the repo's documentation. The docs disagree with the implementation in three load-bearing places:

| Doc claims | Reality (code) | Consequence |
|---|---|---|
| `require_role("analyst")` RBAC | `authorize("CAPABILITY")` policy-engine ([auth.py:195](backend/core/auth.py#L195)) | ImportError at startup |
| `fn_prevent_audit_modification()` | `fn_prevent_immutability_violation()` ([database.py:81](backend/core/database.py#L81)) | Migration throws "function does not exist" |
| Alembic migrations | `Base.metadata.create_all` in `init_db()`; no alembic installed | `alembic revision` errors |

Plus: `get_current_user` returns a **dict**, the frontend uses **default imports** of **named exports**, `api.js` **already prefixes** `/api/v1`, and **two GET endpoints the UI calls don't exist**. Details in the review above; fixes below.

Design (the 13-stage model + seed content) is kept intact — it's the strong part.

---

## 1. `backend/core/tprm.py` — corrected (full replacement)

Key changes vs. delivered:
- `require_role` → `authorize("TPRM_*")` (capabilities seeded in §3).
- `get_current_user` treated as a **dict**; `created_by`/`reviewed_by` now attributed correctly.
- `accepted_by` derived from the **authenticated admin token**, not client payload.
- Approval logic **moved out of `GET /summary`** into an explicit `POST /approve` (no side effects in GETs, and it's capability-gated).
- Added the two missing read endpoints: `GET /integrations` (list) and `GET /integrations/{id}/stages`.
- Removed dead `required_stage_count`; removed `delete-orphan` cascade on the append-only `risk_acceptances` (conflicts with the immutability trigger).
- tz-aware `datetime.now(timezone.utc)` to match [models.py](backend/core/models.py) / [database.py](backend/core/database.py).

```python
"""
backend/core/tprm.py

Third-Party Risk Management (TPRM) — Vendor Data Integration Assessment.
13-stage egress/ingress vendor risk framework.

Integration notes (reconciled to real code):
  - RBAC via the capability policy engine: authorize("TPRM_*").
    Capabilities are seeded in main.py lifespan (see refactor §3).
  - Tables auto-create via Base.metadata.create_all in init_db().
    Import this router in main.py BEFORE lifespan runs so the models
    are registered on Base.metadata.
  - risk_acceptances immutability trigger is installed in init_db()
    using fn_prevent_immutability_violation() (see refactor §2).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, String, Integer, Text, ForeignKey, DateTime, Enum as SAEnum,
    UniqueConstraint, select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship

from core.models import Base                    # Base lives in core.models
from core.database import get_db
from core.auth import authorize, get_current_user


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


# ── Risk tiering ────────────────────────────────────────────────────────────
REGULATED_KEYWORDS = {"hipaa", "phi", "gdpr", "pci", "pci-dss"}


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


class RiskAcceptanceIn(BaseModel):
    stage_id: uuid.UUID
    gap_description: str
    compensating_control: str
    expires_in_days: int = Field(365, ge=1, le=1095)
    # accepted_by intentionally absent — taken from the authenticated admin.


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
        reassessment_due=_utcnow() + timedelta(days=365),
        created_by=current_user["username"],
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    stages_result = await db.execute(
        select(AssessmentStage).where(AssessmentStage.direction == payload.direction)
    )
    for stage in stages_result.scalars().all():
        db.add(StageResponse(integration_id=integration.id, stage_id=stage.id))
    await db.commit()
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
        )
        .join(StageResponse, StageResponse.stage_id == AssessmentStage.id)
        .where(StageResponse.integration_id == integration_id)
        .order_by(AssessmentStage.stage_number)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=404, detail="Integration not found or no stages")
    return [
        StageOut(stage_id=r.id, stage_number=r.stage_number, title=r.title, status=r.status)
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

    stage_response.status = payload.status
    stage_response.evidence_notes = payload.evidence_notes
    stage_response.reviewed_by = current_user["username"]
    stage_response.reviewed_at = _utcnow()
    await db.commit()
    return {"status": "updated"}


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
    return {"status": "risk acceptance recorded", "integration_status": integration.status}


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
    completed = sum(1 for r in responses if r.status in (StageStatus.PASS_, StageStatus.GAP))
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
async def approve_integration(integration_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
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
        raise HTTPException(
            status_code=409,
            detail="Open gaps without a valid risk acceptance — cannot approve",
        )
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    await db.refresh(integration)
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
```

---

## 2. `backend/core/database.py` — add the trigger to `init_db()` (diff)

Fold the immutability trigger into the existing hardening block using the **real** function name, so it's applied on every boot (never a forgotten manual step). Insert after the evidence-chain block at [database.py:115](backend/core/database.py#L115):

```python
                # 4. Risk acceptances (TPRM) — block UPDATE and DELETE
                await conn.execute(text("""
                    DO $$ BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables
                                   WHERE table_name = 'risk_acceptances') THEN
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_update') THEN
                                CREATE TRIGGER trg_risk_acc_no_update BEFORE UPDATE ON risk_acceptances
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_delete') THEN
                                CREATE TRIGGER trg_risk_acc_no_delete BEFORE DELETE ON risk_acceptances
                                FOR EACH ROW EXECUTE FUNCTION fn_prevent_immutability_violation();
                            END IF;
                        END IF;
                    END $$;
                """))
```

> The `IF EXISTS ... table` guard means the block is safe even before the TPRM models are registered. Because `create_all` runs first in the same `init_db()`, the table will exist by this point once the router is imported (§3).

---

## 3. `backend/main.py` — router + seeded capabilities (diff)

**(a)** Register the router. Add near the other imports (top of file) and after `app` is built:

```python
from core.tprm import router as tprm_router      # also registers TPRM models on Base.metadata
...
app.include_router(tprm_router, prefix="/api/v1/tprm", tags=["tprm"])
```

> Import at module top ensures the models exist on `Base.metadata` **before** `lifespan` → `init_db()` → `create_all` runs.

**(b)** Seed the three capabilities so the policy engine doesn't deny-by-default. Add to the `policies` list at [main.py:74](backend/main.py#L74):

```python
        ("TPRM_VIEW",     "View third-party risk assessments",           "analyst"),
        ("TPRM_ASSESS",   "Create/score integrations and submit stages", "analyst"),
        ("TPRM_SIGNOFF",  "Sign risk acceptances and approve integrations", "admin"),
```

---

## 4. `tprm_migration.sql` — reduced to indexes only

Triggers now live in `init_db()` (§2), so the migration file is **indexes only**. Drop the trigger/`CREATE FUNCTION` blocks entirely:

```sql
-- tprm_migration.sql — supplemental indexes (triggers are installed in init_db()).
CREATE INDEX IF NOT EXISTS idx_integrations_reassessment_due ON integrations (reassessment_due);
CREATE INDEX IF NOT EXISTS idx_stage_responses_integration   ON stage_responses (integration_id);
CREATE INDEX IF NOT EXISTS idx_risk_acceptances_integration  ON risk_acceptances (integration_id);
```

`seed_tprm_stages.py` is **kept as delivered** — it's correct and self-consistent (its `AssessmentStage`/`Direction` import now resolves against the corrected `tprm.py`). No changes needed.

---

## 5. `src/terminals/VendorRiskTerminal.jsx` — corrected + completed (full replacement)

Fixes vs. delivered: **named** imports (`{ api }`, `{ StatusBadge }`); paths **without** the `/api/v1` prefix (api.js adds it); status normalized to the uppercase keys `StatusBadge` expects. **Now folded in:** the New Integration create modal (vendor picker + inline new-vendor + `POST /tprm/integrations`), the admin **Approve** button wired to `POST /tprm/integrations/{id}/approve` with 409 surfacing, role-gated actions via `useAuth`, and a full **tokenization pass** (`var(--layer-*)` / `var(--accent)` / `var(--success|warning|danger)`) so it matches the design system — see §5a.

### §5a Why tokens, not raw hex (design decision)

`GOVERNANCE.md` §3 requires semantic color variables and forbids design degradation; the delivered file used a *parallel* palette of hardcoded Tailwind hex (`text-red-400`, `bg-gray-900`, `text-blue-500`). That would: (1) not respond to token retuning, (2) drift from every other terminal, (3) violate the design-token non-negotiable. The rewrite below maps every color to the existing token set (risk tiers → `--danger/--warning/--accent/--success/--text-tertiary`; stage icons → semantic vars; status badge via the existing `StatusBadge` config keys).

```jsx
import React, { useState } from 'react';
import { Shield, AlertTriangle, CheckCircle2, Clock, ChevronRight, Plus, X, ShieldCheck } from 'lucide-react';
import { useApiData } from '../hooks/useApiData';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../contexts/useAuth';

const TIER_STYLE = {
  critical: { color: 'var(--danger)', bg: 'var(--danger-subtle)' },
  high:     { color: 'var(--warning)', bg: 'var(--warning-subtle)' },
  medium:   { color: 'var(--accent)', bg: 'var(--accent-subtle)' },
  low:      { color: 'var(--success)', bg: 'var(--success-subtle)' },
  unscored: { color: 'var(--text-tertiary)', bg: 'var(--layer-2)' },
};

const STAGE_ICON = {
  pass: <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />,
  gap: <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />,
  in_review: <Clock size={14} style={{ color: 'var(--warning)' }} />,
  not_started: <div className="w-3.5 h-3.5 rounded-full border" style={{ borderColor: 'var(--border-emphasis)' }} />,
};

// Map backend integration status -> StatusBadge's uppercase config keys.
const STATUS_BADGE_KEY = {
  approved: 'COMPLETED',
  approved_with_exceptions: 'PARTIAL',
  under_assessment: 'REVIEW',
  blocked: 'FAILED',
  draft: 'QUEUED',
};

const EMPTY_FORM = {
  vendor_id: '', name: '', direction: 'egress', transfer_method: 'file',
  data_classification: 'PII', volume_per_transfer: 0, involves_regulated_data: 'none',
};

export default function VendorRiskTerminal() {
  const { user } = useAuth();
  const role = user?.role;
  const canAssess = role === 'analyst' || role === 'admin';
  const canSignoff = role === 'admin';

  const { data: integrations, loading, refresh } = useApiData('/tprm/integrations');
  const { data: vendors } = useApiData('/tprm/vendors');

  const [selected, setSelected] = useState(null);
  const [summary, setSummary] = useState(null);
  const [stages, setStages] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [actionError, setActionError] = useState(null);

  const openIntegration = async (integ) => {
    setSelected(integ);
    setActionError(null);
    const [s, st] = await Promise.all([
      api.get(`/tprm/integrations/${integ.id}/summary`),
      api.get(`/tprm/integrations/${integ.id}/stages`),
    ]);
    setSummary(s);
    setStages(st);
  };

  const updateStage = async (stageId, status) => {
    await api.post(`/tprm/integrations/${selected.id}/stages/${stageId}`, { status });
    openIntegration(selected);
  };

  const approve = async () => {
    setActionError(null);
    try {
      await api.post(`/tprm/integrations/${selected.id}/approve`, {});
      await openIntegration(selected);
      refresh();
    } catch (err) {
      setActionError(err.message || 'Approval blocked');
    }
  };

  return (
    <div className="flex-1 flex bg-[var(--layer-0)] text-[var(--text-primary)] overflow-hidden h-full">
      {/* LEFT: integration list */}
      <div className="w-[380px] border-r border-[var(--border-default)] flex flex-col min-h-0 bg-[var(--layer-1)]">
        <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-4 shrink-0">
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-[var(--accent)]" />
            <h2 className="text-[11px] font-bold tracking-widest uppercase font-display">Vendor Risk Assessments</h2>
          </div>
          {canAssess && (
            <button
              onClick={() => { setShowCreate(true); setActionError(null); }}
              className="p-1.5 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded transition"
              title="New Integration"
            >
              <Plus size={14} />
            </button>
          )}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
          {loading && <div className="p-4 text-[10px] text-[var(--text-tertiary)] font-mono uppercase tracking-widest animate-pulse">Loading integrations…</div>}
          {!loading && integrations?.length === 0 && (
            <div className="p-4 text-[10px] text-[var(--text-tertiary)]">No integrations tracked yet. Add one to begin an assessment.</div>
          )}
          {integrations?.map((integ) => {
            const tier = TIER_STYLE[integ.computed_risk_tier] || TIER_STYLE.unscored;
            return (
              <button
                key={integ.id}
                onClick={() => openIntegration(integ)}
                className={`w-full text-left px-4 py-3 border-b border-[var(--border-subtle)] hover:bg-[var(--layer-2)] transition flex items-center justify-between ${selected?.id === integ.id ? 'bg-[var(--layer-2)]' : ''}`}
              >
                <div className="min-w-0">
                  <div className="text-[12px] text-[var(--text-primary)] truncate font-bold">{integ.name}</div>
                  <div className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest mt-0.5 font-mono">
                    {integ.direction} · {integ.transfer_method}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="px-2 py-0.5 rounded-sm text-[9px] font-bold uppercase font-mono border"
                    style={{ color: tier.color, backgroundColor: tier.bg, borderColor: tier.color }}>
                    {integ.computed_risk_tier}
                  </span>
                  <ChevronRight size={14} className="text-[var(--text-tertiary)]" />
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* RIGHT: detail */}
      <div className="flex-1 flex flex-col min-w-0 bg-[var(--layer-0)]">
        {!selected && (
          <div className="flex-1 flex items-center justify-center text-[var(--text-tertiary)] text-[11px] font-mono uppercase tracking-widest">
            Select an integration to review its assessment
          </div>
        )}

        {selected && summary && (
          <>
            <div className="h-14 border-b border-[var(--border-default)] flex items-center justify-between px-6 bg-[var(--layer-1)] shrink-0">
              <div>
                <h3 className="text-[var(--text-primary)] font-bold text-xs font-display tracking-wide">{selected.name}</h3>
                <div className="text-[9px] text-[var(--text-tertiary)] uppercase tracking-widest font-mono mt-0.5">
                  {summary.completed_stages}/{summary.total_stages} stages reviewed
                  {summary.open_gaps > 0 && (
                    <span className="text-[var(--danger)] ml-2">· {summary.open_gaps} open gap(s)</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={STATUS_BADGE_KEY[summary.status] || 'QUEUED'} variant="large" />
                {canSignoff && (
                  <button
                    onClick={approve}
                    className="flex items-center gap-2 px-4 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95"
                  >
                    <ShieldCheck size={13} strokeWidth={2.5} /> Approve
                  </button>
                )}
              </div>
            </div>

            {actionError && (
              <div className="px-6 py-2 bg-[var(--danger-subtle)] border-b border-[var(--danger)] text-[10px] text-[var(--danger)] font-mono flex items-center gap-2">
                <AlertTriangle size={12} /> {actionError}
              </div>
            )}

            <div className="flex-1 overflow-y-auto p-6 space-y-1 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
              {stages.map((stage) => (
                <div key={stage.stage_id}
                  className="flex items-center gap-3 px-3 py-2 rounded border border-[var(--border-default)] bg-[var(--layer-1)]">
                  <div className="w-6 text-center text-[10px] text-[var(--text-tertiary)] font-mono">{stage.stage_number}</div>
                  {STAGE_ICON[stage.status]}
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] text-[var(--text-secondary)] truncate">{stage.title}</div>
                  </div>
                  {canAssess && (
                    <div className="flex gap-1">
                      {['pass', 'gap', 'in_review'].map((s) => (
                        <button key={s} onClick={() => updateStage(stage.stage_id, s)}
                          className={`px-2 py-0.5 rounded-sm text-[9px] uppercase font-bold font-mono border transition ${stage.status === s ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'}`}>
                          {s === 'in_review' ? 'review' : s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {showCreate && (
        <CreateIntegrationModal
          vendors={vendors || []}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); refresh(); }}
        />
      )}
    </div>
  );
}

function CreateIntegrationModal({ vendors, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [newVendor, setNewVendor] = useState(vendors.length === 0);
  const [vendorName, setVendorName] = useState('');
  const [vendorEmail, setVendorEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    setErr(null);
    setSubmitting(true);
    try {
      let vendorId = form.vendor_id;
      if (newVendor) {
        if (!vendorName.trim()) throw new Error('Vendor name is required');
        const v = await api.post('/tprm/vendors', { name: vendorName, contact_email: vendorEmail || null });
        vendorId = v.id;
      }
      if (!vendorId) throw new Error('Select or create a vendor');
      if (!form.name.trim()) throw new Error('Integration name is required');
      await api.post('/tprm/integrations', {
        vendor_id: vendorId,
        name: form.name,
        direction: form.direction,
        transfer_method: form.transfer_method,
        data_classification: form.data_classification,
        volume_per_transfer: Number(form.volume_per_transfer) || 0,
        involves_regulated_data: form.involves_regulated_data,
      });
      onCreated();
    } catch (e) {
      setErr(e.message || 'Create failed');
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full bg-[var(--layer-0)] border border-[var(--border-default)] px-3 py-2 rounded text-[11px] font-mono text-[var(--text-primary)] focus:border-[var(--accent)] outline-none";
  const label = "text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-[520px] max-h-[90vh] overflow-y-auto bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded-lg shadow-2xl">
        <div className="h-12 border-b border-[var(--border-default)] flex items-center justify-between px-5 bg-[var(--layer-2)]">
          <span className="text-[11px] font-bold uppercase tracking-widest font-display">New Integration</span>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>

        <div className="p-5 space-y-4">
          {/* Vendor */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className={label}>Vendor</span>
              <button onClick={() => setNewVendor((v) => !v)}
                className="text-[9px] text-[var(--accent)] uppercase tracking-widest font-bold">
                {newVendor ? 'Pick existing' : '+ New vendor'}
              </button>
            </div>
            {newVendor ? (
              <div className="space-y-2">
                <input className={field} placeholder="Vendor name" value={vendorName} onChange={(e) => setVendorName(e.target.value)} />
                <input className={field} placeholder="Contact email (optional)" value={vendorEmail} onChange={(e) => setVendorEmail(e.target.value)} />
              </div>
            ) : (
              <select className={field} value={form.vendor_id} onChange={set('vendor_id')}>
                <option value="">— select vendor —</option>
                {vendors.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
              </select>
            )}
          </div>

          <div>
            <span className={label}>Integration name</span>
            <input className={field} placeholder="e.g. Daily customer enrichment feed" value={form.name} onChange={set('name')} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className={label}>Direction</span>
              <select className={field} value={form.direction} onChange={set('direction')}>
                <option value="egress">Egress (data leaving)</option>
                <option value="ingress">Ingress (data arriving)</option>
              </select>
            </div>
            <div>
              <span className={label}>Transfer method</span>
              <select className={field} value={form.transfer_method} onChange={set('transfer_method')}>
                <option value="file">File</option>
                <option value="api">API</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className={label}>Data classification</span>
              <select className={field} value={form.data_classification} onChange={set('data_classification')}>
                {['PII', 'PHI', 'financial', 'credentials', 'public'].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <span className={label}>Volume / transfer</span>
              <input type="number" className={field} value={form.volume_per_transfer} onChange={set('volume_per_transfer')} />
            </div>
          </div>

          <div>
            <span className={label}>Regulated data</span>
            <input className={field} placeholder='e.g. "HIPAA, GDPR" or "none"' value={form.involves_regulated_data} onChange={set('involves_regulated_data')} />
          </div>

          {err && <div className="text-[10px] text-[var(--danger)] font-mono flex items-center gap-2"><AlertTriangle size={12} /> {err}</div>}
        </div>

        <div className="h-14 border-t border-[var(--border-default)] flex items-center justify-end gap-3 px-5 bg-[var(--layer-2)]">
          <button onClick={onClose} className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">Cancel</button>
          <button onClick={submit} disabled={submitting}
            className="px-5 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95 disabled:opacity-50">
            {submitting ? 'Creating…' : 'Create & Assess'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

> Notes: the risk **tier is not shown in the modal** — it's computed server-side from classification + volume + regulated flags and appears on the list row after creation. The create form requires a vendor; if none exist, it opens straight into new-vendor mode. Approve/assess controls are role-gated in the UI (`canAssess`/`canSignoff`) *and* enforced server-side by `authorize(...)` — the UI gate is convenience, the backend is the real boundary.

---

## 6. Verification checklist (post-EXECUTE)

```bash
# Backend imports & boots (the require_role ImportError is gone)
cd backend && python -c "from core.tprm import router; print('router ok')"
docker compose -f docker-compose-v2.yml up --build

# Reference stages now AUTO-SEED on backend startup (main.py lifespan),
# idempotently — no manual step, even on a fresh DB volume. The standalone
# script still works for CI / manual re-checks:
docker exec grc-backend python -m data.seed_tprm_stages   # idempotent; "0 rows added" once seeded

# Smoke (as admin): vendor -> integration -> stages -> summary -> approve
#   confirm GET /api/v1/tprm/integrations returns the list (no double prefix)
#   confirm risk_acceptances UPDATE is rejected by the trigger:
#   psql> UPDATE risk_acceptances SET gap_description='x';  -- expect SECURITY exception
```

Frontend: `VendorRiskTerminal` is registered in [TerminalSwitcher.jsx](src/components/TerminalSwitcher.jsx) (nav) and [App.jsx](src/App.jsx) (route) as the `TPRM` / "VENDOR RISK" terminal (minRole analyst).

**Smoke coverage (added):** `backend/tests/smoke_test.py` gained a TPRM section (§14) mirroring the existing security discipline — unauthenticated 401, viewer→403 on `TPRM_VIEW`, analyst→403 on `TPRM_SIGNOFF` (approve + risk-acceptance), deny-by-default approval 409 while stages pending, full vendor→integration→stages→GAP→risk-acceptance lifecycle, computed-tier assertion (PHI+HIPAA→CRITICAL), and a `risk_acceptances` UPDATE-blocked immutability probe (parity with the `audit_logs` trigger test). Healthy baseline moves **27/27 → 42/42**.

**Pytest coverage (added):** `backend/tests/test_tprm.py` — 10 pytest cases (auth 401, viewer/analyst RBAC boundaries, admin-only sign-off, risk tiering across all four tiers, deny-by-default → clean approve, gap-requires-acceptance path, 422 input validation, risk-acceptance target 404/409, and DB-layer immutability). Skips (not fails) when the backend is unreachable. `pyproject.toml` fixed: `ignore=` (silently invalid) → `addopts="--ignore=tests/smoke_test.py"`, so `pytest tests/` now collects 15 cleanly (5 IAM + 10 TPRM).

Run tests (stack up):

```bash
python backend/tests/smoke_test.py                 # expect 42/42
cd backend && pytest tests/test_tprm.py -v          # expect 10 passed (host needs `requests`, `pytest`, docker on PATH)
```

---

## 7. Summary of files touched (on EXECUTE)

| File | Action |
|---|---|
| `backend/core/tprm.py` | **new**, corrected (auth, attribution, endpoints, approve) |
| `backend/core/database.py` | **edit** — trigger block in `init_db()` (§2) |
| `backend/main.py` | **edit** — router include + 3 seeded capabilities (§3) |
| `backend/migrations/tprm_migration.sql` | **new**, indexes only (§4) |
| `backend/data/seed_tprm_stages.py` | **new**, as delivered (unchanged) |
| `src/terminals/VendorRiskTerminal.jsx` | **new**, corrected imports/paths/status (§5) |
| `src/components/TerminalSwitcher.jsx` | **edit** — register terminal |

**✅ Applied.** Remaining runtime gate: boot under `docker compose -f docker-compose-v2.yml up --build`, then `python -m data.seed_tprm_stages` (expect 26 rows), then the smoke sequence in §6.
