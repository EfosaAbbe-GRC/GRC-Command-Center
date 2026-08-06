# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 6, 2026
**Version:** 1.4.0 (Retrieval-Tuned & Re-Ranked + Golden Mapping; TPRM module fully built out AND
browser-verified; Execution Monitor UI and Agent Registry De-stubbing also both built AND
browser-verified)
**Baselines:** **92% RAG accuracy** (v6 benchmark — this is the scorer's actual, corrected output;
a benchmark-scorer bug found the same day was inflating every historical number by one query, see
`RAG_Benchmark_Report_v6.md` §3a) · smoke test **43/43** (grew from 42 with a real `/run-agent`
check) · pytest **32/32** (run from `backend/`; has been getting noticeably slower on the same test
count — see MEMORY.md gotchas, Tier 4 test-data hygiene)

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center (v1.4.0). Read `MEMORY.md` (durable facts),
`SESSION.md` (last session's log), and `task.md` (live board) in the project root, then verify the
stack per the boot ritual in MEMORY.md before proposing anything.

Current state: RAG accuracy is at **92%** (Golden Mapping metadata closed the EU AI Act cluster —
queries #16, #19, #49 — on top of a corrected 84% baseline: a benchmark-scorer bug found the same
day had been inflating every historical number since v1 by exactly one query; both the scorer and
every past report/archive were corrected in place, see `RAG_Benchmark_Report_v6.md` §3a and
MEMORY.md before quoting any of the old 44/72/78/82/86% figures). **Judge Calibration is also done**
(same day) — the locked judge prompt (`validate_diagnostic.py`'s ANSWERED/REFUSED/HALLUCINATED
classifier) is now `v2_calibrated`, 4/4 human agreement on the full current population of ambiguous
cases (see `JUDGE_CALIBRATION_v2.md`). The 4 remaining open benchmark failures are now all confirmed
genuine, not diagnostic artifacts.

**TPRM's entire roadmap (Tier 1+2+3) is complete, browser-verified, and the one bug that
verification found is fixed.** Driven live via Playwright/Chromium 2026-08-06: create integration →
mark gap → attach evidence → sign risk acceptance → export CSV, zero console errors. Found and
same-day-fixed a real bug (`PanelCollapse_refactor.md`, EXECUTED): `VendorRiskTerminal.jsx`'s stage
detail panel used to collapse after every status change or risk-acceptance sign-off.

**RAG P3 Execution Monitor UI is also now built and browser-verified (2026-08-06)**, closing what
had been the biggest remaining item on the board. Read `Execution_Monitor_UI_Roadmap.md` for the
original cold investigation and `ExecutionMonitor_refactor.md` for the executed diff if you need
the detail. Summary: `OpsTerminal.jsx`'s job grid now shows real data — new `AgentRun` table with a
real PENDING/RUNNING/COMPLETED/FAILED lifecycle, `/run-agent` persists + audit-logs
(`log_security_event`, closing a confirmed real gap — agent execution previously wrote zero
audit-trail entries) + broadcasts `JOB_STATUS`, `GET /ops/jobs` reads the real table instead of a
hardcoded fixture, and the console panel renders real `result`/`error` instead of fabricated
"SCANNING_RESOURCE" text. Verified with a two-tab Playwright regression proving the actual
real-time claim: triggering a run in tab 1 populates tab 2's grid via WebSocket push with zero
manual interaction on tab 2 (5/5 checks, zero console errors).

**Agent Registry De-stubbing is also now built and browser-verified (2026-08-06, same day)** —
`active-auditor`/`policy-analyzer` in `core/agent.py` do real work now instead of returning canned
responses. Read `AgentRegistry_DeStubbing_Roadmap.md` for the cold scoping (four decisions, all
confirmed with the recommended option) and `AgentRegistry_DeStubbing_refactor.md` for the executed
diff. Summary: `active-auditor` runs 4 canonical NIST AI RMF questions through the real
`rag_engine.query()` pipeline (the same one behind `/chat`, 92% benchmark accuracy) and returns real
per-question answers, real source citations, and severity computed from actual corpus coverage.
`policy-analyzer` inspects the real RBAC `Policy` table and reports the genuine gap sitting there —
all 13 seeded policies missing `source_doc`. **Important correction found only after measuring, not
during scoping:** `active-auditor`'s real duration is **~43s, not the ~16s originally estimated**
(steady-state, confirmed cold and warm), and — more significant — **it blocks the entire backend for
every user during that window, not just the triggering request** (FAISS similarity search and the
cross-encoder reranker run synchronously on the single event loop, no executor offload; pre-existing
`/chat` behavior, now exercised at ~10x normal duration via a button). Decision #3 ("stay
synchronous") wasn't reversed — it was explicitly confirmed and the code works correctly — but the
original framing undersold both the real cost and its blast radius. See MEMORY.md gotchas for the
full detail.

**`ComplianceTerminal.jsx`'s misleading "live scanning" UI is also fixed (2026-08-06, same day)** —
found while scoping De-stubbing: its 5-policy grid turned out to *also* be 100% static fixture data,
same as the RBAC grid was before this session, except representing *external infrastructure*
controls (AWS S3 encryption, IAM MFA, etc.) with no real system in this project to wire it to —
de-stubbing the way TPRM/Execution Monitor/Agent Registry were wasn't achievable here. Worse than
just static: its `Update Policy`/`REMEDIATE_NOW` buttons both silently called `/ingest` (RAG
re-indexing) regardless of which policy was selected, and its evidence panel showed hardcoded fake
incident text ("Security policy threshold breach") for any `FAIL`-status policy. User confirmed the
honest fix over attempting fake realism: `REFERENCE_CATALOG` badge added, the misleading buttons
removed, the fake log replaced with an honest static note. See `ComplianceGrid_Honesty_refactor.md`.
Frontend-only, no backend/schema changes. `Framework_Mappings` has the same underlying issue (a
separate fixture data source) — flagged, not touched in this pass.

This is again an open pivot point — every item on the post-TPRM menu since 2026-08-05 is now closed
(Execution Monitor UI, Agent Registry De-stubbing, ComplianceTerminal honesty). Pick one:

1. **TPRM Tier 4** (opportunistic, low-priority) — test-data hygiene has three independent data
   points now favoring doing it sooner, but the real fix is likely bigger than its "small effort"
   label suggests: `RiskAcceptance` rows (and any `Integration` that has one) are protected by a
   DB-level immutability trigger blocking UPDATE/DELETE by design — a naive "delete old test data"
   cleanup would either fail outright or require bypassing a security invariant this project
   deliberately built. The honest fix is probably a dedicated test schema/DB, not a cleanup script —
   found this scoping tonight, not yet fully investigated. Also: frontend component tests (none
   exist project-wide).
2. **`Framework_Mappings`' fixture-fake data source** (`get_framework_mappings`) — same underlying
   issue as the policy grid just fixed, separate data, not yet scoped.
3. **Revisit `active-auditor`'s synchronous execution now that its real cost is known precisely**
   (optional, not urgent) — ~43s of full-backend blocking per run is a materially different number
   than the ~16s originally discussed when Decision #3 was confirmed. Worth a fresh look with
   accurate numbers if it starts to feel worse in practice than it did on paper; not a defect as-is.
4. **`EU AI ACT 2024_Doc.pdf` has a systematic text-extraction defect** (spaces injected mid-word,
   e.g. `"Ar ticle 9"`) — confirmed isolated to this one file in the 158-doc corpus (no other file
   shares its PDF producer). Would need re-extraction (new dependency — neither `pdfplumber` nor
   `PyMuPDF` is currently installed) and re-ingestion to fix properly. Parked, not urgent — Golden
   Mapping already hand-patches the three queries that were actually affected.
5. **`diagnose_rag.py`'s first-pass discriminator has the same `.startswith("INSUFFICIENT_DATA")`
   bug already fixed in `rag_benchmark.py`** — wrong on 3 of 4 real cases in the 2026-08-05
   calibration run (see `JUDGE_CALIBRATION_v2.md` §4). Low urgency (the calibrated second-stage
   judge is what real decisions should use), but a clean small fix if anyone's in that file.
6. **`diagnose_rag.py` has no resume-from-checkpoint logic** — a ~40-minute run died silently mid-way
   on 2026-08-05 (no error captured, likely transient network turbulence) and had to be patched
   ad-hoc (not committed) to resume from its own checkpoint file rather than restart from scratch.
   Worth adding permanently if this script gets run again — see `JUDGE_CALIBRATION_v2.md` §1.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 43/43
cd backend; python -m pytest -v; cd ..                   # expect 32/32 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # expect 46/50 (92%) -- scorer fixed 2026-08-05
cat RAG_Benchmark_Report_v6.md
```

**Note:** `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an
IPv6/IPv4 loopback mismatch in the healthcheck itself, not a real outage; see MEMORY.md gotchas).
The app serves fine on `http://localhost:3006`.
