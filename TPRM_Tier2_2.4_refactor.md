# TPRM Tier 2 · Item 2.4 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-02), with one unplanned fix found during verification (see below).
All items applied as drafted. Verified: smoke 42/42, pytest 25/25 (20 TPRM incl. 4 new, 5 IAM
regression check).

**Bug found & fixed live during verification — Postgres enum widening:** the first pytest run
failed 3/4 new tests with `500 Internal Security middleware error` →
`asyncpg.exceptions.InvalidTextRepresentationError: invalid input value for enum stagestatus:
"NOT_APPLICABLE"`. Root cause: `Base.metadata.create_all()` only *creates* a Postgres enum type if
missing — it never *alters* an already-existing one when a new Python `enum.Enum` member is added
later. This DB's `stagestatus` type was created back when `StageStatus` only had 4 members, so the
new `NOT_APPLICABLE` label didn't exist at the DB layer even though the Python code now emits it.
Confirmed via `pg_enum` directly, fixed live via `ALTER TYPE stagestatus ADD VALUE IF NOT EXISTS
'NOT_APPLICABLE';` (run as a plain top-level statement — this DDL form cannot execute inside a
PL/pgSQL `DO $$ ... $$` block, unlike every other schema-hardening statement in `init_db()`), then
codified into `database.py::init_db()` so any environment self-heals the same way on boot. Not
something the draft could have caught by reading code alone — needed the live DB to surface it.
**Scope:** `TPRM_Roadmap.md` §2.4 — method-based stage applicability + `NOT_APPLICABLE` status
(decision #1). Files touched: `backend/data/seed_tprm_stages.py`, `backend/core/tprm.py`,
`src/terminals/VendorRiskTerminal.jsx`, `backend/tests/test_tprm.py`.

**Pre-check finding (why the seed file needs to change too):** `applies_to_methods` already exists
on `AssessmentStage`, but every one of the 26 seeded stages defaults to `"both"` — the field has
never actually been populated with a real value. Without fixing the seed data, the fan-out filter
below would compile and pass tests but do nothing in practice.

---

## 1. Seed data — mark the two genuinely method-specific stages

Reading the actual stage content, only two of the 26 stages are truly exclusive to one transfer
method: **egress #4 "Authentication (file transfer)"** (SSH keys — a file-transfer concept) and
**egress #6 "Managed file transfer (MFT) platform"** (MFT is inherently file-based; an API
integration wouldn't have this). Nothing else in the egress or ingress lists is method-exclusive by
content — stage 3 ("Secure transport") covers both methods *within* the same stage rather than
requiring one. I'm not inventing extra overrides beyond what the content actually supports.

**`backend/data/seed_tprm_stages.py`** — add an override table instead of touching all 26 tuples:
```python
# Stages whose content is exclusive to one transfer method. Everything else
# defaults to "both" — the seed tuples themselves stay untouched.
METHOD_OVERRIDES = {
    (Direction.EGRESS, 4): "file",   # SSH-key auth is a file-transfer-specific control
    (Direction.EGRESS, 6): "file",   # MFT is a file-transfer-specific platform
}
```

**`seed()`** — the existing docstring says "idempotent: skips insertion if rows already exist,"
which is right for stage *content* (don't clobber a hand-edited stage), but this DB already has all
26 stages seeded at `"both"` from before this field was ever populated — so plain insert-skip would
leave the filter permanently inert on this environment. Narrow fix: reconcile *only*
`applies_to_methods` on existing rows, leave title/guidance/questions/evidence untouched either way:
```python
async def seed():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AssessmentStage))
        existing_by_key = {(r.direction, r.stage_number): r for r in existing.scalars().all()}

        rows_added = 0
        rows_updated = 0
        for direction, stage_list in ((Direction.EGRESS, EGRESS_STAGES), (Direction.INGRESS, INGRESS_STAGES)):
            for stage_number, title, guidance, questions, evidence in stage_list:
                methods = METHOD_OVERRIDES.get((direction, stage_number), "both")
                key = (direction, stage_number)
                if key in existing_by_key:
                    row = existing_by_key[key]
                    if row.applies_to_methods != methods:
                        row.applies_to_methods = methods
                        rows_updated += 1
                    continue
                db.add(AssessmentStage(
                    direction=direction, stage_number=stage_number, title=title,
                    guidance=guidance, review_questions=questions, evidence_to_collect=evidence,
                    applies_to_methods=methods,
                ))
                rows_added += 1

        await db.commit()
        print(f"Seed complete: {rows_added} stage rows added, {rows_updated} updated.")
```

---

## 2. `backend/core/tprm.py`

**(a) New enum value:**
```python
class StageStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_REVIEW = "in_review"
    PASS_ = "pass"
    GAP = "gap"
    NOT_APPLICABLE = "not_applicable"
```
No change needed to `approve_integration`'s gate logic — it already treats anything that's neither
`(NOT_STARTED, IN_REVIEW)` nor `GAP` as resolved-and-clean, which `NOT_APPLICABLE` satisfies by
construction. That's the whole point of decision #1 (uniform gate, proportionality via documented
exclusion, not a special-cased skip path).

**(b) Stage fan-out filter — `create_integration`:**
```python
    stages_result = await db.execute(
        select(AssessmentStage).where(
            AssessmentStage.direction == payload.direction,
            AssessmentStage.applies_to_methods.in_(["both", payload.transfer_method.value]),
        )
    )
```

**(c) Require justification for N/A — `submit_stage_response`:**
```python
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
```
(Only N/A closures are audited here, not every pass/gap toggle — matching the roadmap's stated
reason: "N/A closures should be audited," not a general audit-everything requirement.)

**(d) Found while implementing — `get_integration_summary` undercounts N/A as incomplete:**
```python
    completed = sum(1 for r in responses if r.status in (StageStatus.PASS_, StageStatus.GAP, StageStatus.NOT_APPLICABLE))
```
Not in the original roadmap item, but a direct consequence of it: without this, a fully-resolved
integration with an N/A stage would show e.g. "11/13 complete" in the summary while simultaneously
being approvable — the progress bar would lie. Flagging it here the same way 1.6 documented an
implementation-time find, rather than silently bundling it in.

---

## 3. `src/terminals/VendorRiskTerminal.jsx`

Add an N/A button next to pass/gap/review, with a justification prompt (the roadmap defers the
*polished* stage-detail UI to 2.1, which this depends on for a proper form — using a plain
`window.prompt()` now rather than building a modal that 2.1 would immediately replace):

```jsx
const STAGE_ICON = {
  pass: <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />,
  gap: <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />,
  in_review: <Clock size={14} style={{ color: 'var(--warning)' }} />,
  not_started: <div className="w-3.5 h-3.5 rounded-full border" style={{ borderColor: 'var(--border-emphasis)' }} />,
  not_applicable: <div className="w-3.5 h-3.5 rounded-sm" style={{ backgroundColor: 'var(--text-tertiary)' }} />,
};
```
```jsx
  const updateStage = async (stageId, status) => {
    let evidence_notes;
    if (status === 'not_applicable') {
      const justification = window.prompt('Justification for marking this stage Not Applicable (required):');
      if (!justification || !justification.trim()) return;
      evidence_notes = justification.trim();
    }
    await api.post(`/tprm/integrations/${selected.id}/stages/${stageId}`, { status, evidence_notes });
    openIntegration(selected);
  };
```
```jsx
                      {['pass', 'gap', 'in_review', 'not_applicable'].map((s) => (
                        <button key={s} onClick={() => updateStage(stage.stage_id, s)}
                          className={`px-2 py-0.5 rounded-sm text-[9px] uppercase font-bold font-mono border transition ${stage.status === s ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'}`}>
                          {s === 'in_review' ? 'review' : s === 'not_applicable' ? 'n/a' : s}
                        </button>
                      ))}
```

---

## New test coverage (`backend/tests/test_tprm.py`)

1. **`test_tprm_stage_fanout_by_method`** — create an egress integration with `transfer_method="api"`,
   assert 11 stages (not 13, excluding #4/#6); create one with `transfer_method="file"`, assert 13.
2. **`test_tprm_not_applicable_requires_justification`** — submit `status="not_applicable"` with no
   `evidence_notes` → 422; with a note → 200.
3. **`test_tprm_not_applicable_resolves_and_allows_approval`** — mark one stage N/A (with
   justification), rest `pass`, approve → 200/`approved` (no risk acceptance needed); summary shows
   `completed_stages == total_stages`.
4. **`test_tprm_not_applicable_audited`** — after marking N/A, `GET /admin/audit/security?event_type=TPRM_STAGE_NOT_APPLICABLE`, assert an event referencing the integration exists.

---

## Confirm before I execute

1. The seed-data reconciliation (updating `applies_to_methods` on the 2 already-existing egress
   rows in this DB) — fine to run automatically on next boot via the existing seed-on-lifespan
   convention, or would you rather I do it as an explicit one-off SQL statement so it's visible in
   the session rather than folded into boot logs?
2. `window.prompt()` for the justification field, deferred to a real form at 2.1 — OK, or do you
   want a minimal inline text input on the stage row instead of a browser prompt?
3. Same as Tier 1: one rebuild + smoke/pytest at the end, not per-item?

Reply **EXECUTE** (with any adjustments) and I'll apply, rebuild, and verify.
