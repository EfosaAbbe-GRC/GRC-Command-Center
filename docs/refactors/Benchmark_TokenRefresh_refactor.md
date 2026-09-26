# Benchmark — the JWT expires mid-run — EXECUTED 2026-09-26

**Date:** 2026-09-26 · **File:** `backend/tests/rag_benchmark.py` · **Effort:** small (one timer,
one retry path, one wording fix) · **Status: APPLIED AND VERIFIED.** EXECUTE given 2026-09-26.

## Verification — 13/13, zero Groq tokens

| Check | Result |
|---|---|
| `authenticate()` called repeatedly, not once (age forced to 0) | **51 calls / 50 queries**, 50 distinct tokens |
| A 401 on query 5 is recovered | scored **ANSWERED**, not `ERROR (401)` |
| Exactly one forced re-auth on that 401 | 2 total (1 initial + 1 forced) |
| Run still valid, all 50 completed | pass |
| Clean run unchanged — 50/50, `valid: true`, accuracy `answered/50` | pass |
| v1/v5/v6/v7 archives parse with unchanged accuracy | pass |

### A second defect, found while verifying — in the *previous* night's fix

Inspecting the real 39/50 output revealed that `Benchmark_Durability_refactor.md` had left a hole
of exactly the kind it was written to close:

```
queries_completed : 39 of 50
complete          : True    <-- an aborted run stamped complete
accuracy_percentage: 64.0   <-- a citable-looking figure for a run that never finished
```

`complete` was being set from the caller's "the script reached the end", which is **also true of
an aborted run**. Only `valid: false` stood between that file and someone quoting 64%.

**Fixed in the same pass:** `_save()` now requires *coverage* as well — `complete` and
`accuracy_percentage` are emitted only when `len(results) == total`. Verified with a stub that
reproduces the exact 39/50 abort shape: `complete: false`, `accuracy_percentage: null`,
`rate_on_completed` still available, and the reason string naming the shortfall. A genuinely
complete run is unaffected (11/11 checks).

Worth recording plainly: **last night's fix shipped with a flaw, and reading its real output is
what found it — not the 21 checks that passed against stubs.** The stubs only ever tested a clean
run and a mid-run snapshot, never an *aborted* one, which is the exact case that matters here.

## Consequence first

`rag_benchmark.py` authenticates **once**, before the loop, and reuses that token for the whole
run. `JWT_EXPIRE_MINUTES` is **15**. A paced 50-query run takes **~32 minutes**.

**The token dies roughly two-thirds of the way through, every single time.** Queries from that
point on return HTTP 401, the abort guard trips after three, and the run ends.

This is not a rate limit, not a Groq problem, and not an engine problem. It is arithmetic.

## Evidence — the 2026-09-26 run

| | |
|---|---|
| `LOGIN_SUCCESS` | 17:33:14 UTC |
| First `Auth: Invalid or expired token` | 17:48:38 UTC |
| **Elapsed** | **15m 24s** — against `JWT_EXPIRE_MINUTES=15` |
| Failures | queries **37, 38, 39**, at exactly 22 s apart (the pacing interval) |
| Labelled | `ERROR (401)` — correctly, the scorer did not call these answers |
| Latency | **0.02–0.03 s** — rejected at the auth layer, **zero Groq tokens spent** |
| Groq state after | probe returned HTTP 200, **964/1000** RPD remaining |

The Groq probe succeeding afterwards is what rules out the rate-limit hypothesis outright. The
budget was never the binding constraint on this run.

## Root cause is the same one that caused the durability bug

The 2026-09-21 pacing change took the run from ~3 minutes to ~32. That broke **two** independent
time-bound assumptions, neither of which anyone revisited:

1. *"Results only need saving at the end"* — a 3-minute run is rarely interrupted. Fixed
   2026-09-25 (`Benchmark_Durability_refactor.md`).
2. *"One login at the start is enough"* — a 3-minute run finishes well inside a 15-minute token.
   **This draft.**

**Both were latent for four days and neither was visible by reading the diff that caused them.**
Worth remembering the next time a change alters how long something runs rather than what it does.

**Corollary — the 2026-09-25 run was doomed regardless.** It was killed externally at 14m26s,
just **34 seconds** short of the same JWT expiry. Had it survived the kill, it would have started
401-ing at query ~35 and aborted a minute later. That night's budget was never going to produce a
complete run.

## The diff

### 1 — Track token age and refresh before it can expire

```diff
 BASE_URL = "http://localhost:8001/api/v1"
 ADMIN_USER = "admin"
 ADMIN_PASS = "grc-admin-2026"
 OUTPUT_FILE = "rag_benchmark_results.json"
+
+# The backend's JWT_EXPIRE_MINUTES is 15, and a paced 50-query run takes ~32 minutes,
+# so a single login cannot cover a whole run -- queries 37-39 died on HTTP 401 on
+# 2026-09-26 at exactly 15m24s after LOGIN_SUCCESS. Refresh well inside that window.
+# Re-authentication is a local DB round-trip and costs ZERO Groq tokens, so refreshing
+# early and often is free; the only cost of getting this wrong is losing the run.
+TOKEN_MAX_AGE_SECONDS = 600  # 10 min, a third of headroom under a 15 min expiry
```

### 2 — A token holder that refreshes itself

```diff
+class _Token:
+    """Holds the JWT and re-acquires it before it can age out mid-run."""
+
+    def __init__(self):
+        self.value = None
+        self.issued_at = 0.0
+
+    def get(self, force=False):
+        if force or self.value is None or (time.time() - self.issued_at) > TOKEN_MAX_AGE_SECONDS:
+            tok = authenticate()
+            if not tok:
+                return None
+            self.value = tok
+            self.issued_at = time.time()
+        return self.value
+
+    def headers(self, force=False):
+        tok = self.get(force=force)
+        return {"Authorization": f"Bearer {tok}"} if tok else None
```

### 3 — Use it per query, and recover from a 401 rather than burning the run

```diff
-    token = authenticate()
-    if not token:
-        sys.exit(1)
-
-    headers = {"Authorization": f"Bearer {token}"}
+    token = _Token()
+    if not token.get():
+        sys.exit(1)
```

```diff
         try:
-            r = requests.post(f"{BASE_URL}/chat", json={"query": query}, headers=headers, timeout=60)
+            headers = token.headers()
+            r = requests.post(f"{BASE_URL}/chat", json={"query": query}, headers=headers, timeout=60)
+            # Belt and braces: if the token still aged out (clock skew, a changed
+            # JWT_EXPIRE_MINUTES, a slow query), re-auth once and retry rather than
+            # scoring an infrastructure failure as a result. Costs no Groq tokens on
+            # the 401 itself -- it never reached the LLM.
+            if r.status_code == 401:
+                retry_headers = token.headers(force=True)
+                if retry_headers:
+                    r = requests.post(f"{BASE_URL}/chat", json={"query": query},
+                                      headers=retry_headers, timeout=60)
             latency = round(time.time() - start_time, 2)
```

### 4 — Stop calling every error an "engine failure"

`invalid_reason` currently reports `"3 engine failure(s)"` for three HTTP 401s. The per-query
`outcome` was correct (`ERROR (401)`), but the summary line a future reader sees first was not.
That is exactly the kind of small dishonesty this file was hardened against on 2026-08-17.

```diff
     if not summary["valid"]:
         summary["invalid_reason"] = (
-            f"{summary['error']} engine failure(s)"
+            f"{summary['error']} failed quer(y/ies)"
             + (f"; aborted at query {aborted_at}/{summary['total']}" if aborted_at else "")
             + (f"; only {len(results)}/{summary['total']} queries completed"
                if len(results) != summary["total"] else "")
         )
```

## Expected effect

| | Before | After |
|---|---|---|
| Max run length before auth death | **~15 min** (≈ query 36) | unbounded — refreshes every 10 min |
| A 401 mid-run | scored as a failure, 3 in a row aborts the run | re-auth and retry once, transparently |
| Groq cost of the fix | — | **zero** — auth is a local DB call |
| `invalid_reason` wording | calls 401s "engine failures" | names failures without asserting a cause |
| Scoring, pacing, output | unchanged | unchanged |

## Verification plan

1. **Zero-token stub run** with `TOKEN_MAX_AGE_SECONDS = 2` and `GRC_BENCH_PACING=0`: confirm
   `authenticate()` is called repeatedly, not once.
2. Stub a 401 on a chosen query; confirm exactly one forced re-auth, one retry, and that the query
   scores on its retried result rather than as `ERROR (401)`.
3. Confirm a normal stubbed run still produces 50/50, `valid: true`, and an unchanged
   `accuracy_percentage`.
4. Confirm the v1–v7 archives still parse unchanged.
5. **Live:** re-run the real benchmark on a fresh budget and confirm it passes 15 minutes / query
   36 without a 401 — the specific point both previous attempts died at or before.

Steps 1–4 cost nothing. Step 5 is the real run.

## What this does NOT address

**Raising `JWT_EXPIRE_MINUTES` was considered and rejected.** A 15-minute access token is a
reasonable security posture and it is the *application* that is correct here; the test harness was
wrong to assume one login covers a 32-minute job. Weakening a real security parameter to suit a
benchmark would be the wrong trade, and it would leave the harness just as fragile the next time
the run gets longer.
