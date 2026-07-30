"""
Shared pytest fixtures for the backend suite.

Guards against admin-state poisoning. Several IAM tests mutate the SHARED
`admin` account's `must_change_password` flag (the forced-reset flow). If one
fails mid-flow it can leave admin locked, which then 403-cascades every
downstream admin-dependent test (all TPRM writes, iam_09/10) — producing a
misleading `11 failed / 4 passed` that looks like a TPRM regression but is not.

This autouse fixture clears the forced-reset flag for the seeded accounts
before AND after each test, so every test starts from a clean auth state and no
test can leak a lock to the next — regardless of order or mid-test failure.

It no-ops silently if docker/psql isn't reachable (the same dependency the
immutability tests already assume), so a bare run without the stack still works.
"""
import subprocess

import pytest

_DB_CONTAINER = "grc-db-pg"
_DB_USER = "grc_admin"
_DB_NAME = "grc_audit"


def _clear_forced_reset():
    """Best-effort: unlock the seeded accounts via the DB (users is mutable)."""
    try:
        subprocess.run(
            ["docker", "exec", _DB_CONTAINER, "psql", "-U", _DB_USER, "-d", _DB_NAME,
             "-c", "UPDATE users SET must_change_password = false "
                   "WHERE username IN ('admin', 'analyst', 'viewer');"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        # docker/psql unavailable — fall back to prior behavior silently.
        pass


@pytest.fixture(autouse=True)
def ensure_clean_admin_state():
    """Before each test: guarantee an unlocked start so no prior test can
    cascade a lock into this one. (Pre-clear is enough for isolation; the
    session finalizer below handles leaving the env clean, so we avoid a
    second docker-exec per test and the latency that caused a flaky timeout.)"""
    _clear_forced_reset()
    yield


@pytest.fixture(scope="session", autouse=True)
def _leave_clean_admin_state():
    """After the whole run: leave the seeded accounts unlocked regardless of
    what the last test did."""
    yield
    _clear_forced_reset()
