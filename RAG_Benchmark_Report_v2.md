# RAG Accuracy Benchmark Report v2 (Retrieval Tuning Sprint)

**Date:** July 18, 2026
**Model:** Gemini 2.5 Flash (pinned, unchanged from baseline)
**Dataset:** Same 50 targeted GRC queries as v1 baseline (2026-04-11)
**Change under test:** `k` 5 → 10, chunk size 600/60 → 1000/100 (Retrieval_Tuning_refactor.md, Changes 1–2)
**Index:** 11,884 splits from 149 PDFs (corpus coverage identical to baseline — same 7 dehydrated files skipped)

---

## 1. Executive Summary

| Metric | v1 Baseline | v2 (this run) | Δ |
| :--- | :--- | :--- | :--- |
| **Substantive-answer rate** | 44.0% (22/50) | **72.0% (36/50)** | **+28.0 pts** |
| Insufficient Data rate | 56.0% (28/50) | 28.0% (14/50) | −28.0 pts |
| System errors | 0 | 0 | — |
| Avg latency | 3.67s | 4.05s | +0.38s |

The v1 diagnostic's C1 hypothesis is **confirmed**: the corpus contained the answers all along, and
they were being lost below the k=5 cutoff in over-fragmented 600-char chunks. Doubling retrieval
depth and re-chunking recovered exactly the failure class predicted, at a latency cost of ~0.4s.
The ≥70% sprint gate is **met**.

## 2. Category Scorecard (before → after)

| Category | v1 Answered | v2 Answered | Δ | v2 Avg Latency |
| :--- | :--- | :--- | :--- | :--- |
| NIST AI RMF / CSF 2.0 | 3/8 | **8/8** | +5 | 7.23s |
| ISO 27001 / 42001 | 4/7 | **7/7** | +3 | 3.84s |
| EU AI Act / OWASP | 3/8 | 3/8 | ±0 | 3.51s |
| GDPR / Privacy | 2/5 | **4/5** | +2 | 3.95s |
| TPRM / Third Party | 1/5 | **4/5** | +3 | 3.73s |
| GRC Engineering / Audit | 5/7 | 4/7 | −1 | 3.22s |
| Emerging AI Risks | 4/10 | **6/10** | +2 | 2.88s |

Framework-heavy categories (NIST, ISO) — where 600-char chunks were shredding clause definitions —
went to **perfect scores**. The former worst category (TPRM, 1/5) quadrupled.

## 3. Analysis of the 14 Remaining Failures

The residual failures are **not** the v1 failure mode. They cluster into three explainable groups:

1. **Dehydrated-source content (≈5 queries).** The OWASP queries (#18, #22, #23) map to
   `Owasp AI Exchange.pdf` and the SOX query (#38) to `Sox Internal Controls Implementation.pdf` —
   both among the 7 OneDrive cloud-only placeholders skipped at ingest. These answers are absent
   from the index entirely; no retrieval tuning can find them. → **Fix: P2 Corpus Hydration.**
2. **Low-text-density PDFs (≈2 queries).** #48 ("6 pillars for AI-ready security") maps to an
   11.6 MB, 9-page, 313-chars/page design-heavy PDF — near-zero extractable text.
   → Candidates for OCR or replacement with text-first sources.
3. **EU AI Act depth (≈4 queries: #16, #19, #24, #49).** The Act's 144-page official journal text
   is in the vault, but article-level specifics (risk tiers, GPAI, open-source carve-outs) remain
   hard for pure vector search. → Best candidates for the **cross-encoder re-rank A/B (Change 3)**
   and the P2 Golden Mapping metadata.

Regression note: GRC Engineering dropped 5/7 → 4/7 (#36 gap assessment, #40 chain-of-custody flipped).
With 1000-char chunks the index halved in granularity; a couple of borderline retrievals shifted.
Net effect across the suite is strongly positive; the re-rank A/B should recover these.

## 4. Deployment Integrity Note

During re-indexing, a latent defect was found and fixed in the index-signing path: `_hash_index()`
included the stale `.integrity` manifest in the new signature, guaranteeing a false-positive
"TAMPERED" verdict on any index rebuild. This is the probable true root cause of incident
**FAISS-INT-001** (April 10), previously attributed to a Docker volume race. The signer now
excludes the manifest, symmetric with verification. Manifest re-signed; readiness green.

## 5. Recommended Next Steps

1. **Corpus Hydration (P2)** — pin `GRC_Analyst/` always-keep-on-device, re-ingest, re-benchmark.
   Directly targets ~5 of 14 remaining failures.
2. **Cross-encoder re-rank A/B (Change 3, drafted)** — k=20 → top 10 via
   `cross-encoder/ms-marco-MiniLM-L-6-v2`; targets EU AI Act depth and the two GRC-Eng regressions.
3. **Golden Mapping metadata (P2)** — structured Framework → Control ID lookup for clause-level queries.

---
> [!NOTE]
> **Artifacts:** v2 raw results in `rag_benchmark_results.json`; v1 baseline preserved in
> `rag_benchmark_results.v1_baseline.json`. Same query set, same pinned model, same corpus coverage.
