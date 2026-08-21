# Execution Monitor UI — Implementation Diff

**Status:** ✅ EXECUTED (2026-08-06). Applied as drafted, with two corrections found during
implementation (both noted inline below where they occurred): `core/database.py` needed `import json`
added (the draft's claim that `main.py` already had it was also wrong — added there too), and a new
`smoke_test.py` check was needed since `/ops/jobs` moving from a static fixture to real data broke
the existing "at least 1 item" assertion on a fresh boot with zero agent runs yet (fixed by having
the smoke test trigger one run before checking, which also gives direct coverage of the new
endpoint). Rebuilt both `grc-backend` and `grc-frontend`. Verified: smoke **43/43** (grew from 42),
pytest **32/32**, manual curl round-trip (both real agents + one deliberately-unregistered id, all
persisted correctly with real status/result/error), confirmed `AGENT_EXECUTE` audit-trail rows via
`GET /admin/audit/security` (Decision #3's actual point), and a two-tab Playwright regression proving
the real-time claim: triggering a run in tab 1 populated tab 2's grid via the `JOB_STATUS` WebSocket
broadcast with zero manual interaction on tab 2. 5/5 browser checks passed, zero console errors on
either tab.
**Scope confirmed 2026-08-06** per `Execution_Monitor_UI_Roadmap.md`'s three open decisions:
1. Build monitor now, not sequenced after Agent Registry De-stubbing (recommended option).
2. Stay synchronous; design the schema so it doesn't need a rewrite later (recommended option).
3. Add audit-trail logging for agent execution — confirmed gap: `run_agent_endpoint` currently
   calls only `logger.info`, never `log_security_event`, unlike every other privileged action in
   this codebase (recommended option).

**One roadmap claim corrected before drafting:** `Execution_Monitor_UI_Roadmap.md` §Tier 0.1 states
`src/lib/api.js:255-256` has a stray-backslash path bug (`'\run-agent'`). Re-checked the actual file
just now — the path is already correctly `/run-agent` (forward slash). That part of the roadmap was
wrong/stale; not propagating it. The real bug at that line is narrower: the body field is
`agent_name`, but the backend's `AgentRunRequest` schema requires `agent_id` — that mismatch is
real and is what Tier 0.1 below actually fixes.

Covers Tier 0 + Tier 1 + Tier 2 from the roadmap's recommended sequence (0.1 → 0.2 → 1.1 → 1.2 →
1.3 → 2.1 → 2.2 → 2.3). Tier 3 (true async/queued execution, historical retention beyond a simple
cap) stays explicitly out of scope per the roadmap.

---

## Tier 0 — Fix what's already broken

### 0.1 — `src/lib/api.js`: fix the field name `runAgent()` sends

```diff
     // Agent execution
-    runAgent: (agentName, args = {}) =>
-        api.post('/run-agent', { agent_name: agentName, args }),
+    runAgent: (agentId, args = {}) =>
+        api.post('/run-agent', { agent_id: agentId, args }),
```

### 0.2 — `src/terminals/OpsTerminal.jsx`: trigger a real, selectable registry id

Today's `runAgent()` hardcodes `'compliance_checker'`, which isn't in `AGENT_REGISTRY` at all (only
`active-auditor` and `policy-analyzer` are) — the call would 403 even after 0.1's fix. Since there
are two real registered agents, adding a small inline picker (admin-only, matches the existing
`isAdmin` gate) is barely more code than hardcoding one and makes the feature actually usable for
both agents rather than arbitrarily picking one:

```diff
 export const OpsTerminal = () => {
     const { user } = useAuth();
     const isAdmin = user?.role === 'admin';
     const [selectedJob, setSelectedJob] = useState(null);
-    const [manualOutput, setManualOutput] = useState(null);
     const [stats, setStats] = useState({ running: 2, queued: 0, failed: 2 });
     const [showGovernance, setShowGovernance] = useState(false);
+    const [selectedAgent, setSelectedAgent] = useState('active-auditor');
+    const [triggering, setTriggering] = useState(false);
```

(`manualOutput` removal and the rewritten `runAgent()` are covered together in 2.3 below, since
they're one continuous change — no point showing the state split from its own usage.)

---

## Tier 1 — Give agent runs a real, persisted lifecycle

### 1.1 — New `AgentRun` model

Added to `core/models.py`, following that file's existing house style (plain-string status columns
with a `server_default`, like `EvidenceChain.status`) rather than `tprm.py`'s `SAEnum` style — this
avoids the `ALTER TYPE ... ADD VALUE` class of gotcha entirely for a brand-new table, and keeps this
system-level table consistent with `AuditLog`/`SecurityEvent`, not the TPRM-specific module:

```diff
 from datetime import datetime
 from typing import Optional, List
 from sqlalchemy import String, Integer, Boolean, Text, ForeignKey, DateTime, func
 from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
+import json
```

```diff
 class Policy(Base):
     __tablename__ = "policies"
     ...
     updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())
+
+
+class AgentRun(Base):
+    """Persisted lifecycle for a single agent execution (Execution Monitor UI).
+
+    Status stays a plain string, not a SQLAlchemy Enum -- see the ALTER TYPE
+    gotcha in MEMORY.md; a new table has no such migration hazard, but a
+    plain string keeps this consistent with the rest of this file and
+    sidesteps the whole class of problem if a status value is ever added.
+    Values in practice: PENDING, RUNNING, COMPLETED, FAILED.
+    """
+    __tablename__ = "agent_runs"
+
+    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
+    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
+    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
+    args_json: Mapped[Optional[str]] = mapped_column(Text)
+    result_json: Mapped[Optional[str]] = mapped_column(Text)
+    error: Mapped[Optional[str]] = mapped_column(Text)
+    triggered_by: Mapped[str] = mapped_column(String(100), nullable=False)
+    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
+    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

`args`/`result` stored as JSON text (`args_json`/`result_json`), matching how `AuditLog.context`/
`sources` already store serialized text in this same file — not a new pattern.

New table only — `Base.metadata.create_all` (already run on every boot per `core/database.py`'s
`init_db()`) creates it automatically, no `ALTER TYPE` involved since nothing existing is being
changed.

### 1.2 — `core/database.py`: `AuditLogger` methods for the new table, wired into `/run-agent`

Following the exact sync-bridge pattern already used for `update_policy`/`get_policy` (public sync
method wrapping `_run_async(self._xxx_async(...))`), not `tprm.py`'s `Depends(get_db)` pattern,
since `main.py` doesn't import `get_db` and every other main.py endpoint goes through `audit_logger`:

```diff
 from core.models import Base, AuditLog, EvidenceChain, User, RefreshToken, SecurityEvent, Policy
+from core.models import AgentRun
```

```diff
+    async def _create_agent_run_async(self, agent_id: str, args: dict, triggered_by: str) -> int:
+        async with AsyncSessionLocal() as session:
+            run = AgentRun(
+                agent_id=agent_id,
+                status="RUNNING",
+                args_json=json.dumps(args or {}),
+                triggered_by=triggered_by,
+                started_at=_naive_utcnow(),
+            )
+            session.add(run)
+            await session.commit()
+            await session.refresh(run)
+            return run.id
+
+    def create_agent_run(self, agent_id: str, args: dict, triggered_by: str) -> int:
+        """Inserts directly as RUNNING, not PENDING->RUNNING as two writes: execution is
+        synchronous (Decision #2, 2026-08-06) so there's no real gap between the two states
+        worth a second DB round-trip for. The status column still supports PENDING for when
+        async execution lands and that gap becomes real."""
+        return _run_async(self._create_agent_run_async(agent_id, args, triggered_by))
+
+    async def _finish_agent_run_async(self, run_id: int, status: str, result: dict = None, error: str = None):
+        async with AsyncSessionLocal() as session:
+            run = await session.get(AgentRun, run_id)
+            run.status = status
+            run.result_json = json.dumps(result) if result is not None else None
+            run.error = error
+            run.completed_at = _naive_utcnow()
+            await session.commit()
+
+    def finish_agent_run(self, run_id: int, status: str, result: dict = None, error: str = None):
+        return _run_async(self._finish_agent_run_async(run_id, status, result, error))
+
+    async def _list_agent_runs_async(self, limit: int = 50) -> list:
+        async with AsyncSessionLocal() as session:
+            result = await session.execute(
+                select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
+            )
+            return result.scalars().all()
+
+    def list_agent_runs(self, limit: int = 50) -> list:
+        return _run_async(self._list_agent_runs_async(limit))
+
     def update_policy(self, policy_id: int, required_role: str, is_active: bool, modified_by: str, source_doc: str = None):
         return _run_async(self._update_policy_async(policy_id, required_role, is_active, modified_by, source_doc))
```

(New methods placed directly above `update_policy` as a natural insertion point; exact placement is
not load-bearing.) Also add `import json` to `core/database.py`'s import block if not already
present (it isn't, per the current top-of-file import list).

### `core/main.py`: rewrite `run_agent_endpoint` to persist + audit-log + broadcast

```diff
+AGENT_TASK_LABELS = {
+    "active-auditor": "NIST AI RMF Audit",
+    "policy-analyzer": "Policy Gap Analysis",
+}
+
 @app.post("/api/v1/run-agent", response_model=AgentResult, dependencies=[Depends(authorize("AGENT_EXECUTE"))])
 @limiter.limit("10/minute")
 async def run_agent_endpoint(request: Request, payload: AgentRunRequest):
     user = get_current_user(request)
     logger.info("Registry Agent execution requested", agent=payload.agent_id, user=user["username"])
-    
-    # Internal execution via the Zero-Trust Registry
+
+    run_id = audit_logger.create_agent_run(payload.agent_id, payload.args, user["username"])
+
+    # Internal execution via the Zero-Trust Registry
     result = agent_runner.execute_agent(payload.agent_id, payload.args)
-    
+
     status = "success" if "error" not in result else "failed"
+    final_status = "COMPLETED" if status == "success" else "FAILED"
+    audit_logger.finish_agent_run(
+        run_id,
+        status=final_status,
+        result=result if status == "success" else None,
+        error=result.get("error") if status == "failed" else None,
+    )
+
+    log_security_event(
+        request, "AGENT_EXECUTE",
+        f"User '{user['username']}' executed agent '{payload.agent_id}' -> {final_status} (run_id={run_id})"
+    )
+    await manager.broadcast({"type": "JOB_STATUS"})
+
     return AgentResult(
         status=status,
         agent=payload.agent_id,
-        result=result
+        result=result,
+        run_id=run_id
     )
```

Decision #3's audit-trail fix is this `log_security_event` call — same shape as `POLICY_CHANGE`,
one line, independent of the rest of this feature's scope as the roadmap noted.

### `schemas.py`: widen `AgentResult`, `JobItem`

```diff
 class AgentResult(BaseModel):
     status: str
     agent: str
     result: Dict[str, Any]
+    run_id: int
```

```diff
 class JobItem(BaseModel):
     id: str
     agent: str
     task: str
     status: str
     duration: str
     cpu: str
     ram: str
+    result: Optional[Dict[str, Any]] = None
+    error: Optional[str] = None
```

`result`/`error` included directly in the list response (not a separate per-job detail fetch) —
the dataset is small (currently two stub handlers' worth of JSON, capped at 50 rows total) and this
avoids a second round-trip every time a row is selected in the grid.

### 1.3 — `main.py`: repoint `GET /api/v1/ops/jobs` at the real table

```diff
 @app.get("/api/v1/ops/jobs", response_model=List[JobItem], dependencies=[Depends(authorize("RAG_QUERY"))])
 def get_ops_jobs():
-    return data_service.get_ops_jobs()
+    runs = audit_logger.list_agent_runs()
+    jobs = []
+    for r in runs:
+        if r.completed_at:
+            elapsed = (r.completed_at - r.started_at).total_seconds()
+            duration = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
+        else:
+            duration = "—"
+        jobs.append(JobItem(
+            id=f"RUN_{r.id}",
+            agent=r.agent_id,
+            task=AGENT_TASK_LABELS.get(r.agent_id, r.agent_id),
+            status=r.status,
+            duration=duration,
+            cpu="N/A",
+            ram="N/A",
+            result=json.loads(r.result_json) if r.result_json else None,
+            error=r.error,
+        ))
+    return jobs
```

`cpu`/`ram` become honest `"N/A"` rather than fixture-fake percentages — there's no real resource
telemetry behind a synchronous in-process call, and inventing numbers would be worse than admitting
there aren't any. `import json` needed in `main.py` too (already imported — confirmed at top of
file). `data_service.get_ops_jobs()` and `fixtures.json`'s `jobs` array become dead code; left in
place rather than deleted (`data_service.py` is a shared fixture loader used by several other
endpoints — not touching its structure for a one-method change; the dead fixture data is a Tier 4
cleanup candidate, not blocking this feature).

---

## Tier 2 — Wire the frontend to the real data

### 2.1 — Verify the existing `JOB_STATUS` handler

No code change: `OpsTerminal.jsx`'s WS handler already branches on `JOB_STATUS` and calls `refresh()`
(confirmed at the top of this file, unchanged since the TPRM session's `OpsTerminal` WS-auth fix).
Once 1.2 actually broadcasts that type, this "just works" as the roadmap predicted. Verification
step, not a diff.

### 2.2 + 2.3 — Real console rendering + the "Run Agent" button actually populating the grid

These two are one continuous change in practice: fixing 2.3 (manual trigger updates `jobs`/
`selectedJob`) means the manual-trigger path and the WS-driven path both flow through the same
`activeJob`-based rendering that 2.2 needs anyway. Replacing them separately would mean writing the
real-rendering logic once for the WS path and then immediately deleting it to redo for the manual
path.

```diff
-    const runAgent = async () => {
-        setManualOutput("> Initializing Agent Instance...\n> SECURE_TUNNEL_ESTABLISHED\n> Handshaking with regional GRC node...\n> Validating compliance manifests...");
-        try {
-            const data = await api.runAgent('compliance_checker');
-            if (data.result.stdout) {
-                setManualOutput(data.result.stdout);
-            } else {
-                setManualOutput("Agent session terminated. No STDOUT received.");
-            }
-        } catch (err) {
-            setManualOutput(`FATAL_ERROR: ${err.message}`);
-        }
-    };
+    const runAgent = async () => {
+        setTriggering(true);
+        try {
+            const data = await api.runAgent(selectedAgent);
+            await refresh();
+            setSelectedJob(`RUN_${data.run_id}`);
+        } catch (err) {
+            console.error("Agent execution failed:", err);
+        } finally {
+            setTriggering(false);
+        }
+    };
```

Button + picker (replaces the single unconditional `Play` button in the admin controls row):

```diff
                             {isAdmin ? (
                                 <>
-                                    <button onClick={runAgent} title="Run Agent" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--success)] transition-all active:scale-90"><Play size={14} strokeWidth={2.5} /></button>
+                                    <select
+                                        value={selectedAgent}
+                                        onChange={(e) => setSelectedAgent(e.target.value)}
+                                        className="bg-[var(--layer-2)] border border-[var(--border-default)] rounded text-[9px] font-mono font-bold py-1 px-2 text-[var(--text-primary)]"
+                                    >
+                                        <option value="active-auditor">active-auditor</option>
+                                        <option value="policy-analyzer">policy-analyzer</option>
+                                    </select>
+                                    <button onClick={runAgent} disabled={triggering} title="Run Agent" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--success)] transition-all active:scale-90 disabled:opacity-40">
+                                        <Play size={14} strokeWidth={2.5} className={triggering ? 'animate-pulse' : ''} />
+                                    </button>
                                     <button title="Rerun" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-all active:scale-90"><RotateCcw size={14} strokeWidth={2.5} /></button>
                                     <button title="Stop Agent" className="p-2 hover:bg-[var(--layer-3)] rounded-md text-[var(--text-tertiary)] hover:text-[var(--danger)] transition-all active:scale-90"><AlertOctagon size={14} strokeWidth={2.5} /></button>
                                 </>
```

`"Rerun"`/`"Stop Agent"` stay inert (no `onClick`) — same as today; wiring them is out of scope
(stopping a run only means something once execution is actually async, which Decision #2 defers).

Console panel — replace the hardcoded status-conditional fiction with real `activeJob.result`/
`activeJob.error`:

```diff
                         <div className="relative z-10">
-                            {manualOutput ? (
-                                <div className="whitespace-pre-wrap text-[var(--text-primary)] font-bold">{manualOutput}</div>
-                            ) : (
-                                <div className="space-y-1.5">
-                                    <div className="text-[var(--text-tertiary)] opacity-60 mb-4 font-bold"># Initializing operational context for session {activeJob.id}...</div>
-                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:02</span> <span className="text-[var(--accent)] font-bold">[INFO]</span> <span className="text-[var(--text-secondary)]">Agent runtime v2.4.1 environment validated.</span></div>
-                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:03</span> <span className="text-[var(--accent)] font-bold">[INFO]</span> <span className="text-[var(--text-secondary)]">Consolidating endpoint metrics for <span className="text-[var(--text-primary)] font-bold italic">{activeJob.task}</span>.</span></div>
-                                    <div className="flex gap-4"><span className="text-[var(--text-tertiary)] w-10">09:14:03</span> <span className="text-[var(--success)] font-bold">[AUTH]</span> <span className="text-[var(--text-secondary)]">Target security certificate successfully negotiated.</span></div>
-                                    
-                                    {activeJob.status === 'RUNNING' && (
-                                        <div className="mt-4 space-y-1">
-                                            <div className="text-[var(--accent)] animate-pulse font-bold flex items-center gap-3">
-                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
-                                                <span>SCANNING_RESOURCE: arn:aws:s3:::prod-compliance-data-01</span>
-                                            </div>
-                                            <div className="text-[var(--accent)] animate-pulse [animation-delay:200ms] font-bold flex items-center gap-3">
-                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
-                                                <span>SCANNING_RESOURCE: arn:aws:s3:::prod-compliance-data-02</span>
-                                            </div>
-                                            <div className="text-[var(--accent)] animate-pulse [animation-delay:400ms] font-bold flex items-center gap-3">
-                                                <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
-                                                <span>ANALYZING_PERMISSION_DELTAS...</span>
-                                            </div>
-                                        </div>
-                                    )}
-                                    
-                                    {activeJob.status === 'FAILED' && (
-                                        <div className="mt-4 p-4 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded shadow-lg animate-in shake duration-500">
-                                            <div className="text-[var(--danger)] font-bold flex items-center gap-2 mb-1">
-                                                <Hash size={12} /> CRITICAL_THREAD_ABORT
-                                            </div>
-                                            <div className="text-[var(--text-primary)] font-medium leading-relaxed">Connection timeout after 30s. Target node 10.0.0.15 unreachable in current VPC scope.</div>
-                                            <div className="mt-3 text-[9px] text-[var(--danger)] opacity-60 font-bold uppercase tracking-widest">Trace_ID: 0x55921A (ABORTED)</div>
-                                        </div>
-                                    )}
-                                    
-                                    {activeJob.status === 'COMPLETED' && (
-                                        <div className="mt-4 p-4 bg-[var(--success-subtle)] border border-[var(--success)] rounded shadow-lg animate-in zoom-in duration-300">
-                                            <div className="text-[var(--success)] font-bold flex items-center gap-2 mb-1">
-                                                <CheckCircle2 size={12} /> SESSION_TERMINATED_CLEANLY
-                                            </div>
-                                            <div className="text-[var(--text-primary)] font-medium italic">All compliance objectives satisfied. 0 Issues discovered in current infrastructure epoch.</div>
-                                        </div>
-                                    )}
-                                    <div className="opacity-20 mt-8 pt-4 border-t border-[var(--border-default)] text-[9px] font-bold tracking-[0.3em] text-center">END_OF_EVENT_LOG</div>
-                                </div>
-                            )}
+                            <div className="space-y-1.5">
+                                <div className="text-[var(--text-tertiary)] opacity-60 mb-4 font-bold"># {activeJob.task} — agent '{activeJob.agent}' — {activeJob.id}</div>
+
+                                {(activeJob.status === 'RUNNING' || activeJob.status === 'PENDING') && (
+                                    <div className="text-[var(--accent)] animate-pulse font-bold flex items-center gap-3">
+                                        <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] glow-accent" />
+                                        <span>{activeJob.status}...</span>
+                                    </div>
+                                )}
+
+                                {activeJob.status === 'FAILED' && (
+                                    <div className="mt-2 p-4 bg-[var(--danger-subtle)] border border-[var(--danger)] rounded shadow-lg">
+                                        <div className="text-[var(--danger)] font-bold flex items-center gap-2 mb-1">
+                                            <Hash size={12} /> EXECUTION_ERROR
+                                        </div>
+                                        <div className="text-[var(--text-primary)] font-medium leading-relaxed whitespace-pre-wrap">{activeJob.error || 'Unknown error'}</div>
+                                    </div>
+                                )}
+
+                                {activeJob.status === 'COMPLETED' && (
+                                    <div className="mt-2 p-4 bg-[var(--success-subtle)] border border-[var(--success)] rounded shadow-lg">
+                                        <div className="text-[var(--success)] font-bold flex items-center gap-2 mb-2">
+                                            <CheckCircle2 size={12} /> COMPLETED
+                                        </div>
+                                        <pre className="text-[var(--text-primary)] text-[10px] whitespace-pre-wrap">{JSON.stringify(activeJob.result, null, 2)}</pre>
+                                    </div>
+                                )}
+                                <div className="opacity-20 mt-8 pt-4 border-t border-[var(--border-default)] text-[9px] font-bold tracking-[0.3em] text-center">END_OF_EVENT_LOG</div>
+                            </div>
                         </div>
```

`activeJob.result`/`.error` now come from real `JobItem.result`/`.error` (widened in 1.2's schema
change) — this also fixes an until-now-unnoticed side issue: the old code checked
`data.result.stdout`, a field neither stub handler has ever returned (`active_auditor_handler`
returns `status`/`msg`/`findings_severity`/`evidence_cited`; `policy_analyzer_handler` returns
`status`/`msg`) — every prior manual trigger silently fell through to "No STDOUT received.", not
just the ones with 403/422 failures. Rendering the real `result` object directly sidesteps that.

`Layers`/`Database` icon imports stay (still used elsewhere in the file); `Hash`/`CheckCircle2`
stay in use (repurposed above, not orphaned).

### `src/components/StatusBadge.jsx`: add `PENDING`

```diff
     REVIEW: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'UNDER REVIEW' },
     RUNNING: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'RUNNING', animate: true },
+    PENDING: { color: 'var(--text-tertiary)', bg: 'var(--layer-2)', label: 'PENDING' },
     PROCESSING: { color: 'var(--accent)', bg: 'var(--accent-subtle)', label: 'PROCESSING', animate: true },
```

Without this, a `PENDING` row would fall back to the generic gray "unknown status" style — harmless,
but `PENDING` is now a real value this component can receive, so it earns its own entry like every
other real status here.

---

## What's deliberately NOT touched

- `data_service.py` / `fixtures.json`'s `jobs` array — becomes dead code, not deleted. Cleanup
  candidate for whenever Tier 4-style housekeeping happens next; deleting it now is out of scope for
  what this diff is actually here to do.
- Async/queued execution, "Stop Agent" wiring, real CPU/RAM telemetry, historical pagination beyond
  the 50-row cap — all explicitly Tier 3, out of scope per the roadmap.
- Agent Registry De-stubbing (`active-auditor`/`policy-analyzer` still return canned responses) —
  separate, unscoped effort per Decision #1.

## Verification plan

- `smoke_test.py` (expect 42/42 or higher if a new smoke check is worth adding for `/run-agent`'s
  new persistence — TBD during implementation) and `pytest` from `backend/` (expect 32/32 or higher).
  New DB table means re-checking the boot ritual matters more than usual here.
- Rebuild both `grc-backend` and `grc-frontend` (backend model change needs a real rebuild+restart,
  not just a frontend swap).
- Manual/Playwright pass: trigger both `active-auditor` and `policy-analyzer` from the picker, confirm
  each appears in the grid with real duration/result, confirm the WS broadcast updates a second
  browser tab without a manual refresh (the actual "real-time monitor" claim this feature is named
  for), confirm `FAILED` rendering by triggering an unregistered agent id directly via API (bypassing
  the picker) if a natural failure case doesn't present itself otherwise.
- Confirm `log_security_event` writes a `security_events` row per run (Decision #3's actual point) —
  check via the existing security-events read path, not just that the code compiles.
