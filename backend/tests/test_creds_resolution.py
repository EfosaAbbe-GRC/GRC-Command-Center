"""Where tests and the benchmark find their secrets (Secrets_DB_Privilege_refactor.md §4).

The secrets file moved out of OneDrive (F5: its old copy synced to the cloud, and OneDrive
re-creates deleted files). tests/_creds.py reads GRC_ENV_FILE, else the first file in
COMPOSE_ENV_FILES, refuses any path inside OneDrive, and never falls back to the repo .env.
Each case imports _creds in a fresh interpreter, because it reads the file at import.
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
GOOD = "ADMIN_PASSWORD=a-long-enough-pw-1\nANALYST_PASSWORD=a-long-enough-pw-2\nVIEWER_PASSWORD=a-long-enough-pw-3\n"


def _import_creds(**env_overrides):
    env = {k: v for k, v in os.environ.items()
           if not k.endswith("_PASSWORD") and k not in ("GRC_ENV_FILE", "COMPOSE_ENV_FILES")}
    env.update(env_overrides)
    return subprocess.run([sys.executable, "-c", "import tests._creds as c; print(c.ROOT_ENV)"],
                          cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)


def test_reads_the_file_compose_reads(tmp_path):
    f = tmp_path / "grc.env"
    f.write_text(GOOD, encoding="utf-8")
    r = _import_creds(COMPOSE_ENV_FILES=f"{f},{tmp_path / 'other.env'}")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(f)


def test_grc_env_file_wins(tmp_path):
    f = tmp_path / "explicit.env"
    f.write_text(GOOD, encoding="utf-8")
    r = _import_creds(GRC_ENV_FILE=str(f), COMPOSE_ENV_FILES=str(tmp_path / "ignored.env"))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(f)


def test_refuses_a_secrets_file_inside_onedrive(tmp_path):
    f = tmp_path / "OneDrive" / "Desktop" / "grc.env"
    f.parent.mkdir(parents=True)
    f.write_text(GOOD, encoding="utf-8")
    for var in ("GRC_ENV_FILE", "COMPOSE_ENV_FILES"):
        r = _import_creds(**{var: str(f)})
        assert r.returncode != 0, f"{var}: a secrets file under OneDrive was accepted"
        assert "OneDrive" in r.stderr and "a-long-enough" not in r.stderr


def test_no_configured_file_fails_loudly_without_repo_fallback():
    r = _import_creds()
    assert r.returncode != 0
    assert "COMPOSE_ENV_FILES" in r.stderr
