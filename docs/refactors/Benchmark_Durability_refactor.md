# Benchmark Durability — a killed run must not lose everything — EXECUTED 2026-09-25

**Date:** 2026-09-25 · **File:** `backend/tests/rag_benchmark.py` · **Effort:** small (one helper,
two call sites, one flush) · **Status: APPLIED AND VERIFIED.** EXECUTE given 2026-09-25.

## Verification — 21/21, zero Groq tokens

All against a stubbed `/chat`, per the plan below. No tokens were spent proving this works, which
was the point after the run it exists to prevent.

| Check | Result |
|---|---|
| Output file exists mid-run | pass |
| Simulated kill at query 6 leaves exactly 5 saved results | pass |
| `queries_completed: 5`, `complete: false`, `valid: false` | pass |
| **`accuracy_percentage: null`** on a partial | pass |
| `invalid_reason` reads `PARTIAL SNAPSHOT -- 5/50 queries. Not a measurement; do not cite.` | pass |
| `rate_on_completed` present and correct | pass |
| Full 50-query stubbed run → `complete: true`, `valid: true` | pass |
| `accuracy_percentage` still `answered/50`, not `answered/completed` | pass |
| `pacing_seconds` and `avg_latency` still recorded | pass |
| All seven v1–v7 archives parse with unchanged accuracy (42/70/76/80/84/92/90) | pass |

The last row matters most: the new `queries_completed` / `rate_on_completed` / `complete` fields
are purely additive and no existing field changed meaning, so every historical archive still reads
exactly as it did.

One refinement made during EXECUTE, beyond the draft: `invalid_reason` now also appends
`"; only N/50 queries completed"` when a run ends short, so the reason string names the actual
cause rather than leaving it to be inferred from `queries_completed`.

## Consequence first

`rag_benchmark.py` writes its results **exactly once, after the loop finishes**. Any interruption
before that point — kill, timeout, crash, Ctrl-C, laptop sleep — discards every completed query.

This is not hypothetical. **2026-09-25: the run was killed at query 33 of 50 and wrote nothing.**
33 healthy queries, zero engine errors, roughly **100,000–130,000 Groq tokens — half to
two-thirds of the organization-wide daily budget — produced no file.**

The budget is the scarce resource here, not the wall clock. A 50-query run costs 77–100% of a
day's tokens (`Benchmark_Pacing_refactor.md`), so **a lost run costs a day**, and there is no way
to buy the day back.

## What actually happened, verified

| Observation | Evidence |
|---|---|
| 33 queries completed, all HTTP 200 | backend log, 20:46:09 → 20:59:43 UTC |
| **Zero** engine failures | re-scored from `audit_logs`: 0 errors in 32 recovered rows |
| **Not** rate-limited | zero 429s in the window; the documented failure mode did not occur |
| Container never restarted | `StartedAt` 2026-09-23, `ExitCode 0`, `OOMKilled false` |
| Process died mid-pacing-sleep | last query 20:59:43, process exit 21:00:02 (19 s into a 22 s sleep) |
| Nothing written | no `rag_benchmark_results*.json` anywhere on the filesystem |

The run was **healthy when it died.** The abort guard never fired because there was nothing to
abort on. The guard protects against a *failing* engine; it does nothing for an *interrupted* one,
and interruption is the failure mode that actually cost us a day.

**stdout was also lost entirely** — Python block-buffers when redirected to a file, so 14 minutes
of progress output never reached disk. Health had to be reconstructed from Docker logs after the
fact. During the run there was no way to distinguish "working fine" from "dead".

## Why the single write exists

Nothing deliberate — the script grew from a one-shot script where a 50-query run took ~3 minutes
unpaced. Pacing (2026-09-21) took the run to ~32 minutes, which widened the interruption window by
**10×** without anyone revisiting the write strategy. This is a consequence of that change that
the pacing draft did not anticipate.

## The diff

### 1 — Extract the save so it can be called more than once

```diff
+def _save(results, summary, aborted_at=None, complete=False):
+    """Write results to disk. Called after EVERY query, not just at the end.
+
+    A run killed at query 33 on 2026-09-25 lost all 33 completed results and
+    ~100k tokens of an organization-wide daily budget, because the only write
+    happened after the loop. Partial data is recoverable data; an absent file
+    is a wasted day. `complete` distinguishes a finished run from a snapshot so
+    a partial file can never be mistaken for a real measurement.
+    """
+    done = len(results)
+    snap = dict(summary)
+    snap["queries_completed"] = done
+    snap["complete"] = complete
+    snap["accuracy_percentage"] = (
+        round((snap["answered"] / snap["total"]) * 100, 2) if complete else None
+    )
+    snap["rate_on_completed"] = round((snap["answered"] / done) * 100, 2) if done else 0.0
+    if not complete:
+        snap["valid"] = False
+        snap["invalid_reason"] = (
+            f"PARTIAL SNAPSHOT -- {done}/{snap['total']} queries. "
+            "Not a measurement; do not cite."
+        )
+    with open(OUTPUT_FILE, "w") as f:
+        json.dump({"summary": snap, "results": results}, f, indent=4)
```

### 2 — Save after every query, and flush progress output

```diff
         # Live feedback
-        print(f"{i+1:<3} | {outcome:<18} | {latency:<8} | {sources_count:<8}")
+        # flush=True: without it Python block-buffers to a redirected file and 14
+        # minutes of progress output is lost if the process is killed (2026-09-25).
+        print(f"{i+1:<3} | {outcome:<18} | {latency:<8} | {sources_count:<8}", flush=True)
+
+        # Persist immediately. Costs ~2 ms against a 22 s pacing sleep.
+        _save(results, summary)
```

### 3 — Final write goes through the same helper

```diff
-    summary["valid"] = (summary["error"] == 0 and aborted_at is None)
-    if not summary["valid"]:
-        summary["invalid_reason"] = (
-            f"{summary['error']} engine failure(s)"
-            + (f"; aborted at query {aborted_at}/{summary['total']}" if aborted_at else "")
-        )
-
-    # Save to file
-    final_output = {
-        "summary": summary,
-        "results": results
-    }
-    with open(OUTPUT_FILE, "w") as f:
-        json.dump(final_output, f, indent=4)
+    summary["valid"] = (summary["error"] == 0 and aborted_at is None
+                        and len(results) == summary["total"])
+    if not summary["valid"]:
+        summary["invalid_reason"] = (
+            f"{summary['error']} engine failure(s)"
+            + (f"; aborted at query {aborted_at}/{summary['total']}" if aborted_at else "")
+        )
+    _save(results, summary, aborted_at=aborted_at, complete=True)
```

Note the added `len(results) == summary["total"]` clause: a run that ends early for **any** reason
is now invalid by construction, not only one that trips the error guard.

## How to run it so it survives — procedure, no code change

Tonight's run died because it was a child of a tool session with its own lifecycle. Two changes to
how it is invoked, independent of the diff above:

```powershell
# Unbuffered, detached, output captured to a real file.
$env:PYTHONUTF8 = "1"
Start-Process -FilePath python `
  -ArgumentList "-u", "backend/tests/rag_benchmark.py" `
  -WorkingDirectory "C:\Users\efosb\OneDrive\Desktop\GRC Inspector\GRC_Command_Center" `
  -RedirectStandardOutput "bench_run.log" `
  -RedirectStandardError  "bench_run.err" `
  -NoNewWindow
```

- **`-u`** — unbuffered; progress appears in the log as it happens.
- **`Start-Process`** — the run is not a child of the calling session, so the session ending, timing
  out, or being interrupted does not kill it.
- **Watch it live** with `Get-Content bench_run.log -Wait`, or read `rag_benchmark_results.json`,
  which is now current to the last completed query.

## Expected effect

| | Before | After |
|---|---|---|
| Run killed at query 33 | **all 33 results lost** | 33 results on disk, flagged `complete: false` |
| Progress visibility | none until process exit | every query, live |
| Cost of an interruption | a full day's token budget | the single in-flight query |
| A partial file being miscited | n/a — no file existed | `valid: false`, `accuracy_percentage: null` |
| Completed-run behaviour | unchanged | unchanged — same fields, same scoring |

## Verification plan

1. Run with `GRC_BENCH_PACING=0` against a **stubbed** `/chat` (no Groq spend) — confirm
   `rag_benchmark_results.json` exists and grows after each query.
2. Kill it at ~query 5; confirm the file holds 5 results, `complete: false`, `valid: false`,
   `accuracy_percentage: null`.
3. Let a stubbed run finish; confirm `complete: true`, `valid: true`, and that
   `accuracy_percentage` matches the old formula (answered / **50**, not answered / completed).
4. Confirm the v1–v8 archives still parse — `rate_on_completed` and `queries_completed` are
   additive, and no existing field changes meaning.
5. Only then spend real tokens.

**Steps 1–4 cost zero Groq tokens.** Given tonight, that ordering is the point.

## Related, not included

- **Recovering a lost run from `audit_logs`.** Tonight's 33 queries were reconstructed from the
  audit trail (32 of them — one was missing to the NUL-byte bug, see
  `AuditLog_NulByte_refactor.md`) and re-scored with this module's own scorer at zero cost. That
  worked, but by luck: the audit trail is not a benchmark backup and should not become one. The
  fix above makes the benchmark durable on its own. A `--recover-from-audit` flag is a reasonable
  future addition; it is not proposed here.
- **`max_retries=2` on `ChatGroq`.** Tonight's run consumed ~43 Groq calls for 33 queries,
  implying ~10 internal retries that spent tokens invisibly. Noted in
  `Benchmark_Pacing_refactor.md` and still unaddressed. Not touched here — it is a `rag.py`
  concern and deserves its own draft.
