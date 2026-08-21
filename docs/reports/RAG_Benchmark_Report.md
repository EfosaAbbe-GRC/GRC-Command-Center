# RAG Accuracy Benchmark Report (v1.3.1)

**Date:** April 11, 2026  
**Model:** Gemini 2.5 Flash  
**Dataset:** 50 Targeted GRC Queries  
**Knowledge Base:** 174 PDF documents (PostgreSQL Evidence Chain)

> [!NOTE]
> **Correction (2026-08-05), two separate issues found and fixed:**
> 1. **Scorer bug:** the scorer used `answer.startswith("INSUFFICIENT_DATA")`, which missed cases
>    where the model answered part of a multi-part question and stated `INSUFFICIENT_DATA` inline
>    for the rest rather than as the literal first token. Query #31 (SOC 2 Type II) was
>    misclassified this way. Same bug found in every subsequent run through v6 — see
>    `RAG_Benchmark_Report_v6.md` for the full finding.
> 2. **Category table never matched the raw data.** Re-deriving §2's table directly from
>    `rag_benchmark_results.v1_baseline.json` found 6 of 7 rows didn't match the archive at all —
>    independent of the scorer bug above, and never fixed in any later report because v2 onward
>    computed this table correctly (checked: v2's matches its archive exactly; v3/v5 don't carry
>    this table format at all). The errors summed to exactly zero, which is why the grand total
>    (22/50) was still right despite 6 of 7 rows being wrong — the table below was corrected
>    2026-08-05 by direct computation from the archive, not estimated.
>
> True corrected figures: 42.0% (21/50, was 44.0%/22/50), 29 insufficient (was 28). §2's table below
> is corrected; §3's prose (which cited the old, wrong per-category picture) is corrected too.

---

## 1. Executive Summary: The Quality Baseline

The GRC Command Center has established a **42.0% RAG Accuracy Baseline** (corrected; originally
reported as 44.0% — see correction note above). While the infrastructure is 100% stable (zero
system errors), the retrieval layer for complex framework mappings (NIST AI RMF, ISO 27001 Clauses)
currently results in high "Insufficient Data" rates.

### **Key Metrics**
- **RAG Accuracy Percentage:** **42.0%** (21/50 Substantive Answers) — corrected, was 44.0% (22/50)
- **Insufficient Data Rate:** **58.0%** (29/50 Responses) — corrected, was 56.0% (28/50)
- **Average Response Latency:** **3.67s**
- **System Reliability:** **100.0%** (0 Errors)

---

## 2. Accuracy Scorecard (Framework Breakdown)

**Corrected 2026-08-05** — computed directly from `rag_benchmark_results.v1_baseline.json` (id
ranges per `rag_benchmark.py`'s category comments, confirmed identical to `diagnose_rag.py`'s
`get_expected_category()`). Originally-reported values struck through where changed.

| Category | Answered | Insufficient | Avg Latency |
| :--- | :--- | :--- | :--- |
| **NIST AI RMF / CSF 2.0** | ~~3/8~~ **5/8** | ~~5/8~~ **3/8** | ~~4.12s~~ **3.44s** |
| **ISO 27001 / 42001** | ~~4/7~~ **3/7** | ~~3/7~~ **4/7** | ~~3.85s~~ **3.28s** |
| **EU AI Act / OWASP** | 3/8 | 5/8 | ~~3.45s~~ **3.13s** |
| **GDPR / Privacy** | ~~2/5~~ **3/5** | ~~3/5~~ **2/5** | ~~3.10s~~ **3.94s** |
| **TPRM / Third Party** | 1/5 | 4/5 | ~~5.20s (Peak)~~ **3.23s** |
| **GRC Engineering / Audit** | ~~5/7~~ **4/7** | ~~2/7~~ **3/7** | ~~2.85s (Fastest)~~ **3.11s** |
| **Emerging AI Risks** | ~~4/10~~ **2/10** | ~~6/10~~ **8/10** | ~~3.50s~~ **2.89s** |

---

## 3. Findings & Retrieval Dead Zones

**Corrected 2026-08-05** — two bullets below made specific per-query claims that don't hold up
against the raw archive (found while re-deriving §2); struck through and fixed rather than deleted.

### 🔍 **Retrieval Strengths**
- **GRC Engineering**: The system excelled at queries related to ITGCs and Three Lines of Defense
  ~~, and Audit Evidence (5/7 Answered)~~ (**4/7 Answered** — the chain-of-custody/"Audit Evidence"
  query, #40, was actually `INSUFFICIENT_DATA`, not a strength).
- **ISO 27001 Core**: Successfully retrieved ~~Annex A.5.7 and~~ Context of Organization details.
  (~~Annex A.5.7~~ was actually `INSUFFICIENT_DATA` — #10 never retrieved successfully in this run.)

### ⚠️ **The "Generalization" Gap (Dead Zones)**
- **NIST AI RMF depth**: While the system knows the functions (Govern, Map, etc.), it struggled with
  specific core outcomes and implementation levels. (Verified: NIST was actually the strongest
  category overall at 5/8, not the 3/8 originally reported in §2 — this bullet's narrower claim
  about implementation-level depth specifically still holds, #6 CSF tiers did fail.)
- **TPRM Specifics**: High "Insufficient Data" on vendor assessment strategies, suggesting the
  knowledge base contains brochures rather than deep procedural manuals for TPRM. (Verified
  accurate: 1/5 answered.)
- ~~**EU AI Act Complexity**: Failed to provide substantive details on target-human transparency~~
  — **this claim was backwards**: the target-human-transparency query (#20) was actually
  `ANSWERED`. EU AI Act's real dead zone is the risk-tiers/GPAI/open-source cluster (#16/#19/#49,
  fixed 2026-08-05 by Golden Mapping — see `RAG_Benchmark_Report_v6.md`), not this query.

---

## 4. Optimization Roadmap for Week 2

1. **Context Expansion (k-increase)**: Increase `k` from 3 to 5 in `rag.py` to provide more chunk-density to the LLM.
2. **Chunk Re-tuning**: The current 600-char chunk size may be truncating complex framework definitions. Recommend testing 1000-char chunks for framework-heavy corridors.
3. **Structured Meta-Data**: Ingest a "Golden Mapping" spreadsheet of Framework -> Control ID to bypass fuzzy vector retrieval for known compliance IDs.

---
> [!NOTE]
> **Full Results:** A detailed JSON breakdown of every query, latency, and answer is available in [rag_benchmark_results.json](file:///c:/Users/efosb/OneDrive/Desktop/GRC%20Inspector/GRC_Command_Center/rag_benchmark_results.json).
