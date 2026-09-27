# Golden Mapping for the enumeration queries (#4, #12, #18, #26) — Draft

**Status:** 📝 DRAFT (2026-09-27, revised same day) — awaiting EXECUTE. Draft-first per `GOVERNANCE.md`.
**Change type:** **data only** — ~~three~~ **four** new entries in `backend/data/golden_mappings.json`.

> **Revised 2026-09-27 — #12 is back in.** The first version excluded #12 claiming "no official
> ISO source in the corpus". **That was wrong.** Efosa asked for a check, and
> `GRC_Analyst/ISO 27001-2022 BookLet.pdf` is the **official ISO/IEC 27001:2022 (third edition,
> 2022-10)** — confirmed by content, not filename: the exact normative wording of 4.1, 6.1.3 d)
> and 7.5.1, the official title, "© ISO/IEC 2022", clauses 4–10 on PDF pp. 7–16, Annex A from
> p. 17, a clean text layer, no licensee watermark. The error: the first check searched filenames,
> found a consultancy PDF, and never opened the file named "BookLet". Decision 1 is corrected below. No code
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
| #12 ISO 27001 mandatory documents | INCOMPLETE 0/11 | ~~no official source in the corpus~~ the official standard **is** indexed, but never *lists* the documents — the requirements are scattered across ~14 clauses over 10 pages, so no chunk holds the list |

## New finding — the official GDPR PDF has a damaged text layer

`GDPR_Regulation_Text.pdf` (the official Regulation (EU) 2016/679 text) extracts with words broken
apart. This is Article 5 exactly as the index sees it (PDF p. 35):

```text
Pr inciples relating to processing of personal dat a
(a) … (‘lawfulness, fa ir ness and transparency’);
(b) collect ed f or specified, explicit and legitimate pur poses … (‘pur pose limitation’);
```

A sample across the document found ~700 split-word pairs in ~7,200 words (~1 in 10). Search can't
match words it can't see whole. Across the **entire** extracted text:

| Word | Appears intact | Appears broken |
| --- | --- | --- |
| "purpose" | **0** | 261 ("pur pose") |
| "Article" | **0** | 508 ("Ar ticle") |
| "principles" | **0** | 30 ("pr inciples") |
| "fairness" | **0** | 1 ("fa ir ness") |

As far as the index can tell, the GDPR never uses the word "purpose". For comparison, the ISO
27001 standard's text layer is clean — clause 4.1 extracts word-for-word. **This revises the 2026-09-26 diagnosis of #26**, which attributed
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
| `ISO27001_DOCUMENTED_INFO` | ✅ 0.863 | ✅ 0.794, 0.787 (+ 0.811, 0.740) | none — incl. the other ISO queries #9, #13, #14 | 0.538 (#13) |

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
| ISO 27001 | "What must be written down to meet ISO/IEC 27001 requirements?" · "Give me the list of required ISMS documents for ISO 27001:2022." *(The ISO entry's first two "fresh" rewordings were also scored during selection, so these are its new untouched set.)* |

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

```json
{
  "id": "ISO27001_DOCUMENTED_INFO",
  "framework": "ISO/IEC 27001:2022",
  "trigger_phrases": [
    "ISO 27001 mandatory documents and records",
    "Which documents are mandatory for ISO 27001 certification audits?",
    "What must an organisation document to be certified against ISO 27001?"
  ],
  "canonical_context": "ISO/IEC 27001:2022 (third edition, 2022-10) contains no single list of mandatory documents; its clauses require documented information in these places: 4.3 the ISMS scope; 5.2 the information security policy; 6.1.2 the information security risk assessment process; 6.1.3 the risk treatment process, including the Statement of Applicability (6.1.3 d) and the risk treatment plan (6.1.3 e); 6.2 the information security objectives; 7.2 evidence of competence; 7.5.1 b) any further documented information the organization determines is necessary for ISMS effectiveness; 8.1 documented information to the extent needed for confidence that processes are carried out as planned; 8.2 the results of information security risk assessments; 8.3 the results of risk treatment; 9.1 evidence of monitoring and measurement results; 9.2.2 evidence of the internal audit programme and audit results; 9.3.3 evidence of management review results; 10.2 evidence of nonconformities, actions taken and the results of corrective action.",
  "citations": [
    {"clause": "4.3, 5.2", "pdf_pages": "8–9"},
    {"clause": "6.1.2, 6.1.3 (d, e), 6.2", "pdf_pages": "10–11"},
    {"clause": "7.2, 7.5.1, 8.1", "pdf_pages": "12–13"},
    {"clause": "8.2, 8.3, 9.1", "pdf_pages": "14"},
    {"clause": "9.2.2, 9.3.3, 10.2", "pdf_pages": "15–16"}
  ],
  "source_file": "ISO 27001-2022 BookLet.pdf"
}
```

**Copyright safeguard (applies to this entry only).** ISO/IEC 27001 is a copyrighted, paid
standard, and `golden_mappings.json` lives in the **public** repo. So this entry **cites clause
numbers and paraphrases** what each clause requires, never quoting the standard's text. The other
three sources are freely reusable (NIST: US government work; GDPR: EU legislation; OWASP: open
licence, titles only). The standard's PDF itself stays in `GRC_Analyst/`, which is **not tracked**
by git — verified 2026-09-27; keep it that way.

---

## Decisions for Efosa

1. ~~**#12 (ISO 27001 mandatory documents) — excluded; no official source.**~~ **Corrected
   2026-09-27: resolved — no decision needed.** The official standard is in the corpus
   (`ISO 27001-2022 BookLet.pdf`) and #12 is now the fourth entry above. The consultancy PDF
   (`iso 27001mandstory documentation.pdf`, cyveer.com) is still not used as a source.
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
4. **v9 benchmark** on a fresh Groq day, detached. Success = #4, #12, #18, #26 graded `COMPLETE` and
   **no other query's grade changes** (all three entries have zero false matches, so any other
   change is noise, and gets reported as such). Archive as
   `rag_benchmark_results.v9_golden_enumerations.json`; report both legacy and graded scores.
   Label the four as **mapping-attributed** in the report — a lookup table answering them is a
   real product feature, but it must never be presented as retrieval improving.
