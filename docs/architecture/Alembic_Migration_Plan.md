# Alembic Migration Plan: SQLite → PostgreSQL

This document outlines the architectural implementation of the database transition while maintaining the **Strict Immutability** requirements of the GRC Command Center.

## 1. Schema Porting (SQLAlchemy)

The core models will be transitioned to SQLAlchemy 2.0 `DeclarativeBase`. The Primary Keys will shift from SQLite's `AUTOINCREMENT` to PostgreSQL `SERIAL` or `IDENTITY` columns.

## 2. Immutability Triggers (PL/pgSQL)

In PostgreSQL, triggers require a separate function. We will implement a centralized security function to enforce the "Deny-by-Default" rule on the audit trail.

### Security Function
```sql
CREATE OR REPLACE FUNCTION fn_prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'SECURITY VIOLATION: Audit logs and evidence records are immutable. UPDATE/DELETE operations are prohibited.';
END;
$$ LANGUAGE plpgsql;
```

### Trigger Bindings
The following triggers must be applied to `audit_logs`, `evidence_chain`, and `security_events`:

```sql
-- Applied to audit_logs
CREATE TRIGGER trg_no_update_audit BEFORE UPDATE ON audit_logs 
FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_modification();

CREATE TRIGGER trg_no_delete_audit BEFORE DELETE ON audit_logs 
FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_modification();

-- Applied to evidence_chain
CREATE TRIGGER trg_no_update_evidence BEFORE UPDATE ON evidence_chain 
FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_modification();

CREATE TRIGGER trg_no_delete_evidence BEFORE DELETE ON evidence_chain 
FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_modification();
```

## 3. Data Porting Sequence (Python Script)

Per the Supervisor's instruction, a custom Python script will perform a one-time "Extract, Transform, Load" (ETL) operation:

1.  **Extract**: Connect to `grc_audit.db` via `sqlite3`.
2.  **Transform**: Map SQLite `TEXT` (ISO timestamps) to PostgreSQL `TIMESTAMP`.
3.  **Load**: Batch insert into the PostgreSQL container using `asyncpg` to ensure data integrity.
4.  **Verify**: Perform a count-check on both databases to ensure 100% record parity before decommissioning the SQLite volume.

## 4. Volume Persistence Verification

| Volume | Migration Action |
| :--- | :--- |
| `grc-db` (SQLite) | Archived after successful ETL. |
| `grc-db-data` (PG) | **NEW:** Initialized with migrated data. |
| `grc-faiss` (Vector) | **PRESERVED:** No modification; shared across containers. |
