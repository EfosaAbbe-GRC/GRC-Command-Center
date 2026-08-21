# Fix: Stage detail panel collapses after every in-panel action

**Status:** ✅ EXECUTED (2026-08-06). Applied exactly as drafted below, no deviations. Rebuilt
`grc-frontend`, re-ran the full boot ritual (smoke 42/42, pytest 32/32) plus a dedicated Playwright
regression (`verify_panel_fix.py`, scratchpad) reproducing the exact bug scenario: panel now stays
open through marking a stage GAP and through signing a risk acceptance, with no re-click needed;
switching to a *different* integration still correctly starts with no stage expanded. 7/7 checks
passed, zero console errors.
**Found:** 2026-08-06, browser-verifying TPRM's UI surfaces (see `TPRM_Roadmap.md`, `MEMORY.md` gotchas)
**File:** `src/terminals/VendorRiskTerminal.jsx`
**Effort:** trivial (one function signature, two call sites)

## The bug

`openIntegration()` unconditionally does `setExpandedStage(null)` and `setStageEvidence({})`. It's
called from two different contexts that need opposite behavior:

1. **Selecting an integration from the left-hand list** (`onClick={() => openIntegration(integ)}`)
   — here, resetting to no-stage-expanded is correct. You just switched integrations; nothing should
   still be open.
2. **Refreshing data after an action taken *inside* an already-expanded stage** — `updateStage()`
   (any pass/gap/review/n-a click) and `RiskAcceptanceModal`'s `onSigned` callback both call
   `openIntegration(selected)` purely to refetch updated summary/stages/acceptances. Because the
   function always resets `expandedStage` to `null`, the panel you were just looking at — the one
   you took the action in — slams shut immediately after. An analyst marking a stage `gap`, then
   trying to attach evidence or sign a risk acceptance, has to re-click the stage row every single
   time. Confirmed live via Playwright this session; not crash-causing, no console error, just a
   real workflow papercut in the module's core loop.

## The fix

Give `openIntegration` an options parameter, defaulting to today's reset behavior, and have the two
"just refreshing after an in-panel action" call sites opt out of the reset.

```diff
--- a/src/terminals/VendorRiskTerminal.jsx
+++ b/src/terminals/VendorRiskTerminal.jsx
@@
-  const openIntegration = async (integ) => {
+  const openIntegration = async (integ, { resetExpanded = true } = {}) => {
     setSelected(integ);
     setActionError(null);
-    setExpandedStage(null);
-    setStageEvidence({});
+    if (resetExpanded) {
+      setExpandedStage(null);
+      setStageEvidence({});
+    }
     const [s, st, ra] = await Promise.all([
       api.get(`/tprm/integrations/${integ.id}/summary`),
       api.get(`/tprm/integrations/${integ.id}/stages`),
       api.get(`/tprm/integrations/${integ.id}/risk-acceptances`),
     ]);
     setSummary(s);
     setStages(st);
     setAcceptances(ra);
   };
@@
     await api.post(`/tprm/integrations/${selected.id}/stages/${stageId}`, { status, evidence_notes });
-    openIntegration(selected);
+    openIntegration(selected, { resetExpanded: false });
   };
```

```diff
--- a/src/terminals/VendorRiskTerminal.jsx  (RiskAcceptanceModal)
+++ b/src/terminals/VendorRiskTerminal.jsx
@@
-        onSigned={async () => { setSigningStage(null); await openIntegration(selected); }}
+        onSigned={async () => { setSigningStage(null); await openIntegration(selected, { resetExpanded: false }); }}
```

The left-hand list's `onClick={() => openIntegration(integ)}` is untouched — it keeps calling with
no second argument, so it defaults to `resetExpanded: true` and preserves today's correct
switch-integrations behavior.

Not touching `stageEvidence` on these two refresh paths is intentional, not just a side effect of
gating it with the same flag: neither a stage-status change nor a risk-acceptance sign-off mutates
evidence, so the cached evidence for the currently-expanded stage stays valid and doesn't need a
refetch.

## Why this shape, not alternatives considered

- **Always preserve `expandedStage` across every `openIntegration` call** (drop the reset entirely)
  — rejected: would leave a stage panel open when you switch to a *different* integration in the
  list, which is a worse bug (stale stage IDs, evidence-fetch mismatch) than the one being fixed.
- **Split into two functions** (`openIntegration` / `refreshIntegration`) — rejected: more surface
  area for a one-line behavioral difference; the default-parameter approach keeps the single
  source-of-truth fetch logic and makes the two intents explicit at each call site instead.

## Verification plan

- `smoke_test.py` (expect 42/42) and `pytest` from `backend/` (expect 32/32) — unaffected, this is a
  frontend-only, no-schema-risk change, but re-run per the boot ritual regardless.
- Re-run the same Playwright flow from the 2026-08-06 browser-verification session (mark a stage
  `gap`, confirm the panel stays open; attach evidence without re-clicking; sign a risk acceptance,
  confirm the panel stays open and shows the "Risk Accepted" block without a re-click) — this is the
  exact scenario the bug was found in, so it's also the exact regression test.
- Manual sanity check: clicking a *different* integration in the left list still correctly starts
  with no stage expanded (confirms `resetExpanded: true` default still fires on that path).
