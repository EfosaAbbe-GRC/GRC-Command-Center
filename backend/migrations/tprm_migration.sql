-- tprm_migration.sql — supplemental indexes for the TPRM module.
--
-- The immutability triggers for risk_acceptances are installed in code by
-- AuditLogger.init_db() (backend/core/database.py), reusing the existing
-- fn_prevent_immutability_violation() function — the SAME pattern used for
-- audit_logs and evidence_chain. They are NOT created here.
--
-- Tables themselves are created via Base.metadata.create_all in init_db().
-- This file only adds supplemental performance indexes, which SQLAlchemy's
-- create_all does not emit on its own. Safe to run repeatedly (IF NOT EXISTS).

CREATE INDEX IF NOT EXISTS idx_integrations_reassessment_due ON integrations (reassessment_due);
CREATE INDEX IF NOT EXISTS idx_stage_responses_integration   ON stage_responses (integration_id);
CREATE INDEX IF NOT EXISTS idx_risk_acceptances_integration  ON risk_acceptances (integration_id);
