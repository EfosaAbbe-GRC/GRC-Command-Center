# TPRM Tier 2 · Item 2.1 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-02). Applied exactly as drafted, no surprises this time (no
schema/enum risk — additive read-only fields only). Verified: smoke 42/42, pytest 25/25 (no new
tests needed — every existing stage-read call already exercises the widened response), plus a
manual API check confirming real guidance/review_questions/evidence_to_collect content flows
through (e.g. stage 1: "Establish what data is leaving, how sensitive it is...").
**Scope:** `TPRM_Roadmap.md` §2.1 — surface each stage's `guidance`, `review_questions`, and
`evidence_to_collect` in the UI (the roadmap's own words: "the seed content is the *product*").
Files touched: `backend/core/tprm.py`, `src/terminals/VendorRiskTerminal.jsx`.

**Design call:** the roadmap says "extend stage read *or* add `GET .../stages/{stage_id}`." Going
with **extend** — widen `StageOut` once more (same move as 1.2) rather than a new per-stage
endpoint, since the guidance/questions/evidence text is small (a sentence or two each per the seed
data) and the UI needs it for every stage in the list anyway once a row expands. A separate endpoint
would just mean an extra round-trip on every expand for no real benefit. Say so if you'd rather have
the dedicated endpoint instead.

---

## 1. `backend/core/tprm.py`

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
    guidance: str
    review_questions: str
    evidence_to_collect: str
```

**`get_integration_stages`** — select and pass through the three new columns:
```python
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
```
Additive-only on the wire — no existing consumer breaks.

---

## 2. `src/terminals/VendorRiskTerminal.jsx`

Turn each stage row into an expand/collapse: click the row to reveal guidance, review questions,
and evidence-to-collect below it; clicking a status button still works without triggering
expand/collapse (stops propagation).

**New state**, alongside the existing ones:
```jsx
  const [expandedStage, setExpandedStage] = useState(null);
```
**Reset it when switching integrations** (in `openIntegration`, alongside the existing `setSummary`/`setStages` calls):
```jsx
    setExpandedStage(null);
```

**Stage row** — replace the current flat row with an expandable one:
```jsx
              {stages.map((stage) => {
                const isExpanded = expandedStage === stage.stage_id;
                return (
                  <div key={stage.stage_id}
                    className="rounded border border-[var(--border-default)] bg-[var(--layer-1)] overflow-hidden">
                    <div
                      className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-[var(--layer-2)] transition"
                      onClick={() => setExpandedStage(isExpanded ? null : stage.stage_id)}
                    >
                      <ChevronRight size={12} className={`text-[var(--text-tertiary)] transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                      <div className="w-6 text-center text-[10px] text-[var(--text-tertiary)] font-mono">{stage.stage_number}</div>
                      {STAGE_ICON[stage.status]}
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] text-[var(--text-secondary)] truncate">{stage.title}</div>
                      </div>
                      {canAssess && (
                        <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                          {['pass', 'gap', 'in_review', 'not_applicable'].map((s) => (
                            <button key={s} onClick={() => updateStage(stage.stage_id, s)}
                              className={`px-2 py-0.5 rounded-sm text-[9px] uppercase font-bold font-mono border transition ${stage.status === s ? 'border-[var(--accent)] text-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'}`}>
                              {s === 'in_review' ? 'review' : s === 'not_applicable' ? 'n/a' : s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    {isExpanded && (
                      <div className="px-4 pb-3 pt-1 space-y-2 border-t border-[var(--border-subtle)] bg-[var(--layer-0)]">
                        <StageDetailField label="Guidance" value={stage.guidance} />
                        <StageDetailField label="Review Questions" value={stage.review_questions} />
                        <StageDetailField label="Evidence to Collect" value={stage.evidence_to_collect} />
                        {stage.evidence_notes && (
                          <StageDetailField label={`Notes${stage.reviewed_by ? ` — ${stage.reviewed_by}` : ''}`} value={stage.evidence_notes} />
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
```

**New small helper component** (module scope, alongside `CreateIntegrationModal`):
```jsx
function StageDetailField({ label, value }) {
  return (
    <div>
      <div className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-0.5">{label}</div>
      <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{value}</div>
    </div>
  );
}
```

Not touched: the N/A justification is still a `window.prompt()` (from 2.4) — the roadmap frames the
*real* form-based version as depending on 2.1's detail panel, but that's a follow-on polish, not
something this item's own scope (surfacing guidance/questions/evidence) requires. Flagging in case
you want it folded in now rather than later.

---

## Verification plan

No schema/migration risk this time (no new columns, no new enum values) — but I'll still rebuild
both containers (frontend changed) and run smoke + pytest to confirm no regression, plus a manual
check that `GET .../stages` now returns the three new fields with real content.

## Confirm before I execute

1. Extend-`StageOut` approach (§ design call above) vs. a dedicated `GET .../stages/{stage_id}`
   endpoint — extend, unless you'd rather have the dedicated route.
2. OK to leave the N/A justification as `window.prompt()` for now (not folding that polish into this
   item), or fold it in while I'm touching this component anyway?

Reply **EXECUTE** (with any adjustments) and I'll apply, rebuild, and verify.
