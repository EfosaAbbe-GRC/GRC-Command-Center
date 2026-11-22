# Risk-tiers card: say who carries out the conformity assessment (v13.1)

**Status: EXECUTED 2026-11-22 (owner: "Execute"; E1–E3 as recommended), steps 1–5 done (§9); Groq run waits for the merge.** Drafted 2026-11-21 (GOVERNANCE.md §A). Comes from
owner decision **D5 (a)** on 2026-11-21 ("I go with A. Draft the card fix"): keep v13, and fix
the one card gap behind v13's conformity-assessment slips as its own one-variable change.
Parent: `Golden_Reference_Correction_refactor.md` (v13). Evidence: `RAG_Benchmark_Report_v13.md`,
"New errors". Built shift-left: the finding first, a failing test before the change, the outcome
rules (with thresholds on every row) before the run.

## 0. In plain English

v13 fixed the EU AI Act cards, and the answers stopped copying the old errors. But in 2 of the 6
answers that received the risk-tiers card, the model said something the card doesn't say: that
*every* high-risk AI system is checked by an outside body ("a notified body", "third-party
conformity assessment"). The Regulation says the opposite for most of them: for seven of the eight
Annex III areas, the provider checks its own system (internal control), with no outside body.

The card isn't wrong, it's **silent**. It mentions "third-party conformity assessment" once, as
part of the test for whether a product-safety AI is high-risk, and later says high-risk systems
"undergo conformity assessment (Article 43)" without saying who does it. The model fills the gap
with the only "who" it was given. It's like a form that says "must be inspected" on one line and
"inspected by a licensed inspector" on an unrelated line above: readers assume the inspector does
every inspection.

**The fix:** replace that one sentence with four that say, from Article 43 itself, who carries out
the assessment on each route. Data only: no code, prompt, trigger or retrieval change.

**What changes for a user of the app:** questions about high-risk AI or the risk tiers (#16, #17)
get the conformity-assessment routes right. Nothing else changes.

## 1. The finding (from the v13 run, 2026-11-21)

| Sample | The answer says | Card's role |
| --- | --- | --- |
| #17 s1 | high-risk systems need "a conformity assessment **by a notified body** (Article 43)" | card: "undergo conformity assessment (Article 43)", silent on who |
| #16 s3 | all high-risk systems "undergo **third-party** conformity assessment" | card says "third-party" only for the Art. 6(1) classification test |

Same error family, **2 of the 6** v13 samples that received this card (#16 ×3, #17 ×3). It was in
**none** of v12's samples of #16 or #17 (checked in the v13 report). v13 made the high-risk part of
the card more detailed (the Chapter III, Section 2 list next to "conformity assessment"), which may
be why the gap now shows; that is a guess, not a measured cause.

## 2. What the Regulation says (tier 1, checked 2026-11-21)

Source: `GRC_Analyst/EU AI ACT 2024_Doc.pdf` (Regulation (EU) 2024/1689, OJ L 12.7.2024), text
extracted locally with `pypdf`, read in context. PDF page numbers, as the cards use.

| Rule | Text | Page |
| --- | --- | --- |
| **Art. 43(2)** | For Annex III **points 2 to 8**, providers "shall follow the conformity assessment procedure based on internal control as referred to in Annex VI, **which does not provide for the involvement of a notified body**." | p78 |
| **Art. 43(1)** | For Annex III **point 1** (biometrics): where the provider has applied harmonised standards (Art. 40) or, where applicable, common specifications (Art. 41), it opts for either internal control (Annex VI) or the Annex VII procedure "with the involvement of a notified body". It must follow Annex VII where it hasn't applied them (standards don't exist, applied only in part, a restricted standard). | p78 |
| **Art. 43(3)** | For high-risk systems covered by the Union harmonisation legislation in **Section A of Annex I**, the provider "shall follow the relevant conformity assessment procedure as required under those legal acts"; the Section 2 requirements become part of that assessment. | p78 |
| **Art. 6(1)(b)** | The third-party assessment is a **classification condition** for Annex I products: the product "is required to undergo a third-party conformity assessment … pursuant to the Union harmonisation legislation listed in Annex I." | p53 |
| **Art. 16(f)** | Providers shall "ensure that the high-risk AI system undergoes the relevant conformity assessment procedure as referred to in Article 43, prior to its being placed on the market or put into service". | p62 |
| **Annex III, point 1** | "Biometrics, in so far as their use is permitted under relevant Union or national law" | p127 |

Not added (judgement, to keep one variable and a short card): Art. 43(1)'s market-surveillance
authority acting as notified body for law-enforcement, migration and Union-institution systems;
Art. 43(4) re-assessment after substantial modification; Art. 43(6) (the Commission may move points
2–8 to Annex VII by delegated act). Accurate, but they are follow-up questions, and every extra
clause is one more thing the model can over-generalise.

## 3. The change (data only)

**One entry:** `EU_AI_ACT_RISK_TIERS` in `backend/data/golden_mappings.json`. Everything else in
the file stays byte-identical.

### 3.1 `canonical_context`: one sentence replaced

**Today:**

> High-risk systems must meet the requirements of Chapter III, Section 2 (risk management, data
> governance, technical documentation, record-keeping, transparency to deployers, human oversight,
> accuracy, robustness and cybersecurity) and undergo conformity assessment (Article 43).

**New:**

> High-risk systems must meet the requirements of Chapter III, Section 2 (risk management, data
> governance, technical documentation, record-keeping, transparency to deployers, human oversight,
> accuracy, robustness and cybersecurity), and the provider must ensure the system undergoes the
> relevant conformity assessment procedure under Article 43 before it is placed on the market or
> put into service (Article 16(f)). Who carries out that assessment depends on the system. For the
> Annex III areas in points 2 to 8, the procedure is internal control (Annex VI), which does not
> involve a notified body (Article 43(2)). For biometric systems (Annex III, point 1), the provider
> may choose internal control if it has applied harmonised standards or, where applicable, common
> specifications; otherwise it must follow the Annex VII procedure, which involves a notified body
> (Article 43(1)). For products covered by the legislation in Section A of Annex I, the provider
> follows the conformity assessment procedure those acts require (Article 43(3)).

Every other sentence of the card is unchanged, including "needs third-party conformity assessment
(Article 6(1))": it is correct, and the new sentences now give it its contrast.

### 3.2 `citations`

- Art. 43 entry: article `"Article 43(1)–(3)"`, title "Conformity assessment", p78 (title and page
  unchanged).
- **Add** Art. 16(f), "Obligations of providers of high-risk AI systems", tier "High risk", p62.
- **Add** Annex III, point 1, "Biometrics", tier "High risk", p127.

### 3.3 `verified` record

`"on"` → the execution date; `"draft"` → this file. `against` and `method` unchanged.

**Unchanged:** `trigger_phrases` (so the same questions fire: #16 at 0.891, #17 at 0.878; #21's
0.699 stays a near miss), the other six entries, `rag.py`, the prompt, the index, the model.

**Length:** the card grows by about 90 words. #17 receives two cards (risk tiers + GPAI), so its
context grows too. A longer card could invite more elaboration elsewhere; §5's new-error row is
there to catch that.

## 4. Tests first (red today)

In `backend/tests/test_golden_reference_accuracy.py`:

| Test | Checks | Today |
| --- | --- | --- |
| `test_risk_tiers_says_who_performs_conformity_assessment` (new) | the risk-tiers text contains "article 43(1)", "article 43(2)", "article 43(3)", "internal control", "annex vi", "annex vii", "notified body", "article 16(f)" | 🔴 |
| `KNOWN_ERRORS` (one row added) | risk-tiers text doesn't contain "conformity assessment by a notified body" (v13 #17 s1's wording) | 🟢, a guard for future edits |
| existing 12 tests + v12's 4 hygiene tests | unchanged | 🟢, must stay green |

As with v13, these pin words, not truth: the §2 read is what makes the text right.

## 5. Measuring it (pre-registered, written before the run)

**Before (already measured, current card):** v13's samples, `rag_benchmark_repeats_v13_after.json`:
the error family in **2 of 6** (#16 s3, #17 s1).

**After:** `GRC_BENCH_ONLY=16,17`, `GRC_BENCH_REPEAT=5`, `GRC_BENCH_LABEL=v13_1_after`. 10 calls,
≈ 35k tokens, ≈ 4 minutes. Only #16 and #17 receive this card, so no other question can be
affected. Five samples rather than three (decision E2): the error showed up about once in three, so
three clean samples would happen by chance about 30% of the time even with no fix.

**The checklist.** Every row has a threshold (the lesson from v13's D5).

| # | Read in each after-sample | Rule | Meaning |
| --- | --- | --- | --- |
| 1 | conformity assessment stated as by a notified body / third-party **for high-risk systems in general** (pooled over #16 + #17, 10 samples) | **0 of 10** → fixed; **1 of 10** → lead, not shown; **≥ 2 of 10** → not fixed | at v13's rate (2 in 6), 10 clean samples would happen by chance about 2% of the time |
| 2 | where an answer names who does the assessment, it matches Art. 43 (internal control for Annex III points 2–8) | reported, not scored | tells us whether the new text is used, not just whether the error stopped |
| 3 | **regression guard:** #16 graded COMPLETE (4/4) | **≥ 4 of 5**, else revert (§8) | same bar as v13's ≥ 2 of 3, scaled to 5 |
| 4 | **new errors** about anything in the changed sentences (Art. 43, 16(f), Annex I/III routes), checked against §2 | the same new error in **≥ 2 of 5** samples of one question → revert; **1 of 5** → lead, reported | the threshold v13's outcome C was missing |
| 5 | v13's other #17 slip ("only systems that adhere to the requirements are high-risk") | reported, not scored | not this change's variable; belongs to v15 (list-only) |

**Outcomes:**

- **A. Fixed:** row 1 = 0 of 10, rows 3–4 hold. The silence in the card was the cause.
- **B. Not shown / not fixed:** row 1 = 1, or ≥ 2 of 10, with rows 3–4 holding. Keep the change
  anyway if row 2 shows the answers using the correct routes (the card is more accurate either way),
  and carry the remaining over-generalisation to v15.
- **C. Regression:** row 3 or row 4 trips its threshold. Revert (§8) and rethink.

The citable figure stays **"42% → 92%"**. #17 is ungraded and #16 was already COMPLETE, so no
percentage can move.

## 6. Execution steps (on EXECUTE)

**No Groq:**

1. Add §4's tests; run them: the new one red, everything else green.
2. Edit `golden_mappings.json` by script: only `EU_AI_ACT_RISK_TIERS`'s `canonical_context`,
   `citations` and `verified` change. The script checks: same 7 IDs in order, every
   `trigger_phrases` identical, the other six entries byte-identical, new text equal to §3.1 word
   for word. LF line endings (`.gitattributes`).
3. §4's tests green; full non-Groq pytest (expect 305 + 1 new = **306 passed**, same skips).
4. Rebuild both backends; container mapping SHA-256 = repo's; readiness 6/6. Record the hash.
5. Branch + PR (bot); the owner merges.

**Groq (weekend):**

6. Pre-flight per HANDOFF "Running a benchmark": probe, readiness, hash, checkout = `origin/main`.
7. Subset run (§5). Then `audit_logs`: #16 one block, #17 two, each containing the new sentence
   (marker: "does not involve a notified body").
8. Read all 10 answers against §5 and §2 → `RAG_Benchmark_Report_v13.1.md`.

**Timing:** steps 1–5 take about an hour and can be done today; step 6–8 can run **Sunday
2026-11-22** (Groq is weekend-only, the daily budget resets, and today's v13 run used about a
quarter of it). If the merge doesn't happen before Sunday, the run moves to the next weekend:
pre-flight requires the change to be on `origin/main`.

## 7. Decisions for the owner

- **E1. Approve the new text (§3.1) and citations (§3.2).** Recommended: check **Art. 43(2) on
  p78** yourself first. It's one paragraph, and it's the whole point of the change: an auditor
  re-performs the control instead of trusting the description.
- **E2. Five samples per question, not three** (§5). ≈ 35k tokens instead of ≈ 20k. **Recommended:
  five.** At a once-in-three error rate, three clean samples prove nothing.
- **E3. Name: v13.1** (label `v13_1_after`, report `RAG_Benchmark_Report_v13.1.md`).
  **Recommended**, so v14 (GDPR re-extract) and v15 (list-only instruction) keep the names they were
  given on 11-15 instead of being renumbered a second time.

## 8. Rollback

`git revert` of the data commit and a backend rebuild. Data only; no schema, no state. The v13
cards remain as they are on `main` today.

## 9. Execution record, part 1 (2026-11-22, owner's EXECUTE; no Groq)

1. **Red first.** §4's test added, plus the `KNOWN_ERRORS` row:
   `test_risk_tiers_says_who_performs_conformity_assessment` **red** on the old card; the other 17
   (12 v13 accuracy tests + the new guard row + v12's 4 hygiene tests) green.
2. **Data change** by script: only `EU_AI_ACT_RISK_TIERS` changed. Checked by the script: same 7
   IDs in order, every `trigger_phrases` identical, the other six entries identical, the card's text
   = old text with exactly the one sentence replaced; checked separately that §3.1's new text appears
   in the card word for word. Citations 6 → 8 (§3.2); `verified.on` 2026-11-22, `draft` → this
   file. LF line endings kept.
3. **Green.** All 18 card tests pass. Full pytest without the Groq Interview Simulator file (12
   tests): **307 passed, 6 skipped, 0 failed** (14 min, against the rebuilt test stack).
4. **Deployed.** The test stack had been stopped since 11-15; brought back up and rebuilt, dev
   backend rebuilt. Container `golden_mappings.json` SHA-256 = repo's, **`a45ad960…`**, on dev and
   test (was `eb4c6411…`); readiness 6/6 on both (audit chain 6/6, PII active).
5. **PR:** committed by the bot to PR #11's branch (docs + this change in one merge, to avoid a
   stacked PR). The run (§6 steps 6–8) needs it on `origin/main` first.
