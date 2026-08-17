# Corpus Refresh Runbook

**Purpose:** a repeatable procedure for changing the RAG corpus without breaking the ability to
measure or undo it. Written 2026-08-17 off the back of `Corpus_Audit_2026-08-17.md`, but intended for
every future corpus change, not just this one.

**The two rules everything else serves:**

1. **Nothing enters the corpus unvalidated.** A file that looks fine can yield zero text (90 MB of
   the corpus did). Filename and file size prove nothing.
2. **One ingest, one measurement, one changelog.** All file moves happen first; the index is rebuilt
   once; the benchmark runs once; the report lists exactly what changed so a bad result can be
   bisected instead of guessed at.

---

## Phase 0 — Baseline (assistant, ~2 min)

Record the exact starting state so any step can be undone and any result explained.

- Snapshot the top-level file list, count and total size to the session scratchpad.
- Confirm `rag_benchmark_results.json` matches its `v7` archive (the v7 run is the comparison point).

**Gate:** baseline recorded. Nothing has moved yet.

## Phase 1 — Remove the provably useless (user, ~10 min)

**Zero risk — these cannot be retrieved today, so removing them cannot lose an answer.**

Move to `GRC_Analyst/Excluded Docs/`:

*The five zero-text files (90 MB, invisible to RAG):*

- `Why_ISO_27001_27001_Clause_7_is_important_.pdf` (44.5 MB)
- `ISO_27001_2022_the_significance_of_Clause_4.pdf` (38.9 MB)
- `Owasp Gen AI security project.pdf` (3.6 MB)
- `AI_Data_and_Scale_Transforming_Cyber_Defense_1760960000.pdf` (2.0 MB)
- `best-practices-to-elevate-your-policy-and-procedure-management.pdf` (0.5 MB)

*Cert-prep textbooks (not GRC source material):*

- `B0DF8Z5HTT.pdf` (45.4 MB — CompTIA Security+ Study Guide)
- `Security plus study guide.pdf` (35.3 MB)
- `Cloud_Security_for_Dummies_Oracle_3rdEdition.pdf` (4.2 MB)

**Do NOT remove the thin infographics yet** — several are currently the only source for a benchmark
query. They come out in Phase 4, *after* their replacement is in.

**Gate:** ~176 MB moved; nothing that could answer a question has been lost.

## Phase 2 — Acquire authoritative sources into staging (user, ~30-45 min)

Create `GRC_Analyst/_incoming/` and download into **there**, not the corpus root. Staging exists so
nothing unvalidated ever enters the index.

| Document | Issuer | Serves |
| --- | --- | --- |
| NIST CSF 2.0 (CSWP 29) | NIST | **#6** — replaces a third-party "audit checklist" |
| NIST SP 800-61 (Incident Handling) | NIST | **#51** — query names it; currently absent |
| GDPR — Regulation (EU) 2016/679 full text | EUR-Lex | **#32–36** (five queries) |
| SOC 2 / Trust Services Criteria | AICPA | **#41** — absent; core TPRM |
| Three Lines Model (2020) | IIA | **#47** — current IIA file is about staffing |
| ISACA AI audit resource *(optional)* | ISACA | #50 |

**Standing rule (`MEMORY.md`): official sources only** — from the issuing body's own site, not a
blog mirror or a summary. Prefer the full publication over an executive summary or preview.

**Gate:** files sitting in `_incoming/`, nothing yet in the corpus.

## Phase 3 — Validate at the gate (assistant, ~2 min)

Every staged file is checked before admission:

- opens as a valid PDF and ends with `%%EOF` (existing rule — catches truncated downloads)
- plausible page count and size
- **yields > 300 characters per page** (new rule, added after the 2026-08-17 audit — this is the
  check that would have caught 90 MB of image-only files)
- first page confirms it is the *actual* publication, not commentary about it (the
  `Nist Csf 2.0.pdf` trap: titled like a framework, contents were a checklist)

Anything that fails goes back with the reason. Only passing files move to the corpus root.

**Gate:** every new file is real, readable and authoritative.

## Phase 4 — Retire the superseded material (user, ~5 min)

**Only now**, and only where a validated replacement is in place. Pair them explicitly:

| Retire | Because |
| --- | --- |
| `Nist Csf 2.0.pdf` (checklist) | superseded by NIST CSWP 29 |
| `iso 27001mandstory documentation.pdf` (202 c/p vendor infographic) | only if an authoritative ISO 27001 documentation source was added |
| `iia-whitepaper_resourcing-...pdf` | superseded by the Three Lines Model |

Everything else thin stays for now — losing the only source for a query is worse than a weak source.

**Gate:** no query has been left without any source.

## Phase 5 — One ingest (assistant, ~11 min)

Rebuild the index once, covering every change from Phases 1–4 together.

- `POST /api/v1/ingest`, monitored via `docker logs grc-backend` (**not** HTTP — ingestion blocks the
  API for its duration; JWTs expire during the wait).
- Afterwards confirm the FAISS integrity manifest verifies and `/readiness` is green.

**Gate:** index rebuilt, readiness green.

## Phase 6 — Measure (assistant, ~15 min)

- Archive `rag_benchmark_results.json` → `.v8_corpus_refresh.json` **before** running.
- Warm the re-ranker with one throwaway query (cold start is 30-120s and would distort latency).
- Run nothing else against the backend while the benchmark executes.
- Publish `RAG_Benchmark_Report_v8.md` with the trajectory table **and an explicit changelog** —
  every file added and removed — so a bad number can be bisected.

**Expectation, stated up front so a modest result is not misread:** this should stop weak sources
crowding out authoritative ones in the top-10 reranked slots. It will **not** fix the enumeration
failures (#4, #6, #12, #18) — those are a chunking problem and need Golden Mapping. #6 is the one
plausible exception, since its failure was traced to having a checklist instead of the framework.

## Phase 7 — Close out (assistant, ~5 min)

Per the standing session ritual: update `SESSION.md`, `task.md`, `MEMORY.md`, `HANDOFF.md`, then
**commit and push**. Update the workspace-level chain only if a durable decision came out of it.

---

## If v8 comes back worse

The whole design above exists to make this cheap:

1. `Excluded Docs/` still holds every removed file — nothing was deleted.
2. The v8 report's changelog lists each change individually.
3. Move back the most suspicious removals, re-ingest, re-measure.

The most likely culprit in a regression is Phase 4 (retiring a thin file whose replacement covers the
topic differently), **not** Phase 1 — Phase 1 removed files that were provably contributing nothing.
