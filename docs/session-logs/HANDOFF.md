# GRC Command Center — Session Handoff (v1.5.0)

**Date:** 2026-09-25. **Rewritten clean** — the previous version was an August base carrying two
layered correction blocks (2026-09-18 and 2026-09-21) and a stale "everything is pushed (`0e60631`)"
line. Its own header told the next person to rewrite rather than layer again; this is that rewrite.
**If this file starts accumulating update blocks again, rewrite it — do not append another.**

This is the **briefing**: current state and what to do first. The ledger with full history is
`task.md`; the narrative is `SESSION.md`.

---

## Where things stand

**Version 1.5.0.** TPRM complete (all tiers). RAG P3 Execution Monitor, Agent Registry de-stubbing,
the Interview Simulator Tier 1, and all honesty fixes are built and browser-verified. LLM is Groq
`openai/gpt-oss-120b`.

**Baselines — all re-verified 2026-09-25:**

| | Status |
|---|---|
| `smoke_test.py` (test stack, `:8002`) | **44/44** |
| `pytest` (from `backend/`) | **50/50** |
| RAG accuracy | **90.0% (v7)** — see the qualifier below |
| Index | curated: **148 files / 17,123 chunks** (re-ingested 2026-09-21) |

**⚠ The 90.0% figure measures an index that no longer exists.** It is not wrong; it measures the
pre-curation corpus. Attach that qualifier anywhere it is quoted — it appears on Efosa's resume and
in the Workstreet interview prep. It stops needing the qualifier the moment a clean v8 runs.

**⚠ Do not read the repo's `faiss_index/` folder to learn the index state.** It is an April 11
decoy. The live index is in the `grc-faiss` Docker volume.

---

## ▶ 0. FIRST: run the clean v8 benchmark — detached

*Efosa's stated first priority since 2026-09-21. Attempted 2026-09-25 and lost; see below.*

Everything is staged. Nothing to build or approve. **This is purely the run**, ~32 minutes.

### What happened on the last attempt — read this, it changes how you launch it

The run completed **33 of 50 queries, all HTTP 200, zero 429s, zero engine failures** — then was
**killed externally** at 14m26s. Because the script saved only after the loop, it wrote **nothing**:
~100–130k tokens, half to two-thirds of the org-wide daily budget, for no file.

**That hole is now fixed** (`Benchmark_Durability_refactor.md`): results are written after every
query, so an interruption costs one query instead of the day. But **launch it detached anyway** —
the last run died because it was a child of a tool session:

```powershell
$env:PYTHONUTF8 = "1"
Start-Process -FilePath python `
  -ArgumentList "-u", "backend/tests/rag_benchmark.py" `
  -WorkingDirectory "C:\Users\efosb\OneDrive\Desktop\GRC Inspector\GRC_Command_Center" `
  -RedirectStandardOutput "bench_run.log" -RedirectStandardError "bench_run.err" -NoNewWindow
```

Watch with `Get-Content bench_run.log -Wait`, or just read `rag_benchmark_results.json` — it is now
current to the last completed query.

### On the day, in order

1. **Confirm no other project on the Groq account needs tokens.** A hard gate, not a courtesy.
   Derived from the v7 archive: ~3,073 tokens typical / ~4,010 worst case per query, so a 50-query
   run costs **~154,000–200,500 tokens — 77% to 100% of the entire 200,000/day organization-wide
   budget.** There is no TPD header to check the balance with.
   **Note (2026-09-25, unverified):** several other stacks run on this machine (`mufasa_*`,
   `gravity_backend`, `optionterminal-governor`, `uts-*`). Whether any call Groq has never been
   checked. Worth establishing once — it affects every future benchmark day.
2. **Pre-flight:** `x-ratelimit-remaining-requests` should read at or near 1,000.
3. **Launch detached**, as above. Confirm the banner prints the pacing (22.0s default).
4. **Nothing else Groq-backed for the duration** — no interactive `/chat`, no agent runs, no
   Interview Simulator grading, no LLM-touching smoke tests.
5. **Archive** as `rag_benchmark_results.v8_curated_corpus.json` and write the report. **Label it
   explicitly:** it measures the corpus refresh *and* the 2026-08-18 curation together — a
   deliberate bundling, accepted to avoid spending a second day's budget on a corpus state already
   abandoned. One unattributable reading, recorded as such.
6. **If it aborts,** the failure shape names the limit: intermittent-with-recovery = TPM (raise
   `GRC_BENCH_PACING`, retry same day); sustained-with-no-recovery = TPD (needs a fresh day).

### What the recovered partial already tells us

The lost run was reconstructed from `audit_logs` and archived as
`rag_benchmark_results.v8_PARTIAL_recovered_2026-09-25.json` (`valid: false`,
`accuracy_percentage: null`). **It is not a v8 and must not be cited.** The one sound reading is
the same-subset comparison against v7 on the identical 32 query ids:

| | v7 | Recovered |
|---|---|---|
| Same 32 queries | 28/32 (87.5%) | **29/32 (90.6%)** |

Two outcome flips up, one down — see item 1 below. Also: real query latency was **~3.5 s** against
v7's 16.86 s, which answers the long-standing "was v7 throttled?" question. It was.

---

## The rest of the queue — independent of each other, except where noted

**1. Golden Mapping for the enumeration queries — RE-SCOPE BEFORE BUILDING.** This has been carried
as "the highest-value lever," targeting **#4, #6, #12, #18**. The recovered partial shows that
**#6 and #12 now answer correctly from the corpus curation alone**, with no query-time work at all.
**It may be a two-query problem (#4, #18) rather than four.** Confirm against a real v8 — don't build
against the partial. Root cause for the remainder is unchanged: 1000-char chunking shatters
multi-page enumerations. **Do not re-diagnose #18 as a retrieval bug** — investigated and disproved,
see `RAG_Benchmark_Report_v7.md` §Correction.

**2. Investigate #26's regression.** *"List the seven core principles of GDPR"* went
ANSWERED → INSUFFICIENT_DATA. One of the five documents removed on 2026-09-21 was evidently
carrying it — the first evidence the curation was not purely additive. Confirm it persists in v8
before digging.

**3. Decide A/B/C on audit-write failure.** The NUL-byte bug is fixed, but `except Exception` still
swallows *unknown* audit failures — and it swallowed a bug introduced during that very fix, which
is the argument for changing it. Options in `AuditLog_NulByte_refactor.md`; **B recommended**
(return `audit_logged: false`), matching the `grading_failed` / ComplianceTerminal honesty pattern.
Needs its own draft — it is a response-schema change.

**4. Minimum-content/quality filter before re-ranking.** ~30% of #18's context budget went to a
mojibake sponsors page and two sub-150-char stubs. A length threshold plus a non-ASCII-ratio guard
fixes this class across all documents, including future additions.

**5. Corpus authority review — user-led, human judgement.** Efosa's own proposal, still open. A
crude name heuristic flagged 33 of 158 PDFs as personal/secondary; **that count predates the
refresh to 148 files — re-run the heuristic before trusting it.** Evidence it costs accuracy: on
query #12, `Notes from Study +.pdf` supplied 4 of 10 chunks and out-retrieved the actual standard.
Removing documents needs a re-ingest (**~36.5 min**, not the ~11 min some older notes claim) and
will move the benchmark — one deliberate change, one variable per run, archive first.

**6. Frontend component test harness** (Vitest + RTL). Still unbuilt; zero frontend component tests
exist project-wide, and five frontend fixes now rest purely on manual browser verification. Touches
`package.json`; needs its own draft.

**7. Interview Simulator Tier 2** — only on a specific pull toward it, not the default next move.
See `Interview_Simulator_Roadmap.md`.

**Lower priority, unchanged:** migrate `diagnose_rag.py` / `validate_diagnostic.py` off the dead
Gemini key (has blocked analysis twice); the binary benchmark scorer still cannot distinguish a
correct refusal from a failure, which rewards the less honest model — a real methodology gap, not
urgent. Also unaddressed: `ChatGroq(max_retries=2)` means a throttled query can fire three calls;
the 2026-09-25 run spent ~43 Groq calls for 33 queries.

**Standing recommendation, not a queued item:** this is explicitly a *progressive* project.
Production is the eventual goal, not soon. The known gaps versus real GRC tools (no live
infrastructure integration, no multi-tenancy/SSO, single-process, no frontend tests) are already
priced in — don't re-raise them as new findings. The "genuine hands-on personal-use pass" ask is
satisfied for TPRM; the Interview Simulator has not had an equivalent extended-use pass.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
docker compose -f docker-compose.test.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 44/44 (hits :8002)
cd backend; python -m pytest -q; cd ..                   # expect 50/50 -- MUST run from backend/
Invoke-RestMethod http://localhost:8001/api/v1/readiness # dev stack health, read-only, safe anytime
```

**Notes:**

- Backend source is **not** bind-mounted. Any change to `backend/` needs
  `docker compose -f docker-compose-v2.yml up -d --build backend` to take effect (~20 s warm,
  ~15 min if the pip layer cache has been evicted). The test stack needs the same treatment via
  `docker-compose.test.yml`, or smoke tests green against code you did not change.
- `grc-frontend` shows healthcheck "unhealthy" continuously — harmless, an IPv6/IPv4 loopback
  mismatch in the check itself. The app serves fine on `http://localhost:3006`.
- `smoke_test.py` / `pytest` target `:8002` by default. For the dev stack set
  `GRC_TEST_BASE=http://localhost:8001` first.
- `smoke_test.py` calls `/chat` three times — it costs roughly 9k Groq tokens. Don't run it on a
  benchmark day.
- This repo is the one deliberate exception to the workspace's "local-only" rule: it has a public
  remote (`EfosaAbbe-GRC/GRC-Command-Center`) and commits go straight to `main`.
