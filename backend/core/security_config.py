"""Refuse to start with a configuration that is known to be insecure.

Runs at app startup (lifespan), not at import, so tooling that imports core.*
without a full environment keeps working. See
docs/refactors/Security_Hardening_refactor.md (S4/S5).
"""
from core.config import settings

# Every password value that has ever been public: the placeholders in config.py
# and the defaults hard-coded in this repo's tests and legacy compose file before
# 2026-10-25. Rejecting them is what makes the rotation stick.
KNOWN_PUBLIC_PASSWORDS = frozenset({
    "CHANGE-ME-SET-IN-ENV",
    "grc-admin-2026", "grc-admin-new-2026", "grc-analyst-2026", "grc-viewer-2026",
})
JWT_PLACEHOLDER = "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET"
MIN_PASSWORD_LEN = 12
MIN_JWT_SECRET_LEN = 32
BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores everything past this


def password_problem(pw: str) -> str | None:
    """Why `pw` is unacceptable, or None. Never includes the password itself."""
    if pw in KNOWN_PUBLIC_PASSWORDS:
        return "is a publicly known value"
    if len(pw) < MIN_PASSWORD_LEN:
        return f"is shorter than {MIN_PASSWORD_LEN} characters"
    if len(pw.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return f"is longer than bcrypt's {BCRYPT_MAX_BYTES}-byte limit"
    return None


def config_problems(cfg=settings) -> list[str]:
    """Names of insecure settings -- names only, never values."""
    problems = []
    if cfg.AUTH_ENABLED is not True:
        problems.append("AUTH_ENABLED is off")
    jwt = cfg.JWT_SECRET_KEY
    if jwt == JWT_PLACEHOLDER or len(jwt) < MIN_JWT_SECRET_LEN:
        problems.append(f"JWT_SECRET_KEY is the placeholder or under {MIN_JWT_SECRET_LEN} chars")
    for name in ("ADMIN_PASSWORD", "ANALYST_PASSWORD", "VIEWER_PASSWORD"):
        why = password_problem(getattr(cfg, name))
        if why:
            problems.append(f"{name} {why}")
    return problems


def assert_secure_config(cfg=settings) -> None:
    problems = config_problems(cfg)
    if problems:
        raise RuntimeError("Insecure configuration, refusing to start: " + "; ".join(problems))


# ── Database posture (Secrets_DB_Privilege_refactor.md §5.4) ────────────────────────────
# Until 2026-10-31 the backend connected as the superuser that owned every table, so its own
# login could disable the immutability triggers (F1), and schema setup only logged failures
# (F2). The backend now refuses to start unless its role is unprivileged, owns nothing, and
# every protected table still has its blockers and its chain trigger.
PROTECTED_TABLES = ("audit_logs", "evidence_chain", "security_events",
                    "risk_acceptances", "stage_evidence_links",
                    "risk_events")   # risk register history (Risk_Register_refactor.md T1)
ROLE_FLAGS = ("rolsuper", "rolcreaterole", "rolcreatedb", "rolbypassrls")
TRIGGER_CHECKS = ("update", "delete", "truncate", "chain")

_POSTURE_SQL = {
    "flags": "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
             "FROM pg_roles WHERE rolname = current_user",
    "owned": """
        SELECT (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relowner = r.oid)
             + (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proowner = r.oid)
             + (SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE n.nspname = 'public' AND t.typowner = r.oid)
        FROM pg_roles r WHERE r.rolname = current_user""",
    # tgtype bits: 4 INSERT, 8 DELETE, 16 UPDATE, 32 TRUNCATE. tgenabled 'D' = disabled.
    "tables": """
        SELECT c.relname,
               bool_or(t.tgfoid = 'fn_prevent_immutability_violation'::regproc AND t.tgtype & 16 > 0),
               bool_or(t.tgfoid = 'fn_prevent_immutability_violation'::regproc AND t.tgtype & 8 > 0),
               bool_or(t.tgfoid = 'fn_prevent_immutability_violation'::regproc AND t.tgtype & 32 > 0),
               bool_or(t.tgfoid = 'fn_chain_append'::regproc AND t.tgtype & 4 > 0)
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_trigger t ON t.tgrelid = c.oid AND t.tgenabled <> 'D'
        WHERE n.nspname = 'public' AND c.relname = ANY(:tables)
        GROUP BY c.relname""",
}


def db_posture_problems(facts: dict) -> list[str]:
    """Names of failed posture checks -- check names only, never values."""
    problems = [f"database role has {flag}" for flag in ROLE_FLAGS if facts["flags"].get(flag) is not False]
    if facts["owned_objects"]:
        problems.append("database role owns objects in schema public")
    for table in PROTECTED_TABLES:
        found = facts["tables"].get(table)
        missing = [c for c in TRIGGER_CHECKS if not (found or {}).get(c)]
        if missing:
            problems.append(f"{table} lacks enabled trigger(s): {', '.join(missing)}")
    return problems


def assert_db_posture_facts(facts: dict) -> None:
    problems = db_posture_problems(facts)
    if problems:
        raise RuntimeError("Unsafe database posture, refusing to start: " + "; ".join(problems))


async def assert_db_posture(engine) -> None:
    """Read the posture over the app's own connection and refuse to start if it's unsafe.
    If the catalog functions are missing (no migration ran), the query itself fails: also a refusal."""
    from sqlalchemy import text
    try:
        async with engine.connect() as conn:
            flags = (await conn.execute(text(_POSTURE_SQL["flags"]))).one()
            owned = (await conn.execute(text(_POSTURE_SQL["owned"]))).scalar_one()
            rows = (await conn.execute(text(_POSTURE_SQL["tables"]),
                                       {"tables": list(PROTECTED_TABLES)})).all()
    except Exception as e:
        raise RuntimeError("Unsafe database posture, refusing to start: posture check failed "
                           f"({type(e).__name__}); has core.migrate run?") from None
    assert_db_posture_facts({
        "flags": dict(zip(ROLE_FLAGS, flags)),
        "owned_objects": owned,
        "tables": {r[0]: dict(zip(TRIGGER_CHECKS, r[1:])) for r in rows},
    })
