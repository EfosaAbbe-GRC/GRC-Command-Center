# Diagnosis — the two "regressions" from the 2026-09-21 curation

**Date:** 2026-09-26 · **Cost:** zero Groq tokens (corpus inspection + `audit_logs`, no LLM calls)
· **Supersedes:** the "curation is break-even" reading recorded earlier the same day.

## Conclusion first

**The curation was correct and should stand. Do not restore `Notes from Study +.pdf`.**

The four outcome flips are not two gains and two losses. They are **two genuine gains, one
pre-existing weakness that the curation exposed rather than caused, and one improvement that the
benchmark's binary scorer recorded as a loss.**

| # | Flip | What it actually is |
|---|---|---|
| #6 | INSUFFICIENT_DATA → ANSWERED | **genuine gain** |
| #12 | INSUFFICIENT_DATA → ANSWERED | **genuine gain** |
| #26 | ANSWERED → INSUFFICIENT_DATA | **retrieval weakness revealed, not caused** |
| #36 | ANSWERED → INSUFFICIENT_DATA | **the system got more honest; the scorer punished it** |

## Method

`audit_logs` persists the retrieved `sources` for every `/chat`, and it goes back to 2026-08-14 —
covering the v7 run (2026-08-17) and both v8 attempts. That makes a direct before/after comparison
of *what was retrieved* possible without re-running anything. Corpus claims were then checked
against the PDFs themselves.

## One document explains three of the four flips

`Notes from Study +.pdf` — personal study notes, moved to `GRC_Analyst/Excluded Docs/` by the
2026-08-18 curation and dropped from the index on 2026-09-21.

| # | v7 sources (2026-08-17) | 2026-09-26 sources |
|---|---|---|
| #6 | `Nist Guide to RA`, **`Notes from Study +`**, `NISTIR 8286`, `NIST SP 800-39`, **`B0DF8Z5HTT`**, `NIST SP 800-30r1` — **no CSF 2.0** | **`NIST CSF 2.0 (CSWP 29)`**, `Nist Guide to RA`, `NISTIR 8286`, … |
| #12 | `iso 27001mandstory documentation`, …, **`Notes from Study +`**, `Implementation Guide ISO 27001` | same minus the notes; and minus `Implementation Guide ISO_IEC 27001_2022`, the byte-identical duplicate that had been consuming a second slot |
| #26 | `Cloud_Security_for_Dummies`, **`Notes from Study +`**, `GDPR Checklist`, `GDPR-Third-Party-Compliance-Checklist` | `GDPR-Third-Party-Compliance-Checklist`, `Grc Checklist`, `AI Iso 42001`, `GDPR Checklist` |
| #36 | `complete guide to ISO 27001 risk assessment`, **`Notes from Study +`**, `Next Steps as GRC Program Lead` | 6 sources incl. `Gap Assessment Checklist Template` — still refuses |

**#6 and #12 are unambiguous wins.** On #6 the actual standard — `NIST CSF 2.0 (CSWP 29).pdf` —
was **not retrieved at all** in v7; two secondary documents were occupying its slots. Remove them
and the standard surfaces. On #12 a byte-identical duplicate was burning a second retrieval slot.
This is exactly the mechanism the corpus authority review was proposed to exploit, now
demonstrated rather than predicted.

## #26 — the authoritative source is present and works; it just doesn't surface here

**`GDPR_Regulation_Text.pdf` is in the live corpus, is indexed, and is retrieved successfully.**

| Check | Result |
|---|---|
| In live corpus (not excluded) | yes — 88 pages, ~200k extractable chars |
| Ever retrieved? | **6 times** |
| For which queries? | #24 (automated decision-making), #25 (DPIA), #28 (cross-border transfers) — **all ANSWERED** |
| Retrieved for #26? | **no** |

So this is not a missing document and not a broken document. The official text containing Article 5
is sitting in the index, answering its neighbours, and losing to checklists on
*"List the seven core principles of GDPR."*

**That is the enumeration failure already documented for Golden Mapping** (`HANDOFF` item 1):
1000-char chunks shatter multi-page enumerations, so "list the whole framework" queries retrieve
fragments and the model correctly refuses. The study notes had been supplying a tidy summary list
that the retriever preferred — **masking the weakness, not fixing it.**

**Action: #26 joins the Golden Mapping target list (#4, #18, #26).** It is not a curation problem
and restoring anything would only re-hide it.

## #36 — the corpus has no crosswalk, and v7 answered anyway

| Check | Result |
|---|---|
| `NIST CSF 2.0 (CSWP 29).pdf` mentions of `27001` | **0** |
| Mentions of `crosswalk` | **0** |
| Any live PDF pairing CSF with 27001 (filename scan) | **none** |

There is no NIST CSF ↔ ISO 27001 mapping anywhere in the corpus. So what did v7 answer with?

> *"Below is a step-by-step approach that follows the gap-analysis methodology described in the
> provided context. The process uses the same activities that are applied when a gap analysis is
> performed against **any** industry standard (e.g., ISO 27001, NIST CSF)…"*
>
> Table header: `Phase | Action (as described in the context) | **How it applies to NIST CSF ↔ ISO 27001**`

**v7 retrieved a generic gap-analysis methodology and extrapolated the framework-specific column
itself.** The mapping was model inference, presented in a citation-bearing answer whose sources did
not support the specific claim.

Today: `INSUFFICIENT_DATA: The provided compliance frameworks do not contain this information.`
**That is the correct answer given this corpus.**

A GRC platform presenting generic process as a framework-specific mapping is the precise failure
class this project has spent months removing (`ComplianceTerminal`'s fake policy grid,
`ExecutiveTerminal`'s invented KPIs, the `grading_failed` state in `interview_sim.py`). #36 is the
RAG pipeline finally behaving the way the rest of the system was fixed to behave.

**Two actions:**

1. **Corpus acquisition, not a query-time fix:** obtain an authoritative CSF ↔ ISO 27001 mapping.
   NIST publishes Informative References for exactly this. Until then, refusing is right.
2. **The scorer gap is no longer theoretical.** `HANDOFF` already lists *"the binary scorer cannot
   distinguish a correct refusal from a failure and currently rewards the less honest model"* as a
   known issue marked **not urgent**. It has now distorted a real decision — it is the sole reason
   the curation read as break-even instead of positive. **Promote it.**

## What this corrects

Recorded earlier on 2026-09-26, on the 36-query sample, and **now superseded**:

- ~~"The curation is break-even — two gains, two regressions."~~ → **Net positive.** Two gains, one
  weakness exposed, one honesty improvement mis-scored.
- ~~"Golden Mapping may now be a two-query problem (#4, #18) rather than four."~~ → **Still about
  four**, but a different four: **#4, #18, #26**, with #36 reclassified as corpus acquisition.
- ~~"Removing documents is not free — weigh that before the corpus authority review."~~ → **The
  review is better supported than before.** #6 is direct evidence that secondary material
  out-competes primary standards for retrieval slots. The caveat that survives is narrower:
  *removing a document can expose an enumeration weakness it was masking* — which is a reason to
  benchmark after each removal, not a reason to remove less.

## Confidence

- **#6, #12 gains:** high — retrieved-source lists before and after are unambiguous.
- **#26 as retrieval, not corpus:** high — the official source is present, indexed, and demonstrably
  retrieved for three sibling queries.
- **#36 corpus gap:** high — zero `27001` occurrences in the CSF paper, no crosswalk by filename.
- **#36 v7 answer as extrapolation:** high — the answer text says so in its own words.
- **Not yet verified:** whether a clean v8 reproduces all four flips. Everything here rests on a
  39/50 partial and the v7 archive. Re-confirm after the next full run.
