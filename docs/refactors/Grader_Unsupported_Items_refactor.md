# Grader: fail closed-list answers that add items the official list doesn't have

**Status:** DRAFT 2026-10-04 — awaiting EXECUTE. Efosa's choice for v9 decision b (2026-10-04):
"have the grader catch made-up items". Tests-only; zero Groq tokens; no rebuild.

## Why

v9 #12 listed every real ISO/IEC 27001:2022 documented-information requirement **plus** an
invented one ("information security guideline, 5.2 e" — not in the standard, checked against the
official text). The grader only checks that required items are *present*, so it scored a pass. In
GRC terms, telling someone a requirement exists when it doesn't is an error, not a bonus.

## Change — `backend/tests/rag_grading.py`

1. New `ALLOWED_ITEMS` dict for closed-list queries whose full official list is known: **#4**
   (6 GOVERN categories), **#12** (all 14 clause locations, incl. 7.5.1 b and 8.1, which the
   presence check deliberately leaves out), **#18** (2025 *and* 2023 OWASP names, since either
   edition is accepted), **#26** (7 Art. 5 principles). Each is a superset of that query's
   `CLOSED_LIST` patterns.
2. In `grade()`, after a closed-list answer reaches the pass bar: extract its top-level list items
   (numbered lines and markdown table rows); if any item matches **no** allowed pattern, return a
   new grade **`UNSUPPORTED_ITEM`** with the offending text in `detail`. It is **not** in `PASSING`.
3. `ALL_GRADES` gains `UNSUPPORTED_ITEM`; `summarise()` counts it.

## Evidence — prototype run over every valid archive (v1–v9)

| Archive | Query | Items | Flagged | Reading |
| --- | --- | --- | --- | --- |
| v9 | #12 | 15 | 1 — "Information security guideline… 5.2 e" | **true catch** |
| v8 | #4 | 4 | 1 — "GOVERN 4 Risk documentation and communication" | **borderline**: loose paraphrase of GOVERN 4 ("culture that considers and communicates AI risk"); already `INCOMPLETE`, grade unchanged |
| all others | #4/#12/#18/#26 | 0–15 | 0 | — |

**Grade impact:** v9 graded 49 → **48/50** (#12 becomes `UNSUPPORTED_ITEM`). No other archive's
pass/fail changes.

**Decision in the draft (recommendation: accept the paraphrase).** Allow `communicat` for GOVERN 4
so a faithful paraphrase passes and only content absent from the framework is flagged. The check is
meant to catch inventions, not wording.

## Known limits — stated, not hidden

- Only numbered items and table rows are checked; a fabricated **bullet** (`- …`) is not. Most
  enumeration answers in the archives are numbered. Extend only if a bulleted fabrication is seen.
- Only the four queries above. The other closed-list queries (#1, #6, #16, #39) are 4-item lists
  where an extra item is unlikely; add them when a case appears.
- It catches fabricated **items**, not wrong statements inside a correct item.

## Verification

New tests in `test_rag_grading.py` from real archives: v9 #12 → `UNSUPPORTED_ITEM`; v9 #4, #26 stay
`COMPLETE`; v8 #4 stays `INCOMPLETE`. `pytest` from `backend/`; then
`scripts/rescore_benchmarks.py` and confirm the only change is v9 #12. Update the v9 report's
graded figure with a dated correction (98% → 96%), keeping the original visible.
