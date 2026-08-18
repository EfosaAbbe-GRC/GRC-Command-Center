# GRC Command Center — CLAUDE.md

## System Reference for AI-Assisted Development

**Version:** 1.5.0 (TPRM Interview Simulator)
**Last Updated:** 2026-08-18 — RAG accuracy is **90.0%** under Groq/`openai/gpt-oss-120b` (the
86% below is a stale, pre-correction, pre-provider-migration figure; see `MEMORY.md` for the
current number and full trajectory, never quote this line).

> Cold-start order: read `MEMORY.md` (durable facts) → `SESSION.md` (last session) → `task.md` (live board).

---

## System Overview

GRC.OS is an agentic Governance, Risk, and Compliance platform that orchestrates AI-powered document analysis, autonomous compliance checking, and real-time executive visibility. Built for high-density security auditing, the system enforces zero-trust access control, immutability of audit trails via PL/pgSQL database triggers, and a "Deny-by-Default" governance model for all agentic AI actions.

---

## Architecture

```text
GRC Command Center v1.2.0
├── Backend: FastAPI (Python 3.11, port 8001)
│   ├── LLM: Groq (`openai/gpt-oss-120b`) — migrated from Gemini 2.5 Flash 2026-08-13; Groq retired
│   │        `llama-3.3-70b-versatile` days later, re-pinned 2026-08-17, see MEMORY.md
│   ├── Embeddings: all-MiniLM-L6-v2 (local HuggingFace)
│   ├── Re-Ranker: cross-encoder/ms-marco-MiniLM-L-6-v2 (k=20 → top 10)
│   ├── Vector Store: FAISS (with SHA-256 integrity hashing)
│   ├── Database: PostgreSQL 16 (Hardened with SECURITY DEFINERTriggers)
│   ├── Auth: JWT (IAM-10 with Independent Account Seeding)
│   ├── Agent Registry: Zero-Trust Python Registry (Subprocess eliminated)
│   ├── Database Engine: SQLAlchemy 2.0 Async (Asyncpg + NullPool)
│   └── Policy Engine: Capability-based RBAC with Sync Bridge fallback
│
├── Frontend: React 19 + Vite 7 + Tailwind CSS v4
│   ├── UI: "Enterprise Command Authority" Design System
│   ├── Logic: AuthContext + useAuth Hook (Modularized)
│   └── Comms: Synchronous Event Bus (WebSocket @ /api/v1/stream)
│
└── Orchestration: Docker Compose (v2)
    ├── grc-backend: Python 3.11-slim
    ├── grc-frontend: Nginx Alpine (Multi-stage build)
    ├── grc-db-pg: PostgreSQL 16
    └── grc-db-backup: Automated Daily Backups
```

---

## File Structure

```text
GRC_Command_Center/
├── backend/
│   ├── main.py                    # Root FastAPI application & endpoint registry
│   ├── core/
│   │   ├── agent.py               # Zero-Trust Registry Pattern (InternalAgentRunner)
│   │   ├── auth.py                # JWT, RBAC, and policy enforcement
│   │   ├── config.py              # Pydantic Settings & PostgreSQL connection strings
│   │   ├── database.py            # AuditLogger & Sync Bridge Pattern (NullPool enforced)
│   │   ├── models.py              # SQLAlchemy 2.0 Declarative Models
│   │   ├── logger.py              # Structured JSON logging with Correlation IDs
│   │   ├── rag.py                 # RAGEngine: Vector Indexing & LLM Orchestration
│   │   ├── tprm.py                # TPRM: 13-stage vendor egress/ingress assessment, risk acceptances
│   │   ├── interview_sim.py       # TPRM Interview Simulator: mock-interview sessions grounded in real TPRM stage content, live-graded
│   │   └── ws.py                  # Sync Event Bus: WebSocket stream management
│   ├── data/
│   │   ├── fixtures.json          # Initial GRC seeding data (policies, KPIs, framework mappings)
│   │   └── seed_tprm_stages.py    # Idempotent seeding of 26 reference TPRM stages (run from lifespan)
│   ├── data_service.py            # Loads fixtures.json; serves policies/dashboard/framework mappings
│   ├── requirements.txt           # Backend dependencies
│   └── tests/
│       └── smoke_test.py          # Primary functional endpoint verification
│
├── src/
│   ├── App.jsx                    # Root component with Auth and Reset gates
│   ├── contexts/
│   │   ├── useAuth.js             # AuthContext creation and useAuth Hook
│   │   └── AuthContext.jsx        # AuthProvider component logic
│   ├── hooks/
│   │   ├── useWebSocket.js        # Exponential backoff telemetry hook
│   │   └── useApiData.js          # REST data fetching hook
│   ├── lib/
│   │   └── api.js                 # Unified API client with automatic refresh
│   └── terminals/
│       ├── ComplianceTerminal.jsx  # Policy management (WebSocket synced)
│       ├── ExecutiveTerminal.jsx   # High-level KPIs
│       ├── OpsTerminal.jsx        # Job oversight (WebSocket synced)
│       ├── KnowledgeTerminal.jsx  # Vector store and document metadata
│       ├── VendorRiskTerminal.jsx # TPRM: vendor risk register, stage review, sign-off (minRole analyst)
│       └── InterviewSimTerminal.jsx # TPRM Interview Simulator: mock-interview practice, live grading (minRole analyst)
│
├── Dockerfile.backend             # Production backend build
├── Dockerfile.frontend            # Production frontend build (Nginx)
├── docker-compose-v2.yml          # Production-hardened orchestration (Postgres)
└── GOVERNANCE.md                  # Project Root: Immutable Prime Directive
```

---

## Build, Run & Test Commands

- **Production Boot (Hardened):** `docker compose -f docker-compose-v2.yml up --build`
- **Backend Dev:** `cd backend && python main.py` (Port 8001)
- **Frontend Dev:** `npm run dev` (Port 3006)
- **Deployment Smoke Test:** `python backend/tests/smoke_test.py`
- **Lints:** `flake8 backend/`, `npm run lint`

---

## Key technical Decisions

### 1. High-Concurrency Infrastructure

- **PostgreSQL 16 Migration**: Replaced SQLite with a production-grade PostgreSQL stack to support multi-agent concurrency and row-level locking.
- **NullPool Fix**: Implemented `sqlalchemy.pool.NullPool` to resolve the "Different Loop" runtime error caused by asyncpg connections binding to discarded import-time loops.
- **Sync Bridge Pattern**: Established `_run_async` helpers in `database.py` to allow legacy synchronous middleware and seeding tasks to interface with the new Async engine.

### 2. Zero-Trust Security & Immutability

- **Subprocess Eradication**: Eliminated all `subprocess.run()` calls. Agents are now hardcoded Python functions in the `AGENT_REGISTRY`.
- **Hardened Triggers**: Implemented native PL/pgSQL `SECURITY DEFINER` triggers, all bound to a single shared function (`fn_prevent_immutability_violation`), that block all `UPDATE` and `DELETE` operations on `audit_logs`, `evidence_chain`, and `risk_acceptances` at the database layer.
- **Independent Seeding**: Refactored the `lifespan` startup to check for `admin`, `analyst`, and `viewer` accounts independently, ensuring 100% RBAC test coverage on every boot.

### 3. Real-Time Telemetry

- **WebSocket Event Bus**: Replaced high-latency polling with a low-latency event stream at `/api/v1/stream`.
- **Telemetry Isolation**: Decoupled WebSocket state from `useAuth` to ensure stable UI updates without triggering AuthContext cascading re-renders.

---

## Audit History

- **Interview Simulator Sprint (Aug 18)**: TPRM Interview Simulator Tier 1 shipped
  (`interview_sim.py` + `InterviewSimTerminal.jsx`) — mock-interview practice grounded in real
  seeded TPRM stage content and real vendor GAP data, live Groq grading with an honest
  `grading_failed` state (never a fabricated score). Smoke 44/44, pytest 50/50, browser-verified.
- **Retrieval Sprint (Jul 18)**: RAG accuracy 44% → **86%** (k=10, 1000-char chunks, corpus repaired/expanded to 158 official docs, cross-encoder re-ranker). Fixed latent `.integrity` signer bug (true root cause of FAISS-INT-001). Corpus pinned against OneDrive dehydration; 7 truncated PDFs quarantined and substituted with official NIST/SEC/OWASP sources.
- **Hardening Sprint (Apr 11)**: PostgreSQL 16 migration complete. Baseline smoke test reached **27/27 GREEN**. Implemented NullPool stability and independent user seeding.
- **Zero-Trust (Apr 10)**: Registry pattern implemented in `agent.py`. All subprocess paths neutralized. 
- **WebSocket Bus (Apr 10)**: Transitioned UI to Synchronous Event Bus telemetry. Resolved React 19 ref-lifecycle conflicts.
- **Legacy Phase**: SQLite foundation and initial RAG orchestration (v1.0.0).
