# GRC Command Center

An agentic Governance, Risk, and Compliance (GRC) platform with AI-powered document analysis, automated compliance checking, third-party risk management, and real-time executive dashboards.

## Highlights

- **RAG accuracy 42% → 90%** on a fixed 50-query benchmark, driven by
  measured changes (chunking, retrieval depth, cross-encoder re-ranking,
  golden mapping) — each kept only after an independent before/after
  evidence check, including catching and reverting a scorer bug that once
  misreported a fake 96%. The 42% baseline is itself a corrected figure: the
  original scorer only detected refusals at the start of a response, so
  answers that refused halfway through were counted as passes. Every
  historical run was re-scored and the record corrected downward.
  *Current caveat: the corpus was re-curated on 2026-09-21 and the 90% figure
  measures the previous index — a fresh benchmark is pending.* Full trajectory
  and writeups in [`docs/reports/`](docs/reports/), starting with
  [`RAG_Benchmark_Report_v7.md`](docs/reports/RAG_Benchmark_Report_v7.md).
- **Immutable audit trail** — PL/pgSQL `SECURITY DEFINER` triggers block
  `UPDATE`/`DELETE` on audit logs, evidence, and TPRM risk acceptances at
  the database layer, not just the application layer.
- **Third-Party Risk Management** — 13-stage vendor assessment workflow
  with automatic risk tiering and admin-signed, append-only risk
  acceptances.
- **44/44 smoke tests green** (plus 50/50 unit tests), including a live probe
  that attempts to tamper with an audit row via `docker exec` and asserts the
  trigger rejects it.

## Architecture

- **Backend:** FastAPI (Python) with Groq (`openai/gpt-oss-120b`) LLM, FAISS vector store.
- **Database:** PostgreSQL 16 for high-concurrency audit logging and user registry.
- **Real-Time:** Synchronous Event Bus (WebSockets) for zero-latency terminal updates.
- **Frontend:** React 19 + Vite + Tailwind CSS v4.
- **AI Engine:** RAG pipeline using LangChain, local `all-MiniLM-L6-v2` embeddings, and a
  `cross-encoder/ms-marco-MiniLM-L-6-v2` re-ranker (wide k=20 recall filtered to top 10).

## Production Setup (Docker)

The production stack is fully containerized and hardened. This is the recommended way to run GRC.OS.

### Prerequisites

- Docker and Docker Compose
- Groq API key ([get one here](https://console.groq.com/keys)) — the free tier
  is enough to run the platform, but note its limits: 30 requests/min,
  1,000 requests/day, 8,000 tokens/min and 200,000 tokens/day, all binding at
  once and scoped to your whole Groq organization.

### Quick Start

1. **Configure Environment:**
   Create `backend/.env` with your `GROQ_API_KEY`, plus `ADMIN_PASSWORD` / `ANALYST_PASSWORD` /
   `VIEWER_PASSWORD` and `JWT_SECRET_KEY`. The checked-in defaults for those four are non-functional
   placeholders (`CHANGE-ME-...`), so the seeded accounts won't log in until you set real values.
   (`GOOGLE_API_KEY` still appears in the settings model, but it is retained only for parked
   Gemini-pinned diagnostic scripts — it is **not** used by the live RAG pipeline.)

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

Endpoint smoke tests — run from the repository root (expect **44/44**):

```bash
python backend/tests/smoke_test.py
```

Unit tests — must run from `backend/`, since the suite imports `core.*` (expect **50/50**):

```bash
cd backend
python -m pytest -q
```

Both target the isolated test stack (`docker-compose.test.yml`, port 8002) by default. To point
them at the dev stack instead, set `GRC_TEST_BASE=http://localhost:8001` first.

> `smoke_test.py` makes three live `/chat` calls, so it consumes roughly 9,000 Groq tokens per run
> — worth knowing against the free tier's 200,000/day.
