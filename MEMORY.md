# MEMORY.md — Durable Project Facts (read me on cold start)

*Stable knowledge that survives sessions. For what happened last session, read `SESSION.md`.
For the live task board, read `task.md`. For governance rules, read `GOVERNANCE.md` (binding).*

## What this is

GRC.OS / GRC Command Center — agentic GRC platform. FastAPI backend (:8001) + React 19 frontend
(:3006, Nginx) + PostgreSQL 16 + FAISS RAG over the `../GRC_Analyst/` PDF corpus. 4 containers via
`docker compose -f docker-compose-v2.yml`. Current accuracy baseline: **92%** on the 50-query suite
(2026-08-05, Golden Mapping metadata + a scorer-bug fix — see `RAG_Benchmark_Report_v6.md` §3/§3a;
**this is now the scorer's actual output**, not a manual footnote — the whole historical trajectory
was corrected the same day, see "Key numbers" below). **TPRM (Third-Party Risk Management) module —
Tier 1, 2, and 3 all complete as of 2026-08-04**: 13-stage vendor egress/ingress assessment, risk
acceptances, vendor-level risk rollup, WebSocket-pushed reassessment surfacing, CSV export, and
file-upload evidence linkage into `evidence_chain`. See `TPRM_Roadmap.md` for the full item-by-item
history; only opportunistic Tier 4 hardening remains, unscheduled.

## Boot & verify (the ritual)

```powershell
docker compose -f docker-compose-v2.yml up -d          # boot (no --build unless code changed)
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py  # expect 42/42 (grew from 27 with TPRM)
cd backend; python -m pytest -v; cd ..                 # expect 32/32 — MUST run from backend/,
                                                         # not repo root (pyproject.toml's
                                                         # smoke_test.py --ignore only applies
                                                         # from that rootdir)
Invoke-RestMethod http://localhost:8001/api/v1/readiness  # expect all "ready"
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py  # expect 46/50 (92%) -- scorer fixed
                                                            # 2026-08-05, also needs PYTHONUTF8=1
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
- **New Docker volume mount → check the Dockerfile, not just docker-compose.yml.** Adding a named
  volume in `docker-compose-v2.yml` alone isn't enough if the mount target is a *new* path under
  `/app/data/` — the backend runs as non-root `grcuser`, and Docker only inherits ownership into a
  fresh volume from a path that already exists (and is already `chown`'d) in the image. Any new
  writable subdirectory needs adding to `Dockerfile.backend`'s `mkdir -p ... && chown -R grcuser`
  line *before* it gets a volume mount, or every write 500s with `Permission denied` (found 2026-08-04
  building TPRM evidence upload).
- **A full `docker compose down` is more disruptive than a plain `up -d --build`** on this
  Windows/WSL2 Docker Desktop setup — expect transient network turbulence (spurious 401s,
  connection resets) right after, and re-verify with a solo test run before trusting a red result
  that immediately follows a `down`.
- **`rag_benchmark.py` also needs `PYTHONUTF8=1`** (same emoji-in-print issue as `smoke_test.py`) —
  fails with `UnicodeEncodeError` on a bare 🚀 print otherwise, on this Windows/cp1252 console.
- **Frontend container shows Docker-healthcheck "unhealthy" permanently, harmlessly** (found
  2026-08-05): `wget http://localhost:3006/` inside `grc-frontend` resolves `localhost` to `::1`
  first (per its `/etc/hosts`), and this Docker network has no IPv6 route, so the healthcheck
  connection-refuses on IPv6 and never retries IPv4 — nginx only binds `0.0.0.0:3006` (IPv4). The
  app itself is fine (`curl localhost:3006` from the host, or `wget http://127.0.0.1:3006/` from
  inside the container, both return 200). Not fixed — nothing currently depends on this health
  status — but don't mistake `docker ps`'s "unhealthy" for a real outage on this container.
- **On this Windows/Git-Bash setup, `docker cp`/`docker exec` args starting with `/` get silently
  mangled into Windows paths** (MSYS path conversion) — e.g. `docker exec grc-backend ls /tmp/`
  fails looking for a Windows `C:/...` path. Fix: `export MSYS_NO_PATHCONV=1` before the docker
  command (or prefix inline: `MSYS_NO_PATHCONV=1 docker exec ...`).
- **`EU AI ACT 2024_Doc.pdf`'s text extraction systematically injects spaces inside words**
  (`"Ar ticle 9"`, `"r isk"`, `"A ct"` — 576+ occurrences of "Article" alone, found 2026-08-05
  investigating Golden Mapping). Article numbers/legal terms survive but a literal string search
  for `"Article 9"` finds nothing in this file — likely a producer-specific artifact
  (`PDFlib+PDI 9.0.7p3`). Not fixed (would mean re-extracting/re-chunking/re-embedding this file, a
  bigger separate lever) — worth checking whether other PDFs from the same producer have it too,
  next time retrieval quality on this file is in question.

## Key numbers to not re-derive

- Benchmark trajectory (**corrected 2026-08-05** — see below): 42 (v1, Apr 11) → 70 → 76 → 80 → 84
  (v5, Jul 18) → **92** (v6, Aug 5 — Golden Mapping). Archives in `rag_benchmark_results.v*.json`;
  query list lives inside `backend/tests/rag_benchmark.py`.
- **A scorer bug (`answer.startswith("INSUFFICIENT_DATA")` instead of a substring check) inflated
  every single one of these numbers by exactly 1 query/2pts** — the model would answer part of a
  multi-part question and state `INSUFFICIENT_DATA` inline for the rest, which the strict prefix
  check missed. Originally reported: 44/72/78/82/86/94. Fixed in `rag_benchmark.py` 2026-08-05;
  every archived JSON and the v1/v2/v3/v5 report `.md` files were corrected in place (with a
  `_correction_note` field in the JSON and a callout in each `.md`), not silently overwritten. Trend
  and every inter-run delta (+28pts, re-ranker's +4 net, etc.) are unchanged — only absolute values
  moved. Full detail: `RAG_Benchmark_Report_v6.md` §3a.
- **Separate issue from the same correction pass, since traced and fixed:** v1's report had a
  category-breakdown table (NIST/ISO/EU AI Act/GDPR/etc.) that didn't match its own raw per-query
  archive on 6 of 7 rows, independent of the scorer bug above — confirmed NOT a category-scheme
  mismatch (`diagnose_rag.py`'s `get_expected_category()` uses identical id ranges), confirmed
  isolated to v1 only (v2's table matches its archive exactly on all 7 rows; v3/v5 don't carry this
  table format at all). The errors summed to exactly zero, which is why the report's grand total
  (22/50) was still right despite the per-category breakdown being wrong — the signature of a table
  that was estimated to match a known total rather than computed. Corrected 2026-08-05 by direct
  computation from the archive (`RAG_Benchmark_Report.md` §2/§3, struck-through not silently
  overwritten); also caught two specific wrong claims in §3's prose along the way (Annex A.5.7
  called a retrieval success when it was actually `INSUFFICIENT_DATA`; the target-human-transparency
  EU AI Act query called a failure when it was actually `ANSWERED`).
- Corpus: 158 valid PDFs, 17,088 splits @ 1000/100 chars. Unchanged by Golden Mapping — no
  re-ingestion, no FAISS rebuild; that change touches the query path only.
- Smoke test: 42 checks (grew from 27 pre-TPRM), includes live DB-trigger immutability probes via
  `docker exec`. Pytest: 32 checks (5 IAM + 27 TPRM) — run from `backend/`, not the repo root.
- 4 open benchmark failures (post-correction): #50 (CISA booklet missing — no lever fixes an absent
  source), #6 (CSF tiers table) and #35 (Three Lines of Defense) — same failure shape, a multi-part
  enumeration where only the first part is in the corpus, not yet assigned a fix, #36/#45 (jitter →
  judge calibration, unchanged). #16/#19/#49 (EU AI Act cluster) fixed by Golden Mapping
  (`backend/data/golden_mappings.json`, 3 entries) — confirmed via verbatim reproduction of the
  curated context in the LLM's answers, not just a score-flip coincidence.
