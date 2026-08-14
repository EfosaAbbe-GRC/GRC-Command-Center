# TPRM Genuine Dogfooding Pass — Meridian Cloud Storage

**Status:** ✅ EXECUTED (2026-08-13). First judgment-driven, non-fixture data the app has held,
immediately following the TPRM Tier 4 reset (`TPRM_Tier4_TestDataHygiene_refactor.md`) that
purged 608 vendors of 100%-test-generated noise. This is the "genuine hands-on personal-use pass"
flagged as the standing recommendation in `task.md`/`HANDOFF.md` since 2026-08-06.

**Scope actually covered vs. not:** this pass drove the real backend API on the dev stack
(`localhost:8001`) end to end — the same endpoints `VendorRiskTerminal.jsx` calls — with individually
reasoned judgment calls at every stage, not scripted/placeholder text. **It did not click through the
actual React UI**: no browser-automation tool was available in this session (earlier Playwright
passes — see `SESSION.md`'s 2026-08-06 entry — used a tool that isn't present here). This is
API-layer dogfooding, not the full UI dogfooding originally envisioned. A follow-up browser pass
(manual, by the user, or a future session with Playwright available) against this exact data is the
natural next step to close that gap — see Open Items below.

## What was built

One fictional-but-realistic vendor, **Meridian Cloud Storage**, with two integrations exercising
both directions, both a CRITICAL and a LOW risk tier, and a mix of `pass`/`gap`/`not_applicable`
stage outcomes with real compensating-control reasoning — deliberately not a clean run, since the
gap → risk-acceptance → approve-with-exceptions path is the module's most legally/architecturally
loaded workflow (the immutable-sign-off "Mufasa interview story" per the Tier 4 doc) and the one
least exercised by a trivial happy-path fixture.

- **Egress — "Nightly Customer PII Backup Export"** (file transfer, PII + GDPR/PCI, 15,000
  rows/transfer → **CRITICAL** tier, correctly computed). 13 stages reasoned through: 11 `pass`, 2
  deliberate `gap` (manual/undocumented SSH key rotation; vendor's 72hr breach-notification window
  vs. our 24-48hr policy). Both gaps evidenced, then risk-accepted by admin (90-day expiry, matching
  the CRITICAL reassessment cadence) and the integration approved with exceptions.
- **Ingress — "Quarterly DR Restore-Test File Return"** (file transfer, synthetic/internal data
  only, low volume → **LOW** tier, correctly computed). 13 stages reasoned through: 10 `pass`, 1
  `gap` (IR playbook doesn't name this ingress path), 2 genuine `not_applicable` (rate limiting
  doesn't apply to a ~4x/year manual push; the inbound compliance clauses don't apply to
  non-regulated synthetic data) — each with a written justification, since the API requires one for
  `not_applicable` and rejects the submission otherwise.
- **2 evidence files uploaded and linked** (a fictional SOC 2 Type II excerpt, a fictional executed
  DPA excerpt — both explicitly labeled as fictional test artifacts inside the file content itself).
- **3 risk acceptances signed** by admin, correctly rejected when attempted by analyst (403).
- **Both integrations approved with exceptions** by admin, correctly rejected when attempted by
  analyst (403).
- **RBAC boundaries probed directly, not assumed:** unauthenticated → 401; viewer → 403 on both
  read and write TPRM endpoints (worth knowing explicitly: `TPRM_VIEW` requires `analyst`+, so the
  `viewer` role cannot see TPRM data at all, not just write it — a real product characteristic, not
  a bug, but easy to not notice without testing it directly); analyst → 403 on sign-off/approve/
  export.
- **Vendor-level tier rollup verified live:** `Meridian Cloud Storage` correctly recomputed to
  **CRITICAL** (max severity across its CRITICAL + LOW integrations), not overwritten by the
  later-created LOW integration.
- **CSV export verified**, admin-only (analyst correctly 403'd), content contains both real
  integration names and the vendor name.

## Method

One-off Python script (`dogfood_tprm_pass.py`, kept in the session scratchpad, **not committed to
this repo** — it's a driver for a manual exercise, not a new permanent fixture generator; committing
it would work against the same test-data-hygiene principle Tier 4 just fixed). 61 assertions across
login, RBAC boundaries, vendor/integration creation, all 26 stage submissions, evidence upload, risk
acceptance sign-off, approval, summaries, vendor tier recompute, and reporting endpoints — **61/61
passed**. Backend logs (`docker logs grc-backend`) cross-checked for the same window: every event is
an expected `Security Event` log line (logins, `FORBIDDEN` denials, `TPRM_STAGE_NOT_APPLICABLE`,
`TPRM_EVIDENCE_LINKED`, `TPRM_RISK_ACCEPTANCE`, `TPRM_APPROVE_WITH_EXCEPTIONS`) — no unhandled
exceptions or tracebacks. DB state cross-checked directly via `psql` (not just trusting API
responses): 2 integrations, 21/3/2 stage-response status split (pass/gap/not_applicable, sums to 26
as expected), 3 risk acceptances, 2 evidence links — all matching what the API reported.

## Result: no application bugs found

Unlike the 2026-08-06 UI pass (found the `expandedStage` collapse bug) and the Tier 4 pass (found two
hardcoded-container test-scaffolding bugs), **this pass found zero bugs in the actual TPRM module
logic.** Risk tiering, the deny-by-default approval gate, the GAP-only risk-acceptance validation,
RBAC enforcement at every boundary, the vendor-tier max-severity rollup, evidence linking/hashing,
and CSV export all behaved exactly as documented under genuine, non-trivial, judgment-driven input.
That's a real (negative) finding worth recording, not just an absence of news — the backend has now
been exercised by something closer to real use than any prior pass, and held up.

## Open items

1. **Real browser/UI verification against this exact data is still outstanding** — this pass proves
   the API surface is sound; it says nothing about whether `VendorRiskTerminal.jsx` renders 26 mixed-
   status stages, 3 risk acceptances, and a CRITICAL/LOW vendor rollup cleanly, or whether the CSV
   download button actually works end-to-end from the browser (the 2026-08-06 pass caught a real
   auth-header bug in exactly that kind of button). Next session with browser tooling available
   should pick this up against `Meridian Cloud Storage` rather than throwaway data.
2. **The `expandedStage` panel-collapse bug fixed 2026-08-06** was re-exercised indirectly (multiple
   sequential stage submissions per integration) but only through the API — the fix itself is a
   frontend behavior (`openIntegration`'s `resetExpanded` option) that this pass cannot verify without
   a browser.
3. This vendor/integration data is now real (non-test-fixture) dev-stack state — it should **not**
   be swept up by any future TPRM Tier-4-style cleanup pass; if a future session finds it during a
   vendor-count check, it's expected, not noise to purge.
