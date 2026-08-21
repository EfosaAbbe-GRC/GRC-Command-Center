# Fix: the benchmark scores engine errors as correct answers

**Status:** ✅ EXECUTED (2026-08-17). All four parts applied as drafted.

**Verified by reproducing the failure first, which is the point.** The daily token budget had already
begun to reset by the time the fix was ready, so rather than wait (or burn quota), the negative test
used the bogus-model trick from `RAG_Model_Outage_refactor.md` — the engine fails instantly and
consumes **zero tokens**. Under the exact conditions that produced a fake 96%, the patched scorer now
gives:

```text
1   | ERROR (Engine Failure) | 21.35    | 0
2   | ERROR (Engine Failure) | 3.22     | 0
3   | ERROR (Engine Failure) | 3.1      | 0

!! ABORTING after 3 queries -- 3 consecutive engine failures.
!! RUN INVALID -- DO NOT QUOTE THIS ACCURACY FIGURE
!! 3 engine failure(s); aborted at query 3/50
```

…and **exits non-zero (1)**, so it cannot silently pass in a script or CI step. Backend reverted to
`openai/gpt-oss-120b` by force-recreating from the image; `rag_benchmark_results.json` restored to the
last *valid* run (v7); the contaminated archive renamed
`rag_benchmark_results.v8_INVALID_rate_limited.json` per archive-don't-delete.

**Still outstanding: a real v8.** The corpus refresh is done and sound, but its measurement does not
exist yet. Re-run when the daily budget has fully reset — and note the run itself will consume most
of a day's tokens.
**Found:** 2026-08-17, running the v8 benchmark after the corpus refresh. The run reported
**96.0% (48/50)** — its best score ever. **32 of those 50 "answers" were rate-limit errors.**
**File:** `backend/tests/rag_benchmark.py`
**Effort:** small (one branch, one abort guard, one validity flag)

## The bug

`/api/v1/chat` returns **HTTP 200 with an error message in the body** when the LLM call fails — it
does not return a 5xx. The scorer's ladder is:

```python
if r.status_code == 200:              # true, even for an engine failure
    answer = data.get("response", "")
    if "INSUFFICIENT_DATA" in answer:  # error strings contain no such marker
        outcome = "INSUFFICIENT_DATA"
    elif len(answer) > 20:             # "I encountered an error..." is 44 chars
        outcome = "ANSWERED"           # <-- scored as a correct answer
```

So every engine failure lands in the `ANSWERED` bucket and **inflates accuracy**.

**This is the third appearance of one defect class in a single day**, and I missed it here after
fixing it twice:

| Location | Symptom | Fixed |
| --- | --- | --- |
| `core/agent.py` `active-auditor` | "4/4 core functions substantiated" from 4 failed queries | 2026-08-17 |
| `tests/smoke_test.py` `/chat` check | 43/43 green while every RAG call 404'd | 2026-08-17 |
| **`tests/rag_benchmark.py`** | **96% accuracy from 32 errors** | **this draft** |

Same root cause every time: **a check that asks "is there a response?" instead of "is the response
real?"**

## What it cost

The v8 run hit Groq's free-tier ceiling (**200,000 tokens/day** — "Used 199,902") at **query #11**.
Queries #11–50 all returned `429`, and all were scored as correct.

Only **#1–10** are valid, and that slice is genuinely encouraging — **9/10 vs v7's 8/10**, with #6
recovered (independently confirmed live: the newly-added `NIST CSF 2.0 (CSWP 29).pdf` answers the
Tier question with correct citations). But the headline 96%, the "improved" 7.71s latency, and the
apparent recovery of #12 and #50 are all **artifacts of counting errors as passes**. None of it is
real.

## Part A — engine failures are ERROR, never ANSWERED

```diff
--- a/backend/tests/rag_benchmark.py
+++ b/backend/tests/rag_benchmark.py
@@
+# /chat returns HTTP 200 with an error message in the BODY when the LLM call fails,
+# so status_code is not sufficient to detect failure. Keep in sync with
+# core/agent.py's _ENGINE_FAILURE_MARKERS -- deliberately duplicated rather than
+# imported, because this script runs on the HOST against the container's HTTP port
+# and cannot import core.* (which pulls in langchain and the rest of the backend
+# stack). Four rarely-changing strings; the duplication is the cheaper risk.
+ENGINE_FAILURE_MARKERS = (
+    "i encountered an error processing your request",
+    "security alert: knowledge base integrity check failed",
+    "error loading index:",
+    "rag engine not initialized",
+)
+
+
+def is_engine_failure(answer: str) -> bool:
+    if not answer or not answer.strip():
+        return True
+    low = answer.lower()
+    return any(m in low for m in ENGINE_FAILURE_MARKERS)
@@
             if r.status_code == 200:
                 data = r.json()
                 answer = data.get("response", "")
                 sources = data.get("sources", [])
                 sources_count = len(sources)
 
-                if "INSUFFICIENT_DATA" in answer:
+                # Checked BEFORE the INSUFFICIENT_DATA / length branches: an engine
+                # failure is not a refusal and not an answer. Counting it as either
+                # produced a fake 96% on 2026-08-17.
+                if is_engine_failure(answer):
+                    outcome = "ERROR (Engine Failure)"
+                    summary["error"] += 1
+                elif "INSUFFICIENT_DATA" in answer:
                     outcome = "INSUFFICIENT_DATA"
                     summary["insufficient_data"] += 1
                 elif len(answer) > 20:
                     outcome = "ANSWERED"
                     summary["answered"] += 1
```

## Part B — abort the run instead of generating 40 more fake results

Once the daily token budget is gone, every remaining query fails. Continuing wastes ~10 minutes and
writes a polluted archive.

```diff
+        # Three consecutive engine failures means the backend is down or the token
+        # budget is exhausted -- every further query will fail too. Stop rather than
+        # manufacture dozens of meaningless rows.
+        if outcome.startswith("ERROR"):
+            consecutive_errors += 1
+            if consecutive_errors >= 3:
+                print(f"\n!! ABORTING after {i+1} queries -- 3 consecutive engine failures.")
+                print("!! Check GET /api/v1/readiness and the backend logs (rate limit?).")
+                aborted_at = i + 1
+                break
+        else:
+            consecutive_errors = 0
```

## Part C — a run with any error is not a valid measurement

```diff
     summary["accuracy_percentage"] = round(summary["answered"] / summary["total"] * 100, 1)
+    # A run with ANY engine error cannot be compared against a clean one -- the
+    # denominator is intact but the numerator is contaminated. Mark it in the JSON so
+    # a future reader cannot mistake it for a real data point.
+    summary["valid"] = summary["error"] == 0 and not aborted_at
+    if not summary["valid"]:
+        summary["invalid_reason"] = (
+            f"{summary['error']} engine failure(s)"
+            + (f"; aborted at query {aborted_at}/{summary['total']}" if aborted_at else "")
+        )
```

…and print a loud banner instead of a clean-looking percentage:

```diff
+    if not summary["valid"]:
+        print("=" * 50)
+        print("!! RUN INVALID -- DO NOT QUOTE THIS ACCURACY FIGURE")
+        print(f"!! {summary['invalid_reason']}")
+        print("=" * 50)
```

## Part D — housekeeping: quarantine the bad archive

`rag_benchmark_results.v8_corpus_refresh.json` currently holds the contaminated run. Per
archive-don't-delete, **rename** it to
`rag_benchmark_results.v8_INVALID_rate_limited.json` so the trajectory table can never accidentally
cite it. The real v8 gets the clean name when it is re-run.

## Verification plan

1. **Reproduce the bug first** — run the benchmark now, while still rate-limited. Current code
   reports a high accuracy; patched code must abort after 3 queries with the INVALID banner. *A fix
   that cannot be shown failing on the old behaviour is not verified.*
2. Once the daily budget resets, run clean and confirm `"valid": true` with zero errors.
3. `smoke_test.py` **44/44** and `pytest` **38/38** — untouched by this, but run per the ritual.

## The operational fact this exposes, which matters beyond the fix

**Groq's free tier allows roughly one full benchmark run per day.** 50 queries at ~2–4k tokens each
is 100–200k tokens against a 200,000 TPD cap — and that is *before* any interactive `/chat` use,
agent runs, or smoke tests, which draw from the same budget.

Consequences worth planning around:

- **Benchmarking is now a once-daily operation.** Do not schedule it casually.
- **A benchmark run can take the app down for the rest of the day** for every other LLM feature.
- This also retro-explains v7's "latency regression" (6.6s → 16.86s), recorded then as an unproven
  hypothesis: it was almost certainly throttling as the budget depleted, **not** a slower model. That
  hypothesis can now be marked confirmed.
- If regular benchmarking is wanted, the options are a paid Groq tier or local inference (Ollama),
  the standing fallback since 2026-08-13.
