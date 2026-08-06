# TPRM Module — Implementation Roadmap (What Comes Next)

**Created:** 2026-07-21 · **Status of base module:** APPLIED & LIVE-VERIFIED (see `TPRM_Integration_refactor.md`).
Smoke 42/42, pytest 10/10, auto-seeds on boot. This roadmap is the backlog *after* that baseline.

Each item: **what · why · where · effort (S≈hours / M≈day / L≈multi-day) · depends-on**. Ordered within tiers.
Two lenses noted where they diverge — **security-parity** (your stated priority) vs **user-value** (making the terminal actually useful day-to-day).

---

## Tier 1 — Close security & parity gaps (do first; small, high assurance)

**✅ TIER 1 COMPLETE (2026-08-02)** — 1.1 through 1.5 executed per `TPRM_Tier1_refactor.md`
(now marked EXECUTED). Verified: smoke 42/42, pytest 21/21 (16 TPRM incl. 6 new, 5 IAM regression
check). Next up per the Recommended sequence below: **2.4**.

**1.1 Audit-log the privileged TPRM actions** — S
- *What:* emit `log_security_event(...)` on approve and risk-acceptance sign-off (and optionally integration create).
- *Why:* every other privileged action in the app writes to the security audit trail (`main.py` login/policy/ingest all call `log_security_event`). TPRM sign-off currently does **not** — a gap for a module whose whole point is defensibility. "Who approved this vendor, and when" must be in the immutable trail, not just inferable.
- *Where:* `core/tprm.py` `approve_integration` + `create_risk_acceptance`; inject `request`, call `log_security_event`.
- *Depends-on:* nothing.

**1.2 Read-back for risk acceptances + stage evidence** — S/M
- *What:* `GET /tprm/integrations/{id}/risk-acceptances` (list), and extend the stage read to include `evidence_notes`, `reviewed_by`, `reviewed_at`.
- *Why:* the acceptances table is **write-only** through the API today — you can sign one but never retrieve it. An append-only record you can't read isn't usable evidence. Same for stage review metadata (who reviewed, when, with what note).
- *Where:* `core/tprm.py` new route + widen `StageOut`.
- *Depends-on:* nothing. (Enables UI 2.2.)

**1.3 Expired-acceptance detection** — M
- *What:* a check (endpoint `GET /tprm/acceptances/expiring` + a status re-evaluation) that flags `approved_with_exceptions` integrations whose covering acceptance has lapsed (`expires_at < now`).
- *Why:* `approve` already refuses expired acceptances, but an integration approved *yesterday* silently becomes non-compliant when the acceptance expires — nothing surfaces it. A signed exception with an expiry that nobody watches is a latent finding.
- *Where:* `core/tprm.py`; mirrors the `reassessments/due` pattern.
- *Depends-on:* 1.2 (shares the acceptance read logic). Feeds Tier 3 reassessment surfacing.

**1.4 `BEFORE TRUNCATE` triggers on the immutable tables** — S
- *What:* add `BEFORE TRUNCATE` triggers to `risk_acceptances` (and, for completeness, `audit_logs` / `evidence_chain`).
- *Why:* row-level `BEFORE UPDATE/DELETE` triggers **do not fire on `TRUNCATE`** — so today an owner-level `TRUNCATE` bypasses the immutability guarantee. Low likelihood (needs elevated DB privs), but it's a real hole in an "immutable" claim.
- *Where:* `core/database.py` `init_db()`, alongside the existing trigger block.
- *Depends-on:* nothing. Touches shared hardening code — test the existing audit/evidence immutability still passes.

**1.5 Per-tier reassessment cadence** — S · *decision #2*
- *What:* `REASSESSMENT_DAYS_BY_TIER = {CRITICAL: 90, HIGH: 180, MEDIUM: 365, LOW: 365}`; use it in `create_integration` (replaces the flat hardcoded `365d`) and on any future tier recompute.
- *Why:* risk-proportionate reassessment. Today every integration gets 365d regardless of tier; a CRITICAL PHI feed should recur quarterly.
- *Where:* `core/tprm.py` `create_integration` (near `compute_risk_tier`).
- *Depends-on:* nothing. Feeds 3.1.

**1.6 Test isolation + the product bug it uncovered** — *found & largely fixed 2026-07-22*
- **✅ PRODUCT BUG (the real find) — FIXED & VERIFIED LIVE 2026-07-22:** `change-password` 500'd because `database.py` wrote **tz-aware** `datetime.now(timezone.utc)` into `User`/`Policy` columns that are `TIMESTAMP WITHOUT TIME ZONE` (naive) — asyncpg `DataError`. SQLite tolerated this; Postgres does not. Impact: **forced-reset recovery was broken in prod** (a `must_change_password` user could never clear it); `update_last_login` was also silently failing. Fixed via `_naive_utcnow()` (4 call sites). Verified post-rebuild: locked admin self-recovers via `/auth/change-password` → 200, `mcp` cleared.
- **✅ DONE & VERIFIED:** `backend/tests/conftest.py` autouse guard clears the forced-reset flag before each test + a session finalizer (cascade eliminated: `11 failed/4 passed` → **`15 passed`**, stable across reruns; admin ends unlocked). `force_reset_util.py` now has `--unlock`.
- *Future (separate, low priority):* (a) migrate those columns to `TIMESTAMPTZ` for correctness rather than storing naive UTC; (b) the suite is single-worker/`NullPool` and can occasionally `ReadTimeout` on a request under heavy back-to-back load — bump per-request timeouts or reduce parallelism if it recurs.
- *Original why (for context):* the IAM password-lifecycle tests mutate a shared mutable admin and didn't clean up on failure — one failed `iam_05` deterministically 403-cascaded the whole suite (`11 failed / 4 passed`); TPRM itself was `10/10` in isolation. The `conftest.py` guard now neutralizes that class of bug for any admin-touching test, not just these two.
- *Still optional:* add `try/finally` inside `test_iam_05`/`_07` themselves so they self-restore even without the conftest safety net (defence in depth).

---

## Tier 2 — Complete the workflow & unlock the framework's value (medium)

**✅ 2.1 COMPLETE (2026-08-02)** — executed per `TPRM_Tier2_2.1_refactor.md` (now marked EXECUTED).
`StageOut` widened with `guidance`/`review_questions`/`evidence_to_collect`; `VendorRiskTerminal.jsx`
stage rows now expand into a detail panel. No schema risk this time — additive read-only fields
only. Verified: smoke 42/42, pytest 25/25, plus a manual API check confirming real content flows
through. Next up per the Recommended sequence: **2.2** (UI risk-acceptance form).

**2.1 Surface stage guidance in the UI** ⭐ *highest user-value item* — M
- *What:* show each stage's `guidance`, `review_questions`, and `evidence_to_collect` in a stage-detail panel/drawer.
- *Why:* the seed content is the *product* — the 13-stage methodology's worth is the guidance and evidence checklist. Right now the terminal is just pass/gap/review toggles with the guidance invisible in the DB. This is what turns it from a status board into an actual assessment tool.
- *Where:* `core/tprm.py` (extend stage read or add `GET .../stages/{stage_id}`), `VendorRiskTerminal.jsx` (expand row → detail).
- *Depends-on:* 1.2 (widened stage read).

**✅ 2.2 COMPLETE (2026-08-02)** — executed per `TPRM_Tier2_2.2_refactor.md` (now marked EXECUTED).
Frontend-only (1.1/1.2 already covered the API side): acceptance status embedded in each GAP
stage's detail panel (from 2.1), with a `RiskAcceptanceModal` for admins to sign one. Verified:
smoke 42/42, pytest 25/25, plus a manual end-to-end API check of the exact sign→list round-trip
the modal drives. Not browser-verified (no browser-automation tool this session). Next up per the
Recommended sequence: **2.3** (vendor-level risk rollup).

**2.2 UI risk-acceptance form (admin)** — M
- *What:* a modal for admins to sign a risk acceptance against a GAP stage (gap description, compensating control, expiry), + a panel listing existing acceptances.
- *Why:* the flow is API-only today; the UI can mark a gap but not resolve it. Closes the loop UI-side.
- *Where:* `VendorRiskTerminal.jsx` (new modal, token-styled like `CreateIntegrationModal`).
- *Depends-on:* 1.2 (list endpoint), 1.1 (so the sign-off is audited).

**✅ 2.3 COMPLETE (2026-08-03)** — executed per `TPRM_Tier2_2.3_refactor.md` (now marked EXECUTED).
`_recompute_vendor_tier` (max-severity rollup) hooked into both `create_integration` and both
`approve_integration` success paths; `VendorRiskTerminal.jsx` gained a vendor-portfolio strip
(name + tier-badge chips) and the create-integration vendor dropdown now shows each vendor's tier
inline. New `test_tprm_vendor_rollup` (asserts a later lower-tier integration doesn't downgrade an
already-critical vendor). Verified: smoke 42/42, pytest 26/26, plus a live API check confirming
real tier distribution across 244 vendors (was 100% `unscored` before). Not independently
browser-verified — no browser-automation tool this session; substituted a live API check (same gap
2.2 had). Tier 2 is now fully complete (2.1/2.2/2.3/2.4 all ✅). Next up: **Tier 3** (3.1
reassessment surfacing, per the roadmap's recommended sequence).

**2.3 Vendor-level risk rollup** — S/M
- *What:* compute `Vendor.overall_risk_tier` as the max tier across its integrations (currently hard-stuck at `UNSCORED`).
- *Why:* a vendor with three CRITICAL integrations should read CRITICAL at the vendor level; today the field exists but is never populated. Enables a vendor-portfolio view.
- *Where:* `core/tprm.py` (recompute on integration create/approve), `VendorRiskTerminal.jsx` vendor list.
- *Depends-on:* nothing.

**✅ 2.4 COMPLETE (2026-08-02)** — executed per `TPRM_Tier2_2.4_refactor.md` (now marked EXECUTED).
Found & fixed live: the Postgres `stagestatus` enum type needed `ALTER TYPE ... ADD VALUE` to pick
up `NOT_APPLICABLE` — `create_all()` doesn't retrofit existing enum types. Verified: smoke 42/42,
pytest 25/25. Next up per the Recommended sequence: **2.1** (stage guidance UI).

**2.4 Method-based stage applicability + "Not Applicable" status** — M · *decision #1*
- *What:* (a) honor the seeded `applies_to_methods` field so stages that don't fit the transfer method aren't fanned out on create (e.g. SSH-key auth / MFT on an API integration); (b) add a `NOT_APPLICABLE` `StageStatus` requiring a justification note, treated as "resolved, non-gap" in the approval gate.
- *Why:* proportionality via *documented exclusions*, not tier-based skipping — all applicable stages stay mandatory for every tier, and genuinely-inapplicable ones are closed out auditably.
- *Where:* `core/tprm.py` (stage fan-out filter in `create_integration`; enum + gate logic in `approve_integration`), `VendorRiskTerminal.jsx` (N/A control + justification field).
- *Depends-on:* 1.1 (N/A closures should be audited), 2.1 (surfaced in stage detail).

---

## Tier 3 — Lifecycle & reporting (larger)

**✅ 3.1 COMPLETE (2026-08-03)** — executed per `TPRM_Tier3_3.1_refactor.md` (now marked EXECUTED).
`_broadcast_reassessment_status` (bare `TPRM_REASSESSMENT_STATUS` signal, no payload — the
receiving terminal re-fetches the two existing GET routes) hooked into `create_integration`,
`create_risk_acceptance`, and both `approve_integration` success paths. Event-driven only, no
backend scheduler (none exists in this codebase; a real, accepted limitation is that a due-date
lapsing with zero TPRM activity won't push live — refreshes on mount/reconnect/next action).
`VendorRiskTerminal.jsx` gained a header badge + expandable panel listing real overdue/expiring
items, wired via `useWebSocket`. **Found and fixed a real pre-existing bug along the way:**
`OpsTerminal.jsx`'s WebSocket connection was passing `user?.access_token`, a field that doesn't
exist on the auth-context user object — its telemetry stream had never actually connected. Fixed
via a new `api.getAccessToken()` export, used correctly in both files. Verified: smoke 42/42,
pytest 26/26, plus a one-off WS client script confirming the broadcast frame actually arrives after
`create_integration`. Not browser-verified (no browser tool this session; also no naturally-overdue
data exists yet to visually check the badge against). Next up: **3.2** (CSV export) per the
roadmap's recommended sequence.

**3.1 Reassessment surfacing (no polling)** — M/L
- *What:* a dashboard badge / panel driven by `GET /reassessments/due` and expired-acceptance data, pushed via the **WebSocket event bus** (not `setInterval` — GOVERNANCE §3 bans polling).
- *Why:* `reassessments/due` exists but nothing consumes it. Stage 13 (both directions) is literally "continuous monitoring and periodic reassessment" — the module should embody it, not just store the date.
- *Where:* `core/ws.py` broadcast, `VendorRiskTerminal.jsx` or a small header badge.
- *Depends-on:* 1.3 (expiry), and reuse of the existing WS manager.

**✅ 3.2 COMPLETE (2026-08-03)** — executed per `TPRM_Tier3_3.2_refactor.md` (now marked EXECUTED).
`GET /tprm/export` streams a three-section CSV (Integrations, Stage Assessments, Risk Acceptances)
mirroring `/compliance/export`'s pattern, gated by the existing `EVIDENCE_EXPORT` capability (no
new capability added). **Found and fixed a second real pre-existing bug along the way:**
`ComplianceTerminal.jsx`'s "Export CSV Report" button used `window.location.href`, which sends no
`Authorization` header — since `/compliance/export` isn't a public route, that button was silently
401ing instead of downloading. Fixed via a new shared `api.downloadFile()` helper (authenticated
fetch → blob → client-side download), used by both the fixed compliance button and the new TPRM
export button in `VendorRiskTerminal.jsx`. Verified: smoke 42/42, pytest 28/28 (26 + 2 new,
including an RBAC check), plus a manual `curl` check confirming correct headers, real data, and
403 for non-admin. Not browser-verified. **Tier 3 now 2/3 done.** Next up: **3.3** (evidence
linkage to `evidence_chain`) per the roadmap's recommended sequence.

**3.2 TPRM assessment report export** — M
- *Why:* auditor-facing evidence; parity with `/compliance/export`. The whole point is producing a defensible artifact.
- *Where:* `core/tprm.py` streaming CSV (mirror `main.py` `export_compliance_csv`), gated by an export capability.
- *Depends-on:* 1.2.

**✅ 3.3 COMPLETE (2026-08-04)** — executed per `TPRM_Tier3_3.3_refactor.md` (now marked EXECUTED).
Full file-upload architecture (confirmed over a lighter hash-reference alternative): new
`StageEvidenceLink` append-only table, `POST/GET .../stages/{stage_id}/evidence`, `AuditLogger.
log_evidence` widened to return the row id and propagate exceptions instead of swallowing them.
**Real infra bug found and fixed:** the new evidence Docker volume mounted root-owned on first
creation (unlike `faiss_index`, `data/tprm_evidence` wasn't pre-created+chowned in the Dockerfile),
so uploads 500'd under the non-root container user — fixed in `Dockerfile.backend`, volume
recreated, durability re-verified with an upload-then-rebuild round trip. Verified: smoke 42/42,
pytest 32/32. Not browser-verified. **Tier 3 is now fully complete (3.1/3.2/3.3 all ✅) — the
entire TPRM roadmap (Tier 1 + Tier 2 + Tier 3) is done.** Remaining backlog: Tier 4 (opportunistic
hardening/housekeeping — test-data hygiene, frontend tests) whenever revisited.

**✅ Browser verification pass (2026-08-06)** — 2.3, 3.1, 3.2, and 3.3 had only ever been checked via
API/curl/WS-client; this session drove all four live through a real Chromium browser (Playwright,
admin session) end to end: created a vendor+integration, expanded a stage, marked it `gap`, attached
a real evidence file, signed a risk acceptance, exported the CSV, all against the actual running
frontend at `localhost:3006`. **Result: all four work correctly** — zero console errors, zero failed
network requests across the whole run. Vendor-portfolio strip rendered all 435 real vendor chips
with correct tier coloring (2.3). CSV export downloaded with correct auth, filename, and content,
including the freshly-created row (3.2). Evidence upload appended a real entry (filename, size, hash
prefix, uploader) to the stage panel (3.3). The WS-broadcast → refetch pipeline for reassessment
data fired correctly on every qualifying action (6 GETs to `reassessments/due`/`acceptances/expiring`
across 1 mount + 2 broadcasting actions, matching the code's design exactly) — confirmed the pipeline
itself works, though no due/expiring badge was actually visible on screen this session because
current data has 0 overdue reassessments and 0 expired acceptances (nothing in the corpus is old
enough yet) (3.1).

**One real, previously-undiscovered UX bug found — since fixed (see below):** `openIntegration()`
unconditionally reset `expandedStage` to `null` on every call — and it was called after *every*
stage-status button click (`updateStage`) and after signing a risk acceptance (`onSigned`). So the
stage detail panel collapsed immediately after marking a stage `gap`/`pass`/etc., or right after
signing a risk acceptance — forcing a re-click to see the result of the action just taken. Not
crash-causing, no error, but a genuine papercut in the exact workflow (mark gap → attach evidence →
sign acceptance) this module exists for.

**✅ FIXED (2026-08-06)** — executed per `PanelCollapse_refactor.md` (now marked EXECUTED).
`openIntegration` gained a `{ resetExpanded = true }` option; the two "just refreshing after an
in-panel action" call sites (`updateStage`, `RiskAcceptanceModal`'s `onSigned`) now pass
`{ resetExpanded: false }`, while the left-hand integration-list click keeps the default (reset)
behavior. Rebuilt `grc-frontend`, verified: smoke 42/42, pytest 32/32, plus a dedicated Playwright
regression reproducing the exact original bug scenario — panel now stays open through marking a
stage GAP and through signing a risk acceptance with zero re-clicks, while switching to a different
integration still correctly starts with no stage expanded. 7/7 checks passed, zero console errors.

Verified: smoke 42/42, pytest 32/32 (re-ran clean after the browser session; one transient
`ReadTimeout` on `test_tprm_export_csv` during a first pass immediately after the browser run
reproduced as a pass in isolation and on a full clean rerun — not a regression, just contention from
the dataset now being large, see Tier 4 test-data hygiene below).

**3.3 Evidence linkage to `evidence_chain`** — L
- *What:* let a stage attach real evidence (file hash / chain-of-custody) into the existing immutable `evidence_chain`, instead of free-text `evidence_notes` only.
- *Why:* elevates "evidence" from a note to a tamper-evident, hashed artifact — consistent with how RAG-ingested docs are already chained.
- *Where:* `core/tprm.py` + reuse `AuditLogger.log_evidence`.
- *Depends-on:* 2.1.

---

## Tier 4 — Hardening & housekeeping (opportunistic)

- **4.1 Tier-driven mandatory stage count — SUPERSEDED** by decision #1. All stages stay mandatory per tier; proportionality is handled by **2.4** (method applicability + N/A) instead. Not planned.
- **4.2 Test-data hygiene** — S. Smoke/pytest create vendors/integrations that accumulate; add a cleanup path or a dedicated test schema/marker.
- **4.3 Frontend tests** — M. No component tests exist project-wide; not TPRM-specific, but the create/approve flows are now worth covering.

---

## Recommended sequence (CONFIRMED: security-parity first — "shift left")

1. **Tier 1 in full** (1.1 → 1.2 → 1.3 → 1.4 → 1.5) — small, and it brings TPRM's *auditability* and *lifecycle correctness* to the same bar as the rest of the system. This is the shift-left lead: controls and assurance in before any feature/UX work.
2. **2.4** (method applicability + N/A status) — resolves decision #1 and cleans up assessment correctness before the UX build layers on top.
3. **2.1 (stage guidance)** — biggest jump in day-to-day value; unblocks 2.2 and 3.3.
4. **2.2 + 2.3**, then Tier 3 (3.1 reassessment surfacing → 3.2 CSV export, PDF later → 3.3 evidence linkage).
5. Tier 4 opportunistically alongside the above.

Fastest path to "audit-defensible": **1.1 + 1.2 + 3.2** (log it → read it → export it).

---

## Decisions

**✅ 1. Stage applicability (decided 2026-07-21):** all 13 stages remain mandatory for **every** tier — no tier-based skipping. Proportionality is expressed via (a) `applies_to_methods` to auto-hide stages that don't apply to the transfer method, and (b) a new "Not Applicable" stage status requiring a written justification. Rationale: a documented "assessed & marked N/A because X" is more defensible than a silently skipped stage, and the approval gate stays uniform. Tier drives *cadence*, not *which stages are answered*. → drives **2.4**; supersedes the old 4.1.

**✅ 2. Reassessment cadence (decided 2026-07-21):** per-tier (industry standard). Defaults — CRITICAL 90d, HIGH 180d, MEDIUM 365d, LOW 365d; everyone ≥ annual, plus out-of-cycle triggers on risk-indicator change. → drives **1.5**.

**✅ 3. Export format (decided 2026-07-21):** CSV first (fast, parity with `/compliance/export`), PDF as a follow-on. → shapes **3.2**.

**✅ 4. Priority lens (decided 2026-07-21):** lead with **security-parity (Tier 1)**, consistent with the system's **shift-left** philosophy — auditability and controls get built in *before* the feature/UX layer, never retrofitted. → confirms the Recommended sequence.

*All four decisions resolved — roadmap is ready to execute next session.*
