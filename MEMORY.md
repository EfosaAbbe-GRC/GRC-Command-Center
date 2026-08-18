# MEMORY.md — Durable Project Facts (read me on cold start)

*Stable knowledge that survives sessions. For what happened last session, read `SESSION.md`.
For the live task board, read `task.md`. For governance rules, read `GOVERNANCE.md` (binding).*

## What this is

GRC.OS / GRC Command Center — agentic GRC platform. FastAPI backend (:8001) + React 19 frontend
(:3006, Nginx) + PostgreSQL 16 + FAISS RAG over the `../GRC_Analyst/` PDF corpus. 4 containers via
`docker compose -f docker-compose-v2.yml`. LLM is **Groq (`openai/gpt-oss-120b`)** as of 2026-08-17.
History worth knowing: Gemini → Groq `llama-3.3-70b-versatile` on 2026-08-13 (the user stopped paying
for Gemini, see `LLM_Groq_Migration_2026-08-13.md`), then **Groq retired that Llama model within four
days** and named `openai/gpt-oss-120b` its successor — see `RAG_Model_Outage_refactor.md`. The model
id now lives in one place, `core/rag.py`'s `GROQ_MODEL` constant, and `/readiness` validates it
against Groq's live model list. **RAG accuracy is now MEASURED under Groq: 90.0% (45/50), v7,
2026-08-17** (`RAG_Benchmark_Report_v7.md`, archive `rag_benchmark_results.v7_groq_gptoss120b.json`).
Quote **90%**, not the older 92% — that was Gemini 2.5 Flash-era. **TPRM (Third-Party Risk
Management) module —
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
errors). **`ExecutiveTerminal` was the last and largest instance of this same class, closed
2026-08-17** (`ExecutiveHonesty_refactor.md`) — found by a 5-terminal empty-state audit. Its
`/executive/stats` and `/executive/dashboard` were pure `fixtures.json` passthroughs presented as live
governance KPIs *with trend deltas*, including **142 active users against 3 real accounts**. Now: the
three footer metrics are live-computed (unresolved TPRM gaps / policy `source_doc` coverage / user
count) and badged **Live**; the four panels with no possible real source (KPI cards, posture trend
chart, capital allocation, strategic indicators) are badged **Reference** with honest captions;
`UNIT_HEALTH` reads the real `/readiness` endpoint instead of a hardcoded "OPTIMAL" and
`FISCAL_CONTEXT` is computed rather than frozen at `Q3_FY2026`; and the non-functional
`1M/3M/6M/YTD` period buttons were removed (same call as ComplianceTerminal's misleading buttons).
`SECURITY_IDENTITY_AUDIT` and `STRATEGIC_POLICY_ENGINE` were always real and are untouched.
**`policy_coverage` now honestly reads 0%** (0 of 13 policies cite a framework source) — that is
correct, matches `policy-analyzer`'s independent finding, and is not a bug to "fix".

**The 5-terminal empty-state audit itself came back clean** (2026-08-17): all five terminals render
honest empty states under empty list payloads, zero crashes, zero JS errors, action controls
reachable. The hypothesis behind it — that the two 2026-08-16 bugs were one "no data" class with more
instances hiding — is **closed**; the Ops deadlock was the only one.

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

**TPRM dogfooding done in two halves — API layer 2026-08-13, UI/browser layer 2026-08-16/17. The
standing "genuine hands-on personal-use pass" ask is now SATISFIED for TPRM.** One realistic
fictional vendor (`Meridian Cloud Storage`, two integrations, 26 individually-reasoned stages, real
risk-acceptance sign-offs). The API half found **zero** application bugs
(`TPRM_Dogfooding_Pass_2026-08-13.md`); the UI half found **two real ones the API half structurally
could not see**, both since fixed and verified (`TPRM_Dogfooding_UI_Pass_2026-08-16.md`):

- **Stage evidence-notes wipe (data loss)** — clicking `pass`/`gap`/`review` erased that stage's
  `evidence_notes`, because the UI omits the field for those statuses and `tprm.py` assigned it
  unconditionally ("not sent" → NULL). Fixed via `payload.model_fields_set` gating; omission now
  preserves, explicit null still clears. Covered by a pytest regression test —
  **pytest is now 33/33, not 32/32.** See `StageNotes_Preservation_refactor.md`. Note the structural
  point: `stage_responses` is *not* protected by the immutability triggers covering `audit_logs`/
  `evidence_chain`/`risk_acceptances`.
- **Operations terminal deadlock** — `OpsTerminal.jsx`'s `!activeJob` early return sat above the
  **Run Agent** button, so zero `agent_runs` meant no UI path to create the first run. Fixed by
  scoping the empty state to the console pane; the same fix removed a **fabricated `stats` default**
  (`{running: 2, failed: 2}`, only recomputed when `jobs.length > 0`) that the early return had been
  hiding. See `OpsTerminal_EmptyState_refactor.md`.

This vendor's data is real dev-stack state, not test noise — don't purge it in a future Tier-4-style
cleanup; it was CSV-backed-up and diffed byte-identical after both passes. `agent_runs` holds 3 real
rows for the same reason (they keep Operations reachable).

**Two things still open from that work:** no *frontend* regression test for either bug (zero frontend
component tests exist project-wide — both bugs were frontend-triggered, so this gap now demonstrably
costs something), and **the UI has no way to author a stage note for `pass`/`gap`/`in_review` at
all** — notes are read-only in the panel and only the N/A prompt ever creates one, so a
browser-only analyst cannot record why a control passed. Needs a UI decision; deliberately kept out
of the data-loss fix.

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
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py  # 46/50 (92%) was the Gemini-era number,
                                                            # NOT YET RE-RUN against Groq (migrated
                                                            # 2026-08-13) -- also needs PYTHONUTF8=1;
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
- **Commit AND push after approval (standing rule, set 2026-08-17).** The full loop is
  draft → EXECUTE → verify → commit → **push**. Don't stop at commit, and don't end a piece of work
  with a dirty working tree. Requested directly after 12 commits sat unpushed for a day; the reasons
  are that work on one machine is at risk, and that the user uses **claude.ai as a second reviewer**
  against the GitHub repo — which only sees what has actually been pushed. Repo is
  `EfosaAbbe-GRC/GRC-Command-Center`, **public**, commits go straight to `main` (this repo's
  established pattern).
- **Explain the work in plain English, analogies welcome.** Standing request, 2026-08-17: the user
  wants to fully understand what he is approving, not rubber-stamp it. Lead with what a change means
  in practice, then the mechanism. This is not a request to simplify the *work* or soften findings —
  plain English means clearer, never vaguer.
- **Task board:** `task.md`, priority-ordered (P0–P3), checkboxes with completion dates.
- **Benchmarks:** always archive `rag_benchmark_results.json` → `.vN_<change>.json` BEFORE re-running;
  one variable per run; report as `RAG_Benchmark_Report_vN.md` with trajectory table.
- **Corpus additions:** official sources only, validate `%%EOF` + size before install, SHA-256 goes
  to evidence chain on ingest automatically.

## Hard-won gotchas

- **Groq's free tier caps you at 200,000 tokens/day, which is roughly ONE 50-query benchmark run —
  shared with every other LLM feature.** Hit 2026-08-17 ("Used 199,902"): the v8 benchmark exhausted
  the budget at query #11 and every query after returned `429`. Consequences to plan around:
  benchmarking is a **once-daily** operation, and **running one can take the app's AI features down
  for the rest of the day**. This also **confirms** what v7 recorded as an unproven hypothesis —
  its 6.6s → 16.86s "latency regression" was throttling as the budget depleted, *not* a slower model.
  Paid tier or local Ollama are the options if regular benchmarking is wanted.
- **The benchmark scored engine errors as correct answers — the SAME defect, in a THIRD place
  (2026-08-17).** `/chat` returns HTTP 200 with the error in the *body*, so `status_code == 200`
  passed and the 44-char error string satisfied `len(answer) > 20` → `ANSWERED`. The rate-limited v8
  run reported **96.0%, its best score ever, from 32 errors**. Fixed
  (`Benchmark_Scorer_Honesty_refactor.md`): engine failures are checked first and score as ERROR, 3
  consecutive failures abort the run, any run with an error is stamped `"valid": false` in the JSON
  and prints a DO-NOT-QUOTE banner, and the script now **exits non-zero**. **The pattern to
  internalise:** `active-auditor`, `smoke_test.py` and `rag_benchmark.py` all asked *"is there a
  response?"* instead of *"is the response real?"* — when checking any LLM-backed result, assume the
  error path returns 200 with plausible-looking text.
- **Hosted-model retirement is a live failure mode, and it took out the core feature for ~4 days
  silently (2026-08-17).** Groq retired `llama-3.3-70b-versatile` — every RAG call 404'd — while
  `/readiness` said "ready", `smoke_test.py` reported 43/43 twice, and `active-auditor` returned
  *"NIST AI RMF Audit Complete — 4/4 core functions substantiated, severity LOW"* from four failed
  queries. **All four checks were shape-checks, not substance-checks.** Now fixed:
  `/readiness` resolves `GROQ_MODEL` against Groq's live model list (cheap GET, not a generation
  call); the smoke test fails on the generic error string or zero sources; `active-auditor` returns
  `status: "error"` when the engine fails instead of a severity; and `/run-agent` records `FAILED`
  when a handler self-reports `status: "error"` (it previously only detected an `"error"` *key*, so a
  dead-engine audit was logged `COMPLETED`). All four verified with **deliberate negative tests**
  against a bogus model id — do the same if you touch them. See `RAG_Model_Outage_refactor.md`.
  **This is the second provider-side breakage in five days;** local Ollama remains the standing
  zero-external-dependency fallback if it recurs.
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
  discovery doesn't repeat. **Re-confirmed working 2026-08-16 (Chromium 141) — and note that the
  2026-08-13 session wrongly concluded "no browser-automation tool was available" without checking
  this package, which is what left the UI dogfooding half undone for three days. Check `python -c
  "import playwright"` before ever concluding browser verification isn't possible here.**
- **The UI CSS-uppercases most labels, so Playwright `inner_text()` returns `NOTES` / `GUIDANCE` /
  `RISK ACCEPTED`, not the casing in the JSX.** Case-sensitive substring assertions silently fail
  against a perfectly working UI — 7 of 28 checks in the first 2026-08-16 run were this, not app
  bugs. Worse, one such check passed **vacuously** (its `"Notes" in before` precondition was itself
  false), which would have hidden a real data-loss bug. Compare `.upper()`, and assert preconditions
  explicitly — a green check whose precondition never held is worse than a red one.
- **Whole-page text assertions are too coarse to trust on these terminals — this has now produced a
  false pass twice.** 2026-08-16: a vacuous precondition nearly hid the evidence-notes data loss.
  2026-08-17: `"READY" in page_text`, meant to confirm `UNIT_HEALTH` was wired to real `/readiness`,
  was satisfied by the unrelated `AUDIT_STATE` KPI card that also reads "READY" — the tile was actually
  rendering `--`, and only a **screenshot** caught it. Assert against the specific DOM node
  (`label.parentElement.lastElementChild.textContent`), not the page body. Screenshots are worth taking
  even when checks are green.
- **`/readiness` resolves after first paint**, so `UNIT_HEALTH` legitimately shows its `--` placeholder
  for a moment before settling on `READY`. Not a bug — but browser checks on it need an explicit wait,
  or they race the fetch.
- **The search/grep tool's output renders `/` as `\` in some content lines on this Windows setup.**
  This made `api.post('/run-agent', …)` look like `api.post('\run-agent', …)` — which would have been
  a genuine bug (`\r` = carriage return, breaking the endpoint) had it been real. It isn't: the file
  has `U+002F`, confirmed by character codes and by watching the live browser request succeed. Same
  artifact makes `border-white/10` look like `border-white\10` and `/>` look like `\>`. **Confirm any
  backslash-escape finding against raw bytes or live behaviour before reporting it.**
- **`docker-compose.test.yml` has no frontend service**, and the `:3006` frontend is built against the
  dev backend (`:8001`) — so there is **no browser path to the test stack**. Browser-verifying a
  frontend state that depends on backend data (e.g. an empty `agent_runs` table) can't be done by
  "just point the browser at :8002". Use Playwright `page.route()` interception to fulfil the endpoint
  with the payload you need instead; it isolates the frontend change and destroys no dev-stack data.
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

- Benchmark trajectory (**corrected 2026-08-05**): 42 (v1, Apr 11) → 70 → 76 → 80 → 84 (v5, Jul 18)
  → 92 (v6, Aug 5 — Golden Mapping, **Gemini 2.5 Flash**) → **90 (v7, Aug 17 — `openai/gpt-oss-120b`,
  first Groq-era measurement)**. **There is no valid v8.** The corpus refresh (2026-08-17) is done
  and sound, but its run hit the token cap at query #11 and the pre-fix scorer reported a **fake
  96%**; that archive is quarantined as `rag_benchmark_results.v8_INVALID_rate_limited.json` and must
  never be cited. **v7's 90% remains the current figure until a clean v8 is run.** The only
  salvageable signal from the void run is queries #1-10: **9/10 vs v7's 8/10, with #6 recovered** —
  independently confirmed live, the new `NIST CSF 2.0 (CSWP 29).pdf` answers the Tier question with
  correct citations. Archives in `rag_benchmark_results.v*.json`; query list lives inside
  `backend/tests/rag_benchmark.py`. **v1–v6 are Gemini-era; only v7 reflects the current stack.**
- **v7's headline (90% vs 92%) is one query and understates the change — read
  `RAG_Benchmark_Report_v7.md` before drawing conclusions.** #36 and #45 **recovered** (#36 was a
  confirmed Gemini *hallucination* — a real quality win the number hides). #4/#12/#18 newly fail.
- **#4, #6, #12 and #18 are ONE root cause, not four — verified by dumping the retrieved chunks
  (2026-08-17).** 1000-char chunking shatters multi-page enumerations (AI RMF Table 1, the OWASP Top
  10, ISO 27001's mandatory-documentation list), so "list/explain the whole framework" queries
  retrieve scattered fragments and the model **correctly refuses**. Bigger `k` or a better re-ranker
  cannot fix it — the complete answer exists in no retrievable unit. **Gemini masked this by
  confabulating partial answers that scored ANSWERED; gpt-oss-120b surfaces it by refusing, so part
  of the "drop" is the new model being more honest.** Do **not** re-diagnose #18 as a retrieval
  failure: its retrieval is the *strongest* measured (all 10 chunks from the right file, top rerank
  scores 8.56 vs 5.58 for a working control) — an early call of "retrieval regression" was
  investigated and disproved, see that report's Correction section. **Established fix: Golden
  Mapping entries** (the same mechanism that closed the EU AI Act cluster).
- **No minimum-content/quality filter runs before re-ranking.** In #18, ~30% of the 10-chunk context
  budget went to a **mojibake sponsors page** (glyph-corrupted, same extraction-defect class as
  `EU AI ACT 2024_Doc.pdf`) plus two sub-150-char stubs. A length threshold + non-ASCII-ratio guard
  would reclaim those slots for every query.
- **v7 latency (16.86s avg vs v6's 6.6s) is NOT established as a model property — do not quote it as
  one.** Isolated calls to this model ran 1.0-1.3s, and in the benchmark queries #1-3 took 3-5s
  before jumping to a 13-28s band — the shape of free-tier rate limiting, not per-token cost.
  `active-auditor` (4 chained queries) measured 31s right after the swap, consistent with the fast
  end. Needs a paced re-run to settle.
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
- Smoke test: **44** checks (grew from 27 pre-TPRM; 43 → 44 on 2026-08-17 with a real *substance*
  assertion on `/chat` — see gotchas), includes live DB-trigger immutability probes via
  `docker exec`. Pytest: **38** checks — grew 32 → 33 with
  `test_tprm_stage_restatus_preserves_existing_notes` (evidence-notes wipe regression), then 33 → 38
  with the new `tests/test_executive.py` (5 tests pinning `/executive/dashboard` to real computed
  values instead of fixture fabrications). Both 2026-08-17. Run from `backend/`, not the repo root.
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
