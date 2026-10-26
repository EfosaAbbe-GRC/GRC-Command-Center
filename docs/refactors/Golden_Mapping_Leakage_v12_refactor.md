# v12: remove benchmark questions copied into golden-mapping triggers

**Status:** DRAFT 2026-10-26, awaiting EXECUTE (GOVERNANCE.md §A). Decided 2026-10-12 (owner: "go
with the recommendation"); first proposed in `Golden_Mapping_Enumerations_refactor.md` Decision 2
(2026-09-27). **Benchmark: Sunday 2026-11-01** (weekend-only Groq budget). Built shift-left (owner's
standing rule): the risk first, a failing guard test before the change, and a pre-registered
outcome before the run.

**One variable:** three trigger phrases are deleted from `backend/data/golden_mappings.json`.
No code, prompt, model, index, threshold or other mapping text changes.

## 1. The risk: test-set leakage

A golden mapping injects verified reference text into the model's context whenever a question is
semantically close (cosine ≥ 0.70) to one of its trigger phrases. **Three triggers are the benchmark
questions themselves, word for word**, so those questions match at similarity 1.0 and are
*guaranteed* the verified text. Their passes measure the lookup table, not the system. This is a
measurement-integrity defect, and the same kind of thing as the 2026-08 scorer bug and the v7
error-counted-as-answer: a number that flatters the system for the wrong reason.

| Entry | Trigger (copied) | Benchmark question | Word overlap |
| --- | --- | --- | --- |
| `EU_AI_ACT_RISK_TIERS` | "What are the four risk categories defined in the EU AI Act?" | **#16** | 1.00 |
| `EU_AI_ACT_GPAI_GENERATIVE` | "How does the EU AI Act handle generative AI like ChatGPT?" | **#19** | 1.00 |
| `EU_AI_ACT_OPEN_SOURCE` | "How does the EU AI Act impact open-source AI development?" | **#49** | 1.00 |

The next-highest overlap of any trigger with any question is **0.54**, so these are the only copies.

**History, stated plainly:** the copies were deliberate in v6 (`Golden_Mapping_refactor.md`: "one
trigger per entry is the benchmark wording, plus 3 paraphrases for production phrasing"). That was
reasonable for proving the mechanism and is wrong for measuring the system. The four later entries
(#4, #12, #18, #26) were written with paraphrased triggers only, so they're unaffected.

## 2. What actually fires today (measured, not assumed)

From v11's own `audit_logs` (2026-10-25 run; `context` starts with "[… — verified reference]" when
a mapping fires). **9 of 50 questions received golden context:**

| Questions | Entry | Why |
| --- | --- | --- |
| #4, #12, #18, #26 | NIST GOVERN, ISO docs, OWASP, GDPR | intended, paraphrased triggers |
| **#16, #19, #49** | the three EU AI Act entries | **the copied triggers** (v12's target) |
| #17 (two EU AI Act entries), #21 (one) | EU AI Act entries | adjacent EU AI Act questions. Judged "additive, accurate context" in v6. **Not v12's variable**; observed, not changed. |

## 3. Phase 0: guard test first (RED today)

New `backend/tests/test_golden_mappings_hygiene.py`: pure unit tests with no stack, no model and no
Groq, so they're fast and pipeline-ready. Benchmark questions are read from
`rag_benchmark.py`'s `QUERIES` via `ast`, so the benchmark is never executed.

| Test | Asserts | Today |
| --- | --- | --- |
| `test_no_trigger_copies_a_benchmark_question` | no trigger equals a benchmark question after normalising case and punctuation | 🔴 3 |
| `test_no_trigger_near_copies_a_benchmark_question` | word-set overlap (Jaccard) of every trigger vs every question < **0.80** (today's highest legitimate value is 0.54) | 🔴 3 |
| `test_every_entry_keeps_at_least_two_triggers` | after the change every entry still has ≥ 2 triggers | 🟢 (stays green: 3 / 3 / 2 remain) |
| `test_mapping_file_is_valid` | every entry has `id`, `framework`, `trigger_phrases`, `canonical_context`, `source_file` | 🟢 |

**Why this is the shift-left part:** the leakage can't come back silently. Any future mapping that
copies a benchmark question fails the suite before it can inflate a score, and the DevSecOps
pipeline will run this on every push.

## 4. The change

Delete the three rows in §1's table from `trigger_phrases`. Then rebuild the backend (the mapping
file is baked into the image at `/app/data/`) and **verify the container's file is byte-identical
to the repo's** (SHA-256), as v10 did.

## 5. Pre-registered outcomes (written before the run, so they can't be fitted afterwards)

For each of #16, #19, #49, Sunday's `audit_logs` show whether the entry still fired (through its
remaining paraphrased triggers).

**What can be measured, corrected in the 2026-10-26 self-review:**

- **Only #16 is objectively graded**: it's in `rag_grading.CLOSED_LIST` (the four risk tiers).
- **#19 and #49 are ungraded**: any non-refusal counts as a pass. Their outcome comes from
  **reading the answer text against the EU AI Act source**, recorded as a judgement in the report,
  never as a grade.
- **Generation runs at temperature 0.7** (the `ChatGroq` default; never set), so a single run can't
  separate outcome B from sampling noise. A one-question flip is reported as a lead, not an effect
  (see v11's #39 correction). The remedy is **repeated sampling** (§6), not forcing
  temperature 0: that was briefly proposed in the same review and rejected on vendor guidance.

| Outcome | Meaning | How it's reported |
| --- | --- | --- |
| **A.** Stops firing, still answered correctly (graded for #16; read for #19/#49) | the pass never depended on the copy: **real** | keep the pass |
| **B.** Stops firing, refuses or degrades | the pass was inflated: **the expected case** (2026-10-12 note) | report the drop as a correction, as with #39 in v11 |
| **C.** Still fires via a paraphrase | the leak is closed; the entry legitimately matches a reworded question, which is its job | a pass, footnoted |

- **Everything else unchanged** (#4/#12/#18/#26 grades; #17/#21 still get EU AI Act context or
  not, but that's reported, not judged).
- **The citable figure is unaffected:** "42% → 92%" is v8's historical result. A drop here makes
  later runs more honest; it doesn't rewrite v8.
- **Zero-Groq pre-check, best effort:** replicating the 0.70 match offline for all 50 questions was
  attempted on 2026-10-26. It **couldn't run**: loading the embedding model in a second process
  hangs (found no cache readable by the app user; see the pipeline draft's open question on how
  the model is obtained). The post-run `audit_logs` measurement above replaces it.

## 6. Measuring through the noise (added 2026-10-26 self-review)

**Why:** generation is sampled. `ChatGroq`'s default is temperature 0.7 (never set explicitly). One
run per version can't tell a real effect from chance, and v8's #4 already failed to reproduce
across three runs. **Forcing temperature 0 was considered and rejected:** OpenAI's gpt-oss README
("Recommended Sampling Parameters") says *"We recommend sampling with temperature=1.0 and
top_p=1.0"*, and Groq's API reference says seeded sampling is "best effort … Determinism is not
guaranteed." So the noise is **measured** instead: the target questions are asked **3 times on
each side** of the change.

**Harness change (test tooling only; no app or retrieval change, so it isn't a benchmark
variable).** `rag_benchmark.py` gains:

- `GRC_BENCH_ONLY=16,19,49,17,21` and `GRC_BENCH_REPEAT=3`;
- subset runs write `rag_benchmark_repeats_<label>.json`, marked `subset: true` and
  `valid_full_run: false`. They **never overwrite** `rag_benchmark_results.json`, and the existing
  rescorer already skips them (not 50 results).

A unit test comes first: argument parsing, the refusal to overwrite, and the output marking.

**Pre-registered decision rule:** a question's outcome counts as **real** only if it holds in **≥ 2
of 3** samples on *both* sides of the change. Otherwise it's reported as **inconclusive (sampling
noise)**. Sunday's report is **provisional**; the 3-v-3 verdict lands the following Saturday.

| Sample set | When | Groq cost (≈) |
| --- | --- | --- |
| **Before:** #16, #19, #49, #17, #21 × 3, triggers still present | Sat 10-31, morning, after the security verification | ~50k |
| v12 change applied (data only, rebuild, hash check) | Sat 10-31, after the samples | 0 |
| **After, sample 1:** full 50-question v12 run | Sun 11-01, **≥ 24 h after Saturday's last Groq call** (in case the daily window rolls) | 150–200k |
| **After, samples 2–3:** the 5 targets × 2 | Sat 11-07, morning | ~35k |

**Recorded with every run:** model `openai/gpt-oss-120b`, temperature 0.7 (library default),
pacing. *Not v12's variable:* moving to the vendor-recommended temperature 1.0, or setting it
explicitly, is a separate one-variable change for later.

## 7. Sunday's run

**Prerequisite:** Saturday's security change touches secrets and DB roles, not retrieval. Confirm no
change under `backend/core/rag.py`, the prompt, the index or `golden_mappings.json` other than this
draft's, so v12 stays one variable.

1. Pre-flight probe (RPD near 1,000), at least 24 h after Saturday's last Groq call. Readiness.
   The container mapping hash equals the repo's.
2. Run per HANDOFF "Running a benchmark". The benchmark reads credentials via `_creds.py`
   (Saturday's change points it at the new secrets location).
3. Archive as `rag_benchmark_results.v12_no_benchmark_triggers.json`. Rescore all archives.
4. Run §2's `audit_logs` query for the v12 window, then **read the full answer text** of #16, #19,
   #49 (and any other flipped question) before writing `RAG_Benchmark_Report_v12.md`
   (**provisional** until the 11-07 samples).

## 8. Verification of the change (before Sunday)

| Check | Expected |
| --- | --- |
| `test_golden_mappings_hygiene.py` | 🔴 3 → 🟢 all |
| Full non-Groq pytest | unchanged count + the new tests |
| Container `golden_mappings.json` SHA-256 | equals the repo's |
| Readiness | ready |

## Rollback

`git revert` plus a rebuild. It's data-only.
