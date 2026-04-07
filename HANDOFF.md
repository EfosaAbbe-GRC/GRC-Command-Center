# GRC Command Center — Session Handoff Document
## Continue from this point in a new chat
**Date:** April 5, 2026
**Last commit:** e90b2e9 (main) — "Phase C: Switch to local HuggingFace embeddings"

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center. Here's where we are:

**The system is a GRC (Governance, Risk, Compliance) platform** with a FastAPI backend (Python), React 19 frontend, RAG pipeline using local HuggingFace embeddings (all-MiniLM-L6-v2) + Gemini 2.0 Flash LLM, JWT auth with refresh token rotation, RBAC with 10 capability-based policies, and an "Enterprise Command Authority" dark UI. It runs in Docker Compose (two containers: backend port 8001, frontend port 3006).

**The CLAUDE.md in the project root has the complete system reference.**

**Current state:** Feature-complete through Phase C. Git on main at e90b2e9. All Phase A validation done, Docker running, RAG pipeline built and indexed.

**What was completed last session (Phases A, B, C):**

1. ✅ smoke_test.py — auth-aware, 27/27 passing, immutability trigger verified real
2. ✅ Password reset flow — E2E verified (modal appears, blocks, clears correctly)
3. ✅ Policy toggle flow — verified (disable RAG_QUERY → chatbot blocked, re-enable → works)
4. ✅ Docker Compose — two containers running, volumes mounted, health checks passing
5. ✅ RAG ingestion — 18,318 splits from 148 PDFs indexed into FAISS
6. ✅ Local embeddings — switched from Google API to all-MiniLM-L6-v2 (384 dimensions)
7. ✅ PolicyModel schema fix — was causing 500 on /admin/policies
8. ✅ api.put() method added — policy toggle was silently failing without it
9. ✅ useAuth.js split — Vite Fast Refresh compliance
10. ✅ ComplianceTerminal hook violation fixed

**One item to verify first thing:**
- Test the RAG chatbot: POST /api/v1/chat with {"query": "What are the access control requirements in ISO 27001 Annex A.9?"}
- It was hitting Gemini free tier daily quota last session — should reset overnight
- If it returns a real answer with PDF sources, RAG is fully verified ✅
- If still quota error, check if a new Google API key is needed

**Architecture:**
```
Backend: FastAPI (port 8001) + Gemini 2.0 Flash (LLM only) + all-MiniLM-L6-v2 (local embeddings) + FAISS + SQLite
Frontend: React 19 + Vite 7 + Tailwind CSS v4 (port 3006)
Auth: JWT (15min access + 7-day refresh with rotation) + bcrypt + RBAC (admin/analyst/viewer)
Policy Engine: 10 capabilities, DENY_BY_DEFAULT
Database: 6 tables with immutability triggers
Design: "Enterprise Command Authority" — Outfit + JetBrains Mono
Containers: grc-backend, grc-frontend (Docker Compose)
```

**Seeded Users:**
- admin / grc-admin-2026 (role: admin)
- analyst / grc-analyst-2026 (role: analyst)
- viewer / grc-viewer-2026 (role: viewer)

**Key files:**
- CLAUDE.md — complete system reference
- backend/core/rag.py — RAG pipeline (HuggingFaceEmbeddings + ChatGoogleGenerativeAI)
- backend/core/auth.py — JWT, RBAC, policy engine
- backend/requirements.txt — pinned deps including sentence-transformers, langchain-huggingface
- docker-compose.yml — two services, volume mounts
- src/lib/api.js — includes api.put() method
- src/contexts/useAuth.js — hook split from AuthContext

**Project location:** C:\Users\efosb\OneDrive\Desktop\GRC Inspector\GRC_Command_Center

**Known limitations:**
- Gemini free tier: 1,500 requests/day for LLM generation — add billing if hitting limits regularly
- SQLite single-writer — PostgreSQL migration recommended before multi-user production
- 7 corrupt PDFs skipped during ingestion (Stream has ended unexpectedly) — malformed files
- KnowledgeTerminal metadata sidebar has some presentational placeholders
- Session ID in TerminalSwitcher is a random seed per session (cosmetic)
- FAISS index is in a Docker volume — survives restarts but lost on docker compose down -v

**What comes next:**
- Verify RAG chatbot works (quota should have reset)
- Run full pytest suite: cd backend && python -m pytest tests/ -v
- Consider adding billing to Google Cloud project for higher quotas + text-embedding-004 access
- PostgreSQL migration (when ready for production)

**Git log (recent):**
- e90b2e9 — Phase C: Switch to local HuggingFace embeddings
- ebbac2c — Fix: api.put method, PolicyModel schema alignment, governance UI wiring
- 74b1f18 — Fix: move policy seeding into lifespan(); update CLAUDE.md

---

## Docker status commands
```powershell
# Check containers
docker compose ps

# Check backend health
Invoke-RestMethod "http://localhost:8001/api/v1/health"

# Test RAG chatbot
$token = (Invoke-RestMethod -Uri "http://localhost:8001/api/v1/auth/login" -Method POST -ContentType "application/json" -Body '{"username":"admin","password":"grc-admin-2026"}').access_token
Invoke-RestMethod -Uri "http://localhost:8001/api/v1/chat" -Method POST -Headers @{Authorization="Bearer $token"; "Content-Type"="application/json"} -Body '{"query":"What are the key controls in ISO 27001 Annex A?"}' | ConvertTo-Json
```
