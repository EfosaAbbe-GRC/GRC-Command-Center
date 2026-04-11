# GRC Command Center — Session Handoff Document

## Continue from this point in a new chat
**Date:** April 10, 2026
**Version:** 1.2.0 (High-Concurrency Production Hardened)
**Last commit:** eefe6bb (main) — "Admin: Codebase polish - Fixed React ref-lifecycle and Markdown lints"

---

## What to tell Claude in the new chat

Paste this as your first message:

---

I'm continuing work on the GRC Command Center. Here's where we are:

**The system is a production-hardened GRC (Governance, Risk, Compliance) platform** with a FastAPI backend, React 19 frontend, and a PostgreSQL 16 database. It features a Zero-Trust Agent Registry (no shell execution), real-time WebSocket synchronization (Synchronous Event Bus), and automated GRC backups.

**Current state:** Fully hardened and production-ready (v1.2.0). Docker Compose v2 is active and healthy.

**Architecture Refresher:**
- **Backend:** FastAPI (port 8001), PostgreSQL 16 (port 5432), FAISS Vector Store.
- **Frontend:** React 19 + Vite + Tailwind CSS v4 (port 3006).
- **Security:** Zero-Trust Agent Registry (agent.py), IAM-10 JWT Auth with refresh rotation.
- **Monitoring:** Automated backups (grc-db-backup), health checks with 60s start period.
- **Comms:** WebSockets (`/api/v1/stream`) for zero-latency terminal updates.

**What was completed this session (Hardening Sprint):**

1. ✅ **PostgreSQL Migration**: Migrated from SQLite to full PostgreSQL 16 for high-concurrency compliance logging.
2. ✅ **Zero-Trust Registry**: Removed all `subprocess.run()` risky paths. Agents are now hardcoded Python callables in `core/agent.py`.
3. ✅ **WebSocket Event Bus**: Replaced 5s polling with real-time WebSocket streams (`useWebSocket.js` hook).
4. ✅ **Immutability Triggers**: Ported SQLite triggers to native PL/pgSQL `fn_prevent_audit_modification`.
5. ✅ **Automated Backups**: Integrated daily `pg_dump` service with 30-day retention.
6. ✅ **Healthcheck Optimization**: Fixed startup race conditions by adding a `start_period` to the backend.
7. ✅ **React Ref Fix**: Resolved "Cannot update ref during render" in `useWebSocket.js`.
8. ✅ **Codebase Polish**: Neutralized all Markdown linting warnings across the repository.

**Seeded Users (Current):**

- admin / (env-defined) (role: admin)
- analyst / (env-defined) (role: analyst)
- viewer / (env-defined) (role: viewer)

**Credentials derived from `backend/data_fixtures.py` during seeding.**

**What comes next:**

- **Stability Monitoring**: Monitor the WebSocket connection stability under high multi-user stress.
- **Recovery Testing**: Perform a manual data recovery from a generated backup file in the `grc-db-backups` volume.
- **E2E Scaling**: Test the UI's reaction to high-frequency agent event bursts via the WebSocket bus.

---

## Infrastructure Status commands

```powershell
# Check hardened containers
docker compose -f docker-compose-v2.yml ps

# Monitor logs for WebSocket events
docker compose -f docker-compose-v2.yml logs -f backend

# Verify Backend health (Postgres + Agent Registry probes)
Invoke-RestMethod "http://localhost:8001/api/v1/health" | ConvertTo-Json
```
