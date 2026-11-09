# Export safety, viewer landing, safe retries (three issues found during the risk register)

**Status: ✅ EXECUTED 2026-11-08 (owner's EXECUTE: "execute with all the fixes", after a
re-assessment).** Found while executing `Risk_Register_refactor.md` (§10). No Groq used.

## The three issues, as found

| # | Issue | Effect |
| --- | --- | --- |
| F1 | The Vendor Risk and Compliance CSV exports write cells as typed. A cell starting with `=`, `+`, `-`, `@`, tab or CR runs as a formula when the file is opened in a spreadsheet (CSV injection, OWASP) | A vendor name, gap description or note can run on the reviewer's machine |
| F2 | The Compliance terminal was shown to viewers, but its data needs `RAG_QUERY` (analyst), and it was everyone's default tab | Every viewer logged in to a 403 |
| F3 | `fetchWithRetry` retried **every** failure 3 times with 1/2/4 s backoff | A refusal took ~7 s to show; a save that hit a network or server error was **sent again**, which could duplicate a record that the append-only history then keeps for good |

## Re-assessment before EXECUTE (owner's request)

| # | Found | Decision |
| --- | --- | --- |
| RA1 | The exports' section markers (`--- INTEGRATIONS ---`) start with `-`; a blanket guard would turn them into `'--- …` | Guard **data rows only**; tests pin the markers unchanged |
| RA2 | 401 and 429 mean the server didn't process the request, so resending is safe for any method; network errors and 5xx don't tell you | Resend writes only after 401 (once, with a fresh token) or 429; retry network/5xx for reads only; never retry other 4xx |
| RA3 | FastAPI validation errors are a list; the client showed them as `[object Object]` | Readable `field: message` text |
| RA4 | **Uploads and downloads skipped the silent token refresh.** The access token lives 15 min and the 5-minute heartbeat calls a public route, so it never refreshes it. After 15 idle minutes an evidence upload (the Vendor Risk walkthrough) or any export failed with 401 | Refresh once and resend once (safe: a 401 wasn't processed). **Proven on dev before the fix:** a 16-minute idle test, then Export → 401, no file, nothing on screen |
| RA5 | The refresh path could recurse without limit if the resent request was refused again | One refresh per request |
| RA6 | The tab list lived in the switcher, the default tab in `App.jsx`: two places that had already drifted | One list, `src/lib/terminals.js`; App opens the first tab the role can use and never renders one it can't |
| RA7 | The Risk Register export button had no error handling (failures only reached the console) | Shows the error on screen |
| RA8 | **Vendor Risk is frozen** for the owner's walkthrough | Owner left the call to Claude. Fixed, because it's a security issue, and the change is confined to the export function (three data rows wrapped, one import); no screen, stage, verdict or rule changed. The full `test_tprm.py` suite passes unchanged |
| — | `src/components/AgentStatus.jsx` is unused and calls a non-existent route without a token | Noted only (dead code, not imported anywhere) |

## Changes

| File | Change |
| --- | --- |
| `backend/core/export_safety.py` (new) | `csv_safe`, `safe_row`: the one guard for every export (moved from `risk_scoring.py`, which re-exports it) |
| `backend/core/tprm.py` | `export_tprm_csv`: the three data `writerow` calls wrapped in `safe_row` |
| `backend/main.py` | `export_compliance_csv`: the two data `writerow` calls wrapped |
| `src/lib/api.js` | safe retry rules (RA2), one refresh per request (RA5), readable errors (RA3), refresh for upload/download (RA4) |
| `src/lib/terminals.js` (new), `TerminalSwitcher.jsx`, `App.jsx` | one tab list; Compliance minimum role analyst; role-aware landing tab |
| `src/terminals/RiskRegisterTerminal.jsx` | export errors shown |
| `backend/tests/test_export_safety.py` (new) | formula cells neutralised in the TPRM export; section markers unchanged in both exports |

## Verification

| Check | Result |
| --- | --- |
| `test_export_safety.py` before the fix | **red** (TPRM export passed `=HYPERLINK(…)` through); the two marker tests green, as guards |
| after the fix | 3 passed; `test_tprm.py` unchanged and green |
| Browser, test stack | viewer: one tab (Risk Register), lands on it, **no 4xx**; admin 7 tabs, analyst 6, no 4xx after login; a refusal shows in **0.2 s** and a validation error in **0.1 s** as `reason: String should have at least 3 characters`; each refused request sent **once** |
| Idle test, dev, **before** the fix (16 min, then Export) | **401, no download**, error only in the console |
| Idle test, dev, after the fix | **file downloaded** (`risk_register.csv`); one 401 logged by the browser for the first attempt, then the refresh and resend succeeded |
| Full pytest, test stack | **293 passed, 1 skipped**, 17 deselected (Interview Simulator + image tests) |
| Dev after deploy | readiness ready, audit chain 6/6 intact, posture (read-only) 14 passed, `golden_mappings.json` unchanged (`597b6908…`); viewer lands on Risk Register and admin on Compliance, no 4xx. Smoke not re-run (uses Groq; next weekend) |
