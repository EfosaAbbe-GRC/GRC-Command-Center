# Session Log — 2026-08-18 ("The Interview Simulator, and What It's Actually Grading")

**Outcome:** a new module shipped — the TPRM Interview Simulator — and the strongest evidence it
works isn't the test count, it's a screenshot of it correctly failing a bad answer.

**Where this came from:** the user surfaced a "GRC Analyst Agent" blueprint from an earlier
claude.ai conversation that had never been recorded in this project's doc chain (three modules:
a job-sourcing engine, an interview-prep simulator, a hands-on GRC mentor lab). Two decisions
confirmed before any code: build the interview simulator first (not the sourcing engine — the
existing Indeed/Dice cloud routine already does that job), and build it *inside*
`GRC_Command_Center` rather than as a standalone project, reusing the existing stack instead of
the blueprint's proposed OpenRouter/Crawl4AI one.

**The reuse argument turned out to be the actual finding.** The blueprint assumed synthesizing
mock-interview content from scratch. This project already had it: the 26 seeded TPRM stages carry
real `guidance`/`review_questions`/`evidence_to_collect`, and `Meridian Cloud Storage` (seeded for
the 2026-08-13 dogfooding pass) is a real mock vendor with real open GAP stages. Tier 1's whole
design is assembling already-verified platform capability into a new surface, not building new
infrastructure — see `Interview_Simulator_Roadmap.md` for the full "why this is smaller than it
looks" case, drafted and EXECUTE-approved before any code (per `GOVERNANCE.md` §4.A).

**Built:** `backend/core/interview_sim.py` (new router + two tables, mirrors `tprm.py`'s pattern of
keeping its own models local rather than in shared `models.py`), a new `INTERVIEW_RUN` capability,
`InterviewSimTerminal.jsx`. Session length genuinely varies by real data rather than a fixed
question count — vendor-scoped sessions use however many GAP/IN_REVIEW stages a vendor actually
has open; method-scoped sessions reuse `create_integration`'s own `applies_to_methods` filtering.
Grading is a live Groq call (same bounded client config as `rag.py`) with an explicit
`grading_failed` state — a failed call is surfaced honestly, never turned into a fabricated score.
That design choice was deliberate from the start, not a fix found later: this project has a real,
repeated history (the Groq-outage incident, ExecutiveTerminal's fixture KPIs) of a failure state
quietly reporting as a clean result, and this module was built to not repeat it.

**Verification, and why the screenshot matters more than the numbers:** smoke 44/44 (no
regression), full pytest 50/50 (38 prior + 12 new — kept deliberately LLM-call-frugal, only one
test in the new file actually hits the live Groq grading endpoint, given the documented shared
200k-token/day budget). A Playwright browser pass came back 9/9, zero console errors, zero failed
requests — but the number that actually proves the feature *works as intended*, not just that it
runs without crashing, is that an intentionally weak, off-topic test answer was graded **5/100**
across all three rubric dimensions with specific, non-generic feedback naming exactly what was
missing. A grader that gives everything a high score would still pass all 9 browser checks; this
one doesn't, which is the whole point.

**Committed and pushed** (`0e60631`) — draft → EXECUTE → verify → commit → push, same loop as
every other change in this project.

**Separately, the same session:** the user asked for guidance on building hands-on GRC experience
more broadly (not just tooling), which led to auditing `GRC resources/`'s Career Lab and finding
its own tracker had drifted (a fully-drafted project marked "Not Started"); then to a
workspace-wide doc-chain standardization pass across the whole `GRC Inspector` parent folder. Both
are recorded in that parent workspace's own `SESSION.md`/`CLAUDE.md`, not duplicated here — this
project's own state didn't change as a result of that pass beyond what's recorded above.

---

# Session Log — 2026-08-17d ("The Corpus Refresh, and a Fake 96%")

**Outcome:** the user ran a full corpus curation pass, and the measurement of it exposed the same
defect class for the third time in one day.

**The corpus work (user-led, and it was the right call).** He proposed manually cleaning the corpus
and wanting "original standardized documents". Auditing what was actually there validated that hard
(`Corpus_Audit_2026-08-17.md`): **90 MB of the corpus yielded zero retrievable text** — image/carousel
exports that look healthy in a file listing and are invisible to RAG. The sharpest case: a file named
`ISO_27001_2022_the_significance_of_Clause_4.pdf`, clearly added to serve benchmark query #14,
contributing nothing. Eleven more files were text-starved (50-300 chars/page) and benchmark queries
pointed straight at several. And several "framework" files turned out to be commentary — `Nist Csf
2.0.pdf` was a third-party **audit checklist**, which directly explained why #6 had always failed
("names the tiers but never defines them").

Ran it as a gated procedure (`Corpus_Refresh_Runbook.md`): remove the provably useless first, stage
downloads in `_incoming/`, **validate at the gate before admission** (valid PDF, `%%EOF`, >300
chars/page, and page 1 confirming it is the publication not a summary), retire superseded files only
once their replacement is in, then one ingest. 12 files admitted — NIST CSF 2.0 (CSWP 29), SP 800-61
r2+r3, SP 800-171r3, the GDPR regulation text, AICPA Trust Services Criteria, IIA Three Lines Model,
PCI DSS 4.0.1, CMMC, ENISA NIS2 guidance and both EU Implementing Regulation parts. Net across the
session: **158 → 153 files, 684 MB → 460 MB**, but **chunks went UP (17,088 → 17,498)** — dense text
replacing images. Two useful catches along the way: `B0DF8Z5HTT.pdf` was a 45 MB CompTIA Security+
textbook hiding behind a meaningless filename, and NIST now ships 800-61r2 with a **withdrawn**
notice, so it was renamed to carry that status into any citation.

**Then the measurement lied.** v8 reported **96.0% (48/50)** — the best score ever recorded. It was
false. Groq's free tier caps at **200,000 tokens/day**; the run exhausted it at query #11 ("Used
199,902") and every subsequent query returned `429`. `/chat` returns **HTTP 200 with the error in the
body**, so the scorer's `status_code == 200` passed and the 44-character error string satisfied
`len(answer) > 20` → **ANSWERED**. 32 errors were scored as correct.

**This is the same defect class found and fixed twice earlier the same day** — `active-auditor`
reporting "4/4 substantiated" from four failed queries, and `smoke_test.py` reporting 43/43 through a
total outage. Both were fixed hours before; the benchmark was not checked. Every instance asks *"is
there a response?"* instead of *"is the response real?"*

Fixed (`Benchmark_Scorer_Honesty_refactor.md`): engine failures checked first and scored ERROR, three
consecutive failures abort the run, any run with an error is stamped `"valid": false` with a
DO-NOT-QUOTE banner, and the script **exits non-zero**. **Verified by reproducing the failure first**
— using the bogus-model trick so it consumed zero tokens — where the old code gave 96%, the new code
aborts after 3 queries and exits 1.

**What is and isn't known now.** The corpus refresh is done, verified and sound. Its *measurement does
not exist*: **v7's 90% remains the current figure**, the contaminated archive is quarantined as
`rag_benchmark_results.v8_INVALID_rate_limited.json`, and a clean v8 is the first task next session.
The only salvageable signal is queries #1-10: **9/10 vs v7's 8/10 with #6 recovered** — confirmed
independently by a live query citing the new CSF document. #4 still fails, exactly as predicted, since
it is the enumeration/chunking problem that corpus curation was never going to fix.

**A useful side-effect:** this confirms v7's unproven latency hypothesis. The 6.6s → 16.86s
"regression" was throttling as the token budget depleted, not a slower model. And it establishes a
hard operational constraint: **one benchmark run per day, and running it can take the app's AI
features down for the rest of that day.**

---

# Session Log — 2026-08-17c ("The Benchmark That Found the Engine Was Dead")

**Outcome:** Set out to run the oldest open item — re-run `rag_benchmark.py` against Groq. The
benchmark never got started: the warmup query came back empty, and the investigation turned up that
**the core RAG engine had been dead for up to four days.** Groq retired
`llama-3.3-70b-versatile` (404 `model_not_found` on every call) sometime after the 2026-08-13
migration verified it working. The user later confirmed Groq had sent advance notice naming
`openai/gpt-oss-120b` as the successor — so the outage was *foreseeable*, and the real failure is
that nothing in the system noticed.

**Four independent checks reported green through a total outage:** `/readiness` said "ready" (it only
checked a key string existed), `smoke_test.py` reported 43/43 twice today (its `/chat` check asserted
only that the fields `response` and `sources` were *present* — an error string and `[]` satisfied it),
`pytest` doesn't cover `/chat`, and worst of all **`active-auditor` returned "NIST AI RMF Audit
Complete — 4/4 core functions substantiated from corpus, severity LOW"** from four failed queries,
because its severity logic only counts a function unsubstantiated when the answer contains
`INSUFFICIENT_DATA` — and an error string contains no such marker. A GRC tool issuing a favourable
audit opinion from a dead engine. Same class as the fabricated Executive KPIs fixed hours earlier,
except generated at runtime rather than hardcoded.

**Fixed all four, plus a fifth found by testing.** Model swapped to `openai/gpt-oss-120b` — chosen by
running four candidates against the module's *own* `PRODUCTION_PROMPT_TEMPLATE` on both scored
behaviours, before knowing Groq had designated it; the two agreed independently. Model id now lives in
one place (`GROQ_MODEL` in `core/rag.py`) so `/readiness` validates the same string the chain uses.
`/readiness` now resolves that model against Groq's live model list. The smoke test now fails on the
generic error string or zero sources. `active-auditor` returns `status: "error"` with an explicit "no
audit conclusion is available" message. **The fifth:** the negative test revealed `/run-agent` decided
success by looking for an `"error"` *key*, so my handler's `status: "error"` still recorded
`COMPLETED` — Part D was honest in its payload and dishonest in its envelope. Caught only by running
the negative test instead of trusting the code.

**Every fix verified with a deliberate negative test** against a bogus model id (patched inside the
container, reverted by force-recreating from the image): readiness → `error` naming the model;
smoke → **43/44 with a precise diagnostic** where it previously reported all-green; agent → `failed`,
no severity, `AgentRun` row `FAILED` with the explanation. Then restored: **smoke 44/44** (the new
substance check is the +1), **pytest 38/38**, live `/chat` answering with real citations,
`active-auditor` back to its 31s baseline with 4 real sources.

**Then the original task finally ran — `RAG_Benchmark_Report_v7.md`, the first Groq-era measurement:
90.0% (45/50).** Against v6's Gemini-era 92% that is one query, comfortably inside noise. But the
failure set churned and the composition is the real story: #6/#50 still fail (both have documented
non-model root causes — a good sign the diagnosis was right), **#36 and #45 recovered** (#36 was a
confirmed Gemini *hallucination*, a quality win the number hides), and **#4/#12/#18 newly fail —
all three "list/enumerate" queries that refused despite successful retrieval.** `gpt-oss-120b` looks
stricter about completeness, which is arguably better auditor behaviour but costs points under a
binary scorer that cannot distinguish a correct refusal from a failure.

**Two things deliberately left as hypotheses, not conclusions:** the latency shift (6.6s → 16.86s
avg) is probably free-tier rate limiting, not the model — isolated calls ran 1.0-1.3s and the run's
first three queries took 3-5s before jumping to a 13-28s band; and three answers came back with
**zero retrieved sources** (#35/#39/#45), the signature of unguarded generation, which cannot be
classified because `validate_diagnostic.py`'s calibrated judge is *still Gemini-pinned and dead*.
That tooling gap has now blocked analysis twice.

**Most actionable follow-up:** #18 retrieves only **1 source** and refuses — on a document (OWASP Top
10 for LLMs 2025) that was added to the corpus *specifically to fix #18*. That reads as a retrieval
regression rather than model conservatism.

---

# Session Log — 2026-08-17b ("The Audit Before the Tests: Executive Was Serving Fiction")

**Outcome:** The user asked for automated screen tests, given that both 2026-08-16 bugs were
frontend-triggered and no frontend tests exist. **Pushed back on the ordering and the user accepted:**
writing tests against untested code encodes current behaviour as correct, and this codebase has a
documented history of fabricated data (ComplianceTerminal, Framework_Mappings, and the `stats: {running:
2}` default fixed hours earlier). Test-first here would have written
`expect(governancePosture).toBe('92.4%')` and cemented a fabrication as the expected contract. So:
audit first, fix, *then* tests.

Made the audit hypothesis-driven rather than open-ended — both prior bugs were the same class ("what
does this screen do with no data?") and the other four terminals had never been checked for it. Drove
all five as admin with every list endpoint intercepted to `[]`.

**The hypothesis came back clean.** All five render honest empty states, zero crashes, zero JS errors,
action controls reachable. The Ops deadlock was the only instance. A negative result worth recording.

**But it surfaced something larger on the way past: `ExecutiveTerminal` was serving `fixtures.json` as
live governance KPIs** — the last and largest instance of the exact class already fixed twice, on the
most stakeholder-facing screen in the app, with trend deltas ("+1.2% VS PRIOR PERIOD") implying a
historical baseline that exists nowhere in this system. `142 active users` against **3** real accounts.
8 open findings against 3 real gaps. 98% coverage. A fabricated AUG→JAN trend chart. Invented budget
figures including two `$450k`/`$120k` values hardcoded in the JSX. `UNIT_HEALTH: OPTIMAL` hardcoded.
`FISCAL_CONTEXT: Q3_FY2026` frozen (correct by luck in August, wrong from October). And `1M/3M/6M/YTD`
buttons with no `onClick` — the same defect as ComplianceTerminal's removed buttons. Roughly the top
two-thirds of the screen; the bottom third (identity audit, policy engine) always was genuinely real.

Fixed per the user's chosen approach, *wire what's real, label the rest* (`ExecutiveHonesty_refactor.md`):
the three footer metrics now compute from real state (unresolved TPRM gaps / policy `source_doc`
coverage / user count) via the established `_run_async` sync-bridge — using raw SQL for the gap count,
because `core.tprm` imports `core.database` and the ORM route would be circular. Four unbackable panels
got `Reference` badges with honest captions. `UNIT_HEALTH` now reads the real `/readiness` endpoint;
`FISCAL_CONTEXT` computes. Dead period buttons removed. **`policy_coverage` now honestly reads 0%** —
true, matching `policy-analyzer`'s independent finding, and deliberately not massaged.

**Verified:** new `backend/tests/test_executive.py` (**pytest 33 → 38**), **smoke 43/43**, **15/15**
browser checks with zero console errors, and an audit re-run showing no regression (Executive's button
count correctly 10 → 6).

**Three corrections from this session, all mine:**

- **A verification check gave a false pass.** `"READY" in page_text`, meant to prove `UNIT_HEALTH` was
  wired to real readiness, was satisfied by the unrelated `AUDIT_STATE` KPI card that also reads
  "READY" — while the tile actually rendered `--`. **A screenshot caught it, not the check.** This is
  the *second* false pass from whole-page text assertions in two days (the first nearly hid the
  evidence-notes data loss). Rewritten to read the specific DOM node. Lesson recorded in `MEMORY.md`:
  take screenshots even when checks are green.
- **That `--` then turned out to be correct behaviour**, not a bug — `/readiness` resolves after first
  paint, so the honest placeholder shows briefly before settling on `READY`. Confirmed by DOM dump and
  a cropped screenshot. The check now waits.
- **A scary rebuild failure was transient.** Compose reported `grc-backend is unhealthy / dependency
  failed to start` and never started the frontend; the backend logs showed a clean boot with health
  returning 200. Compose gave up before the healthcheck threshold. A second plain `up -d` fixed it.
  Consistent with the existing `MEMORY.md` warning about post-rebuild red herrings on this WSL2 setup.

**One addition beyond the approved draft, disclosed:** once four panels carry a `Reference` badge, the
three real footer metrics read as ambiguous by omission — added a counterpart green `Live` badge.
Three lines, serves the fix's purpose, called out rather than slipped in.

**Also noted honestly:** the audit re-run's Compliance row showed populated data rather than the empty
state, because the script arms interception after login and Compliance is the default landing terminal.
The original run did observe its genuine empty state; the re-run just didn't re-test that path.

**Next:** the component test harness (Vitest + React Testing Library, empty/render-state contracts for
all five terminals plus regressions for the three bugs fixed 2026-08-16/17) — now unblocked, and it will
assert the *corrected* Executive behaviour. It touches `package.json` and adds dev dependencies, so it
comes as its own draft.

---

# Session Log — 2026-08-16/17 ("Closing the UI Dogfooding Gap: Two Real Bugs, Both Fixed")

**Outcome:** Closed the open item the 2026-08-13 pass left behind — the browser/UI half of the
dogfooding ask. **First correction of the session: 2026-08-13's "no browser-automation tool was
available" was wrong.** The host's Python `playwright` package works with zero setup (Chromium 141);
nothing needed installing. Drove the real React UI as `admin` against the *same*
`Meridian Cloud Storage` data rather than throwaway records, having first confirmed the dataset was
intact (2 integrations, 21/3/2 pass/gap/N-A split, 3 acceptances, 2 evidence links) and dumped all 26
stage evidence notes to CSV *before* any mutating click.

**Two real bugs found, both invisible to the API-layer pass, both fixed and verified the same
session** (drafted per `GOVERNANCE.md` §4.A, EXECUTEd on approval):

1. **Stage evidence-notes wipe — silent data loss.** Clicking `pass`/`gap`/`review` on a stage
   destroyed that stage's `evidence_notes` and reassigned `reviewed_by`, with no warning or undo. The
   UI omits `evidence_notes` for those three statuses (only the N/A branch sets it), `JSON.stringify`
   drops the undefined key, and `tprm.py` assigned it unconditionally — so "field not sent" became
   "erase the audit rationale". Confirmed at the DB layer (notes 26 → 25 on one click) *and* as a
   user-visible symptom. Worth naming: `stage_responses` is not covered by the immutability triggers
   protecting `audit_logs`/`evidence_chain`/`risk_acceptances`, so the sign-off artifacts are
   append-only while the reasoning justifying them was overwritable. Fixed by gating on
   `payload.model_fields_set` (omission preserves, explicit null still clears) + a new pytest
   regression test. `StageNotes_Preservation_refactor.md`.
2. **Operations terminal deadlock.** `OpsTerminal.jsx`'s `!activeJob` early return sat *above* the
   **Run Agent** button — the only UI control that can create an agent run — so zero runs meant no way
   to start one, permanently. Reachable precisely *because* of legitimate recent work (Tier 4 hygiene
   + a restart left `agent_runs` genuinely empty). Fixed by scoping the empty state to the console
   pane. **The fix also had to remove a fabricated stats default** (`{running: 2, failed: 2}`, only
   recomputed when `jobs.length > 0`): invisible today *only because* the early return hid the header,
   so shipping the obvious fix alone would have displayed invented operational activity — the same
   class of dishonesty the ComplianceTerminal work existed to remove.
   `OpsTerminal_EmptyState_refactor.md`.

**Everything else passed:** zero console errors, zero failed requests, zero 4xx/5xx across every run.
CSV export downloads end-to-end from the browser (the control that previously carried a dead-auth-header
bug), the RISK ACCEPTED block renders with signer + expiry, evidence shows hash/uploader, tier badges
and N/A stages render correctly, and the 2026-08-06 panel-collapse fix still holds.
**Verification after the fixes:** smoke **43/43**, pytest **33/33** (was 32 — the new regression test),
plus a 16/16 browser pass. Meridian dataset diffed **byte-identical** to its pre-pass backup at the
end.

**Three method notes worth carrying forward, all self-corrections:**

- **A green check whose precondition never held is worse than a red one.** Run 1's "notes preserved"
  check *passed vacuously* — the UI CSS-uppercases text, so `inner_text()` returns `NOTES`, and the
  case-sensitive precondition was itself false. That green would have hidden the data-loss bug
  entirely. All 7 of run 1's "failures" were likewise script bugs, not app bugs.
- **A phantom bug, caught before reporting.** `api.post('\run-agent', …)` appeared to contain a `\r`
  escape that would break the endpoint. It doesn't — the file has a real forward slash (`U+002F`),
  verified by character codes *and* by watching the live request succeed. The search tool's output
  renders `/` as `\` in some content lines on this Windows setup (same artifact made
  `border-white/10` look like `border-white\10`). Verify that class of finding against raw bytes.
- **A planned verification step that had to change.** The Ops fix was meant to be verified against the
  isolated test stack (boots with zero runs), but `docker-compose.test.yml` has no frontend and
  `:3006` points at the dev backend; deleting the dev stack's `agent_runs` was correctly blocked as a
  destructive write. Substituted Playwright route-interception of `/ops/jobs` → `[]`, which isolates
  the frontend change and destroys nothing — arguably better, but a real deviation, so it's on the
  record in the refactor doc.

**Left deliberately:** `agent_runs` holds 3 real rows (seeded to break the deadlock, plus the runs the
verification created) — they keep Operations reachable, not test noise. **Still open:** no frontend
regression test for either bug (zero frontend component tests project-wide; both bugs this pass were
frontend-triggered, which is a fair argument the gap now costs something), and the UI still has no way
to *author* a stage note for pass/gap/review — read-only display, only the N/A prompt creates one, so
a browser-only analyst cannot write the rationale for a control they just passed. Needs a UI decision;
deliberately not bundled into a data-loss fix.

---

# Session Log — 2026-08-13 ("Committing a Half-Closed Session, a Genuine TPRM Dogfooding Pass, and a Forced LLM Migration")

**Outcome:** Picked up mid-stream from a prior session (2026-08-13) that had left work executed but
uncommitted — the working tree had two finished, verified refactors sitting as diffs: the
`Framework_Mappings` honesty caption and TPRM Tier 4 test-data hygiene (isolated test stack + dev-
stack reset). Investigated both diffs against their own `_refactor.md` docs (already marked EXECUTED
with verification detail) to confirm they matched what was claimed before committing anything — they
did, exactly. Committed as two commits (`6bb960f`, `56aaac1`), matching this repo's established
one-commit-per-refactor-doc convention. Then, with the dev stack confirmed clean (0 vendors/
integrations post-Tier-4-reset) and no strong pull toward a specific build, ran the standing
recommendation: a genuine dogfooding pass (see `MEMORY.md`'s "Project direction," open since
2026-08-06). No browser-automation tool was available this session, so it covered the backend API
surface only — real judgment-driven use of the same endpoints the frontend calls, not actual UI
clicking. **Zero application bugs found** — a real (negative) result, distinct from every prior pass,
which had each found at least one genuine bug.

## What happened, in order

1. **Investigated the 15-ish dirty working-tree items** the user flagged, rather than assuming they
   were safe to commit blind: read both untracked `_refactor.md` docs (`FrameworkMappings_Honesty_
   refactor.md`, `TPRM_Tier4_TestDataHygiene_refactor.md`), confirmed each already said `Status: ✅
   EXECUTED` with real verification numbers (Playwright 5/5, pytest 32/32, smoke 43/43), then diffed
   every changed file against what the docs claimed — `git diff` on `ComplianceTerminal.jsx` and all
   nine test files matched the docs' own diffs exactly, including a duplicate-import cleanup in
   `test_iam_08.py`. Checked `docker-compose.test.yml`'s default password fallback against
   `docker-compose-v2.yml`'s pre-existing convention before staging it, to rule out a new secret
   being introduced.
2. **Committed as two commits**, splitting `ComplianceTerminal.jsx`+doc from the nine test files+
   `docker-compose.test.yml`+doc (letting `MEMORY.md`/`task.md`'s combined diff ride with the larger
   TPRM Tier 4 commit, since splitting those two files' hunks precisely wasn't worth the friction for
   a same-day, same-session pair of changes).
3. **Confirmed dev stack state before proposing the dogfooding pass**: `docker compose ps` (all
   healthy), `/api/v1/readiness` (all green), direct `psql` count (0 vendors, 0 integrations) — not
   assumed from the Tier 4 doc's claim.
4. **Asked the user directly** how to source the dogfooding vendor (real vendor vs. realistic
   fictional vendor vs. user-driven browser walkthrough) rather than guessing — this is a judgment
   call about real-world exposure and time cost only the user could make. Chose: realistic fictional
   vendor, filled out with genuine reasoning.
5. **Read the actual TPRM module** (`core/tprm.py`, `data/seed_tprm_stages.py`) cold rather than
   working from memory of the roadmap docs, to get the real 13-stage egress/ingress question sets,
   endpoint payload shapes, RBAC capability names, and role hierarchy (`admin=3 > analyst=2 >
   viewer=1`) right.
6. **Wrote a one-off driver script** (`dogfood_tprm_pass.py`, kept in scratchpad, not committed —
   deliberately not a new permanent fixture generator, which would work against the same test-data-
   hygiene principle Tier 4 just fixed) that creates one vendor, **Meridian Cloud Storage**, with a
   CRITICAL-tier egress PII-backup integration and a LOW-tier ingress DR-test-return integration, and
   walks all 26 assessment stages with individually reasoned pass/gap/not_applicable judgments (not
   placeholder text) — 2 deliberate gaps on egress (manual SSH-key rotation; a 72hr vs. 24-48hr
   breach-notification mismatch), 1 gap + 2 genuine not-applicables on ingress. Also uploads 2
   evidence files, signs 3 risk acceptances, approves both integrations, and probes RBAC boundaries
   (unauthenticated, viewer, analyst) at each privileged step.
7. **Ran it against the real dev stack** (`localhost:8001`, not the new isolated test stack — the
   whole point is this is the app's first genuine non-test data). **61/61 checks passed.**
   Cross-checked beyond just trusting API responses: `docker logs grc-backend` showed only expected
   `Security Event` log lines (no swallowed exceptions), and a direct `psql` query confirmed the DB
   state matched exactly (26 stage responses split 21 pass / 3 gap / 2 not_applicable, 3 risk
   acceptances, 2 evidence links, vendor tier correctly recomputed to CRITICAL as the max across its
   two integrations).
8. **Documented the result** in `TPRM_Dogfooding_Pass_2026-08-13.md`, `task.md`, and `MEMORY.md`'s
   "Project direction" section — explicitly flagging what this pass does *not* cover (real browser/
   UI interaction — no automation tool was available this session) so a future session doesn't
   mistake "API-layer dogfooding passed clean" for "the dogfooding ask is fully satisfied." Also
   flagged Meridian's vendor data as real state now, not test noise, so a future Tier-4-style cleanup
   doesn't sweep it up by mistake.
9. **Ran the full boot-ritual verification** (`smoke_test.py` + `pytest`, both against the new
   isolated test stack) before committing the doc updates, as a sanity check — pytest came back
   32/32 clean, but smoke_test.py returned 28/34 with a cluster of 401s. Investigated rather than
   re-running blind: `docker logs grc-backend-test` showed the real cause was external, not a
   regression — `GOOGLE_API_KEY` hit a `403 PERMISSION_DENIED` and then the free-tier's
   20-requests/day `429 RESOURCE_EXHAUSTED` cap during the `active-auditor` RAG call, and with no
   fast-fail/circuit-breaker in `rag.py`'s retry loop, that single request stayed blocking the whole
   single-threaded backend for **~23 minutes** — long enough that the smoke test's own JWT expired
   mid-wait and cascaded into 401s on every subsequent check, including the TPRM vendor-creation
   check. Confirmed this wasn't a regression from anything committed this session (pytest's 32/32
   doesn't touch RAG at all; the dogfooding pass's 61/61 had already proven the TPRM/RBAC code path
   clean minutes earlier on the dev stack). Logged as a new `MEMORY.md` gotcha with an explicit open
   action item (check the Gemini project's billing/quota status) rather than silently patching
   `rag.py`'s retry behavior without being asked.
10. **User revealed the root cause directly**: they'd stopped paying for the Gemini API key — the
    `PERMISSION_DENIED`/quota issue wasn't transient, it was permanent. Asked what to use instead
    rather than guessing; recommended Groq's free tier (over local Ollama) as the lower-friction move
    most likely to hold the 92% RAG benchmark baseline, since `core/rag.py` already goes through
    LangChain's provider-agnostic chat-model interface — confirmed this via a cold read of `rag.py`
    before recommending, not assumed. User confirmed Groq.
11. **User asked whether to reuse an existing Groq key from a different project** — answered directly
    (dedicated key recommended: free-tier limits pool per-account either way, so a separate key buys
    clean usage attribution and independent revocation, not more quota) rather than treating it as
    obvious. User created a dedicated key and pasted it in chat.
12. **Migrated `core/rag.py`'s LLM call from `ChatGoogleGenerativeAI` to `ChatGroq`**
    (`llama-3.3-70b-versatile`), plus `requirements.txt`, `config.py`, `main.py`'s readiness/root-
    endpoint text, both `docker-compose*.yml` files, and `CLAUDE.md`'s architecture header. **Also
    closed the actual reliability gap from step 9, not just swapped providers**: added
    `max_retries=2, timeout=30` to the new client, since the old integration's total absence of any
    bound is what let one bad Gemini response block the backend for 23 minutes — bounding it now
    means no future provider's hiccup can reproduce that regardless of which API is behind it.
13. **A secret-hygiene mistake, caught and disclosed immediately**: a `grep` intended to check
    whether `.env` already had a `GROQ_API_KEY` line used `-n` (content) instead of `-c` (count) and
    printed the existing `GOOGLE_API_KEY` value into the transcript. Told the user directly in the
    same turn and recommended rotating that key in Google Cloud Console — practical risk was low
    (the key was already dead), but flagged rather than left unmentioned. Used `-c`-only checks and
    `sed`-based in-place edits for the rest of the `.env` work to avoid repeating it.
14. **Verified live, not just import-clean**: rebuilt both `grc-backend` and `grc-backend-test`
    images from the updated `requirements.txt`, confirmed `/api/v1/readiness` reports the Groq key as
    ready on both stacks, ran a real `/api/v1/chat` call that answered correctly with real corpus
    citations, then re-ran the full boot-ritual suite — **smoke 43/43** and **pytest 32/32**, both
    measurably *faster* than the failing-Gemini run from step 9 (pytest 76s vs. 108s). The specific
    `active-auditor` call that had blocked for ~23 minutes under the dying Gemini key completed in
    **~31 seconds** against Groq — back at the originally-documented baseline, confirming the block
    was the API key's failure mode, not something wrong with the architecture itself.
15. **Caught and fixed a dating mistake before committing**: had written "2026-08-14" throughout the
    new migration doc and doc updates, going purely off UTC timestamps in Docker logs without
    converting to local time. Checked directly (UTC 02:25 on the 14th converts to 22:25 EDT on the
    13th) — still the same calendar day this whole session has been dated. Renamed the doc file and
    corrected every reference before it could seed a future session's confusion, consistent with this
    workspace's own standing rule to convert relative/ambiguous dates to absolute ones and get them
    right the first time.
16. **Documented in `LLM_Groq_Migration_2026-08-13.md`, `task.md`, `MEMORY.md` (resolving the step-9
    gotcha rather than leaving it as an open action item), and `HANDOFF.md`** — including an explicit
    flag that the 92% RAG benchmark figure is now stale (measured against Gemini, not yet re-run
    against Groq) so a future session doesn't quote it as current without re-running
    `rag_benchmark.py` first.

---

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

## Session close: a full assessment, and the durable direction it produced

After the four builds above, the user asked for a full professional assessment of the whole system
against real market GRC tools (Vanta/Drata/OneTrust-style continuous compliance automation,
ServiceNow/Archer-class enterprise GRC suites, ProcessUnity/Prevalent-class TPRM tools). Gave an
honest one: strong on domain modeling (TPRM's 13-stage lifecycle, DB-level immutability enforcement)
and on process discipline (draft-first governance, a doc trail that survives context resets, a
demonstrated pattern this session of finding and correcting real problems — including three of its
own draft estimates — rather than declaring victory on green tests); genuinely behind category
leaders on exactly the things that can't be fixed by writing better code alone (no real
infrastructure integration, no multi-tenancy/SSO, single-process architecture with the
full-backend-blocking issue found tonight, zero frontend tests). Also flagged that calling the two
registered agents "agentic" is a stretch against what that term now usually implies, though the
constrained zero-trust dispatch model is arguably the more defensible design choice for a
regulated-industry context regardless.

**User's response, now the durable framing for this project (also recorded in `MEMORY.md`):** this
is explicitly a progressive project — production is the eventual goal, not an imminent one, and the
gap list is already fully priced in, not new information. What the user wants before any real
production push is a genuine hands-on, rigorous personal-use pass — actual end-to-end workflows, not
the isolated feature-verification pattern used all session. That's the right thing to propose next
time the backlog runs dry or production comes up as a live topic, not a checklist to start closing
unprompted.

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
