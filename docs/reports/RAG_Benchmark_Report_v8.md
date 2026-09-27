# RAG Benchmark v8 — First measurement of the curated corpus

**Run date:** 2026-09-27 · **Result: 92.0% (46/50)** · avg latency **3.76s** · 0 system errors
**Archive:** `rag_benchmark_results.v8_curated_corpus.json`
**What changed since v7 — two things, deliberately bundled:** the 2026-09-21 corpus refresh
(re-ingest, 153 files/17,498 chunks → 148/17,123) **and** the 2026-08-18 curation it carried
(duplicate and secondary-document removals). Model, chunking, embeddings, re-ranker, `k`, golden
mappings and prompt are unchanged since v7. **This is one unattributable reading of both changes
together** — accepted to avoid spending a second day's token budget on a corpus state already
abandoned. Do not credit the +2 points to either change alone.

## Why this run took three attempts

| Attempt | Date | Outcome | Cause | Fix |
| --- | --- | --- | --- | --- |
| 1 | 2026-09-25 | killed at 33/50, **nothing saved** | process killed externally; results written only after the loop | save after every query (`Benchmark_Durability_refactor.md`) |
| 2 | 2026-09-26 | aborted at 39/50 on HTTP 401 | single login, 15-min JWT, ~32-min paced run | refresh every 10 min + retry once on 401 (`Benchmark_TokenRefresh_refactor.md`) |
| **3** | **2026-09-27** | **complete, 50/50, valid** | — | both fixes held: two mid-run re-logins, zero 401s, zero 429s |

Both failures traced to the 2026-09-21 pacing change (run time ~3 min → ~32 min) silently breaking
two time-bound assumptions. Pre-flight for this run: RPD 999/1000, readiness 4/4, launched detached
at 11:20:19, finished 11:41:40 (~21 min — faster than the ~32 planned because real latency is far
below v7's).

## Trajectory

| Version | Change | Accuracy | Avg latency |
| --- | --- | --- | --- |
| v1 | Baseline (SQLite era) | 42% | — |
| v2 | k=5→10, 1000-char chunks | 70% | — |
| v3 | Corpus repair | 76% | — |
| v4 | Corpus expanded (158 docs) | 80% | — |
| v5 | Cross-encoder re-ranker | 84% | — |
| v6 | Golden Mapping (Gemini 2.5 Flash) | 92% | 6.6s |
| v7 | Model → `openai/gpt-oss-120b` | 90% | 16.86s |
| **v8** | **Corpus refresh + curation (bundled)** | **92%** | **3.76s** |

All figures post-scorer-correction. v6's 92% and v8's 92% are different models on different
corpora — equal numbers, not the same measurement.

## Headline: +2 points, but the number overstates the change in one place and understates it in another

**90% → 92% is two queries**, and the composition matters more than the net:

| | Query | v7 | v8 | Reading |
| --- | --- | --- | --- | --- |
| **Gained** | #6 CSF 2.0 Tier 1–4 | ❌ | ✅ | **Real.** Stable across all three v8 attempts. The actual standard was never retrieved under v7 (`Curation_Regression_Diagnosis_2026-09-26.md`). Answer is correct. |
| | #12 ISO 27001 mandatory documentation | ❌ | ✅ | **Scored a pass; the answer is wrong.** See below. |
| | #4 GOVERN core outcomes (AI RMF) | ❌ | ✅ | **Run-to-run variance, and incomplete.** See below. |
| **Lost** | #26 GDPR seven principles | ✅ | ❌ | Enumeration weakness exposed by curation, not damage — the diagnosis stands. Golden Mapping target. |
| | #36 CSF ↔ ISO 27001 gap assessment | ✅ | ❌ | **A correct refusal scored as a failure.** No crosswalk exists in the corpus. |
| **Still failing** | #18 OWASP Top 10 for LLMs | ❌ | ❌ | 1 source retrieved; known enumeration/chunking root cause (v7 §Correction). |
| | #50 CISA AI Audit Booklet | ❌ | ❌ | Source absent from the corpus — refusal is correct. |

### #12 — a false pass the binary scorer cannot see

The answer states that ISO 27001 requires exactly one mandatory document ("Information security
guideline", §5.2(e)) and that "no other documents are identified in the context as mandatory." That
is **substantively wrong**: ISO/IEC 27001:2022 requires documented information for, at minimum,
the ISMS scope (4.3), the information security policy (5.2), the risk assessment and treatment
processes and results (6.1.2, 6.1.3, 8.2, 8.3), the Statement of Applicability (6.1.3 d), the
security objectives (6.2), evidence of competence (7.2), monitoring and measurement results (9.1),
the internal audit programme and results (9.2), management review results (9.3) and nonconformities
and corrective actions (10.2). It is faithful to its retrieved context — the context just didn't
contain the list — but it presents a one-item answer as complete instead of refusing or flagging
partial coverage. The scorer only asks "did it refuse?", so it passes.

### #4 — variance, and a partial list presented as whole

Query #4 refused in **both** partial runs (2026-09-25, 2026-09-26) on the identical index and code, then
answered here. Same inputs, different outcome: this flip is sampling variance, not an improvement.
The answer itself lists GOVERN 1, 2, 4 and 5 and omits **GOVERN 3** (workforce diversity, equity,
inclusion) and **GOVERN 6** (third-party/supply-chain AI risk) — the multi-page-enumeration
chunking problem again, without saying the list is partial.

### Honest reading of the 92%

- **Strictly correct answers ≈ 45**, not 46: #12 is a wrong answer counted as a pass.
- **At least two of the four refusals are correct behaviour** (#36 no crosswalk, #50 no source).
- **#4's pass is not reproducible** on the evidence of three runs.
- Only the seven queries above were content-checked. **The other 43 ANSWERED results were not
  graded for correctness** — the calibrated judge (`validate_diagnostic.py`) is still pinned to the
  dead Gemini key. So "92%" means *answered without refusing*, not *answered correctly* — as it has
  for every version in the trajectory.

## Zero-source answers: resolved

v7 had three ANSWERED results with `sources_count: 0` (#35, #39, #45) — the signature of
unguarded generation. **v8 has none.** Every answer cites retrieved context.

## Latency: 16.86s → 3.76s

Confirms what the partials suggested: v7's latency was rate-limit throttling (unpaced queries
hitting the 8,000 TPM ceiling and waiting out retries), not a property of the model. Paced at 22s,
real per-query latency is 2.24–9.08s, median 3.56s.

## What this changes in the queue

1. **The binary scorer is now the most important methodology fix.** It has distorted the reading in
   both directions in a single run: a correct refusal (#36) scored as a loss, a wrong answer (#12)
   scored as a pass. Minimum viable change still stands — score `INSUFFICIENT_DATA` as a distinct
   category — but #12 shows refusal-classification alone isn't enough; completeness on enumeration
   queries needs a check too. A scorer change applies retroactively to every archive.
2. **Golden Mapping targets: #4, #12, #18, #26.** #12 rejoins the list (answered, but wrong); #6
   stays off it (fixed by curation, correct, stable).
3. **#36 needs an authoritative CSF ↔ ISO 27001 crosswalk** (NIST Informative References) — a
   corpus gap, not a code fix.
4. **Run-to-run variance is now observed, not hypothetical.** Single-run deltas of ±1 query are
   noise. Any future claim of improvement from one run should be ≥2 queries and checked for
   stability.

## Quoting this figure

**"92% (46/50) on the current curated corpus, v8, 2026-09-27"** — with "answered without refusing"
as the definition if asked. Paired with the corrected baseline: **42% → 92%**. The 90% (v7) figure
is now historical — it measured a corpus that no longer exists.
