# RAG Benchmark v10 — Official descriptions in the OWASP mapping

**Run date:** 2026-10-17 · **Legacy: 96.0% (48/50) · Graded: 98.0% (49/50, checkable 9/10)** ·
avg latency **3.70s** · 0 system errors

**Archive:** `rag_benchmark_results.v10_owasp_descriptions.json`
**What changed since v9 — one thing:** the OWASP Top 10 for LLMs entry in `golden_mappings.json`
now carries a short official description of each of the ten 2025 risks
(`Golden_Mapping_OWASP_Descriptions_refactor.md`, `c4b03a5`). Verified, not assumed: no `backend/`
commit since `c4b03a5`; the container's `/app/data/golden_mappings.json` is byte-identical to the
repo's (SHA-256 `dbc03e1d…`). The dev image also contains PII redaction (live since 2026-10-04),
which the `test_pii` release gate proved changes none of the 50 questions, so it is not a second
variable. Model, corpus (148 files / 17,123 chunks), chunking, embeddings, re-ranker, `k` and
prompt are unchanged.

**Do not quote 96% or 98% as accuracy.** The figure to cite stays *"42% → 92%"* (v8). See
§"What the number means".

## The run

Pre-flight: readiness 4/4; RPD probe **999/1000** (one ~81-token call), so nothing else had used
the Groq organisation in the current window. Mufasa does not run its AI analysis at weekends (owner);
its log had no Groq activity in the previous 12 hours. Its `/api/admin/costs` returned 403 without
an admin login, so its dollar figure was **not** checked this time. Launched detached 23:33:05,
finished ~23:54 (~21 min). Two mid-run re-logins, **zero 401s, zero 429s, zero engine errors**.

## Result against the success criterion

Criterion set in `HANDOFF.md` before the run: *#18 `ANSWERED` and `COMPLETE`, no `INSUFFICIENT_DATA`
text, descriptions consistent with the mapping; every other grade unchanged.*

| Query | v9 | v10 | Answer text, read in full |
| --- | --- | --- | --- |
| #18 OWASP Top 10 for LLMs | INSUFFICIENT_DATA / WRONG_REFUSAL | **ANSWERED / COMPLETE 6/6** | **Correct.** All ten LLM01–LLM10:2025 names, each with a "core risk" description that paraphrases the mapping's text closely (checked line by line), plus a one-line plain explanation per risk and an auditor takeaway. No `INSUFFICIENT_DATA` anywhere. The plain-explanation column is the model's own elaboration; it reads accurately and adds no claim that contradicts the mapping. |

**Every other query:** outcome and grade identical to v9 (all 49). That includes #12, still
`UNSUPPORTED_ITEM` with the same invented "information security guideline (5.2 e)" item, which is
expected: nothing in v10 touched it (that is v14's variable). #36 and #50 remain correct refusals.
For the 40 ungraded queries this only means each was answered again; their text was not compared
for correctness.

**Criterion: met.** Re-grading every archive with the current grader (`benchmark_regrade_2026-10-17.json`)
leaves v1–v9 unchanged.

## What the number means

- **Legacy 96% (48/50)** = answered without refusing. +1 vs v9 is #18.
- **Graded 98% (49/50)** = legacy, plus #36 and #50 counted as correct refusals, minus #12 for its
  invented item. 40 of 50 answers are still not checked, so this is not an accuracy figure.
- **Quotable:** *"Adding the official risk descriptions to one mapping turned a refusal into a
  complete, correct answer, with no change to the other 49."* Not quotable: 96% or 98% as accuracy.
- **Single run**, as always.

## Next

v11 (next weekend): remove the three personal files from the corpus, re-ingest, benchmark
(HANDOFF 0b). Then v12–v14 as decided 2026-10-12.
