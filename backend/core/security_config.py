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
