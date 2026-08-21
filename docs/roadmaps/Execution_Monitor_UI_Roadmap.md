# Execution Monitor UI — Implementation Roadmap (read this cold, before drafting anything)

**Created:** 2026-08-05 · **Status:** ✅ BUILT (2026-08-06) — Tier 0 + Tier 1 + Tier 2 all executed
per `ExecutionMonitor_refactor.md` (now marked EXECUTED). All three decisions in §0 were confirmed
with the recommended option in each case. Smoke 43/43, pytest 32/32, real cross-tab WebSocket
verification passed 5/5. Tier 3 (async/queued execution, real telemetry, historical pagination)
remains explicitly out of scope, unchanged from this roadmap's original recommendation. This
document is now historical scoping record, not a live task list — see `task.md`/`SESSION.md` for
current state.

---

## 0. Correcting the record: "frontend healthy, bus ready" was optimistic

`HANDOFF.md` and `task.md` have described this item as "frontend healthy, bus ready ... deferred
since April" across several sessions. **That framing doesn't hold up against the actual code.**
Investigated fresh 2026-08-05 (agent/WS/DB/frontend, file:line references below) — here's what's
really there:

- **`useWebSocket.js` is genuinely solid** — real exponential-backoff reconnect (1s→2s→4s...capped
  30s), `onMessage` kept in a ref so reconnects don't tear down the handler. No rework needed. This
  is the one part of "frontend healthy" that's actually true.
- **`OpsTerminal.jsx`'s job table is a static fixture, not live telemetry.** `GET /api/v1/ops/jobs`
  (`main.py:487-489`) returns `data_service.get_ops_jobs()`, which is `fixtures.json`'s hardcoded
  `jobs` array (`backend/data/fixtures.json:44-72`) — loaded once at boot, **never mutated at
  runtime**. The grid renders once on mount and never updates.
- **The WebSocket message types the frontend listens for don't exist.** `OpsTerminal.jsx:56-65`
  branches on `INGEST_STATUS` (real), `JOB_STATUS` (never broadcast anywhere in the backend), and
  `POLICY_UPDATE` (also never broadcast). Grepped every `manager.broadcast` call site in the whole
  backend — there are exactly two: `INGEST_STATUS` (`main.py:337-341`) and `TPRM_REASSESSMENT_STATUS`
  (`core/tprm.py:229`). `JOB_STATUS` is 100% net-new backend work, not "ready."
- **Agent execution has no lifecycle to monitor.** `InternalAgentRunner.execute_agent()`
  (`core/agent.py:38-54`) calls the registry handler *synchronously inside the HTTP request* and
  returns immediately. No job ID is minted, no status row is written anywhere, no start/end
  timestamp is persisted. There is no `Job`/`Run`/`Execution` table in `models.py` (only
  `AuditLog`, `EvidenceChain`, `User`, `RefreshToken`, `SecurityEvent`, `Policy` exist) or in
  `tprm.py`'s models. A "real-time monitor" needs something with a PENDING→RUNNING→DONE lifecycle
  to observe; today's registry produces neither a queue nor elapsed time, just an instant return
  value.
- **The "Run Agent" button is currently broken end-to-end**, independent of monitoring scope:
  `src/lib/api.js:255-256` has `api.post('\run-agent', ...)` — a stray backslash, not `/run-agent`
  — and sends body field `agent_name`, but `AgentRunRequest` (`schemas.py:62-68`) requires
  `agent_id`. Even if the path were fixed, the call would 422 on Pydantic validation. It also sends
  `agent_id: 'compliance_checker'`, which isn't in `AGENT_REGISTRY` at all (only `active-auditor`
  and `policy-analyzer` are registered, `core/agent.py:20-23`) — would 403 "not in the approved
  registry" even with a valid schema.
- **The registry itself is two hardcoded stub functions**, not real work:
  ```python
  # core/agent.py:9-26 (full registry)
  def active_auditor_handler(args): return {"status": "success", "msg": "NIST AI RMF Audit Complete", "findings_severity": "HIGH", ...}
  def policy_analyzer_handler(args): return {"status": "success", "msg": "Strategic analysis complete: 0 gaps found..."}
  AGENT_REGISTRY = {"active-auditor": active_auditor_handler, "policy-analyzer": policy_analyzer_handler}
  ```
  Both return canned, constant results regardless of input. This is the *other* unchecked P3 box
  on the board ("Agent Registry De-stubbing") — see Decision #1 below for why it matters here.

**Bottom line:** this is a real, mostly-net-new feature (persistence layer + broadcast wiring +
frontend rewire + bugfixes), not a "wire up the last mile" task. Budget accordingly — this is
closer to TPRM-Tier-2-sized work than a small polish item.

---

## Key open decisions — confirm with the user before drafting the diff

**Decision #1 — Build the monitor now, or sequence after Agent Registry De-stubbing?**
If the monitor ships first, it will faithfully show real-time status for agent runs whose actual
*content* is two hardcoded stub responses (`"findings_severity": "HIGH"` always,
`"0 gaps found"` always) — a real-time monitor of fake results. If De-stubbing ships first, the
monitor has something substantively real to watch, but that's a separate, larger effort (wiring
`active-auditor`/`policy-analyzer` to real RAG/audit logic) with its own scope.
*Recommendation:* build the monitor infrastructure now anyway — the persistence layer, broadcast
wiring, and frontend rewire are valuable regardless of what the handlers actually compute, and
De-stubbing can swap in real logic later without touching any of this. Flag it plainly in the UI
copy if needed ("demo data" / handler names) rather than blocking on De-stubbing.

**Decision #2 — Synchronous or async execution?**
Today's handlers return in milliseconds. Keeping `execute_agent()` synchronous but *persisting*
start/end state is simplest and matches current behavior — a "RUNNING" status would flash and
vanish before anyone could observe it anyway. Moving to `BackgroundTasks`/a real queue only starts
to matter once De-stubbing makes handlers slow (real RAG calls, real audits).
*Recommendation:* stay synchronous, but design the persisted schema (status enum, timestamps) so it
doesn't need a rewrite later — i.e. write it as if it *could* be async even though nothing today
requires it.

**Decision #3 — Does agent execution need audit-trail rigor (TPRM-style immutability), or is this
just an ops convenience view?**
`run-agent` already requires the `AGENT_EXECUTE` policy (`main.py:423`). Worth checking (not yet
confirmed in this investigation) whether it currently calls `log_security_event` anywhere — if not,
that's arguably a real gap given the project's "zero-trust, every privileged action goes in the
immutable trail" pattern already established for TPRM approvals and policy changes.
*Recommendation:* check this first; if missing, add it regardless of the rest of this feature's
scope — it's a small, independent security-parity fix in the same spirit as TPRM Tier 1.1.

---

## Tier 0 — Fix what's already broken (small, unblocks everything else)

**0.1 Fix `api.js`'s `runAgent()` call** — S
- *What:* `'\run-agent'` → `'/run-agent'`; body field `agent_name` → `agent_id` to match
  `AgentRunRequest`.
- *Where:* `src/lib/api.js:255-256`.
- *Depends-on:* nothing.

**0.2 Point `OpsTerminal.jsx`'s trigger at a real registry id** — S
- *What:* replace the hardcoded `'compliance_checker'` (not in `AGENT_REGISTRY`) with
  `'active-auditor'` or `'policy-analyzer'`, or add a picker if both should be triggerable.
- *Where:* `OpsTerminal.jsx:67-79`.
- *Depends-on:* 0.1 (no point fixing the id if the call itself 404s/422s first).

## Tier 1 — Give agent runs a real, persisted lifecycle (the actual prerequisite for "monitor")

**1.1 New `AgentRun` model + migration** — M
- *What:* `id, agent_id, status (PENDING/RUNNING/COMPLETED/FAILED), args (JSON), result (JSON),
  error, triggered_by, started_at, completed_at`.
- *Why:* nothing like this exists today (confirmed: `models.py` has no job/run table).
- *Where:* `core/models.py` (new model), a new Alembic-equivalent migration matching however this
  project's existing schema changes are applied (check `TPRM_Tier1_refactor.md`'s approach for
  precedent — TPRM tables were added the same way).
- *Depends-on:* Decision #3 (affects whether this also needs an audit-log write path).

**1.2 Wire `/api/v1/run-agent` to create + update the row, broadcast `JOB_STATUS`** — M
- *What:* on request: insert `AgentRun` row (status PENDING→RUNNING), call the existing
  synchronous handler (per Decision #2), update row to COMPLETED/FAILED with `result`/`error`,
  broadcast `{"type": "JOB_STATUS"}` (payload-free, matching the `TPRM_REASSESSMENT_STATUS`
  precedent at `tprm.py:229` — GOVERNANCE §3 bans `setInterval` polling but the established pattern
  here is "nudge, then refetch," not a full payload push).
- *Where:* `main.py:423-437` (`run_agent_endpoint`), `core/agent.py` (`InternalAgentRunner`).
- *Depends-on:* 1.1.

**1.3 Repoint `GET /api/v1/ops/jobs` at the new table** — S
- *What:* replace `data_service.get_ops_jobs()`'s fixture read with a real query against
  `AgentRun`, mapped to the existing `JobItem` schema shape (`schemas.py:26-33` — note `duration`
  is currently a formatted string like `"14m 22s"`; decide whether to keep that format
  client-computed from `started_at`/`completed_at`, or change the schema to raw timestamps — the
  latter is cleaner but touches the frontend rendering too).
- *Where:* `main.py:487-489`, `data_service.py:39-40`.
- *Depends-on:* 1.1, 1.2.

## Tier 2 — Wire the frontend to the real data

**2.1 Verify/adjust the existing `JOB_STATUS` WS handler** — S
- *What:* `OpsTerminal.jsx:56-65` already branches on `JOB_STATUS` and calls `refresh()` — this
  should largely "just work" once Tier 1 actually broadcasts that type. Verify the shape match and
  that `refresh()` re-hits the now-real `/ops/jobs` endpoint correctly.
- *Where:* `OpsTerminal.jsx`.
- *Depends-on:* 1.2, 1.3.

**2.2 Replace the hardcoded console-log simulation with real run output** — M
- *What:* the "SCANNING_RESOURCE... FATAL... CRITICAL_THREAD_ABORT" blocks are hardcoded JSX text
  keyed off `activeJob.status`, not streamed output — replace with real rendering of the selected
  `AgentRun`'s `result`/`error` fields.
- *Where:* `OpsTerminal.jsx` (the terminal console section).
- *Depends-on:* 1.1-1.3.

**2.3 Make the "Run Agent" button actually populate the grid** — S
- *What:* currently `runAgent()` sets `manualOutput` from the HTTP response directly and never
  touches `jobs`/`selectedJob` state — a triggered run doesn't appear in the table at all right
  now. Once 1.2's broadcast exists, this should resolve via 2.1's refresh, but verify the manual
  trigger path and the WS-driven path converge on the same visible state.
- *Where:* `OpsTerminal.jsx`.
- *Depends-on:* 2.1.

## Tier 3 — Explicitly out of scope for now (note, don't build)

- **True async/queued execution** (Celery-style worker, real "RUNNING" progress) — only justified
  once Agent Registry De-stubbing makes handlers slow. Building it now would be solving a problem
  that doesn't exist yet (today's handlers return in milliseconds).
- **Historical retention/pagination** beyond whatever's simplest — this reads as an ops convenience
  view, not an audit-trail replacement (see Decision #3 for the one piece of audit-trail rigor that
  *might* be warranted).

---

## Recommended sequence

0.1 → 0.2 → 1.1 → 1.2 → 1.3 → 2.1 → 2.2 → 2.3, checking Decision #3 (audit-log gap) alongside 1.1.
Draft as a single `_refactor.md` diff per GOVERNANCE §4.A once the three decisions above are
confirmed — this roadmap is the pre-work, not the diff itself.
