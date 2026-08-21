# TPRM Interview Simulator — Implementation Roadmap

**Created:** 2026-08-18 · **Status:** ✅ **TIER 1 EXECUTED & VERIFIED (2026-08-18)**. See "Open
questions" at the end — all three resolved before EXECUTE. Kept in place as a historical record per
this repo's convention (draft-first artifacts are updated in place with a status header, not
deleted).

**Verification (2026-08-18):** `backend/core/interview_sim.py` (new module, models registered on
`Base.metadata` same way as TPRM), wired into `main.py` (router + `INTERVIEW_RUN` capability seed),
`InterviewSimTerminal.jsx` (new terminal, registered in `App.jsx` + `TerminalSwitcher.jsx`), and
`backend/tests/test_interview_sim.py` (12 new tests). Results:
- Smoke test: **44/44**, no regression.
- Full pytest suite: **50/50** (38 prior + 12 new), no regression.
- Browser pass (Playwright, dev stack): 9/9 checks, zero console errors, zero failed requests — full
  round trip (start a Generic Drill session → real Stage 1 question rendered → submit an
  intentionally off-topic answer → graded **5/100** across all three rubric dimensions with specific,
  non-generic feedback naming exactly what was missing → advance to a distinct real Stage 2 question).
  The low, specific score on a deliberately weak answer is the meaningful signal here — it shows the
  LLM judge is actually grading against the real reference guidance, not rubber-stamping.
- Vendor-scoped mode confirmed live: the vendor dropdown lists real seeded vendors; a fresh vendor
  with no GAP/IN_REVIEW stages correctly 409s instead of fabricating a scenario.

**Origin:** picks up a "GRC Analyst Agent" concept from an earlier ideation conversation (claude.ai,
not recorded in this project's own doc chain — that's why it isn't in `MEMORY.md`). That conversation
proposed three modules: a Sourcing Engine, an Interview Prep/TPRM Simulator, and a Framework Mapper.
Two decisions were confirmed 2026-08-18: **build the TPRM Interview Simulator first**, and **build it
as a new module inside GRC Command Center**, not a standalone project — reusing this repo's existing
FastAPI/Postgres 16/RAG stack rather than the original blueprint's proposed OpenRouter + Crawl4AI/
Firecrawl stack. This roadmap is scoped to that decision, not the full original blueprint.

---

## Why this is a smaller build than the original blueprint suggested

The original idea assumed building scenario generation and question content from scratch. This
project already has real, non-fabricated material to ground it in, which changes the shape of the
build substantially:

- **The question bank already exists.** All 26 seeded TPRM stages carry real `guidance`,
  `review_questions`, and `evidence_to_collect` content (`backend/data/seed_tprm_stages.py`, live
  since Tier 2.1, 2026-08-02) — this *is* the "mock vendor interview" question set the blueprint
  wanted to synthesize. No content-generation module needed for V1.
- **A real mock vendor already exists.** `Meridian Cloud Storage` — two integrations, 26
  individually-reasoned stages, real evidence uploads and risk acceptances — was seeded for the
  2026-08-13 dogfooding pass and is still live on the dev stack. It can be the simulator's scenario
  context (e.g. "this vendor has an open GAP on stage 14 — defend a remediation plan") instead of a
  synthesized fake SOC 2 report.
- **The grounding/grading engine already exists.** `rag_engine`'s Groq client (`core/rag.py`) is
  already configured with the `max_retries=2, timeout=30` hardening from the Gemini→Groq migration.
  No new LLM provider or routing layer needed for V1 — OpenRouter multi-model routing is real scope,
  just not V1 scope.
- **The RBAC, audit-logging, and event-bus patterns already exist** and just need to be applied the
  same way TPRM applied them, not redesigned.

This is consistent with what prompted picking this module first: it's largely assembling existing,
already-verified platform capability into a new surface, not building new infrastructure.

---

## Tier 1 — MVP vertical slice (proposed scope for this EXECUTE cycle)

**Goal:** a working, honest, single-session interview loop — start a session, get a real
TPRM-grounded question, submit a free-text answer, get a real graded rubric back, get the next
question, see a session summary at the end. No Framework Mapper hook, no multi-scenario-type
selector, no analytics dashboard yet — those are Tier 2.

### 1.1 Data model — `backend/core/interview_sim.py` (own module, mirrors `tprm.py`'s pattern)

Two new tables, defined in this module (matching TPRM's precedent of keeping its own models local
rather than in the shared `models.py`):

- **`interview_sessions`**: `id` PK, `scenario_vendor` (nullable str — e.g. `"Meridian Cloud
  Storage"`, null for a generic session), `status` (plain string, not a Postgres enum — per the
  documented `ALTER TYPE` gotcha in `MEMORY.md`; values `in_progress`/`completed` — no `abandoned`
  state in Tier 1, there's no abandon endpoint; a session just sits `in_progress` if unfinished),
  `started_by`, `started_at`, `completed_at`, `overall_score` (nullable int, computed on
  completion).
- **`interview_turns`**: `id` PK, `session_id` FK, `turn_number`, `source_stage_id` (nullable FK-ish
  reference to the TPRM stage this question was drawn from — keeps every question traceable to real
  seed content, not invented per-turn), `question_text`, `question_category` (the stage title),
  `user_response_text` (nullable until answered), `rubric_json`, `score` (nullable), `feedback_text`,
  `grading_status` (`pending`/`graded`/`grading_failed`), `created_at`, `graded_at`.

**Timestamp convention:** `DateTime(timezone=True)` throughout, matching TPRM's own tables — not the
naive convention `User`/`Policy` use. This sidesteps the tz-naive/tz-aware `DataError` class of bug
that hit the User/Policy migration; new tables have no reason to repeat it.

### 1.2 Grounding & grading logic

- **Question selection, and why the session length varies (decided 2026-08-18: this should mirror
  real-world variability, not a fixed count):**
  - **Vendor-scoped session** (`scenario_vendor` set, e.g. `Meridian Cloud Storage`): pull every
    stage currently `gap` or `in_review` for that vendor's integrations — whatever that real count
    happens to be. This is the realistic case: an auditor drills you on however many actual open
    findings exist, not an arbitrary round number.
  - **Method-scoped generic session** (`scenario_vendor` null, caller passes `direction` [egress/
    ingress] + `transfer_method` [file/api] instead — the same two fields `create_integration`
    already takes): pull every stage matching that direction and applicable to that transfer method
    via the existing `applies_to_methods` field (the same Tier 2.4 logic that already drives real
    `NOT_APPLICABLE` stage filtering in `VendorRiskTerminal.jsx`) — different direction/method
    combinations already have different real stage counts today, so this naturally varies session
    length without inventing new logic.
  - Either path reuses data/logic that already exists; no new "difficulty" or "length" parameter is
    introduced.
- **Grading:** a new `grade_response()` call using the same Groq client config as `rag.py`. Prompt
  includes the stage's real `guidance`/`evidence_to_collect` as the rubric and the user's answer;
  asks for a structured JSON score (e.g. completeness / technical accuracy / defensibility, 0–100
  each) plus qualitative feedback.
- **Honesty boundary (explicit design constraint, not an afterthought):** if the grading call fails
  or returns unparseable output, `grading_status = "grading_failed"` and the turn is surfaced to the
  user as ungraded — **never a fabricated score.** This directly mirrors the `_is_engine_failure`
  pattern in `core/agent.py` and the ExecutiveTerminal honesty fix — both existed because this
  project has a real, documented history of a failure state quietly reporting as a clean result. Same
  discipline applies here from day one.

### 1.3 API surface — new router, prefix `/api/v1/interview-sim`

- `POST /sessions` → start a session (optional `scenario_vendor`), returns session + first question.
- `GET /sessions/{id}` → session detail + all turns so far.
- `POST /sessions/{id}/turns/{turn_id}/respond` → submit an answer; grades synchronously and returns
  the graded turn plus the next question (or marks the session `completed` when the scenario's real
  question pool is exhausted).
- `GET /sessions` → list past sessions (this is the "track which scenarios you stumble on" piece from
  the original idea — a real history table, not a stateless one-off).

**Grading is synchronous in the request/response cycle for V1**, not pushed over the WebSocket event
bus. Groq calls in this project have consistently run in low single-digit seconds; adding a new
`INTERVIEW_STATUS` broadcast type for a solo-user practice tool is complexity Tier 1 doesn't need.
Flagged as a Tier 2 item if latency turns out to be annoying in practice.

### 1.4 RBAC

One new capability, **`INTERVIEW_RUN`** (analyst role), seeded in `main.py`'s lifespan block the same
way `TPRM_VIEW`/`TPRM_ASSESS`/`TPRM_SIGNOFF` are. Not splitting view/run/signoff the way TPRM does —
there's no sign-off concept for a personal practice tool, and the viewer role represents a read-only
external-auditor fiction elsewhere in this platform that doesn't map to anything meaningful here.
Open to revisiting if that's wrong.

### 1.5 Frontend — new terminal, `src/terminals/InterviewSimTerminal.jsx`

Registered in `App.jsx` (`case 'INTERVIEW_SIM'`) and `TerminalSwitcher`, following the existing dark
"Enterprise Command Authority" design tokens (§3 of `GOVERNANCE.md`). Surface: start-session control,
current question + stage category, response textarea, submit → shows the graded rubric and feedback
inline, then advances to the next question automatically. A session-history list (past sessions,
scores, timestamps) using the same list-and-badge pattern as `VendorRiskTerminal.jsx`'s vendor strip.

### 1.6 Tests

New `backend/tests/test_interview_sim.py` following the existing pytest conventions: session
create/read, turn submission + grading round-trip, a negative test for the grading-failure path (mock
or force a Groq failure and assert `grading_status == "grading_failed"`, not a fabricated score —
same shape as the existing `test_tprm_evidence_link_immutable` direct-probe pattern), and an RBAC
403 check for a role below `analyst`. Smoke test additions mirroring the existing TPRM smoke checks.

**Effort estimate:** comparable to TPRM Tier 3.3 (evidence linkage) — the largest single Tier 3 item —
given two new tables, a new router, new RBAC capability, new LLM-grading logic, and a new frontend
terminal. Realistically multi-day, not a single sitting.

---

## Tier 2 — deferred, not abandoned

- **Framework Mapper hook.** Given a JD requirement or interview question, surface which real
  `NARRATIVE_BANK.md` STAR story or which platform feature (Mufasa triggers, TPRM module, RAG
  cross-framework mapping table) answers it — this was originally its own separate module in the
  blueprint; makes more sense as Tier 2 here since it can reuse the session/turn data model this Tier
  1 build establishes, rather than being built in parallel from scratch.
- **Additional scenario sources beyond TPRM stages** — e.g. general SOC 2/ISO 27001 questions
  grounded via `rag_engine.query()` directly against the ingested corpus, not just the 26 TPRM
  stages.
- **Session analytics** — "which categories does he consistently score lowest on" aggregation across
  session history, once there's enough session history to make it meaningful.
- **Async grading + WebSocket push**, if synchronous grading proves too slow in practice.
- **Speech-to-text input** (from the original blueprint) — real scope, not remotely urgent.

## Tier 3 — the original blueprint's other two modules, still deferred

- **Sourcing Engine upgrade** (Crawl4AI/Firecrawl + OpenRouter routing) — the existing Indeed/Dice
  daily cloud routine already does this job functionally (see `job-search-tracker-automation`
  memory); revisit only if that routine's official-connector approach proves insufficient, not on a
  fixed schedule.

---

## Open questions — resolved 2026-08-18

1. **Question budget per session** — should vary by scenario/vendor, matching real-world variability.
   Resolved as described in §1.2: vendor-scoped sessions use that vendor's real open (`gap`/
   `in_review`) stage count; method-scoped sessions use the real `applies_to_methods` count for that
   method. No fixed number anywhere.
2. **`INTERVIEW_RUN`-only RBAC** — confirmed, single capability as drafted in §1.4.
3. **Tier 1/2 scope boundary** — confirmed as drafted; no changes.
