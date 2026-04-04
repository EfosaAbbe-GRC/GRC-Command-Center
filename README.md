# GRC Command Center

An agentic Governance, Risk, and Compliance (GRC) platform with AI-powered document analysis, automated compliance checking, and real-time executive dashboards.

## Architecture

- **Backend:** FastAPI (Python) with Gemini 2.0 Flash LLM, FAISS vector store, SQLite audit logging
- **Frontend:** React 19 + Vite + Tailwind CSS
- **AI Engine:** RAG pipeline using LangChain + text-embedding-004 Google Generative AI embeddings

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google AI API key ([get one here](https://makersuite.google.com/app/apikey))

### Setup

1. **Clone and install frontend dependencies:**

   ```bash
   npm install
   ```

2. **Install backend dependencies:**

   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure environment:**

   Create `backend/.env`:

   ```env
   GOOGLE_API_KEY=your-api-key-here
   AUTH_ENABLED=false
   ```

4. **Start the backend:**

   ```bash
   cd backend
   python main.py
   ```

5. **Start the frontend (separate terminal):**

   ```bash
   npm run dev
   ```

6. **Open:** <http://localhost:3006>

## Project Structure

```text
├── backend/
│   ├── main.py              # FastAPI orchestrator
│   ├── core/
│   │   ├── agent.py          # Hardened agent runner
│   │   ├── auth.py           # JWT authentication
│   │   ├── config.py         # Pydantic settings
│   │   ├── database.py       # SQLite audit logger
│   │   ├── logger.py         # Structured JSON logging
│   │   └── rag.py            # RAG engine (FAISS + Gemini)
│   ├── agents/               # Compliance check scripts
│   ├── data/                 # Fixtures and audit DB
│   ├── schemas.py            # Pydantic request/response models
│   └── tests/                # Security and RAG tests
├── src/
│   ├── App.jsx               # Root with error boundaries
│   ├── lib/api.js            # Centralized API client
│   ├── hooks/useApiData.js   # Data fetching hook
│   ├── components/           # Shared UI components
│   └── terminals/            # Dashboard views
└── package.json
```

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/health` | System health check |
| POST | `/api/v1/auth/login` | JWT authentication |
| POST | `/api/v1/chat` | RAG-powered Q&A |
| POST | `/api/v1/ingest` | Trigger document indexing |
| POST | `/api/v1/run-agent` | Execute compliance agent |
| GET | `/api/v1/compliance/policies` | Policy status grid |
| GET | `/api/v1/ops/jobs` | Operations job tracker |
| GET | `/api/v1/executive/stats` | Executive KPIs |
| GET | `/api/v1/executive/dashboard` | Dashboard stats & trends |
| GET | `/api/v1/knowledge/documents` | Indexed document metadata |
| GET | `/api/v1/notebook/structure` | Notebook file tree |

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `GOOGLE_API_KEY` | Yes | - | Google AI API key for Gemini |
| `AUTH_ENABLED` | No | `false` | Enable JWT authentication |
| `JWT_SECRET_KEY` | If auth enabled | (insecure default) | Secret for JWT signing |
| `DEBUG` | No | `false` | Enable debug mode |
| `PORT` | No | `8001` | Backend port |
| `DOCUMENTS_PATH` | No | `../GRC_Analyst` | Path to compliance documents |

## Testing

```bash
cd backend
python -m pytest tests/
python tests/security_audit.py
python tests/rag_accuracy.py
```
