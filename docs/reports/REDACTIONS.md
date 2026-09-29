# Redactions in archived reports

Archived benchmark and diagnostic files are kept unchanged by rule. This file records every
exception, what was changed, and why, so no archive is ever altered silently.

## 2026-09-29 — personal (non-GRC) material removed

**Why:** the corpus had at some point included the owner's personal job-search material:
interview-prep scenarios, a job description, and personal study notes containing prepared
interview answers. None of it is GRC content, and none of it belongs in a public repository.
Redacted at the owner's request.

**What changed:** only the affected **file names** (`chunk_id`) and **retrieved-text** (`text`)
values. Every score, rank, verdict and result is unchanged. Verified by loading each file before
and after and confirming that no other field differs.

| File | Change |
|---|---|
| `corpus_profile.csv` | 3 file names → `[personal file, removed from corpus]` (3 rows; the third added the same day on the owner's decision) |
| `load_bearing_documents.csv` | 1 file name → same placeholder |
| `diagnostic_results.v1_uncalibrated.2026-05-24_pre-retrieval-sprint.json` | 1 `chunk_id`, 3 `text` values; `_redaction_note` added at the top |
| `diagnostic_results.v2_calibrated.json` | 1 `chunk_id`, 3 `text` values; `_redaction_note` added at the top |

The CSV files carry no inline note (a comment line would break CSV readers); this file is their note.

**Follow-up:** the three remaining files are removed from the indexed corpus after the v9 benchmark
(see `docs/session-logs/HANDOFF.md`), so future reports can't contain them. The study-notes file
was already excluded in the 2026-08-18 curation.
