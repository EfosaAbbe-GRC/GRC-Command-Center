# RAG Benchmark v12 — Benchmark questions removed from golden-mapping triggers

**Status: PROVISIONAL.** This is "after, sample 1" of v12's pre-registered 3-v-3 design
(`docs/refactors/Golden_Mapping_Leakage_v12_refactor.md` §6). The final verdict needs the after
samples (#16, #19, #49, #17, #21 × 2), now scheduled for **Saturday 2026-11-14**.

**Run date:** 2026-11-08 · **Legacy: 96.0% (48/50) · Graded: 96.0% (48/50, checkable 8/10)** ·
avg latency **5.5s** · 0 system errors

**Archive:** `rag_benchmark_results.v12_no_benchmark_triggers.json`
**What changed since v11 — one thing:** three trigger phrases that were word-for-word copies of
benchmark questions #16, #19 and #49 were deleted from `backend/data/golden_mappings.json`
(`ae9db7b`, PR #4). Each entry keeps its paraphrased triggers (3 / 3 / 2). Verified, not assumed:
the running container's mapping file is byte-identical to the repo's (SHA-256 `597b6908…`), and
`git diff` between the checkout and `origin/main` is empty. No change to `rag.py`, the prompt, the
index (145 files / 16,998 chunks) or the model since v11 (§9 of the draft).

**Do not quote 96% as accuracy.** The figure to cite stays *"42% → 92%"* (v8).

## The run

Pre-flight: Groq RPD probe **999/1000** (17:29 EST, ≈ 7 days after the last Groq call); readiness
6/6 (audit chain 5/5 intact, PII redaction active); only `grc-backend` among the 13 running
containers holds a Groq variable. Launched detached 17:29:43, finished ≈ 17:52 (~23 min at 22 s
pacing). Two mid-run re-logins, **zero 401s, zero 429s, zero engine errors**. Model
`openai/gpt-oss-120b`, temperature 0.7 (library default, unchanged).

## Result against the pre-registered outcomes (§5)

**Every one of the 50 queries has the same outcome and grade as v11.** No flips.

Which golden entries fired, from this run's own `audit_logs` (50 rows, 22:30–22:52 UTC): **the same
9 questions as v11** (#4, #12, #16, #17, #18, #19, #21, #26, #49). So all three targets still
receive the EU AI Act reference text, now through a paraphrased trigger. Similarity measured
offline in the backend container with the same embedding model (threshold 0.70):

| Query | Matched through (paraphrased trigger) | Cosine | Outcome (§5) |
| --- | --- | --- | --- |
| #16 risk categories | "What are the risk tiers under the EU AI Act?" | 0.891 | **C** — still fires; graded COMPLETE 4/4 |
| #19 generative AI | "EU AI Act ChatGPT GPT-4 generative AI regulation" | 0.792 | **C** — still fires; answered |
| #49 open source | "Are open-source AI models exempt from the EU AI Act?" | 0.836 | **C** — still fires; answered |

Outcome C, as pre-registered: *the leak is closed; the entry legitimately matches a reworded
question, which is its job; a pass, footnoted.* The copied triggers were redundant. Each question
sits well above the threshold through a paraphrase, so their removal changed nothing measurable.
(Near miss noted: #49 also scores 0.697 against `EU_AI_ACT_GPAI_GENERATIVE`, just under 0.70.)

**Provisional verdict:** the passes on #16/#19/#49 did not depend on the copies (no outcome B). The
3-v-3 rule still applies before this is final.

## Reading the answer text: a new finding the grade can't see

Per §7 step 4, the full answers to #16, #19 and #49 were read and checked against the official text
(`GRC_Analyst/EU AI ACT 2024_Doc.pdf`, Regulation (EU) 2024/1689, OJ L 12.7.2024).

**#16** is graded objectively (all four tiers present). Fine.

**#19 and #49 are ungraded, and both reproduce errors that sit in the golden mapping's own
"verified reference" text.** The answers follow `canonical_context` nearly line by line, so the
errors come from the mapping, not from the model:

| Entry | Claim in the "verified reference" (and the answer) | What the Regulation says |
| --- | --- | --- |
| `EU_AI_ACT_OPEN_SOURCE` (#49) | The open-source exemption is lost only if the system is high-risk **or a GPAI model with systemic risk** | **Art. 2(12):** the Regulation doesn't apply to AI systems under free and open-source licences *"unless they are placed on the market or put into service as high-risk AI systems or as an AI system that falls under Article 5 or 50"*. Prohibited practices (Art. 5) and transparency duties (Art. 50) are missing; "systemic risk" belongs to a different rule (below). |
| same | Open-source models outside those categories are outside "most" obligations | **Art. 53(2)** (GPAI models): the open-source exception covers only **points (a) and (b)** of Art. 53(1). The copyright policy (c) and the public training-content summary (d) **still apply**, and the exception doesn't apply to GPAI models with systemic risk. The mapping merges Art. 2(12) and Art. 53(2) into one rule. |
| `EU_AI_ACT_GPAI_GENERATIVE` (#19) | The Act "does not name … 'generative AI' directly" | Recitals **(99)** and **(105)** name "large generative AI models". True only of the articles. |
| same | Baseline GPAI duties = documentation, copyright policy, training summary | Art. 53(1) has **four**: (b), information and documentation for downstream providers, is missing. |
| same | Incident reporting "to the Commission" | **Art. 55(1)(c):** *"to the AI Office and, as appropriate, to national competent authorities"*. |
| same | (silent) | **Art. 50(2):** providers of systems generating synthetic audio, image, video or text must mark the output as artificially generated: the most direct "generative AI" rule, absent. |

**Why this matters more than the v12 question itself:** v12 asked whether the golden mappings
inflated the score by matching benchmark wording. They didn't. But the mapping text is labelled
**"verified reference"** in the model's context, and two of the three EU AI Act entries weren't
verified against the Regulation. The model trusts it, so the error is reproduced confidently, with
article numbers, and the ungraded scorer counts it as a pass. It's the same family as #12's invented
item (v9 onward): an answer that reads authoritative and isn't.

**Nothing is changed today.** The pre-registered rule holds: no retrieval, prompt, index or mapping
change until the after samples (2026-11-14). The fix is a separate, one-variable change after that.
Proposed, not decided: (1) correct the two entries against the Regulation, citing article and
paragraph; (2) audit the other golden entries (NIST AI RMF Govern, ISO 27001 documents, OWASP LLM
Top 10, GDPR principles, EU AI Act risk tiers) the same way, since none had a recorded line-by-line
check against tier-1 text; (3) consider adding #49's Art. 2(12) exceptions as a checkable grade so
this can't pass silently again.

## What the number means

- **Legacy 96% (48/50)** = answered without refusing, identical to v11.
- **Graded 96% (48/50)** = legacy, plus #36 and #50 as correct refusals, minus #12 (invented item)
  and #39 (incomplete), all as in v11. 40 of 50 answers remain unchecked, and this run shows two of
  them carry errors. Not an accuracy figure.
- **Quotable:** *"I found three benchmark questions copied into the system's reference lookups,
  removed them, and confirmed the passes didn't depend on them. Reading the answers against the
  regulation then showed the reference text itself had errors, which the score couldn't see."*

Re-grading every archive with the current grader (`benchmark_regrade_2026-11-08.json`) leaves
v1–v11 unchanged.

## Next

1. **Sat 2026-11-14:** after samples (5 × 2, `GRC_BENCH_LABEL=v12_after`) → final 3-v-3 verdict.
2. **Then:** the golden-mapping content correction above, as its own draft and EXECUTE.
3. v13 (GDPR PDF re-extract) and v14 (list-only instruction) as decided 2026-10-12; #39's wording
   question waits behind them.
