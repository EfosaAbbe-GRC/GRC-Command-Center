# GRC Command Center — Session Handoff (v1.5.0)

**Date:** 2026-10-04. **Rewritten clean** after v9 ran and PII redaction reached dev. **If this file
starts accumulating update blocks again, rewrite it — do not append another.**

This is the **briefing**: current state and what to do first. The ledger with full history is
`task.md`; the narrative is `SESSION.md`.

---

## Where things stand

**Version 1.5.0.** TPRM complete (all tiers). RAG P3 Execution Monitor, Agent Registry de-stubbing,
the Interview Simulator Tier 1, and all honesty fixes are built and browser-verified. LLM is Groq
`openai/gpt-oss-120b`. **PII redaction is live on dev** (2026-10-04).

**Baselines:**

| | Status | Last verified |
| --- | --- | --- |
| `smoke_test.py` (test stack, `:8002`) | **44/44** | 2026-09-29 |
| `smoke_test.py` (dev, `:8001`) | **43/44** — the one failure is a Groq **per-minute** 429 (see §0) | 2026-10-04 |
| `test_pii.py` (in the dev container) | **21/21** | 2026-10-04 |
| `pytest` (from `backend/`) | **66 passed, 1 skipped** (test_pii skips on host) | 2026-10-04 |
| RAG, citable | **42% → 92%** (v8, 46/50) | 2026-09-27 |
| RAG, latest run | v9: legacy 94% (47/50), graded 98% — **not citable as accuracy** | 2026-10-04 |
| Index | curated: **148 files / 17,123 chunks** | re-ingested 2026-09-21 |

**How to quote the RAG figure:** *"42% → 92%"*. v9's 94/98% include #12 with an **invented item**
and leave 40 of 50 answers ungraded — see `docs/reports/RAG_Benchmark_Report_v9.md`. v7's 90% was
never valid. Never quote 90%.

**⚠ Do not read the repo's `faiss_index/` folder to learn the index state.** It is an April 11
decoy. The live index is in the `grc-faiss` Docker volume.

---

## ▶ 0. FIRST: Efosa's decisions from v9, then the next corpus change

v9 (2026-10-04) measured Golden Mapping: **#4 and #26 fixed and correct; #12 complete plus one
invented item** ("information security guideline, 5.2 e" — not in ISO/IEC 27001:2022, checked
against the official text); **#18 still fails** — list correct, 7 of 10 explanations refused, and
the query says "Explain". All other 46 grades unchanged. Full reading in the v9 report.

Independent of each other — take them to Efosa:

- **a. #18 — approved; DRAFTED, awaiting EXECUTE:** `Golden_Mapping_OWASP_Descriptions_refactor.md`
  (official descriptions from the corpus PDF, wording checked page by page). Measured by **v10**,
  which pushes the corpus removal (0b) to v11 — one variable per run.
- **b. #12's invented item — Efosa chose the grader route; DRAFTED, awaiting EXECUTE:**
  `Grader_Unsupported_Items_refactor.md` (new `UNSUPPORTED_ITEM` grade; prototype over v1–v9: one
  true catch, one borderline paraphrase, no false alarms; v9 graded 49 → 48). Prompt tightening
  stays a possible later variable.
- **c. ~~`Grader_Hyphen_refactor.md`~~ — EXECUTED 2026-10-04.** pytest 66 + 1 skipped; no grade
  changed in any archive.
- **d. Smoke test vs Groq TPM — approved; DRAFTED, awaiting EXECUTE:** `Smoke_TPM_Pacing_refactor.md`. the `active-auditor` run (makes several RAG calls) is followed
  ~12 s later by the chat check; together they exceed 8,000 tokens/minute, so "Chat generation"
  fails with a 429 (seen twice on dev, 2026-10-04). Not caused by PII: a standalone chat with
  made-up PII returned 200 and correct redactions. Fix candidate: pause ~60 s before the chat check,
  or retry it once after a 429. Needs a draft.
- Carried: fix the v6 entries' exact-wording triggers (misfire on #17/#21); re-extract the damaged
  GDPR PDF.

**Then, sequential — one variable per benchmark day:** v10 = the OWASP descriptions (a); v11 = 0b
below (remove the three personal files, re-ingest, benchmark). Weekend benchmarks only
while Mufasa trades on market days; pre-flight per "Running a benchmark".

---

## The rest of the queue — independent of each other, except where noted

**0b. Remove three personal (non-GRC) files from the corpus — APPROVED 2026-09-29, now unblocked
(v9 done).** File names are recorded in the owner's **private** workspace `GRC resources/task.md`
(not here: they are personal). Move them from `GRC_Analyst/` to `GRC_Analyst/Excluded Docs/`
(archive, don't delete), re-ingest (~36.5 min, blocks the backend), then benchmark it as its own
variable. Treatment I3 in the owner's ISO 42001 impact assessment. Archives already redacted
(`docs/reports/REDACTIONS.md`).

**0a. PII redaction — DONE, live on dev 2026-10-04.** Rebuilt `backend frontend` (~10 min: pip
cache had been evicted; spaCy `lg` downloaded fine). Verified on dev: `test_pii` 21/21; live chat
with a made-up name/email/phone → `redactions: {PHONE_NUMBER:1, EMAIL_ADDRESS:1, PERSON:1}`;
`audit_logs.query` stored `[PERSON] ([EMAIL_ADDRESS], [PHONE_NUMBER])`, **0** rows with the
originals. Smoke 43/44 (see §0 d). Execution record: `docs/refactors/PII_Redaction_refactor.md`.
Groq **Zero Data Retention** enabled 2026-09-29 (org-wide).

**1. ~~Golden Mapping for the enumeration queries — #4, #12, #18, #26.~~ DONE — executed
2026-09-27, measured by v9 2026-10-04 (3 of 4; follow-ups are §0 a/b).** Root cause it addressed:
1000-char chunking shatters multi-page enumerations. **Do not re-diagnose #18 as a retrieval bug**
— disproved, `RAG_Benchmark_Report_v7.md` §Correction.

**2. Acquire an authoritative NIST CSF ↔ ISO 27001 crosswalk** (NIST Informative References) for
query #36. Corpus gap, not a code fix. Until then, refusing is correct.

**3. Decide A/B/C on audit-write failure.** `except Exception` still swallows unknown audit
failures. Options in `AuditLog_NulByte_refactor.md`; **B recommended** (return
`audit_logged: false`). Response-schema change — needs its own draft.

**4. Minimum-content/quality filter before re-ranking.** ~30% of #18's context budget went to a
mojibake sponsors page and two sub-150-char stubs. Length threshold + non-ASCII-ratio guard.

**5. Corpus authority review — user-led, human judgement.** Supported by the 2026-09-26 diagnosis
(#6: secondary docs displaced the actual standard). Caveat: a removal can expose an enumeration
weakness it was masking (#26), so benchmark after each removal. Re-run the name heuristic first
(its 33-of-158 count predates the refresh). Re-ingest is ~36.5 min.

**6. Frontend component test harness** (Vitest + RTL). Zero frontend component tests exist.
Touches `package.json`; needs its own draft.

**7. Interview Simulator Tier 2** — only on a specific pull toward it.

**Lower priority:** migrate `diagnose_rag.py` / `validate_diagnostic.py` off the dead Gemini key —
the calibrated judge is the only way to grade the 43 unchecked answers, so this rises if §0's
rule-based check proves too coarse. `ChatGroq(max_retries=2)` can fire three calls per throttled
query.

**Standing recommendation, not a queued item:** this is a *progressive* project. The known gaps
versus real GRC tools (no live infrastructure integration, no multi-tenancy/SSO, single-process, no
frontend tests) are priced in — don't re-raise them as new findings.

---

## Running a benchmark (when one is next needed)

The procedure that worked on 2026-09-27, first try:

1. **Groq budget is organization-wide: 200,000 tokens/day; one run costs 77–100% of it.** Confirm
   nothing else Groq-backed will run. **Confirmed 2026-09-28: `mufasa_backend` is in the SAME Groq
   organization** — a different key (SHA-256 fingerprint), but one ~90-token probe per key showed a
   shared counter (`x-ratelimit-remaining-requests` 999 → 998, reset timer 1m26s → 2m52s). So
   **every benchmark needs Mufasa's AI analysis paused**, which is Efosa's call. Mufasa reports its own
   daily Groq spend at `GET localhost:8000/api/admin/costs` inside `mufasa_backend`; subtract it from
   200k for a rough "left today" (the only estimate available, as Groq has no TPD header). No other
   container has a Groq variable (re-checked 2026-09-28, 18 containers).
2. **Pre-flight:** `x-ratelimit-remaining-requests` near 1,000 (a one-word probe from inside
   `grc-backend` costs ~80 tokens).
3. **Launch detached:**

   ```powershell
   $env:PYTHONUTF8 = "1"
   Start-Process -FilePath python `
     -ArgumentList "-u", "backend/tests/rag_benchmark.py" `
     -WorkingDirectory "C:\Users\efosb\OneDrive\Desktop\GRC Inspector\GRC_Command_Center" `
     -RedirectStandardOutput "bench_run.log" -RedirectStandardError "bench_run.err" -NoNewWindow
   ```

   ~21 minutes at 22 s pacing. Results save after every query; the JWT refreshes every 10 min.
4. **Nothing else Groq-backed, and nothing CPU-heavy, for the duration** — the re-ranker runs on
   the host CPU.
5. **Archive** `rag_benchmark_results.json` → `docs/reports/rag_benchmark_results.vN_<change>.json`
   and **spot-check every flipped query's answer text** before writing the report. That is what
   caught #12 and #4 on v8; the summary numbers alone would not have.

---

## Quick status commands

```powershell
docker compose -f docker-compose-v2.yml ps
docker compose -f docker-compose.test.yml ps
$env:PYTHONUTF8=1; python backend/tests/smoke_test.py   # expect 44/44 (hits :8002)
cd backend; python -m pytest -q; cd ..                   # expect 65/65 -- MUST run from backend/
python scripts/rescore_benchmarks.py                     # re-grade all archives, zero tokens
Invoke-RestMethod http://localhost:8001/api/v1/readiness # dev stack health, read-only, safe anytime
```

**Notes:**

- Backend source is **not** bind-mounted. Any change to `backend/` needs
  `docker compose -f docker-compose-v2.yml up -d --build backend` (~20 s warm, ~15 min if the pip
  layer cache has been evicted). The test stack needs the same via `docker-compose.test.yml`.
- `grc-frontend` shows healthcheck "unhealthy" continuously — harmless, an IPv6/IPv4 loopback
  mismatch in the check itself. The app serves fine on `http://localhost:3006`.
- `smoke_test.py` / `pytest` target `:8002` by default. For the dev stack set
  `GRC_TEST_BASE=http://localhost:8001` first.
- `smoke_test.py` calls `/chat` three times (~9k Groq tokens). Don't run it on a benchmark day.
- This repo is the one deliberate exception to the workspace's "local-only" rule: public remote
  `EfosaAbbe-GRC/GRC-Command-Center`, commits go straight to `main`.
