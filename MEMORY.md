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
file-upload evidence linkage into `evidence_chain`. **Browser-verified 2026-08-06** (all four UI
surfaces driven live via Playwright, not just API-tested; the one UX bug that pass found was fixed
same day — see gotchas). See `TPRM_Roadmap.md` for the full item-by-item history; only opportunistic
Tier 4 hardening remains, unscheduled. **Execution Monitor UI also built and browser-verified
2026-08-06**: `OpsTerminal.jsx` now shows real agent-run data (new `AgentRun` table, real
PENDING/RUNNING/COMPLETED/FAILED lifecycle, real `JOB_STATUS` WebSocket push confirmed live across
two browser tabs) instead of a static fixture — see `ExecutionMonitor_refactor.md`. **Agent Registry
De-stubbing also built and browser-verified 2026-08-06**: `active-auditor` runs 4 canonical NIST AI
RMF questions through the real `rag_engine.query()` pipeline (same one behind `/chat`) and returns
real source-cited findings; `policy-analyzer` inspects the real RBAC `Policy` table and reports the
genuine gap sitting there (all 13 seeded policies missing `source_doc`). Real cost: `active-auditor`
takes **~43s and blocks the entire backend for everyone** during that window, not just the triggering
request — see gotchas. See `AgentRegistry_DeStubbing_refactor.md` for the executed diff.
**`ComplianceTerminal.jsx`'s misleading "live scanning" UI fixed the same day (2026-08-06)**: its
5-policy grid (`get_compliance_policies`) is 100% static fixture data representing external
infrastructure controls (AWS S3 encryption, IAM MFA, etc.) with no real backing in this project —
unlike TPRM/Execution Monitor/Agent Registry, there was nothing real to wire it to, so "de-stubbing"
it the same way wasn't achievable. Worse than just static: its `Update Policy`/`REMEDIATE_NOW`
buttons both silently called `/ingest` (RAG re-indexing) regardless of which policy was selected,
and its evidence panel showed hardcoded fake incident text. Fixed via honesty instead of fake
realism: added a `REFERENCE_CATALOG` badge, removed the misleading buttons, replaced the fake log
with an honest static note. See `ComplianceGrid_Honesty_refactor.md`. `Framework_Mappings`
(`get_framework_mappings`) closed the same day **2026-08-13** — re-investigated cold rather than
assumed: it's *not* the same class of problem (no misleading buttons, no fabricated logs, just static
hand-curated control-mapping content — a legitimate GRC artifact). Added a one-line honest caption
("Hand-curated reference mapping — not live-computed.") under the panel header so it's unambiguous
even standalone, not relying on the neighboring panels' labels by inference. See
`FrameworkMappings_Honesty_refactor.md`. Frontend-only, browser-verified (5/5 checks, zero console
errors).

## Project direction (durable — read before proposing what's next)

This is a **progressive** project. The eventual goal is shipping to production, but **not soon** —
no deadline pressure to close gaps fast. A full professional assessment against real market GRC
tools was given 2026-08-06 (see that session's closing exchange in `SESSION.md` for the full text)
— the user is already aware of every gap it surfaced (no live infrastructure integration behind
`ComplianceTerminal`'s grid, no multi-tenancy/SSO, single-process architecture with the
FAISS/reranker full-backend-blocking issue, zero frontend tests). **Don't re-raise these as new
findings in a future session** — they're known and accepted as expected for where this project is.

**Before any real production push, the explicit ask is a genuine hands-on, rigorous personal-use
pass** — actual end-to-end workflows across terminals as a real user would run them (log in per
role, run a vendor through the full TPRM lifecycle, trigger both real agents, export reports, work
the compliance grid), not the feature-by-feature build-then-verify-in-isolation pattern this project
has mostly used so far. That isolated pattern is good at catching "does this one thing work" but
misses friction and gaps that only surface when features are used together over a realistic
session. **This is the right thing to propose once the backlog runs dry of clear next builds, or
whenever production-readiness comes up as a live question** — not something to wait to be asked for
explicitly, and not a checklist of the known gaps to start silently closing.

**First TPRM dogfooding pass done 2026-08-13, API layer only** — one realistic fictional vendor
(`Meridian Cloud Storage`, two integrations, 26 individually-reasoned stages, real risk-acceptance
sign-offs) driven through the real backend on the dev stack. Zero application bugs found. See
`TPRM_Dogfooding_Pass_2026-08-13.md`. **Explicitly incomplete:** no browser-automation tool was
available that session, so the actual React UI was never clicked through against this data — do
that (Playwright or manual) before calling the dogfooding ask fully satisfied. This vendor's data is
real dev-stack state now, not test noise — don't purge it in a future Tier-4-style cleanup.

## Boot & verify (the ritual)

**Changed 2026-08-13 (TPRM Tier 4):** `smoke_test.py`/`pytest` now default to an isolated test
stack (`docker-compose.test.yml`, port 8002) instead of the dev/dogfooding stack — see
`TPRM_Tier4_TestDataHygiene_refactor.md`. A bare run no longer touches dev-stack data.

```powershell
docker compose -f docker-compose-v2.yml up -d           # boot dev stack (no --build unless code changed)
docker compose -f docker-compose.test.yml up -d         # boot isolated test stack (own DB, port 8002,
                                                          # reuses the real FAISS index read-only)
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # hits :8002 by default -- expect 43/43
cd backend; python -m pytest -v; cd ..                  # hits :8002 by default -- expect 32/32,
                                                          # MUST run from backend/ (pyproject.toml's
                                                          # smoke_test.py --ignore only applies from
                                                          # that rootdir)
Invoke-RestMethod http://localhost:8001/api/v1/readiness  # dev stack health -- expect all "ready"
                                                            # (read-only, safe to run directly against
                                                            # the dev stack any time)
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py  # expect 46/50 (92%) -- scorer fixed
                                                            # 2026-08-05, also needs PYTHONUTF8=1;
                                                            # untouched by the test-stack split,
                                                            # still targets :8001 by default (read-only,
                                                            # never created TPRM data)
```

**To check the dev/dogfooding stack specifically** (not just "does the suite pass"): set
`GRC_TEST_BASE=http://localhost:8001` before running `smoke_test.py`/`pytest` — every test file
resolves its target container (`grc-db-pg` vs `grc-db-pg-test`) and database name from the same
variable, so the immutability probes stay correct either way. Do this sparingly — the whole point
of the split is that routine runs shouldn't touch dev-stack data; reach for it only when you
specifically need to confirm the dev stack's own health end-to-end (e.g. right after resetting it).

Credentials: `.env` at project root (admin / analyst / viewer seeded on boot, both stacks).

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
- **A struggling Gemini API key turned `active-auditor`'s documented ~43s full-backend block into
  ~23 minutes** (found 2026-08-13 re-running smoke_test.py post-Tier-4): `rag.py`'s RAG-query call
  had no fast-fail/timeout, so when `GOOGLE_API_KEY` hit a `403 PERMISSION_DENIED` plus the free
  tier's `429 RESOURCE_EXHAUSTED` (20 requests/day) back to back, the SDK's own retry/backoff kept
  the entire single-threaded backend blocked for ~23 minutes — long enough that the calling
  smoke-test's own JWT expired mid-wait, cascading into unrelated-looking 401s on every subsequent
  check. **Resolved 2026-08-13**, not by fixing Gemini but by leaving it — the user had stopped
  paying for that Cloud project. Migrated the LLM call to **Groq** (`llama-3.3-70b-versatile`), and
  explicitly bounded `max_retries=2, timeout=30` on the new client so no future provider hiccup can
  reproduce this multi-minute block regardless of which API is behind it. See
  `LLM_Groq_Migration_2026-08-13.md`. Confirmed fixed, not just swapped: a live `active-auditor` run
  against Groq completed in ~31s (back in line with the original baseline), smoke 43/43 and pytest
  32/32 both clean and measurably faster than the failing-Gemini run minutes earlier.
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
- **`VendorRiskTerminal.jsx`'s stage detail panel used to collapse after every action taken inside
  it** (found 2026-08-06, browser-verifying TPRM; **fixed same day**, see `PanelCollapse_refactor.md`):
  `openIntegration()` unconditionally set `expandedStage` to `null`, and it was called after both
  `updateStage` (any pass/gap/review/n-a click) and the risk-acceptance `onSigned` callback — so
  marking a stage or signing an acceptance closed the very panel being looked at. Fix: `openIntegration`
  now takes `{ resetExpanded = true }`; the two refresh-after-action call sites pass `false`, the
  integration-list click keeps the default. If this regresses, it'll look like a re-click being
  needed after a stage action again.
- **No project `run`-skill existed for this app as of 2026-08-06**, and `chromium-cli` isn't on
  `PATH` — browser verification used Python's `playwright` package directly instead (already
  installed, `p.chromium.launch(headless=True)` worked with no setup). Worth generating a proper
  project skill via `/run-skill-generator` next time browser-driving this app comes up, so this
  discovery doesn't repeat.
- **`GET /ops/jobs` used to always return exactly 3 hardcoded fixture rows regardless of state;
  since Execution Monitor UI (2026-08-06) it reads real `AgentRun` rows and returns genuinely
  empty on a fresh boot with zero agent executions.** `fixtures.json`'s `jobs` array and
  `data_service.get_ops_jobs()` are now dead code (left in place, not deleted — a Tier 4 cleanup
  candidate). `smoke_test.py` now triggers a real `/run-agent` call before checking this endpoint
  for exactly this reason.
- **pytest went from ~2min to ~4m45s this session (same 32 tests, no new tests added to that
  count)** on the same dataset-growth trend already noted for the `test_tprm_export_csv` transient
  timeout — a third data point that Tier 4 test-data hygiene (435+ vendors, 429+ integrations from
  accumulated smoke/pytest/verification runs) is worth doing sooner rather than later.
- **`rag_engine.query()`'s FAISS `similarity_search` and cross-encoder `.predict()` are both
  synchronous, CPU-bound calls made directly inside an `async def`, with no executor offload — they
  block the entire single-threaded event loop, not just the calling request.** Known and accepted
  for a single `/chat` query (~4s per the benchmark's average latency) but easy to underestimate
  once something chains several queries together: `active-auditor` (Agent Registry De-stubbing,
  2026-08-06) runs 4 sequential queries and takes **~43s measured** (steady-state, confirmed cold
  and warm — not a one-time model-load tax), during which **the whole backend is unresponsive to
  every user**, confirmed by a concurrent login request queuing behind an in-flight run. If
  something else on this backend seems to hang for tens of seconds with no error, check whether a
  RAG-chaining call (like `active-auditor`) is mid-flight before assuming a real bug — and don't run
  concurrent manual curl/API checks against this backend while timing something RAG-related, it'll
  contaminate the measurement (confirmed: an artificially-inflated 180s+ smoke-test failure turned
  out to be exactly this, not a defect — re-ran clean in isolation).
- **When a Python script needs to run inside `grc-backend` for verification** (e.g. one that imports
  `core.agent`/`core.rag` directly rather than going through the HTTP API), the local host Python
  environment does NOT have the full `requirements.txt` stack installed (confirmed:
  `ModuleNotFoundError: No module named 'langchain_huggingface'` running locally) — it has to run
  inside the container. `docker exec`/`docker cp` both work fine on this setup (with
  `MSYS_NO_PATHCONV=1`, per the existing path-mangling gotcha) — no need to assume they're
  unavailable. Note also: `backend/tests/` is **not** copied into the image (`smoke_test.py`/pytest
  are designed to run from the host against the container's exposed HTTP port, not via
  `docker exec`) — a script meaning to run in-process inside the container needs `docker cp`'d in
  first, and needs to land at the *same relative path* it expects at runtime if it does its own
  relative-path logic (found copying `security_audit.py` to the wrong depth first, which broke its
  unrelated `../agents` dummy-script bootstrap — fixed by copying to `/app/tests/` instead of
  `/app/`).
- **Piping `smoke_test.py`'s output through `head -N`/`tail -N` on this Windows/Git-Bash setup gives
  a false "exited with code 0"** (found 2026-08-13, TPRM Tier 4 verification): `head -N` closes its
  end of the pipe once it has its N lines, which kills the still-running Python process via
  `BrokenPipeError` the next time it tries to print — and in a bash pipeline, `$?`/the reported exit
  code reflects the *last* command (`head`/`tail`), not the producer, so this reads as a clean
  success even though the script died partway through and never printed its final `RESULTS:` line.
  `tail -N` has the same failure mode but looks like total silence instead (it can't emit anything
  until it sees EOF from the killed-early producer). Confirmed by checking for the process directly
  (`tasklist` showed nothing running) after a "completed" pipe run had truncated output. Fix: redirect
  straight to a file (`python ... > out.log 2>&1`, no pipe) and read the file after, never pipe a
  long-running script's stdout through `head`/`tail` on this setup.

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
- 4 open benchmark failures (post-correction), **all confirmed genuine via the 2026-08-05 judge
  calibration exercise** (not diagnostic artifacts): #50 (CISA booklet — source absent from corpus
  entirely), #6 (CSF tiers table — structured-content extraction gap, names the tiers but never
  defines them), #36 (NIST CSF↔ISO 27001 gap assessment — confirmed **hallucination**, not a
  prompt-strictness issue as first suspected), #45 (AI-agent compliance benefits — the one genuine
  true-C1 case, strict prompt really was too conservative here). #16/#19/#49 (EU AI Act cluster)
  fixed by Golden Mapping (`backend/data/golden_mappings.json`, 3 entries) — confirmed via verbatim
  reproduction of the curated context in the LLM's answers, not just a score-flip coincidence.
- **Judge calibration (2026-08-05):** the "locked judge prompt" (`validate_diagnostic.py`'s
  ANSWERED/REFUSED/HALLUCINATED classifier) is now `v2_calibrated` — 4/4 human agreement against the
  full current population of C1/C2 candidates (not a sample; only 4 exist today). Old
  `v1_uncalibrated` data was from May 24, predating the whole retrieval-tuning sprint — archived, not
  used. Separate finding: `diagnose_rag.py`'s first-pass discriminator shares the exact
  `.startswith("INSUFFICIENT_DATA")` bug already fixed in `rag_benchmark.py` the same session — wrong
  on 3/4 real cases, flagged not fixed (low urgency, real decisions should use the calibrated
  second-stage judge, not the first-pass label). See `JUDGE_CALIBRATION_v2.md`.
