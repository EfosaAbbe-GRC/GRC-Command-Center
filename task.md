# Active Auditor: Task Checklist

- [x] **Phase 1: Orchestration & Infrastructure**
    - [x] Run `docker compose ps` to verify container availability
    - [x] Check `http://localhost:8001/api/v1/health` status
- [x] **Phase 2: Security Handshake (IAM-10)**
    - [x] Fetch admin JWT via `/api/v1/auth/login`
    - [x] Verify `AGENT_EXECUTE` via `/api/v1/admin/policies` (Status: ENABLED)
    - [x] (Abort if disabled) - Proceeding to Phase 3.
- [x] **Phase 3: Intelligence Gathering (RAG Extraction)**
    - [x] Query NIST AI RMF Manage Function context
    - [x] Verify sources in retrieval response (Source: AI RMF 1.0.pdf)
    - [x] **Vault Integrity Verified Healthy** (SHA-256 Match)
- [x] **Phase 4: Comparative Analysis**
    - [x] Identify discrepancies and `INSUFFICIENT_DATA` points (HIGH SEVERITY)
- [x] **Phase 5: Reporting**
    - [x] Generate `NIST_Gap_Analysis_Report.md` artifact
