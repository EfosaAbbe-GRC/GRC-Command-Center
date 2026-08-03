# TPRM Tier 1 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-02). All five items applied as drafted below — no changes from
plan. Design call on 1.3 confirmed as read-only (no persisted status flip). 6 new tests added to
`test_tprm.py`; verified smoke 42/42, pytest 21/21 (16 TPRM + 5 IAM regression check), TRUNCATE
triggers confirmed live via `pg_trigger`. See `task.md` P4 and `TPRM_Roadmap.md` for the
checked-off record.
**Scope:** `TPRM_Roadmap.md` Tier 1, items 1.1–1.5, in the confirmed sequence (1.6 is already
done — see roadmap, no action needed). Files touched: `backend/core/tprm.py`,
`backend/core/database.py`, `backend/tests/test_tprm.py` (new coverage for the above).

---

## 1.1 Audit-log the privileged TPRM actions

**Why:** every other privileged action in the app calls `log_security_event` (login, policy
change, password reset). TPRM approve/sign-off currently doesn't — "who approved this vendor,
and when" isn't in the immutable trail.

**`backend/core/tprm.py`** — add the import:
```python
from core.auth import authorize, get_current_user, log_security_event
```

**`approve_integration`** — add `request: Request` param, log on all three outcomes (clean
approve / approved-with-exceptions / blocked):
```python
async def approve_integration(integration_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)):
    ...
    if not gap_stage_ids:
        integration.status = IntegrationStatus.APPROVED
        await db.commit()
        await db.refresh(integration)
        log_security_event(request, "TPRM_APPROVE",
            f"Integration {integration.id} ('{integration.name}') approved clean")
        return integration
    ...
    if not gap_stage_ids.issubset(covered):
        integration.status = IntegrationStatus.BLOCKED
        await db.commit()
        log_security_event(request, "TPRM_APPROVE_BLOCKED",
            f"Integration {integration.id} ('{integration.name}') blocked — open gaps without valid risk acceptance")
        raise HTTPException(status_code=409, detail="Open gaps without a valid risk acceptance — cannot approve")
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    await db.refresh(integration)
    log_security_event(request, "TPRM_APPROVE_WITH_EXCEPTIONS",
        f"Integration {integration.id} ('{integration.name}') approved with exceptions")
    return integration
```

**`create_risk_acceptance`** — already has `request: Request`; add one call after commit:
```python
    db.add(acceptance)
    integration.status = IntegrationStatus.APPROVED_WITH_EXCEPTIONS
    await db.commit()
    log_security_event(request, "TPRM_RISK_ACCEPTANCE",
        f"Risk acceptance signed for integration {integration_id}, stage {payload.stage_id}, "
        f"expires {acceptance.expires_at.isoformat()}")
    return {"status": "risk acceptance recorded", "integration_status": integration.status}
```

---

## 1.2 Read-back for risk acceptances + stage evidence

**Why:** the acceptances table is write-only through the API today. Widen the stage read too, so
who-reviewed/when/with-what-note is retrievable, not just storable.

**New schema + endpoint** (after `RiskAcceptanceIn`):
```python
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
```
```python
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
```

**Widen `StageOut`:**
```python
class StageOut(BaseModel):
    stage_id: uuid.UUID
    stage_number: int
    title: str
    status: StageStatus
    evidence_notes: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
```

**`get_integration_stages`** — select and pass through the extra columns:
```python
    result = await db.execute(
        select(
            AssessmentStage.id, AssessmentStage.stage_number,
            AssessmentStage.title, StageResponse.status,
            StageResponse.evidence_notes, StageResponse.reviewed_by, StageResponse.reviewed_at,
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
                 evidence_notes=r.evidence_notes, reviewed_by=r.reviewed_by, reviewed_at=r.reviewed_at)
        for r in rows
    ]
```
Additive-only — existing tests that read `stage_id`/`title`/`status` off this response are unaffected.

---

## 1.3 Expired-acceptance detection

**Why:** `approve` refuses expired acceptances at approval time, but an integration approved
*yesterday* silently goes non-compliant when its acceptance later lapses — nothing surfaces it
today.

**Design call-out (confirm before EXECUTE):** implementing this as **pure read, no stored-state
mutation** — computed live on every call, exactly like `reassessments/due` already does. The
roadmap's "status re-evaluation" phrase could also mean *persisting* a flip back to `BLOCKED`
when an acceptance lapses; I'd rather not have a `GET` silently mutate rows, and Tier 3 (3.1)
is where this gets pushed to the UI anyway. If you want the persisted-flip behavior instead, say
so and I'll adjust before executing.

```python
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
```

---

## 1.4 `BEFORE TRUNCATE` triggers on the immutable tables

**Why:** row-level `BEFORE UPDATE/DELETE` triggers don't fire on `TRUNCATE` — a real (if
low-likelihood, needs elevated DB privs) hole in the immutability claim.

**`backend/core/database.py`** — add a `FOR EACH STATEMENT` trigger inside each existing `DO`
block (same guarded-idempotent pattern already used there):

Audit logs block — add inside the existing `DO $$ BEGIN ... END $$;`:
```sql
IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_audit_no_truncate') THEN
    CREATE TRIGGER trg_audit_no_truncate BEFORE TRUNCATE ON audit_logs
    FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
END IF;
```

Evidence chain block — same pattern:
```sql
IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_evidence_no_truncate') THEN
    CREATE TRIGGER trg_evidence_no_truncate BEFORE TRUNCATE ON evidence_chain
    FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
END IF;
```

Risk acceptances block — inside the existing table-exists guard:
```sql
IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_risk_acc_no_truncate') THEN
    CREATE TRIGGER trg_risk_acc_no_truncate BEFORE TRUNCATE ON risk_acceptances
    FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_immutability_violation();
END IF;
```
`fn_prevent_immutability_violation()` doesn't reference `NEW`/`OLD`, so it's already compatible
with a statement-level `TRUNCATE` trigger — no change needed to the function itself.

---

## 1.5 Per-tier reassessment cadence

**Why:** every integration currently gets a flat 365-day cadence regardless of tier; a CRITICAL
PHI feed should recur quarterly.

**`backend/core/tprm.py`** — near `compute_risk_tier`:
```python
REASSESSMENT_DAYS_BY_TIER = {
    RiskTier.CRITICAL: 90,
    RiskTier.HIGH: 180,
    RiskTier.MEDIUM: 365,
    RiskTier.LOW: 365,
}
```

**`create_integration`** — replace the hardcoded `365`:
```python
        reassessment_due=_utcnow() + timedelta(days=REASSESSMENT_DAYS_BY_TIER.get(tier, 365)),
```
(`.get(tier, 365)` fallback covers `UNSCORED`, which `compute_risk_tier` never actually returns,
but keeps this defensive rather than a `KeyError` waiting to happen.)

---

## New test coverage (`backend/tests/test_tprm.py`)

Proposed additions, same style/fixtures as the existing suite:

1. **`test_tprm_risk_acceptance_readback`** — sign an acceptance, then `GET .../risk-acceptances`
   and assert it's in the list with the right `accepted_by`/`expires_at`.
2. **`test_tprm_stage_readback_includes_review_metadata`** — set a stage to `pass` with
   `evidence_notes`, re-`GET` stages, assert `evidence_notes`/`reviewed_by`/`reviewed_at` come back
   populated.
3. **`test_tprm_expiring_acceptances`** — sign an acceptance with `expires_in_days=1`... this can't
   actually elapse inside a test run, so instead: assert the endpoint returns `200` and an empty/
   list shape for a fresh non-expired acceptance (behavioral smoke test, not a time-travel test —
   flag if you'd rather skip this one as low-value).
4. **`test_tprm_reassessment_cadence_by_tier`** — create a CRITICAL integration, assert
   `reassessment_due` is ~90 days out (not 365); create a LOW integration, assert ~365 days.
5. **`test_tprm_security_events_logged_on_approve`** — approve an integration as admin, then hit
   whatever the existing security-events read path is (check `main.py`/`database.py` for the
   route before writing this one — didn't want to guess it) and assert a `TPRM_APPROVE*` event
   exists.
6. **`test_tprm_risk_acceptance_truncate_blocked`** — same `docker exec` pattern as the existing
   `test_tprm_risk_acceptance_immutable`, but issuing `TRUNCATE risk_acceptances` instead of
   `UPDATE`, asserting it's rejected.

---

## Confirm before I execute

1. Sequence: apply 1.1 → 1.2 → 1.3 → 1.4 → 1.5 in that order, one `docker compose ... up --build`
   + smoke test after all five (not per-item), matching how the base module shipped?
2. The 1.3 design call-out above (read-only vs. persisted status flip) — read-only unless you say
   otherwise.
3. OK to add the 6 tests above, or ship the endpoint/trigger code only and leave tests for later?

Reply **EXECUTE** (with any adjustments to the above) and I'll apply this to source, rebuild, and
run smoke + pytest to confirm green before reporting back.
