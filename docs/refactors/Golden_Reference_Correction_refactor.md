# Golden reference correction: fix the EU AI Act entries and audit every entry against tier-1 text

**Status: DRAFT, awaiting the owner's review and EXECUTE** (GOVERNANCE.md §A). Drafted Sunday
2026-11-15, right after v12 closed (`RAG_Benchmark_Report_v12.md` "Final verdict"). Writing it used
no Groq. **Proposed run: Saturday 2026-11-21** (subset only, ~50k tokens; §6).

## 0. In plain English

The system keeps seven hand-written "verified reference" answers. When a question matches one, the
answer is put in front of the model, labelled *verified reference*, and the model trusts it. v12
showed two of them were wrong about the EU AI Act, and the model repeated the mistakes in every one
of its answers (6 of 6 samples for each question). It's like a reference librarian handing out a
summary card with a typo in the article number: everyone who reads the card copies the typo.

This draft does three things:

1. **Audits all seven cards** against the official text in the system's own library (tier 1 only,
   per the workspace's order-of-trust rule). Result: **three need correcting (all EU AI Act), one is
   accurate but cut short (GDPR), three are correct (NIST AI RMF, OWASP, ISO 27001).**
2. **Rewrites the three EU AI Act cards**, each claim tied to an article and a PDF page, and gives
   every card a written record of when and against what it was checked, so "verified" means
   something checkable.
3. **Measures the fix** with the same repeat-sampling method v12 used, against a checklist of the
   specific errors written down *before* the run.

**What changes for a user of the app:** questions about the EU AI Act's risk tiers, generative AI
and open source get answers that match the Regulation. Nothing else changes: no code, no prompt, no
retrieval setting, no trigger phrase. It's a data-file change plus tests.

---

## 1. How the audit was done

- **Source:** the same files the system ingests, in `GRC_Analyst/` (each entry's `source_file`):
  `EU AI ACT 2024_Doc.pdf` (Regulation (EU) 2024/1689, OJ L 12.7.2024), `AI RMF 1.0.pdf` (NIST AI
  100-1), `OWASP Top 10 for LLM Applications 2025.pdf`, `GDPR_Regulation_Text.pdf` (Regulation (EU)
  2016/679, OJ L 119), `ISO 27001-2022 BookLet.pdf`.
- **Method:** text extracted locally with `pypdf` 6.5.0 (no network, no Groq); every claim in every
  entry searched in the text and read in context. **Page numbers below are PDF page numbers**, the
  convention the entries already use (`pdf_pages`).
- **Rule applied:** the official text is the authority. A claim that is a common summary but not in
  the text is labelled as a summary, not stated as the Regulation's words.

## 2. Audit results

| Entry | Fires on | Verdict | What's wrong |
| --- | --- | --- | --- |
| `EU_AI_ACT_RISK_TIERS` | #16, #17 | **Needs correction** | 3 errors (§3.1) |
| `EU_AI_ACT_GPAI_GENERATIVE` | #19, #17, #21 | **Needs correction** | 7 errors (§3.2) |
| `EU_AI_ACT_OPEN_SOURCE` | #49 | **Needs correction** | fuses three different rules into one; 5 errors (§3.3) |
| `GDPR_ART5_PRINCIPLES` | #26 | Accurate, abridged | omits qualifiers in 5(1)(b), (d), (e) without marking the cut (§3.4; decision D2) |
| `NIST_AI_RMF_GOVERN` | #4 | **Verified, no change** | all six category texts match Table 1 word for word; pages 27–29 correct |
| `OWASP_LLM_TOP10_2025` | #18 | **Verified, no change** | all ten names and numbers match; 15 descriptive claims spot-checked (e.g. "imperceptible to humans", RAG/fine-tuning "do not fully mitigate", system prompt "should not be considered a secret, nor … a security control", Denial of Wallet, model theft); description pages 7–39 correct |
| `ISO27001_DOCUMENTED_INFO` | #12 | **Verified, no change** | all 14 clause references carry a documented-information requirement where stated; pages 8–16 correct. Nuance, not an error: 6.1.3 e) says *formulate* a risk treatment plan; the documented-information duty sits on the treatment *process* (6.1.3) and *results* (8.3) |

("Fires on" was measured offline today in `grc-backend` with the live embedding model and the
0.70 threshold, no Groq. Highest similarity per entry: #16 → RISK_TIERS 0.891; #17 → RISK_TIERS
0.878 + GPAI 0.758; #19 → GPAI 0.792; #21 → GPAI 0.718 (RISK_TIERS 0.699, a near miss); #49 →
OPEN_SOURCE 0.836 (GPAI 0.697, a near miss). These match the entry counts in v12's `audit_logs`.)

## 3. The findings, entry by entry

### 3.1 `EU_AI_ACT_RISK_TIERS`

| # | The card says | The Regulation says | Where |
| --- | --- | --- | --- |
| R1 | Article 5 is in "Title II" | Article 5 is in **Chapter II**. "Titles" were the 2021 proposal's structure; the adopted Regulation uses Chapters. | p51 |
| R2 | Limited-risk systems include tasks of a "narrow and limited nature" posing only limited risk (under Art. 50) | That phrase is **recital 53**, explaining **Art. 6(3)**: how an Annex III system can fall *out of* the high-risk class (e.g. "a narrow procedural task", 6(3)(a)). Nothing to do with Art. 50. | p14, p54 |
| R3 | Art. 50 citation titled "Transparency obligations for certain AI systems" | "Transparency obligations for **providers and deployers of** certain AI systems" | p82 |

Also stated more carefully in the new text: "limited risk" and "minimal risk" don't appear in the
Regulation at all (searched: 0 hits for either); they are the usual summary. The card already says
there is no single list; it now says which words are the Regulation's. "Minimal risk = no
obligations" is avoided on purpose: **Art. 4 (AI literacy) applies to all providers and deployers**
(p51).

### 3.2 `EU_AI_ACT_GPAI_GENERATIVE`

| # | The card says | The Regulation says | Where |
| --- | --- | --- | --- |
| G1 | The Act "does not name … 'generative AI' directly" | True of the articles only. **Recital 99:** "Large generative AI models are a typical example for a general-purpose AI model"; **recital 105** likewise. | p26, p27 |
| G2 | Baseline duties: documentation, copyright policy, training summary (three) | **Four** (Art. 53(1)): (a) technical documentation for the AI Office and national authorities; **(b) information and documentation for providers who integrate the model**; (c) copyright policy; (d) public training-content summary | p84 |
| G3 | Systemic-risk duties: evaluation, adversarial testing, incident reporting, cybersecurity | Art. 55(1) has four points, and adversarial testing is *part of* (a) evaluation. The card **omits (b): assess and mitigate possible systemic risks at Union level**. | p86 |
| G4 | Incidents reported "to the Commission" | "to the **AI Office** and, as appropriate, to national competent authorities" (55(1)(c)) | p86 |
| G5 | (silent) | **Art. 50(2):** providers of systems generating synthetic audio, image, video or text must mark outputs, machine-readable, as artificially generated. The most direct "generative AI" rule. | p82 |
| G6 | ChatGPT is regulated as a GPAI *model* | The **model** is a GPAI model (Art. 3(63)); the **chatbot** is an AI system, a "general-purpose AI system" (Art. 3(66)), which carries Art. 50(1): tell people they are interacting with an AI system. | p50, p82 |
| G7 | Citation "Articles 52–56: GPAI provider obligations" | Obligations are **Art. 53 and 55**. Art. 52 is the classification procedure, 54 authorised representatives, 56 codes of practice. | p83–86 |

Kept, because correct: Art. 51 classification; the compute condition, now stated exactly
(presumed high-impact above **10^25 floating-point operations**, Art. 51(2), p83).

### 3.3 `EU_AI_ACT_OPEN_SOURCE`

The card merges three rules that apply to different things:

| Rule | Applies to | What it says | Where |
| --- | --- | --- | --- |
| **Art. 2(12)** | AI **systems** | The Regulation doesn't apply to AI systems under free and open-source licences, *"unless they are placed on the market or put into service as high-risk AI systems or as an AI system that falls under Article 5 or 50"* | p46 |
| **Art. 53(2), 54(6)** | GPAI **models** | Open models (licence allows access, use, modification, distribution; weights, architecture and usage information public) are exempt from 53(1)(a) and (b) and from appointing an authorised representative (Art. 54). **Not** exempt from (c) copyright policy or (d) training summary. No exemption at all for models with systemic risk. | p85–86 |
| **Art. 25(4)** + recital 89 | Third-party **tools, services, processes, components other than GPAI models** | Not required to sign the written supply agreement with high-risk providers. Recital 89 *encourages* model cards and data sheets. | p67, p24 |

| # | The card says | The Regulation says |
| --- | --- | --- |
| O1 | The exemption is lost by high-risk systems **or GPAI models with systemic risk** | For AI systems (2(12)): lost by high-risk, **Art. 5** or **Art. 50** systems. "Systemic risk" belongs to the GPAI-model rule (53(2)). |
| O2 | Outside those categories, open-source AI is outside "several"/"most" obligations | For GPAI models, only (a) and (b) are lifted; **copyright policy and training summary still apply** (53(2); recital 104 explains why). |
| O3 | "Tools, services, processes, or components … encouraged to adopt model cards and datasheets" as the general rule | That's Art. 25(4)/recital 89, which **excludes GPAI models** and is about value-chain agreements, not the Regulation's scope. |
| O4 | Citation "Recital (whitepaper preamble)" | Recitals 89 and 102–104; the binding rules are Art. 2(12), 25(4), 53(2), 54(6). |
| O5 | Citation "Article 51: GPAI systemic-risk carve-out from the exemption" | Art. 51 *classifies* systemic-risk models; the carve-out is the last sentence of **53(2)** (and of 54(6)). This misplaced citation is what the model turned into "according to Article 51, … are excluded" in both 11-15 samples. |

Not added (judgement): recital 103's point that **monetised** components don't benefit from the
open-source exceptions is included as one sentence, labelled as a recital, because it's the usual
follow-up question.

### 3.4 `GDPR_ART5_PRINCIPLES` (accurate, abridged)

Every word present matches Art. 5 (pp35–36). Three qualifiers are dropped with no ellipsis: 5(1)(b)
*further processing for archiving, scientific or historical research or statistical purposes is not
incompatible* (Art. 89(1)); 5(1)(d) *every reasonable step must be taken to erase or rectify
inaccurate data without delay*; 5(1)(e) *longer storage for those Art. 89(1) purposes*. Not an error
a reader would repeat as a false fact, so **not part of this change** (decision D2).

## 4. The change (data only)

### 4.1 New `canonical_context` texts

**`EU_AI_ACT_RISK_TIERS`:**

> The EU AI Act (Regulation (EU) 2024/1689) has no single list of four risk categories.
> "Unacceptable, high, limited and minimal risk" is a common summary of four separate parts of the
> Regulation; of those labels, only "high-risk" is the Regulation's own term. (1) Unacceptable risk:
> Article 5, "Prohibited AI practices" (Chapter II), practices banned outright, for example
> subliminal, manipulative or deceptive techniques (Article 5(1)(a)) and social scoring (Article
> 5(1)(c)). (2) High risk: Article 6, "Classification rules for high-risk AI systems": AI that is a
> safety component of, or itself, a product under the legislation in Annex I that needs third-party
> conformity assessment (Article 6(1)), or AI used in the areas listed in Annex III (Article 6(2)).
> High-risk systems must meet the requirements of Chapter III, Section 2 (risk management, data
> governance, technical documentation, record-keeping, transparency to deployers, human oversight,
> accuracy, robustness and cybersecurity) and undergo conformity assessment (Article 43). Under
> Article 6(3), an Annex III system is not high-risk if it poses no significant risk of harm, for
> example because it performs a narrow procedural task. (3) Limited risk: Article 50, "Transparency
> obligations for providers and deployers of certain AI systems": people must be told they are
> interacting with an AI system (Article 50(1)), synthetic audio, image, video or text must be
> marked as artificially generated (Article 50(2)), and deep fakes must be disclosed (Article
> 50(4)). (4) Minimal risk: all other AI systems, with no obligations tied to a risk class; Article
> 95 encourages voluntary codes of conduct, and the AI literacy duty in Article 4 applies to all
> providers and deployers.

**`EU_AI_ACT_GPAI_GENERATIVE`:**

> The EU AI Act's articles don't use the term "generative AI", but its recitals do: recital 99 calls
> large generative AI models a typical example of a general-purpose AI model (see also recital 105).
> The model behind a chatbot like ChatGPT is a "general-purpose AI model" (Article 3(63)), regulated
> in Chapter V (Articles 51 to 56); the chatbot built on it is an AI system, a "general-purpose AI
> system" (Article 3(66)). Every provider of a general-purpose AI model must (Article 53(1)): (a)
> draw up and keep up to date technical documentation of the model, to provide on request to the AI
> Office and national competent authorities; (b) draw up, keep up to date and make available
> information and documentation to providers of AI systems who intend to integrate the model; (c)
> put in place a policy to comply with Union copyright law, including identifying and complying with
> rights reservations under Article 4(3) of Directive (EU) 2019/790; (d) draw up and make publicly
> available a sufficiently detailed summary of the content used for training, using the AI Office's
> template. A model is a general-purpose AI model with systemic risk if it has high-impact
> capabilities or the Commission designates it (Article 51(1)); high-impact capabilities are presumed
> when the cumulative training compute exceeds 10^25 floating-point operations (Article 51(2)).
> Providers of those models must also (Article 55(1)): (a) perform model evaluation, including
> conducting and documenting adversarial testing; (b) assess and mitigate possible systemic risks at
> Union level; (c) keep track of, document and report serious incidents and possible corrective
> measures without undue delay to the AI Office and, as appropriate, national competent authorities;
> (d) ensure adequate cybersecurity protection for the model and its physical infrastructure. The AI
> system itself also carries transparency duties under Article 50: providers must make sure people
> are told they are interacting with an AI system (Article 50(1)), and providers of AI systems,
> including general-purpose AI systems, that generate synthetic audio, image, video or text must mark
> the outputs in a machine-readable format as artificially generated or manipulated (Article 50(2)).

**`EU_AI_ACT_OPEN_SOURCE`:**

> The EU AI Act has three separate open-source rules, not one exemption. (1) AI systems, Article
> 2(12): the Regulation does not apply to AI systems released under free and open-source licences,
> unless they are placed on the market or put into service as high-risk AI systems or as an AI system
> that falls under Article 5 (prohibited practices) or Article 50 (transparency obligations). (2)
> General-purpose AI models, Articles 53(2) and 54(6): a provider whose model is released under a
> free and open-source licence that allows access, usage, modification and distribution, and whose
> parameters, including the weights, the model architecture information and the model usage
> information are publicly available, is exempt from the technical-documentation duty (Article
> 53(1)(a)), the duty to inform downstream providers (Article 53(1)(b)) and the duty to appoint an
> authorised representative (Article 54). The provider must still put in place a copyright policy
> (Article 53(1)(c)) and publish the training-content summary (Article 53(1)(d)). These exceptions do
> not apply to general-purpose AI models with systemic risk. (3) The AI value chain, Article 25(4):
> third parties that make tools, services, processes or components other than general-purpose AI
> models available to the public under a free and open-source licence don't have to sign the written
> agreement that suppliers to high-risk AI providers otherwise need; recital 89 encourages them to
> use documentation practices such as model cards and data sheets. Recital 103 adds that AI
> components provided against a price or otherwise monetised don't benefit from the open-source
> exceptions.

### 4.2 New `citations` arrays

- **RISK_TIERS:** Art. 5 "Prohibited AI practices" (Chapter II, p51); Art. 6 / Annex I / Annex III
  (p53–54, incl. 6(3) p54); Art. 43 "Conformity assessment" (p78); Art. 50 "Transparency obligations
  for providers and deployers of certain AI systems" (p82); Art. 95 "Codes of conduct for voluntary
  application of specific requirements" (p113); Art. 4 "AI literacy" (p51).
- **GPAI_GENERATIVE:** Recitals 99, 105 (p26–27); Art. 3(63), 3(66) (p50); Art. 50(1)–(2) (p82);
  Art. 51 (p83); Art. 53(1) (p84); Art. 55(1) (p86).
- **OPEN_SOURCE:** Art. 2(12) (p46); Art. 25(4) (p67); Art. 53(2) (p85); Art. 54(6) (p86); Recitals
  89 (p24), 103–104 (p27).

### 4.3 A verification record on every entry (all seven)

New key, ignored by `rag.py` (it reads only `trigger_phrases`, `framework`, `canonical_context`):

```json
"verified": {
  "against": "EU AI ACT 2024_Doc.pdf",
  "on": "2026-11-15",
  "method": "tier-1 text, claim by claim; pdf page numbers",
  "draft": "docs/refactors/Golden_Reference_Correction_refactor.md"
}
```

NIST, OWASP and ISO get the record with no text change. GDPR gets it with `"note": "abridged; see
draft §3.4"` unless D2 says otherwise.

**Unchanged:** every `trigger_phrases` list (so v12's guard tests stay green and the same questions
fire), `rag.py`, the prompt, the index, the model.

## 5. Tests first (red today)

New `backend/tests/test_golden_reference_accuracy.py`: pure unit tests on the JSON, no stack, no
Groq, pipeline-ready.

| Test | Checks | Today |
| --- | --- | --- |
| `test_every_entry_has_a_verification_record` | `verified.against` equals `source_file`, `on` is an ISO date | 🔴 7 |
| `test_eu_known_errors_are_gone` | none of: "Title II"; "narrow and limited nature"; "to the Commission" within the incident sentence; "does not name"; "Articles 52-56"; "Recital (whitepaper" | 🔴 6 |
| `test_open_source_names_the_real_exceptions` | `OPEN_SOURCE` mentions Article 2(12), Article 5, Article 50, 53(2), copyright, and doesn't cite Article 51 as the exemption's source | 🔴 |
| `test_gpai_lists_all_duties` | `GPAI_GENERATIVE` mentions 53(1)(a)–(d), 55(1)(a)–(d), "AI Office", Article 50(2) | 🔴 |
| `test_cited_pages_exist` | every `pdf_pages`/page in `citations` is within the source PDF's page count (count stored in the test, so it needs no PDF) | 🟢 expected (guards future edits) |

These pin *these* errors. They can't prove a card is right, which is what the human read in §3 is
for. They stop the known errors coming back.

## 6. Measuring it (pre-registered, written before the run)

**Before (already measured, current cards):** v12's three samples per question, the 11-08 full run
plus the 11-15 samples (`rag_benchmark_results.v12_no_benchmark_triggers.json`,
`rag_benchmark_repeats_v12_after.json`). No new "before" run is needed: nothing has changed since.

**After:** `GRC_BENCH_ONLY=16,19,49,17,21`, `GRC_BENCH_REPEAT=3`, label per D4. ~15 calls, ~50k
tokens, ~7 minutes. Fits one Saturday with room for a smoke run. **A full 50-question run isn't
needed:** triggers are unchanged, so the same 9 questions get golden context, and only the five
EU AI Act ones receive changed text.

**The checklist, read against each after-sample's answer text** (each error was present in 3 of 3
before):

| Question | Error that should be gone | Fixed if absent in |
| --- | --- | --- |
| #19 | incidents reported "to the Commission" | ≥ 2 of 3 |
| #19 | three baseline GPAI duties (should be four, or not counted wrongly) | ≥ 2 of 3 |
| #19 | "the Act does not name generative AI" stated as fact without the recital caveat | ≥ 2 of 3 |
| #19 | no mention of the Art. 50(2) marking duty | ≥ 2 of 3 |
| #49 | exemption lost through "systemic risk" for AI systems, with Art. 5/50 missing | ≥ 2 of 3 |
| #49 | copyright policy / training summary not kept for open GPAI models | ≥ 2 of 3 |
| #49 | the exemption attributed to "Article 51" | ≥ 2 of 3 |
| #16 | **regression guard:** still graded COMPLETE (4/4) | ≥ 2 of 3, else revert |
| #17, #21 | answered; read for any *new* error introduced by the longer cards | reported, not scored |

**Outcomes:**

- **A. Fixed:** every row passes. The cards were the source, as v12 concluded.
- **B. Partly fixed:** some errors persist although the card no longer contains them. Then the
  model or the retrieved chunks are a second source; recorded, and the next step is reading those
  chunks in `audit_logs`, not another card edit.
- **C. Regression:** #16 drops, or #17/#21 gain an error that wasn't there. Revert (§9) and rethink.

The citable figure stays **"42% → 92%"** whatever happens. This is a correctness fix the scorer
can't see (#19 and #49 are ungraded), so it won't move any percentage, and the report will say so.

## 7. Execution steps (on EXECUTE)

**Weekday, no Groq:**

1. Write §5's tests; run them: red as in the table.
2. Edit `backend/data/golden_mappings.json`: three texts, three citation arrays, seven `verified`
   records. Keep LF line endings (`.gitattributes` pins it).
3. §5 tests green; v12's `test_golden_mappings_hygiene.py` still green; full non-Groq pytest.
4. Rebuild both backends; container mapping SHA-256 = repo's; readiness 6/6. Record the hash.

**Saturday 11-21 (Groq):**

5. Pre-flight per HANDOFF "Running a benchmark": probe, readiness, hash, checkout = `origin/main`.
6. Subset run (§6). Then `audit_logs`: confirm each question received the same number of EU AI
   Act blocks as in §2 (triggers are unchanged, so it should).
7. Read every after-sample's answer against §6's checklist and the Regulation; write the report.

## 8. Decisions for the owner

- **D1. Approve the three corrected texts (§4.1).** Recommended: before approving, check **two
  claims yourself** in the PDF, for example Art. 2(12) on p46 and Art. 55(1)(c) on p86. It takes five
  minutes, and it's the same skill as an auditor re-performing a control instead of trusting the
  description.
- **D2. GDPR abridgement:** (a) leave it, with the `note`, and fix it alongside the GDPR PDF
  re-extract (the GDPR work, also #26); or (b) add the three qualifiers now. **Recommended: (a)**,
  so this change stays EU-AI-Act-only and its effect can't be confused with a GDPR change.
- **D3. Make #49 checkable** (add Art. 2(12)'s three exceptions to the grader's closed list).
  **Recommended: not in this change.** It changes the measuring tool; doing it in the same run makes
  it impossible to tell which change moved what. Queue it; old answers can be re-graded later at
  zero token cost with `scripts/rescore_benchmarks.py`.
- **D4. Version number.** This run happens before the GDPR re-extract and the list-only instruction
  that were queued as v13 and v14. **Recommended: call this v13 and move those to v14 and v15**, so
  version numbers follow run order. Report name: `RAG_Benchmark_Report_v13.md`; label `v13_after`.

## 9. Rollback

`git revert` and a backend rebuild. Data only; no schema, no state.
