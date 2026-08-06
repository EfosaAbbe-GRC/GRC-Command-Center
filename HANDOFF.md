# GRC Command Center — Session Handoff (v1.4.0)

## Continue from this point in a new chat

**Date:** August 6, 2026
**Version:** 1.4.0 — RAG tuned + Golden Mapping; TPRM, Execution Monitor UI, Agent Registry
De-stubbing, and ComplianceTerminal honesty fix all built AND browser-verified.
**Baselines:** **92% RAG accuracy** (`RAG_Benchmark_Report_v6.md` §3a — this is the corrected,
actual scorer output) · smoke test **43/43** · pytest **32/32** (run from `backend/`)

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

1. **A genuine dogfooding pass** (see above) — arguably the highest-value next session if there's no
   strong pull toward a specific feature. Would mean actually using the app: log in as each role,
   run a vendor through the full TPRM lifecycle, trigger both real agents, export reports, work the
   compliance grid — end to end, looking for friction and gaps that isolated feature checks miss.
2. **TPRM Tier 4** (test-data hygiene) — real, but bigger than its "small effort" label:
   `RiskAcceptance` rows (and any `Integration` with one) are DB-immutable by design, so a naive
   cleanup script would fail or require bypassing a real security invariant. The honest fix is
   likely a dedicated test schema/DB — found this while scoping, not yet investigated further. Also
   bundled here: zero frontend component tests exist project-wide.
3. **`Framework_Mappings`' fixture-fake data source** — same underlying issue as the
   `ComplianceTerminal` policy grid just fixed, separate data, not yet scoped.
4. **Revisit `active-auditor`'s synchronous execution** (optional, not a defect) — now that its real
   cost (~43s full-backend blocking) is known precisely, worth a fresh look if it starts to feel
   worse in practice than it did on paper.
5. **Minor, low-urgency parked items:** `EU AI ACT 2024_Doc.pdf`'s text-extraction defect (isolated
   to one corpus file, Golden Mapping already hand-patches the affected queries);
   `diagnose_rag.py`'s first-pass discriminator sharing a bug already fixed in `rag_benchmark.py`;
   `diagnose_rag.py` has no resume-from-checkpoint logic. See `JUDGE_CALIBRATION_v2.md` §1/§4 for
   detail on the latter two.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 43/43
cd backend; python -m pytest -v; cd ..                   # expect 32/32 -- MUST run from backend/
$env:PYTHONUTF8=1; python backend/tests/rag_benchmark.py # expect 46/50 (92%) -- scorer fixed 2026-08-05
cat RAG_Benchmark_Report_v6.md
```

**Note:** `grc-frontend` shows Docker-healthcheck "unhealthy" continuously (harmless — an
IPv6/IPv4 loopback mismatch in the healthcheck itself, not a real outage; see MEMORY.md gotchas).
The app serves fine on `http://localhost:3006`.
