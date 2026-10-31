"""Test and benchmark credentials -- read from the environment, never hard-coded.

Lookup order per role: the GRC_<ROLE>_PASSWORD environment variable, then
<ROLE>_PASSWORD in the secrets file: GRC_ENV_FILE if set, else the first file in
COMPOSE_ENV_FILES (the same file docker compose reads). There is deliberately no
fallback value and no fallback to a repo-root .env: since 2026-10-31 the secrets
file lives outside OneDrive, and one found inside OneDrive is refused
(Secrets_DB_Privilege_refactor.md §4). Only integration tests import this;
conftest.py keeps them out of a `-m "not integration"` run, so the unit suite
needs no secrets at all.
"""
import os
from pathlib import Path


def _secrets_file() -> Path | None:
    named = os.environ.get("GRC_ENV_FILE") or os.environ.get("COMPOSE_ENV_FILES", "").split(",")[0]
    if not named.strip():
        return None
    path = Path(named.strip()).expanduser().resolve()
    synced = [Path(v).resolve() for k, v in os.environ.items()
              if k in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial") and v]
    if any(part.lower().startswith("onedrive") for part in path.parts) or             any(path.is_relative_to(root) for root in synced):
        raise RuntimeError(f"Refusing a secrets file inside OneDrive ({path}): it syncs to the "
                           "cloud and keeps version history. Move it outside OneDrive.")
    return path


ROOT_ENV = _secrets_file()


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


_DOTENV = _read_dotenv(ROOT_ENV) if ROOT_ENV else {}


def password(role: str) -> str:
    key = f"{role.upper()}_PASSWORD"
    value = os.environ.get(f"GRC_{key}") or _DOTENV.get(key)
    if not value:
        where = ROOT_ENV or "the secrets file (set COMPOSE_ENV_FILES or GRC_ENV_FILE)"
        raise RuntimeError(f"No {key}: set GRC_{key} or add {key} to {where}")
    return value


ADMIN_PASS = password("admin")
ANALYST_PASS = password("analyst")
VIEWER_PASS = password("viewer")
