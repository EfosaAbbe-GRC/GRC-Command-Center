# Fix: RAG is dead (Groq retired the model) — and four layers of checks all reported green

**Status:** 📝 DRAFT — awaiting `EXECUTE` per `GOVERNANCE.md` §4.A.
**Found:** 2026-08-17, while warming the re-ranker to re-run `rag_benchmark.py` (the oldest open
item). The benchmark never ran — the warmup query came back empty and the investigation went sideways
into this.
**Files:** `backend/core/rag.py`, `backend/main.py`, `backend/tests/smoke_test.py`,
`backend/core/agent.py`
**Effort:** Part A is one line. Parts B–D are the reason nobody noticed for four days.

## Part 0 — what is actually broken

**`llama-3.3-70b-versatile` no longer exists on this Groq account.** Every RAG query returns:

```text
Error code: 404 - {'error': {'message': 'The model `llama-3.3-70b-versatile` does not exist
or you do not have access to it.', 'type': 'invalid_request_error', 'code': 'model_not_found'}}
```

`/chat` currently returns `{"response": "I encountered an error processing your request.", "sources": []}`.
Groq retired the model sometime after 2026-08-13 (it demonstrably worked that day — see
`LLM_Groq_Migration_2026-08-13.md`'s verification). **So the core feature of this project has been
dead for up to four days.**

Confirmed against the live account — no Llama family model remains:

```text
allam-2-7b · canopylabs/orpheus-* · groq/compound · groq/compound-mini
meta-llama/llama-prompt-guard-2-{22m,86m} · openai/gpt-oss-{20b,120b}
openai/gpt-oss-safeguard-20b · qwen/qwen3.6-27b · whisper-large-v3{,-turbo}
```

The two `llama-prompt-guard` entries are safety classifiers (512-token context), not chat models.

**One silver lining worth noting:** the `max_retries=2, timeout=30` bounds added on 2026-08-13 are
doing their job — this fails in ~5s instead of reproducing the 23-minute full-backend block. The
reliability fix held even though the provider moved underneath it.

## Part 0b — the genuinely alarming part: everything reported healthy

Four independent checks all passed while the core engine was returning 404 on every call.

| Check | What it said | Why it missed this |
| --- | --- | --- |
| `/readiness` | `overall: "ready"`, `llm_api_key: "Groq API key configured"` | only checks a key **string exists** — never that the model resolves |
| `smoke_test.py` | **43/43 passed**, twice today | its `/chat` check asserts only that the fields `response` and `sources` are *present* — an error string in `response` and `sources: []` satisfy it |
| `pytest` | 38/38 | doesn't cover `/chat` at all |
| `active-auditor` | see below | treats the error string as a valid answer |

And the worst one. Running `active-auditor` right now — the NIST AI RMF audit agent — returns:

```text
status:            success
msg:               NIST AI RMF Audit Complete — 4/4 core functions substantiated from corpus
findings_severity: LOW
evidence_cited:    False
sources:           0
first answer:      I encountered an error processing your request.
```

**It reports a clean audit — "4/4 core functions substantiated", severity LOW — having substantiated
nothing at all.** The handler's severity logic counts a function as *unsubstantiated* only when the
answer contains `INSUFFICIENT_DATA`; an error string contains no such marker, so all four errors count
as successes. `evidence_cited: False` and `sources: 0` are the only tells, and neither reaches the
headline or the severity.

For a compliance tool this is the worst possible failure mode. An agent that crashes is annoying; an
agent that issues a favourable audit opinion from a dead engine is the thing the whole discipline
exists to prevent. This is the same class as the fabricated Executive KPIs fixed hours ago — a
confident claim with nothing behind it — except here it is generated at runtime rather than
hardcoded.

## Part A — swap the model (restores the feature)

**Provenance — confirmed by the user 2026-08-17:** Groq sent advance notice that the Llama model was
being retired and named **`openai/gpt-oss-120b` as its designated replacement**. That was not known
when the candidates below were evaluated, so the recommendation and the provider's own migration path
were arrived at independently and agree. This makes Part A a documented provider migration rather
than a judgement call.

It also reframes what went wrong here. **The retirement was announced in advance; the outage was
foreseeable.** What actually failed is that nothing in the system noticed when it happened — which is
Parts B–D, and is the more valuable half of this fix.

Candidates were **tested against the real `PRODUCTION_PROMPT_TEMPLATE`**, not chosen from a
description, on the two behaviours the 50-query benchmark actually scores: answer *is* in context
(must answer) and answer is *not* in context (must emit `INSUFFICIENT_DATA`).

| Model | Answers from context | Refuses when absent | Latency | Verdict |
| --- | --- | --- | --- | --- |
| **`openai/gpt-oss-120b`** | ✅ | ✅ | 1.3s / 1.0s | **recommended** |
| `openai/gpt-oss-20b` | ✅ | ✅ | 1.9s / 1.1s | viable fallback |
| `qwen/qwen3.6-27b` | ❌ | ✅ | 3.4s / 1.9s | **disqualified** — see below |
| `groq/compound-mini` | ✅ | ✅ | 1.5s / 1.1s | works, but wrong tool |

```diff
--- a/backend/core/rag.py
+++ b/backend/core/rag.py
@@ def _init_chain(self):
-        model = ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=self.api_key,
-                          max_retries=2, timeout=30)
+        # llama-3.3-70b-versatile was retired by Groq between 2026-08-13 and 2026-08-17
+        # (404 model_not_found on every call). Replacement chosen by testing candidates
+        # against this module's own PRODUCTION_PROMPT_TEMPLATE -- see
+        # RAG_Model_Outage_refactor.md for the comparison.
+        model = ChatGroq(model="openai/gpt-oss-120b", groq_api_key=self.api_key,
+                          max_retries=2, timeout=30)
```

**Why `qwen/qwen3.6-27b` is disqualified, and why it matters beyond this choice:** it emits visible
`<think>…</think>` reasoning into its output. That would pollute every answer, and worse — its
reasoning block *quotes the prompt's own instructions*, so the string `INSUFFICIENT_DATA` appears in
the output **even when it answers correctly**. The benchmark's substring scorer would mark correct
answers as refusals. That is the exact scorer-fragility class already fixed once in this project (the
`.startswith` → substring change, 2026-08-05). A reasoning-leaking model would have silently corrupted
the very benchmark this session set out to run.

**Why not `groq/compound-mini`:** it passed both cases, but it is an agentic *system* with built-in
tool use (including web search), not a plain chat model. A RAG chain whose prompt says "ONLY based on
the provided context" must not have an independent path to outside information. Rejected on
architecture, not performance.

**Expect the benchmark number to move.** This is a different model family, not a like-for-like
restore. The Gemini-era 92% was never reproduced under Groq at all (the 2026-08-13 migration verified
`/chat` worked but never re-ran the suite), so the upcoming run is the **first real Groq-era data
point** — `v7`, not a re-measurement. It could land either side of 92%.

## Part B — make `/readiness` tell the truth

```diff
--- a/backend/main.py
+++ b/backend/main.py
@@ (readiness llm check)
-    # existing: presence-only check on the API key string
+    # A configured key proves nothing -- the model behind it can be retired out from
+    # under us (2026-08-17: llama-3.3-70b 404'd for four days while this said "ready").
+    # Validate that the configured model actually resolves.
```

Concretely: resolve the configured model against Groq's `/models` endpoint (a cheap GET, no
generation) and report `degraded` with the provider's own message when it is missing. Deliberately
**not** a full generation call — readiness is polled, and a 1-3s LLM call per poll is its own problem.
The model-list check catches exactly this failure (retired/renamed/no-access) at negligible cost.

## Part C — make the smoke test's `/chat` check mean something

```diff
--- a/backend/tests/smoke_test.py
+++ b/backend/tests/smoke_test.py
@@
     chat_result = test("Chat endpoint", "POST", f"{V1}/chat",
                        json_body={"query": "What is ISO 42001?"},
                        check_fields=["response", "sources"])
 
     if chat_result:
         response_text = chat_result.get("response", "")
+        # Field-presence alone is not a pass: an error string plus sources: [] satisfied
+        # this check for four days while every RAG query 404'd (2026-08-17).
+        if "error processing your request" in response_text.lower():
+            fail("Chat endpoint returned an error response — RAG generation is broken")
+        elif not chat_result.get("sources"):
+            fail("Chat endpoint cited zero sources — retrieval or generation is broken")
```

Same reasoning as the two false passes already recorded in `MEMORY.md` gotchas this week: a check that
asserts shape rather than substance reports green through total failure.

## Part D — stop `active-auditor` issuing audit opinions from errors

```diff
--- a/backend/core/agent.py
+++ b/backend/core/agent.py
@@ async def active_auditor_handler(args):
     for question in NIST_AI_RMF_AUDIT_QUESTIONS:
         result = await rag_engine.query(question)
         answer = result.get("answer", "")
         sources = result.get("sources", [])
         all_sources.update(sources)
-        if "INSUFFICIENT_DATA" in answer:
+        # An engine error is NOT an audit finding. Counting it as "substantiated"
+        # produced "4/4 core functions substantiated, severity LOW" against a dead
+        # LLM on 2026-08-17 -- a favourable opinion backed by nothing.
+        if not answer or "error processing your request" in answer.lower():
+            errored += 1
+        elif "INSUFFICIENT_DATA" in answer:
             unanswered += 1
```

…and when `errored > 0`, return `status: "error"` with an explicit message naming the engine failure,
rather than a severity rating. An audit that could not run must say so.

## Verification plan

1. Rebuild `grc-backend` on both stacks (backend-only change; prefer `up -d --build`).
2. `/readiness` → still `ready`, and now genuinely validated (then temporarily point the model at a
   bogus id to confirm it reports `degraded` — the negative test is the point of Part B).
3. Live `/chat` → a real ISO 42001 answer **with non-empty sources**.
4. `active-auditor` → real source-cited findings; and with a bogus model, `status: error` rather than
   "4/4 substantiated".
5. `smoke_test.py` → **43/43**, and confirm Part C's new assertions fail against a deliberately broken
   model (a check that cannot fail is the thing being fixed here).
6. `pytest` → **38/38**.
7. **Then the original task:** archive `rag_benchmark_results.json` → `.v7_groq_gptoss.json` per the
   benchmark convention, run `rag_benchmark.py`, and publish `RAG_Benchmark_Report_v7.md` with the
   trajectory table. Note the re-ranker cold start (~30-120s) — warm with a throwaway query first, and
   run nothing else against the backend while it executes.

## Postscript

The 50 sequential benchmark queries may hit Groq's free-tier rate limits. If they do, that is itself
worth recording rather than working around quietly — it is the same fragility (a free hosted
dependency under someone else's control) that produced both this outage and the 23-minute block. The
standing fallback discussed on 2026-08-13 remains local inference via Ollama: zero external
dependency, at some accuracy cost. Worth revisiting if this recurs — this is now the **second**
provider-side breakage in five days.
