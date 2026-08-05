# RAG Accuracy Benchmark Report (v1.3.1)

**Date:** April 11, 2026  
**Model:** Gemini 2.5 Flash  
**Dataset:** 50 Targeted GRC Queries  
**Knowledge Base:** 174 PDF documents (PostgreSQL Evidence Chain)

> [!NOTE]
> **Correction (2026-08-05):** the scorer used `answer.startswith("INSUFFICIENT_DATA")`, which
> missed cases where the model answered part of a multi-part question and stated
> `INSUFFICIENT_DATA` inline for the rest rather than as the literal first token. Query #31 (SOC 2
> Type II) was misclassified this way. True corrected figures below (was 44.0% / 22/50 / 28
> insufficient). Same bug found in every subsequent run through v6 — see
> `RAG_Benchmark_Report_v6.md` for the full finding. **The category breakdown table below (§2) has
> not been re-audited against the raw per-query archive and may contain independent, unrelated
> inaccuracies — found while correcting this, not yet resolved.** Treat table cell counts there
> with caution until that's separately verified.

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

| Category | Answered | Insufficient | Avg Latency |
| :--- | :--- | :--- | :--- |
| **NIST AI RMF / CSF 2.0** | 3/8 | 5/8 | 4.12s |
| **ISO 27001 / 42001** | 4/7 | 3/7 | 3.85s |
| **EU AI Act / OWASP** | 3/8 | 5/8 | 3.45s |
| **GDPR / Privacy** | 2/5 | 3/5 | 3.10s |
| **TPRM / Third Party** | 1/5 | 4/5 | 5.20s (Peak) |
| **GRC Engineering / Audit** | 5/7 | 2/7 | 2.85s (Fastest) |
| **Emerging AI Risks** | 4/10 | 6/10 | 3.50s |

---

## 3. Findings & Retrieval Dead Zones

### 🔍 **Retrieval Strengths**
- **GRC Engineering**: The system excelled at queries related to ITGCs, Three Lines of Defense, and Audit Evidence (5/7 Answered).
- **ISO 27001 Core**: Successfully retrieved Annex A.5.7 and Context of Organization details.

### ⚠️ **The "Generalization" Gap (Dead Zones)**
- **NIST AI RMF depth**: While the system knows the functions (Govern, Map, etc.), it struggled with specific core outcomes and implementation levels.
- **TPRM Specifics**: High "Insufficient Data" on vendor assessment strategies, suggesting the knowledge base contains brochures rather than deep procedural manuals for TPRM.
- **EU AI Act Complexity**: Failed to provide substantive details on target-human transparency, likely due to document fragmentation in the vault.

---

## 4. Optimization Roadmap for Week 2

1. **Context Expansion (k-increase)**: Increase `k` from 3 to 5 in `rag.py` to provide more chunk-density to the LLM.
2. **Chunk Re-tuning**: The current 600-char chunk size may be truncating complex framework definitions. Recommend testing 1000-char chunks for framework-heavy corridors.
3. **Structured Meta-Data**: Ingest a "Golden Mapping" spreadsheet of Framework -> Control ID to bypass fuzzy vector retrieval for known compliance IDs.

---
> [!NOTE]
> **Full Results:** A detailed JSON breakdown of every query, latency, and answer is available in [rag_benchmark_results.json](file:///c:/Users/efosb/OneDrive/Desktop/GRC%20Inspector/GRC_Command_Center/rag_benchmark_results.json).
