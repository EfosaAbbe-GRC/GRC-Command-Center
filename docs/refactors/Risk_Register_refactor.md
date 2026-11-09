# Phase 1 of the linked data model: risk register (entities, risks, risk history)

**Status: ✅ EXECUTED 2026-11-08 (owner's EXECUTE, all §9 recommendations taken; re-assessed first, §0; record §10).** Drafted 2026-11-08. Blueprint:
`Linked_Data_Model_refactor.md`. No Groq needed (no LLM call anywhere in this change), so it can be
executed on a weekday. **Does not touch any TPRM code** (the owner's Vendor Risk walkthrough is
still open); the gap → risk link is Phase 1b.

## 0. Re-assessment before EXECUTE (2026-11-08, owner's request; owner took all §9 recommendations)

Re-read against the code before building. Changes to the plan below, each reflected in the
sections that follow:

| # | Found | Change |
| --- | --- | --- |
| R1 | §5 had smoke create a risk on every stack. Risks can't be deleted (T2), so each dev smoke run would leave permanent junk in the register the owner will use | Smoke stays **read-only**: list as viewer, refusal checks only. Creation is tested by pytest on the test stack only |
| R2 | CSV export: a cell starting with `=`, `+`, `-`, `@`, tab or CR runs as a formula when opened in Excel (CSV injection) | T9 added: export neutralises such cells. **Same gap in the existing TPRM export** (`tprm.py` `export_tprm_csv`): flagged to the owner, not fixed here (TPRM freeze, one change at a time) |
| R3 | Acceptance could be proposed before residual risk was rated; 6.1.3 f is about **residual** risk | Proposal requires a residual rating |
| R4 | A later change to the owner or the ratings would leave an acceptance standing that the current owner never gave | Changing owner, inherent or residual rating, or treatment **voids** an active or pending acceptance, recorded in the event |
| R5 | No length limits on free text | Limits on every text field (title 200, statement/plan/controls 4,000, reason 1,000) |
| R6 | `verify_audit_chain.py` has its own table list | Already corrected in §4 |
| R7 | The posture test that copies a row needs a `risk_events` row; a fresh test DB has none | Its fixture creates one risk through the API, on the test stack only |
| R8 | Score inputs testable only through the live stack | Pure scoring rules move to `core/risk_scoring.py` (no DB imports), unit-tested in CI's unit job |
| R9 | Status set by hand can drift from the facts (e.g. "accepted" with no acceptance) | Status is **derived** server-side from the record; only *closed* is set explicitly |

## 1. Why

The app has no risk register (verified 2026-11-08: none of the 15 tables holds risks; no code uses
likelihood, impact, inherent/residual or risk owner). ISO/IEC 27001:2022 requires the organisation
to identify risk owners (6.1.2 c 2), assess consequence and likelihood and determine risk levels
(6.1.2 d), compare them with defined acceptance criteria (6.1.2 a, e), choose treatments (6.1.3 a),
obtain **risk owners'** approval of the treatment plan and acceptance of residual risk (6.1.3 f),
reassess at planned intervals and retain the results (8.2). The standard doesn't require a
"register" by name; a register is the normal way to hold that documented information. Today the
app can show none of it, and the only risk-adjacent records are vendor tiers and vendor-stage
acceptances.

## 2. Threats first (what could make this register lie)

| # | Threat | Control in this change | Test |
| --- | --- | --- | --- |
| T1 | A rating, owner or treatment is quietly changed to look better, and the old value is lost | Every change writes `risk_events` (before/after, actor from the token, reason). Table is append-only and hash-chained (added to `PROTECTED_TABLES`) | edit → event exists with both values; `grc_app` UPDATE/DELETE on `risk_events` refused; chain verifies |
| T2 | A risk is deleted to hide it | No DELETE route; `grc_app` has no DELETE on `risks`/`entities`; closing needs a reason | DELETE → 405; posture test |
| T3 | Someone approves their own acceptance | `RISK_APPROVE` is admin-only; the recording admin must differ from the user who proposed the acceptance | same user → 403 |
| T4 | Acceptance recorded without the risk owner (6.1.3 f) | Acceptance requires `accepted_by_owner` (the owner's name, matching the risk's owner) plus the admin who recorded it; optional evidence file via the existing evidence register | missing/mismatched owner → 422 |
| T5 | Invented or out-of-range scores | Likelihood and impact are 1–5 (DB CHECK); scores and bands computed server-side; the API rejects any client-sent score; residual can't exceed inherent | 0/6 → 422; residual > inherent → 422 |
| T6 | Two people edit at once and one silently overwrites the other | Optimistic locking: every PATCH carries `version`; mismatch → 409 | concurrent edit → 409 |
| T7 | Acceptances never expire, reviews never happen | Acceptance max 365 days; `review_due` set on every assessment by band; overdue shown in the list | expiry > 365 → 422; overdue filter |
| T8 | A viewer or analyst exceeds their role | Capabilities `RISK_VIEW` (viewer), `RISK_EDIT` (analyst), `RISK_APPROVE` (admin), seeded like `TPRM_*` | role matrix test |
| T9 | An exported register cell runs as a spreadsheet formula on the reviewer's machine (R2) | Cells starting with `= + - @`, tab or CR are prefixed with `'` | export test with a `=HYPERLINK(...)` title |

## 3. Data model

**`entities`** (the shared anchor every later phase uses): `id` uuid; `name`; `entity_type`
(organisation, business_unit, process, application, asset, vendor); `vendor_id` (nullable FK to
`vendors`, unique; reading the vendors table needs no TPRM code change); `description`; `owner`;
`created_by`, `created_at`. Unique (`entity_type`, `name`).

**`risks`** (mutable, history in `risk_events`):

| Field | Notes |
| --- | --- |
| `id` uuid, `ref` | `ref` = human-readable `R-0001` from a sequence |
| `title`, `statement` | statement written as cause → event → consequence |
| `category` | information_security, operational, compliance, third_party, privacy, strategic |
| `entity_id` | FK `entities` (what is at risk) |
| `owner` | free text: the accountable business person or role (owners usually have no app login) |
| `inherent_likelihood`, `inherent_impact` | 1–5, CHECK |
| `existing_controls` | free text until Phase 3 replaces it with control links |
| `residual_likelihood`, `residual_impact` | 1–5, CHECK; nullable until assessed |
| `inherent_score`, `residual_score` | generated columns, L × I |
| `treatment` | undecided, mitigate, accept, transfer, avoid |
| `treatment_plan`, `target_date` | required when treatment = mitigate |
| `status` | identified → assessed → treatment_in_progress / accepted → closed (reopen allowed) |
| `acceptance_expires_at` | cached from the latest acceptance event |
| `review_due` | set on each assessment: critical 90 d, high 180 d, medium/low 365 d (same cadence as TPRM tiers) |
| `version`, `created_*`, `updated_*` | optimistic lock; actors from the token |

**Bands (5 × 5, L × I):** 1–4 low, 5–9 medium, 10–16 high, 20–25 critical. This is the risk
criteria 6.1.2 a) asks the organisation to define; the standard doesn't prescribe a matrix. Kept as
one documented constant so it can change later without a migration.

**Acceptance criteria (proposed default, owner decides):** low and medium residual can be accepted;
high needs an acceptance of at most 180 days; critical can't be accepted (must be treated).

**`risk_events`** (append-only, hash-chained): `id` bigserial; `risk_id`; `event_type` (CREATED,
UPDATED, ASSESSED, TREATMENT_SET, ACCEPTANCE_PROPOSED, ACCEPTED, CLOSED, REOPENED); `changes` jsonb
(field → before/after); `reason` (required for rating changes, ACCEPTED, CLOSED); `actor`; for
ACCEPTED also `accepted_by_owner`, `expires_at`, `evidence_chain_id` (optional); `at`.

## 4. Code changes

| File | Change |
| --- | --- |
| `backend/core/risk_register.py` (new) | models, schemas, scoring/band functions, router (pattern of `tprm.py`) |
| `backend/core/security_config.py` | `PROTECTED_TABLES` += `risk_events` |
| `backend/core/migrate.py` | import the module; `BLOCKER_PREFIX["risk_events"]`; `REVOKE DELETE ON risks, entities FROM grc_app` |
| `backend/main.py` | include router at `/api/v1/risks` and `/api/v1/entities`; seed `RISK_VIEW`/`RISK_EDIT`/`RISK_APPROVE` |
| `scripts/verify_audit_chain.py` | its own hard-coded `TABLES` list (line 17) += `risk_events`; better, import `PROTECTED_TABLES` so the two lists can't drift (a guard test pins them equal) |
| `src/terminals/RiskRegisterTerminal.jsx` (new) + `src/App.jsx` | new terminal, minimum role viewer |
| `backend/tests/test_risk_register.py` (new), `test_db_posture.py`, `smoke_test.py` | tests below |

**API:** `GET /risks` (filters: status, entity, owner, band, overdue) · `GET /risks/{id}` (with
history) · `POST /risks` · `PATCH /risks/{id}` (`version` + `reason`) · `POST /risks/{id}/propose-acceptance`
(analyst) · `POST /risks/{id}/accept` (admin, ≠ proposer, owner named) · `POST /risks/{id}/close` ·
`POST /risks/{id}/reopen` · `GET /risks/heatmap` · `GET /risks/export` (CSV, `EVIDENCE_EXPORT`) ·
`GET/POST /entities`. Every write broadcasts `{"type": "RISK_REGISTER_CHANGED"}`.

**Terminal:** register table (ref, title, entity, owner, inherent and residual band chips,
treatment, status, review due, overdue flag), filters, a 5 × 5 heat map with an inherent/residual
toggle, a detail panel with the full history timeline, and forms for create, assess, treat,
propose acceptance, accept (admin) and close. Empty state explains how to add the first risk.

## 5. Tests first (all red before any code)

`test_risk_register.py`: band boundaries (4/5, 9/10, 16/20); residual > inherent rejected;
client-sent score ignored or rejected; role matrix for every route; acceptance by the proposer → 403;
acceptance without the owner's name → 422; acceptance > 365 days → 422 and critical residual → 422
(if decision 3 holds); every write creates exactly one event with correct before/after; version
conflict → 409; DELETE → 405; export columns. `test_db_posture.py`: `grc_app` can't UPDATE/DELETE
`risk_events` and can't DELETE `risks`/`entities`; `risk_events` has blockers and the chain trigger.
`smoke_test.py`: read-only (R1): no-token 401, viewer can list risks, viewer refused on create (44 → 47 checks); nothing is written.

## 6. Verification

| Check | Expected |
| --- | --- |
| New tests | red → green |
| Full pytest (from `backend/`) | 211 passed + the new tests, 6 skipped |
| `verify_audit_chain.py --test` | 6/6 tables intact |
| Readiness on dev | ready, audit chain 6/6 |
| Smoke, test stack and dev | 47/47 |
| Browser pass | create, assess, accept, close one risk as the right roles; a viewer sees no edit controls |
| **Owner's acceptance test** | enter three practice-scenario risks (one mitigated, one accepted, one closed); record worked / friction / couldn't per screen |

## 7. Rollback

`git revert` and rebuild. The new tables are additive and left in place (harmless; `risk_events` is
protected by design and can't be dropped by the app role). No existing table changes shape.

## 8. Out of scope here

Gap → risk link and vendor entities auto-created (Phase 1b, after the walkthrough); controls and the
Statement of Applicability (Phase 3); issues and corrective actions (Phase 2); Executive changes and
metric history (Phase 4); any AI assistance.

## 9. Decisions for the owner (recommendation first)

1. **5 × 5 matrix, L × I, the four bands above.** Recommended: it's the common convention and easy
   to defend; the criteria are documented as the organisation's own choice (6.1.2 a).
2. **Risk owner as free text** (a person or role) rather than an app user. Recommended: owners are
   business people; the admin records their acceptance (6.1.3 f) with optional evidence.
3. **Acceptance criteria:** low/medium acceptable; high ≤ 180 days; critical not acceptable.
   Recommended as the starting default.
4. **Recording admin ≠ proposer.** Recommended (segregation of duties).

## 10. Execution record (2026-11-08, owner's EXECUTE)

**Order:** re-assessment (§0, 9 corrections) → tests written → **red** against the old test-stack
image (36 failing; the unit module failed at import) → code → test stack rebuilt → green → browser →
dev deployed.

| Check | Result |
| --- | --- |
| `test_risk_scoring.py` (unit, CI-safe) | 50 passed |
| `test_risk_register.py` (test stack) | 26 passed. Two first failed on **my test data** (a 2-character reason, rightly refused by the 3-character minimum), which also meant the owner-name test had been passing for the wrong reason; fixed, and it now asserts the owner message |
| `test_db_posture.py` (test stack) | green incl. `risk_events` blockers and chain, no UPDATE/DELETE on it, no DELETE on `risks`/`entities`, UPDATE still allowed |
| `test_security_config.py` | pinned set updated five → six tables (`test_six_protected_tables`): the reviewed change it exists to catch |
| Full pytest, test stack | **290 passed, 1 skipped**, 17 deselected (Interview Simulator: Groq, code untouched; image tests) |
| Migration (test, dev) | `sealed 0 pre-chain rows of risk_events`; grants applied |
| `verify_audit_chain.py` | dev **6/6 intact** (`risk_events` 0 rows); test 6/6 (102 events) |
| Readiness, dev | ready, audit chain **6/6** |
| Smoke, dev (one run: the v12 run had used most of the day's Groq budget) | **47/47**; register still 0 items afterwards (R1 holds) |
| `test_db_posture.py`, dev (read-only) | 14 passed, writes skipped by design |
| Container `golden_mappings.json`, dev | unchanged (`597b6908…`): v12's no-mapping-change rule holds |
| Browser, test stack (local Vite → :8002) | analyst: entity, risk, assess/treat with reason, propose; admin: records the owner's acceptance; viewer: reads, no write controls; the analyst never sees the record button |
| Browser, dev | Risk Register tab, empty state, no console errors |

**Found, not fixed (outside this change):** (1) the TPRM CSV export has the same formula-injection
gap (R2); (2) a **viewer's default tab is Compliance**, whose `/compliance/policies` needs analyst,
so a viewer lands on a 403 (pre-existing); (3) `fetchWithRetry` retries 4xx responses with backoff,
so a refused action takes seconds to show its error (pre-existing UX). Owner to decide.

**Next:** the owner's acceptance test (§6, last row) with practice-scenario risks; then Phase 1b
after the Vendor Risk walkthrough.
