# Fix: Marking a stage silently destroys its evidence notes

**Status:** ✅ EXECUTED (2026-08-17). Applied exactly as drafted, plus the proposed regression test
(the draft offered it as opt-out; it wasn't declined). Verified: **pytest 33/33** (was 32/32 — the new
`test_tprm_stage_restatus_preserves_existing_notes` is the +1), **smoke 43/43**, and a browser
re-verification against the real `Meridian Cloud Storage` data — expanded a stage with notes, clicked
its current status, and the `NOTES` block is still there afterwards (16/16 checks in the combined
post-fix run, zero console errors, zero failed requests). The Meridian dataset was diffed against its
pre-pass CSV backup afterwards and is **byte-identical**.

**One honest caveat on the regression test:** it passes against the fixed code, and its two-part
assertion (omitted → preserved, explicit null → cleared) proves `model_fields_set` discriminates
correctly. It was **not** re-run against reverted code to watch it fail. That step was skipped as
redundant rather than overlooked: the pre-fix behaviour was already measured directly twice during
the 2026-08-16 dogfooding pass (stages-with-notes 26 → 25 on a single UI click), and since
`payload.evidence_notes` is `None` in the omitted case either way, the old unconditional assignment
could only ever have written `NULL` there. The failure is a logical consequence of verified facts,
not an assumption — but it is inferred, not observed, and that distinction belongs on the record.
**Found:** 2026-08-16, TPRM UI/browser dogfooding pass — see
`TPRM_Dogfooding_UI_Pass_2026-08-16.md` (Bug 1).
**Files:** `backend/core/tprm.py` (the fix) · `src/terminals/VendorRiskTerminal.jsx` (context only,
unchanged by this draft)
**Effort:** trivial (one conditional) — but the *semantic* decision behind it is the real content
here, so it's worth reading past the diff.

## The bug

Clicking any of the `pass` / `gap` / `review` status buttons on a stage **permanently erases that
stage's `evidence_notes`** — the written rationale for the assessment decision — with no warning, no
confirmation, and no undo. `reviewed_by` is also silently reassigned to whoever clicked.

Two halves combine:

1. **Frontend** (`VendorRiskTerminal.jsx`, `updateStage()`): `evidence_notes` is only ever assigned
   inside the `not_applicable` branch, which prompts for a justification. For `pass`/`gap`/`in_review`
   the variable stays `undefined`, and `JSON.stringify` drops undefined-valued keys entirely — so the
   request body is literally `{"status":"pass"}`, with no `evidence_notes` key at all.
2. **Backend** (`tprm.py`, `submit_stage_response`): does
   `stage_response.evidence_notes = payload.evidence_notes` **unconditionally**. Absent key →
   Pydantic fills the `Optional[str] = None` default → the stored note is overwritten with `NULL`.

Confirmed both at the DB layer (stages-with-notes went 26 → 25 after one UI click; the row's
`evidence_notes` became `NULL` and `reviewed_by` flipped `analyst` → `admin`) and as a user-visible
symptom (the `NOTES` block just disappears from the open panel).

**Why every prior pass missed it:** the 2026-08-13 API dogfooding driver and both `smoke_test.py` and
`test_tprm.py` always send an explicit `evidence_notes` value, so none of them ever produced the
omitted-field request shape that the UI actually sends.

**Worth stating plainly:** `stage_responses` is *not* covered by the PL/pgSQL immutability triggers
that protect `audit_logs`, `evidence_chain`, and `risk_acceptances` (GOVERNANCE §2.2). So the
sign-off artifacts are append-only while the *reasoning that justifies them* is silently
overwritable. For a GRC tool that's the wrong way round.

## The fix

Treat an **omitted** `evidence_notes` as "leave the existing rationale alone", while still honouring
an **explicit** `null` as a deliberate clear. Pydantic 2 (pinned at 2.12.5) distinguishes these
natively via `model_fields_set`.

```diff
--- a/backend/core/tprm.py
+++ b/backend/core/tprm.py
@@ async def submit_stage_response(
     if payload.status == StageStatus.NOT_APPLICABLE and not (payload.evidence_notes or "").strip():
         raise HTTPException(status_code=422,
             detail="A justification note is required to mark a stage Not Applicable")
 
     stage_response.status = payload.status
-    stage_response.evidence_notes = payload.evidence_notes
+    # An OMITTED evidence_notes means "don't touch the existing rationale"; only an
+    # explicitly-sent value (including an explicit null) may overwrite it. The UI omits
+    # this field for pass/gap/in_review, and treating that as NULL silently destroyed
+    # the assessment rationale on every status click (found 2026-08-16, UI dogfooding).
+    if "evidence_notes" in payload.model_fields_set:
+        stage_response.evidence_notes = payload.evidence_notes
     stage_response.reviewed_by = current_user["username"]
     stage_response.reviewed_at = _utcnow()
     await db.commit()
```

That is the entire change. No schema migration, no frontend change, no API contract break.

## Why this shape, not the alternatives

- **Make the frontend send the existing note back** (`evidence_notes: stage.evidence_notes`) —
  rejected as the *primary* fix. It would work for this one caller, but leaves the destructive
  default one careless caller away, and makes correctness depend on every client remembering to
  echo state back. The backend should not have a "silently erase the audit rationale" default at
  all. (This is still worth doing as belt-and-braces later; it is not needed once the backend is
  correct, so it's left out to keep the diff to one decision.)
- **Make `evidence_notes` required on every submission** — rejected: it would break `_set_stage()` in
  `test_tprm.py`, the smoke test's own calls, and any legitimate "just flip the status" workflow, to
  solve a problem that only exists because omission was mapped to deletion.
- **Add a DB immutability trigger on `stage_responses`** — rejected: notes genuinely need to be
  editable during an assessment (unlike a signed risk acceptance). Append-only is the wrong model
  here; "don't clobber what wasn't sent" is the right one.

## Known adjacent gap — deliberately NOT in this diff

Even with this fix, **the UI still has no way to author a note for a `pass`/`gap`/`in_review`
stage.** Notes are rendered read-only in the expanded panel, and the only UI path that ever *creates*
one is the `not_applicable` justification prompt. So the 24 non-N/A notes on the Meridian vendor
could only have arrived via the API — a real analyst working purely in the browser cannot write the
rationale for a control they just passed.

That's a genuine product gap, but it is **feature work, not this bug**, and fixing it means a UI
decision (inline editor vs. a prompt like the N/A path vs. a proper stage-detail form). Flagged here
so it's a deliberate follow-up rather than something quietly bundled into a data-loss fix.

## Verification plan

1. **Regression test for the exact bug** (new, in `backend/tests/test_tprm.py` — proposed, say the
   word if you'd rather I skip it): create an integration, `POST` a stage with
   `{"status":"pass","evidence_notes":"rationale"}`, then `POST` the *same* stage with
   `{"status":"pass"}` only, and assert `evidence_notes` is still `"rationale"`. This test fails on
   today's code and passes after the fix — the honest definition of a regression test.
2. `pytest` from `backend/` — expect **32/32** (33/33 if the test above is included). No existing
   test asserts that omission clears notes; `_set_stage()` sends `{"status": …}` with no notes but
   never asserts the note was erased, so it is unaffected — checked, not assumed.
3. `smoke_test.py` — expect **43/43**. Its one stage submission sends explicit notes, so it exercises
   the unchanged path.
4. **Browser re-verification** against the real `Meridian Cloud Storage` data (Python `playwright`,
   per `MEMORY.md` gotchas): expand a stage with notes, click its current status, confirm the `NOTES`
   block is still there afterwards — the exact scenario that found the bug, so the exact regression
   check. Back up the notes to CSV first regardless, same as the 2026-08-16 pass.
5. Confirm the N/A path still behaves: marking a stage `not_applicable` with a justification still
   stores it, and marking N/A with an empty justification still 422s.

**Backend change ⇒ `grc-backend` needs a rebuild**, and per `MEMORY.md` prefer
`docker compose -f docker-compose-v2.yml up -d --build` over a full `down`/`up` cycle on this
Windows/WSL2 setup.
