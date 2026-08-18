# GRC Command Center — Session Handoff (v1.5.0)

**Date:** 2026-08-18. Rewritten clean — the previous version had accumulated three layered
"update blocks" on top of stale content, which was itself becoming hard to trust. If this file
ever does that again, rewrite it clean rather than layering another correction on top.

## Continue from this point in a new chat

**Version:** 1.5.0 — TPRM Interview Simulator Tier 1 shipped, verified, and pushed (see
`SESSION.md`'s 2026-08-18 entry and `Interview_Simulator_Roadmap.md` for full detail). Everything
else unchanged since the last handoff: TPRM (all tiers) complete, RAG P3 Execution Monitor +
Agent Registry de-stubbing + all honesty fixes (ComplianceTerminal/Framework_Mappings/
ExecutiveTerminal) built and browser-verified, LLM on Groq (`openai/gpt-oss-120b`), corpus refreshed
to 153 valid PDFs.

**Baselines:** smoke **44/44** · pytest **50/50** (both against the isolated test stack,
`docker-compose.test.yml`, port 8002). RAG accuracy: **90.0% (v7)** — this is the current, citable
figure. **Everything is pushed** (`0e60631`).

**RAG accuracy status, carried forward unresolved:** v7 (90.0%) was measured *before* the
2026-08-17 corpus refresh (158→153 files, image-only junk removed, 12 official documents added).
A post-refresh "v8" run was attempted but is **invalid** — it hit Groq's 200k-token/day cap at
query #11, and the pre-fix scorer counted the resulting rate-limit errors as correct answers,
reporting a false 96%. The scorer bug is now fixed (`Benchmark_Scorer_Honesty_refactor.md`) and
the bad archive is quarantined as `rag_benchmark_results.v8_INVALID_rate_limited.json` — never
cite it. **A clean v8 has still not been run.** This is the single most useful next action and
should happen first, before anything else that draws on the same Groq token budget (a 50-query run
consumes most of the daily 200k allowance — run it before interactive chat, agent runs, or
Interview Simulator grading sessions, or it will fail partway again).

## ▶ NEXT SESSION — start here

**These are independent, not sequential, except where a benchmark run is involved** (Golden
Mapping and the content filter are query-time changes needing no re-index; the corpus review needs
a re-ingest; the Interview Simulator Tier 2 items touch neither). What needs sequencing is
*measurement*: run the benchmark between changes so each lever's effect stays attributable, per the
standing one-variable-per-run convention, or bundle deliberately and accept one unattributable
reading.

1. **🔴 Run a clean v8 RAG benchmark first** (`$env:PYTHONUTF8=1; python
   backend/tests/rag_benchmark.py`) — budget the day around it per the token-cap gotcha above. This
   both confirms the corpus refresh's real effect and unblocks trusting any number quoted after it.
2. **Golden Mapping entries for the enumeration queries (#4, #6, #12, #18).** Highest-value lever on
   RAG accuracy — one root cause: 1000-char chunking shatters multi-page enumerations (AI RMF Table
   1, OWASP Top 10, ISO 27001's mandatory-documentation list), so "list/explain the whole
   framework" queries retrieve fragments and the model correctly refuses. Golden Mapping is the
   established fix (it already closed the EU AI Act cluster). **Do not re-diagnose #18 as a
   retrieval bug** — investigated and disproved, see `RAG_Benchmark_Report_v7.md` §Correction.
3. **Minimum-content/quality filter before re-ranking.** ~30% of #18's context budget went to a
   mojibake sponsors page and two sub-150-char stubs. A length threshold + non-ASCII-ratio guard
   fixes this class across all documents automatically, including future additions.
4. **Corpus authority review — user-led, human judgement required** (the user's own proposal,
   2026-08-17, still open). A crude name heuristic flags **33 of 158 PDFs** as personal/secondary
   material (note: this count predates the 2026-08-17 refresh to 153 files — re-run the heuristic
   before trusting the 33 figure). `MEMORY.md` already carries an "official sources only" rule that
   predates much of it. Evidence it costs accuracy: on query #12, `Notes from Study +.pdf` supplied
   4 of 10 chunks and out-retrieved the actual standard. Removing documents requires a re-ingest
   (~11 min) and will move the benchmark — treat as one deliberate change, one variable per run,
   archive first.
5. **Frontend component test harness** (Vitest + RTL) — still unbuilt. The gap it's protecting
   against has grown since it was first flagged: zero frontend component tests exist project-wide,
   and four separate frontend fixes now rely purely on manual browser verification (stage-notes
   preservation, Ops empty-state, ExecutiveTerminal honesty, and now the new Interview Simulator
   terminal). Touches `package.json`; needs its own draft.
6. **TPRM Interview Simulator, Tier 2** (only if there's a specific pull toward it — not the
   default next move over items 1-5). Per `Interview_Simulator_Roadmap.md`: a Framework Mapper hook
   (surface which real STAR story/platform feature answers a given JD requirement or interview
   question — reuses this Tier 1 build's session/turn data model), additional scenario sources
   beyond TPRM stages (general SOC 2/ISO questions grounded via `rag_engine.query()` directly), and
   session analytics once there's enough history to make it meaningful.

**Lower priority, still open, unchanged from before:** establish whether v7's latency was free-tier
rate limiting (not yet proven a model property); migrate `diagnose_rag.py`/`validate_diagnostic.py`
off the dead Gemini key (has blocked analysis twice, still non-functional); the binary benchmark
scorer cannot distinguish a correct refusal from a failure and currently rewards the less honest
model — a real scoring-methodology gap, not urgent.

**Standing recommendation, not a queued item:** this is explicitly a *progressive* project — the
goal is eventually shipping to production, but not soon. The user already knows the gaps a real
GRC-tool comparison surfaces (no live infrastructure integration, no multi-tenancy/SSO,
single-process architecture, no frontend tests) — don't re-raise those as new findings. The
standing "genuine hands-on personal-use pass" ask is **satisfied** for TPRM (dogfooded twice, both
bugs found fixed) — the Interview Simulator has not yet had an equivalent extended-use pass beyond
the one verification session that shipped it; worth doing once it's had more real use.

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
docker compose -f docker-compose.test.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 44/44 (hits :8002 by default)
cd backend; python -m pytest -v; cd ..                   # expect 50/50 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # run this FIRST -- see token-budget note above
Invoke-RestMethod http://localhost:8001/api/v1/readiness  # dev stack health, read-only, safe anytime
```

**Notes:**
- `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an IPv6/IPv4 loopback
  mismatch in the healthcheck itself, not a real outage; see `MEMORY.md` gotchas). The app serves
  fine on `http://localhost:3006`.
- `smoke_test.py`/`pytest` target the isolated test stack (`:8002`) by default now, not the dev
  stack. To check the dev/dogfooding stack specifically, set
  `GRC_TEST_BASE=http://localhost:8001` first — see `MEMORY.md`'s "Boot & verify" section.
- This project follows a workspace-wide doc-chain standard as of 2026-08-18 (see the parent
  `GRC Inspector/CLAUDE.md`) — this repo is the one deliberate exception to "local-only": it has a
  public GitHub remote (`EfosaAbbe-GRC/GRC-Command-Center`) and commits go straight to `main`.
