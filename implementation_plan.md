# Active Auditor: NIST AI RMF Gap Analysis Mission Plan

This document governs the autonomous execution of the baseline gap analysis against the NIST AI Risk Management Framework (RMF).

## Execution Hierarchy
1. **Level 1 (Global):** `Rules.md` (Deny-by-default, No DB Writes)
2. **Level 2 (Domain):** `active-auditor/SKILL.md` (Read-Only RAG)
3. **Level 3 (Mission):** This `implementation_plan.md` (Logical sequence)
4. **Level 4 (State):** `task.md` (Tracking)

## 5-Step Strategy

### Phase 1: Orchestration & Infrastructure
- Verify `grc-backend` status via `docker compose ps`.
- Check `http://localhost:8001/api/v1/health` to confirm the RAG engine is warm and initialized.

### Phase 2: Security Handshake (IAM-10)
- Authenticate as `admin` to acquire a temporary JWT.
- Query the `/api/v1/admin/policies` endpoint to verify the `AGENT_EXECUTE` capability status.
- **CRITICAL ABORT CONDITION:** If the `is_active` status for `AGENT_EXECUTE` is `false`, the mission must cease all execution immediately.

### Phase 3: Intelligence Gathering (RAG Extraction)
- Perform targeted queries for **"NIST AI RMF - Manage Function"** using the `/api/v1/chat` endpoint.
- Extract control documentation from the existing 18,337-split FAISS index.

### Phase 4: Comparative Analysis
- Map retrieved control evidence against the NIST AI RMF requirements.
- Identify specific instances of `INSUFFICIENT_DATA` or missing organizational controls.

### Phase 5: Reporting
- Generate a comprehensive `NIST_Gap_Analysis_Report.md` artifact.
- Include query traces, cited sources, identified gaps, and proposed remediation steps.

---
> [!IMPORTANT]
> This agent is strictly prohibited from writing directly to the `grc_audit.db` SQLite database. All reporting must be done via Markdown Artifacts.
