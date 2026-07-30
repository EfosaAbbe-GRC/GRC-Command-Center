# GRC Command Center — CLAUDE.md

## System Reference for AI-Assisted Development

**Version:** 1.4.0 (Retrieval-Tuned & Re-Ranked)
**Last Updated:** 2026-07-18 (Retrieval Sprint Complete — RAG accuracy 86%)

> Cold-start order: read `MEMORY.md` (durable facts) → `SESSION.md` (last session) → `task.md` (live board).

---

## System Overview

GRC.OS is an agentic Governance, Risk, and Compliance platform that orchestrates AI-powered document analysis, autonomous compliance checking, and real-time executive visibility. Built for high-density security auditing, the system enforces zero-trust access control, immutability of audit trails via PL/pgSQL database triggers, and a "Deny-by-Default" governance model for all agentic AI actions.

---

## Architecture

```text
GRC Command Center v1.2.0
├── Backend: FastAPI (Python 3.11, port 8001)
│   ├── LLM: Google Gemini 2.5 Flash
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
│   │   └── ws.py                  # Sync Event Bus: WebSocket stream management
│   ├── data/
│   │   └── data_fixtures.py       # Initial GRC seeding logic
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
│       └── KnowledgeTerminal.jsx  # Vector store and document metadata
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
- **Hardened Triggers**: Implemented native PL/pgSQL `SECURITY DEFINER` triggers (`fn_prevent_audit_modification`, `fn_prevent_evidence_modification`) that block all `UPDATE` and `DELETE` operations at the database layer.
- **Independent Seeding**: Refactored the `lifespan` startup to check for `admin`, `analyst`, and `viewer` accounts independently, ensuring 100% RBAC test coverage on every boot.

### 3. Real-Time Telemetry

- **WebSocket Event Bus**: Replaced high-latency polling with a low-latency event stream at `/api/v1/stream`.
- **Telemetry Isolation**: Decoupled WebSocket state from `useAuth` to ensure stable UI updates without triggering AuthContext cascading re-renders.

---

## Audit History

- **Retrieval Sprint (Jul 18)**: RAG accuracy 44% → **86%** (k=10, 1000-char chunks, corpus repaired/expanded to 158 official docs, cross-encoder re-ranker). Fixed latent `.integrity` signer bug (true root cause of FAISS-INT-001). Corpus pinned against OneDrive dehydration; 7 truncated PDFs quarantined and substituted with official NIST/SEC/OWASP sources.
- **Hardening Sprint (Apr 11)**: PostgreSQL 16 migration complete. Baseline smoke test reached **27/27 GREEN**. Implemented NullPool stability and independent user seeding.
- **Zero-Trust (Apr 10)**: Registry pattern implemented in `agent.py`. All subprocess paths neutralized. 
- **WebSocket Bus (Apr 10)**: Transitioned UI to Synchronous Event Bus telemetry. Resolved React 19 ref-lifecycle conflicts.
- **Legacy Phase**: SQLite foundation and initial RAG orchestration (v1.0.0).
