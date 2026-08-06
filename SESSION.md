# Session Log — 2026-08-06 ("TPRM, Execution Monitor UI, Agent Registry De-stubbing, and a Compliance-Grid Honesty Fix — Four Items, One Session")

**Outcome:** Picked "browser-verify TPRM's UI" off the post-TPRM pivot-point menu (recommended over
Execution Monitor UI, which needs design decisions before any code can be drafted). TPRM's four
Tier 2/3 surfaces (2.3 vendor rollup, 3.1 reassessment surfacing, 3.2 CSV export, 3.3 evidence
upload) had only ever been checked via API/curl/WS-client — never actually clicked through in a
real browser, despite the project's own history of finding real bugs (wrong WS token field, missing
auth header on an export button) exactly that way. Drove all four live via Playwright/Chromium
(no project-level run skill existed yet for this app, and `chromium-cli` wasn't on `PATH`, so used
Python's `playwright` package directly — already installed, browser binary launched clean). Found
one real bug (a stage detail panel that collapsed after every in-panel action); user chose to fix it
immediately rather than move on to Execution Monitor UI — drafted, EXECUTED, and regression-tested
it same day (see step 9 below). Then, same session, moved on to Execution Monitor UI itself: three
open scope decisions confirmed with the user, a full diff drafted and EXECUTED covering a new
`AgentRun` persistence layer, real audit logging, real WebSocket broadcasting, and a frontend
rewire — verified with smoke/pytest plus a two-tab Playwright regression proving genuine real-time
cross-tab updates (see steps 10-16 below). **Then, same session again**, moved on to a third item —
Agent Registry De-stubbing — scoped it cold (four decisions, all confirmed), drafted and EXECUTED
real logic for both stub handlers, and in the process of verifying it, caught and corrected two of
its own draft's estimates that turned out to be meaningfully wrong once actually measured (see
steps 17-24 below) — consistent with this whole session's pattern of not taking an estimate on
faith once the real system can just be asked. **User asked for one more before stopping, offered the
choice; picked `ComplianceTerminal.jsx`'s fixture-fake policy grid** over TPRM Tier 4 (which turned
out to be more architecturally loaded than expected — see step 25). Scoping it cold revealed the
problem was worse than the earlier flag suggested (misleading buttons doing something unrelated to
what they claimed, a fabricated incident log), and that genuine "de-stubbing" wasn't achievable (no
real infrastructure to wire to) — fixed via honesty instead (see steps 26-28).

## What happened, in order

1. **Boot-ritual verification first:** stack already up (20h+ uptime), smoke **42/42**, readiness
   all green. Noted in passing: 427 integrations / 434 vendors accumulated from repeated
   smoke/pytest runs — the existing Tier 4 test-data-hygiene item, not new.
2. **No project `run` skill existed for this app** — checked per the `run` skill's own instructions,
   found nothing. `chromium-cli` also wasn't installed. Fell back to Python's `playwright` package
   (present, browser binary launched successfully on the first try) rather than generating a whole
   new skill for a one-off verification pass.
3. **Wrote a Playwright driver** (`verify_tprm.py`, scratchpad) that logs in as admin, creates a
   throwaway vendor+integration, expands a stage, marks it `gap`, attaches a real evidence file,
   signs a risk acceptance, and exports the CSV — capturing a screenshot at every step plus all
   console errors and failed network requests.
4. **First run surfaced a real, previously-unknown UX bug immediately:** `VendorRiskTerminal.jsx`'s
   `openIntegration()` resets `expandedStage` to `null` on every call, and it's invoked after *every*
   stage-status button click (`updateStage`) and after signing a risk acceptance (`onSigned`) — so
   the detail panel collapses right after the action you just took, breaking the driver's
   `wait_for_selector` and, in real use, forcing an analyst to re-click after every single action in
   the module's core workflow (mark gap → attach evidence → sign acceptance). Not crash-causing, no
   console error — just a genuine papercut that only surfaced by actually clicking through, exactly
   the class of bug this pass was meant to find. **Not fixed** — flagged for a one-line fix
   (`setExpandedStage(stageId)` instead of `null` after refetch) whenever next in that file.
5. **Also discovered mid-script (not a bug, a UI default):** the "New Integration" modal's vendor
   field defaults to a `<select>` dropdown once ≥1 vendor exists (`newVendor` state initialized to
   `vendors.length === 0`) rather than the new-vendor text inputs — correct, intentional behavior,
   just had to toggle "+ New vendor" to reach a clean, identifiable test subject.
6. **All four features confirmed working end to end**, once the script accounted for both of the
   above: **zero console errors, zero failed network requests** across the full run.
   - **2.3 vendor rollup:** portfolio strip rendered all 435 real vendor chips, correct tier coloring.
   - **3.1 reassessment surfacing:** the WS-broadcast → refetch pipeline fired exactly as designed —
     6 GETs to `reassessments/due`/`acceptances/expiring` (1 initial mount + 2 broadcasting actions,
     each triggering 2 refetches) — though the badge itself wasn't visually confirmed on screen,
     since current data has 0 due/0 expiring (nothing in the corpus is old enough yet). Chose not to
     backdate database timestamps to force a visual (a heavier-handed test than this pass called
     for); the live network trace is sufficient evidence the mechanism itself works.
   - **3.2 CSV export:** real Chromium download, correct filename/auth/content, including the
     freshly-created test row in the Integrations section.
   - **3.3 evidence upload:** real file upload, evidence entry appeared with correct filename, size,
     hash prefix, and uploader.
7. **Pytest went 31/32 on the first re-run right after the browser session** — one `ReadTimeout` on
   `test_tprm_export_csv`. Didn't take it at face value: reran the single test in isolation (passed
   in 4.4s) and the full suite clean (**32/32** in 126s) — confirmed transient, not a regression.
   Reinforces the test-data-hygiene item as worth doing sooner given the dataset's now-real size.
8. **Updated `TPRM_Roadmap.md`, `task.md`, and this file** with the verification results and the one
   real finding.
9. **User chose to fix the panel-collapse bug before moving on to Execution Monitor UI.** Drafted
   `PanelCollapse_refactor.md` per GOVERNANCE §4.A draft-first (the fix touches production code, so
   the verification-only exemption didn't apply once actual changes were on the table). User replied
   EXECUTE. Applied exactly as drafted: `openIntegration` gained a `{ resetExpanded = true }` option;
   `updateStage` and `RiskAcceptanceModal`'s `onSigned` now pass `{ resetExpanded: false }`; the
   integration-list click keeps the default. Rebuilt `grc-frontend` only (frontend-only change, no
   schema risk). Smoke **42/42**, pytest **32/32** (one transient `ReadTimeout` on
   `test_tprm_export_csv` mid-verification, same pattern as earlier in the session — reran clean).
   Wrote a dedicated Playwright regression (`verify_panel_fix.py`, scratchpad) reproducing the exact
   original bug scenario end to end: mark a stage GAP → panel stays open, no re-click; sign a risk
   acceptance → panel stays open, "Risk Accepted" visible with no re-click; switch to a *different*
   integration → still correctly starts with no stage expanded. **7/7 checks passed, zero console
   errors.** One debugging detour along the way: the first regression-script attempt hit a false
   alarm (stage appeared not to update after marking GAP) that traced to the test's own 1-second
   blind sleep racing the async refetch, not a real bug — fixed the script to wait for the actual
   DOM update instead of a fixed delay, then confirmed clean. A second, unrelated flake (the "New
   Integration" modal's vendor-field default depends on whether the vendors list finished loading
   before the modal mounted) turned out to be pre-existing, harmless nondeterminism, not a
   regression — made the script tolerant of either starting state rather than "fixing" product code
   that wasn't the point of this pass.

10. **User chose to build the Execution Monitor UI next, same session.** Read
    `Execution_Monitor_UI_Roadmap.md` cold per its own instruction before assuming scope. Confirmed
    the one open factual question left in it (Decision #3 — does `run_agent_endpoint` currently
    audit-log?) by grepping the actual code: it called only `logger.info`, never
    `log_security_event`, unlike every other privileged action in the codebase — a real, confirmed
    gap. Presented all three of the roadmap's open decisions to the user with the roadmap's own
    recommendation on each; **all three recommended options confirmed** (build now, not sequenced
    after De-stubbing; stay synchronous; add audit logging).
11. **Drafted `ExecutionMonitor_refactor.md`** per GOVERNANCE §4.A, covering Tier 0+1+2 from the
    roadmap's recommended sequence (Tier 3 stays explicitly out of scope). Investigated actual
    current code before drafting rather than trusting the roadmap's claims verbatim — caught the
    roadmap itself citing a stray-backslash path bug in `api.js` that turned out not to exist in the
    current file (only the `agent_name`→`agent_id` field mismatch was real); corrected that in the
    draft rather than propagating it.
12. **User replied EXECUTE.** Applied across 7 files: new `AgentRun` model (`core/models.py`, plain
    string status column, not a SQLAlchemy Enum — sidesteps the ALTER-TYPE class of gotcha entirely
    for a new table); three new sync-bridge `AuditLogger` methods in `core/database.py`
    (`create_agent_run`/`finish_agent_run`/`list_agent_runs`, matching the existing `update_policy`
    pattern rather than `tprm.py`'s `Depends(get_db)` style, since `main.py` doesn't import that);
    `run_agent_endpoint` rewritten to persist + audit-log + broadcast `JOB_STATUS`; `GET /ops/jobs`
    repointed at the real table; `schemas.py` widened (`AgentResult.run_id`,
    `JobItem.result`/`.error`); `api.js`'s field-name fix; `OpsTerminal.jsx` rewired (real
    picker+trigger, real console rendering replacing the fabricated "SCANNING_RESOURCE"/
    "CRITICAL_THREAD_ABORT" text — which also fixed a latent bug found along the way: the old code
    checked `data.result.stdout`, a field neither stub handler has ever returned, so every prior
    manual trigger silently fell through to "No STDOUT received." regardless of the id/field bugs);
    `StatusBadge.jsx` gained a `PENDING` style. **Two corrections found only during implementation,
    not caught in drafting:** the draft claimed `main.py` already had `import json` — it didn't,
    added it; `core/database.py` also needed `import json` added (draft had this one right).
13. **Rebuilt both `grc-backend` and `grc-frontend`.** Backend booted clean, new `agent_runs` table
    created via the existing `create_all()` path with no errors. First smoke run came back 41/42:
    `/ops/jobs` moving from an always-3-rows fixture to real data meant a genuinely-empty list on a
    fresh boot with zero agent runs yet, breaking the old "≥1 item" assertion. Fixed by having the
    smoke test trigger a real `/run-agent` call first — this also gives direct smoke coverage of the
    new endpoint, not just a weakened assertion. Reran clean: **43/43**. Pytest: **32/32**, but ran
    noticeably slower (4m45s vs. the usual ~2min on the same 32 tests) — another data point for the
    Tier 4 test-data-hygiene item, not a regression from this session's changes.
14. **Manual curl verification:** triggered both real agents plus one deliberately-unregistered id;
    all three persisted correctly with real status/result/error, the unregistered one correctly
    403-equivalent-denied with a real error message stored. Confirmed Decision #3's actual point by
    reading `GET /admin/audit/security?event_type=AGENT_EXECUTE` directly — real audit rows exist,
    each correlated to its `run_id`.
15. **Two-tab Playwright regression** (`verify_exec_monitor.py`, scratchpad): tab 1 triggers a run
    via the new picker, tab 2 (already open, no manual action) picks it up live via the `JOB_STATUS`
    WebSocket broadcast. This is the actual "real-time monitor" claim the feature is named for, and
    it was the one thing curl alone couldn't prove. First attempt hit two script-only false alarms,
    both traced and fixed without touching product code: a hardcoded expected run-id collided with
    leftover rows from an earlier interrupted script run (fixed by capturing the real `run_id` from
    the actual API response instead of assuming a number), and a Playwright strict-mode ambiguity
    where "RUN_6" legitimately appeared in both a grid row and the console header text (fixed by
    scoping the locator to the grid column). Final run: **5/5 checks passed, zero console errors on
    either tab** — FAILED-row rendering, COMPLETED-row real result JSON, tab 1's own refresh, and
    tab 2's live WS-driven update all confirmed working.
16. **Updated `Execution_Monitor_UI_Roadmap.md`, `task.md`, `MEMORY.md`, `HANDOFF.md`, and this
    file** with the build results.

17. **User asked what to do next; recommended Agent Registry De-stubbing over TPRM Tier 4** — the
    Execution Monitor UI just built gives real infrastructure to show agent output in, but that
    output was still two hardcoded stub functions; wiring real logic in was judged the more
    compounding next step versus low-priority cleanup. User agreed, asked to start the scope.
18. **Investigated `core/agent.py` cold.** Found `rag_engine.query()` (the real pipeline behind
    `/chat`, 92% benchmark accuracy) as a natural substrate for `active-auditor` — but noted it's
    `async` while the handler/runner chain is sync, reopening Execution Monitor UI's own
    just-confirmed Decision #2 ("stay synchronous... handlers return in milliseconds"). Checked the
    real RBAC `Policy` table for `policy-analyzer` and found a genuine, immediately-defensible gap
    already sitting there: all 13 seeded policies have `source_doc: null`. **Separate discovery,
    explicitly flagged and not folded in:** `ComplianceTerminal.jsx`'s entire policy grid
    (`get_compliance_policies`) turned out to *also* be 100% static fixture data — same shape of
    problem `/ops/jobs` had before Execution Monitor UI, but on the primary compliance dashboard.
19. **Presented four scoping decisions** (what should each handler really do; sync-vs-async given
    RAG's real latency; whether new frontend input was needed) with recommendations on each,
    matching the pattern that worked for Execution Monitor UI. **All four recommended options
    confirmed:** fixed NIST AI RMF question set; real `Policy`-table gap analysis; stay synchronous;
    no new frontend input.
20. **Drafted `AgentRegistry_DeStubbing_refactor.md`.** Resolved the sync/async bridging question
    while drafting (not left as an open decision): converting `execute_agent` and both handlers to
    `async def` is safe, confirmed by checking `_run_async` (dedicated thread + fresh event loop —
    the same mechanism already proven this session by `create_agent_run`/`finish_agent_run`). Found
    a second caller the roadmap hadn't checked — `tests/security_audit.py`, a standalone diagnostic
    script that would have silently broken — and included its fix too.
21. **User said to EXECUTE if the timing trade-off still seemed worth it.** Judged sequential
    execution (not `asyncio.gather`) still correct — FAISS similarity search is documented in this
    codebase's own code as synchronous/CPU-bound, so concurrency would only partially help while
    adding shared-state risk to the lazy-loaded reranker, for a rate-limited admin-only action.
    Applied the diff across `core/agent.py`, `main.py`, and `tests/security_audit.py`. Rebuilt
    `grc-backend` (container took longer than usual to become responsive post-rebuild — confirmed
    via `docker stats` it was actively CPU-bound, not deadlocked; resolved on its own, logs were
    clean once startup actually began).
22. **First verification pass produced a real false alarm, traced honestly rather than shrugged
    off:** the smoke test's own `active-auditor` check failed with a 180s read timeout. Rather than
    assume a defect, isolated the variable — the failure coincided with a manual `curl` check run
    concurrently against the same backend. Re-ran the smoke test with nothing else hitting the
    backend: clean **43/43**. This also surfaced a real, worth-keeping architectural fact (not
    unique to the false alarm): `rag_engine.query()`'s FAISS/reranker work blocks the single event
    loop for its full duration, so *any* concurrent request queues behind an in-flight RAG-chaining
    call — confirmed directly by watching a login request stall behind an in-flight `active-auditor`
    run.
23. **Measured `active-auditor`'s real duration twice, isolated, to settle it precisely: ~43s both
    times (cold and warm).** The draft's ~16s estimate (based on the RAG benchmark's cited ~4s
    average latency) was simply too optimistic — this is the genuine steady-state cost of 4
    sequential real queries against this corpus, not a one-time model-load tax. Corrected the
    record in `AgentRegistry_DeStubbing_refactor.md`, `task.md`, `MEMORY.md`, and `HANDOFF.md` with
    the real number and the fuller blocking-scope finding, rather than letting the original,
    too-optimistic figure stand. Decision #3 ("stay synchronous") wasn't reversed — it was
    explicitly confirmed by the user and the code works correctly — but the number it was confirmed
    against was wrong, and that's now on the record accurately.
24. **Full verification, once run cleanly in isolation:** smoke 43/43, pytest 32/32 (back to its
    normal ~2min, confirming the earlier ~4m45s this session was dataset-growth variance, not
    related to this change), manual curl round-trips against both real agents plus a
    deliberately-unregistered id, `tests/security_audit.py` re-verified working inside the container
    (host Python lacks the RAG dependency stack; `backend/tests/` also isn't baked into the image —
    both now-documented gotchas, worked around with `docker cp` + `MSYS_NO_PATHCONV=1`; 3/4 cases
    pass, the 1 fail is a pre-existing stale test-case id unrelated to this change), and a Playwright
    browser pass triggering both real agents from the actual UI picker (7/7 checks, zero console
    errors) — confirming the real, high-quality NIST AI RMF findings (accurate answers, real source
    citations, correctly-computed severity) and real policy-gap output both render correctly.

25. **User asked for one more item before stopping, offered the choice.** Weighed TPRM Tier 4 against
    the flagged `ComplianceTerminal.jsx` fixture grid — investigated Tier 4 first and found its
    "small effort" label doesn't hold up: `RiskAcceptance` rows (and any `Integration` that has one)
    are protected by a DB-level immutability trigger blocking UPDATE/DELETE by design, so a naive
    "clean up old test data" fix would either fail outright or mean bypassing a security invariant
    this project deliberately built. Picked `ComplianceTerminal.jsx` instead — purely additive
    (make something honest instead of fake), no deletion risk, same shape as the day's other three
    fixes.
26. **Investigated `ComplianceTerminal.jsx` cold and found the problem was worse than originally
    flagged.** Its 5-policy grid is static fixture data representing *external infrastructure*
    controls (AWS S3 encryption, IAM MFA enforcement, etc.) — unlike TPRM/Execution Monitor/Agent
    Registry, there's no real system in this project to wire it to; building fake cloud-API
    integration would just swap one kind of fakeness for another. Worse: its `Update Policy`/
    `REMEDIATE_NOW` buttons both silently called `/ingest` (RAG re-indexing) regardless of which
    policy was selected — clicking "REMEDIATE_NOW" on the failed IAM MFA policy did nothing about
    MFA — and its evidence panel showed a hardcoded fake incident log ("Security policy threshold
    breach (Found: 644)") for any failed policy, static, never real.
27. **Presented this reframed finding to the user before drafting anything** — "de-stub it" wasn't
    achievable the way the other three were; the real choice was between honesty (relabel, stop the
    misleading buttons) and a bigger scope change (replace with a different real data source
    entirely). User confirmed the honest, smaller fix.
28. **Drafted and EXECUTED `ComplianceGrid_Honesty_refactor.md`** per GOVERNANCE §4.A: added a
    `REFERENCE_CATALOG` badge, removed both misleading buttons (replaced with a static "no live
    scan/remediate actions" note), replaced the fabricated incident log with an honest static
    explanation. Frontend-only, no backend/schema risk. Rebuilt `grc-frontend`, verified via
    Playwright: badge visible, old fake content confirmed gone, untouched functionality (search, CSV
    export, real data-structure view, framework mappings) still works — 10/10 checks, zero console
    errors.

## Where this leaves things

TPRM's entire roadmap (Tier 1+2+3) is now **fully built, browser-verified, and the one bug found in
that verification is fixed and regression-tested**. **RAG P3 Execution Monitor UI is now also fully
built and browser-verified**, the same session — all three of its open decisions confirmed, real
persistence + real audit logging + real cross-tab WebSocket updates proven live. **Agent Registry
De-stubbing is now also fully built and browser-verified, the same session again** — both handlers
do real work, with one important correction on the record: `active-auditor` genuinely costs ~43s of
full-backend blocking per run, not the ~16s/single-request framing its own draft estimated.
**`ComplianceTerminal.jsx`'s misleading "live scanning" UI is fixed too, the same session a fourth
time** — honest labeling in place of fake realism, since no real infrastructure exists to back
genuine compliance scanning here. Four substantial things shipped in one session, each following the
same discipline: investigate cold, surface what's actually true (even when it contradicts the
original framing or a prior estimate), present real decisions before drafting, verify for real
(smoke/pytest/curl/browser) rather than trust that code compiling means it works. Next session's
menu: **TPRM Tier 4** (test-data hygiene's real fix is likely a dedicated test schema, not a cleanup
script, given the immutability constraint found tonight — not yet fully investigated),
**`Framework_Mappings`' own separate fixture-fake data source** (same underlying issue as the policy
grid just fixed), or **revisiting `active-auditor`'s sync execution** with the now-accurate ~43s
number in hand (optional — not a defect, just worth a fresh look if it feels worse in practice than
it did on paper).

---

# Session Log — 2026-08-05 ("Golden Mapping Closes the EU AI Act Cluster; a Scorer Bug Traced Back Through Every Prior Run")

**Outcome:** Picked RAG P2 Golden Mapping off the post-TPRM pivot-point menu (over Judge
Calibration and Execution Monitor UI). Diagnosed the EU AI Act cluster (#16/#19/#49) against the
actual source PDF rather than trusting the v5 report's summary alone, drafted and EXECUTED a
query-time Golden Mapping layer, and closed all three targeted failures. A 4th flip in the same
benchmark run turned out to be a scorer artifact, not a real fix — asked to review it (and the PDF
defect) before committing anything, which led to tracing the exact same scorer bug back through
**every prior benchmark run this project has ever recorded** and correcting the whole historical
trajectory. Final, corrected number: **84.0% → 92.0%** (both the pre- and post-Golden-Mapping
figures moved down 2pts from what had been reported — see below, nothing about the retrieval work
itself changed).

## What happened, in order

1. **Boot-ritual verification first** (per HANDOFF.md instruction): stack was already up, readiness
   green, smoke 42/42, pytest 32/32 — matched docs exactly. Also found, incidentally, that
   `grc-frontend` has been reporting Docker-healthcheck "unhealthy" for its entire 40-hour uptime —
   traced to an IPv6/IPv4 loopback mismatch in the healthcheck itself (see MEMORY.md gotcha); the
   app is actually fine. Not fixed, just documented — out of scope for today's focus.
2. **Root-caused #16/#19/#49 against the real PDF**, not just the v5 report's one-line diagnosis:
   pulled actual extracted text from `EU AI ACT 2024_Doc.pdf` via `pypdf` to confirm exact article
   citations (Article 5 unacceptable risk, Article 6 high-risk, Article 50 limited-risk/
   transparency, Article 95 voluntary codes; Articles 51-56 GPAI/"general-purpose AI model" as the
   Act's actual term for what the benchmark calls "ChatGPT"; the open-source licence exemption
   clause). Also found, along the way, that this specific PDF's text extraction systematically
   injects spaces inside words (`"Ar ticle 9"`) — a real, previously undocumented corpus-quality
   defect, deliberately **not** fixed this session (bigger lever, would need re-extraction/
   re-ingestion of at least this file) — flagged in MEMORY.md as a future candidate.
3. **Drafted `Golden_Mapping_refactor.md`** per GOVERNANCE §4.A draft-first — before proposing a
   similarity threshold, actually ran the real `all-MiniLM-L6-v2` model (inside the running
   `grc-backend` container, read-only, `MSYS_NO_PATHCONV=1` needed for `docker cp`/`exec` on this
   Windows/Git-Bash setup — new gotcha, now in MEMORY.md) against all 50 benchmark queries to find
   the actual closest cross-framework false-positive risk (a NIST query at 0.648 cosine similarity)
   before picking 0.70 as the threshold — a data-backed number, not a guess.
4. **User replied EXECUTE.** Implemented: new `backend/data/golden_mappings.json` (3 hand-curated,
   source-cited entries), `rag.py` gained `_load_golden_mappings`/`_match_golden_mappings`
   (query-time cosine-similarity match against cached trigger-phrase embeddings, reusing the
   already-loaded embedding model — no new ML dependency). **One necessary deviation from the
   draft, found mid-implementation:** `RAGEngine` had no persistent `self.embeddings` attribute
   anywhere (every call site created its own local instance) — added a small `_get_embeddings()`
   cache rather than touch existing ingestion/query code paths, to keep blast radius additive-only.
   `numpy` promoted from transitive to declared dependency in `requirements.txt`.
5. **Rebuilt backend only** (no re-ingestion — this doesn't touch the FAISS index). Smoke **42/42**,
   pytest **32/32**, unchanged from pre-deploy baseline.
6. **Re-ran the full 50-query benchmark**, archived as `rag_benchmark_results.v6_golden_mapping.json`.
   Result: 94.0% raw (47/50). Verified the mechanism actually fired for #16/#19/#49 by reading the
   answer text itself — each one reproduces the curated `canonical_context` near-verbatim, not just
   a coincidental score flip. Zero regressions among the 43 previously-passing queries.
7. **Caught a 4th flip (#6, CSF tiers) that did NOT belong to this change:** Golden Mapping has no
   NIST CSF entry — reading the actual answer showed it's the same substantively-incomplete response
   v5 gave (Tier 1 only, explicit inline `INSUFFICIENT_DATA` for Tiers 2-4), just phrased so the
   literal string `INSUFFICIENT_DATA` no longer led the response — `rag_benchmark.py`'s scorer only
   checked `.startswith("INSUFFICIENT_DATA")`. Reported both numbers (94% raw / 92% attributable)
   rather than taking credit for what looked, at the time, like a one-off scorer quirk.
8. **User asked to review this and the PDF defect before committing anything.** Checking blast
   radius on the PDF issue first: confirmed via producer/creator metadata across all 158 corpus
   PDFs that `EU AI ACT 2024_Doc.pdf` is the **only** file with this producer — isolated, not
   systemic. Then, scanning every archived `rag_benchmark_results.v*.json` for the same
   `.startswith()` failure pattern found it wasn't a v6-only fluke: **v1 (#31, SOC 2), v2 (#6, CSF
   tiers), v3/v4/v5 (#35, Three Lines of Defense) all had exactly one identically-shaped false
   `ANSWERED`** — a real partial answer with an inline refusal for the unanswerable part. Every
   historical topline this project has ever reported (44/72/78/82/86/94%) had been inflated by one
   query, this whole time.
9. **User chose: fix the scorer + correct the old reports.** Changed `rag_benchmark.py`'s check to a
   substring match. Reclassified the affected entry in every archived JSON (plus the live
   `rag_benchmark_results.json`) with an added `_correction_note`/`_corrected_2026-08-05` field —
   nothing silently overwritten. Updated `RAG_Benchmark_Report.md` (v1), `_v2.md`, `_v3.md`, `_v5.md`,
   and `_v6.md` with correction callouts and the true numbers: **42/70/76/80/84/92%**. The trend and
   every inter-run delta (+28pts, re-ranker's +4 net) are exactly unchanged — only absolute values
   moved, each by one query.
10. **Found, initially left unfixed pending review:** re-checking v1's report against its own raw
    archive to correct the scorer bug's specific effect surfaced an unrelated problem — the report's
    category-breakdown table (NIST/ISO/EU AI Act/GDPR/etc.) didn't match the archive at all,
    independent of the startswith bug. Committed everything else first, then traced this
    specifically: confirmed it's not a category-scheme mismatch (`diagnose_rag.py`'s
    `get_expected_category()` uses identical id ranges to `rag_benchmark.py`'s comment blocks), and
    confirmed it's isolated to v1 only — v2's category table matches its own archive exactly on all
    7 rows; v3/v5 don't carry this table format at all. The errors in v1's table summed to exactly
    zero (which is why the grand total was still right despite 6 of 7 rows being wrong) — the
    signature of a table that was estimated to match a known total rather than computed. **User
    approved fixing it.** Corrected `RAG_Benchmark_Report.md` §2's table and §3's prose by direct
    computation from the archive (struck-through, not silently overwritten) — also caught two
    specific wrong claims in §3 along the way: Annex A.5.7 called a retrieval success when it was
    actually `INSUFFICIENT_DATA`, and the target-human-transparency EU AI Act query called a failure
    when it was actually `ANSWERED` (backwards).

## Judge Calibration (same session, picked up right after the above was committed)

Asked which RAG backlog item to pick up next; recommended Judge Calibration over Execution Monitor
UI, reasoning that this session's whole storyline was discovering the benchmark's own scoring layer
couldn't be trusted at face value — validating the LLM-judge layer was the natural continuation of
that same measurement-integrity thread. User agreed.

11. **Found the existing calibration data was badly stale before touching anything:**
    `diagnostic_results.v1_uncalibrated.json` / `validation_results.json` were both dated **May
    24** — from the original 44%-baseline diagnostic sprint, predating the entire July 18
    retrieval-tuning sprint and today's Golden Mapping work. That old file still called #16
    `HALLUCINATED` and #19 `REFUSED`, both now correctly `ANSWERED`. Only 4 queries are currently
    C1/C2 (down from 28) — asked the user whether to re-run the diagnostic pipeline fresh first
    (cost: several hundred LLM calls, real time) or just archive the stale data and stop. **User
    chose to re-run fresh.**
12. Archived the stale files via `git mv` (dated names, not deleted). `diagnose_rag.py` and
    `validate_diagnostic.py` import the RAG stack directly (not via HTTP) and need the full backend
    dependency set — neither the host Python nor the container has both the deps AND the test files
    together (`.dockerignore` excludes `backend/tests/` from the image by design, since
    smoke/benchmark tests hit the API over HTTP instead). Copied both scripts + the current
    `rag_benchmark_results.json` into the running `grc-backend` container to execute them where the
    dependencies actually live (same technique as the Golden Mapping threshold probe earlier).
13. **First `diagnose_rag.py` run died silently after 40/50 queries**, no error captured — likely
    the "Windows/WSL2 Docker Desktop network turbulence" pattern already in MEMORY.md. The script has
    no resume logic (confirmed by reading it) — patched a minimal checkpoint-resume into the
    container's working copy only (not the committed source), plus added `flush=True` /
    unbuffered mode after realizing the first attempt's apparent "silence" for 40 minutes was
    actually just Python's full-buffering-when-piped, not a hang — a poll-based Monitor reading the
    checkpoint JSON directly (bypassing stdout entirely) is what actually confirmed real progress.
    Resumed successfully from the checkpoint rather than repeating ~40 minutes of already-done work.
14. **Final diagnostic: 46 SUCCESS, 4 C1, 0 C2, 0 A, 0 B** — all 4 current failures (#6, #36, #45,
    #50) got the first-pass "C1" label. Ran `validate_diagnostic.py`'s second-stage judge on all 4,
    then pulled full evidence (retrieved chunks + relaxed-prompt responses) and formed an
    independent read before asking the user to render the actual human verdict per query (real
    calibration needs a human label, not another LLM's opinion standing in for one). **Found the
    first-pass discriminator has the exact same `.startswith("INSUFFICIENT_DATA")` bug already fixed
    in `rag_benchmark.py`'s scorer earlier this session** — same session, same bug class, second
    occurrence. It was wrong on #6, #36, and #50 (all mislabeled C1 when they're really A/B-gap or
    hallucination), right only on #45.
15. **User's human labels: 4/4 agreement with the second-stage "locked" judge, 1/4 with the
    first-pass discriminator.** Promoted the locked judge prompt to `v2_calibrated`. Published
    `JUDGE_CALIBRATION_v2.md` and `judge_calibration_v2.json` (the actual human-labeled set with
    full evidence/reasoning per query). Confirmed 4 queries is the *complete* current population for
    this judge, not an artificially small sample — it only ever runs on C1/C2 candidates in
    production, and there are only 4 of those today (down from 28 in May), because the retrieval
    work already fixed the rest.

## Things found and deliberately left unfixed (documented, not silently dropped)

- The PDF text-mangling defect (`"Ar ticle 9"`) — confirmed isolated to one corpus file, but fixing
  properly needs a new extraction dependency (`pdfplumber`/`PyMuPDF`, neither currently installed)
  plus re-ingestion. User chose to park this.
- `diagnose_rag.py`'s first-pass `.startswith()` discriminator bug (item 14 above) — same bug class
  as the already-fixed scorer, but low urgency since the calibrated second-stage judge is what real
  decisions should use.
- `diagnose_rag.py`'s missing resume-from-checkpoint logic — the fix used this session was ad-hoc
  (container-only, not committed to the tracked source).

## Execution Monitor UI — scoped cold, not implemented (same session, after agreeing to stop coding)

Asked whether to keep going or stop; agreed this was a natural stopping point for the RAG-quality
thread (Golden Mapping → scorer fix → historical correction → Judge Calibration is a complete arc).
User then asked for the next item to be scoped into a curated implementation plan so a future
session can start cold, rather than left as the one-line HANDOFF/task.md description it's had for
months.

Investigated the actual code fresh (agent registry, WS bus, DB models, `OpsTerminal.jsx`,
`useWebSocket.js`, `api.js`) instead of trusting the existing "frontend healthy, bus ready" framing
— which turned out to be wrong: the job grid is a static fixture that never updates, the
`JOB_STATUS` WS type it listens for is never broadcast anywhere in the backend, agent execution has
no persisted lifecycle at all (`execute_agent()` runs synchronously in-request, no job/run table
exists in `models.py`), and the "Run Agent" button has three independent bugs (bad URL, wrong field
name, references an unregistered agent id) making it non-functional today regardless of monitoring
scope. Published `Execution_Monitor_UI_Roadmap.md` — a TPRM-Tier-Roadmap-style scoping document
(tiers, what/why/where/depends-on, effort sizing) rather than a ready-to-EXECUTE diff, since real
design decisions need the user's input first: build the monitor before or after "Agent Registry
De-stubbing" (the other unchecked P3 item — building first means monitoring two hardcoded stub
responses faithfully in real time); keep execution synchronous or move to a real queue; whether
agent runs need audit-trail rigor like TPRM's immutable trail. Corrected `task.md`/`HANDOFF.md` to
point at this roadmap instead of repeating the stale "frontend healthy, bus ready" line.

**No code touched this part of the session** — investigation and planning only, per the user's
explicit request to prep for a cold start next time, not to start implementing now.

## Current deployed state

- RAG accuracy: **92%** (corrected; up from a corrected 84% baseline — see MEMORY.md's "Key
  numbers" for the full before/after table). Judge Calibration: **v2_calibrated**, 4/4 human
  agreement. TPRM unchanged (still fully complete per 2026-08-04). Smoke 42/42, pytest 32/32.
- New files: `backend/data/golden_mappings.json`, `judge_calibration_v2.json`,
  `JUDGE_CALIBRATION_v2.md`, `diagnostic_results.v2_calibrated.json`,
  `validation_results.v2_calibrated.json`. Modified: `backend/core/rag.py`,
  `backend/requirements.txt` (numpy declared), `backend/tests/rag_benchmark.py` (scorer fix), all
  6 `rag_benchmark_results.v*.json` archives + the live one, 5 `RAG_Benchmark_Report*.md` files.
  Archived (renamed via `git mv`, not deleted): the stale May-24 diagnostic/validation files.
- **Not browser-verified** — neither change this session has a UI surface (query-path and
  offline-diagnostic only), so N/A this time, unlike the outstanding TPRM UI-surface
  browser-verification gap (still open from 2026-08-04).

## Next session menu

1. **RAG P3 Execution Monitor UI** — **start with `Execution_Monitor_UI_Roadmap.md`**, not from
   scratch. Confirm the 3 open decisions with the user (sequencing vs. De-stubbing; sync vs async;
   audit-trail rigor), then draft the actual `_refactor.md` diff per GOVERNANCE §4.A.
2. **TPRM Tier 4** (opportunistic, still low-priority) / **browser-verify TPRM's UI surfaces**
   (still outstanding from 2026-08-04) — unchanged, not touched this session.
3. The EU AI Act PDF extraction defect — parked, not blocking; raise only if corpus/harness hygiene
   becomes a priority.
4. `diagnose_rag.py`'s first-pass discriminator bug + missing resume logic (items 14/13 above) —
   both real, both low-urgency, both easy fixes if anyone's back in that file.
5. The frontend Docker-healthcheck false-"unhealthy" (IPv6/IPv4 mismatch) — cosmetic only, fix is
   a one-line `HEALTHCHECK` change to `wget http://127.0.0.1:3006/` if ever worth doing.

---

# Session Log — 2026-08-03/04 ("Closing Out the TPRM Roadmap: Tier 2 → Tier 3, Start to Finish")

**Outcome:** Pushed the prior session's held-back commit, then executed and shipped the entire
remaining TPRM backlog in one continuous push — Tier 2's last item (2.3) and all three Tier 3
items (3.1, 3.2, 3.3). **The full TPRM roadmap (Tier 1 + Tier 2 + Tier 3) is now complete.** Found
and fixed three real, previously-undiscovered bugs along the way, none of them things this session
set out to look for.

## What happened, in order

1. **Pushed `f0bff91`** (Tier 1 + 2.4/2.1/2.2, held back at prior session's close).
2. **2.3 — Vendor-level risk rollup:** `_recompute_vendor_tier` (max-severity across a vendor's
   integrations) hooked into `create_integration` + both `approve_integration` paths. Frontend
   vendor-portfolio strip. Closes Tier 2.
3. **3.1 — Reassessment surfacing:** event-driven WebSocket broadcast (no backend scheduler exists
   in this repo, and none was added — confirmed with the user rather than assumed) nudges
   connected terminals to re-fetch `/reassessments/due` + `/acceptances/expiring`. Header badge +
   expandable panel. **Bug found:** `OpsTerminal.jsx`'s WebSocket had never actually connected —
   `user?.access_token` doesn't exist on the auth context; the real token lives in `api.js`'s
   private `tokenStore`. Fixed via a new `api.getAccessToken()`.
4. **3.2 — CSV assessment export:** `GET /tprm/export`, three-section CSV mirroring
   `/compliance/export`'s pattern. **Bug found:** that same `/compliance/export`'s existing
   "Export CSV Report" button used `window.location.href`, which sends no auth header — it had
   been silently 401ing. Fixed via a new shared `api.downloadFile()` helper.
5. **3.3 — Evidence linkage to `evidence_chain`:** the largest item. Real architecture decision
   (confirmed with the user before drafting): full file upload, not a lighter hash-reference
   alternative — this codebase had zero prior upload endpoints anywhere. New append-only
   `StageEvidenceLink` table, `POST/GET .../stages/{stage_id}/evidence`, `AuditLogger.log_evidence`
   widened to return the row id and propagate exceptions instead of swallowing them. **Bug found:**
   the new Docker volume for evidence storage mounted root-owned on first creation (Windows/WSL2
   Docker Desktop inherits ownership into a fresh named volume only from a path that already
   exists, chowned, in the image — `data/tprm_evidence` wasn't in `Dockerfile.backend`'s `mkdir`
   line, unlike `faiss_index`, which is why that one already worked). Fixed the Dockerfile,
   recreated the volume, and specifically proved durability (upload → rebuild → file and DB row
   both survived) rather than just trusting the fix.

Every item followed the same loop: draft artifact → confirm design calls via targeted questions →
apply → rebuild → smoke + pytest → close out docs/memory → commit → push (all explicitly confirmed
by the user each time, per GOVERNANCE §4.A).

## The three bugs, as a pattern

All three were variants of the same root cause: **a frontend action that bypassed `api.js`'s
central auth-header plumbing** (a raw `window.location.href`, a WebSocket built with the wrong
token source) or **an infra assumption that didn't hold under the non-root container user** (a
volume mount that needed the image to already own the path). None were things any Tier item asked
for — all three surfaced from reading the code adjacent to what was actually being built, then
verifying rather than assuming it worked. Worth the same scrutiny next time new frontend
download/upload/telemetry code — or a new Docker volume — gets added.

## One process correction worth remembering

Running `pytest backend/tests/ -v` from the repo root (instead of `cd backend && pytest -v`)
silently skips `backend/pyproject.toml`'s `--ignore=tests/smoke_test.py` rule (that ignore path is
relative to `backend/` as pytest's rootdir). This produced a false-alarm regression signal once
this session (2 `ReadTimeout`s that looked exactly like a code-caused failure) before being traced
to the invocation, not the change. Always run pytest from inside `backend/` in this repo.

## Current deployed state

- All TPRM roadmap work is live and pushed: `f0bff91`, `5f4e59c` (2.3), `21c3c3b` (3.1), `3abce53`
  (3.2), `70d5e84` (3.3). Repo fully in sync with `origin/main`.
- Smoke test: **42/42**. Pytest: **32/32** (5 IAM + 27 TPRM), run from `backend/`.
- New Docker volume `grc-tprm-evidence` (evidence file storage), correctly owned by `grcuser`.
- **Not browser-verified this session at all** — no browser-automation tool was available. Every
  new UI surface (2.3's vendor strip, 3.1's reassessment badge, 3.2's export button, 3.3's evidence
  upload/list panel) was verified via API/curl/WS-client checks only. Worth an actual browser pass
  next time one's available, even though nothing here is expected to be broken.

## Next session menu

TPRM's roadmap is exhausted — this is an open pivot point, not a "next item per the plan" like
every prior session this arc.

1. **RAG backlog** (parked behind TPRM since 2026-08-02, never actually abandoned): P2 Judge
   Calibration (results still flagged `v1_uncalibrated`), P2 Golden Mapping (the expected path from
   86% into the 90s, targets the EU AI Act cluster), or P3 Execution Monitor UI (deferred since
   April, frontend/WS bus both ready). Any of the three is a reasonable default to raise
   proactively, since there's no more TPRM backlog to fall back on.
2. **TPRM Tier 4** (opportunistic, explicitly low-priority): test-data hygiene (smoke/pytest have
   been accumulating vendors/integrations across many runs — hundreds by now), frontend component
   tests (none exist project-wide).
3. **Browser-verify the four TPRM UI surfaces** above, once a browser-automation tool is available.
