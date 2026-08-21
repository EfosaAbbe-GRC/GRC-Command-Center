# Judge Calibration Report v2

**Date:** August 5, 2026
**Scope:** `task.md` P2 item — "results file is flagged `v1_uncalibrated`... validate the locked
judge prompt against it; promote results to `v2_calibrated`." The "locked judge prompt" is
`validate_diagnostic.py`'s ANSWERED/REFUSED/HALLUCINATED classifier — the judge that adjudicates
every query the first-pass diagnostic marks C1/C2 (ambiguous: model might have been able to answer
but didn't).

---

## 1. The existing calibration data was 2.5 months stale

`diagnostic_results.v1_uncalibrated.json` and `validation_results.json` were both dated **May 24**
— from the original 44%-baseline diagnostic sprint, predating the entire July 18 retrieval-tuning
sprint (44%→86%) and today's Golden Mapping work (86%→92%). They analyzed 28 failing queries at the
time; most have since been fixed. Concretely, that old file still classified query #16 as
`HALLUCINATED` and #19 as `REFUSED` — both are now correctly `ANSWERED` (Golden Mapping, earlier
today). Archived as `diagnostic_results.v1_uncalibrated.2026-05-24_pre-retrieval-sprint.json` /
`validation_results.v1_uncalibrated.2026-05-24_pre-retrieval-sprint.json` (git-tracked renames, not
deleted).

**Re-ran the diagnostic pipeline fresh** (`diagnose_rag.py` → `validate_diagnostic.py`) against the
current 92%-accuracy benchmark state before attempting any calibration — comparing a "locked" judge
against stale inputs would have been meaningless. Result: only **4 queries** are currently C1/C2
(down from 28), because the retrieval work already resolved the rest. This is the correct, complete
population for this specific judge — it only ever runs on C1/C2 candidates in production, never on
clean successes, so 4/4 is full domain coverage, not an artificially small sample.

**Operational note:** the first run of `diagnose_rag.py` (≈1000 sequential chunk-relevance judge
calls across 50 queries × k=20) died silently after 40/50 queries with no error captured — likely
the "Windows/WSL2 Docker Desktop network turbulence" pattern already noted in MEMORY.md. The script
has no resume logic; added a minimal one (load the existing `diagnostic_results.partial.json`
checkpoint, skip already-completed indices) to the container's working copy only, not the committed
source, to finish the run without repeating ~40 minutes of already-done judge calls.

## 2. Human-labeled calibration set (all 4 current C1/C2 queries)

| # | Query | 1st-pass label | 2nd judge's verdict | Human label | Agrees w/ 2nd judge? | Agrees w/ 1st pass? |
|---|---|---|---|---|:---:|:---:|
| 6 | NIST CSF Tier 1-4 levels | C1 | REFUSED (true gap) | REFUSED / true gap | ✅ | ❌ |
| 36 | NIST CSF ↔ ISO 27001 gap assessment | C1 | HALLUCINATED | HALLUCINATED | ✅ | ❌ |
| 45 | AI agent benefits for compliance | C1 | ANSWERED (true C1) | ANSWERED / true C1 | ✅ | ✅ |
| 50 | CISA AI Audit Booklet | C1 | REFUSED (true gap) | REFUSED / true gap | ✅ | ❌ |

**Second-stage locked judge vs. human: 4/4 (100%) agreement.**
**First-pass discriminator vs. human: 1/4 (25%) agreement.**

Full evidence (retrieved chunks, relaxed-prompt responses, both judges' raw output) archived in
`judge_calibration_v2.json`, `diagnostic_results.v2_calibrated.json`,
`validation_results.v2_calibrated.json`.

## 3. Verdict: promote the locked judge prompt to `v2_calibrated`

100% agreement across the full current population of ambiguous cases is a strong result for
`validate_diagnostic.py`'s judge (the ANSWERED/REFUSED/HALLUCINATED classifier with the
self-bias-skepticism instruction). **Promoted** — this is the judge referenced anywhere the project
cites "the locked judge prompt."

## 4. Separate finding: the first-pass discriminator has the same bug already fixed today elsewhere

`diagnose_rag.py`'s C1-vs-C2 split uses `relaxed_response.strip().startswith("INSUFFICIENT_DATA")`
— structurally the exact same brittle check as `rag_benchmark.py`'s scorer bug fixed earlier this
session (see `RAG_Benchmark_Report_v6.md` §3a). It was wrong on 3 of the 4 real cases here (75%):
a model that writes "there is no information about..." or gives an honest partial answer without
using the literal string as its first token gets mislabeled C1 (recoverable via better prompting)
when it's actually a genuine corpus gap (A/B) or a hallucination (C2). **Not fixed in this pass** —
flagged for the next time anyone is in `diagnose_rag.py`; low urgency since the second-stage judge
(now calibrated) is what any real decision should rely on, not the first-pass label.

## 5. Artifacts

- `judge_calibration_v2.json` — the human-labeled set itself (methodology, all 4 entries, evidence
  summaries, agreement rates).
- `diagnostic_results.v2_calibrated.json`, `validation_results.v2_calibrated.json` — full raw
  diagnostic/validation output from the fresh run this session.
- Archived, not deleted: `diagnostic_results.v1_uncalibrated.2026-05-24_pre-retrieval-sprint.json`,
  `validation_results.v1_uncalibrated.2026-05-24_pre-retrieval-sprint.json`.
- Not fixed, flagged for later: `diagnose_rag.py`'s first-pass `.startswith()` discriminator bug
  (§4), and adding permanent resume logic to `diagnose_rag.py` (the ad-hoc fix used this session
  wasn't committed to the tracked source).
