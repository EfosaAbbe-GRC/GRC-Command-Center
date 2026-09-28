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
| `pytest` (from `backend/`) | **65/65** | 2026-09-27 |
| RAG accuracy | **92.0% (46/50), v8** — legacy and graded both | 2026-09-27 |
| Index | curated: **148 files / 17,123 chunks** | re-ingested 2026-09-21 |

**How to quote the RAG figure:** *"42% → 92%"*. 92% means **answered without refusing**, not
graded-correct — see `docs/reports/RAG_Benchmark_Report_v8.md`. Spot-checking the flipped queries
found **#12 is a wrong answer scored as a pass** and **#36 a correct refusal scored as a failure**;
and #4's pass did not reproduce across three runs. The other 43 answers have not been graded for
correctness. **v7's 90% was never valid** (3 engine errors scored as answers — corrected
2026-09-27); v8 is the first valid Groq-era figure. Never quote 90%.

**⚠ Do not read the repo's `faiss_index/` folder to learn the index state.** It is an April 11
decoy. The live index is in the `grc-faiss` Docker volume.

---

## ▶ 0. FIRST: run the v9 benchmark — measures Golden Mapping (EXECUTED 2026-09-27)

The four entries are **live** (`Golden_Mapping_Enumerations_refactor.md`, status block has the
verification). **One variable changed since v8:** those four `golden_mappings.json` entries. Run v9
on a fresh Groq day using §"Running a benchmark" below (**Mufasa's AI analysis paused** — it shares
this Groq org; detached; ~21 min). **Deferred 2026-09-28** — Efosa needed Mufasa running that day,
and only ~176k of 200k tokens remained (Mufasa had spent 23,249), too tight for a 154–200k run.
The CPU is clear: the transcription job finished 2026-09-28 03:44.
Archive as `rag_benchmark_results.v9_golden_enumerations.json`. **Success:** #4, #12, #18, #26
graded `COMPLETE`, every other query's grade unchanged (report any change as noise, not a gain).
Label the four **mapping-attributed** in the report. Then take the two open decisions to Efosa:
(2) fix the v6 entries' exact-wording triggers — they also misfire on #17 and #21; (3) re-extract
the damaged GDPR PDF.

### Background (written before EXECUTE)

Queue item 1 below, promoted: the scorer and the v7 correction are both done, and the new grader's
completeness checks are exactly what shows whether Golden Mapping works (today: #4 4/6, #12
0/11, #18 and #26 refused). Draft-first. One variable per run; the next benchmark costs a day's Groq budget.

**DRAFTED 2026-09-27 — `docs/refactors/Golden_Mapping_Enumerations_refactor.md`, awaiting EXECUTE.**
Data-only (**4** JSON entries: #4, #12, #18, #26), triggers tested at zero tokens in-container: all
four match their query and rewordings with **zero false matches** against the other queries.
~~#12 excluded — no official ISO source in the corpus.~~ *Corrected same day at Efosa's prompt:*
`GRC_Analyst/ISO 27001-2022 BookLet.pdf` **is** the official ISO/IEC 27001:2022 (verified by
content) — the first check only searched filenames. The ISO entry paraphrases clause references
rather than quoting (copyrighted standard, public repo). Two decisions left in the draft. New finding inside
it: the official **GDPR PDF's text layer is damaged** (~1 in 10 words split: "pur pose limitation"),
a likely contributing cause of #26 and of weak GDPR retrieval generally.

### Done 2026-09-27 — scorer fix and v7 correction

**The scorer fix is DONE** (2026-09-27, `047cbc0`, `Benchmark_Grading_refactor.md` Parts A–D):
`backend/tests/rag_grading.py` grades 7 outcomes (closed-list completeness for 8 queries, expected
refusals for #36/#50, engine errors re-detected from text); `rag_benchmark.py` now records `grade`
per query and `graded_*` summary fields next to the unchanged legacy `accuracy_percentage`;
`scripts/rescore_benchmarks.py` re-grades every archive (zero tokens, archives untouched). pytest
**65/65**. **v8 is 92% graded as well (46/50; checkable 6/10).**

**Part E — DONE, approved by Efosa 2026-09-27.** Re-grading found **v7 stored three engine-error
messages as ANSWERED** (#35, #39, #45 = "I encountered an error processing your request.") — the
three "zero-source answers" the v7 report had read as possible hallucinations. v7 was 42/50 with 3
engine errors: **invalid**. Corrected with strikethrough + dated callouts in
`RAG_Benchmark_Report_v7.md`, `RAG_Benchmark_Report_v8.md` ("+2 vs v7", "zero-source resolved"),
`MEMORY.md` and `CLAUDE.md`. Historical `SESSION.md`/`task.md` entries were left as written — they
are the record of what was believed at the time. v8's 92% and the README are unaffected.

---

## The rest of the queue — independent of each other, except where noted

**0a. PII redaction — DRAFT awaiting EXECUTE, deploy AFTER v9** (added 2026-09-28).
`docs/refactors/PII_Redaction_refactor.md`: redact personal data locally (Microsoft Presidio)
before a question is sent to Groq or written to the immutable `audit_logs`. Efosa decided the
approach 2026-09-28; it's the treatment for impacts I6/I7 in his ISO 42001 impact assessment.
Two open choices in the draft: spaCy model size (recommend `lg`), and a pre-flight check that the
model downloads past this PC's firewall. Groq's Services Agreement §4.2 (last modified
2026-06-22) prohibits training on inputs/outputs; Efosa doesn't rely on it alone. Also for Efosa:
check that **Zero Data Retention** is enabled in the Groq console (otherwise requests are kept up
to 30 days).

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
   nothing else Groq-backed will run. **Confirmed 2026-09-28: `mufasa_backend` is in the SAME Groq
   organization** — a different key (SHA-256 fingerprint), but one ~90-token probe per key showed a
   shared counter (`x-ratelimit-remaining-requests` 999 → 998, reset timer 1m26s → 2m52s). So
   **every benchmark needs Mufasa's AI analysis paused**, which is Efosa's call. Mufasa reports its own
   daily Groq spend at `GET localhost:8000/api/admin/costs` inside `mufasa_backend`; subtract it from
   200k for a rough "left today" (the only estimate available, as Groq has no TPD header). No other
   container has a Groq variable (re-checked 2026-09-28, 18 containers).
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
cd backend; python -m pytest -q; cd ..                   # expect 65/65 -- MUST run from backend/
python scripts/rescore_benchmarks.py                     # re-grade all archives, zero tokens
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
