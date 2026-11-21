# RAG Benchmark v13 — EU AI Act golden reference texts corrected against the Regulation

**Status: run done 2026-11-21; checklist verdict A (every pre-registered error gone, 3 of 3).
One owner decision open (D5, below): whether two new 1-of-3 errors trigger the pre-registered
revert.** Recommended: no revert.

**Run date:** 2026-11-21 (Saturday) · subset run, **not an accuracy figure** · 15/15 calls, 0 errors

**Archive:** `rag_benchmark_repeats_v13_after.json` (`subset: true`, `valid_full_run: false`)
**Draft:** `docs/refactors/Golden_Reference_Correction_refactor.md` (§6 pre-registered checklist,
§10–§11 execution record)
**What changed since v12 — one thing:** the `canonical_context` and `citations` of the three EU AI
Act golden entries (`EU_AI_ACT_RISK_TIERS`, `EU_AI_ACT_GPAI_GENERATIVE`, `EU_AI_ACT_OPEN_SOURCE`)
were rewritten against Regulation (EU) 2024/1689, and every entry gained a `verified` record
(executed 2026-11-15, PR #8 → #9). No trigger, prompt, retrieval setting, index or model change.

**Do not quote any percentage from this run.** The figure to cite stays *"42% → 92%"* (v8). #19
and #49 are ungraded, so this correctness fix can't move a score, by design.

## The run

**Pre-flight (draft §7 step 5):** checkout = `origin/main` (`ef50974`); repo and container
`golden_mappings.json` SHA-256 both **`eb4c6411…`**; readiness 6/6 (audit chain 6/6 intact, PII
redaction active); Groq probe **999/1000** requests left, 89 tokens (≈ 6 days after the last Groq
call). Of 17 running containers, only `mufasa_backend` holds a Groq variable besides `grc-backend`
(variable names checked, no values printed); a new container, `gravity_backend`, holds none.

**Run:** `GRC_BENCH_ONLY=16,19,49,17,21`, `GRC_BENCH_REPEAT=3`, `GRC_BENCH_LABEL=v13_after`, dev
stack, launched detached 14:12:54 EST, done ≈ 14:20. **15/15 calls, 0 errors, 0 401s, 0 429s.**
Model `openai/gpt-oss-120b`, temperature 0.7 (library default), 22 s pacing. Latency 4.7–7.0 s,
except the first call (47.6 s: the embedding model's first load after the container's start).

**Golden context, from this run's `audit_logs` (rows 529–543), draft §7 step 6:** identical to
v12. #16, #19, #49 and #21 got one EU AI Act block each, #17 got two (risk tiers + GPAI). Each
logged context contains the **corrected** text (marker phrases from §4.1 present: "AI Office and,
as appropriate", "three separate open-source rules", "only "high-risk" is the").

## Result against the pre-registered checklist (draft §6)

Every answer was read in full against the checklist and, where an answer said something new,
against the Regulation's text (`GRC_Analyst/EU AI ACT 2024_Doc.pdf`, local `pypdf`, PDF page
numbers). Before = v12, where each error was present in **3 of 3** samples.

| Question | Error that should be gone | v13 after: s1 · s2 · s3 | Rule | Result |
| --- | --- | --- | --- | --- |
| #19 | incidents reported "to the Commission" | AI Office · AI Office · AI Office | gone in ≥ 2/3 | **Fixed 3/3** |
| #19 | three baseline GPAI duties | four · four · four (53(1)(a)–(d)) | ≥ 2/3 | **Fixed 3/3** |
| #19 | "does not name generative AI" with no recital caveat | caveat given (recitals 99, 105) · not claimed · not claimed | ≥ 2/3 | **Fixed 3/3** (s1 wording nit below) |
| #19 | no Art. 50(2) marking duty | present · present · present | ≥ 2/3 | **Fixed 3/3** |
| #49 | exemption lost through "systemic risk", Art. 5/50 missing | Art. 2(12) with high-risk, Art. 5, Art. 50 in all three | ≥ 2/3 | **Fixed 3/3** in the body (s2's summary re-merges, below) |
| #49 | copyright policy / training summary not kept | kept · kept · kept (53(1)(c)–(d)) | ≥ 2/3 | **Fixed 3/3** |
| #49 | exemption attributed to "Article 51" | absent · absent · absent | ≥ 2/3 | **Fixed 3/3** |
| #16 | regression guard: COMPLETE (4/4) | COMPLETE · COMPLETE · COMPLETE | ≥ 2/3 | **Holds 3/3** |
| #17, #21 | any *new* error from the longer cards | see "New errors" | reported | 1 of 3 in #17 (below) |

**Checklist verdict: outcome A.** Every error the 11-15 audit found in the cards, and that v12's
answers repeated 3 of 3, is gone in 3 of 3. It confirms v12's conclusion: the cards were the
source. Bonus, not on the checklist: #16 s3 now says on its own that only "high-risk" is the
Regulation's term, and all three #19 answers list Art. 55(1)(b) (systemic-risk assessment at Union
level), which the old card omitted.

## New errors the corrected cards did not contain (all 1 of 3)

The model sometimes elaborates beyond the card. Each item below was checked against the
Regulation and was **not** in any v12 sample of the same question.

| Where | The answer says | The Regulation says | Card's role |
| --- | --- | --- | --- |
| #17 s1 | high-risk systems need "a conformity assessment **by a notified body** (Article 43)" | **Art. 43(2)** (p78): for Annex III points 2–8, the procedure is *"internal control … which does not provide for the involvement of a notified body"* | The card says "undergo conformity assessment (Article 43)", accurate but silent on who performs it |
| #17 s1 | only systems that "adhere to the associated compliance requirements are considered high-risk" | Classification (Art. 6) decides high-risk; compliance is the consequence, not a condition | none |
| #16 s3 | all high-risk systems "undergo **third-party** conformity assessment" | Third-party assessment is the Art. 6(1) / Annex I route; Annex III mostly internal control (Art. 43(2)) | Card mentions "third-party" only for 6(1); the model generalised it |
| #19 s2 | the chatbot is a general-purpose AI system "**because it can generate text**" | **Art. 3(66)** (p50): based on a GPAI model *and* "has the capability to serve a variety of purposes" | none |
| #49 s3 | the copyright policy governs "**reuse of the model and its outputs**" | **Art. 53(1)(c)**: a policy to comply with Union copyright law, in particular rights reservations under Art. 4(3) of Directive 2019/790 | none |
| #49 s3 | copyright policy, training summary and "monitoring downstream use" are "mandatory for **all** open-source AI releases" | 53(1)(c)–(d) bind **GPAI model** providers; open AI systems under Art. 2(12) are outside the Regulation; no monitoring duty | none |
| #49 s2 | summary: exemptions hold "only when … not high-risk, do not pose systemic risk, and are not monetised" | Body is right; the summary drops Art. 5/50 and merges the systemic-risk rule (GPAI models) back into the AI-system rule | none; the old error's shape, in a summary line only |

Wording nit, not counted: #19 s1 says "the Act does not use the term" then cites the recitals that
do. Recitals are part of the Act; the card says "articles".

**Pattern:** the pre-registered errors were faithful copies of the card. These are different: the
model paraphrasing a correct card more broadly than the source, once per question, at temperature
0.7. That is the same family as #12's invented item, and the queued **list-only / stay-within-source
instruction (now v15)** is the matching fix, not another card edit.

## D5 — owner decision: does the pre-registered revert apply?

The draft's outcome C reads: *"#16 drops, or #17/#21 gain an error that wasn't there. Revert (§9)
and rethink."* #16 didn't drop (3/3). #17 gained an error in **1 of 3** samples (notified body).
The pre-registration set no threshold for C, while every other row uses **≥ 2 of 3**, the
project's standing rule that single-sample flips at temperature 0.7 are leads, not effects.

- **(a) Recommended: keep v13; treat the 1-of-3 items as leads.** Reverting would put back 15
  verified errors that appeared in 3 of 3 samples to remove one that appeared in 1 of 3. Queue a
  separate, one-variable precision edit to the risk-tiers card ("conformity assessment under
  Article 43: for most Annex III systems, internal control without a notified body, Art. 43(2);
  third-party assessment for Annex I products under their own legislation") with its own draft
  and run, and carry the other items into the v15 list-only measurement.
- **(b) Apply C literally:** `git revert` the v13 data change, rebuild, rethink.

Either way, the pre-registration's C row should say "in ≥ 2 of 3" in future drafts, so this
question can't come up again.

## Found on the way: a pre-existing #21 error (not this change's variable)

Every #21 answer since v12 (9 of 9: v12 before ×3, full run, after ×2; v13 ×3) lists **€1,500,000**
and **€750,000** as general AI Act fines, under labels like "general non-compliance" or (v13 s1)
"GDPR-related AI infringements". In the Regulation these are **Art. 100(2)–(3)** (p117): fines the
**European Data Protection Supervisor** may impose on **Union institutions, bodies, offices and
agencies**. Also missing from all nine: **Art. 99(5)** (p116), up to **€7,500,000 or 1 %** for
supplying incorrect, incomplete or misleading information to notified bodies or authorities. #21
gets the GPAI card, which says nothing about fines, so this comes from the retrieved chunks and the
model, not the card. Proposed, not decided: a penalties golden entry (Art. 99(3)–(6), 100, 101,
tier-1-verified) or a retrieval look at why the Art. 100 chunk outranks Art. 99(5). One variable,
own draft, after v14.

## What the result means

- **Quotable:** *"An audit of the system's 'verified reference' cards against the EU AI Act found
  15 errors in three of them, and the answers copied every one. After correcting the cards against
  the Regulation, all of those errors disappeared from every re-sampled answer. Reading the answers
  closely also showed what the fix can't do: the model still occasionally over-generalises beyond a
  correct source, which is the next thing to measure."*
- No percentage moves: #19, #49, #17 and #21 are ungraded; #16 was already COMPLETE.

## Next

1. **Owner:** D5 (a) or (b).
2. If (a): the risk-tiers precision edit (own draft, no Groq to write it; weekend run).
3. Then, as queued: **v14** GDPR PDF re-extract + re-ingest; **v15** list-only instruction (also
   measures this report's 1-of-3 elaborations); #21 penalties and #49 grader check (D3) after that.
