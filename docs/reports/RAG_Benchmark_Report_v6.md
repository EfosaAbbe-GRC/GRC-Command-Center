# RAG Benchmark Report v6 — Golden Mapping Metadata

**Date:** August 5, 2026
**Change:** `Golden_Mapping_refactor.md`, EXECUTED — 3 hand-curated, source-cited entries
(`backend/data/golden_mappings.json`) covering the EU AI Act risk-tiers / GPAI-generative-AI /
open-source clusters, matched at query time via cosine similarity against the already-loaded
`all-MiniLM-L6-v2` embeddings (no new dependency, no index rebuild, no re-ingestion).

---

## 1. Full-Day-and-Beyond Trajectory

*Every number below reflects a 2026-08-05 correction (see §3a) to a scorer bug present in every
run since v1 — the trend and every delta are unchanged, only the absolute values moved.*

| Run | Change | Score | Insufficient | Avg Latency |
| :--- | :--- | :--- | :--- | :--- |
| v1 (Apr 11) | baseline (k=5, 600-char chunks) | 42.0% | 29 | 3.67s |
| v2 | k=10 + 1000-char chunks | 70.0% | 15 | 4.05s |
| v3 | corpus repair (OWASP AI Exchange restored) | 76.0% | 12 | 3.94s |
| v4 | +8 official docs (17,088 splits) | 80.0% | 10 | 5.00s |
| v5 (Jul 18) | + cross-encoder re-ranker | 84.0% | 8 | 5.94s |
| **v6** | **+ Golden Mapping metadata** | **92.0%** | **4** | 6.6s |

**The scorer's raw, uncorrected output for this run said 94.0% (47/50) — see §3 for exactly why
that number is wrong and 92.0% (46/50) is the one to actually cite.**

## 2. What Golden Mapping actually fixed (confirmed, not assumed)

All three targeted queries flipped `INSUFFICIENT_DATA` → `ANSWERED`, and — unlike a retrieval-tuning
change, where you infer the mechanism from the score — here the answer text itself proves the
mechanism fired, because the LLM's response is a near-verbatim reproduction of the curated
`canonical_context`:

- **#16** ("four risk categories"): answer opens *"The EU AI Act defines a risk-based framework
  across four separate provisions... 1. Unacceptable risk: Article 5... 2. High risk: Article 6...
  3. Limited risk: Article 50..."* — structurally identical to the `EU_AI_ACT_RISK_TIERS` entry.
- **#19** ("ChatGPT"): *"The EU AI Act does not directly name 'ChatGPT'... it regulates this category
  as 'general-purpose AI models' (GPAI) under Chapter V, Articles 51-56..."* — matches
  `EU_AI_ACT_GPAI_GENERATIVE` verbatim in structure and citation.
- **#49** (open-source): *"The EU AI Act conditionally exempts free and open-source AI
  development... does not apply if these open-source AI systems are placed on the market... as a
  general-purpose AI model with systemic risk"* — matches `EU_AI_ACT_OPEN_SOURCE`.

Zero regressions: all 43 queries that passed in v5 still pass in v6.

## 3. The fourth flip (#6) is a scoring-script artifact, not a fix — flagged, not claimed

Query #6 ("Tier 1 thru Tier 4 implementation levels in NIST CSF 2.0") also flipped to `ANSWERED`,
but **Golden Mapping does nothing for NIST CSF — no entry targets it.** Reading the actual answer:

> *Tier 1: Partial [...described in full...]. Tier 2, Tier 3, and Tier 4: INSUFFICIENT_DATA: The
> provided compliance frameworks do not contain the definitions for Tier 2, Tier 3, or Tier 4...*

This is substantively the same partial, incomplete answer v5 gave — the CSF tiers table still isn't
recoverable from the corpus (structured-content extraction, per v5's diagnosis, still unresolved).
It only counts as `ANSWERED` because `rag_benchmark.py`'s scorer checks
`answer.startswith("INSUFFICIENT_DATA")`, and this run's phrasing happened to lead with "Based on
the provided context:" instead — pushing the literal string `INSUFFICIENT_DATA` into the body
instead of the first token. That's LLM phrasing non-determinism surfacing a real fragility in the
scoring script, not a retrieval or corpus improvement. **Treating this as still open.**

## 3a. Retroactive correction applied project-wide (2026-08-05)

The `#6` false-positive above wasn't a one-off — it's the same bug present in **every single
benchmark run this project has ever recorded**, one query at a time:

| Run | Falsely-`ANSWERED` query | Reported topline | Corrected topline |
| :--- | :--- | :--- | :--- |
| v1 | #31 (SOC 2 Type II) | 44.0% (22/50) | **42.0% (21/50)** |
| v2 | #6 (CSF tiers) | 72.0% (36/50) | **70.0% (35/50)** |
| v3 | #35 (Three Lines of Defense) | 78.0% (39/50) | **76.0% (38/50)** |
| v4 | #35 (same, persisted) | 82.0% (41/50) | **80.0% (40/50)** |
| v5 | #35 (same, persisted) | 86.0% (43/50) | **84.0% (42/50)** |
| v6 | #6 (recurred) | 94.0% (47/50) | **92.0% (46/50)** |

Fixed and applied:
- `backend/tests/rag_benchmark.py`'s check changed from `answer.startswith("INSUFFICIENT_DATA")` to
  `"INSUFFICIENT_DATA" in answer` — the model's own prompt template only promises to *include* that
  literal marker when part of an answer is missing, never that it will lead with it; a preamble like
  "Based on the provided context:" was enough to slip a partial answer past the old check.
- Every archived `rag_benchmark_results.v*.json` (plus the live `rag_benchmark_results.json`) had its
  one affected entry reclassified to `INSUFFICIENT_DATA` and its `summary` block recomputed, with a
  `_correction_note` / `_corrected_2026-08-05` field added for auditability — nothing was silently
  overwritten.
- `RAG_Benchmark_Report.md` (v1), `_v2.md`, `_v3.md`, and `_v5.md` were each given a correction
  callout and had their topline numbers updated to the corrected values. **The trend and every
  reported delta (+28 pts, +4 net from the re-ranker, etc.) are unchanged** — the bug affected
  consecutive runs identically, so differences between runs were never wrong, only each run's
  absolute number.

**Found but explicitly NOT fixed, separate from the above:** re-checking v1's per-query archive
against its own report's category-breakdown table (NIST/ISO/EU AI Act/GDPR/TPRM/etc.) turned up
inconsistencies unrelated to this scorer bug — e.g. the report's NIST row says "3/8 answered" while
the raw archived per-query outcomes say 5/8. This is a **different, unaudited issue**, out of scope
for this correction (which was scoped specifically to the `.startswith()` bug), and hasn't been
verified across the other category rows or other reports. Flagged in `RAG_Benchmark_Report.md`'s
correction note; not resolved here.

## 4. Remaining 3 failures — unchanged, out of scope for this change (as planned)

| Cluster | Queries | Nature |
| :--- | :--- | :--- |
| Missing source | #50 (CISA AI Audit Booklet) | Document absent from corpus entirely |
| Structured-content extraction | #6 (CSF 2.0 tiers) | Effectively still failing — see §3; table/graphic content invisible to the text splitter |
| Jitter | #36, #45 | Candidates for judge-calibration review, unchanged by this deploy |

(#6 listed here rather than in the "fixed" column, despite the raw scoreboard saying `ANSWERED` —
see §3.)

## 5. Deployment facts

- No re-ingestion, no FAISS rebuild, no chunk/index changes — `backend/core/rag.py`'s query path
  only, additive (golden context prepended alongside, never replacing, normal top-10 retrieval).
- Rebuilt `grc-backend` only; smoke **42/42**, pytest **32/32** — no change from pre-deploy baseline,
  confirming this was a pure query-path addition with zero schema/model blast radius.
- `numpy` promoted from transitive (via faiss-cpu/sentence-transformers) to a declared dependency in
  `requirements.txt`, since `rag.py` now imports it directly.

## 6. Artifacts

- Result archives (corrected 2026-08-05, see §3a): `.v1_baseline` 42% → `.v2_tuned` 70% →
  `.v3_corpus_repair` 76% → `.v4_corpus_expanded` 80% → `.v5_reranked` 84% → `.v6_golden_mapping`
  **92%** — all in `rag_benchmark_results.*.json`. 92.0% is now the scorer's actual output, not a
  manual attribution footnote — `rag_benchmark.py` itself was fixed, so this is what any future run
  will produce going forward too.
- Code: `backend/core/rag.py` (`_load_golden_mappings`, `_match_golden_mappings`), new
  `backend/data/golden_mappings.json` — per `Golden_Mapping_refactor.md`. Also
  `backend/tests/rag_benchmark.py` (scorer fix, see §3a).
- Not fixed, deliberately parked: the PDF text-extraction defect found investigating this
  (`EU AI ACT 2024_Doc.pdf` systematically renders "Article" as "Ar ticle" — 576+ occurrences, only
  file in the corpus with this producer), and the v1 category-breakdown-table discrepancy found
  while doing the §3a correction (separate from the scorer bug, not yet audited). Both are real,
  both are candidates for a future session, neither was in this change's scope.
