# GRC Command Center — CLAUDE.md

## System Reference for AI-Assisted Development

**Version:** 1.2.0 (High-Concurrency Production Hardened)
**Last Updated:** 2026-04-10

---

## System Overview

GRC.OS is an agentic Governance, Risk, and Compliance platform that orchestrates AI-powered document analysis, autonomous compliance checking, and real-time executive visibility. Built for high-density security auditing, the system enforces zero-trust access control, immutability of audit trails via PL/pgSQL database triggers, and a "Deny-by-Default" governance model for all agentic AI actions.

---

## Architecture

```text
GRC Command Center v1.2.0
├── Backend: FastAPI (Python 3.11, port 8001)
│   ├── LLM: Google Gemini 2.0 Flash
│   ├── Embeddings: text-embedding-004
│   ├── Vector Store: FAISS (with SHA-256 integrity hashing)
│   ├── Database: PostgreSQL 16 (High-Concurrency)
│   ├── Auth: JWT (Access + Refresh Rotation)
│   ├── Agent Registry: Zero-Trust Python Handlers (Eradicated subprocess)
│   └── Policy Engine: Capability-based RBAC
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
│   │   ├── agent.py               # InternalAgentRunner: Zero-Trust Registry Pattern
│   │   ├── auth.py                # JWT, RBAC middleware, and policy enforcement
│   │   ├── config.py              # Pydantic Settings and environment configuration
│   │   ├── database.py            # AuditLogger: SQLAlchemy 2.0 / PostgreSQL integration
│   │   ├── logger.py              # Structured JSON logging with Correlation IDs
│   │   ├── rag.py                 # RAGEngine: FAISS indexing and Gemini orchestration
│   │   └── ws.py                  # ConnectionManager: WebSocket synchronization
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

### 1. Infrastructure Scaling
- **PostgreSQL 16**: Migrated from SQLite to support multi-agent concurrency and row-level locking.
- **Automated Backups**: Integrated `postgres-backup-local` for daily GRC record persistence.

### 2. Zero-Trust Security
- **Subprocess Eradication**: Replaced `subprocess.run()` with a hardcoded `AGENT_REGISTRY` in `core/agent.py`.
- **PL/pgSQL Triggers**: Implemented `fn_prevent_audit_modification` to enforce audit trail immutability at the engine level.

### 3. Real-Time Telemetry
- **WebSocket Event Bus**: Replaced 5s polling with a synchronous stream at `/api/v1/stream`.
- **Decoupled Lifecycle**: WebSocket state is isolated from `useAuth` to prevent Vite Fast Refresh collisions.

---

## Audit History

- **Hardening (Current Session)**: SQLite to Postgres migration complete. WebSocket event bus established. Zero-Trust Agent Registry implemented.
- **Phase B**: Production-ready containerization completed. Fixed dependency conflicts and pathing resolution.
- **Phase A**: Auth-aware smoke test (27/27), lifespan-ordered seeding, immutability triggers verified.
