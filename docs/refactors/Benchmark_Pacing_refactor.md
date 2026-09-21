# Benchmark Pacing — DRAFT (awaiting EXECUTE)

**Date:** 2026-09-21 · **File:** `backend/tests/rag_benchmark.py` · **Effort:** small (one config
constant, one sleep, one summary field, one corrected message)

## Why

The benchmark fires all 50 queries back-to-back with **no sleep, no backoff, no pacing**. That was
survivable when v7 ran; it is not survivable under the rate limit actually in force today.

**Measured against the live Groq API on 2026-09-21** (response headers on a real call with the
production model `openai/gpt-oss-120b`):

```
x-ratelimit-limit-tokens:     8000        reset: 547ms     <- per MINUTE
x-ratelimit-remaining-tokens: 7927
x-ratelimit-limit-requests:   1000        reset: 2m52.8s
```

**⚠ Correction (2026-09-21, before EXECUTE).** An earlier version of this draft claimed the
headers above *contradicted* the project's documented "200,000 tokens/day" figure, and that the
existing TPD advice was stale. **That was wrong, and the error was mine.** Groq's published free
tier for `openai/gpt-oss-120b` enforces **four limits simultaneously**:

| Limit | Value | Exposed in headers? |
|---|---|---|
| Requests/minute (RPM) | 30 | no |
| Requests/day (RPD) | 1,000 | yes — `x-ratelimit-*-requests` |
| Tokens/minute (**TPM**) | **8,000** | yes — `x-ratelimit-*-tokens` |
| Tokens/day (**TPD**) | **200,000** | **no — Groq returns no TPD header** |

The absence of a TPD header is a gap in Groq's API surface, not evidence that no daily cap exists.
The 2026-08-17 error message quoted in `Benchmark_Scorer_Honesty_refactor.md` — *"200,000 tokens/day
— Used 199,902"* — was a genuine observation of the real TPD limit. **Both figures are correct and
both limits bind; whichever is reached first returns 429.** The existing documentation was right;
this draft now only *adds* the TPM dimension rather than replacing anything.

**Scope: limits are per ORGANIZATION, not per project or per API key.** Groq's documentation states
this explicitly, and it means there is no way to ring-fence an allocation for this project — every
other project on the same Groq account draws from the same 8,000 TPM / 200,000 TPD pool, and
issuing additional API keys does not raise the ceiling.

## What each limit explains

- **TPM (8,000)** explains the *intermittent* failures in v8 from query #11 onward — the run was
  bursting over the per-minute bucket, failing, then partially recovering as the bucket refilled.
  That is why queries 12–16, 18, 19 and 32 succeeded in between failures, which the v8 post-mortem's
  "queries #11–50 all returned 429" does not account for.
- **TPD (200,000)** explains the *permanent* failure from query #33 to the end — cumulative usage
  exhausted the daily budget, after which nothing could succeed.

Together they fit the observed archive exactly; neither limit alone does.

**Arithmetic that explains the v8 failure.** v7 completed 50 queries in 842s — about **3.5
queries/minute**. At a conservative ~3,500–4,500 tokens per query (k=10 retrieved chunks at 1,000
chars ≈ 2,500 tokens of context, plus prompt and completion), that is roughly **12,000–16,000
tokens/minute — 1.5×–2× over the 8,000 TPM ceiling.** An unpaced run today will throttle, exactly
as v8 did.

**Corroborating detail the v8 post-mortem got wrong.** That report states "Queries #11–50 all
returned 429." The archive does not support this: queries **12, 13, 14, 15, 16, 18, 19 and 32
succeeded**, and the unbroken failure run only begins at #33. Intermittent failure followed by
sustained failure is the signature of a per-minute bucket being exhausted and partially refilling —
not of a daily ceiling being hit once at #11. (The headline figure, 32 engine errors scored as
correct, is accurate and unchanged.)

## What this does NOT do, deliberately

**No automatic retry on engine failure.** `/chat` returns HTTP 200 with a generic
`"I encountered an error processing your request."` in the body — the reason is not surfaced, so
the benchmark cannot distinguish a rate-limit from a genuine engine fault. Retrying blind would
risk silently papering over a real failure, which is the exact class of defect this file was
hardened against on 2026-08-17. The abort guard stays as the honest failure signal: if pacing is
still insufficient, the run aborts loudly and we raise the delay rather than hide the symptom.

## The diff

### 1 — Config constant, env-overridable

```diff
 BASE_URL = "http://localhost:8001/api/v1"
 ADMIN_USER = "admin"
 ADMIN_PASS = "grc-admin-2026"
 OUTPUT_FILE = "rag_benchmark_results.json"
+
+# Groq enforces a per-MINUTE token bucket (measured 2026-09-21: 8,000 TPM on
+# openai/gpt-oss-120b; no daily cap is exposed in the response headers). One benchmark
+# query costs roughly 3,500-4,500 tokens (k=10 x 1,000-char chunks of context, plus
+# prompt and completion). Unpaced, the loop ran at ~3.5 queries/min in v7 -- about
+# double the ceiling -- which is what produced v8's cascade of rate-limit errors.
+# At ~17s natural latency plus this delay, the run sits near 1.5 queries/min
+# (~6,000-7,000 tokens/min), inside the limit with headroom. Tune via env var if the
+# limit changes; the value used is recorded in the results JSON.
+PACING_SECONDS = float(os.getenv("GRC_BENCH_PACING", "22"))
```

### 2 — Sleep between queries (not after the last one)

```diff
         else:
             consecutive_errors = 0
 
+        # Stay under the per-minute token bucket. Skipped after the final query so the
+        # pacing never inflates the reported wall-clock of the run itself.
+        if PACING_SECONDS > 0 and i < len(QUERIES) - 1:
+            time.sleep(PACING_SECONDS)
+
     # Calculate final accuracy
```

### 3 — Record the pacing so runs stay comparable

```diff
     summary["accuracy_percentage"] = accuracy_pct
     summary["avg_latency"] = avg_latency
+    # Recorded so a future reader can tell a paced run from an unpaced one. `latency`
+    # and `avg_latency` remain REQUEST latency only and exclude this sleep, so they stay
+    # directly comparable with v1-v7.
+    summary["pacing_seconds"] = PACING_SECONDS
```

### 4 — Add the TPM dimension to the failure message, keeping the TPD advice

The existing TPD lines are **accurate and stay**. An earlier version of this draft deleted them,
which would have destroyed correct information — see the correction notice above.

```diff
     if not summary["valid"]:
         print("!! RUN INVALID -- DO NOT QUOTE THIS ACCURACY FIGURE")
         print(f"!! {summary['invalid_reason']}")
         print("!! Engine failures are NOT answers. Re-run once the backend is healthy;")
         print("!! on Groq's free tier the daily token budget (200k TPD) allows roughly")
         print("!! one full 50-query run per day, shared with all other LLM features.")
+        print(f"!! There is ALSO an 8,000 tokens/MINUTE cap. This run paced at {PACING_SECONDS}s")
+        print("!! between queries; if failures were intermittent rather than sustained, that")
+        print("!! points at TPM, not TPD -- raise the pacing and retry the same day:")
+        print("!!   GRC_BENCH_PACING=30 python backend/tests/rag_benchmark.py")
+        print("!! Sustained failure from one query onward with no recovery points at TPD;")
+        print("!! that one needs a fresh day, and limits are shared ACROSS the whole Groq")
+        print("!! organization -- other projects on the same account consume the same budget.")
```

### 5 — Print the pacing in the start banner

```diff
-    print(f"\n🚀 Starting RAG Benchmark ({len(QUERIES)} queries)...\n")
+    print(f"\n🚀 Starting RAG Benchmark ({len(QUERIES)} queries, "
+          f"pacing {PACING_SECONDS}s between queries)...\n")
```

## Expected effect

| | Before | After |
|---|---|---|
| Queries/min | ~3.5 | ~1.5 |
| Tokens/min (est.) | 12,000–16,000 | 6,000–7,000 |
| Against 8,000 TPM | **over by 1.5–2×** | under, with headroom |
| Wall clock, 50 queries | ~14 min (then throttles) | ~32 min |
| Accuracy figure | unchanged — pacing does not touch retrieval, ranking, or scoring |

## Verification plan

1. Run it. Expect 50/50 with `"error": 0` and `"valid": true`.
2. Confirm `summary.pacing_seconds` is present in the output JSON.
3. Confirm `avg_latency` is in the same range as v7's 16.86s — if pacing had leaked into the
   latency measurement it would read ~39s, which would break comparability with v1–v7.
4. If it still aborts on rate limits, re-run with `GRC_BENCH_PACING=30`. One variable, one change.

## What this fix does NOT solve — read before running

**Pacing addresses TPM only. It does nothing for TPD, and TPD is the tighter constraint.**

A 50-query run costs roughly 100,000–200,000 tokens (50 × ~2–4k). The daily cap is **200,000**.
So a single full run can consume the entire day's budget on its own — exactly what
`HANDOFF.md` said, and that advice stands unchanged.

Three consequences to plan around:

1. **One full run per day, realistically.** Slowing the run down does not make it cheaper; it
   spends the same tokens over a longer window.
2. **The budget is shared organization-wide.** Any other project on the same Groq account spends
   from the same 200,000. If those projects run today, this benchmark can fail partway through
   even when perfectly paced — and nothing in the headers will warn us in advance, because Groq
   exposes no TPD counter.
3. **Nothing else Groq-backed should run today if the benchmark runs** — no interactive `/chat`,
   no agent runs, no Interview Simulator grading, no smoke tests that hit the LLM.

**Pre-flight check that is available:** `x-ratelimit-remaining-requests` (RPD) is exposed and
refills slowly — 1 request per 86.4 s. If it reads well below 1,000, the account has been active
recently and a run is riskier. Measured 2026-09-21 before this draft: **999/1000**, i.e. the
account was essentially idle. That is a useful proxy, but only for roughly the last hour, and it
says nothing directly about tokens.

If the run does abort, the invalid-run guard reports it honestly rather than producing a number —
and the failure *shape* now tells us which limit we hit: intermittent-with-recovery means TPM
(raise the pacing, retry today), sustained-with-no-recovery means TPD (wait for a fresh day).
