# Audit Log — NUL byte silently destroys audit records — EXECUTED 2026-09-25

**Date:** 2026-09-25 · **File:** `backend/core/database.py` · **Effort:** small (one helper, one
call site) · **Status: APPLIED AND VERIFIED.** EXECUTE given 2026-09-25.

## Verification — passed, but only on the second attempt

| Check | Result |
|---|---|
| `_pg_safe` unit tests (11 cases, extracted from the real source) | **11/11 pass** — NULs stripped, unicode and other control chars preserved, clean text untouched |
| Live: the exact failing query (#13, ISO 27001 cloud controls) | `audit_logs` **144 → 145** — the row that could not previously be written now exists |
| Sanitization disclosed | `WARNING ... nul_bytes_removed: 10, fields: {"context": 10}` then `INFO Audit log entry created` |
| Regression: a clean query (KRI vs KPI) | row written, **no warning** — correlated by `request_id`, not by log window |
| `pytest` (host, against modified source) | **50/50** |
| `smoke_test.py` (test stack rebuilt with this change) | **44/44** |

Ten NUL bytes, all in `context` — exactly the predicted field, since it concatenates ~10 raw PDF
chunks.

### ⚠ The first attempt failed, and it was my own bug

The draft specified `logger.warning(...)`. This codebase's `StructuredLogger` (`core/logger.py`)
exposes **`warn`**, not `warning` — and every other call site in the repo already uses
`logger.warn`. The mismatch raised `AttributeError: 'StructuredLogger' object has no attribute
'warning'` **before** the INSERT, so the first build still wrote no row and the audit gap stayed
open. Corrected to `logger.warn` and re-verified above.

Two things worth keeping from that:

1. **The bug was invisible for the same reason the original one was.** `except Exception` caught my
   `AttributeError` and logged it as `"Audit logging failed"` — the identical symptom as the NUL
   bug it was meant to fix. A fix for a silent failure, failing silently, in the same way. This is
   direct evidence for **option B** below.
2. **It would not have happened if the draft had matched the surrounding code.** Every existing
   call site was already correct; the draft introduced the only outlier.

## Consequence first

**A chat interaction whose retrieved context contains a NUL byte (`0x00`) returns a normal answer
to the user and writes no audit record at all.** The failure is caught, logged at ERROR, and
swallowed. The API returns HTTP 200. Nothing surfaces to the caller, the UI, or any health check.

On a platform whose headline security claim is *database-enforced immutable audit trails*
(`GOVERNANCE.md` §2.2), a silent hole in that trail is the most serious class of defect available.
Immutability was never the weak point — **capture** is.

## How it was found

Not by looking for it. During the interrupted benchmark run of 2026-09-25, one of 33 queries logged:

```
ERROR  Audit logging failed
  request_id: b7b8f613-aa1b-407c-b497-1ebb1da08a78
  error: (asyncpg) CharacterNotInRepertoireError:
         invalid byte sequence for encoding "UTF8": 0x00
  [SQL: INSERT INTO audit_logs (request_id, query, response, context, sources) ...]
```

Query #13, *"How does ISO 27001:2022 address cloud security controls?"* — answered normally,
never recorded.

**Verified, not inferred.** `audit_logs` holds 32 rows for that run's window
(20:46:09–20:59:43 UTC) against 33 `POST /api/v1/chat` requests in the backend log. Exactly one
row missing, matching exactly one error. The gap is real and reproducible.

## Root cause

PostgreSQL `text`/`varchar` columns **cannot store `0x00`** — it is not an encoding problem that a
different client setting fixes; the type genuinely has no representation for it. PDF text
extraction emits NUL bytes routinely (font/encoding artifacts, embedded binary), so any chunk
carrying one poisons the whole `INSERT`.

`context` is the exposed field: it concatenates ~10 retrieved chunks of raw PDF text, so it has
roughly ten times the chance of containing one as any other column. `response` and `query` are
lower risk but not zero — the model can echo context verbatim.

**Scope is the RAG audit path only.** `evidence_chain` (filenames, hashes) and the TPRM tables
(typed user input) do not carry extracted PDF text. Not changed here.

## Why it survived this long

The `except Exception` in `_log_interaction_async` is correct in intent — an audit write must not
take down a user request — but it converts a **data-integrity failure** into a log line nobody
reads. The system had no way to tell you the trail had a hole in it.

## The diff

### 1 — Sanitizer helper (new, module level, near the other helpers)

```diff
+def _pg_safe(value: str) -> tuple[str, int]:
+    """Strip NUL bytes so a text column can store the value.
+
+    PostgreSQL text/varchar cannot represent 0x00 -- asyncpg raises
+    CharacterNotInRepertoireError and the entire INSERT is lost. PDF text
+    extraction emits NULs routinely, so an un-sanitized RAG context silently
+    destroyed its own audit record (observed 2026-09-25, benchmark query #13).
+    Returns the cleaned text and how many bytes were removed, so the caller can
+    record that the stored record was altered rather than altering it silently.
+    """
+    if not value:
+        return value or "", 0
+    removed = value.count("\x00")
+    if not removed:
+        return value, 0
+    return value.replace("\x00", ""), removed
```

### 2 — Sanitize at the boundary, and say so when it happens

```diff
     async def _log_interaction_async(self, request_id: str, query: str, response: str, context: str, sources: list):
         """Async: persist a RAG interaction to the audit trail."""
         try:
             async with AsyncSessionLocal() as session:
                 sources_str = ", ".join(sources) if sources else ""
+                # Sanitize BEFORE the INSERT. A single NUL anywhere in these four
+                # fields loses the whole row, and the row is the audit trail.
+                query, n_q = _pg_safe(query)
+                response, n_r = _pg_safe(response)
+                context, n_c = _pg_safe(context)
+                sources_str, n_s = _pg_safe(sources_str)
+                stripped = n_q + n_r + n_c + n_s
+                if stripped:
+                    # WARNING, not silence: the stored record differs from what was
+                    # served, and an audit trail must disclose its own alterations.
+                    logger.warning(
+                        "Audit record sanitized before write",
+                        request_id=request_id,
+                        nul_bytes_removed=stripped,
+                        fields={"query": n_q, "response": n_r,
+                                "context": n_c, "sources": n_s},
+                    )
                 log = AuditLog(
                     request_id=request_id,
                     query=query,
                     response=response,
                     context=context,
                     sources=sources_str,
                 )
                 session.add(log)
                 await session.commit()
             logger.info("Audit log entry created", request_id=request_id)
         except Exception as e:
             logger.error("Audit logging failed", request_id=request_id, error=str(e))
```

## What this deliberately does NOT change — one decision is yours

**The `except Exception` still swallows the failure.** After this fix the *known* cause is gone,
but an unknown one would still produce a silently missing audit record.

That is a governance question, not an engineering one, so it is not decided here:

| Option | Behaviour on audit-write failure | Trade-off |
|---|---|---|
| **A — keep as-is** | log ERROR, return the answer | availability over completeness; the hole stays invisible |
| **B — surface it** | return the answer, add `audit_logged: false` to the response | honest; needs a response-schema change and UI handling |
| **C — fail closed** | return 500, no answer | a real GRC posture; the strictest reading of §2.2 |

**Recommendation: B.** It matches the honesty pattern already established in this codebase —
`interview_sim.py`'s explicit `grading_failed` state, and `ComplianceTerminal`'s
reference-catalog relabel. Both chose *disclose the limitation* over *hide it* or *refuse to
serve*. C is defensible but would have turned tonight's single NUL byte into a failed user
request. Your call — happy to draft B separately.

## Expected effect

| | Before | After |
|---|---|---|
| Chat with a NUL in context | answer served, **audit record lost** | answer served, audit record written |
| Record fidelity | n/a (no record) | NULs removed, removal logged with per-field counts |
| Other audit paths | unaffected | unaffected |
| User-visible behaviour | none | none |

## Verification plan

1. **Reproduce first, then fix.** Call `_log_interaction_async` directly with
   `context="abc\x00def"`; confirm it raises today and writes a row after the change.
2. Confirm the warning fires with `nul_bytes_removed: 1` and the stored `context` reads `abcdef`.
3. Re-run benchmark query #13 (*ISO 27001:2022 cloud security controls*) — the one that failed
   tonight — and confirm an `audit_logs` row now appears for it.
4. `pytest` (expect 50/50) and `smoke_test.py` (expect 44/44) against the test stack, `:8002`.
5. Confirm no regression in normal logging: a query with no NUL writes exactly as before and emits
   **no** warning.

Steps 1–3 cost zero Groq tokens if done against a stored context string rather than a live query;
only step 3 needs one real call.

## Footnote — this bug cost us one query tonight, and the same trail saved the other 32

The 2026-09-25 benchmark run was killed at query 33 before writing its results file. All 33
results were recoverable **from `audit_logs`** — every query, response and source list was there.
Query #13 was the single unrecoverable one, because of this bug.

The audit trail turned out to be the only durable record of a run that otherwise lost ~100k tokens
of budget for nothing. That is an argument for fixing its one known hole, and also for not relying
on it as a backup by accident — see `Benchmark_Durability_refactor.md`.
