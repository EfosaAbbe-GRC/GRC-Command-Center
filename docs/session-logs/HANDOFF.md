# GRC Command Center — Session Handoff (v1.5.0)

**Date:** 2026-09-27. **Rewritten clean** after v8 completed — the previous version's §0 ("run the
clean v8") is done. **If this file starts accumulating update blocks again, rewrite it — do not
append another.**

This is the **briefing**: current state and what to do first. The ledger with full history is
`task.md`; the narrative is `SESSION.md`.

---

## Where things stand

**Version 1.5.0.** TPRM complete (all tiers). RAG P3 Execution Monitor, Agent Registry de-stubbing,
the Interview Simulator Tier 1, and all honesty fixes are built and browser-verified. LLM is Groq
`openai/gpt-oss-120b`.

**Baselines:**

| | Status | Last verified |
|---|---|---|
| `smoke_test.py` (test stack, `:8002`) | **44/44** | 2026-09-25 |
| `pytest` (from `backend/`) | **50/50** | 2026-09-25 |
| RAG accuracy | **92.0% (46/50), v8** | 2026-09-27 |
| Index | curated: **148 files / 17,123 chunks** | re-ingested 2026-09-21 |

**How to quote the RAG figure:** *"42% → 92%"*. 92% means **answered without refusing**, not
graded-correct — see `docs/reports/RAG_Benchmark_Report_v8.md`. Spot-checking the flipped queries
found **#12 is a wrong answer scored as a pass** and **#36 a correct refusal scored as a failure**;
and #4's pass did not reproduce across three runs. The other 43 answers have not been graded for
correctness. v7's 90% measured a corpus that no longer exists and is now historical.

**⚠ Do not read the repo's `faiss_index/` folder to learn the index state.** It is an April 11
decoy. The live index is in the `grc-faiss` Docker volume.

---

## ▶ 0. FIRST: fix the scorer — it now mis-reads results in both directions

*The benchmark is only as honest as its scorer, and v8 showed it failing both ways in one run.*

`rag_benchmark.py` scores **"did it refuse?"** and nothing else:

- **#36** — correctly refuses (no NIST CSF ↔ ISO 27001 crosswalk exists in the corpus) → scored ❌.
- **#12** — confidently states ISO 27001 has **one** mandatory document (it has ~12 clauses
  requiring documented information) → scored ✅.

Minimum viable change, draft-first per `GOVERNANCE.md`:

1. Score a well-formed `INSUFFICIENT_DATA` as a **distinct third category**, not a failure, and
   keep a per-query expected-behaviour field (`answer` vs `refuse`) so #36/#50 can be judged
   *correct refusals*.
2. For enumeration queries, a completeness check against a short expected-item list (#4 GOVERN 1–6,
   #12 the documented-information clauses, #26 GDPR's seven principles, #18 OWASP LLM01–10).
   Rule-based, not an LLM judge.

**Costs zero Groq tokens**: it re-scores the stored `answer` text, so it applies retroactively to
**every** archive v1–v8 without a new run. Report the re-scored trajectory alongside the old one;
never overwrite the old figures.

---

## The rest of the queue — independent of each other, except where noted

**1. Golden Mapping for the enumeration queries — #4, #12, #18, #26.** #12 **rejoins** (answered,
but wrong); #6 stays off (fixed by curation, correct, stable across all three v8 attempts). Root
cause: 1000-char chunking shatters multi-page enumerations. **Do not re-diagnose #18 as a retrieval
bug** — disproved, `RAG_Benchmark_Report_v7.md` §Correction. Easier to measure after §0 lands, since
the completeness check is what shows whether it worked.

**2. Acquire an authoritative NIST CSF ↔ ISO 27001 crosswalk** (NIST Informative References) for
query #36. Corpus gap, not a code fix. Until then, refusing is correct.

**3. Decide A/B/C on audit-write failure.** `except Exception` still swallows unknown audit
failures. Options in `AuditLog_NulByte_refactor.md`; **B recommended** (return
`audit_logged: false`). Response-schema change — needs its own draft.

**4. Minimum-content/quality filter before re-ranking.** ~30% of #18's context budget went to a
mojibake sponsors page and two sub-150-char stubs. Length threshold + non-ASCII-ratio guard.

**5. Corpus authority review — user-led, human judgement.** Supported by the 2026-09-26 diagnosis
(#6: secondary docs displaced the actual standard). Caveat: a removal can expose an enumeration
weakness it was masking (#26), so benchmark after each removal. Re-run the name heuristic first
(its 33-of-158 count predates the refresh). Re-ingest is ~36.5 min.

**6. Frontend component test harness** (Vitest + RTL). Zero frontend component tests exist.
Touches `package.json`; needs its own draft.

**7. Interview Simulator Tier 2** — only on a specific pull toward it.

**Lower priority:** migrate `diagnose_rag.py` / `validate_diagnostic.py` off the dead Gemini key —
the calibrated judge is the only way to grade the 43 unchecked answers, so this rises if §0's
rule-based check proves too coarse. `ChatGroq(max_retries=2)` can fire three calls per throttled
query.

**Standing recommendation, not a queued item:** this is a *progressive* project. The known gaps
versus real GRC tools (no live infrastructure integration, no multi-tenancy/SSO, single-process, no
frontend tests) are priced in — don't re-raise them as new findings.

---

## Running a benchmark (when one is next needed)

The procedure that worked on 2026-09-27, first try:

1. **Groq budget is organization-wide: 200,000 tokens/day; one run costs 77–100% of it.** Confirm
   nothing else Groq-backed will run. **Established 2026-09-27:** `mufasa_backend` holds a Groq key
   — a **different key** from this project's (compared by SHA-256 fingerprint), but whether it is
   the same Groq organization is **not known**. Ask Efosa before each run; he confirmed it idle on
   2026-09-27. No other container on the machine has a Groq variable.
2. **Pre-flight:** `x-ratelimit-remaining-requests` near 1,000 (a one-word probe from inside
   `grc-backend` costs ~80 tokens).
3. **Launch detached:**

   ```powershell
   $env:PYTHONUTF8 = "1"
   Start-Process -FilePath python `
     -ArgumentList "-u", "backend/tests/rag_benchmark.py" `
     -WorkingDirectory "C:\Users\efosb\OneDrive\Desktop\GRC Inspector\GRC_Command_Center" `
     -RedirectStandardOutput "bench_run.log" -RedirectStandardError "bench_run.err" -NoNewWindow
   ```

   ~21 minutes at 22 s pacing. Results save after every query; the JWT refreshes every 10 min.
4. **Nothing else Groq-backed, and nothing CPU-heavy, for the duration** — the re-ranker runs on
   the host CPU.
5. **Archive** `rag_benchmark_results.json` → `docs/reports/rag_benchmark_results.vN_<change>.json`
   and **spot-check every flipped query's answer text** before writing the report. That is what
   caught #12 and #4 on v8; the summary numbers alone would not have.

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
  `docker compose -f docker-compose-v2.yml up -d --build backend` (~20 s warm, ~15 min if the pip
  layer cache has been evicted). The test stack needs the same via `docker-compose.test.yml`.
- `grc-frontend` shows healthcheck "unhealthy" continuously — harmless, an IPv6/IPv4 loopback
  mismatch in the check itself. The app serves fine on `http://localhost:3006`.
- `smoke_test.py` / `pytest` target `:8002` by default. For the dev stack set
  `GRC_TEST_BASE=http://localhost:8001` first.
- `smoke_test.py` calls `/chat` three times (~9k Groq tokens). Don't run it on a benchmark day.
- This repo is the one deliberate exception to the workspace's "local-only" rule: public remote
  `EfosaAbbe-GRC/GRC-Command-Center`, commits go straight to `main`.
