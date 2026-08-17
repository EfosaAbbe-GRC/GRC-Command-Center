# TPRM Dogfooding — UI/Browser Layer (closes the 2026-08-13 open item)

**Status:** ✅ EXECUTED (2026-08-16). Closes Open Item #1 and #2 of
`TPRM_Dogfooding_Pass_2026-08-13.md`, which drove the backend API end to end but explicitly could
not click through the actual React UI (no browser tooling that session).

**Tooling note:** the blocker is gone. `chromium-cli` still isn't on `PATH` and there is still no
browser MCP tool, but the host's Python `playwright` package works with zero setup
(`p.chromium.launch(headless=True)`, Chromium 141.0.7390.37) — same approach as the 2026-08-06 pass.
Recording this again because the 2026-08-13 session concluded "no browser-automation tool was
available" without checking the Python package; check that first next time.

**Target data:** the real `Meridian Cloud Storage` dogfooding vendor from 2026-08-13 — *not*
throwaway data, per that doc's Open Item #3.

## Method

Two headless Chromium passes against the dev stack (`localhost:3006` → backend `:8001`), logged in
as `admin` through the real login form, plus one focused OpsTerminal probe. Console errors,
`pageerror`s, failed requests, and every 4xx/5xx response were captured continuously across all runs.

**Data safety:** all 26 stage evidence notes were dumped to CSV *before* any mutating click, and the
final DB state was diffed against that backup — **byte-identical, dataset fully restored** (see
Restoration below).

## Result: 2 real bugs found, both invisible to the API-layer pass

### Bug 1 — Marking a stage silently destroys its evidence notes (data loss)

**Severity: high for a GRC tool.** Clicking any of the `pass` / `gap` / `review` status buttons on a
stage **permanently wipes that stage's `evidence_notes`** and reassigns `reviewed_by` to the clicking
user, with no warning, no confirmation, and no undo.

- **Frontend:** `VendorRiskTerminal.jsx`'s `updateStage()` only ever populates `evidence_notes` for
  the `not_applicable` branch (which prompts for a justification). For `pass`/`gap`/`in_review` the
  variable stays `undefined`, and `JSON.stringify` drops undefined keys — so the request body is
  `{"status": "pass"}` with no `evidence_notes` at all.
- **Backend:** `core/tprm.py`'s stage-update handler does
  `stage_response.evidence_notes = payload.evidence_notes` **unconditionally**. Absent key →
  Pydantic default `None` → the existing note is overwritten with `NULL`.

**Confirmed both ways, not inferred:**

- DB layer: stages-with-notes went **26 → 25** after a single UI click; the affected row's
  `evidence_notes` became `NULL` and `reviewed_by` flipped `analyst` → `admin`.
- User-visible layer: the `NOTES` block simply disappears from the open stage panel after the click.
  Nothing tells the user anything was lost.

**Why the 2026-08-13 API pass missed it:** that pass always sent an explicit `evidence_notes` value
on every stage submission, so it never exercised the omitted-field path the UI actually produces.

**Worth noting:** `stage_responses` is *not* covered by the PL/pgSQL immutability triggers that
protect `audit_logs`, `evidence_chain`, and `risk_acceptances` — so nothing at the DB layer catches
this either. The assessment *rationale* (why a control passed) is the thing being destroyed, while
the sign-off artifacts around it are immutable.

**Not fixed** — per `GOVERNANCE.md` draft-first, this needs a proposed diff and an EXECUTE.

### Bug 2 — Operations terminal is unreachable from a clean state (chicken-and-egg deadlock)

`OpsTerminal.jsx:108` early-returns the `OPERATIONAL_WAIT_STATE` empty state whenever `activeJob` is
null, i.e. whenever `/ops/jobs` is empty. That early return sits **above** the header block
(`OpsTerminal.jsx:225-240`) that contains the agent picker and the **Run Agent** button — the only UI
control that can create an agent run.

**So: zero agent runs → no way to start one from the UI. Permanently stuck.**

Confirmed live: with `agent_runs = 0`, the Operations tab rendered only `OPERATIONAL_WAIT_STATE`,
`button[title="Run Agent"]` count **0**, `select` count **0**, role correctly `admin`. After seeding
a single run through the API (`POST /run-agent`, `policy-analyzer`, `run_id: 1`), the same tab
rendered the full console with all three controls (`Run Agent`, `Rerun`, `Stop Agent`) and the button
then worked correctly.

This became reachable precisely *because* of recent legitimate work — TPRM Tier 4's test-data hygiene
plus a stack restart left `agent_runs` genuinely empty, which is exactly the state
`MEMORY.md`'s own gotcha predicted (`/ops/jobs` "returns genuinely empty on a fresh boot with zero
agent executions"). The consequence for the UI just hadn't been walked through.

**Not fixed** — needs a draft + EXECUTE.

## Correction on the record: one reported defect was a false alarm

While reading `src/lib/api.js` this session, `api.post('\run-agent', …)` appeared to contain a
backslash, which in a JS string literal would be `\r` (carriage return) and would have made the
endpoint resolve to `/api/v1un-agent` after URL-parser CR-stripping. **This was wrong.** The file
genuinely contains `'/run-agent'` — verified by character codes (`U+002F`, a real forward slash) and
independently by observing the actual browser request go to `http://localhost:8001/api/v1/run-agent`
and succeed. The backslash was a rendering artifact of the search tool's output on this Windows
setup (the same artifact made `border-white/10` look like `border-white\10` and `/>` look like `\>`
in other files). Recorded here so it isn't "rediscovered" as a bug later — and as a reminder to
confirm this class of finding against raw bytes or live behaviour before reporting it.

## What passed (everything else)

**Zero console errors, zero `pageerror`s, zero failed requests, zero 4xx/5xx responses** across all
three browser runs.

- Vendor portfolio strip renders `Meridian Cloud Storage` with a genuinely colour-coded **CRITICAL**
  badge (`rgb(248, 81, 73)`), not the grey `unscored` fallback — worth checking explicitly because
  `TIER_STYLE`/`STATUS_BADGE_KEY`/`STAGE_ICON` are all keyed lowercase while the DB enums are
  uppercase; the API lowercases them on the way out, so the mapping is correct.
- Both integrations listed with correct tier badges (EGRESS **CRITICAL**, INGRESS **LOW**).
- Header renders `13/13 STAGES REVIEWED` and surfaces `2 OPEN GAP(S)`.
- Status badge correctly resolves `approved_with_exceptions` → **PARTIAL** (not the `QUEUED` fallback).
- All 13 stages render for each integration (26 total).
- Both genuine `not_applicable` stages render as active **N/A** in the UI.
- Expanded GAP stage shows the **RISK ACCEPTED** block with gap description, compensating control,
  and `Accepted by admin · expires 11/11/2026`.
- Expanded stages show Guidance / Review Questions / Evidence to Collect, and reviewer attribution
  (`NOTES — ANALYST`).
- Linked evidence renders with filename, size, hash prefix and uploader
  (`0.4KB · e2def74b3635… · analyst`).
- **CSV export works end-to-end from the browser** — real download captured (10,949 bytes),
  containing the vendor name and both integration names. This is the exact control that carried a
  dead-auth-header bug in a previous pass; it is clean now.
- **The 2026-08-06 `expandedStage` panel-collapse fix holds** — the stage panel stayed open after an
  in-panel status action (closes Open Item #2 of the 2026-08-13 doc).

## Method note: 7 "failures" in run 1 were my own assertion bugs, not app bugs

Run 1 reported 21/28. All 7 failures were case-sensitivity errors in the *test script* — the UI
applies CSS `text-transform: uppercase`, so `inner_text()` returns `NOTES` / `GUIDANCE` /
`RISK ACCEPTED`, and case-sensitive substring checks missed them. Re-run case-insensitively, all 7
passed. Recorded because one of them mattered: the "notes preserved" check passed *vacuously* in run
1 (its precondition `"Notes" in before` was itself false for the same reason), which would have
hidden Bug 1 entirely. A green check whose precondition never held is worse than a red one.

## Restoration / current dev-stack state

- The one wiped note was restored from the pre-pass CSV backup, along with its original
  `reviewed_by = 'analyst'`. Final DB state **diffs byte-identical** against the pre-pass backup:
  26 notes, 3 risk acceptances, 2 evidence links, 1 vendor, 2 integrations.
- **Not restored (accepted):** `reviewed_at` timestamps on the re-marked stage now read 2026-08-16.
  That column wasn't captured in the backup and isn't rendered anywhere in the UI.
- **Intentionally left behind:** `agent_runs` now holds **2** rows (one seeded via API to break the
  Bug 2 deadlock, one from the subsequent successful button click). These are real runs of a real
  agent, and they keep the Operations terminal usable — do not treat them as test noise to purge.
- Scripts (`ui_dogfood_tprm.py`, `ui_dogfood_run2.py`, `ops_probe.py`) and screenshots live in the
  session scratchpad and are **not committed**, same rationale as the 2026-08-13 driver script.

## Open items

1. ~~**Bug 1 (notes wipe) needs a fix + EXECUTE.**~~ ✅ **Fixed 2026-08-17** —
   `StageNotes_Preservation_refactor.md`. Backend now treats an omitted `evidence_notes` as "leave
   unchanged" while an explicit null still clears; covered by a new pytest regression test
   (**33/33**) and re-verified in the browser against this same Meridian data.
2. ~~**Bug 2 (Ops deadlock) needs a fix + EXECUTE.**~~ ✅ **Fixed 2026-08-17** —
   `OpsTerminal_EmptyState_refactor.md`. The empty state is now scoped to the console pane instead of
   short-circuiting the terminal. That fix also had to remove a **fabricated stats default**
   (`{running: 2, failed: 2}`, only recomputed when `jobs.length > 0`) which was invisible only
   *because* the early return hid the header — shipping the obvious fix alone would have put invented
   operational activity on screen.
3. **Still open:** neither bug has a *frontend* regression test, because the project has **zero
   frontend component tests** project-wide. Bug 1 got a backend pytest regression test; Bug 2's
   verification is a scratchpad Playwright script, not a committed test. Both bugs in this pass were
   frontend or frontend-triggered, which is a fair argument the gap is starting to cost something —
   still parked, still not something to start closing unasked.
4. **Follow-up surfaced by the Bug 1 fix, not itself a bug:** the UI has no way to *author* a note
   for a `pass`/`gap`/`in_review` stage — notes render read-only and only the N/A prompt creates one.
   An analyst working purely in the browser cannot write the rationale for a control they just
   passed. Needs a UI decision (inline editor vs. prompt vs. stage-detail form); deliberately left
   out of the data-loss fix. See `StageNotes_Preservation_refactor.md` § "Known adjacent gap".
