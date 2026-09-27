# Golden Mapping for the enumeration queries (#4, #18, #26) — Draft

**Status:** 📝 DRAFT (2026-09-27) — awaiting EXECUTE. Draft-first per `GOVERNANCE.md`.
**Change type:** **data only** — three new entries in `backend/data/golden_mappings.json`. No code
change: the matching and injection logic in `core/rag.py` (`_match_golden_mappings`, threshold
0.70) is reused exactly as shipped in `Golden_Mapping_refactor.md` (v6).
**Token cost of this draft: zero.** All trigger testing below ran locally, in the backend container,
with the app's own embedding model (`all-MiniLM-L6-v2`). Measuring the effect needs one benchmark
run (≈ one day's Groq budget) — v9.

---

## Why these queries

The v8 re-grade (`rag_grading.py`) shows the list-type ("enumeration") queries are the weak spot:

| Query | v8 grade | Cause |
| --- | --- | --- |
| #4 GOVERN outcomes (NIST AI RMF) | INCOMPLETE 4/6 — misses GOVERN 3 and 6 | the six categories span 3 PDF pages of a table; 1000-char chunks split them |
| #18 OWASP Top 10 for LLMs | WRONG_REFUSAL | 1 source retrieved; list spans 2 pages (v7 report §Correction) |
| #26 GDPR seven principles | WRONG_REFUSAL | see the new finding below |
| #12 ISO 27001 mandatory documents | INCOMPLETE 0/11 | **no official source in the corpus** — excluded, see Decision 1 |

## New finding — the official GDPR PDF has a damaged text layer

`GDPR_Regulation_Text.pdf` (the official Regulation (EU) 2016/679 text) extracts with words broken
apart. This is Article 5 exactly as the index sees it (PDF p. 35):

```text
Pr inciples relating to processing of personal dat a
(a) … (‘lawfulness, fa ir ness and transparency’);
(b) collect ed f or specified, explicit and legitimate pur poses … (‘pur pose limitation’);
```

A sample across the document found ~700 split-word pairs in ~7,200 words (~1 in 10). Search can't
match words it can't see whole. **This revises the 2026-09-26 diagnosis of #26**, which attributed
it to the enumeration/chunking weakness alone: the damaged text is at least a contributing cause —
which one dominates is not proven. It is the same defect class already recorded for
`EU AI ACT 2024_Doc.pdf` in `Golden_Mapping_refactor.md`. Golden Mapping works around it for #26;
the underlying fix (re-extract or replace the PDF, then re-ingest) is **out of scope** — Decision 3.

---

## Guarding against "teaching to the test"

These are benchmark questions, so a mapping could simply memorise the answer key. Two rules:

1. **No trigger contains the benchmark question's wording.** (Asserted in the test script.) The
   three existing v6 entries *do* use the exact benchmark text as a trigger — see Decision 2.
2. **Each entry must also fire for rewordings, and must not fire for any other benchmark query.**

### Test results (2026-09-27, zero tokens)

| Entry | Benchmark query matches? | Reworded questions | False matches (other 49 queries) | Nearest other query |
| --- | --- | --- | --- | --- |
| `NIST_AI_RMF_GOVERN` | ✅ 0.888 | ✅ 0.766, 0.971 | none | 0.633 (#15) |
| `OWASP_LLM_TOP10_2025` | ✅ 0.737 | ✅ 0.977, 0.857 | none | 0.493 (#19) |
| `GDPR_ART5_PRINCIPLES` | ✅ 0.760 | ✅ 0.813, 0.925 | none | 0.653 (#24) |

**How we got there — iteration was needed, and is disclosed.** First-round GOVERN triggers were too
generic: they falsely matched #1 (0.895), #2 and #16 — any AI RMF or EU AI Act question would have
had the GOVERN list injected. First-round OWASP triggers missed the benchmark query (0.602). A
candidate pool was then scored one trigger at a time; the sets above are the result.
**Caveat:** the two rewordings per entry were used during that selection, so they are a
*validation* set, not an untouched test. At EXECUTE time, verify against the **fresh rewordings**
below, written now and never used for tuning:

| Entry | Fresh test rewordings (must all score ≥ 0.70; no benchmark query other than the target may) |
| --- | --- |
| GOVERN | "Which governance categories does NIST define for AI risk management?" · "Break down the Govern function of AI RMF 1.0." |
| OWASP | "What are the top LLM security risks according to OWASP?" · "Walk me through OWASP's LLM Top 10 list." |
| GDPR | "What are the core data processing principles under GDPR Article 5?" · "Which principles must personal data processing follow under the GDPR?" |

If a fresh rewording fails, the honest outcome is to report it, not to add it as a trigger.

---

## The proposed entries

Each `canonical_context` is taken from the official document in the corpus, with PDF page
references. OWASP is limited to the official item titles (the only text verified verbatim).

```json
{
  "id": "NIST_AI_RMF_GOVERN",
  "framework": "NIST AI RMF 1.0",
  "trigger_phrases": [
    "What categories make up the Govern function in NIST AI RMF 1.0?",
    "What must organisations put in place under the AI RMF Govern function?",
    "NIST AI RMF Govern function categories GOVERN 1 to GOVERN 6"
  ],
  "canonical_context": "NIST AI 100-1 (AI RMF 1.0), Table 1, defines six categories under the GOVERN function. GOVERN 1: Policies, processes, procedures, and practices across the organization related to the mapping, measuring, and managing of AI risks are in place, transparent, and implemented effectively. GOVERN 2: Accountability structures are in place so that the appropriate teams and individuals are empowered, responsible, and trained for mapping, measuring, and managing AI risks. GOVERN 3: Workforce diversity, equity, inclusion, and accessibility processes are prioritized in the mapping, measuring, and managing of AI risks throughout the lifecycle. GOVERN 4: Organizational teams are committed to a culture that considers and communicates AI risk. GOVERN 5: Processes are in place for robust engagement with relevant AI actors. GOVERN 6: Policies and procedures are in place to address AI risks and benefits arising from third-party software and data and other supply chain issues.",
  "citations": [
    {"section": "Table 1 — GOVERN 1, 2", "pdf_pages": "27–28"},
    {"section": "Table 1 — GOVERN 3, 4", "pdf_pages": "28–29"},
    {"section": "Table 1 — GOVERN 5, 6", "pdf_pages": "29"}
  ],
  "source_file": "AI RMF 1.0.pdf"
}
```

```json
{
  "id": "OWASP_LLM_TOP10_2025",
  "framework": "OWASP Top 10 for LLM Applications 2025",
  "trigger_phrases": [
    "What is the OWASP Top 10 for LLM applications?",
    "OWASP top ten large language model risks",
    "OWASP Top 10 risks for generative AI and LLM applications",
    "Which vulnerabilities does OWASP list for LLM apps?"
  ],
  "canonical_context": "The OWASP Top 10 for LLM Applications 2025 lists: LLM01:2025 Prompt Injection; LLM02:2025 Sensitive Information Disclosure; LLM03:2025 Supply Chain; LLM04:2025 Data and Model Poisoning; LLM05:2025 Improper Output Handling; LLM06:2025 Excessive Agency; LLM07:2025 System Prompt Leakage; LLM08:2025 Vector and Embedding Weaknesses; LLM09:2025 Misinformation; LLM10:2025 Unbounded Consumption.",
  "citations": [
    {"section": "Table of contents — LLM01–LLM05", "pdf_pages": "3"},
    {"section": "Table of contents — LLM06–LLM10", "pdf_pages": "4"}
  ],
  "source_file": "OWASP Top 10 for LLM Applications 2025.pdf"
}
```

```json
{
  "id": "GDPR_ART5_PRINCIPLES",
  "framework": "GDPR",
  "trigger_phrases": [
    "What are the data protection principles in Article 5 of the GDPR?",
    "Which principles relating to processing of personal data does GDPR set out?",
    "GDPR lawfulness fairness transparency purpose limitation data minimisation principles"
  ],
  "canonical_context": "GDPR (Regulation (EU) 2016/679) Article 5, 'Principles relating to processing of personal data'. Article 5(1): personal data shall be (a) processed lawfully, fairly and in a transparent manner in relation to the data subject ('lawfulness, fairness and transparency'); (b) collected for specified, explicit and legitimate purposes and not further processed in a manner that is incompatible with those purposes ('purpose limitation'); (c) adequate, relevant and limited to what is necessary in relation to the purposes for which they are processed ('data minimisation'); (d) accurate and, where necessary, kept up to date ('accuracy'); (e) kept in a form which permits identification of data subjects for no longer than is necessary for the purposes for which the personal data are processed ('storage limitation'); (f) processed in a manner that ensures appropriate security of the personal data, including protection against unauthorised or unlawful processing and against accidental loss, destruction or damage, using appropriate technical or organisational measures ('integrity and confidentiality'). Article 5(2): the controller shall be responsible for, and be able to demonstrate compliance with, paragraph 1 ('accountability').",
  "citations": [
    {"article": "Article 5(1)(a)–(d)", "pdf_pages": "35"},
    {"article": "Article 5(1)(e)–(f), 5(2)", "pdf_pages": "36"}
  ],
  "source_file": "GDPR_Regulation_Text.pdf"
}
```

The GDPR text is the official wording with the extraction damage removed; (b), (d) and (e) are
shortened at a clause boundary — each principle and its official name are verbatim.

---

## Decisions for Efosa

1. **#12 (ISO 27001 mandatory documents) — excluded; no official source.** The only matching
   corpus file, `iso 27001mandstory documentation.pdf`, is marketing material from a consultancy
   (cyveer.com). The standard itself is a paid ISO publication. Under the official-sources-only
   rule there is nothing to cite. Options: **(a, recommended)** leave #12 unmapped and accept it as
   a known limit; (b) purchase ISO/IEC 27001:2022 and add it to the corpus (one change, one run);
   (c) relax the rule for this one entry — not recommended; it is exactly what the rule prevents.
2. **The three existing v6 entries use the benchmark's exact wording as a trigger.** That inflates
   #16, #19 and #49 by design. Options: **(a, recommended)** a follow-up change that removes the
   exact-wording triggers and re-tests them the way this draft does — separate run, so it doesn't
   muddy v9's attribution; (b) leave as-is and note it in every report. *Not bundled here.*
3. **GDPR text-layer damage** — log it as its own item (re-extract or replace the PDF, re-ingest
   ~36.5 min, then benchmark). Worth doing because the damage affects every GDPR query, not just
   #26. *Not bundled here.*

## Verification plan after EXECUTE

1. Validate the JSON loads, then **rebuild** the backend — `backend/data/` is baked into the image,
   not bind-mounted (HANDOFF note): `docker compose -f docker-compose-v2.yml up -d --build backend`.
2. Re-run the zero-token trigger test inside the container, including the fresh rewordings above.
3. pytest (expect 65/65) and smoke (44/44) — smoke costs ~9k Groq tokens; not on the benchmark day.
4. **v9 benchmark** on a fresh Groq day, detached. Success = #4, #18, #26 graded `COMPLETE` and
   **no other query's grade changes** (all three entries have zero false matches, so any other
   change is noise, and gets reported as such). Archive as
   `rag_benchmark_results.v9_golden_enumerations.json`; report both legacy and graded scores.
   Label the three as **mapping-attributed** in the report — a lookup table answering them is a
   real product feature, but it must never be presented as retrieval improving.
