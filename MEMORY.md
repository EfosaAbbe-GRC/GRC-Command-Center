# MEMORY.md — Durable Project Facts (read me on cold start)

*Stable knowledge that survives sessions. For what happened last session, read `SESSION.md`.
For the live task board, read `task.md`. For governance rules, read `GOVERNANCE.md` (binding).*

## What this is

GRC.OS / GRC Command Center — agentic GRC platform. FastAPI backend (:8001) + React 19 frontend
(:3006, Nginx) + PostgreSQL 16 + FAISS RAG over the `../GRC_Analyst/` PDF corpus. 4 containers via
`docker compose -f docker-compose-v2.yml`. Current accuracy baseline: **86%** on the 50-query suite
(2026-07-18).

## Boot & verify (the ritual)

```powershell
docker compose -f docker-compose-v2.yml up -d          # boot (no --build unless code changed)
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py  # expect 27/27
Invoke-RestMethod http://localhost:8001/api/v1/readiness  # expect all "ready"
```

Credentials: `.env` at project root (admin / analyst / viewer seeded on boot).

## Conventions (established, keep following)

- **Draft-first (GOVERNANCE §4.A):** propose code changes as a markdown diff artifact, wait for the
  user's "EXECUTE" before touching production files. Small deployment-blocking bugfixes found
  mid-deploy may proceed but must be documented in the artifact.
- **Task board:** `task.md`, priority-ordered (P0–P3), checkboxes with completion dates.
- **Benchmarks:** always archive `rag_benchmark_results.json` → `.vN_<change>.json` BEFORE re-running;
  one variable per run; report as `RAG_Benchmark_Report_vN.md` with trajectory table.
- **Corpus additions:** official sources only, validate `%%EOF` + size before install, SHA-256 goes
  to evidence chain on ingest automatically.

## Hard-won gotchas

- **Ingestion blocks the entire API** for its duration (sync work on the async event loop). Monitor
  via `docker logs grc-backend`, not HTTP. JWTs expire during the wait — re-login per poll.
- **OneDrive:** corpus folder is pinned always-keep-on-device (2026-07-18). Files failing with
  "Stream has ended unexpectedly" are TRULY truncated (check `%%EOF` tail), not dehydrated —
  7 such files sit quarantined as `GRC_Analyst/*.pdf.corrupt`.
- **FAISS `.integrity` manifest:** signer must exclude the manifest itself (fixed 2026-07-18; this
  asymmetry was the real FAISS-INT-001 cause). If "Integrity check failed" ever reappears after a
  legit ingest, re-sign via `docker exec grc-backend python -c "from core.rag import rag_engine; rag_engine._save_index_hash('faiss_index')"`.
- **Re-ranker cold start:** ~30s first query after backend rebuild (downloads
  `cross-encoder/ms-marco-MiniLM-L-6-v2`). Warm with a throwaway query before benchmarking.
- **CLAUDE.md history:** its architecture header drifted before (claimed Gemini 2.0 + Google
  embeddings when code used 2.5-flash + MiniLM). Synced 2026-07-18 — keep it synced when rag.py changes.

## Key numbers to not re-derive

- Benchmark trajectory: 44 (v1, Apr 11) → 72 → 78 → 82 → 86 (v5, Jul 18). Archives in
  `rag_benchmark_results.v*.json`; query list lives inside `backend/tests/rag_benchmark.py`.
- Corpus: 158 valid PDFs, 17,088 splits @ 1000/100 chars.
- Smoke test: 27 checks, includes live DB-trigger immutability probe via `docker exec`.
- 7 open benchmark failures: #16/#19/#49 (EU AI Act→Golden Mapping), #6 (CSF tiers table),
  #50 (CISA booklet missing), #36/#45 (jitter→judge calibration).
