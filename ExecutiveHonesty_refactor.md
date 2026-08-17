# Fix: Executive terminal presents fabricated data as live KPIs

**Status:** ✅ EXECUTED (2026-08-17). Applied as drafted, including the optional readiness/quarter
wiring (not dropped). **Verified: pytest 38/38** (33 → 38, five new tests in a new
`backend/tests/test_executive.py`), **smoke 43/43**, **15/15 browser checks** with zero console errors
and zero failed requests, and a re-run of the 5-terminal empty-state audit showing no regression
(Executive's button count correctly dropped 10 → 6 as the dead period selector went away).

Live values now served, matching the DB exactly: `active_users` **3** (was a fabricated 142),
`open_findings` **0** (was 8), `policy_coverage` **0%** (was 98%). `trend_data` still fixture-backed
and labelled, as designed.

**One addition beyond the draft, disclosed:** the fix introduced its own coherence problem — once four
panels carry a `Reference` badge, the three genuinely-real footer metrics read as ambiguous by
omission. Added a counterpart green **`Live`** badge with "Computed from current system state." That
wasn't in the approved diff; it's three lines, it serves the fix's stated purpose, and calling it out
here rather than letting it pass silently.

**`policy_coverage` does read 0%**, exactly as the draft predicted. That is the true state (0 of 13
RBAC policies cite a framework source document) and matches what `policy-analyzer` independently
reports. Left truthful. Say the word if you'd rather that tile carried TPRM assessment completion
instead (real, and 100% today).

**Three things worth recording from the execution, all corrections:**

1. **My own verification check gave a false pass.** The first version asserted `"READY" in page_text`
   to confirm `UNIT_HEALTH` was wired to real readiness — and was satisfied by the unrelated
   `AUDIT_STATE` KPI card, which also reads "READY". A screenshot is what caught it: the tile actually
   rendered `--`. Rewritten to read the tile's own value node. **This is the second time today the same
   failure mode appeared** (the first hid the evidence-notes data loss on 2026-08-16) — whole-page text
   assertions are not scoped enough to be trusted on this UI.
2. **The `--` turned out to be correct behaviour, not a bug.** `/readiness` resolves after first paint,
   so the tile briefly shows its honest placeholder before settling on `READY`. Confirmed via DOM dump
   and a cropped screenshot (green `READY` with the live pulse). The verification now waits for it.
3. **A scary-looking rebuild failure was transient.** `docker compose up -d --build` reported
   `container grc-backend is unhealthy / dependency failed to start`, so the frontend never came up.
   The backend logs showed a completely clean boot ("Application startup complete", health returning
   200) — compose simply gave up before the healthcheck threshold passed. A plain second `up -d`
   started the frontend fine. Consistent with `MEMORY.md`'s existing warning not to trust a red result
   immediately following a rebuild on this Windows/WSL2 setup.

**One caveat on the audit re-run:** its Compliance row showed populated policy rows rather than the
empty state, because the audit script arms its route interception *after* login and Compliance is the
default landing terminal — its first fetch can land before interception is active. The original run
did observe Compliance's genuine empty state (clean, no crash); the re-run simply didn't re-test that
one path. Noted so the two runs aren't read as identical evidence.
**Found:** 2026-08-17, empty-state audit across all 5 terminals (see
`TPRM_Dogfooding_UI_Pass_2026-08-16.md` for the pass that motivated the audit).
**Files:** `backend/core/database.py`, `backend/main.py`, `src/terminals/ExecutiveTerminal.jsx`
**Effort:** medium — one new DB query method, one endpoint merge, and labelling/removal in the JSX.
**Approach chosen by the user:** *wire what's real, label the rest.*

## Why this exists

The empty-state audit (its own hypothesis — that both 2026-08-16 bugs were the same "no data" class —
came back **clean**: all 5 terminals render honest empty states, zero crashes, zero JS errors) turned
up something bigger on the way past: **the Executive terminal is the largest remaining instance of the
exact fabricated-data problem already fixed twice** — `ComplianceTerminal`'s policy grid (2026-08-06,
`REFERENCE_CATALOG` badge) and `Framework_Mappings` (2026-08-13, honest caption).

It is also the worst-placed instance. It is the most stakeholder-facing screen in the app, and its
numbers carry **trend deltas** ("+1.2% VS PRIOR PERIOD") implying a historical baseline that does not
exist anywhere in this system.

A note on ordering, because it matters: the user asked for automated screen tests, and this fix was
sequenced *first* deliberately. Writing tests against this screen today would have encoded
`expect(governancePosture).toBe('92.4%')` — permanently cementing a fabrication as the expected
contract. Tests lock in behaviour; behaviour has to be correct first.

## What is actually fabricated

`/executive/stats` → `fixtures.json.kpis` and `/executive/dashboard` → `fixtures.json.dashboard` are
**pure static passthroughs** (`main.py:535-541` → `data_service.get_executive_stats()` /
`get_dashboard_stats()` → cached JSON). Nothing computes them; they never change.

| § | Element | Source | Real? |
| --- | --- | --- | --- |
| 1 | `UNIT_HEALTH: OPTIMAL` | hardcoded in JSX | ❌ |
| 1 | `FISCAL_CONTEXT: Q3_FY2026` | hardcoded in JSX | ❌ (correct by luck today; wrong from October) |
| 2 | `GOVERNANCE_POSTURE 92.4% / +1.2%` | fixtures | ❌ |
| 2 | `CRITICAL_EXPOSURE 12/100 / -4pts` | fixtures | ❌ |
| 2 | `DETECTED_VULNERABILITIES 34 / +5` | fixtures | ❌ nothing scans for vulnerabilities |
| 2 | `AUDIT_STATE READY / ISO-42001` | fixtures | ❌ |
| 3 | `SECURITY_POSTURE_TRENDING` chart (AUG→JAN) | fixtures `trend_data` | ❌ no historical KPI storage exists |
| 3 | `1M / 3M / 6M / YTD` buttons | — | ❌ **no `onClick` at all** — pure decoration |
| 3 | `GRC_CAPITAL_ALLOCATION` budget bar | fixtures `budget` | ❌ |
| 3 | `Infosec_Tools $450k` / `External_Audit $120k` | hardcoded in JSX | ❌ |
| 3 | `STRATEGIC_INDICATORS` alerts | fixtures `alerts` | ❌ |
| 4 | `SECURITY_IDENTITY_AUDIT` table + filters | `/admin/audit/security` | ✅ **real** |
| 5 | `UNRESOLVED_AUDIT_FINDINGS 8` | fixtures | ❌ → **can be real** |
| 5 | `FRAMEWORK_POSTURE_COVERAGE 98%` | fixtures | ❌ → **can be real** |
| 5 | `IDENTIFIED_SYSTEM_AUTHORS 142` | fixtures | ❌ → **can be real** (there are **3** users) |
| 6 | `STRATEGIC_POLICY_ENGINE` | `/admin/policies` | ✅ **real**, incl. working updates |

The starkest one: **`142 active users` against 3 real accounts.** Also worth noting the irony — the
component's own `initialData` uses honest `"--"` placeholders and zeros (`ExecutiveTerminal.jsx:15-32`).
It was *written* to degrade gracefully; the backend overwrites that honesty with fiction.

The `1M/3M/6M/YTD` buttons deserve separate mention: they are the same defect class as
`ComplianceTerminal`'s `Update Policy` / `REMEDIATE_NOW` buttons, which were **removed** on 2026-08-06
for looking functional while doing nothing meaningful. Same precedent applies.

## Part A — wire the three footer metrics to real data

All three have genuine sources. Verified against the live DB today:

| Metric | Real definition | Value today |
| --- | --- | --- |
| `open_findings` | TPRM stage responses at `GAP` with **no** risk acceptance — genuinely unresolved | **0** |
| `policy_coverage` | % of RBAC policies citing a framework `source_doc` | **0%** (0 of 13) |
| `active_users` | rows in `users` | **3** |

New method in `database.py`, following the established `_x_async()` + `_run_async()` sync-bridge
pattern already used by `list_policies()`:

```diff
--- a/backend/core/database.py
+++ b/backend/core/database.py
@@
     def list_policies(self):
         return _run_async(self._list_policies_async())
 
+    async def _dashboard_metrics_async(self):
+        """Real counts behind the Executive footer metrics.
+
+        The TPRM gap count uses raw SQL on purpose: core.tprm imports
+        core.database, so importing the TPRM ORM models here would be a
+        circular import. User/Policy are already imported above.
+        """
+        try:
+            async with AsyncSessionLocal() as session:
+                users = await session.scalar(select(func.count()).select_from(User))
+                pol_total = await session.scalar(select(func.count()).select_from(Policy))
+                pol_sourced = await session.scalar(
+                    select(func.count()).select_from(Policy).where(
+                        Policy.source_doc.isnot(None), Policy.source_doc != ""
+                    )
+                )
+                unresolved = (await session.execute(text("""
+                    SELECT COUNT(*) FROM stage_responses sr
+                    WHERE sr.status = 'GAP'
+                      AND NOT EXISTS (
+                          SELECT 1 FROM risk_acceptances ra
+                          WHERE ra.stage_id = sr.stage_id
+                            AND ra.integration_id = sr.integration_id
+                      )
+                """))).scalar()
+                return {
+                    "open_findings": int(unresolved or 0),
+                    "policy_coverage": round((pol_sourced / pol_total) * 100) if pol_total else 0,
+                    "active_users": int(users or 0),
+                }
+        except Exception as e:
+            logger.error("Dashboard metrics query failed", error=str(e))
+            return {"open_findings": 0, "policy_coverage": 0, "active_users": 0}
+
+    def get_dashboard_metrics(self):
+        return _run_async(self._dashboard_metrics_async())
```

Endpoint merges real values over the fixture payload, so `trend_data` (labelled illustrative in the
UI, Part B) still satisfies the `DashboardStats` response model:

```diff
--- a/backend/main.py
+++ b/backend/main.py
@@
 @app.get("/api/v1/executive/dashboard", response_model=DashboardStats, dependencies=[Depends(authorize("RAG_QUERY"))])
 def get_dashboard_stats():
-    return data_service.get_dashboard_stats()
+    # Real metrics override the fixture values; trend_data stays fixture-backed and is
+    # labelled ILLUSTRATIVE in the UI (no historical KPI storage exists to compute it).
+    return {**data_service.get_dashboard_stats(), **audit_logger.get_dashboard_metrics()}
```

**A caveat to decide with eyes open:** `FRAMEWORK_POSTURE_COVERAGE` will read **0%**, because not one
of the 13 RBAC policies cites a framework source document. That is true, and it is the same gap
`policy-analyzer` already reports as its real finding. It will look worse than the fictional 98%. My
recommendation is to ship the truth. If you'd rather that tile carried a real metric that isn't near
zero, the honest alternative is **TPRM assessment completion** (integrations fully reviewed — 2 of 2,
**100%** today); say so and I'll swap it.

## Part B — label what cannot be real

Fabricated sections get the established treatment: a `REFERENCE` badge plus a one-line honest caption,
matching `REFERENCE_CATALOG` on `ComplianceTerminal` and the `Framework_Mappings` caption.

```diff
--- a/src/terminals/ExecutiveTerminal.jsx
+++ b/src/terminals/ExecutiveTerminal.jsx
@@ (section 2, above the KPI grid)
+                {/* Fabricated-KPI honesty label -- these four tiles have no live data source.
+                    Same treatment as ComplianceTerminal's REFERENCE_CATALOG badge. */}
+                <div className="flex items-center gap-3 -mb-4">
+                    <span className="px-2 py-0.5 rounded-sm border text-[9px] font-bold uppercase font-mono"
+                          style={{ borderColor: 'var(--warning)', color: 'var(--warning)', backgroundColor: 'var(--warning-subtle)' }}>
+                        Reference
+                    </span>
+                    <span className="text-[10px] font-mono text-[var(--text-tertiary)]">
+                        Illustrative reference figures -- not live-computed. No historical baseline exists,
+                        so the trend deltas are illustrative too.
+                    </span>
+                </div>
                 <div className="grid grid-cols-4 gap-6">
                     <KPICard
                         title="GOVERNANCE_POSTURE"
```

The same `Reference` badge + caption goes on **`SECURITY_POSTURE_TRENDING`**, on
**`GRC_CAPITAL_ALLOCATION`**, and on **`STRATEGIC_INDICATORS`** (three more small insertions, identical
shape — omitted here to keep the diff readable; they are mechanical repeats of the block above).

`UNIT_HEALTH` and `FISCAL_CONTEXT` are handled differently, because both *can* be real cheaply:

```diff
@@ (section 1, header tiles)
-                                <div className="text-[var(--text-tertiary)] ...">UNIT_HEALTH</div>
-                                <div className="text-[var(--success)] ...">
-                                    ... OPTIMAL
+                                <div className="text-[var(--text-tertiary)] ...">UNIT_HEALTH</div>
+                                <div className="... " style={{ color: readiness === 'ready' ? 'var(--success)' : 'var(--warning)' }}>
+                                    ... {readiness ? readiness.toUpperCase() : '--'}
@@
-                                <div className="text-[var(--text-primary)] font-bold text-2xl font-mono">Q3_FY2026</div>
+                                <div className="text-[var(--text-primary)] font-bold text-2xl font-mono">{fiscalQuarter()}</div>
```

…backed by a real readiness fetch and a two-line date helper:

```diff
+    // Real system health -- /readiness already reports DB/FAISS/LLM-key/JWT status.
+    const { data: readinessData } = useApiData('/readiness', { initialData: null });
+    const readiness = readinessData?.overall ?? null;
+
+// Calendar-quarter label, computed rather than frozen at Q3_FY2026 (which silently
+// becomes wrong in October).
+const fiscalQuarter = () => {
+    const d = new Date();
+    return `Q${Math.floor(d.getMonth() / 3) + 1}_FY${d.getFullYear()}`;
+};
```

**Drop this bit if you'd rather keep the diff smaller** — it's the one genuinely optional part. Both
elements could just take the `Reference` label instead. I included it because "wire what's real" is the
approach you picked and `/readiness` is real data already sitting there unused. Note the fiscal quarter
assumes fiscal year = calendar year; if yours differs, say so.

## Part C — remove the non-functional period selector

```diff
@@ (section 3, trend chart header)
-                            <div className="flex gap-2 bg-[var(--layer-2)] p-1.5 rounded-lg border border-[var(--border-default)]">
-                                {['1M', '3M', '6M', 'YTD'].map(p => (
-                                    <button key={p} className={`... ${p === 'YTD' ? '...' : '...'}`}>
-                                        {p}
-                                    </button>
-                                ))}
-                            </div>
```

These have no handler and no state — clicking them does nothing, while permanently highlighting `YTD`
as though a range were selected. Removed rather than wired, because there is no time-series data for a
range selector to filter. Exactly the call made for `ComplianceTerminal`'s misleading buttons.

## Part D — leave the genuinely real sections alone

`SECURITY_IDENTITY_AUDIT` (§4) and `STRATEGIC_POLICY_ENGINE` (§6) are real, with working filters and
working policy updates. Untouched. Worth stating explicitly so the screen isn't read as wholesale
fake: roughly the bottom third of it always was real.

## Why this shape, not the alternatives

- **Remove the fabricated tiles entirely** — considered (it was option 3 when you chose). Rejected per
  your choice, and it is also the most destructive: it would gut the screen's visual purpose when
  labelling already resolves the honesty problem, which is the precedent both prior fixes set.
- **Invent plausible computations** for compliance % / vulnerabilities / risk score so every tile shows
  "real" numbers — firmly rejected. A formula chosen to make a tile non-empty is fabrication with extra
  steps. `ComplianceTerminal` faced exactly this and the answer was honesty over fake realism.
- **Return `trend_data: []`** so the chart renders its own `'--'` placeholder fallback (the component
  already supports this, line 207) — genuinely tempting, and more honest than a labelled fake chart.
  Rejected only to match the established precedent of "keep the illustrative content, label it
  clearly". Say the word and I'll flip it; it's a one-line change.
- **Delete `kpis`/`dashboard` from `fixtures.json`** — rejected: `ExecutiveStats` requires those keys,
  so this would need schema changes too. Out of scope for an honesty fix.

## Verification plan

1. `pytest` from `backend/` — expect **33/33**, plus a proposed new test asserting
   `/executive/dashboard` returns the **real** user count rather than the fixture's 142 (that is the
   regression test for this bug; it fails today).
2. `smoke_test.py` — expect **43/43**. It does not currently assert on these endpoints' values.
3. **Browser**: confirm the three footer metrics show 0 / 0% / 3 (matching the DB), the `Reference`
   badges and captions render on all four fabricated sections, the period buttons are gone,
   `UNIT_HEALTH` reflects real readiness, `FISCAL_CONTEXT` computes, and §4/§6 still work. Zero console
   errors, zero failed requests.
4. Re-run the 5-terminal empty-state audit afterwards to confirm no regression in the other four.
5. Backend + frontend both change ⇒ **rebuild both images**; prefer `up -d --build` over a full
   `down`/`up` per `MEMORY.md`.

## Then, and only then: the component test harness

The second half of what you asked for (Vitest + React Testing Library, empty/render-state contracts for
all 5 terminals plus regressions for the two bugs fixed on 2026-08-17) comes as its own draft **after
this lands** — so those tests assert the corrected Executive behaviour instead of freezing `92.4%` and
`142 active users` into the suite as expected values. That harness touches `package.json` and adds new
dev dependencies, so it needs its own review.
