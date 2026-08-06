# Fix: ComplianceTerminal's misleading "live scanning" UI

**Status:** ✅ EXECUTED (2026-08-06). Applied exactly as drafted, no deviations. Rebuilt
`grc-frontend`. Verified via Playwright: `REFERENCE_CATALOG` badge visible, the fabricated incident
log ("Security policy threshold breach", "Accessing encrypted node...") confirmed gone, the honest
static note renders in its place, no `REMEDIATE_NOW`/`TRIGGER_RESCAN`/`Update Policy` buttons remain
for admin users, and untouched functionality (search, CSV export, real `DATA_STRUCTURE_VIEW`,
`Framework_Mappings`) all still work. 10/10 checks passed, zero console errors.
**Found:** 2026-08-06, scoping what a "real" fix for `ComplianceTerminal.jsx`'s fixture-fake policy
grid would look like (flagged while scoping Agent Registry De-stubbing earlier the same day).
**File:** `src/terminals/ComplianceTerminal.jsx`
**Scope:** confirmed with user — stop the misleading interactive elements and clearly label the
grid as reference/demo data; do NOT attempt real cloud-infrastructure scanning (no real AWS/IAM/etc.
backing exists in this project, and building fake integration would just be a different flavor of
the same problem).

## What's actually there today

`GET /compliance/policies` returns 5 hardcoded fixture rows (`data_service.cached_policies`, loaded
once from `fixtures.json`, never mutated) representing infrastructure/cloud compliance controls —
`AWS_S3_Encryption_v1`, `GDPR_Data_Retention_v1`, `SOC2_Access_Control_v1`,
`ISO27001_Risk_Assessment_v1`, `IAM_Root_MFA_Enforcement_v1` — with static `compliance` percentages
and `last_scan` timestamps ("12m ago") that never change no matter how long the server has been up.

That alone would just be static demo data, same shape as `/ops/jobs` was before Execution Monitor
UI. What makes this worse: the UI actively invites the user to interact with it as if it's live —

- **`handleTriggerRescan`** (bound to the "Update Policy" button) and **`handleRemediate`** (bound
  to the "REMEDIATE_NOW"/"TRIGGER_RESCAN" button) both call `api.post('/ingest')` — the RAG document
  re-indexing endpoint. Clicking "REMEDIATE_NOW" on the `FAIL`-status `IAM_Root_MFA_Enforcement_v1`
  policy does nothing about IAM or MFA; it re-ingests PDFs, waits a scripted 2-second
  `setTimeout`, then re-fetches the same static fixture. The displayed compliance score can never
  change.
- **The "OPERATIONAL_EVIDENCE_STREAM" panel** in the inspector drawer is a hardcoded, static block
  of fake timestamped log lines — "Accessing encrypted node configuration pool...", "Cross-
  referencing telemetry (v1.2.4-stable)", and for any `FAIL`-status policy, a fabricated incident:
  "Security policy threshold breach (Found: 644)". These render identically for every policy
  (only the id substitutes in) and never reflect anything real. This is the same fabricated-console
  pattern already fixed in `OpsTerminal.jsx` during Execution Monitor UI — just not caught there
  since it's a different terminal.

## The fix

Not a data/backend change — this is entirely about not letting the UI claim capabilities that don't
exist, per the confirmed scope.

1. **Add a small, honest label** in the command bar so the grid doesn't read as live: e.g. a
   `REFERENCE_CATALOG` badge next to `POLICY_GRID_CONTROL`, styled consistently with existing
   terminal badges (matches the pattern already used for `SECURED_SESSION`/`ACTIVE_ENFORCEMENT`
   elsewhere in the app).
2. **Remove `handleTriggerRescan` and `handleRemediate`**, and the two buttons that call them.
   Replace that action slot with a static note explaining what the panel actually is, rather than
   leaving an empty gap or a disabled-looking control.
3. **Replace the fabricated `OPERATIONAL_EVIDENCE_STREAM` log block** with an honest static
   explanation (this is fixture/reference data, not live telemetry) instead of fake timestamped
   incident lines. Keep the panel's visual shell (same column, same header icon/label) so the layout
   doesn't shift — only the fabricated content changes.

Everything else is untouched: the real `DATA_STRUCTURE_VIEW` (genuinely shows the real fixture
object via `JSON.stringify`), the `Framework_Mappings` panel (also fixture-backed — flagged as the
same underlying issue but a separate data source, not touched in this pass to keep scope to what was
approved), the CSV export, search, and the real WebSocket connection indicator (the WS connection
itself is real; only relabeling what it's monitoring is out of scope here).

## Diff

```diff
--- a/src/terminals/ComplianceTerminal.jsx
+++ b/src/terminals/ComplianceTerminal.jsx
@@
-    const handleTriggerRescan = async () => {
-        if (!isAdmin) return;
-        try {
-            await api.post('/ingest');
-            refresh();
-        } catch (err) {
-            console.error("Rescan trigger failed:", err);
-        }
-    };
-
-    const handleRemediate = async () => {
-        if (!isAdmin) return;
-        setRemediating(true);
-        try {
-            await api.post('/ingest');
-            setTimeout(() => {
-                refresh();
-                setRemediating(false);
-            }, 2000);
-        } catch (err) {
-            console.error("Remediation failed:", err);
-            setRemediating(false);
-        }
-    };
-
     const activePolicy = (policies && policies.length > 0) ? (policies.find(p => p.id === selectedId) || policies[0]) : {};
```

(`remediating` state is also removed — it was only ever set by `handleRemediate`.)

```diff
                     <span className="text-[var(--text-primary)] font-bold tracking-widest text-xs font-display">POLICY_GRID_CONTROL</span>
+                    <span className="px-2 py-0.5 rounded-sm border text-[9px] font-bold uppercase font-mono tracking-widest"
+                        style={{ borderColor: 'var(--text-tertiary)', color: 'var(--text-tertiary)' }}
+                        title="Illustrative reference data -- not connected to live infrastructure scanning">
+                        REFERENCE_CATALOG
+                    </span>
                     <div className="h-6 w-px bg-[var(--border-subtle)]" />
```

```diff
                     <div className="col-span-4 p-5 space-y-3 overflow-y-auto border-r border-[var(--border-default)] scrollbar-thin scrollbar-thumb-[var(--layer-4)]">
                         <h4 className="text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-[0.2em] mb-3 flex items-center gap-1.5">
-                            <Terminal size={11} className="text-[var(--accent)]" /> OPERATIONAL_EVIDENCE_STREAM
+                            <Terminal size={11} className="text-[var(--accent)]" /> REFERENCE_ENTRY_DETAIL
                         </h4>
-                        <div className="font-mono text-[9px] leading-relaxed space-y-1.5">
-                            <div className="flex gap-3"><span className="text-[var(--text-tertiary)] opacity-30">001</span> <span>[10:42:01]</span> <span className="text-[var(--success)] font-bold">INIT</span> <span>Accessing encrypted node configuration pool...</span></div>
-                            <div className="flex gap-3"><span className="text-[var(--text-tertiary)] opacity-30">002</span> <span>[10:42:02]</span> <span className="text-[var(--accent)] font-bold">INFO</span> <span>Policy {activePolicy.id} validator active.</span></div>
-                            <div className="flex gap-3"><span className="text-[var(--text-tertiary)] opacity-30">003</span> <span>[10:42:02]</span> <span className="text-[var(--accent)] font-bold">INFO</span> <span>Cross-referencing telemetry (v1.2.4-stable).</span></div>
-                            {activePolicy.status === 'FAIL' && (
-                                <>
-                                    <div className="flex gap-3 text-[var(--danger)] bg-[var(--danger-subtle)] animate-pulse px-1 rounded-sm">
-                                        <span className="opacity-30">004</span> <span>[10:42:03]</span> <span className="font-bold">FAIL</span> <span>Telemetry mismatch detected in shadow config.</span>
-                                    </div>
-                                    <div className="flex gap-3 text-[var(--danger)]"><span className="opacity-30">005</span> <span>[10:42:03]</span> <span className="font-bold">CRIT</span> <span>Security policy threshold breach (Found: 644).</span></div>
-                                </>
-                            )}
-                            {activePolicy.status !== 'FAIL' && (
-                                <div className="flex gap-3 text-[var(--success)]"><span className="opacity-30">004</span> <span>[10:42:03]</span> <span className="font-bold">PASS</span> <span>14/14 Node validators successfully closed.</span></div>
-                            )}
-                            <div className="flex gap-3"><span className="text-[var(--text-tertiary)] opacity-30">006</span> <span>[10:42:04]</span> <span className="text-[#bc8cff] font-bold">ARTIFACT</span> <span>Metadata hash logged: {activePolicy.id}_integrity.json</span></div>
-                        </div>
+                        <div className="text-[10px] text-[var(--text-tertiary)] leading-relaxed italic">
+                            This entry is illustrative reference data (see REFERENCE_CATALOG above) —
+                            not backed by live infrastructure scanning. Status and score are static.
+                        </div>
                     </div>
```

```diff
                         {isAdmin ? (
                             <div className="mt-4 pt-4 border-t border-[var(--border-default)] flex gap-3">
-                                <button 
-                                    onClick={handleTriggerRescan}
-                                    className="flex-1 py-1 px-3 bg-[var(--layer-2)] hover:bg-[var(--layer-3)] border border-[var(--border-default)] rounded text-[10px] font-bold text-[var(--text-primary)] transition-all"
-                                >
-                                    Update Policy
-                                </button>
-                                <button 
-                                    disabled={remediating}
-                                    onClick={() => handleRemediate()}
-                                    className={`flex-1 py-1 px-3 border rounded text-[10px] font-bold transition-all shadow-lg flex items-center justify-center gap-2 ${activePolicy.status === 'FAIL' ? 'bg-[var(--danger)] hover:bg-[#f86d67] border-[var(--danger)] text-white' : 'bg-[var(--layer-2)] border-[var(--border-default)] hover:bg-[var(--layer-3)]'}`}
-                                >
-                                    {remediating ? <Activity className="animate-spin" size={14} /> : (activePolicy.status === 'FAIL' ? 'REMEDIATE_NOW' : 'TRIGGER_RESCAN')}
-                                </button>
+                                <div className="flex-1 text-center text-[9px] font-bold text-[var(--text-tertiary)] uppercase tracking-widest opacity-50 py-1">
+                                    No live scan/remediate actions -- reference catalog only
+                                </div>
                             </div>
                         ) : (
```

`remediating` state variable declaration also removed. `Activity` import may become unused for this
file if not referenced elsewhere — check before removing the import (it's used for the loading
spinner earlier in the file, so the import itself stays; only the `remediating`-driven spinner usage
here goes away).

## Verification plan

- No backend changes — `smoke_test.py`/pytest unaffected, rebuild `grc-frontend` only.
- Browser check: open Compliance terminal, confirm `REFERENCE_CATALOG` badge visible, select a
  `FAIL`-status policy (`IAM_Root_MFA_Enforcement_v1`), confirm the old fake incident log text is
  gone and replaced with the honest note, confirm no rescan/remediate buttons remain for admin users,
  confirm CSV export and search still work (untouched).
