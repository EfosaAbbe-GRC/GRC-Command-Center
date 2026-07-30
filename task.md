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
- [ ] **Judge Calibration**: results file is flagged `v1_uncalibrated` — build a small human-labeled set (~15 queries) and validate the locked judge prompt against it; promote results to `v2_calibrated`
- [ ] **Golden Mapping Metadata**: ingest structured Framework → Control ID mapping to bypass fuzzy vector retrieval for known compliance identifiers (HANDOFF priority #2)

## P3 — Platform Debt & Features

- [ ] **Execution Monitor UI**: real-time agent job monitor on the WebSocket telemetry bus (HANDOFF priority #3)
- [ ] **Agent Registry De-stubbing**: `active-auditor` / `policy-analyzer` handlers in `agent.py` return canned responses — wire them to real RAG/audit logic
- [ ] **Documentation Drift**: CLAUDE.md claims `text-embedding-004` embeddings + Gemini 2.0 Flash; code actually uses `all-MiniLM-L6-v2` + `gemini-2.5-flash` — sync CLAUDE.md to reality

---

**Active item:** RETRIEVAL SPRINT COMPLETE *(2026-07-18)* — trajectory **44% → 72% → 78% → 82% → 86%** (+42 pts, zero errors across 250 queries). Corpus expanded to 158 docs; cross-encoder re-ranker A/B'd (+4 net, +0.94s latency) and **kept**. See `RAG_Benchmark_Report_v5.md`.
Remaining 7 failures need *different* levers: EU AI Act clause structure → Golden Mapping (P2); CSF tiers table → structured extraction; CISA booklet → missing source; 2 jitter queries → judge calibration (P2).
**Next session:** P2 Judge Calibration + Golden Mapping, or pivot to P3 Execution Monitor UI. Refresh HANDOFF.md at session close.
