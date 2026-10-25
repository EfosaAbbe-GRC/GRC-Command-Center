"""Test and benchmark credentials -- read from the environment, never hard-coded.

Lookup order per role: the GRC_<ROLE>_PASSWORD environment variable, then
<ROLE>_PASSWORD in the repo-root .env (the same gitignored file docker compose
reads). There is deliberately no fallback value: a missing password fails loudly
instead of trying a default that is published in this public repo.
"""
import os
from pathlib import Path

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


def _read_dotenv(path: Path) -> dict:
    values = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return values


_DOTENV = _read_dotenv(ROOT_ENV)


def password(role: str) -> str:
    key = f"{role.upper()}_PASSWORD"
    value = os.environ.get(f"GRC_{key}") or _DOTENV.get(key)
    if not value:
        raise RuntimeError(f"No {key}: set GRC_{key} or add {key} to {ROOT_ENV}")
    return value


ADMIN_PASS = password("admin")
ANALYST_PASS = password("analyst")
VIEWER_PASS = password("viewer")
