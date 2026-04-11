# GRC Command Center

An agentic Governance, Risk, and Compliance (GRC) platform with AI-powered document analysis, automated compliance checking, and real-time executive dashboards.

## Architecture

- **Backend:** FastAPI (Python) with Gemini 2.0 Flash LLM, FAISS vector store.
- **Database:** PostgreSQL 16 for high-concurrency audit logging and user registry.
- **Real-Time:** Synchronous Event Bus (WebSockets) for zero-latency terminal updates.
- **Frontend:** React 19 + Vite + Tailwind CSS v4.
- **AI Engine:** RAG pipeline using LangChain + text-embedding-004 Google Generative AI embeddings.

## Production Setup (Docker)

The production stack is fully containerized and hardened. This is the recommended way to run GRC.OS.

### Prerequisites

- Docker and Docker Compose
- Google AI API key ([get one here](https://makersuite.google.com/app/apikey))

### Quick Start

1. **Configure Environment:**
   Create `backend/.env` with your API key.

2. **Launch the Hardened Stack:**

   ```bash
   docker compose -f docker-compose-v2.yml up --build
   ```

3. **Access the Terminal:**
   Open: <http://localhost:3006>  
   *Default Credentials:* `admin` / `admin` (if seeded via fixtures)

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

## Testing

```bash
cd backend
python backend/tests/smoke_test.py
```
