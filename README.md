# GRC Command Center

An agentic Governance, Risk, and Compliance (GRC) platform with AI-powered document analysis, automated compliance checking, third-party risk management, and real-time executive dashboards.

## Highlights

- **RAG accuracy 44% → 90%** on a fixed 50-query benchmark, driven by
  measured changes (chunking, retrieval depth, cross-encoder re-ranking,
  golden mapping) — each kept only after an independent before/after
  evidence check, including catching and reverting a scorer bug that once
  misreported a fake 96%. Full trajectory and writeups in
  [`docs/reports/`](docs/reports/), starting with
  [`RAG_Benchmark_Report_v7.md`](docs/reports/RAG_Benchmark_Report_v7.md).
- **Immutable audit trail** — PL/pgSQL `SECURITY DEFINER` triggers block
  `UPDATE`/`DELETE` on audit logs, evidence, and TPRM risk acceptances at
  the database layer, not just the application layer.
- **Third-Party Risk Management** — 13-stage vendor assessment workflow
  with automatic risk tiering and admin-signed, append-only risk
  acceptances.
- **27/27 smoke tests green**, including a live probe that attempts to
  tamper with an audit row via `docker exec` and asserts the trigger
  rejects it.

## Architecture

- **Backend:** FastAPI (Python) with Gemini 2.5 Flash LLM, FAISS vector store.
- **Database:** PostgreSQL 16 for high-concurrency audit logging and user registry.
- **Real-Time:** Synchronous Event Bus (WebSockets) for zero-latency terminal updates.
- **Frontend:** React 19 + Vite + Tailwind CSS v4.
- **AI Engine:** RAG pipeline using LangChain, local `all-MiniLM-L6-v2` embeddings, and a
  `cross-encoder/ms-marco-MiniLM-L-6-v2` re-ranker (wide k=20 recall filtered to top 10).

## Production Setup (Docker)

The production stack is fully containerized and hardened. This is the recommended way to run GRC.OS.

### Prerequisites

- Docker and Docker Compose
- Google AI API key ([get one here](https://makersuite.google.com/app/apikey))

### Quick Start

1. **Configure Environment:**
   Create `backend/.env` with your `GOOGLE_API_KEY`, plus `ADMIN_PASSWORD` / `ANALYST_PASSWORD` /
   `VIEWER_PASSWORD` and `JWT_SECRET_KEY`. The checked-in defaults for those four are non-functional
   placeholders (`CHANGE-ME-...`), so the seeded accounts won't log in until you set real values.

2. **Launch the Hardened Stack:**

   ```bash
   docker compose -f docker-compose-v2.yml up --build
   ```

3. **Access the Terminal:**
   Open: <http://localhost:3006>

## Development Setup

### Backend (Standalone)

```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend (Standalone)

```bash
npm install
npm run dev
```

## Security & Governance

This platform operates under the **GRC.OS Prime Directive**:

- **Zero-Trust**: No arbitrary code execution via subprocess. Everything is registered in the `InternalAgentRunner`.
- **Immutability**: Audit trails are protected by PL/pgSQL triggers that prevent all `UPDATE` or `DELETE` operations on core GRC tables.
- **Synchronous Telemetry**: No polling allowed. All data updates are pushed via the custom `useWebSocket` hook.

For more details, see [GOVERNANCE.md](GOVERNANCE.md).

## Documentation

Working history, versioned benchmark reports, and engineering write-ups live under `docs/`,
organized so the root stays focused on the project itself:

- [`docs/reports/`](docs/reports/) — versioned RAG benchmark reports, gap analyses, and raw results
- [`docs/architecture/`](docs/architecture/) — infra, migration, and registry design write-ups
- [`docs/refactors/`](docs/refactors/) — individual fix/refactor logs, including the honesty-audit fixes
- [`docs/roadmaps/`](docs/roadmaps/) — forward-looking feature roadmaps
- [`docs/session-logs/`](docs/session-logs/) — session handoffs and working state (`MEMORY.md`, `SESSION.md`, `task.md`)

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | System health check (with dependency probes) |
| WS | `/api/v1/stream` | Real-time telemetry event bus |
| POST | `/api/v1/auth/login` | JWT authentication |
| POST | `/api/v1/chat` | RAG-powered Q&A |
| POST | `/api/v1/run-agent` | Execute zero-trust compliance agent |
| GET | `/api/v1/compliance/policies` | Policy status grid |
| GET | `/api/v1/knowledge/documents` | Indexed document metadata |
| GET/POST | `/api/v1/tprm/vendors`, `/tprm/integrations` | Vendor & integration risk register |
| POST | `/api/v1/tprm/integrations/{id}/stages/{stage_id}` | Submit a control-stage response |
| POST | `/api/v1/tprm/integrations/{id}/risk-acceptances` | Admin-signed, append-only risk acceptance |
| POST | `/api/v1/tprm/integrations/{id}/approve` | Sign off (blocked while stages are unreviewed) |

## Testing

```bash
cd backend
python backend/tests/smoke_test.py
```
