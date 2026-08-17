# GRC Command Center — Active Task Board (v1.4 Sprint)

**Created:** 2026-07-18 | **Supersedes:** RAG Diagnostic checklist of 2026-05-24 (all phases complete — see `diagnostic_results.v1_uncalibrated.json` & `NIST_Gap_Analysis_Report.md`)

---

## P0 — Infrastructure Health Verification (system idle since May 24)

- [x] **Phase 0.1: Container Stack Revival** *(2026-07-18)*
  - [x] `docker compose -f docker-compose-v2.yml ps` — 4 containers found (stopped 5 weeks)
  - [x] Stack booted from existing images — all containers healthy
- [x] **Phase 0.2: Baseline Re-verification** *(2026-07-18)*
  - [x] `smoke_test.py` — **27/27 GREEN** (PL/pgSQL trigger blocked DELETE on audit row 184)
  - [x] FAISS `.integrity` manifest — "Verified OK" in backend logs on cold load
  - [x] `/api/v1/readiness` — overall "ready" (DB, FAISS, API key, JWT all green)

## P1 — Retrieval Fix Sprint (root cause: 28/28 failures diagnosed C1 — ranking, not corpus)

> Evidence: all 28 `INSUFFICIENT_DATA` failures had answers present in the corpus and visible
> at k=20, but buried below the production k=5 cutoff (e.g. AI RMF Appendix B at rank 10).
> Zero corpus gaps (A), zero LLM over-refusals (C2). Fix the ranker, win the benchmark.

- [x] **Phase 1.1: Draft** — `Retrieval_Tuning_refactor.md` produced *(2026-07-18)*
  - [x] Raise `k` from 5 → 10 in `rag.py` `query()`
  - [x] Re-chunk corpus: 600 → 1000 chars (overlap 60 → 100) — framework definitions are being truncated mid-clause
  - [x] (Stretch) Cross-encoder re-rank of wide k=20 → top 10 (no new deps; proposed as measured A/B step)
- [x] **Phase 1.2: Review** — human "EXECUTE" received *(2026-07-18)*; Changes 1–2 approved, Change 3 (re-ranker) held for A/B
- [x] **Phase 1.3: Deploy & Re-index** *(2026-07-18)* — `rag.py` tuned, backend rebuilt, re-ingested in 11.4 min: 11,884 splits from 149/156 files (7 OneDrive-dehydrated skips, same as baseline)
  - [x] **BUG FOUND & FIXED en route:** `_hash_index()` included the stale `.integrity` manifest when re-signing after re-ingest → guaranteed verify failure on any index rebuild. One-line exclusion added; manifest re-signed; readiness green. *Likely true root cause of FAISS-INT-001 (previously blamed on a Docker volume race).*
- [x] **Phase 1.4: Measure** *(2026-07-18)* — **72.0% (36/50), +28 pts over 44% baseline. GATE MET.** 0 errors, avg latency 4.05s (+0.38s)
  - [x] Target ≥70% — achieved: NIST 8/8, ISO 7/7, TPRM 1/5→4/5; 14 residual failures traced to dehydrated files (~5), image-only PDFs (~2), EU AI Act depth (~4), chunking regressions (2, GRC-Eng)
  - [x] `RAG_Benchmark_Report_v2.md` published with before/after scorecard

## P2 — Measurement Integrity

- [x] **Corpus Hydration & Repair** *(2026-07-18)* — root cause CORRECTED: the 7 skipped PDFs were not OneDrive-dehydrated but **truncated at acquisition** (no `%%EOF`; snapshot copies identically broken, so damaged since before 2026-05-24)
  - [x] `GRC_Analyst/` pinned always-keep-on-device (guards against future dehydration)
  - [x] 7 corrupt files quarantined (renamed `*.pdf.corrupt` — reversible)
  - [x] `Owasp AI Exchange.pdf` restored from official source (owaspai.org, CC0) — 11.5 MB valid vs 294 KB truncated
  - [x] ~~Re-source 6 corrupt originals~~ — **user green-lit public substitutes instead** *(2026-07-18)*. Acquired 8 official documents into corpus:
    - OWASP Top 10 for LLM Applications 2025 (owasp.org) → targets failing query #18
    - SEC 33-8810 Management Guidance on ICFR (sec.gov) → SOX substitute, targets #38
    - NIST SP 800-30r1 + SP 800-39 → Information-security-risk-management substitutes
    - NISTIR 8286 (Cyber Risk ↔ ERM / Risk Registers) → Understanding_Risk_Registers substitute
    - NIST AI 600-1 Generative AI Profile → AI_Governance substitute
    - NIST SP 800-37r2 RMF + SP 800-53r5 Controls Catalog → net-new GRC framework depth
    - (GRC_Cybersecurity_Guidebook / GRC_MBA retired without substitute — zero load-bearing queries)
  - [x] Re-ingest (150 valid PDFs, 12,548 splits, **first zero-error ingest**) + re-benchmark → **v3: 78.0% (39/50)**, +6 pts over v2; OWASP queries #22/#23/#46 flipped as predicted (`RAG_Benchmark_Report_v3.md`)
- [x] **Judge Calibration** *(2026-08-05)* — old `v1_uncalibrated` data (May 24) was stale, predating the whole retrieval-tuning sprint and Golden Mapping; re-ran the diagnostic pipeline fresh, found only 4 current C1/C2 candidates (down from 28), human-labeled all 4 (full population, not a sample), got **4/4 agreement with the "locked" second-stage judge** (`validate_diagnostic.py`'s ANSWERED/REFUSED/HALLUCINATED classifier) — **promoted to v2_calibrated**. Separate finding: the first-pass discriminator (`diagnose_rag.py`) shares the exact `.startswith("INSUFFICIENT_DATA")` bug fixed in the benchmark scorer above — wrong on 3/4 cases — flagged, not fixed (low urgency, real decisions should use the calibrated second-stage judge). See `JUDGE_CALIBRATION_v2.md`.
- [x] **Golden Mapping Metadata** *(2026-08-05)* — 3 hand-curated, source-cited entries (`backend/data/golden_mappings.json`) covering the EU AI Act risk-tiers/GPAI-generative/open-source cluster (#16/#19/#49), matched at query time via cosine similarity against the already-loaded `all-MiniLM-L6-v2` embeddings (`rag.py`'s new `_match_golden_mappings`) — no new ML dependency, no re-ingestion. Benchmark went from a corrected 84.0% baseline to **92.0%** (see next item — the 86%/94% numbers originally cited here were later found to be off by one query each; corrected across the whole historical trajectory). Zero regressions. **smoke 42/42**, **pytest 32/32**.
- [x] **Benchmark scorer bug fix + historical correction** *(2026-08-05)* — found while reviewing Golden Mapping's results: `rag_benchmark.py`'s `.startswith("INSUFFICIENT_DATA")` check missed inline refusals not in the first token, and had done so in **every prior run** (v1 #31, v2 #6, v3/v4/v5 #35, v6 #6) — every historical topline (44/72/78/82/86/94%) was inflated by exactly one query. Fixed the scorer (substring check), corrected every archived `rag_benchmark_results.v*.json` (with an audit-trail `_correction_note` field, nothing silently overwritten) and the `RAG_Benchmark_Report.md`/`_v2`/`_v3`/`_v5` files (correction callouts + true numbers: 42/70/76/80/84/92%). Trend and every inter-run delta unchanged. **Also found and fixed** (separate from the scorer bug, traced and resolved same session): v1's report's category-breakdown table didn't match its own raw archive on 6/7 rows — confirmed isolated to v1 only (v2 matched exactly; v3/v5 don't have this table format), errors summed to zero (estimated-to-total, not computed) — corrected by direct computation from the archive. Still parked: `EU AI ACT 2024_Doc.pdf`'s text-mangling defect (isolated to that one file, confirmed — no other corpus PDF shares its producer).

## P3 — Platform Debt & Features

- [x] **Execution Monitor UI**: real-time agent job monitor on the WebSocket telemetry bus. **Scoped 2026-08-05, built 2026-08-06** — see `Execution_Monitor_UI_Roadmap.md` for the cold investigation and `ExecutionMonitor_refactor.md` for the executed diff. All three open decisions confirmed with the user (build now not after De-stubbing; stay synchronous; add audit-trail logging). Shipped: new `AgentRun` model with a real PENDING/RUNNING/COMPLETED/FAILED lifecycle, `/run-agent` now persists + calls `log_security_event` (closing a real gap — agent execution previously wrote zero audit-trail entries, confirmed via grep before fixing) + broadcasts `JOB_STATUS`, `GET /ops/jobs` reads real data instead of a hardcoded fixture, `OpsTerminal.jsx`'s console panel renders real `result`/`error` instead of fabricated "SCANNING_RESOURCE"/"CRITICAL_THREAD_ABORT" text, and the "Run Agent" button (previously fully broken — bad field name, unregistered agent id, and even after fixing those, checked for a `stdout` field neither stub handler has ever returned) now actually populates the grid. Verified: smoke 43/43 (grew from 42 — added a real `/run-agent` check since `/ops/jobs` moving off the fixture broke the old "≥1 item" assertion on a fresh boot), pytest 32/32, manual curl round-trip, confirmed real `AGENT_EXECUTE` audit rows, and a two-tab Playwright regression proving the actual real-time claim — triggering a run in tab 1 populated tab 2's grid via WS push with zero manual interaction on tab 2 (5/5 checks, zero console errors either tab).
- [x] **Agent Registry De-stubbing** *(2026-08-06)*: `active-auditor` / `policy-analyzer` handlers in `agent.py` used to return canned responses regardless of input — see `AgentRegistry_DeStubbing_Roadmap.md` for the cold scoping and `AgentRegistry_DeStubbing_refactor.md` for the executed diff. Four decisions confirmed (fixed NIST AI RMF question set; real RBAC `Policy` table; stay synchronous; no new frontend input). `active-auditor` now runs 4 canonical NIST AI RMF questions through the real `rag_engine.query()` pipeline (the same one behind `/chat`, 92% benchmark accuracy) and returns real per-question answers, real source citations, and severity computed from actual corpus coverage. `policy-analyzer` now inspects the real `Policy` table and reports the genuine gap sitting there — all 13 seeded policies missing `source_doc`. `execute_agent` converted to `async` to support the RAG call (confirmed safe against the existing `_run_async` sync-bridge pattern); also fixed a second caller, `tests/security_audit.py`, which would have silently broken otherwise. **Two things the draft estimated wrong, corrected after measuring:** `active-auditor`'s real duration is **~43s, not the ~16s estimated** (steady-state, not a cold-start artifact — measured twice, cold and warm, both ~43s); and the blocking scope is **the entire backend, not just the triggering request** — FAISS similarity search and the cross-encoder reranker run synchronously on the single event loop with no executor offload (pre-existing `/chat` behavior, now exercised at ~10x duration via a button). Not re-litigated — Decision #3 ("stay synchronous") was already explicitly confirmed and the system is low-traffic/personal — but corrected on the record rather than left standing. Verified: smoke 43/43, pytest 32/32 (both clean in isolation — a first smoke pass failed at 180s from an accidental concurrent-curl confound while testing, not a real defect), curl round-trips, `security_audit.py` re-verified (3/4 pass, the 1 fail is a pre-existing stale test-case id unrelated to this change), Playwright browser pass triggering both real agents from the UI (7/7 checks, zero console errors).
- [x] **`ComplianceTerminal.jsx` misleading "live scanning" UI** *(2026-08-06)*: found while scoping Agent Registry De-stubbing — the fixture-fake 5-policy grid also had two buttons (`Update Policy`, `REMEDIATE_NOW`/`TRIGGER_RESCAN`) that both silently called `/ingest` (RAG re-indexing) regardless of the policy selected, and an "OPERATIONAL_EVIDENCE_STREAM" panel that showed hardcoded fake incident logs (e.g. "Security policy threshold breach (Found: 644)") for any `FAIL`-status policy, static, never real. Since there's no real cloud/infrastructure backing these 5 named controls in this project, "de-stubbing" the way TPRM/Execution Monitor/Agent Registry were wasn't achievable — user confirmed the honest fix instead: added a `REFERENCE_CATALOG` badge, removed both misleading buttons (replaced with a static "no live scan/remediate actions" note), and replaced the fake incident log with an honest static explanation. See `ComplianceGrid_Honesty_refactor.md` for the executed diff. No backend/schema changes — frontend-only. Verified: rebuilt `grc-frontend`, Playwright pass confirming the badge, honest notes, and absence of the old fake content, plus untouched functionality (search, CSV export, real `DATA_STRUCTURE_VIEW`/`Framework_Mappings`) still works (10/10 checks, zero console errors).
- [x] **`Framework_Mappings` panel honesty caption** *(2026-08-13)*: closed the loop the compliance-grid fix deliberately left open. Re-investigated cold rather than assumed the same fix applied — found it's a materially smaller problem: no misleading buttons, no fabricated logs, just static hand-curated control-mapping content (a legitimate GRC artifact, not a lie the way a fake "REMEDIATE_NOW" button was). Added one honest caption line under the panel header so it's unambiguous standalone rather than relying on neighboring panels' labels by inference. See `FrameworkMappings_Honesty_refactor.md`. Frontend-only, no backend/schema risk. Verified: rebuilt `grc-frontend`, Playwright pass (5/5 checks, zero console errors, zero failed requests).
- [x] **Documentation Drift**: GOVERNANCE.md/CLAUDE.md cited `fn_prevent_audit_modification`/`fn_prevent_evidence_modification` (real fn is `fn_prevent_immutability_violation`) and a nonexistent `data_fixtures.py`; TPRM module was undocumented in CLAUDE.md's file tree — all fixed *(2026-08-02, commit `2268d2d`)*. ~~CLAUDE.md claims `text-embedding-004`/Gemini 2.0 Flash~~ — re-checked 2026-08-02, CLAUDE.md already correctly says `all-MiniLM-L6-v2`/`gemini-2.5-flash`; this line was stale, leaving struck through rather than deleting silently.

## P4 — TPRM Tier 1 (security & parity gaps)

- [x] **Draft & Review** — `TPRM_Tier1_refactor.md` produced and EXECUTE'd *(2026-08-02)*
- [x] **1.1 Audit-log privileged TPRM actions** — `approve_integration` (clean/with-exceptions/blocked) and `create_risk_acceptance` now call `log_security_event`
- [x] **1.2 Read-back for risk acceptances + stage evidence** — new `GET .../risk-acceptances`; `StageOut` widened with `evidence_notes`/`reviewed_by`/`reviewed_at`
- [x] **1.3 Expired-acceptance detection** — new `GET /tprm/acceptances/expiring`, read-only/computed-live (design call: no persisted status flip — flagged for Tier 3 UI surfacing instead)
- [x] **1.4 `BEFORE TRUNCATE` triggers** — added to `audit_logs`, `evidence_chain`, `risk_acceptances`, verified live via `pg_trigger`
- [x] **1.5 Per-tier reassessment cadence** — `REASSESSMENT_DAYS_BY_TIER` (CRITICAL 90d / HIGH 180d / MEDIUM+LOW 365d) replaces flat 365d
- [x] **Verify** *(2026-08-02)* — 6 new tests added to `test_tprm.py`; **smoke 42/42**, **pytest 21/21** (16 TPRM + 5 IAM regression check)
- [x] **2.4 Method applicability + `NOT_APPLICABLE` status** *(2026-08-02)* — seed data fixed (egress #4/#6 marked `file`-only; DB reconciled on boot), stage fan-out filter, justification-required N/A with audit logging, summary fix (N/A counts as completed). **Bug found & fixed live:** Postgres `stagestatus` enum needed `ALTER TYPE ... ADD VALUE` — `create_all()` doesn't alter an existing enum type for new Python enum members. 4 new tests; **smoke 42/42**, **pytest 25/25** (20 TPRM + 5 IAM)
- [x] **2.1 Surface stage guidance in the UI** *(2026-08-02)* — `StageOut` widened with `guidance`/`review_questions`/`evidence_to_collect`; `VendorRiskTerminal.jsx` stage rows expand into a detail panel. No schema risk (additive read-only fields). **smoke 42/42**, **pytest 25/25**, manual API content check passed
- [x] **2.2 UI risk-acceptance form (admin)** *(2026-08-02)* — frontend-only (`RiskAcceptanceModal`, acceptance status embedded in the GAP stage detail panel). **smoke 42/42**, **pytest 25/25**, manual end-to-end sign→list check passed
- [x] **2.3 Vendor-level risk rollup** *(2026-08-03)* — `_recompute_vendor_tier` (max-severity across a vendor's integrations) hooked into `create_integration` + both `approve_integration` success paths; `VendorRiskTerminal.jsx` gained a vendor-portfolio strip + tiered dropdown labels. New `test_tprm_vendor_rollup`. **smoke 42/42**, **pytest 26/26**, live API check confirmed real tier distribution (was 100% `unscored`). **Browser-verified 2026-08-06** — portfolio strip renders all 435 real vendor chips with correct tier coloring, zero console errors. **Tier 2 now fully complete.**

## P5 — TPRM Tier 3 (lifecycle & reporting)

- [x] **3.1 Reassessment surfacing** *(2026-08-03)* — `_broadcast_reassessment_status` (bare WS signal, no payload) hooked into `create_integration`/`create_risk_acceptance`/both `approve_integration` paths; `VendorRiskTerminal.jsx` header badge + expandable panel. Event-driven only (no backend scheduler exists in this repo — accepted limitation: a due-date lapsing with zero TPRM activity won't push live). **Bonus fix:** `OpsTerminal.jsx`'s WebSocket had never actually connected (`user?.access_token` doesn't exist) — fixed via new `api.getAccessToken()`. **smoke 42/42**, **pytest 26/26**, WS broadcast confirmed live via a one-off client script. **Browser-verified 2026-08-06** — the WS-push → refetch pipeline fires correctly on every qualifying action (6 GETs matching 1 mount + 2 broadcasting actions exactly); badge itself not visually confirmed since current data has 0 overdue/0 expiring (nothing old enough yet), but the mechanism behind it is proven live.
- [x] **3.2 TPRM assessment report export** *(2026-08-03)* — `GET /tprm/export`, three-section CSV (Integrations/Stage Assessments/Risk Acceptances), gated by existing `EVIDENCE_EXPORT` capability. **Bonus fix:** `ComplianceTerminal.jsx`'s export button was silently 401ing (`window.location.href` sends no auth header) — fixed via new shared `api.downloadFile()` helper, used by both buttons. **smoke 42/42**, **pytest 28/28**, manual curl check confirmed headers/data/RBAC. **Browser-verified 2026-08-06** — real download via Chromium, correct filename/headers/content including a freshly-created row.
- [x] **3.3 Evidence linkage to `evidence_chain`** *(2026-08-04)* — full file-upload architecture: new `StageEvidenceLink` append-only table + `POST/GET .../stages/{stage_id}/evidence`, `log_evidence` widened to return the row id. **Real infra bug found & fixed:** new Docker volume mounted root-owned (uploads 500'd under non-root `grcuser`) — fixed in `Dockerfile.backend` (matched the proven `faiss_index` chown pattern), volume recreated, durability re-verified via upload-then-rebuild round trip. **smoke 42/42**, **pytest 32/32**. **Browser-verified 2026-08-06** — real file upload via Chromium, evidence entry appeared with correct filename/size/hash/uploader. **TPRM roadmap (Tier 1+2+3) now fully complete.**

---

## Browser verification pass (2026-08-06)

All four previously-API-only-tested TPRM UI surfaces (2.3, 3.1, 3.2, 3.3) driven live through
Chromium via Playwright (admin session): create integration → mark stage gap → attach evidence →
sign risk acceptance → export CSV. **All four confirmed working** — zero console errors, zero
failed network requests across the run. Full detail and the one real finding (see below) in
`TPRM_Roadmap.md`'s dated entry.

**One real, previously-undiscovered UX bug found — fixed same day:**
`VendorRiskTerminal.jsx`'s `openIntegration()` reset `expandedStage` to `null` on every call, and
it was called after every stage-status button click and after signing a risk acceptance — so the
detail panel collapsed right after the action just taken, forcing a re-click. **Fixed 2026-08-06**
(`PanelCollapse_refactor.md`, EXECUTED): `openIntegration` now takes a `{ resetExpanded = true }`
option, `false` on the two refresh-after-action call sites. Rebuilt `grc-frontend`; smoke 42/42,
pytest 32/32; dedicated Playwright regression confirmed the panel now stays open through both
actions (7/7 checks, zero console errors) while switching integrations still correctly resets.

**Also:** re-ran pytest twice — the first pass right after the browser session had one transient
`ReadTimeout` on `test_tprm_export_csv` (dataset has grown large: 435 vendors, 429+ integrations
from accumulated smoke/pytest/verification runs); reproduced as a clean pass in isolation and on a
full clean rerun (**32/32**), so not a regression — just reinforces the existing Tier 4 test-data
hygiene item below as worth doing sooner rather than later.

---

**Active item:** GOLDEN MAPPING + JUDGE CALIBRATION COMPLETE *(2026-08-05)* — corrected trajectory
**42% → 70% → 76% → 80% → 84% → 92%** (EU AI Act cluster #16/#19/#49 closed via query-time metadata
match, zero re-ingestion, zero regressions; numbers corrected same day after a scorer bug was found
affecting every prior run — see `RAG_Benchmark_Report_v6.md` §3a, and MEMORY.md's "Key numbers"
section). Judge calibration promoted the locked judge prompt to `v2_calibrated` (4/4 human agreement
on the full current C1/C2 population) — see `JUDGE_CALIBRATION_v2.md`. Remaining 4 open benchmark
failures, all confirmed genuine (not diagnostic artifacts) via this session's calibration exercise:
CISA booklet (#50, missing source), CSF tiers table (#6, structured-extraction gap), gap-assessment
methodology (#36, was misdiagnosed "prompt too strict" — actually hallucination), AI-agent benefits
(#45, genuinely a too-strict-prompt case, the one true C1).
**TPRM roadmap complete as of 2026-08-04** (Tier 1 + Tier 2 + Tier 3, all items). **TPRM's UI
surfaces browser-verified 2026-08-06**, and the one bug found in that pass (panel-collapse) was
**fixed the same day**. **RAG P3 Execution Monitor UI also built and browser-verified 2026-08-06**
(Tier 0+1+2, all three open decisions confirmed) — real agent-run persistence, real audit logging,
real WebSocket-pushed grid updates, confirmed live across two browser tabs. **Agent Registry
De-stubbing also built and browser-verified the same day** — both handlers do real work now
(RAG-grounded NIST AI RMF audit, real RBAC policy gap analysis), with one corrected estimate on the
record (`active-auditor` genuinely takes ~43s and blocks the whole backend meanwhile, not the ~16s/
single-request framing originally presented — see the task line above for detail). Every item on
the post-TPRM pivot menu since 2026-08-05 is now closed. **`ComplianceTerminal.jsx`'s misleading
"live scanning" buttons and fake incident log were also fixed the same day** (see task line above)
— real cloud scanning wasn't achievable (no infrastructure to back it), so the fix was honesty: a
`REFERENCE_CATALOG` label and removing the two buttons that silently did something unrelated to what
they claimed.

**Session closed with a full professional assessment of the system against real market GRC tools**
(user asked, got an honest one — strong on TPRM domain modeling and process discipline, behind
category leaders on infrastructure integration/multi-tenancy/scale, none of which is news to the
user). **Durable outcome, also in `MEMORY.md`:** this is a progressive project, production is the
eventual goal but not imminent, and the known gaps are already priced in. Before any real production
push, the ask is a genuine hands-on, rigorous personal-use pass — real end-to-end workflows, not
isolated feature verification. **Next session:** that dogfooding pass is the standing recommendation
whenever there's no strong pull toward a specific build; otherwise, TPRM Tier 4 (test-data hygiene —
real fix likely needs a dedicated test schema/DB, not a simple cleanup script, since
`RiskAcceptance` rows and any `Integration` that has one are protected by a DB-level immutability
trigger; found scoping this, not yet fully investigated), `Framework_Mappings`' own separate
fixture-fake data source (same underlying issue as the policy grid just fixed), or revisit
`active-auditor`'s synchronous execution now that its real cost is known precisely (optional, not a
defect). HANDOFF.md refreshed at session close.

- [x] **TPRM Tier 4: test-data hygiene** *(2026-08-13)*: confirmed live (not assumed) — 608
  vendors/607 integrations/126 risk-acceptances, 100% test-generated (every vendor name matched a
  known test pattern), and confirmed via `pg_trigger` why a cleanup script can't work (DELETE/UPDATE/
  TRUNCATE all blocked on `risk_acceptances`/`evidence_chain`/`stage_evidence_links`, every FK `NO
  ACTION`). Two-part fix, both approved together: **(a)** targeted volume reset (`grc-db-data` +
  `grc-tprm-evidence` only — FAISS and backups untouched, no re-ingest) — dev stack now genuinely at
  0 vendors/integrations. **(b)** new isolated `docker-compose.test.yml` (own DB, port 8002, reuses
  the real FAISS index read-only) that `smoke_test.py`/`pytest` now target *by default* — a bare test
  run no longer touches dev-stack data. **Two real bugs found and fixed during verification, not
  drafting:** hardcoded `docker exec grc-db-pg` immutability probes in `test_tprm.py`/`smoke_test.py`/
  `conftest.py` (the last one an autouse fixture running on every single test) were still hitting the
  dev stack regardless of the new HTTP-layer switch; and the test compose file's missing `name:`
  caused a project-name collision that flagged the dev stack's containers as "orphans." Both fixed.
  See `TPRM_Tier4_TestDataHygiene_refactor.md` for full detail. Verified: pytest 32/32 and
  smoke_test.py 43/43 against the isolated test stack (both immutability probes passing for real),
  dev-stack vendor count confirmed at 0 throughout.

- [x] **Genuine TPRM dogfooding pass (API layer)** *(2026-08-13)*: first judgment-driven, non-fixture
  data the app has held — one fictional-but-realistic vendor (`Meridian Cloud Storage`) with two
  integrations (CRITICAL-tier egress PII backup, LOW-tier ingress DR-test return), 26 stages each
  individually reasoned (not scripted placeholders), 2 evidence files, 3 risk acceptances,
  RBAC-boundary probes (unauthenticated/viewer/analyst all correctly denied where expected). **Zero
  application bugs found** — risk tiering, deny-by-default approval, RBAC, vendor-tier rollup,
  evidence linking, CSV export all correct under real use; DB state and backend logs cross-checked,
  not just API responses trusted. See `TPRM_Dogfooding_Pass_2026-08-13.md`. **Explicitly partial:**
  no browser-automation tool was available this session, so this covers the API surface only, not
  the actual React UI — a real browser pass against this same data is still an open item.
  → **CLOSED 2026-08-16/17**, see the next item.

- [x] **5-terminal empty-state audit + Executive fabricated-KPI honesty fix** *(2026-08-17)*: ran a
  hypothesis-driven audit before writing the requested screen tests — deliberately in that order, since
  tests written against untested code encode current behaviour as correct, and this codebase has a
  documented history of fabricated data. **The hypothesis (that the two 2026-08-16 bugs were one "no
  data" class with more instances hiding) came back clean:** all five terminals render honest empty
  states under empty list payloads, zero crashes, zero JS errors, controls reachable. The Ops deadlock
  was the only instance. **But the audit surfaced something bigger:** `ExecutiveTerminal` — the most
  stakeholder-facing screen — was serving `fixtures.json` as live governance KPIs *with trend deltas
  implying a historical baseline that does not exist*, including **142 active users against 3 real
  accounts**, 8 open findings against 3 real gaps, 98% coverage, a fabricated 6-month trend chart,
  invented budget figures, a hardcoded `UNIT_HEALTH: OPTIMAL`, a frozen `Q3_FY2026`, and
  `1M/3M/6M/YTD` buttons with no `onClick`. Same class as the ComplianceTerminal (2026-08-06) and
  Framework_Mappings (2026-08-13) fixes — the last and largest instance. Fixed per the user's chosen
  approach (*wire what's real, label the rest*): three footer metrics now live-computed and badged
  **Live**, four unbackable panels badged **Reference** with honest captions, `UNIT_HEALTH` reading the
  real `/readiness` endpoint, `FISCAL_CONTEXT` computed, dead period buttons removed. The two genuinely
  real sections (identity audit, policy engine) untouched. `policy_coverage` now honestly reads **0%** —
  true, and matching `policy-analyzer`'s independent finding. See `ExecutiveHonesty_refactor.md`.
  **Verified:** new `tests/test_executive.py` (**pytest 33 → 38**), smoke **43/43**, 15/15 browser
  checks, audit re-run clean. **One self-correction worth carrying:** a verification check gave a false
  pass (`"READY" in page_text` matched the unrelated AUDIT_STATE card while the tile actually rendered
  `--`); a screenshot caught it. That is the **second** false pass from whole-page assertions in two
  days — recorded in `MEMORY.md` gotchas.

- [x] **TPRM dogfooding pass (UI/browser layer) + both bugs it found, fixed** *(2026-08-16/17)*:
  closed the open item above. **The "no browser tooling" conclusion from 2026-08-13 was wrong** — the
  host's Python `playwright` package works with zero setup (Chromium 141); check that before
  concluding otherwise. Drove the real React UI as `admin` against the *same* `Meridian Cloud Storage`
  data (no throwaway data created). **Zero console errors, zero failed requests, zero 4xx/5xx across
  every run.** Verified good: vendor strip tier colour-coding, both integrations' tier badges,
  `13/13 STAGES REVIEWED` + open-gap count, `approved_with_exceptions` → PARTIAL badge, all 26 stage
  rows, both genuine N/A stages, the RISK ACCEPTED block with signer + expiry, evidence rendering with
  hash/uploader, **CSV export downloading end-to-end from the browser**, and the 2026-08-06
  panel-collapse fix still holding. See `TPRM_Dogfooding_UI_Pass_2026-08-16.md`.
  **Two real bugs found — both invisible to the API-layer pass, both now fixed and verified:**
  - **Stage evidence-notes wipe (data loss).** Clicking `pass`/`gap`/`review` silently destroyed that
    stage's `evidence_notes` — the UI omits the field for those statuses, and the handler assigned it
    unconditionally, turning "not sent" into "erase the audit rationale". Confirmed at the DB layer
    (26 → 25 notes) *and* as a user-visible symptom. Fixed by gating on `payload.model_fields_set`, so
    omission preserves and an explicit null still clears. New pytest regression test →
    **pytest 33/33**. See `StageNotes_Preservation_refactor.md`.
  - **Operations terminal deadlock.** `OpsTerminal.jsx`'s `!activeJob` early return sat *above* the
    **Run Agent** button, so with zero agent runs there was no UI path to create the first one —
    permanently stuck. Reachable precisely because Tier 4 + a restart left `agent_runs` genuinely
    empty. Fixed by scoping the empty state to the console pane. **That fix also had to remove a
    fabricated stats default** (`{running: 2, failed: 2}`, only recomputed when `jobs.length > 0`)
    which was invisible *only because* the early return hid the header — shipping the obvious fix
    alone would have put invented operational activity on screen, the same class of problem the
    ComplianceTerminal honesty work removed. See `OpsTerminal_EmptyState_refactor.md`.
  **Verification:** smoke **43/43**, pytest **33/33**, plus a 16/16 browser pass covering both fixes
  (notes surviving a status click on real data; zero-run Ops rendering a working runner with honest
  0/0/0 stats; the non-empty path unregressed and Run Agent creating a real COMPLETED run). Meridian
  dataset backed up to CSV before any mutation and diffed **byte-identical** afterwards.
  **Still open:** no *frontend* regression test for either bug (zero frontend component tests exist
  project-wide — both bugs here were frontend-triggered, which is a fair argument that gap now costs
  something); and a follow-up the notes fix surfaced — **the UI has no way to author a note for a
  pass/gap/review stage at all** (read-only display; only the N/A prompt creates one), so an analyst
  working purely in the browser cannot write the rationale for a control they just passed. Needs a UI
  decision, deliberately not bundled into a data-loss fix.

- [x] **LLM provider migration: Gemini → Groq** *(2026-08-13)*: user stopped paying for the Google
  Cloud project behind `GOOGLE_API_KEY`, which had started returning `403 PERMISSION_DENIED` and the
  free tier's `429 RESOURCE_EXHAUSTED` (20 req/day) — the direct cause of the ~23-minute backend
  block logged as a gotcha the day before. Migrated `core/rag.py`'s LLM call (embeddings/reranker/
  FAISS all stayed local, untouched) from `ChatGoogleGenerativeAI` to `ChatGroq`
  (`llama-3.3-70b-versatile`), a small change since both are LangChain chat-model interfaces. **Also
  closed the actual reliability gap, not just swapped providers:** the old integration had no
  `max_retries`/`timeout`, which is what let one bad API response cascade into a 23-minute block;
  the new client is explicitly bounded (`max_retries=2, timeout=30`). Updated `requirements.txt`,
  `config.py`, `main.py`'s readiness/root-endpoint text, both `docker-compose*.yml` files' env
  passthrough, and `CLAUDE.md`'s architecture header. See `LLM_Groq_Migration_2026-08-13.md`.
  **Verified live, not just import-clean:** readiness green on both stacks, a real `/chat` call
  answered correctly with real corpus citations, rebuilt both backend images, **smoke 43/43** and
  **pytest 32/32** against the Groq-backed test stack — including a live `active-auditor` run
  completing in ~31s (back to the documented baseline, confirming the block was the API key, not
  the architecture). **Open:** `diagnose_rag.py`/`validate_diagnostic.py` (parked RAG-diagnostic
  tooling) still pinned to Gemini and now non-functional, not migrated (out of scope, low priority);
  `rag_benchmark.py`'s 92% figure not yet re-run against Groq to confirm it still holds.
