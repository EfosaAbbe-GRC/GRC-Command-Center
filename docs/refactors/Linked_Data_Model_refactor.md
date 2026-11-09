# Linked data model: one shared record set behind every terminal (blueprint)

**Status: DRAFT, awaiting the owner's review.** Drafted 2026-11-08. This is a blueprint, not a
single change: each phase below gets its own draft and its own EXECUTE. Phase 1 is drafted in
`Risk_Register_refactor.md`.

## 1. The problem, measured

Traced from the code on 2026-11-08 (session log of that date):

| Terminal | Where its data comes from | Can a user put data in? |
| --- | --- | --- |
| Vendor Risk | PostgreSQL: `vendors`, `integrations`, `stage_responses`, `stage_evidence_links`, `risk_acceptances` | **Yes** |
| Knowledge | FAISS index (official PDFs), `audit_logs`, `evidence_chain` | Questions only |
| Ops | `agent_runs` | Runs agents |
| Interview Sim | `interview_sessions`/`turns`, reads TPRM stages and gaps | Answers only |
| Executive | 3 values from the DB (open TPRM gaps, `policies` rows with a source, user count); KPI cards and trend from `fixtures.json` | **No** |
| Compliance | `fixtures.json` (5 sample policies, their framework mappings, the CSV export) | **No** |

Six breaks follow from this: vendor gaps never become risks or owned findings; the compliance side
has no input at all; chat research can't be attached to the work it was for; evidence can prove only
one vendor stage; nothing is measured over time; and the `policies` table holds **access-control
rules**, so Executive "policy coverage" measures the app's RBAC, not the compliance programme.

**Root cause:** each terminal was built as its own feature with its own source. Only TPRM was
built on records. There is no shared spine for the others to read.

## 2. The target: one spine, many views

A terminal should be a **view** over shared records, never the owner of a private copy. One record
lives in one table; every terminal that needs it reads that table; links between records are
first-class (a foreign key or a link table, with who and when).

The spine follows the structure ISO/IEC 27001:2022 itself requires (official text, checked
2026-11-08): risk criteria and risk owners (6.1.2 a, c), likelihood, consequence and level
(6.1.2 d), treatment and the Statement of Applicability (6.1.3), the risk owner's acceptance of
residual risk (6.1.3 f), assessments at planned intervals with retained results (8.2), monitoring
(9.1), internal audit (9.2), management review (9.3) and corrective action (10.2). Commercial GRC
platforms are built on the same chain (ServiceNow IRM: authority document → citation → control
objective → control per entity → indicator → issue → exception); that is used here for structure
only, never as the authority on what a standard says.

```text
 authority_documents ─┐
                      ▼
               requirements ◄──── control_requirement_links ────► controls ◄── governance_policies
                                                                    ▲   │
 entities ◄── risks ──────────── risk_control_links ────────────────┘   ▼
 (process,     │  ▲                                                control_tests
  app, asset,  │  └──────────── issue_risk_links ───────┐               │
  vendor)      ▼                                        │               ▼
          risk_events (append-only, chained)          issues ◄── vendor stage gaps, audit findings
                                                        │
                                                        ▼
                                              corrective_actions
 evidence_chain ◄── evidence_links (any record)   exceptions = risk_acceptances (+ risk-level acceptances)
 metric_definitions ──► metric_snapshots (append-only) ──► management_reviews
```

**What each terminal reads once the spine exists:**

| Terminal | Reads |
| --- | --- |
| Vendor Risk | vendors as `entities`; a stage gap raises an `issue` and can link to a `risk`; acceptances unchanged |
| **Risk Register** (new) | `risks`, `entities`, `risk_events`; later linked controls and issues |
| Compliance | requirements → controls → governance policies; status computed from `control_tests` (replaces `fixtures.json`) |
| Executive | numbers computed from records and saved as `metric_snapshots` (replaces the sample KPI cards and trend) |
| Knowledge | can save a chat answer as a research note linked to any record; the evidence register shows what each file proves |
| Ops / agents | agents read the spine (e.g. controls with no test, risks past review) instead of fixtures |
| Interview Sim | can draw scenarios from real risks and issues, not only vendor stages |

## 3. Design rules (apply to every phase)

1. **One record, one home.** Business data never lives in `fixtures.json`. Sample data, if kept for
   demos, is labelled as sample in the UI (the existing honesty convention).
2. **Registers are editable; their history is not.** A risk, control or issue row can change. Every
   change writes an append-only, hash-chained event (who, when, before and after, reason), added to
   `PROTECTED_TABLES` so the existing triggers, chain and posture check cover it.
3. **Decisions are immutable.** Acceptances, approvals and sign-offs are append-only rows, as
   `risk_acceptances` already is.
4. **Nothing is deleted.** Records close with a reason. The app role gets no DELETE on spine tables.
5. **Segregation of duties.** Viewer reads, analyst proposes, admin approves; whoever proposes an
   acceptance can't record its approval.
6. **Server computes, client displays.** Scores, bands, statuses and metrics are computed in the
   backend; the client never sends a score.
7. **Other terminals refresh on change** through the existing WebSocket bus, using payload-free
   nudges (the TPRM pattern), never polling.
8. **Personal data.** Free text stays in the database. Anything sent to the LLM provider passes
   `pii.redact` first and fails closed (the chat rule, extended to any future AI feature).
9. **Official text is the authority** for requirement wording; practice-scenario data goes into the
   database, never into the RAG corpus.
10. **Least privilege per table**, granted in `core/migrate.py` (the only schema-changing code).

## 4. Phases (each one its own draft and EXECUTE, red tests first)

| Phase | Builds | Makes these terminals read the spine | Constraint |
| --- | --- | --- | --- |
| **1** | `entities`, `risks`, `risk_events` + Risk Register terminal | Risk Register | None (no TPRM code touched). **Drafted.** |
| **1b** | Gap → risk link; acceptance shown on the linked risk; vendors become entities | Vendor Risk ↔ Risk Register | Waits for the owner's Vendor Risk walkthrough (TPRM code freeze) |
| **2** | `issues` (shared findings), `corrective_actions`, issue ↔ risk links | Vendor Risk, Risk Register, Executive "open findings" | After 1b |
| **3** | `authority_documents`, `requirements`, `controls`, `governance_policies`, links; Statement of Applicability view | Compliance (fixtures retired), Risk Register | Requirement wording from tier-1 text only |
| **4** | `metric_definitions`, `metric_snapshots`, `management_reviews` | Executive (sample KPIs retired) | Needs 2 and 3 for meaningful metrics |
| **5** | `evidence_links` (any record), research notes from chat | Knowledge, all registers | Chat side follows rule 8 |

Each phase is accepted by entering a realistic practice scenario by hand and recording, per
screen, whether it worked as designed, worked with friction, or couldn't be done.

## 5. Decisions for the owner

1. **Approve the spine and the phase order** (recommended), or reorder (e.g. controls before issues).
2. **Naming:** the RBAC table stays `policies` (renaming a security table is risk for no user gain);
   compliance policies get `governance_policies`, and the UI labels the RBAC one "Access rules".
   Recommended.
3. **Scope boundary kept:** no asset-database sync, IT-incident feeds, SSO or multi-tenancy. These
   stay out of scope (decided 2026-08-06).
