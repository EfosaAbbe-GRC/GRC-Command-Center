# Smoke test: keep the chat check out of the active-auditor's Groq minute

**Status:** EXECUTED 2026-10-04 (EXECUTE from Efosa). Dev smoke **44/44** — waited 60 s, chat
answered with 6 sources (was 43/44 twice). **Test stack: not verified** — the run that followed got
43/44 because the org-wide **daily** budget was spent (Groq log: TPD 199,708 / 200,000 used, after
v9 + three smoke runs + pytest). The wait itself ran (60 s). Re-run the test-stack smoke on a fresh
day. **Was:** DRAFT 2026-10-04. Approved in principle by Efosa 2026-10-04 ("yes"
to v9 decision c/d). Tests-only; no rebuild.

## Problem

`smoke_test.py` triggers `active-auditor` (several real RAG calls) and, ~12 s later, the "Chat
endpoint" check. Together they exceed Groq's **8,000 tokens/minute** limit, so the chat call gets a
429 and the suite reports "FAIL Chat generation". Seen twice on dev 2026-10-04 (log: `Used 5398,
Requested 2759`). The failure is the test's own timing, not the app — a standalone chat right
after passed. It hides real chat failures behind a known false one, which is the outcome this check
was added to prevent (2026-08-17, `RAG_Model_Outage_refactor.md`).

## Change — `backend/tests/smoke_test.py`

```python
# after the active-auditor test:
AUDITOR_DONE = time.monotonic()

# immediately before the "Chat endpoint" test:
# Groq's TPM window is per minute; the auditor's RAG calls and this chat share it otherwise.
TPM_WAIT = float(os.getenv("GRC_SMOKE_TPM_WAIT", "62"))
wait = TPM_WAIT - (time.monotonic() - AUDITOR_DONE)
if wait > 0:
    print(f"     ⏳ waiting {wait:.0f}s so chat doesn't share the auditor's Groq minute")
    time.sleep(wait)
```

Adds up to ~50 s to a run (the tests between the two already take some seconds). Override with
`GRC_SMOKE_TPM_WAIT=0` for a stack without Groq limits.

## Verification

Run smoke against dev (`GRC_TEST_BASE=http://localhost:8001`) → expect **44/44**, and against the
test stack → **44/44**. ~9k Groq tokens each; not on a benchmark day.
