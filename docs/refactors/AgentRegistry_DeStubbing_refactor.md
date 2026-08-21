# Agent Registry De-stubbing — Implementation Diff

**Status:** ✅ EXECUTED (2026-08-06). Applied as drafted, zero deviations in the code itself. Rebuilt
`grc-backend`. Verified: smoke 43/43, pytest 32/32 (both clean when run in isolation — a first
smoke-test pass failed at 180s while a manual curl check was running concurrently against the same
single-worker backend; re-ran clean once nothing else was hitting it, see the corrected finding
below), real curl round-trips against both agents, `tests/security_audit.py` re-verified working
(copied into the container to run — its dependency chain isn't in the local host Python env — 3/4
deny-by-default cases pass, the 4th fails on a stale, pre-existing test-case id (`compliance_checker`)
that predates this change and was never in the registry even before de-stubbing, unrelated), and a
Playwright browser pass triggering both agents from the real UI picker (7/7 checks, zero console
errors).

**Two things measured wrong in the draft, corrected here with real numbers — the code is unaffected,
only the estimates were off:**

1. **`active-auditor`'s real duration is ~43s, not the ~16s estimated.** Measured twice, cold and
   warm, both ~43s — this isn't a one-time cold-start tax (the reranker/vector-store were already
   warm on the second measurement and it was no faster), it's the genuine steady-state cost of 4
   sequential real RAG queries against this corpus, at roughly ~11s/query rather than the
   benchmark's cited ~4s average latency. The draft's estimate was simply too optimistic.
2. **The blocking scope is wider than "the triggering admin waits."** `rag_engine.query()`'s FAISS
   `similarity_search` and the cross-encoder reranker's `.predict()` both run synchronously,
   CPU-bound, directly on the single asyncio event loop — no executor offload. For the ~43s
   `active-auditor` runs, this means **the entire backend is unresponsive to every user**, not just
   the one who clicked the button — confirmed empirically: a concurrent login request queued behind
   an in-flight `active-auditor` call and only completed once it finished. This isn't new
   architecture introduced by this change — `/chat` already had this exact characteristic for a
   single ~4s query — but `active-auditor` now exercises it at roughly 10x the duration of a normal
   chat message, via a button rather than only organic usage. Decision #3 ("stay synchronous... a
   4-20s hang is tolerable for a manually-triggered, admin-only action") was confirmed on an
   incomplete picture of the actual cost and its blast radius. Not re-litigating that decision
   unilaterally — it was explicitly confirmed, the code works correctly, and this is a low-traffic
   personal/portfolio system, not a live multi-tenant service — but flagging accurately rather than
   quietly letting the original ~16s figure stand uncorrected.
**Scope confirmed 2026-08-06** per `AgentRegistry_DeStubbing_Roadmap.md`'s four decisions, all
recommended options taken: fixed NIST AI RMF question set for `active-auditor`; real RBAC `Policy`
table for `policy-analyzer`; stay synchronous; no new frontend input.

One implementation detail resolved while drafting (flagged as a risk, not a decision, in the
roadmap): `rag_engine.query()` is `async`, but `InternalAgentRunner.execute_agent()` and both
handlers are currently sync. Making `execute_agent` and both handlers `async def` is the clean fix
— confirmed safe by checking `_run_async` (`core/database.py`): it always runs its coroutine in a
dedicated thread with a fresh event loop, so `policy_analyzer_handler` calling the sync
`audit_logger.list_policies()` from inside an `async def` handler is safe, no "different loop"
conflict, same mechanism already proven this session by `create_agent_run`/`finish_agent_run`.

**One more caller found that the roadmap didn't check:** `tests/security_audit.py` — a standalone
diagnostic script (not pytest-collected, run via `python tests/security_audit.py`) — calls
`agent_runner.execute_agent()` directly and synchronously. Making `execute_agent` async breaks it
unless updated too. Included below.

---

## `core/agent.py` — the actual de-stubbing

```diff
 import os
-from typing import Dict, Any, Callable
+from typing import Dict, Any, Callable, Awaitable
 from core.logger import logger
+from core.rag import rag_engine
+from core.database import audit_logger

 # --- GRC.OS AGENT REGISTRY (Rule #2) ---
-# Hardcoded mapping of safe identifiers to Python callables. 
+# Hardcoded mapping of safe identifiers to Python callables.
 # This is the single source of truth for all autonomous capabilities.

-def active_auditor_handler(args: Dict[str, Any]) -> Dict[str, Any]:
-    """Handler for the NIST AI RMF Active Auditor analyst-role agent."""
-    return {
-        "status": "success", 
-        "msg": "NIST AI RMF Audit Complete", 
-        "findings_severity": "HIGH",
-        "evidence_cited": args.get("include_evidence", True)
-    }
-
-def policy_analyzer_handler(args: Dict[str, Any]) -> Dict[str, Any]:
-    """Stub for the operational policy analyzer."""
-    return {"status": "success", "msg": "Strategic analysis complete: 0 gaps found in active-policy-set."}
+NIST_AI_RMF_AUDIT_QUESTIONS = [
+    "What are the four core functions of the NIST AI Risk Management Framework?",
+    "What does the NIST AI RMF recommend for governance and accountability of AI systems?",
+    "What does the NIST AI RMF say about mapping and categorizing AI risk?",
+    "What does the NIST AI RMF recommend for measuring and monitoring AI system risk?",
+]
+
+async def active_auditor_handler(args: Dict[str, Any]) -> Dict[str, Any]:
+    """NIST AI RMF Active Auditor: runs a fixed set of canonical NIST AI RMF
+    questions through the real RAG pipeline (the same engine behind /chat,
+    measured at 92% accuracy on the 50-query benchmark) and aggregates real,
+    source-cited findings. Severity reflects corpus coverage: an audit that
+    can't substantiate a core RMF function from the ingested corpus is
+    itself a real finding, not a canned one."""
+    findings = []
+    all_sources = set()
+    unanswered = 0
+    for question in NIST_AI_RMF_AUDIT_QUESTIONS:
+        result = await rag_engine.query(question)
+        answer = result.get("answer", "")
+        sources = result.get("sources", [])
+        all_sources.update(sources)
+        if "INSUFFICIENT_DATA" in answer:
+            unanswered += 1
+        findings.append({"question": question, "answer": answer, "sources": sources})
+
+    total = len(NIST_AI_RMF_AUDIT_QUESTIONS)
+    if unanswered == 0:
+        severity = "LOW"
+    elif unanswered < total / 2:
+        severity = "MEDIUM"
+    else:
+        severity = "HIGH"
+
+    return {
+        "status": "success",
+        "msg": f"NIST AI RMF Audit Complete — {total - unanswered}/{total} core functions substantiated from corpus",
+        "findings_severity": severity,
+        "evidence_cited": len(all_sources) > 0,
+        "sources": sorted(all_sources),
+        "findings": findings,
+    }
+
+async def policy_analyzer_handler(args: Dict[str, Any]) -> Dict[str, Any]:
+    """Policy gap analysis: inspects the real RBAC Policy table (the
+    platform's own access-control capabilities) for governance gaps --
+    missing framework citations and disabled capabilities -- instead of
+    returning a canned "0 gaps found"."""
+    policies = audit_logger.list_policies()
+    total = len(policies)
+    missing_source_doc = [p["name"] for p in policies if not p.get("source_doc")]
+    inactive = [p["name"] for p in policies if not p.get("is_active")]
+    gap_count = len(missing_source_doc) + len(inactive)
+
+    return {
+        "status": "success",
+        "msg": f"Strategic analysis complete: {gap_count} gap(s) found across {total} active-policy-set entries",
+        "total_policies": total,
+        "missing_source_doc": missing_source_doc,
+        "inactive_policies": inactive,
+    }

 # Registry mapping: Explicit, Zero-Trust dispatch table
-AGENT_REGISTRY: Dict[str, Callable] = {
+AGENT_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
     "active-auditor": active_auditor_handler,
     "policy-analyzer": policy_analyzer_handler,
 }

 # --- ZERO-TRUST RUNNER (Rule #1) ---

 class InternalAgentRunner:
     """
-    Replaces the legacy AgentRunner. 
+    Replaces the legacy AgentRunner.
     Eliminates all use of subprocess.run() for agent execution.
     """
     def __init__(self, registry: Dict[str, Callable]):
         self._registry = registry

-    def execute_agent(self, agent_id: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
+    async def execute_agent(self, agent_id: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
         """
         Executes a registry-validated agent function directly in the running Python process.
         """
         if agent_id not in self._registry:
-            logger.error("Security Violation: Unregistered agent execution attempt", 
+            logger.error("Security Violation: Unregistered agent execution attempt",
                          agent_id=agent_id, status="BLOCKED")
             return {"error": f"Access Denied: Agent '{agent_id}' is not in the approved registry."}
-        
+
         try:
             handler = self._registry[agent_id]
             # Direct Python execution: No shell, No subprocess, No injection.
-            result = handler(args or {})
+            result = await handler(args or {})
             return result
         except Exception as e:
             logger.error("Internal Agent Execution Fault", agent_id=agent_id, error=str(e))
             return {"error": f"Internal Execution Error: {str(e)}"}
```

`get_approved_agents()` and the singleton line at the bottom are unchanged.

## `main.py` — one line, the `await`

```diff
-    result = agent_runner.execute_agent(payload.agent_id, payload.args)
+    result = await agent_runner.execute_agent(payload.agent_id, payload.args)
```

## `tests/security_audit.py` — the other caller

```diff
 import sys
 import os
+import asyncio

 # Add backend directory to path so we can import core modules
 sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

 from core.agent import agent_runner
 from core.logger import logger

-def run_security_audit():
+async def run_security_audit():
     logger.info("AUDIT: Starting AgentRunner Security Stress Test")
     ...
     for case in test_cases:
         logger.info(f"AUDIT RUN: Testing {case['name']}...")
-        result = agent_runner.execute_agent(case['agent'])
+        result = await agent_runner.execute_agent(case['agent'])
         ...

 if __name__ == "__main__":
     ...
-    run_security_audit()
+    asyncio.run(run_security_audit())
```

(`...` marks unchanged lines — the test-case list, dummy-script setup, and report printing all stay
as-is; this script's stale pre-Zero-Trust-Registry dummy-script logic is a separate, pre-existing
thing, not touched here.)

---

## What's deliberately NOT touched

- `ComplianceTerminal.jsx`'s fixture-fake policy grid (`get_compliance_policies`) — flagged in the
  roadmap as a separate, bigger, previously-unknown problem. Not folded into this pass.
- `OpsTerminal.jsx`, `core/models.py`, `schemas.py` — Execution Monitor UI already renders whatever
  `result`/`error` a run produces; no frontend or schema change needed for real handler output to
  show up correctly.
- Sync/async architecture of `/run-agent` itself (`BackgroundTasks`, a queue) — stays synchronous
  per Decision #3. `active-auditor` will now take roughly 4× single-RAG-query latency (~16s at the
  benchmark's measured ~4s/query average, four sequential questions, not run concurrently — kept
  sequential deliberately for simplicity/safety over a partial-speedup from `asyncio.gather`, given
  the underlying pipeline mixes truly-async I/O with FAISS's synchronous CPU-bound similarity
  search). Tolerable for a manually-triggered, rate-limited (`10/minute`), admin-only action, per
  Decision #3.
- New frontend input for `active-auditor`'s question — stays the fixed set per Decision #4.

## Verification plan

- `smoke_test.py` (expect 43/43 — same count, `active-auditor`'s existing smoke check will now take
  materially longer, ~16s instead of near-instant; the `test()` helper already uses a 180s timeout,
  no change needed there) and `pytest` from `backend/` (expect 32/32).
- Rebuild `grc-backend` only — no frontend changes.
- Manual curl: trigger `active-auditor`, confirm the response contains real per-question
  `answer`/`sources` (not the old constant `"NIST AI RMF Audit Complete"`/`"HIGH"`), confirm
  `findings_severity` varies meaningfully rather than being hardcoded. Trigger `policy-analyzer`,
  confirm it reports the real 13-policies/`source_doc: null` gap instead of "0 gaps found".
- Browser check: trigger both from the Execution Monitor UI picker, confirm the console panel
  renders the real (larger, richer) result JSON without layout breakage — the `<pre>` block from
  Execution Monitor UI should handle this fine since it already renders arbitrary JSON, but worth
  eyeballing given `active-auditor`'s result is now meaningfully bigger (4 findings with full answer
  text each) than the two-line stub it replaces.
- Run `tests/security_audit.py` standalone to confirm its `await` fix works and its 4 deny-by-default
  cases (unregistered/malicious/traversal/empty agent ids) still all correctly fail fast without
  ever reaching a handler (the registry-membership check happens before `await handler(...)`, so
  these cases don't incur any RAG latency).
