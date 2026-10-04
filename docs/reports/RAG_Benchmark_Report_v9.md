# RAG Benchmark v9 — Golden Mapping for the enumeration queries

**Run date:** 2026-10-04 · **Legacy: 94.0% (47/50) · Graded: 98.0% (49/50, checkable 9/10)** ·
avg latency **3.81s** · 0 system errors
**Archive:** `rag_benchmark_results.v9_golden_enumerations.json`
**What changed since v8 — one thing:** the four `golden_mappings.json` entries for
queries #4, #12, #18 and #26 (`2656906`, `Golden_Mapping_Enumerations_refactor.md`). Verified, not assumed: the dev
`grc-backend` image was built 2026-09-27 20:07, after `2656906` and before the PII redaction
commit `1c18214` (Presidio is not installed in it); the container's `golden_mappings.json` is
byte-identical to the repo's (SHA-256 `cb68d8cc…`); the only non-test `backend/` commit between v8
and the build is `2656906`. Model, corpus (148 files / 17,123 chunks), chunking, embeddings,
re-ranker, `k` and prompt are unchanged.

**Do not quote 94% or 98% as accuracy.** The figure to cite stays *"42% → 92%"* (v8). See
§"What the number means".

## The run

Pre-flight: Mufasa's Groq spend for the day **$0.00** (before and after the run, via
`/api/admin/costs`), RPD probe **999/1000**, readiness 4/4. Launched detached 11:02:50, finished
~11:24 (~21 min). Two mid-run re-logins, **zero 401s, zero 429s, zero engine errors**. Query #1 took
33.5s (v8: 9.1s): a cold start after the backend sat idle, not a regression; without it the average
is ~3.2s.

## Result against the success criterion

Criterion set in `HANDOFF.md` before the run: *#4, #12, #18, #26 graded `COMPLETE`, every other
query's grade unchanged.*

| Query | v8 grade | v9 grade | Answer text, read in full | Attribution |
| --- | --- | --- | --- | --- |
| #4 AI RMF GOVERN outcomes | INCOMPLETE 4/6 | **COMPLETE 6/6** | **Correct.** All six GOVERN categories with accurate summaries. | mapping-attributed |
| #12 ISO 27001 mandatory documentation | INCOMPLETE 0/11 | **COMPLETE** (9/11 reported, really 11/11 — see below) | **Complete, plus one invented item.** All 14 clause requirements in the mapping appear, plus item 3: *"Information security guideline — referenced in clause 5.2 e"*. Checked against the official text in the corpus (`ISO 27001-2022 BookLet.pdf`): 5.2 e) only requires the **policy** to be available as documented information; the standard contains no "guideline" requirement. The item is not in the mapping text either — the model added it. | mapping-attributed, **with a fabricated item** |
| #18 OWASP Top 10 for LLMs | WRONG_REFUSAL | **WRONG_REFUSAL** (unchanged) | **List fixed, explanation not.** All ten 2025 category names are now correct. The query says *"Explain"*; the mapping holds names only, so the model described three risks (LLM04, LLM08, LLM10 — descriptions read as accurate, not yet traced to the retrieved chunks; `sources_count` 1) and wrote `INSUFFICIENT_DATA` against the other seven. The benchmark counts any `INSUFFICIENT_DATA` substring as a refusal — **deliberately** (the 2026-08-05 scorer fix). Had it been classed ANSWERED, the grader would give 6/6. The honest reading is the one the rule gives: incomplete. | criterion **not met** |
| #26 GDPR seven principles | WRONG_REFUSAL | **COMPLETE 7/7** | **Correct.** All seven Article 5 principles, accurate. | mapping-attributed |

**Every other query:** outcome and grade identical to v8 (all 46). For the 40 ungraded queries this
only means each was answered again; their answer text was not compared for correctness.

**Criterion: 3 of 4 met.** #18 needs a decision (below), not a re-run.

## What the number means

- **Legacy 94% (47/50)** = answered without refusing. +1 vs v8 is #26.
- **Graded 98% (49/50)** = legacy, plus #36 and #50 counted as correct refusals, minus nothing. It
  counts #12 as a pass despite its invented item, and 40 of 50 answers are not checked at all.
- **Quotable:** *"A targeted fix took three failing enumeration questions to complete answers with no
  regressions on the other 46."* Not quotable: 98% as an accuracy figure.
- **Single run.** v8 showed #4 flipping between runs; with the mapping its context is now fixed
  text, which should stabilise it, but v9 is one observation.

## Grader finding — hyphens (no grade affected)

`rag_grading._NORMALISE` already maps Unicode hyphens (U+2010/2011, en/em dash) to `-`, but the
item patterns use literal spaces (`internal audit`, `management review`), so any hyphenated form —
Unicode or ASCII — fails to match. `gpt-oss-120b` hyphenates compound nouns often (**469**
non-breaking hyphens across v9's 50 answers); v9 #12 wrote `internal‑audit` and
`management‑review`, which is why it reported items 9 and 10 missing when both are present.
Re-grading **every archive, v1–v9**, with hyphens normalised to spaces changes exactly one result:
v9 #12's detail, 9/11 → 11/11. **No pass/fail grade has ever been affected.** Fix: let a space in an
item pattern also match a hyphen (`Grader_Hyphen_refactor.md`; tests-only, zero tokens) —
**executed 2026-10-04**, regrade confirms the above.

## Open decisions (Efosa's)

1. **#18:** add short official descriptions to the OWASP mapping's canonical text (from the OWASP
   2025 PDF in the corpus), or narrow the expectation to the list. The query asks for explanation,
   so the first is the honest fix.
2. **#12's invented item:** a prompt-side problem (the model elaborating beyond mapped context), not
   a mapping defect. Options: tighten the golden-mapping instruction to "list only what the
   canonical context lists", or add a negative check for known fabrications to the grader. Either
   is its own variable and its own benchmark.
3. Carried over from the handoff: the v6 entries' exact-wording triggers (misfire on #17/#21), and
   re-extracting the damaged GDPR PDF.
