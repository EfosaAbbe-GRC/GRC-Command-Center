# GRC.OS Prime Directive & Governance Protocol

This document serves as the immutable "Constitution" for all autonomous agents operating within the GRC Command Center. It defines the technology stack, strict security boundaries, design tokens, and the required orchestration workflow.

**Any agent spun up within this repository MUST read and acknowledge this file before executing its mission.**

---

## 1. The Technology Stack

All architectural decisions and code generation must strictly adhere to the following stack:

* **Frontend:** React (Vite) with custom hooks for state management.
* **Styling:** Tailwind CSS v4.
* **Backend:** Python / FastAPI.
* **Database:** PostgreSQL 16 (via SQLAlchemy 2.0 / asyncpg).
* **Knowledge Vault:** FAISS (Vector Database) with `all-MiniLM-L6-v2` embeddings.
* **Containerization:** Docker & Docker Compose.

---

## 2. Security Non-Negotiables

Security is the primary directive. Agents must operate under a **Deny-by-Default** philosophy.

1. **Zero-Trust Execution:** The use of `subprocess.run()` or any arbitrary shell execution is strictly prohibited. All agents must be registered and executed via the internal `AGENT_REGISTRY` mapping.
2. **Audit Immutability:** The audit trail (`audit_logs`, `evidence_chain`) must remain append-only. This is enforced at the database level via PL/pgSQL triggers (`fn_prevent_audit_modification`). Do not attempt to bypass this.
3. **Strict Authentication:** All real-time telemetry and API endpoints must validate IAM-10 JWT credentials. WebSockets must handshake via the `?token=` query parameter before upgrading the connection.
4. **Vault Preservation:** Docker volumes containing the `faiss_index` must always be treated as `external: true` or explicitly preserved during infrastructure modifications.

---

## 3. UI/UX & Design Tokens

The GRC Command Center utilizes a **High-Visual-Density Dark Mode**. Agents modifying the UI must preserve these aesthetics to prevent design degradation:

* **Spacing & Layout:** Maintain dense, data-rich layouts suitable for terminal-style interfaces. Avoid excessive padding or whitespace.
* **State Decoupling:** WebSocket connections and high-frequency data streams must be logically decoupled from the `useAuth` state to prevent Vite Fast Refresh collisions and re-render cascading.
* **Polling Prohibition:** The use of `setInterval` for data fetching is banned. All live updates must utilize the synchronous Event Bus (WebSockets).
* **Visual Feedback:** Use Tailwind `animate-pulse` for active connections and strictly adhere to semantic color variables (`var(--success)`, `var(--danger)`, `var(--warning)`) for status indicators.

---

## 4. Agentic Orchestration Protocol

To prevent context contamination and ensure human-in-the-loop oversight, agents must follow this lifecycle:

### A. The "Draft-First" Pattern

No agent is permitted to write directly to production files without prior authorization.

1. **Draft:** Output proposed code changes as a Markdown Diff Artifact (e.g., `[Feature]_refactor.md`).
2. **Review:** Await explicit human/supervisor approval of the artifact.
3. **Deploy:** Apply changes to the source code only after receiving the "EXECUTE" command.

### B. Skill Encapsulation

Agent capabilities reside in `.agents/skills/[skill-name]/SKILL.md`. These files are immutable once certified. Feature enhancements require version bumping (e.g., `v2`), not retroactive editing of established rules.

### C. State Checkpointing & Handoffs

When transitioning between specialized agents (e.g., from Backend Infra to Frontend UI), the departing agent must generate a `HANDOFF.md` artifact detailing schema changes, new endpoints, and structural updates for the incoming agent to digest.
