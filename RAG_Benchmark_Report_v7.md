# RAG Benchmark v7 — First Groq-era measurement (`openai/gpt-oss-120b`)

**Run date:** 2026-08-17 · **Result: 90.0% (45/50)** · avg latency **16.86s** · 0 system errors
**Archive:** `rag_benchmark_results.v7_groq_gptoss120b.json`
**One variable changed:** the generation model. Corpus, chunking, embeddings, re-ranker, `k`, golden
mappings and the prompt are all untouched since v6.

## Why this run exists, and what it is not

The 92% from v6 was measured against **Gemini 2.5 Flash**. The 2026-08-13 Groq migration verified
`/chat` worked but never re-ran the suite, so no Groq-era number has ever existed. Then Groq retired
`llama-3.3-70b-versatile` entirely (see `RAG_Model_Outage_refactor.md`) — so this is not a
re-measurement of v6 and not a measurement of the migration's intended model either. **It is the first
real Groq-era data point, on Groq's own designated successor model.**

## Trajectory

| Version | Change | Accuracy | Avg latency |
| --- | --- | --- | --- |
| v1 | Baseline (SQLite era) | 42% | — |
| v2 | k=5→10, 1000-char chunks | 70% | — |
| v3 | Corpus repair | 76% | — |
| v4 | Corpus expanded (158 docs) | 80% | — |
| v5 | Cross-encoder re-ranker | 84% | — |
| v6 | Golden Mapping (Gemini 2.5 Flash) | **92%** | 6.6s |
| **v7** | **Model → `openai/gpt-oss-120b`** | **90%** | **16.86s** |

All figures post-scorer-correction (see `RAG_Benchmark_Report_v6.md` §3a).

## Headline: accuracy essentially held — but the behaviour changed more than the number suggests

**92% → 90% is a single query.** On a 50-query suite that is well inside noise, and the honest reading
is "the model swap did not cost meaningful accuracy." But the *composition* of the failures churned
substantially, and that is the more interesting finding:

| | Query | v6 (Gemini) | v7 (gpt-oss) |
| --- | --- | --- | --- |
| **Still failing** | #6 CSF 2.0 Tier 1–4 levels | ❌ | ❌ |
| | #50 CISA booklet | ❌ | ❌ |
| **Recovered** | #36 NIST CSF ↔ ISO 27001 gap assessment | ❌ (confirmed **hallucination**) | ✅ |
| | #45 AI-agent compliance benefits | ❌ (prompt too conservative) | ✅ |
| **Newly failing** | #4 "List the core outcomes of the GOVERN function" | ✅ | ❌ (2 sources retrieved) |
| | #12 "List the mandatory documentation for ISO 27001" | ✅ | ❌ (6 sources retrieved) |
| | #18 "Explain the OWASP Top 10 for LLMs" | ✅ | ❌ (1 source retrieved) |

The two persistent failures are exactly the two with documented, non-model root causes — #6 is a
structured-content extraction gap (the corpus names the tiers but never defines them) and #50's source
is absent from the corpus entirely. Those staying put across a model change is a good sign that the
diagnosis was right.

**#36 recovering matters.** Under Gemini it was a confirmed hallucination — the model invented a gap
assessment. gpt-oss now answers it from context. That is a quality improvement the accuracy number
does not show.

## The real finding: a behavioural shift on enumeration queries

All three new failures are **"list/enumerate" questions, and all three refused *despite* successful
retrieval** (2, 6 and 1 sources returned respectively). Retrieval is not the problem — the model
chose `INSUFFICIENT_DATA` where Gemini answered.

The plausible reading is that **`gpt-oss-120b` is stricter about completeness**: asked to *list the
mandatory documentation* or *list the core outcomes*, it appears to refuse when it cannot enumerate
the full set from context, where Gemini would return a partial list and score as ANSWERED.

That is arguably **better auditor behaviour** — a half-answer to "list the mandatory documentation for
certification" is worse than an honest refusal, and this project has repeatedly chosen honesty over
plausible-looking output. But it costs benchmark points, and the benchmark's binary
ANSWERED/INSUFFICIENT_DATA scorer cannot tell "correctly refused an under-supported question" from
"failed."

### Correction: #18 is NOT a retrieval regression — investigated the same session

This report originally flagged #18 ("retrieves only 1 source") as a probable retrieval regression and
the most actionable follow-up. **That was wrong, and the investigation inverted the conclusion.**
Recorded here rather than quietly amended.

Dumping the actual reranked chunks (retrieval only, no LLM call) shows #18's retrieval is the
*strongest* in the whole comparison:

- All 10 chunks come from the correct document (`OWASP Top 10 for LLM Applications 2025.pdf`) — the
  "1 source" figure is the **deduplicated file count**, not a thin result. It means retrieval was
  perfectly concentrated on the right file.
- Its rerank scores are the highest of any query tested — **8.56 / 7.75 / 7.74 / 7.34** versus **5.58**
  for a control query on the same document that answers correctly.
- 7,491 characters of context were supplied.

**The model refused correctly.** Of the 10 chunks: two are front-matter ("Letter from the Project
Leads", "Moving Forward"), three are scenario fragments, one is a 147-char stub of MITRE ATLAS links,
one is a 137-char appendix header, one is **520 characters of pure mojibake** (a sponsors page whose
glyphs extracted as `˯뾽˯뾽…qīďþÐÆĴĮķĨĨďīĴÐīĮ`), and only **two contain actual Top-10 entries**
(LLM08 and LLM10). Asked to explain a list of ten, the context contains two of them. There is no
honest way to answer, and `INSUFFICIENT_DATA` is the correct output.

**#4 shows the identical shape.** "List the core outcomes of the GOVERN function" retrieves two
`Table 1 … (Continued)` fragments containing GOVERN 1.5 and GOVERN 4.2 — two arbitrary subcategories
out of ~19 — plus the List of Tables index. Again: a partial list would be wrong; refusing is right.

### The real root cause, and it is not new

**1000-character chunking shatters multi-page enumerations.** Tables and top-N lists that span pages
(AI RMF Table 1, the OWASP Top 10, ISO 27001's mandatory-documentation list) cannot survive intact in
any single chunk, so a "list/explain the whole thing" query retrieves scattered fragments no matter
how good the ranking is. Neither a larger `k` nor a better re-ranker fixes this — the complete answer
does not exist in any retrievable unit.

This is **the same root cause already documented for #6** ("CSF tiers table — structured-content
extraction gap; names the tiers but never defines them", `MEMORY.md`). So #6, #4, #12 and #18 are
**one problem, not four.**

Which reframes the headline: **Gemini masked this defect by confabulating partial answers that scored
ANSWERED; `gpt-oss-120b` surfaces it by refusing.** Part of the 92% → 90% "drop" is the new model
being more honest about a corpus/chunking limitation that was always there.

### Two concrete, separable follow-ups

1. **Golden Mapping is the established fix for exactly this.** It already solved the EU AI Act cluster
   (#16/#19/#49) by supplying hand-curated, source-cited canonical context for known compliance
   identifiers, bypassing fuzzy retrieval. The OWASP Top 10 list, AI RMF's GOVERN subcategories and
   ISO 27001's mandatory-documentation list are precisely that kind of stable, enumerable, citable
   content. This is the highest-value next lever on RAG accuracy.
2. **The pipeline has no minimum-content or quality filter before re-ranking.** In #18 roughly 30% of
   the 10-chunk context budget went to a mojibake sponsors page and two sub-150-character stubs. A
   cheap length threshold plus a non-ASCII-ratio guard would reclaim those slots for real content, and
   would help every query, not just enumerations. (The mojibake is the same class of PDF-extraction
   defect already documented for `EU AI ACT 2024_Doc.pdf`.)

## Latency: 6.6s → 16.86s (2.6x), and probably not the model's fault

The slowdown is real and worth recording, but the cause is **not yet established**. Two observations
argue against "gpt-oss-120b is simply slower":

1. **Isolated calls to this model are fast.** Direct API calls made during model selection returned in
   **1.0–1.3s** (see `RAG_Model_Outage_refactor.md`'s comparison table).
2. **The first three queries in this run were fast, then latency jumped.** #1 3.03s, #2 4.69s,
   #3 4.00s — then #4 23.46s, and the run stays in the 13–28s band from there.

That shape is characteristic of **free-tier rate limiting / queueing**, not per-token cost. It matches
the Postscript concern raised before this run: 50 sequential queries against a free hosted tier.

**Not investigated further this session** — it would need a controlled test (e.g. the same 50 queries
paced with deliberate delays, or a run on a paid tier) and that is a separate exercise. Recorded as a
hypothesis, not a conclusion. **Do not quote "gpt-oss-120b is 2.6x slower" as fact** until that test
exists.

Practical note: `active-auditor` (4 sequential RAG queries) measured **31s** immediately after the
model swap — consistent with the fast, unthrottled end of the range, not the 16.86s average.

## Three answers with zero retrieved sources

Queries **#35, #39 and #45** were scored ANSWERED with `sources_count: 0` — the model produced an
answer with no citable retrieved context. That is the signature of unguarded generation, and #36 under
Gemini was a confirmed hallucination of exactly this kind.

**Not resolved here.** Confirming whether these are hallucinations needs the calibrated judge in
`validate_diagnostic.py` — which is **still pinned to the dead Gemini key** and non-functional (open
item since 2026-08-13). Flagged, not diagnosed. Worth noting the prompt instructs the model to answer
*only* from context, so a zero-source answer is a prompt-compliance question regardless of whether the
content happens to be correct.

## Open items from this run

1. **Golden Mapping entries for the enumeration queries** (#4, #6, #12, #18) — one root cause, one
   established fix, highest-value next lever on accuracy. ~~#18's retrieval collapse~~ — investigated
   and disproved, see the correction above.
2. **A minimum-content / quality filter before re-ranking** — ~30% of #18's context budget was
   mojibake and sub-150-char stubs.
3. **Establish whether the latency is rate limiting** before treating it as a model property.
4. **Migrate `diagnose_rag.py` / `validate_diagnostic.py` off Gemini** — without them the three
   zero-source answers cannot be classified. This has now blocked analysis twice.
5. **The binary scorer no longer fits the model's behaviour.** It cannot distinguish a *correct
   refusal on an under-served question* from a failure — and this run shows that distinction is now
   load-bearing: #4/#12/#18 are all correct refusals scored as failures, while Gemini's confabulated
   partial answers scored as passes. The metric currently rewards the less honest model.
