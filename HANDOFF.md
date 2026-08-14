# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 13, 2026
**Version:** 1.4.0 — RAG tuned + Golden Mapping; TPRM, Execution Monitor UI, Agent Registry
De-stubbing, ComplianceTerminal + Framework_Mappings honesty fixes, TPRM Tier 4 test-data hygiene, a
first (API-layer-only) TPRM dogfooding pass, and an LLM provider migration (Gemini → Groq) all built
and verified.
**Baselines:** smoke test **43/43** · pytest **32/32**, both against the isolated test stack
(`docker-compose.test.yml`, port 8002) and now running on **Groq** (`llama-3.3-70b-versatile`), not
Gemini — see `LLM_Groq_Migration_2026-08-13.md`. **92% RAG accuracy figure is stale as of the
provider switch** — it was measured against Gemini 2.5 Flash; `rag_benchmark.py` has not yet been
re-run against Groq, so don't quote 92% as current without re-running it first. See `MEMORY.md`'s
"Boot & verify" for the full ritual.

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center (v1.4.0). Read `MEMORY.md` (durable facts),
`SESSION.md` (last session's log — 2026-08-06 entry has the full narrative if you need detail
beyond this summary), and `task.md` (live board) in the project root, then verify the stack per the
boot ritual in MEMORY.md before proposing anything.

**Current state, in brief:** RAG accuracy 92% (corrected trajectory, Golden Mapping + a
scorer-bug fix, both 2026-08-05 — don't quote old 44/72/78/82/86% figures). TPRM's entire roadmap
is complete and browser-verified. RAG P3 Execution Monitor UI is built and browser-verified (real
`AgentRun` persistence, real audit logging, real cross-tab WebSocket push). Agent Registry
De-stubbing is done — `active-auditor` runs real NIST AI RMF questions through the actual RAG
pipeline, `policy-analyzer` inspects the real RBAC `Policy` table (found a genuine gap: all 13
seeded policies missing `source_doc`) — with one corrected number on the record: `active-auditor`
costs **~43s of full-backend blocking per run** (FAISS/reranker work is synchronous, no executor
offload — blocks every user, not just the caller), not the ~16s first estimated.
`ComplianceTerminal.jsx`'s misleading "rescan"/"remediate" buttons and fabricated incident log are
fixed too — replaced with honest `REFERENCE_CATALOG` labeling, since there's no real infrastructure
in this project to back genuine live scanning. Full detail on all four in `SESSION.md`'s 2026-08-06
entry and the four executed `_refactor.md` diffs (`PanelCollapse`, `ExecutionMonitor`,
`AgentRegistry_DeStubbing`, `ComplianceGrid_Honesty`). Everything is pushed (`70d1f43`).

**Important context for how to approach this project going forward, not just what's built:** this
is explicitly a *progressive* project — the goal is eventually shipping to production, but not
soon, and there's no deadline pressure. The user is already fully aware of the gaps a real GRC-tool
comparison surfaces (no live infrastructure integration, no multi-tenancy/SSO, single-process
architecture, no frontend tests) — don't re-raise those as new findings. **Before any real
production push, the user wants a genuine hands-on, rigorous personal-use pass** — actual end-to-end
workflows across terminals as a real user would run them, not the feature-by-feature
build-then-verify-in-isolation pattern used for the four items above. This is a distinct, more
valuable kind of testing, and the right thing to reach for once the backlog runs dry of clear next
builds, or whenever production-readiness comes up as a live question — not a checklist to start
silently closing.

**Open backlog** (none urgent, pick based on what's actually wanted next):

1. **Re-run `rag_benchmark.py` against Groq** — the 92% figure was measured against Gemini 2.5
   Flash; the 2026-08-13 provider migration (see `LLM_Groq_Migration_2026-08-13.md`) hasn't been
   benchmarked yet. No code change needed (the benchmark hits `/chat` over HTTP, not the SDK
   directly) — just needs running and the result recorded, since a 70B Llama model via Groq could
   land meaningfully above or below Gemini 2.5 Flash's number.
2. **Finish the dogfooding pass in a real browser** — highest-value next session if there's no
   strong pull toward a specific feature. 2026-08-13 covered the backend API surface only (no
   browser-automation tool was available that session): one realistic fictional vendor, `Meridian
   Cloud Storage`, two integrations (CRITICAL egress / LOW ingress), 26 individually-reasoned
   stages, evidence uploads, risk-acceptance sign-offs, RBAC-boundary probes — 61/61 checks passed,
   zero application bugs found (see `TPRM_Dogfooding_Pass_2026-08-13.md`). What's still unverified:
   whether `VendorRiskTerminal.jsx` actually *renders* this data cleanly — the 2026-08-06 pass found
   a real UI bug (panel-collapse) and a real auth-header bug (export button) that the API-only pass
   would have missed entirely. Pick up against this same vendor, don't create new throwaway data.
3. **Revisit `active-auditor`'s synchronous execution** (optional, not a defect) — now that its real
   cost (~43s full-backend blocking) is known precisely, worth a fresh look if it starts to feel
   worse in practice than it did on paper.
4. **Minor, low-urgency parked items:** `EU AI ACT 2024_Doc.pdf`'s text-extraction defect (isolated
   to one corpus file, Golden Mapping already hand-patches the affected queries);
   `diagnose_rag.py`'s first-pass discriminator sharing a bug already fixed in `rag_benchmark.py`;
   `diagnose_rag.py` has no resume-from-checkpoint logic; zero frontend component tests exist
   project-wide. See `JUDGE_CALIBRATION_v2.md` §1/§4 for detail on the RAG-diagnostic items.

**Closed since the August 6 version of this doc:** TPRM Tier 4 test-data hygiene (isolated
`docker-compose.test.yml` test stack + one-time dev-stack reset — see
`TPRM_Tier4_TestDataHygiene_refactor.md`); `Framework_Mappings`' honesty caption (see
`FrameworkMappings_Honesty_refactor.md`); the first, API-layer-only dogfooding pass (item 2 above,
minus the browser-verification piece); the Gemini → Groq LLM migration (item 1 above, minus the
benchmark re-run).

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 43/43
cd backend; python -m pytest -v; cd ..                   # expect 32/32 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # 46/50 (92%) was the Gemini-era number --
                                                           # NOT YET RE-RUN against Groq, see backlog #1
cat RAG_Benchmark_Report_v6.md
```

**Note:** `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an
IPv6/IPv4 loopback mismatch in the healthcheck itself, not a real outage; see MEMORY.md gotchas).
The app serves fine on `http://localhost:3006`.
