# Fix: `Framework_Mappings` panel has no in-panel honesty label

**Status:** ✅ EXECUTED (2026-08-13). Applied exactly as drafted. Rebuilt `grc-frontend`. Verified via
Playwright: caption renders under `Framework_Mappings`, `REFERENCE_CATALOG` badge and real framework
data unaffected, no layout shift. 5/5 checks passed, zero console errors, zero failed requests.
**Found:** 2026-08-13, closing the loop `ComplianceGrid_Honesty_refactor.md` deliberately left open
("`Framework_Mappings` panel, also fixture-backed — flagged as the same underlying issue but a
separate data source, not touched in this pass").
**File:** `src/terminals/ComplianceTerminal.jsx`
**Scope:** frontend-only, one panel, no backend/schema change.

## What's actually there (re-investigated cold, not assumed from the old flag)

`GET /compliance/frameworks/{policy_id}` returns hand-authored fixture content from
`backend/data/fixtures.json`: 5 policy IDs, each mapped to 3-4 framework controls (NIST 800-53 /
SOC 2 / ISO 27001 / GDPR / ISO 42001) with a `SATISFIED`/`PARTIAL`/`NOT_MET` status. Static, never
computed, never mutated. Rendered only in `ComplianceTerminal.jsx`'s third inspector column — no
other terminal or KPI depends on this data, so blast radius is contained to this one panel.

**This is not the same class of problem the compliance-grid fix addressed.** That fix targeted UI
that *actively claimed* liveness it didn't have — buttons wired to `/ingest` pretending to be
"REMEDIATE_NOW", a fabricated fake incident log. `Framework_Mappings` has neither: it's pure
read-only display, no buttons, no fake timestamps, no invented log lines. A hand-curated
control-mapping matrix (a human judgment call per control) is a legitimate, normal GRC artifact —
unlike a fake "live rescan" button, a static Satisfied/Partial/Not-Met assessment isn't inherently
dishonest.

**The one real gap:** the page's `REFERENCE_CATALOG` badge (command bar) and the "this entry is
illustrative reference data" note (`REFERENCE_ENTRY_DETAIL`, two columns over) both apply to this
panel by inference — same page, same selected policy — but nothing says so *inside* the
`Framework_Mappings` column itself. Worth closing given this UI could plausibly end up on a
screen-share in an interview context where "hand-curated vs. live-computed" is exactly the kind of
distinction that should be stated, not inferred.

## The fix

Add one small caption line under the `Framework_Mappings` header, matching the existing
`REFERENCE_ENTRY_DETAIL` panel's tone/styling (`text-[9px] text-[var(--text-tertiary)] italic`) —
no new component, no new state, no behavior change.

## Diff

```diff
--- a/src/terminals/ComplianceTerminal.jsx
+++ b/src/terminals/ComplianceTerminal.jsx
@@
                     {/* Framework Mapping & Context (4 cols) */}
                     <div className="col-span-4 p-5 flex flex-col overflow-hidden bg-[var(--layer-1)]">
-                        <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-4">
+                        <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-1">
                             Framework_Mappings
                         </h4>
+                        <div className="text-[9px] text-[var(--text-tertiary)] italic mb-3">
+                            Hand-curated reference mapping — not live-computed.
+                        </div>

                         <div className="flex-1 overflow-y-auto space-y-3 pr-1 scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
```

## Verification plan

- No backend changes — `smoke_test.py`/pytest unaffected, rebuild `grc-frontend` only.
- Browser check: open Compliance terminal, select any policy, confirm the new caption renders under
  `Framework_Mappings`, confirm existing framework badges/content unchanged, confirm no layout shift
  in the neighboring two columns, zero console errors.
