# GRC Command Center — CLAUDE.md
## System Reference for AI-Assisted Development
**Version:** 1.0.0 (Production Candidate)
**Last Updated:** 2026-04-04
**Commit:** b3427b6 (main)

---

## System Overview
GRC.OS is an agentic Governance, Risk, and Compliance platform that orchestrates AI-powered document analysis, autonomous compliance checking, and real-time executive visibility. Built for high-density security auditing, the system enforces zero-trust access control, immutability of audit trails via database triggers, and a "Deny-by-Default" governance model for all agentic AI actions.

---

## Architecture

```
GRC Command Center v1.0.0
├── Backend: FastAPI (Python 3.10+, port 8001)
│   ├── LLM: Google Gemini 2.0 Flash
│   ├── Embeddings: text-embedding-004
│   ├── Vector Store: FAISS (with SHA-256 integrity hashing)
│   ├── Database: SQLite (grc_audit.db)
│   ├── Auth: JWT (Access + Refresh Rotation)
│   └── Policy Engine: Capability-based RBAC
│
├── Frontend: React 19 + Vite 7 + Tailwind CSS v4
│   ├── UI: "Enterprise Command Authority" Design System
│   ├── Logic: AuthContext + useApiData Hook
│   └── Comms: api.js (Retry + Refresh + Polling)
│
└── Config: Pydantic BaseSettings + .env
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
│   │   ├── rag.py                 # RAGEngine: FAISS indexing and Gemini orchestration
│   │   └── agent.py               # AgentRunner: Isolated compliance agent execution
│   ├── agents/
│   │   └── compliance_checker.py  # Reference compliance auditing agent
│   ├── schemas.py                 # Unified Pydantic request/response models
│   ├── data_service.py            # Fixture data and knowledge document discovery
│   ├── notebook_service.py        # Analyst notebook file-system scanning
│   ├── data/
│   │   ├── fixtures.json          # Seed data for policies and dashboard metrics
│   │   └── grc_audit.db           # SQLite Audit Database (GITIGNORED)
│   ├── requirements.txt           # Backend dependencies
│   ├── .env                       # Environment secrets (GITIGNORED)
│   └── tests/
│       ├── smoke_test.py          # Primary functional endpoint verification
│       ├── security_audit.py      # Agent security and isolation stress test
│       ├── rag_accuracy.py        # RAG retrieval and citation accuracy audit
│       ├── test_auth.py           # Authentication lifecycle tests
│       ├── test_iam_05.py         # Password lifecycle and rotation tests
│       ├── test_iam_07.py         # Audit event logging verification
│       ├── test_iam_08.py         # Session management and multi-logon tests
│       ├── test_iam_09.py         # Strategic Policy Engine logic tests
│       └── test_iam_10.py         # Agent governance and capability tests
│
├── src/
│   ├── App.jsx                    # Root component with Auth and Reset gates
│   ├── main.jsx                   # React 19 entry point
│   ├── index.css                  # TailWind 4 and Global Design Tokens
│   ├── lib/
│   │   └── api.js                 # Unified API client with automatic refresh
│   ├── hooks/
│   │   └── useApiData.js          # Polling data fetcher with abort management
│   ├── contexts/
│   │   └── AuthContext.jsx        # Global Identity and RBAC provider
│   ├── components/
│   │   ├── TerminalSwitcher.jsx   # Role-aware navigation and terminal routing
│   │   ├── StatusBadge.jsx        # Functional status UI component
│   │   ├── GRCChatBot.jsx         # RAG-powered co-pilot interface
│   │   └── PasswordResetModal.jsx # Forced password lifecycle UI
│   └── terminals/
│       ├── ComplianceTerminal.jsx  # Policy management and framework mapping
│       ├── ExecutiveTerminal.jsx   # High-level KPIs and security audit history
│       ├── OpsTerminal.jsx        # Job oversight and agent execution
│       └── KnowledgeTerminal.jsx  # Vector store and document metadata
│
├── .gitignore                     # Production-hardened exclusion manifest
├── package.json                   # Frontend dependencies (React 19, Tailwind 4)
└── README.md                      # System documentation and quickstart
```

---

## Database Schema (grc_audit.db)

### Tables
- **audit_logs**: `id`, `request_id`, `timestamp`, `query`, `response`, `context`, `sources`
- **evidence_chain**: `id`, `timestamp`, `filename`, `file_hash`, `file_size_bytes`, `source_path`, `ingested_by`, `status`
- **users**: `id`, `username`, `hashed_password`, `role`, `status`, `last_login`, `created_at`, `updated_at`, `password_changed_at`, `must_change_password`
- **refresh_tokens**: `jti`, `user_id`, `expires_at`, `revoked`
- **security_events**: `id`, `timestamp`, `event_type`, `user`, `ip_address`, `detail`
- **policies**: `id`, `name`, `description`, `required_role`, `is_active`, `policy_version`, `source_doc`, `created_by`, `modified_by`, `created_at`, `updated_at`

### Immutability Triggers
- `prevent_audit_update` / `prevent_audit_delete`: Enforces immutable RAG trails.
- `prevent_evidence_update` / `prevent_evidence_delete`: Protects the evidence chain-of-custody.

---

## Authentication & Authorization

### Flow
1. Login via `POST /api/v1/auth/login` (Returns Access + Refresh pair).
2. Frontend uses `sessionStorage` for tab-isolated identity persistence.
3. `AuthMiddleware` verifies JWT and attaches user metadata to `request.state`.
4. Silent refresh occurs automatically via `api.js` before access token expiry.

### Role Hierarchy
`admin` (3) > `analyst` (2) > `viewer` (1)

### Seeded Users
- Admin: `admin` / `grc-admin-2026`
- Analyst: `analyst` / `grc-analyst-2026`
- Viewer: `viewer` / `grc-viewer-2026`

### Policy Engine (10 Strategic Policies)
- `AUDIT_VIEW`, `INGEST_CONTROL`, `AGENT_EXECUTE` (Admin)
- `RAG_QUERY`, `SYSTEM_REPORTS` (Analyst+)
- `EVIDENCE_VIEW`, `EVIDENCE_EXPORT`, `NOTEBOOK_SYNC`, `USER_MANAGEMENT`, `SYSTEM_AUDIT` (Admin)

---

## API Endpoints

### Public
- `GET /`: Root system status
- `GET /api/v1/health`: Detailed health checks
- `GET /api/v1/readiness`: Deep subsystem readiness probe
- `POST /api/v1/auth/login`: Identity authentication
- `POST /api/v1/auth/refresh`: Token rotation
- `POST /api/v1/auth/logout`: Session revocation

### Protected
- `POST /api/v1/chat`: RAG query (RAG_QUERY)
- `POST /api/v1/ingest`: Trigger document ingestion (INGEST_CONTROL)
- `POST /api/v1/run-agent`: Agent execution (AGENT_EXECUTE)
- `GET /api/v1/admin/audit/security`: Security event retrieval (SYSTEM_AUDIT)
- `GET /api/v1/compliance/report`: CSV Evidence Export (EVIDENCE_EXPORT)
- `GET /api/v1/knowledge/evidence`: Evidence chain view (EVIDENCE_VIEW)
- `PUT /api/v1/admin/policies/{id}`: Policy update (SYSTEM_AUDIT)

---

## Frontend Architecture

- **Design System**: "Enterprise Command Authority" dark mode.
- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite`.
- **State**: `AuthContext` (Identity) + `useApiData` (Server State).
- **Navigation**: Role-filtered terminal switching in `TerminalSwitcher.jsx`.

---

## Environment Variables

- `GOOGLE_API_KEY`: Required for Gemini LLM and standard embeddings.
- `AUTH_ENABLED`: `bool = True`. Global JWT enforcement toggle.
- `JWT_SECRET_KEY`: `str`. Secret for JWT signature.
- `PORT`: `int = 8001`. Backend listening port.
- `DOCUMENTS_PATH`: Path to `GRC_Analyst` repository.

---

## Development Setup

### Backend
1. `cd backend && pip install -r requirements.txt`
2. Configure `.env` with `GOOGLE_API_KEY`.
3. `python main.py`

### Frontend
1. `npm install`
2. `npm run dev`

---

## Testing
- **Suite**: `python -m pytest backend/tests/`
- **Smoke**: `python backend/tests/smoke_test.py`
- **Accuracy**: `python backend/tests/rag_accuracy.py`

---

## Key Technical Decisions
- **Tab-Isolated Sessions**: `sessionStorage` avoids cross-tab session leakage.
- **SQLite RAL**: WAL mode for reliable single-file concurrent reads.
- **Immutable Triggers**: Prevents deletion of compliance evidence at the DB layer.
- **Refresh Rotation**: One-time-use refresh tokens for security.
- **Deny-By-Default**: RBAC middleware blocks unknown roles automatically.

---

## Known Limitations
- SQLite is currently single-writer (Production migration to PostgreSQL recommended).
- `smoke_test.py` lacks token-aware headers for protected routes.
- KnowledgeTerminal metadata sidebar uses some presentational placeholders.

---

## Audit History
- **Phase 1-6**: IAM and RAG core development complete.
- **v2.0 Redesign**: Enterprise Command Authority UI initialized (Tailwind v4).
- **Hardening**: Standardized on text-embedding-004 and Gemini 2.0 Flash.
- **Git Init**: Repository anchored with secrets excluded (Commit: b3427b6).
