# RAG Benchmark v11 — Three personal (non-GRC) files removed from the corpus

**Run date:** 2026-10-25 · **Legacy: 96.0% (48/50) · Graded: 96.0% (48/50, checkable 8/10)** ·
avg latency **4.1s** · 0 system errors

**Archive:** `rag_benchmark_results.v11_personal_files_removed.json`
**What changed since v10 — one thing:** the corpus. Three personal, non-GRC files were moved from
the corpus folder to its `Excluded Docs/` subfolder (archived, not deleted; approved 2026-09-29),
then the index was rebuilt. Re-ingest: **145 files, 16,998 chunks, 0 errors**, 30 min (was 148 /
17,123, so 125 chunks removed). The chunk count was cross-checked against the index file's size
(`16,998 × 1,536 + 45` bytes = exact). Verified, not assumed: the ingest endpoint
(`initialize_index`) lists the top-level folder only, so `Excluded Docs/` is not re-indexed. The
container saw 145 PDFs before the run. No `backend/` change since v10. Model, chunking,
embeddings, re-ranker, `k`, prompt and golden mappings are unchanged.

**Do not quote 96% as accuracy.** The figure to cite stays *"42% → 92%"* (v8).

## The run

Pre-flight: RPD probe **999/1000** twice (before the re-ingest and before the run). Mufasa doesn't
run its AI analysis at weekends (owner). Launched detached ~00:35, finished 00:56 (~21 min). Two
mid-run re-logins, **zero 401s, zero 429s, zero engine errors**.

## Result against the success criterion

Criterion set in `HANDOFF.md` before the run: *no grade changes versus v10. The files are non-GRC,
so any query that moves is evidence they were being retrieved, and its answer text must be read.*

| Query | v10 | v11 | Answer text, read in full |
| --- | --- | --- | --- |
| #39 NIST 800-61 incident-response steps | COMPLETE 4/4 | **INCOMPLETE 3/4** (missing post-incident / lessons learned) | **v10's pass was propped up by a removed file.** The platform's own `audit_logs` show v10's #39 retrieved one of the three personal files as its 5th source. v10's answer used the SANS phase names ("Identification", "Containment & Escalation", "Lessons Learned") under a NIST heading, the weakness `rag_grading.py`'s docstring already flagged for v8 #39. v11 drew only on official NIST sources (4) and uses NIST's own wording ("Detection and Analysis"; containment, eradication and recovery as separate steps), but stops at Recovery and leaves out the fourth phase. |

**Every other query:** outcome and grade identical to v10 (all 49). #12 keeps `UNSUPPORTED_ITEM`
with a reworded version of the same invented "information security guideline" item (v14's
variable). #36 and #50 remain correct refusals.

**Exposure, measured rather than inferred:** across v10's 50 `audit_logs` rows, exactly **1**
answer (#39) retrieved any of the three files. In v11, **0** did.

**Criterion: not met. The removal is still correct, and this is why.** The criterion existed to
detect retrieval of these files, and it did: one compliance answer was partly built from a personal
study document and still labelled as NIST. The lower grade is a more honest measurement, not a
regression to undo. It repeats the 2026-09-26 lesson (#26): a removal can expose a weakness the
removed document was masking. **Do not restore the files.**

**Context for #39, checked in the corpus PDFs:** SP 800-61 **r3** (2025) restructures incident
response around CSF 2.0 (33 mentions). It has no "Detection and Analysis" or "Post-Incident
Activity" phase names, which only the **withdrawn r2** uses (15 and 1). The grader's four checks
are r2's phases. "Lessons learned" still appears 12 times in r3, so the content was retrievable and
the model left it out. Candidate follow-up, not decided: re-word query #39 or its check to target
r3 explicitly, or accept r2's phases as the benchmark's definition. Either is a one-variable change
for its own run.

## What the number means

- **Legacy 96% (48/50)** = answered without refusing, unchanged from v10.
- **Graded 96% (48/50)** = legacy, plus #36 and #50 as correct refusals, minus #12 (invented item)
  and #39 (incomplete). 40 of 50 answers are still unchecked, so this is not an accuracy figure.
- **Quotable:** *"Removing three non-GRC files exposed one answer that had been partly sourced from
  personal study notes; without them it cites only official NIST sources."* Not quotable: 96% as
  accuracy.
- **Single run**, as always.

Re-grading every archive with the current grader (`benchmark_regrade_2026-10-25.json`) leaves
v1–v10 unchanged.

## Next

v12–v14 as decided 2026-10-12 (HANDOFF §0): v12 exact-wording triggers, v13 GDPR PDF re-extract,
v14 list-only instruction. #39's wording question (above) waits behind them.
