# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 6, 2026
**Version:** 1.4.0 (Retrieval-Tuned & Re-Ranked + Golden Mapping; TPRM module fully built out AND
browser-verified)
**Baselines:** **92% RAG accuracy** (v6 benchmark — this is the scorer's actual, corrected output;
a benchmark-scorer bug found the same day was inflating every historical number by one query, see
`RAG_Benchmark_Report_v6.md` §3a) · smoke test **42/42** · pytest **32/32** (run from `backend/`)

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
genuine, not diagnostic artifacts. The TPRM module's entire roadmap — Tier 1, Tier 2, and Tier 3 —
remains complete (unchanged since 2026-08-04), **and as of 2026-08-06 all four of its Tier 2/3 UI
surfaces (2.3, 3.1, 3.2, 3.3) are browser-verified**, not just API-tested — driven live via
Playwright/Chromium (admin session): create integration → mark gap → attach evidence → sign risk
acceptance → export CSV, zero console errors, zero failed network requests. One real
previously-unknown bug found along the way — **fixed the same day** (`PanelCollapse_refactor.md`,
EXECUTED): `VendorRiskTerminal.jsx`'s stage detail panel no longer collapses after a status change
or risk-acceptance sign-off; `grc-frontend` rebuilt, smoke 42/42, pytest 32/32, dedicated Playwright
regression confirmed the exact original scenario now stays open (7/7 checks). This is again an open
pivot point — pick one:

1. **RAG P3 Execution Monitor UI** — **read `Execution_Monitor_UI_Roadmap.md` first, cold, before
   assuming anything about scope.** The "frontend healthy, bus ready" framing this carried for
   months turned out to be wrong once actually investigated 2026-08-05: `OpsTerminal.jsx`'s job grid
   is a static fixture that never updates, the WS message type it listens for (`JOB_STATUS`) is
   never broadcast by the backend, agent execution has zero persisted lifecycle (no job table
   exists anywhere), and the "Run Agent" button is currently broken end-to-end (three independent
   bugs). This is real, mostly-net-new work — a persistence layer + broadcast wiring + frontend
   rewire, roughly TPRM-Tier-2-sized, not a small polish item. The roadmap has three open decisions
   to confirm with the user before drafting the actual diff (sequencing vs. Agent Registry
   De-stubbing; sync vs async execution; whether agent runs need audit-trail rigor).
2. **TPRM Tier 4** (opportunistic, low-priority) — test-data hygiene (smoke/pytest/verification runs
   have accumulated 435+ vendors / 429+ integrations — this also caused one transient pytest
   `ReadTimeout` on 2026-08-06, reproduced clean on rerun, but a second data point that this is worth
   doing sooner), or frontend component tests (none exist project-wide).
3. **`EU AI ACT 2024_Doc.pdf` has a systematic text-extraction defect** (spaces injected mid-word,
   e.g. `"Ar ticle 9"`) — confirmed isolated to this one file in the 158-doc corpus (no other file
   shares its PDF producer). Would need re-extraction (new dependency — neither `pdfplumber` nor
   `PyMuPDF` is currently installed) and re-ingestion to fix properly. Parked, not urgent — Golden
   Mapping already hand-patches the three queries that were actually affected.
4. **`diagnose_rag.py`'s first-pass discriminator has the same `.startswith("INSUFFICIENT_DATA")`
   bug already fixed in `rag_benchmark.py`** — wrong on 3 of 4 real cases in this session's
   calibration run (see `JUDGE_CALIBRATION_v2.md` §4). Low urgency (the calibrated second-stage
   judge is what real decisions should use), but a clean small fix if anyone's in that file.
5. **`diagnose_rag.py` has no resume-from-checkpoint logic** — a ~40-minute run died silently mid-way
   this session (no error captured, likely transient network turbulence) and had to be patched
   ad-hoc (not committed) to resume from its own checkpoint file rather than restart from scratch.
   Worth adding permanently if this script gets run again — see `JUDGE_CALIBRATION_v2.md` §1.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 42/42
cd backend; python -m pytest -v; cd ..                   # expect 32/32 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # expect 46/50 (92%) -- scorer fixed 2026-08-05
cat RAG_Benchmark_Report_v6.md
```

**Note:** `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an
IPv6/IPv4 loopback mismatch in the healthcheck itself, not a real outage; see MEMORY.md gotchas).
The app serves fine on `http://localhost:3006`.
