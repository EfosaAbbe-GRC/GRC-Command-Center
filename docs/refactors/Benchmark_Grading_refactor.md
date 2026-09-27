# Benchmark grading: stop scoring "didn't refuse" as "correct"

**Status:** ✅ **Parts A–D EXECUTED 2026-09-27** (Efosa: "do the score work"; decisions 1 and 2
taken as recommended). Verified: `test_rag_grading.py` 15/15, full pytest **65/65** (was 50),
`rescore_benchmarks.py` reproduces the table below exactly, no archive modified.
⏸ **Part E (correct the v7 record) — NOT executed; awaiting its own explicit approval.**
Drafted 2026-09-27.
**Costs zero Groq tokens.** Everything here re-reads answer text already stored in the archives.
**Files:** new `backend/tests/rag_grading.py`, new `backend/tests/test_rag_grading.py`, new
`scripts/rescore_benchmarks.py`, edit `backend/tests/rag_benchmark.py`.
**Effort:** small–medium. The grading logic already exists as a working prototype, run against
every archive (results below) — this draft is that prototype, cleaned up.

---

## The problem, in one line

`rag_benchmark.py` scores **"did the model refuse?"** — nothing else. Anything that isn't a
refusal and is over 20 characters counts as a correct answer.

## Evidence — found by re-reading archived answers, not assumed

The prototype grader (Part A) was run over all eight complete archives. Every surprising verdict
was then checked by reading the actual answer text:

| Where | Old score | What the answer actually says | Real verdict |
| --- | --- | --- | --- |
| v8 #12 ISO 27001 mandatory docs | ✅ | "Information security guideline" — one item; says nothing else is mandatory | ❌ incomplete (0/11) |
| v8 #4 GOVERN outcomes | ✅ | GOVERN 1, 2, 4, 5 — omits 3 and 6 | ❌ incomplete (4/6) |
| v8 #36 CSF ↔ ISO 27001 gap assessment | ❌ | refuses — no crosswalk exists in the corpus | ✅ correct refusal |
| v6 #18 OWASP LLM Top 10 | ✅ | describes what the list *is*; names **zero** of its items | ❌ incomplete (0/6) |
| v6 #12 ISO 27001 mandatory docs | ✅ | "Essential policies, Processes, Risk evaluations, …" | ❌ incomplete (0/11) |
| **v7 #35, #39, #45** | ✅ ✅ ✅ | **"I encountered an error processing your request."** | **engine errors** — see Part E |

The binary scorer is wrong in **both** directions, and has been since v1.

## Re-graded trajectory (prototype output, 2026-09-27)

| Version | Old score | Re-graded | Engine errors | Checkable queries passed |
| --- | --- | --- | --- | --- |
| v1 | 21/50 | 22/50 | 0 | 4/32 |
| v2 | 35/50 | 35/50 | 0 | 5/20 |
| v3 | 38/50 | 38/50 | 0 | 5/17 |
| v4 | 40/50 | 37/50 | 0 | 4/17 |
| v5 | 42/50 | 41/50 | 0 | 5/14 |
| v6 | 46/50 | 45/50 | 0 | 6/11 |
| v7 | 45/50 | **42/50** | **3** | 4/9 |
| **v8** | **46/50** | **46/50** | 0 | **6/10** |

**v8 stays at 92% under both scorers** — but for different reasons: two false passes removed
(#4, #12), two correct refusals credited (#36, #50). Same number, now defensible. v8 also has the
best result on the checkable queries of any version.

"Checkable" = the 10 queries with an objective answer (8 closed lists + 2 expected refusals).
The other 40 answers are still **ungraded** — counted as passes, exactly as today. This draft does
not pretend to grade them; see Limitations.

---

## Part A — `backend/tests/rag_grading.py` (new, pure functions, no network)

Seven outcomes instead of three:

| Grade | Meaning | Counts as pass? |
| --- | --- | --- |
| `COMPLETE` | closed-list query, required items present | ✅ |
| `INCOMPLETE` | closed-list query, items missing | ❌ |
| `CORRECT_REFUSAL` | refused a query whose source isn't in the corpus | ✅ |
| `UNSUPPORTED_ANSWER` | answered a query whose source isn't in the corpus | ❌ |
| `WRONG_REFUSAL` | refused a query the corpus can answer | ❌ |
| `UNGRADED_ANSWER` | answered; no objective check exists for this query | ✅ (as today) |
| `ERROR` | engine failure — re-detected from the answer text | ❌ |

**Closed-list checks** — official sources only, matched case-insensitively after normalising
Unicode spaces/hyphens (the model writes `Lessons Learned`, which a naive match misses — found
by the prototype):

| # | Query | Items | Pass bar |
| --- | --- | --- | --- |
| 1 | NIST AI RMF functions | Govern, Map, Measure, Manage | all |
| 4 | AI RMF GOVERN outcomes | GOVERN 1–6 (by number or topic) | all |
| 6 | CSF 2.0 tiers | Partial, Risk Informed, Repeatable, Adaptive | all |
| 12 | ISO 27001:2022 mandatory documented information | 11 clauses: scope 4.3, policy 5.2, risk assessment 6.1.2/8.2, risk treatment 6.1.3/8.3, SoA 6.1.3d, objectives 6.2, competence 7.2, monitoring 9.1, internal audit 9.2, management review 9.3, nonconformity/corrective action 10.2 | ≥ 80% |
| 16 | EU AI Act risk tiers | unacceptable, high, limited, minimal | all |
| 18 | OWASP LLM Top 10 | 6 items common to **both** the 2023 and 2025 editions (prompt injection, sensitive info disclosure, supply chain, poisoning, output handling, excessive agency) | ≥ 80% |
| 26 | GDPR Art. 5 principles | all seven | all |
| 39 | NIST SP 800-61r2 IR phases | preparation, detection & analysis, containment/eradication/recovery, post-incident | all |

**Expected refusals** — each records *why* and the corpus state it was verified against, because
the expectation is only true while the source is absent:

```python
EXPECT_REFUSAL = {
    36: ("no NIST CSF <-> ISO 27001 crosswalk in corpus", "curated-148 (2026-09-21)"),
    50: ("CISA AI Audit Booklet not in corpus",           "curated-148 (2026-09-21)"),
}
```

When a crosswalk is added (HANDOFF queue #2), #36 moves from `EXPECT_REFUSAL` to `ENUM` — one
line, and the change is visible in git history.

## Part B — `rag_benchmark.py` records both scores

- Each result gains `grade` and `grade_detail` (e.g. `"4/6 miss[3, 6]"`).
- Summary gains `graded_pass`, `graded_percentage`, `grade_counts`, `checked_pass`, `checked_total`.
- **`accuracy_percentage` is left exactly as it is**, so v1–v8 stay comparable on the old measure.
- The final printout shows both lines:

  ```text
  Answer rate (legacy): 92.0% (46/50)
  Graded:               92.0% (46/50)  -- checkable 6/10, 40 ungraded
  ```

- `import` works as-is: the script runs as `python backend/tests/rag_benchmark.py`, so
  `backend/tests/` is already on `sys.path`. No new dependencies.

## Part C — `scripts/rescore_benchmarks.py` (new)

Re-grades every complete archive and writes **one new file**,
`docs/reports/benchmark_regrade_<date>.json`, plus the table above to stdout. **It never modifies
an archive** — the originals stay byte-identical, per archive-don't-delete.

## Part D — `backend/tests/test_rag_grading.py` (new)

Unit tests built from **real archived answers**, not invented strings — every case below is a
failure that actually happened:

1. v8 #4 → `INCOMPLETE`, misses GOVERN 3 and 6
2. v8 #12 → `INCOMPLETE`
3. v6 #18 (describes the list, names no items) → `INCOMPLETE`
4. v7 #39 ("I encountered an error…" stored as ANSWERED) → `ERROR`
5. v8 #39 (`Lessons Learned`) → `COMPLETE` — the Unicode-space regression
6. v8 #36 refusal → `CORRECT_REFUSAL`; v7 #36 answer → `UNSUPPORTED_ANSWER`
7. v8 #26 refusal → `WRONG_REFUSAL`
8. Any query not in either table → `UNGRADED_ANSWER`
9. `grade()` never raises on an empty or `None` answer

No stack, no network. pytest goes **50 → ~59**.

**Verification after EXECUTE:** new tests green; full pytest green; `rescore_benchmarks.py`
reproduces the table above exactly; `git diff` shows no archive touched.

---

## Part E — correct the v7 record (⚠ separate approval)

**Finding:** v7's three "answers with zero sources" (#35, #39, #45) are the engine's own error
message: `"I encountered an error processing your request."` `RAG_Benchmark_Report_v7.md` read them
as possible hallucinations; they are **engine failures** — most likely Groq's 8,000 TPM limit,
since v7 ran unpaced at ~3.56 queries/min (pacing arrived 2026-09-21).

**Why it slipped through:** the check that catches this string was added on 2026-08-17 *after* the
fake-96% run, and v7 was scored before it. The check was right; it was just never applied
backwards.

**Consequence:** v7 was **42/50 with 3 engine errors**. Under the project's own rule ("a run with
any engine error is not a valid measurement"), **v7's 90% was never a valid figure.**

**Proposed corrections** (strikethrough + dated "Corrected" callout, original values kept visible
— the established convention):

- `RAG_Benchmark_Report_v7.md` — headline and §"Three answers with zero retrieved sources".
- `RAG_Benchmark_Report_v8.md` — two claims written this morning on the strength of v7's number:
  "+2 points vs v7" and "zero-source answers: resolved" (they were never answers).
- `docs/session-logs/MEMORY.md` and the trajectory tables — mark v7 **invalid (3 engine errors)**.

**Unaffected:** v8's 92%, and the public README's "42% → 92%". Neither depends on v7.

---

## Decisions for Efosa

1. **Which number is the headline going forward?** *Recommendation: graded*, with the legacy
   answer rate kept alongside. For v8 they're both 92%, so nothing public changes today — but graded
   is the one that can't be inflated by confident wrong answers.
2. **Pass bars:** all items for short lists, ≥ 80% for the two long ones (#12's 11 clauses,
   #18's 6 items). *Recommendation: as drafted.*
3. **Part E:** approve the v7 correction? *Recommendation: yes* — same reasoning as the 44%→42%
   decision: correct it before anyone else finds it.

## Limitations — stated, not hidden

- **Keyword coverage, not correctness.** v8 #39 passes, but its six steps (Identification,
  Containment & Escalation, …) are the **SANS** incident-response model presented as NIST 800-61
  (whose r2 phases are four). The grader sees the right words and passes it. Only a judge — human
  or the calibrated LLM judge still stuck on the dead Gemini key — can catch misattribution.
- **40 of 50 answers remain ungraded.** The graded score is an honest *upper bound*, not a
  correctness rate. Extending it means migrating `validate_diagnostic.py` to Groq (HANDOFF
  lower-priority item), which does cost tokens.
- **Expected refusals depend on the corpus.** Each one records the corpus state it was verified
  against; revisit them whenever documents are added.
