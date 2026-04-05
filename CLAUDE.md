# GRC Command Center — CLAUDE.md
## System Reference for AI-Assisted Development
**Version:** 1.1.0 (Containerized Production Candidate)
**Last Updated:** 2026-04-04

---

## System Overview
GRC.OS is an agentic Governance, Risk, and Compliance platform that orchestrates AI-powered document analysis, autonomous compliance checking, and real-time executive visibility. Built for high-density security auditing, the system enforces zero-trust access control, immutability of audit trails via database triggers, and a "Deny-by-Default" governance model for all agentic AI actions.

---

## Architecture

```
GRC Command Center v1.1.0
├── Backend: FastAPI (Python 3.11, port 8001)
│   ├── LLM: Google Gemini 2.0 Flash
│   ├── Embeddings: text-embedding-004
│   ├── Vector Store: FAISS (with SHA-256 integrity hashing)
│   ├── Database: SQLite (grc_audit.db) - Mounted Volume
│   ├── Auth: JWT (Access + Refresh Rotation)
│   └── Policy Engine: Capability-based RBAC
│
├── Frontend: React 19 + Vite 7 + Tailwind CSS v4
│   ├── UI: "Enterprise Command Authority" Design System
│   ├── Logic: AuthContext + useAuth Hook (Modularized)
│   └── Comms: api.js (Retry + Refresh + Polling)
│
└── Orchestration: Docker Compose
    ├── grc-backend: Python 3.11-slim
    └── grc-frontend: Nginx Alpine (Multi-stage build)
```

---

## File Structure

```
GRC_Command_Center/
├── backend/
│   ├── main.py                    # Root FastAPI application & endpoint registry
│   ├── core/
│   │   ├── auth.py                # JWT, RBAC middleware, and policy enforcement
│   │   ├── config.py              # Pydantic Settings and environment configuration
│   │   ├── database.py            # AuditLogger: SQLite schema and immutable triggers
│   │   ├── logger.py              # Structured JSON logging with Correlation IDs
│   │   └── rag.py                 # RAGEngine: FAISS indexing and Gemini orchestration
│   ├── data/
│   │   └── grc_audit.db           # SQLite Audit Database (Mounted Volume)
│   ├── requirements.txt           # Backend dependencies (Pinned: 2.12.0)
│   └── tests/
│       └── smoke_test.py          # Primary functional endpoint verification
│
├── src/
│   ├── App.jsx                    # Root component with Auth and Reset gates
│   ├── contexts/
│   │   ├── useAuth.js             # AuthContext creation and useAuth Hook (Fast Refresh Safe)
│   │   └── AuthContext.jsx        # AuthProvider component logic
│   ├── lib/
│   │   └── api.js                 # Unified API client with automatic refresh
│   └── terminals/
│       ├── ComplianceTerminal.jsx  # Policy management and framework mapping
│       ├── ExecutiveTerminal.jsx   # High-level KPIs and security audit history
│       ├── OpsTerminal.jsx        # Job oversight and agent execution
│       └── KnowledgeTerminal.jsx  # Vector store and document metadata
│
├── Dockerfile.backend             # Production backend build
├── Dockerfile.frontend            # Production frontend build (Nginx)
├── docker-compose.yml             # Service orchestration and volumes
└── .gitignore                     # Production-hardened exclusion manifest
```

---

## Build, Run & Test Commands
- **Containerized Run (Recommended):** `docker compose up --build`
- **Backend Dev:** `cd backend && python main.py` (Port 8001)
- **Frontend Dev:** `npm run dev` (Port 3006)
- **Smoke Test (Auth-Aware):** `python backend/tests/smoke_test.py`
- **Backend Linting:** `flake8 backend/`
- **Frontend Linting:** `npm run lint`

---

## Authentication & Authorization

### Flow
1. Login via `POST /api/v1/auth/login` (Returns Access + Refresh pair).
2. Frontend imports `useAuth` from `src/contexts/useAuth.js`.
3. `AuthProvider` manages state in `src/contexts/AuthContext.jsx`.
4. `AuthMiddleware` verifies JWT and attaches user metadata to `request.state`.

### Role Hierarchy
`admin` (3) > `analyst` (2) > `viewer` (1)

---

## Key Technical Decisions
- **Fast Refresh Compliance**: Split `AuthContext` into a hook file (`useAuth.js`) and a provider file (`AuthContext.jsx`) to avoid Vite build/HMR errors.
- **Path Abstraction**: `Settings` class in `config.py` now uses environment-aware paths for `DOCUMENTS_PATH` and `DATABASE_PATH`.
- **Permission Enforcement**: `Dockerfile.backend` explicitly enforces `chmod 755` on persistent data volumes to prevent SQLite permission locks.

---

## Audit History
- **Phase A**: Auth-aware smoke test (27/27), lifespan-ordered seeding, immutability triggers verified.
- **Phase B**: Production-ready containerization completed. Fixed dependency conflicts, pathing resolution, and frontend HMR logic.
- **Hardening**: Health check verified at `status: healthy` across all subsystems.
