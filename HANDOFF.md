# GRC Command Center — Session Handoff (v1.4.0)

> ⚠️ **This file is stale as of 2026-08-17 — read the update block first, then treat the rest as
> historical.** Its "Recommended order for next session" is largely done.
>
> **What changed 2026-08-16/17:** the UI/browser dogfooding pass (its Step 2) **is complete**, and the
> two real bugs it found are **both fixed, verified, and documented** —
> `TPRM_Dogfooding_UI_Pass_2026-08-16.md`, `StageNotes_Preservation_refactor.md`,
> `OpsTerminal_EmptyState_refactor.md`. Read `SESSION.md`'s 2026-08-16/17 entry (top of file) for the
> narrative.
>
> ## ▶ NEXT SESSION — start here (set 2026-08-17)
>
> **These are ordered by value, NOT by dependency — items 1-3 are independent and none blocks
> another.** Golden Mapping and the content filter are both query-time changes needing no re-index;
> the corpus review is the only item requiring a re-ingest (~11 min). The user can therefore start
> the corpus review at any time, in parallel, without waiting on any code change. **What does need
> sequencing is measurement**: benchmark between changes (v8/v9/v10) so each lever's effect is
> attributable, per the standing one-variable-per-run convention — or bundle deliberately and accept
> a single unattributable reading.
>
> 1. **Golden Mapping entries for the enumeration queries (#4, #6, #12, #18).** Highest-value lever on
>    RAG accuracy. These four are **one root cause**: 1000-char chunking shatters multi-page
>    enumerations, so "list/explain the whole framework" queries retrieve fragments and the model
>    correctly refuses. Golden Mapping is the established fix (it closed the EU AI Act cluster).
>    Do **not** re-diagnose #18 as a retrieval bug — that was investigated and disproved, see
>    `RAG_Benchmark_Report_v7.md` §Correction.
> 2. **Minimum-content / quality filter before re-ranking.** ~30% of #18's context budget went to a
>    mojibake sponsors page and two sub-150-char stubs. A length threshold plus a non-ASCII-ratio guard
>    fixes this class across all 158 documents automatically — and keeps working for future additions.
> 3. **Corpus authority review — user-led, human judgement required** (user's own proposal, 2026-08-17).
>    See "Corpus composition" below: a crude name heuristic flags **33 of 158 PDFs** as personal or
>    secondary material, and `MEMORY.md` already carries an "official sources only" rule that predates
>    much of it. Evidence it costs accuracy: on query #12 (ISO 27001 mandatory documentation)
>    `Notes from Study +.pdf` supplied **4 of 10 chunks and out-retrieved the actual standard**.
>    **Removing documents requires a re-ingest (~11 min) and will move the benchmark — treat it as one
>    deliberate change with a v8 measurement, one variable per run, and archive first.**
> 4. **Frontend component test harness** (Vitest + RTL) — still unbuilt, still the only protection
>    missing for three frontend fixes made 2026-08-16/17. Touches `package.json`; needs its own draft.
>
> Lower priority, still open: establish whether v7's latency is free-tier rate limiting (not yet
> proven a model property); migrate `diagnose_rag.py`/`validate_diagnostic.py` off the dead Gemini key
> (has now blocked analysis twice); the binary benchmark scorer cannot distinguish a correct refusal
> from a failure and currently **rewards the less honest model**.
>
> **Corpus composition (measured 2026-08-17):** 158 PDFs / 684 MB. The four largest flagged files are
> `the-modern-analysts-guide-to-preparing-ai-ready-data` (35.4 MB), `Security plus study guide` (35.3 MB
> — Security+ cert prep, not GRC), `Grc Roadmap Booklet!` (35.0 MB) and `Notes from Study +` (24.1 MB) —
> ~130 MB, roughly 19% of the corpus by size. Also present: several "for Dummies" titles, multiple cheat
> sheets, and a **LinkedIn advertising carousel**
> (`Carrossel-LinkedIn-AD1-InsideCouncil-powerfront-...compressed.pdf`). The heuristic over-flags —
> `Nist Guide to RA.pdf` is official NIST and legitimate — which is exactly why this step needs a human,
> not a script.
>
> **Update 2026-08-17 (later):** the RAG benchmark below is **done** — and running it uncovered that
> Groq had retired `llama-3.3-70b-versatile`, leaving the core engine dead for ~4 days while four
> separate checks reported green. Model is now **`openai/gpt-oss-120b`**; readiness/smoke/agent checks
> were all hardened and proven with negative tests. **Current baselines: smoke 44/44, pytest 38/38,
> RAG accuracy 90.0% (v7).** See `RAG_Model_Outage_refactor.md` and `RAG_Benchmark_Report_v7.md`.
> Top follow-up: **query #18 retrieves only 1 source** on a document added specifically to serve it.
>
> **Corrections to the text below:**
>
> - "if browser-automation tooling is available this session" — **it is.** The host's Python
>   `playwright` package works with zero setup (Chromium 141). The claim that it wasn't available on
>   2026-08-13 was simply wrong and cost three days.
> - **pytest is now 33/33, not 32/32** (new regression test for the notes-wipe bug).
> - Step 1 (**re-run `rag_benchmark.py` against Groq**) is **still not done** — it remains the single
>   most useful quick item, and RAG accuracy is still officially UNKNOWN post-migration. Don't quote
>   92%.
> - Step 3's optional items are all still open and still optional.
>
> **New open items from the 2026-08-16/17 work:** (a) no *frontend* regression test for either fixed
> bug — zero frontend component tests exist project-wide, and both bugs were frontend-triggered;
> (b) the UI has **no way to author a stage note** for `pass`/`gap`/`in_review` (read-only display;
> only the N/A prompt creates one), so a browser-only analyst cannot record why a control passed —
> needs a UI decision, deliberately not bundled into the data-loss fix.
>
> **Uncommitted:** everything from 2026-08-16/17 is in the working tree, **not committed** — the repo
> convention is one commit per refactor doc; see the end of `SESSION.md`'s newest entry.

## Continue from this point in a new chat

**Date:** August 13, 2026
**Version:** 1.4.0 — RAG tuned + Golden Mapping; TPRM (all tiers) complete and browser-verified;
Execution Monitor UI + Agent Registry De-stubbing + ComplianceTerminal/Framework_Mappings honesty
fixes all built and verified; TPRM Tier 4 test-data hygiene; a first (API-layer-only) TPRM
dogfooding pass; LLM provider migrated Gemini → Groq.
**Baselines:** smoke test **43/43** · pytest **32/32**, both against the isolated test stack
(`docker-compose.test.yml`, port 8002), now running on **Groq** (`llama-3.3-70b-versatile`) — see
`LLM_Groq_Migration_2026-08-13.md`. **RAG accuracy is UNKNOWN as of the provider switch** — 92% was
measured against Gemini 2.5 Flash and has not been re-run against Groq. Don't quote 92% as current.
**Everything is pushed** (`c130234`).

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center (v1.4.0). Read `MEMORY.md` (durable facts),
`SESSION.md` (last session's log — the 2026-08-13 entry at the top has the full narrative), and
`task.md` (live board) in the project root, then verify the stack per the boot ritual in `MEMORY.md`
before proposing anything.

**Current state, in brief:** TPRM's entire roadmap (Tier 1-4) is complete and browser-verified,
including test-data hygiene — the dev stack runs on an isolated test-suite stack now
(`docker-compose.test.yml`, port 8002) so `pytest`/`smoke_test.py` no longer pollute dev-stack data.
RAG P3 Execution Monitor UI, Agent Registry De-stubbing, and the ComplianceTerminal +
Framework_Mappings honesty fixes are all built and browser-verified (see `SESSION.md`'s 2026-08-06
entry for that work's detail). **Two things changed most recently (2026-08-13), both need
follow-up:**

1. **A first TPRM dogfooding pass ran, API-layer only** — one realistic fictional vendor (`Meridian
   Cloud Storage`, two integrations, 26 individually-reasoned stages, evidence uploads, risk
   acceptances) driven through the real backend. 61/61 checks passed, zero application bugs found
   (see `TPRM_Dogfooding_Pass_2026-08-13.md`). **Not yet verified in an actual browser** — no
   automation tool was available that session, so whether `VendorRiskTerminal.jsx` actually *renders*
   this data cleanly is still unknown. Prior browser passes (2026-08-06) found real bugs an API-only
   check would have missed (panel-collapse, a missing auth header on an export button) — don't treat
   the API-layer pass as equivalent to the real thing.
2. **The LLM provider was forced to migrate from Gemini to Groq** — the user stopped paying for the
   Gemini API key, which was also the direct cause of a ~23-minute full-backend block found during
   that session's boot-ritual check (no fast-fail on the old client). Migrated `core/rag.py` to
   `ChatGroq` (`llama-3.3-70b-versatile`), added explicit `max_retries=2, timeout=30` so no future
   provider hiccup can reproduce that block, verified live (real `/chat` call, smoke 43/43, pytest
   32/32, a live `active-auditor` run back to its ~31s baseline). See
   `LLM_Groq_Migration_2026-08-13.md`. **The RAG benchmark has not been re-run against the new
   provider** — the last known number (92%) is Gemini-era and may not hold under Llama 3.3 70B.

**Important context for how to approach this project, not just what's built:** this is explicitly a
*progressive* project — the goal is eventually shipping to production, but not soon, no deadline
pressure. The user is already aware of the gaps a real GRC-tool comparison surfaces (no live
infrastructure integration, no multi-tenancy/SSO, single-process architecture, no frontend tests) —
don't re-raise those as new findings. Zero frontend component tests exist project-wide (known,
parked, not urgent).

---

## Recommended order for next session

**Step 1 — Re-run the RAG benchmark (do this first, it's quick and unblocks everything else):**
```powershell
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py
```
No code change needed — it hits `/chat` over HTTP, already confirmed working against Groq. Record
the real number (could land above or below 92%) before quoting any RAG accuracy figure. If it drops
meaningfully, that's worth surfacing to the user as a real tradeoff of the forced provider switch,
not silently absorbed.

**Step 2 — Finish the dogfooding pass in an actual browser, if browser-automation tooling is
available this session** (Playwright or similar). This is the single highest-value remaining item:
- Log in as admin, open `VendorRiskTerminal.jsx`, find `Meridian Cloud Storage` (already seeded on
  the dev stack — **don't create new throwaway vendor data**, use this one).
- Confirm the vendor portfolio strip, the CRITICAL/LOW tier badges, and both integrations' 26 mixed
  pass/gap/not_applicable stage rows all render without console errors or failed requests.
- Specifically check the CSV export button and the risk-acceptance detail panel — both are exactly
  the kind of thing the 2026-08-06 pass found broken (missing auth header, panel collapsing after
  in-panel actions) that an API-only check cannot catch.
- If no browser tool is available this session either, say so explicitly rather than re-running the
  API-only script again — that would just re-confirm what's already known and not add new signal.

**Step 3 — optional / only if there's a specific pull toward it:**
- Revisit `active-auditor`'s synchronous execution (not a defect — now that its real cost, ~43s/~31s
  full-backend blocking, is known precisely from two separate live measurements, worth a fresh look
  only if it starts to feel worse in practice).
- Migrate `backend/tests/diagnose_rag.py` / `validate_diagnostic.py` to Groq too — these are
  RAG-diagnostic/judge-calibration tooling, currently non-functional (still pinned to the dead
  Gemini key). Only worth doing if a future benchmark-diagnosis pass is actually needed.
- `EU AI ACT 2024_Doc.pdf`'s text-extraction defect (isolated to one corpus file, Golden Mapping
  already hand-patches the affected queries) — see `JUDGE_CALIBRATION_v2.md` §1/§4.
- Frontend component test coverage (zero exists project-wide) — known gap, not urgent, not something
  to silently start closing without the user asking for it.

**Standing housekeeping reminder (not urgent, user's call):** the old Gemini key was briefly printed
into a conversation transcript during the migration session (already low-risk — the key was already
dead — but flagged to the user directly at the time). Worth confirming it's been revoked in Google
Cloud Console if that hasn't happened yet.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
docker compose -f docker-compose.test.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 43/43 (hits :8002 by default)
cd backend; python -m pytest -v; cd ..                   # expect 32/32 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # NOT YET RE-RUN against Groq -- do this first
Invoke-RestMethod http://localhost:8001/api/v1/readiness  # dev stack health, read-only, safe anytime
```

**Notes:**
- `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an IPv6/IPv4 loopback
  mismatch in the healthcheck itself, not a real outage; see `MEMORY.md` gotchas). The app serves
  fine on `http://localhost:3006`.
- `smoke_test.py`/`pytest` target the isolated test stack (`:8002`) by default now, not the dev
  stack. To check the dev/dogfooding stack specifically, set
  `GRC_TEST_BASE=http://localhost:8001` first — see `MEMORY.md`'s "Boot & verify" section.
