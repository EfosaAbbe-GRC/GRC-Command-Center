# TPRM Tier 2 · Item 2.2 — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-02). Applied exactly as drafted — frontend-only, no backend/schema
changes needed since 1.1/1.2 already covered the API side. Verified: smoke 42/42, pytest 25/25,
plus a manual end-to-end API check (mark GAP → sign acceptance with the modal's exact payload shape
→ re-fetch list → confirms `gap_description`/`compensating_control`/`accepted_by`/`expires_at` all
round-trip correctly for the detail-panel rendering). **Not independently browser-verified** —
same caveat as 2.1, no browser-automation tool available this session to click through the actual
modal open/submit/close interaction.
**Scope:** `TPRM_Roadmap.md` §2.2 — admin UI to sign a risk acceptance against a GAP stage, plus
visibility into existing acceptances. Both dependencies (1.1 audit logging, 1.2 the read-back
endpoint) already shipped, so this is **frontend-only** — no backend or schema changes.
File touched: `src/terminals/VendorRiskTerminal.jsx`.

**Design call — where the "panel listing existing acceptances" lives:** rather than a separate
top-level list disconnected from the stages, I'm embedding acceptance status directly into each
GAP stage's detail panel (the one 2.1 just added): expand a GAP stage and you either see its signed
acceptance (gap description, compensating control, who/when/expires) or a "Sign Risk Acceptance"
button if none exists yet. This keeps the gap and its resolution state in one place instead of
making you cross-reference two lists. Say so if you want a separate standalone acceptances panel
instead.

---

## `src/terminals/VendorRiskTerminal.jsx`

**New state + fetch acceptances alongside stages/summary:**
```jsx
  const [acceptances, setAcceptances] = useState([]);
  const [signingStage, setSigningStage] = useState(null);

  const openIntegration = async (integ) => {
    setSelected(integ);
    setActionError(null);
    setExpandedStage(null);
    const [s, st, ra] = await Promise.all([
      api.get(`/tprm/integrations/${integ.id}/summary`),
      api.get(`/tprm/integrations/${integ.id}/stages`),
      api.get(`/tprm/integrations/${integ.id}/risk-acceptances`),
    ]);
    setSummary(s);
    setStages(st);
    setAcceptances(ra);
  };
```

**Inside the expanded stage detail block (from 2.1), after the existing `StageDetailField`s, add
acceptance status for GAP stages:**
```jsx
                        {stage.status === 'gap' && (() => {
                          const acc = acceptances.find((a) => a.stage_id === stage.stage_id);
                          if (acc) {
                            return (
                              <div className="pt-1 border-t border-[var(--border-subtle)]">
                                <div className="text-[9px] font-bold text-[var(--warning)] uppercase tracking-widest mb-0.5">Risk Accepted</div>
                                <div className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                                  {acc.gap_description} — compensating control: {acc.compensating_control}
                                </div>
                                <div className="text-[9px] text-[var(--text-tertiary)] font-mono mt-1">
                                  Accepted by {acc.accepted_by} · expires {new Date(acc.expires_at).toLocaleDateString()}
                                </div>
                              </div>
                            );
                          }
                          if (canSignoff) {
                            return (
                              <button onClick={() => setSigningStage(stage)}
                                className="mt-1 px-3 py-1 bg-[var(--warning-subtle)] hover:bg-[var(--warning)] hover:text-black border border-[var(--warning)] text-[var(--warning)] rounded text-[9px] font-bold uppercase tracking-wider transition">
                                Sign Risk Acceptance
                              </button>
                            );
                          }
                          return <div className="text-[10px] text-[var(--text-tertiary)]">Gap open — awaiting admin risk acceptance</div>;
                        })()}
```

**New modal component** (module scope, alongside `CreateIntegrationModal`/`StageDetailField`):
```jsx
function RiskAcceptanceModal({ integrationId, stage, onClose, onSigned }) {
  const [gapDescription, setGapDescription] = useState('');
  const [compensatingControl, setCompensatingControl] = useState('');
  const [expiresInDays, setExpiresInDays] = useState(365);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);

  const submit = async () => {
    setErr(null);
    if (!gapDescription.trim() || !compensatingControl.trim()) {
      setErr('Gap description and compensating control are required');
      return;
    }
    setSubmitting(true);
    try {
      await api.post(`/tprm/integrations/${integrationId}/risk-acceptances`, {
        stage_id: stage.stage_id,
        gap_description: gapDescription,
        compensating_control: compensatingControl,
        expires_in_days: Number(expiresInDays) || 365,
      });
      onSigned();
    } catch (e) {
      setErr(e.message || 'Failed to sign risk acceptance');
    } finally {
      setSubmitting(false);
    }
  };

  const field = "w-full bg-[var(--layer-0)] border border-[var(--border-default)] px-3 py-2 rounded text-[11px] font-mono text-[var(--text-primary)] focus:border-[var(--accent)] outline-none";
  const label = "text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest mb-1 block";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-[480px] max-h-[90vh] overflow-y-auto bg-[var(--layer-1)] border border-[var(--border-emphasis)] rounded-lg shadow-2xl">
        <div className="h-12 border-b border-[var(--border-default)] flex items-center justify-between px-5 bg-[var(--layer-2)]">
          <span className="text-[11px] font-bold uppercase tracking-widest font-display">Sign Risk Acceptance — Stage {stage.stage_number}</span>
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><X size={16} /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <span className={label}>Gap description</span>
            <textarea className={field} rows={3} placeholder="What's the gap?" value={gapDescription} onChange={(e) => setGapDescription(e.target.value)} />
          </div>
          <div>
            <span className={label}>Compensating control</span>
            <textarea className={field} rows={3} placeholder="What mitigates the risk in the meantime?" value={compensatingControl} onChange={(e) => setCompensatingControl(e.target.value)} />
          </div>
          <div>
            <span className={label}>Expires in (days)</span>
            <input type="number" className={field} value={expiresInDays} onChange={(e) => setExpiresInDays(e.target.value)} min={1} max={1095} />
          </div>
          {err && <div className="text-[10px] text-[var(--danger)] font-mono flex items-center gap-2"><AlertTriangle size={12} /> {err}</div>}
        </div>
        <div className="h-14 border-t border-[var(--border-default)] flex items-center justify-end gap-3 px-5 bg-[var(--layer-2)]">
          <button onClick={onClose} className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-wider text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">Cancel</button>
          <button onClick={submit} disabled={submitting}
            className="px-5 py-1.5 bg-[var(--accent-emphasis)] hover:bg-[var(--accent)] text-white rounded-md text-[10px] font-bold uppercase tracking-wider transition active:scale-95 disabled:opacity-50">
            {submitting ? 'Signing…' : 'Sign Acceptance'}
          </button>
        </div>
      </div>
    </div>
  );
}
```
(Styled identically to `CreateIntegrationModal` — same `field`/`label` classes, same overlay/header/
footer structure, just with `textarea` for the two free-text fields.)

**Render the modal** near the existing `showCreate` render block:
```jsx
      {signingStage && (
        <RiskAcceptanceModal
          integrationId={selected.id}
          stage={signingStage}
          onClose={() => setSigningStage(null)}
          onSigned={async () => { setSigningStage(null); await openIntegration(selected); }}
        />
      )}
```

No new backend routes, no new tests needed (the endpoints being called already have full pytest
coverage from 1.1/1.2/1.3's work — this is purely wiring the UI to what already exists and is
already verified server-side).

---

## Verification plan

Frontend-only, no schema/migration risk. Rebuild frontend (+ backend, unchanged, just to keep the
compose stack consistent), smoke + pytest to confirm no regression, and a manual end-to-end check:
mark a stage GAP → sign an acceptance via the new modal → confirm it shows up in the detail panel →
confirm `GET .../risk-acceptances` reflects it.

## Confirm before I execute

1. The embedded-in-stage-detail design (vs. a separate standalone acceptances panel) — OK, or would
   you rather have a dedicated list section?
2. Anything else you want in the modal (e.g. showing the stage's own guidance/evidence-to-collect
   inline as a reminder while signing)?

Reply **EXECUTE** (with any adjustments) and I'll apply, rebuild, and verify.
