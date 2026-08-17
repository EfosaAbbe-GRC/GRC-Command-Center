# Corpus Audit — text density and source authority (2026-08-17)

**Trigger:** the user began a manual corpus cleanup and asked whether the approach was right, then
said he wanted the corpus to hold *"original standardized documents."* Auditing what is actually
there strongly validates that instinct — and found a failure class nobody had looked for.

**Method:** read every top-level PDF with `pypdf`, extract text from up to 15 pages, and compute
characters-per-page. A PDF can sit in the corpus at 44 MB, look perfectly healthy in a file listing,
and contribute **zero retrievable text** — because it is scanned images or an infographic export.
That is indistinguishable from "not in the corpus at all" as far as retrieval is concerned.

**State at audit time:** 150 PDFs, 573 MB (after the user's first cleanup pass moved 18 items to
`GRC_Analyst/Excluded Docs/`).

## Finding 1 — 90 MB of the corpus is invisible to RAG

Five files yield **essentially no text**. They occupy index space, inflate the corpus, and can never
be retrieved:

| File | Size | Pages | chars/page |
| --- | --- | --- | --- |
| `Why_ISO_27001_27001_Clause_7_is_important_.pdf` | **44.5 MB** | 8 | **0** |
| `ISO_27001_2022_the_significance_of_Clause_4.pdf` | **38.9 MB** | 7 | **0** |
| `Owasp Gen AI security project.pdf` | 3.6 MB | 7 | **0** |
| `AI_Data_and_Scale_Transforming_Cyber_Defense_1760960000.pdf` | 2.0 MB | 6 | **0** |
| `best-practices-to-elevate-your-policy-and-procedure-management.pdf` | 0.5 MB | 4 | 25 |

The first two are the **largest files in the corpus** after the cert-prep textbooks. 83 MB for 15
pages is the signature of image-based carousel/infographic exports.

**The sharpest example:** benchmark query #14 is *"What is the significance of Clause 4 (Context of
the Organization) in ISO 27001?"* — and the corpus contains a file named literally
`ISO_27001_2022_the_significance_of_Clause_4.pdf`. It was almost certainly added to serve that
query. **It contributes zero text and can never be retrieved.** Same shape as the #18 finding: the
document is present, and useless.

## Finding 2 — eleven more files are text-starved, and benchmark queries point straight at them

50–300 chars/page is the range of a graphic-heavy slide deck: a headline and a caption per page.

| File | Size | chars/page | Benchmark query aimed at it |
| --- | --- | --- | --- |
| `iso 27001mandstory documentation.pdf` | 15.0 MB | 202 | **#12** "mandatory documentation for ISO 27001" |
| `6 pillars for AI-ready security.pdf` | 11.4 MB | 261 | **#62** "the 6 pillars for AI-ready security" |
| `understanding Key risk indicators(KRI).pdf` | 6.8 MB | 255 | **#49** "KRI vs KPI" |
| `annex A.5 (ISO 27001).pdf` | 1.4 MB | 240 | **#10** "Annex A.5.7 Threat Intelligence" |
| `The_TPRM_Lifecycle.pdf` | 0.8 MB | 103 | **#39** "key steps in the TPRM lifecycle" |
| `ISO27001vsMoneyHiest.pdf` | 20.6 MB | 218 | (a themed learning aid) |
| `COSO (RMF).pdf` | 0.3 MB | 223 | — |

**This is a second, independent root cause for benchmark failures**, distinct from the chunking
problem identified in `RAG_Benchmark_Report_v7.md`. #12 in particular now has two strikes against it:
its only real source is a 202-chars/page vendor infographic, *and* it asks for an enumeration.

## Finding 3 — several "framework" files are commentary, not the framework

Filenames imply authority the contents do not carry. Verified by reading page 1 of each:

| File | What it actually is |
| --- | --- |
| `Nist Csf 2.0.pdf` | **"NIST CSF 2.0 AUDIT CHECKLIST"** — a third-party checklist, *not* NIST CSWP 29 |
| `ISO-IEC-42001-2023.pdf` | 14 pages — a **preview/extract**, not the full standard |
| `AI Iso 42001 Artificial Intelligence Framework.pdf` | self-published guide ("About the Author") |
| `iso 27001mandstory documentation.pdf` | vendor marketing (`www.cyveer.com`) |
| `IT_General_Controls_.pdf` | 6-page ACCA webinar summary |
| `iia-whitepaper_resourcing-the-internal-audit-function.pdf` | IIA paper on **staffing**, not the Three Lines model (#47 targets Three Lines) |
| `GRC Enginerring Starter Pack.pdf` | community material (`github.com/ashpearce/GRC-Playground`) |
| `AI Audit Booklet.pdf` | EDPS "AI Auditing Checklist" by Dr. Gemma Galdon Clavell — real text (2601 c/p), but **not** a CISA/ISACA document, which is what **#50** asks about |

**`Nist Csf 2.0.pdf` explains benchmark #6 directly.** #6 asks for the CSF 2.0 Tier 1–4
implementation levels; `MEMORY.md` records that the corpus "names the tiers but never defines them."
An audit *checklist* would do exactly that. The actual NIST publication defines them.

**Genuinely authoritative and confirmed good:** `EU AI ACT 2024_Doc.pdf` (144p, the real Regulation
2024/1689), `AI RMF 1.0.pdf` (48p, NIST AI 100-1), `OWASP Top 10 for LLM Applications 2025.pdf`
(45p, official), `SEC 33-8810 …SOX.pdf` (77p, the real SEC release).

## Finding 4 — the mystery file, and a missed cert-prep book

`B0DF8Z5HTT.pdf` (45.4 MB, the corpus's largest file) is **"CompTIA Security+ Study Guide, Exam
SY0-701, 9th Edition"** by Chapple & Seidl — a commercial exam-prep textbook. Same category the user
was already removing. `Security plus study guide.pdf` (35.3 MB) is a second copy of that subject that
survived the first pass. `Cloud_Security_for_Dummies_Oracle_3rdEdition.pdf` (4.2 MB) also survived
while four other "for Dummies" titles were removed.

## Recommended additions — authoritative, free, and targeted at known failures

Prefer **text-based official publications**. Every item below is free from the issuing body:

| Add | Fixes / serves | Why it's needed |
| --- | --- | --- |
| **NIST CSF 2.0 (CSWP 29)** | **#6** | corpus only has a third-party checklist about it |
| **NIST SP 800-61 (Incident Handling)** | **#51** | query names the document by number; **absent** |
| **GDPR — Regulation (EU) 2016/679 full text** (EUR-Lex) | **#32–36 (five queries)** | corpus has only two GDPR *checklists*, no regulation text |
| **AICPA SOC 2 / Trust Services Criteria** | **#41** | **absent**; core TPRM material |
| **IIA Three Lines Model (2020)** | **#47** | the IIA paper present is about staffing, not the model |
| ISACA AI audit resource | #50 | present booklet is EDPS, not CISA-oriented |

**Validation rule (existing project convention, `MEMORY.md`):** official sources only, confirm
`%%EOF` and a sane file size before installing. **Add a new check after this audit: confirm the file
actually yields text** (>300 chars/page) before trusting it — the scan script used here is the way to
do that.

## Recommended removals (on top of the user's first pass)

- **All 5 zero-text files** (90 MB) — they cannot ever be retrieved.
- `B0DF8Z5HTT.pdf` (45.4 MB), `Security plus study guide.pdf` (35.3 MB) — cert-prep textbooks.
- `Cloud_Security_for_Dummies_Oracle_3rdEdition.pdf` (4.2 MB) — missed in the first pass.
- The thin infographics are a **judgement call**: several are the only source for a benchmark query,
  so removing them without adding an authoritative replacement would make those queries worse, not
  better. Recommended order: **add the replacement first, then remove the infographic.**

## Effect on measurement

This is now a substantial corpus change layered on the user's own cleanup. Both are "improve corpus
quality" and are not competing hypotheses, so bundling them into **one v8 measurement** is
reasonable — but the changes must be listed explicitly in `RAG_Benchmark_Report_v8.md` so a bad
result can be bisected. Removing ~175 MB of unretrievable and non-authoritative material while adding
5–6 genuine standards is expected to help, but **the enumeration failures (#4, #6, #12, #18) are a
chunking problem and will not be fixed by corpus curation alone** — Golden Mapping remains their fix.
