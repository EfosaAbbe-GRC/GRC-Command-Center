# RAG Accuracy Benchmark Report v3 (Corpus Repair)

**Date:** July 18, 2026
**Change under test:** Corpus repair only — retrieval config unchanged from v2 (k=10, 1000/100 chunks)
**Corpus:** 150 valid PDFs / 12,548 splits. 7 truncated files quarantined (`*.pdf.corrupt`);
`Owasp AI Exchange.pdf` restored from official source (owaspai.org, CC0). **First-ever zero-error ingest.**

> [!NOTE]
> **Correction (2026-08-05):** scorer bug (`.startswith("INSUFFICIENT_DATA")` missed inline
> refusals not in the first token) misclassified query #35 (Three Lines of Defense — 1st line
> answered, 2nd/3rd line explicitly `INSUFFICIENT_DATA`) as ANSWERED in this run (and in v4, v5 —
> same query, same failure mode, persisted across all three). True corrected figures below (was
> 78.0% / 39/50 / 11 insufficient). Full finding: `RAG_Benchmark_Report_v6.md`. The trajectory row
> below is corrected; §3's remaining-failures table was not originally re-audited for this query
> and has been updated to include it under a new cluster.

---

## 1. Trajectory

| Metric | v1 (Apr 11) | v2 (Jul 18) | **v3 (Jul 18)** |
| :--- | :--- | :--- | :--- |
| Substantive answers | 21/50 (42%)¹ | 35/50 (70%)¹ | **38/50 (76%)¹** |
| Insufficient data | 29¹ | 15¹ | **12¹** |
| System errors | 0 | 0 | **0** |
| Avg latency | 3.67s | 4.05s | **3.94s** |
| Ingest errors | 7 files | 7 files | **0 files** |

¹ Corrected 2026-08-05 — originally reported 44%/72%/78% (22, 36, 39 answered). The improvement
trend is unchanged; see correction note above.

## 2. What the corpus repair bought (v2 → v3)

**Flipped to ANSWERED (+5):**
- #22 Prompt-injection mitigations, #23 Model Inversion, #46 Model vs Data Poisoning — all served by
  the restored OWASP AI Exchange, as predicted
- #24 GDPR automated decision-making, #40 audit chain-of-custody — v2's borderline retrievals
  stabilized by the healthier index

**Regressed (−2):** #6 (CSF 2.0 tiers), #7 (NIST bias management) — answered in v2, refused in v3.
Retrieval jitter: the corpus content didn't change for these; chunk neighborhoods shifted when the
index grew by 664 splits. These borderline flip-flops (#6, #7, #36, #40 have each flipped at least
once across runs) are the strongest argument for the cross-encoder re-rank (Change 3).

## 3. The 11 Remaining Failures (12, corrected — #35 added)

| Cluster | Queries | Path forward |
| :--- | :--- | :--- |
| EU AI Act article-level depth | #16, #19, #49 | Re-rank A/B + Golden Mapping metadata |
| Missing source documents | #18 (OWASP **LLM Top 10** — a *different* OWASP doc, not AI Exchange), #32 (SOC 2 vendor guidance), #38 (SOX — corrupt file unreplaced), #50 (CISA AI Audit Booklet) | Acquire/replace sources (#18 fetchable from genai.owasp.org; #38 awaiting user re-source or PCAOB substitute) |
| Image-heavy PDF | #48 (6 pillars, 313 chars/page) | OCR or replace with text-first source |
| Retrieval jitter | #6, #7, #36 | Cross-encoder re-rank (Change 3, drafted) |
| Structured/enumerated-list depth *(added 2026-08-05, was hidden by the scorer bug)* | #35 (Three Lines of Defense — 1st line answered, 2nd/3rd not in context) | Same shape as #6 (CSF tiers) — a multi-part enumeration where only the first part is in the corpus; candidate for the same lever as #6, not yet assigned |

## 4. Certification Notes

- Integrity manifest verified green after re-ingest over an existing index — first live regression
  pass of the `_hash_index()` fix (the pre-fix code failed exactly this scenario).
- Evidence chain extended with SHA-256 records for all 150 files, including the restored OWASP
  document (provenance: official owaspai.org distribution, CC0 license).
- Result archives: `rag_benchmark_results.v1_baseline.json` (42%, corrected), `.v2_tuned.json`
  (70%, corrected), `.v3_corpus_repair.json` (76%, corrected) — archives themselves updated
  2026-08-05 with a `_correction_note`/`_corrected_2026-08-05` field on the affected entry; see
  `RAG_Benchmark_Report_v6.md`.
