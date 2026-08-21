# Agent Registry De-stubbing — Scoping (read this cold, before drafting anything)

**Created:** 2026-08-06 · **Status:** ✅ BUILT (2026-08-06) — all four decisions in §2 confirmed
with the recommended option, executed per `AgentRegistry_DeStubbing_refactor.md`. Both handlers now
do real work. One correction found only after measuring, not during scoping: §2 Decision #3's
"~4-20s, tolerable" framing undersold both the actual duration (~43s measured, not ~16s estimated)
and the blast radius (the synchronous FAISS/reranker work blocks the *entire* backend for that
window, not just the triggering request) — see the EXECUTED note at the top of the refactor doc for
the full, corrected picture. The decision itself wasn't reversed, just corrected with real numbers.

---

## 1. What's actually there today

`core/agent.py`'s two registered handlers are pure stubs — constant output regardless of input:

```python
def active_auditor_handler(args):
    return {"status": "success", "msg": "NIST AI RMF Audit Complete",
            "findings_severity": "HIGH", "evidence_cited": args.get("include_evidence", True)}

def policy_analyzer_handler(args):
    return {"status": "success", "msg": "Strategic analysis complete: 0 gaps found in active-policy-set."}
```

Both names imply real analysis; neither does any. The question is what "real" means for each —
and, while checking, two things turned up that change the shape of the answer:

- **`rag_engine.query(text: str)`** (`core/rag.py:330`) is the real, already-proven retrieval
  pipeline behind `/api/v1/chat` — 92% accuracy on the 50-query benchmark, golden mapping,
  cross-encoder reranking, real source citations. It's a natural substrate for `active-auditor`
  (the name literally says "NIST AI RMF Auditor," and the corpus has real NIST AI RMF content —
  8/8 on that benchmark category). But it's not instant: `RAG_Benchmark_Report_v6.md` puts average
  latency at ~4s per query. **This directly reopens Execution Monitor UI's Decision #2 from earlier
  today** ("stay synchronous — today's handlers return in milliseconds"). A real RAG-backed audit
  would not return in milliseconds. See Decision #3 below.

- **The RBAC `Policy` table is real, DB-backed, and already fully exposed** via
  `audit_logger.list_policies()` (used by `GET /admin/policies`, no new plumbing needed) — and it
  has a genuine, checkable gap sitting in it right now: **all 13 seeded policies have
  `source_doc: null`.** Zero of the platform's access-control capabilities cite a compliance
  framework justification. That's a real, defensible finding a "policy gap analysis" could report
  — not fabricated, not requiring new data.

- **Separate discovery, explicitly flagged, not folded into this scope:** `ComplianceTerminal.jsx`'s
  entire policy grid (`POL-001 AWS_S3_Encryption_v1`, `98%` compliance, `"12m ago"` last scan, etc.)
  turns out to be **also** 100% static fixture data — `data_service.get_compliance_policies()` just
  returns `self.cached_policies`, loaded once from `fixtures.json`, never mutated. Same shape of
  problem `/ops/jobs` had before Execution Monitor UI, but on the platform's primary compliance
  dashboard, not a secondary ops view. `policy-analyzer`'s stub message says "gaps... in
  active-policy-set" — language that maps naturally to the RBAC `Policy.is_active` field, not this
  separate fixture grid — so this finding doesn't have to block scoping `policy-analyzer`. But it's
  real, previously undocumented, and materially bigger than de-stubbing two agent handlers. Noting
  it here so it doesn't get silently conflated with this work or silently lost.

---

## 2. Key open decisions — confirm before drafting the diff

**Decision #1 — What should `active-auditor` actually audit?**
- *Recommended:* Run a small fixed set of canonical NIST AI RMF questions (covering the
  framework's core functions — GOVERN/MAP/MEASURE/MANAGE) through the existing `rag_engine.query()`,
  aggregate the real answers/sources into the result. Zero new ML/infra — reuses the exact pipeline
  already measured at 92% accuracy.
- *Alternative A:* Accept a free-text question via `args` instead of a fixed set — more flexible,
  but then this is functionally a re-skin of `/chat` behind a different button, and needs a new
  frontend input (see Decision #4). Worth asking what "agent" adds over just using the existing
  chat co-pilot directly.
- *Alternative B:* Audit something structural instead of RAG-based — e.g., cross-check TPRM
  assessment/evidence completeness against NIST AI RMF stage mappings. Genuinely more "audit"-shaped,
  but a much bigger, cross-module effort (defining what "NIST AI RMF compliance" means structurally
  across TPRM data is its own multi-day scoping question, not a De-stubbing-sized task).

**Decision #2 — What should `policy-analyzer` actually analyze?**
- *Recommended:* The real RBAC `Policy` table via the already-existing `audit_logger.list_policies()`
  — compute genuine metrics: count missing `source_doc` (13/13 today), count `is_active=False`,
  role-distribution summary. Matches the stub's own "active-policy-set" language, zero new backend
  plumbing.
- *Alternative:* The fixture-fake `ComplianceTerminal` grid described above — not recommended for
  this pass; that's a separate, bigger initiative (would mean first deciding what "real" compliance
  scanning even means for that grid, then building it) that shouldn't ride along inside a
  De-stubbing task.

**Decision #3 — Does `/run-agent` need to revisit sync-vs-async, now that a RAG-backed handler
could take several seconds instead of milliseconds?**
- *Recommended:* Stay synchronous for now. A 4-20s HTTP hang (one RAG call per audit question,
  sequential) is tolerable for a manually-triggered, admin-only, rate-limited (`10/minute`) action,
  and keeps today's just-shipped, just-verified Execution Monitor UI infrastructure completely
  untouched. `policy-analyzer` stays fast regardless (a single DB query) — this question is really
  only about `active-auditor`. RUNNING becoming briefly observable for the first time is a nice side
  effect of this choice, not a requirement being engineered for.
- *Alternative:* Move to `BackgroundTasks` now — more architecturally correct long-term, but reopens
  work on infrastructure finished and verified earlier today, to solve a problem (a slow HTTP
  response) that's tolerable, not broken.

**Decision #4 — Does `active-auditor` need new frontend input (e.g., a free-text question box), or
does "Run Agent" stay the current no-args single click?**
- *Recommended:* No new input. Both recommended options above (#1 fixed-question-set,
  #2 real-Policy-table) work with zero args — matching today's picker exactly, no frontend surface
  added. Keeps this pass backend-logic-only.
- *Alternative:* Add an args input — meaningfully more flexible (ties to Decision #1's Alternative A)
  but is frontend scope creep beyond "make the two registered handlers do real work."

---

## 3. What this looks like if all four recommended options are taken

Smallest-scope version: both handlers become real without any new tables, new endpoints, new
frontend inputs, or architecture changes.

- `active_auditor_handler(args)`: loop a short fixed list of NIST AI RMF questions through
  `rag_engine.query()` (note: handler today is synchronous, `rag_engine.query` is `async` — the
  caller, `InternalAgentRunner.execute_agent`, is also synchronous; this needs either an `asyncio`
  bridge inside the handler or promoting `execute_agent`/its call chain to async — a real
  implementation detail to resolve while drafting, not a scope question). Aggregate real
  sources/severity from the real answers.
- `policy_analyzer_handler(args)`: call `audit_logger.list_policies()` (already sync, no bridging
  needed), compute the source_doc/is_active gap metrics, return them as the real `result`.
- No changes to `core/models.py`, `schemas.py`'s `JobItem`/`AgentResult` shapes, `OpsTerminal.jsx`,
  or the WS broadcast path — Execution Monitor UI already renders whatever `result`/`error` a run
  produces, real or stub, so it "just works" once the handlers return real content.

This is meaningfully smaller than either TPRM or Execution Monitor UI — closer to a TPRM-Tier-1-sized
item (small, high-signal) than another multi-day build, *if* the recommended options hold. The async
bridging question in `active_auditor_handler` is the one piece of real implementation risk worth
surfacing now rather than discovering mid-diff.
