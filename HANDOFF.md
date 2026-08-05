# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 5, 2026
**Version:** 1.4.0 (Retrieval-Tuned & Re-Ranked + Golden Mapping; TPRM module fully built out)
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
MEMORY.md before quoting any of the old 44/72/78/82/86% figures). The TPRM module's entire roadmap — Tier 1,
Tier 2, and Tier 3 — remains complete (unchanged since 2026-08-04). This is again an open pivot
point — pick one:

1. **RAG P2 Judge Calibration** — benchmark results are still flagged `v1_uncalibrated`; build a
   ~15-query human-labeled set to validate the locked judge prompt.
2. **RAG P3 Execution Monitor UI** — real-time agent monitor on the WebSocket bus (frontend healthy,
   bus ready; deferred since April).
3. **TPRM Tier 4** (opportunistic, low-priority) — test-data hygiene (smoke/pytest have accumulated
   hundreds of vendors/integrations across runs), or frontend component tests (none exist
   project-wide).
4. **Browser-verify TPRM's UI surfaces** — 2.3/3.1/3.2/3.3 were all built and verified via
   API/curl/WS-client checks only, still no browser-automation tool used on them as of this session.
5. ~~The v1 benchmark report's category-breakdown table doesn't match its own raw archive~~ —
   **resolved 2026-08-05.** Traced (not a category-scheme mismatch; isolated to v1 only, v2's table
   matched its archive exactly) and fixed by direct computation from the archive — see
   `RAG_Benchmark_Report.md` §2/§3 and MEMORY.md.
6. **`EU AI ACT 2024_Doc.pdf` has a systematic text-extraction defect** (spaces injected mid-word,
   e.g. `"Ar ticle 9"`) — confirmed isolated to this one file in the 158-doc corpus (no other file
   shares its PDF producer). Would need re-extraction (new dependency — neither `pdfplumber` nor
   `PyMuPDF` is currently installed) and re-ingestion to fix properly. Parked, not urgent — Golden
   Mapping already hand-patches the three queries that were actually affected.

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
