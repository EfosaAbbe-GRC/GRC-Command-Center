# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 6, 2026
**Version:** 1.4.0 (Retrieval-Tuned & Re-Ranked + Golden Mapping; TPRM module fully built out AND
browser-verified; Execution Monitor UI also built AND browser-verified)
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
manual interaction on tab 2 (5/5 checks, zero console errors). Agent Registry De-stubbing
(`active-auditor`/`policy-analyzer` still return two hardcoded canned responses, not real RAG/audit
logic) was deliberately deferred, per the roadmap's Decision #1 — the monitor infrastructure was
judged valuable regardless of what the handlers actually compute.

This is again an open pivot point — pick one:

1. **Agent Registry De-stubbing** — `active-auditor`/`policy-analyzer` in `core/agent.py` still
   return canned, constant responses regardless of input. The Execution Monitor UI now gives this
   real infrastructure to show its results in, making this a more natural next step than before
   (previously it would've been a real-time monitor of fake data with no visible payoff; now
   there's an actual UI surface that benefits from real handler output). Needs its own scoping pass
   — this repo's own established pattern is investigate-cold-first before assuming scope, same as
   both TPRM and Execution Monitor UI got.
2. **TPRM Tier 4** (opportunistic, low-priority) — test-data hygiene has three independent data
   points now favoring doing it sooner: a transient pytest `ReadTimeout` on 2026-08-06 (reproduced
   clean on rerun), and pytest's wall-clock time growing from ~2min to ~4m45s across the same 32
   tests in the same session. 435+ vendors / 429+ integrations accumulated from repeated
   smoke/pytest/verification runs. Also: frontend component tests (none exist project-wide).
3. **`EU AI ACT 2024_Doc.pdf` has a systematic text-extraction defect** (spaces injected mid-word,
   e.g. `"Ar ticle 9"`) — confirmed isolated to this one file in the 158-doc corpus (no other file
   shares its PDF producer). Would need re-extraction (new dependency — neither `pdfplumber` nor
   `PyMuPDF` is currently installed) and re-ingestion to fix properly. Parked, not urgent — Golden
   Mapping already hand-patches the three queries that were actually affected.
4. **`diagnose_rag.py`'s first-pass discriminator has the same `.startswith("INSUFFICIENT_DATA")`
   bug already fixed in `rag_benchmark.py`** — wrong on 3 of 4 real cases in the 2026-08-05
   calibration run (see `JUDGE_CALIBRATION_v2.md` §4). Low urgency (the calibrated second-stage
   judge is what real decisions should use), but a clean small fix if anyone's in that file.
5. **`diagnose_rag.py` has no resume-from-checkpoint logic** — a ~40-minute run died silently mid-way
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
