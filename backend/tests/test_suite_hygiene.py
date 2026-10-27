"""The unit suite must run with no secrets present, and the full suite must still refuse to.

CI's unit job has no .env and runs `-m "not integration"`. If an integration module were
imported there, tests/_creds.py would raise at import and crash collection (found in the
2026-10-26 pipeline re-assessment). See docs/refactors/DevSecOps_Pipeline_refactor.md.
"""
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _collect(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.endswith("_PASSWORD")}
    env["GRC_ENV_FILE"] = str(tmp_path / "no-such.env")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120,
    )


def test_unit_run_collects_without_secrets(tmp_path):
    r = _collect(tmp_path, "-m", "not integration")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "test_security_config.py" in r.stdout
    assert "test_tprm.py" not in r.stdout


def test_full_run_without_secrets_fails_loudly(tmp_path):
    r = _collect(tmp_path)
    assert r.returncode != 0
    assert "No ADMIN_PASSWORD" in r.stdout + r.stderr
