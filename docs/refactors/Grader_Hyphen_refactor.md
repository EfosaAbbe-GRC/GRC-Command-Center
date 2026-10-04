# Grader: let a space in an item pattern match a hyphen

**Status:** DRAFT 2026-10-04 — awaiting EXECUTE. Tests-only; zero Groq tokens; no container rebuild.
**Found by:** reading v9's #12 answer (`RAG_Benchmark_Report_v9.md` §"Grader finding — hyphens").

## The problem

`backend/tests/rag_grading.py` normalises Unicode hyphens to `-` (`_NORMALISE`), then matches
closed-list item patterns written with literal spaces: `r"internal audit"`, `r"management review"`,
`r"risk assessment"`, `r"purpose limitation"` and others. An answer that writes `internal‑audit`
therefore misses the item. v9 #12 was reported 9/11 when all 11 items are present.

## Impact, measured

Re-grading every archive (v1–v9) with hyphens treated as spaces changes **one detail, no grade**:
v9 #12, 9/11 → 11/11. The risk is a future false `INCOMPLETE` near the pass bar, since
`gpt-oss-120b` hyphenates compound nouns often (469 non-breaking hyphens in v9's answers).

## Change

In `grade()`, match closed-list items against a copy of the text with hyphens replaced by spaces:

```python
        flat = text.replace("-", " ")
        hits = [bool(re.search(p, flat, re.I)) for p in items]
```

Safe for the existing patterns: none contains a literal `-`; the ones that span word boundaries use
`.` (`risk.informed`, `post.incident`, `high.risk`), which matches either form. The refusal and
engine-error checks keep using the unflattened text.

## Test

Add to `test_rag_grading.py`: v9 #12's archived answer grades `COMPLETE 11/11`; an answer with
`internal-audit` (ASCII) matches the internal-audit item. Then run `pytest` from `backend/` (expect
65 + new) and `scripts/rescore_benchmarks.py` (expect only v9 #12's detail to change).
