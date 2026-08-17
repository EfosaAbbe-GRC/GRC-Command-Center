# Fix: Operations terminal is unreachable from a clean state (and shows fabricated stats once it isn't)

**Status:** ✅ EXECUTED (2026-08-17). Applied exactly as drafted. Verified in a real browser
(16/16 checks in the combined post-fix run, zero console errors, zero failed requests):

- **Zero-run state:** the operations grid now renders instead of short-circuiting, showing
  `No_Agent_Runs_Recorded`, a working **Run Agent** control and agent picker, the wait state scoped to
  the console pane, `NO_ACTIVE_RUN` in the console header, and stat tiles reading a real
  **0 / 0 / 0** — not the old fabricated 2 / 0 / 2. The deadlock is broken.
- **Non-empty path unregressed:** real runs still render the console and `END_OF_EVENT_LOG`, and
  clicking **Run Agent** POSTed to `/api/v1/run-agent`, added a new row (2 → 3), and reached
  `COMPLETED` with a real result payload.
- `smoke_test.py` **43/43**, `pytest` **33/33**.

**Deviation from the drafted verification plan, worth recording:** the plan called for reproducing the
deadlock against the isolated test stack because it boots with zero runs. That didn't work out —
`docker-compose.test.yml` has no frontend service, and the `:3006` frontend points at the dev backend,
so there is no browser path to `:8002`. Deleting the dev stack's `agent_runs` rows instead was blocked
by a permission guard (correctly — it's a destructive DB write). The zero-run state was therefore
simulated by intercepting `GET /api/v1/ops/jobs` in Playwright and fulfilling it with `[]`. That is
arguably the better test anyway: this change is purely frontend, so exercising the component against
an empty payload isolates exactly what changed and destroys no data. Recorded because the substitution
is a real difference from the approved plan, not a detail.
**Found:** 2026-08-16, TPRM UI/browser dogfooding pass — see
`TPRM_Dogfooding_UI_Pass_2026-08-16.md` (Bug 2).
**File:** `src/terminals/OpsTerminal.jsx`
**Effort:** small (one early return removed, one conditional added, two state/`onSuccess` lines)

## The bug

`OpsTerminal.jsx:108` early-returns the `OPERATIONAL_WAIT_STATE` placeholder whenever `activeJob` is
null — i.e. whenever `/ops/jobs` comes back empty. That `return` sits **above** the console header
(`:225-240`) that holds the agent picker and the **Run Agent** button, which is the only control in
the entire UI that can create an agent run.

**Zero agent runs → no way to start one → permanently zero agent runs.**

Confirmed live this session: with `agent_runs = 0`, the Operations tab rendered only the placeholder,
`button[title="Run Agent"]` count **0**, `select` count **0**, role correctly `admin`, no console
errors. After seeding one run through the API (`POST /run-agent`, `policy-analyzer`), the same tab
rendered the full console with all three controls, and the Run Agent button then worked correctly.

This became reachable through entirely legitimate work — TPRM Tier 4's test-data hygiene plus a stack
restart left `agent_runs` genuinely empty, exactly the state `MEMORY.md`'s own gotcha already
predicted for `/ops/jobs` ("returns genuinely empty on a fresh boot with zero agent executions").
What hadn't been walked through was what that does to the UI.

## The second bug this fix would otherwise expose

`stats` is initialised to **`{ running: 2, queued: 0, failed: 2 }`** — fabricated numbers — and
`onSuccess` only recomputes it `if (resData.length > 0)`. So with zero jobs the stats never get
corrected.

Today that's invisible, purely because the early return hides the header those numbers live in.
**Removing the early return would put "Running 2 · Failed 2" on screen with zero jobs in the
system** — inventing operational activity that does not exist. That is precisely the class of problem
the 2026-08-06 `ComplianceTerminal`/`Framework_Mappings` honesty work existed to remove, so it has to
be fixed in the same diff rather than introduced by it.

## The fix

Scope the empty state to the console pane where it belongs, instead of using it to short-circuit the
entire terminal — and make the stats always reflect real data.

```diff
--- a/src/terminals/OpsTerminal.jsx
+++ b/src/terminals/OpsTerminal.jsx
@@
-    const [stats, setStats] = useState({ running: 2, queued: 0, failed: 2 });
+    const [stats, setStats] = useState({ running: 0, queued: 0, failed: 0 });
@@
     const { data: jobs, loading, error, refresh } = useApiData('/ops/jobs', {
         onSuccess: (resData) => {
-            if (resData.length > 0) {
-                if (!selectedJob) setSelectedJob(resData[0].id);
-
-                // Calculate real stats
-                const running = resData.filter(j => j.status === 'RUNNING').length;
-                const queued = resData.filter(j => j.status === 'QUEUED').length;
-                const failed = resData.filter(j => j.status === 'FAILED').length;
-                setStats({ running, queued, failed });
-            }
+            if (resData.length > 0 && !selectedJob) setSelectedJob(resData[0].id);
+
+            // Always recompute from real data — an empty run list means real zeros,
+            // not "keep whatever was on screen before".
+            setStats({
+                running: resData.filter(j => j.status === 'RUNNING').length,
+                queued: resData.filter(j => j.status === 'QUEUED').length,
+                failed: resData.filter(j => j.status === 'FAILED').length,
+            });
         }
     });
```

```diff
@@
-    if (!activeJob) {
-        return (
-            <div className="flex-1 flex flex-col items-center justify-center bg-[var(--layer-0)] text-[var(--text-tertiary)] opacity-30">
-                <Monitor className="mb-4" size={64} strokeWidth={1} />
-                <span className="text-[11px] font-bold tracking-[0.4em] font-mono uppercase">Operational_Wait_State</span>
-            </div>
-        );
-    }
-
     return (
```

```diff
@@ jobs table body
                         <div className="divide-y divide-[var(--border-subtle)]">
+                            {(jobs || []).length === 0 && (
+                                <div className="px-6 py-8 text-center text-[10px] font-mono font-bold uppercase tracking-[0.3em] text-[var(--text-tertiary)] opacity-40">
+                                    No_Agent_Runs_Recorded
+                                </div>
+                            )}
                             {(jobs || []).map((job, idx) => (
```

```diff
@@ console header
-                                <Terminal size={14} className="text-[var(--accent)]" /> OPERATIONAL_CONSOLE // <span className="text-[var(--accent)] font-mono">{activeJob.id}</span>
+                                <Terminal size={14} className="text-[var(--accent)]" /> OPERATIONAL_CONSOLE // <span className="text-[var(--accent)] font-mono">{activeJob?.id ?? 'NO_ACTIVE_RUN'}</span>
```

```diff
@@ console body
                         <div className="relative z-10">
+                            {!activeJob ? (
+                                <div className="flex flex-col items-center justify-center py-20 text-[var(--text-tertiary)] opacity-30">
+                                    <Monitor className="mb-4" size={64} strokeWidth={1} />
+                                    <span className="text-[11px] font-bold tracking-[0.4em] font-mono uppercase">Operational_Wait_State</span>
+                                    <span className="mt-3 text-[10px] font-mono tracking-widest opacity-80">
+                                        Select an agent above and press run to begin.
+                                    </span>
+                                </div>
+                            ) : (
                             <div className="space-y-1.5">
                                 <div className="text-[var(--text-tertiary)] opacity-60 mb-4 font-bold"># {activeJob.task} — agent '{activeJob.agent}' — {activeJob.id}</div>
@@ (unchanged RUNNING / FAILED / COMPLETED blocks)
                                 <div className="opacity-20 mt-8 pt-4 border-t border-[var(--border-default)] text-[9px] font-bold tracking-[0.3em] text-center">END_OF_EVENT_LOG</div>
                             </div>
+                            )}
                         </div>
```

Everything inside the `activeJob ?` branch is untouched — all the `activeJob.status` / `.result` /
`.error` dereferences stay exactly as they are, now guaranteed non-null by the conditional. The
`Monitor` import stays in use. The `loading` and `error` early returns above are left alone: those
are genuinely whole-terminal states, unlike "there are no runs yet".

## Why this shape, not the alternatives

- **Duplicate the runner controls into the empty state** — rejected: two copies of the agent picker
  and Run button drift apart, and it keeps the underlying claim ("no runs means nothing to show")
  which is wrong; the grid, stats, and runner are all meaningful at zero runs.
- **Auto-trigger a first run so the list is never empty** — firmly rejected: `active-auditor` is the
  default selection and blocks the entire single-threaded backend for ~31-43s (`MEMORY.md`
  gotchas). Silently running an agent because a tab was opened is exactly the deny-by-default
  violation GOVERNANCE §2 exists to prevent.
- **Seed a fixture run on boot** — rejected: `fixtures.json`'s `jobs` array and
  `data_service.get_ops_jobs()` are already dead code precisely *because* Execution Monitor moved
  this surface onto real `AgentRun` rows. Reintroducing fake rows to paper over an empty state would
  undo that and re-create the honesty problem the 2026-08-06 work removed.

## Verification plan

1. **Reproduce the deadlock first, then confirm it's gone.** Requires a genuinely empty `agent_runs`
   table — the dev stack now has 2 real rows (left deliberately, see the dogfooding doc), so use the
   isolated test stack (`docker-compose.test.yml`, `:8002`) which boots with none, rather than
   deleting real rows from the dev DB.
2. Browser (Python `playwright`): as `admin` on a zero-run stack, confirm the Operations tab renders
   the grid + `No_Agent_Runs_Recorded` + a working **Run Agent** control, that the stat tiles read
   **0 / 0 / 0** (not 2 / 0 / 2), and that clicking Run actually creates a run and populates the
   console. Use `policy-analyzer`, **not** `active-auditor` — the latter blocks the whole backend for
   ~31-43s and will contaminate any timing alongside it.
3. Confirm the non-empty path is unregressed: with runs present, selecting different rows still
   switches the console, and RUNNING/FAILED/COMPLETED blocks still render as before.
4. `smoke_test.py` (**43/43**) and `pytest` from `backend/` (**32/32**) — frontend-only change, no
   API surface touched, but run per the boot ritual regardless.
5. **Frontend change ⇒ `grc-frontend` needs a rebuild.** Expect the container to keep reporting
   Docker-healthcheck `unhealthy` afterwards — that's the known harmless IPv6 loopback quirk, not a
   failed deploy.

## Note

There is no automated regression test proposed here because the project has **zero frontend component
tests** project-wide — a known, previously-parked gap. Both bugs in this dogfooding pass are frontend
or frontend-triggered, which is a fair argument that the gap is starting to cost something; raising
it as an observation, not quietly starting to close it.
