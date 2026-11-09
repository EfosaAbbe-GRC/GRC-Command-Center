"""Startup fail-closed checks (core.security_config). Pure unit tests: no stack, no Groq."""
from types import SimpleNamespace

import pytest

from core.security_config import (
    KNOWN_PUBLIC_PASSWORDS, JWT_PLACEHOLDER, assert_secure_config, config_problems, password_problem,
)

GOOD_PW = "a-long-enough-password"
GOOD_JWT = "x" * 64


def cfg(**overrides):
    base = dict(AUTH_ENABLED=True, JWT_SECRET_KEY=GOOD_JWT,
                ADMIN_PASSWORD=GOOD_PW, ANALYST_PASSWORD=GOOD_PW, VIEWER_PASSWORD=GOOD_PW)
    base.update(overrides)
    return SimpleNamespace(**base)


def test_good_config_passes():
    assert config_problems(cfg()) == []
    assert_secure_config(cfg())  # does not raise


@pytest.mark.parametrize("pw", sorted(KNOWN_PUBLIC_PASSWORDS))
def test_every_known_public_password_is_rejected(pw):
    assert password_problem(pw) == "is a publicly known value"


@pytest.mark.parametrize("pw, reason", [
    ("short", "shorter"),
    ("é" * 37, "72-byte"),          # 37 chars but 74 bytes: bcrypt would silently truncate
])
def test_weak_passwords_are_rejected(pw, reason):
    assert reason in password_problem(pw)


def test_jwt_placeholder_and_short_secret_are_rejected():
    assert any("JWT_SECRET_KEY" in p for p in config_problems(cfg(JWT_SECRET_KEY=JWT_PLACEHOLDER)))
    assert any("JWT_SECRET_KEY" in p for p in config_problems(cfg(JWT_SECRET_KEY="x" * 31)))


def test_auth_disabled_is_rejected():
    assert "AUTH_ENABLED is off" in config_problems(cfg(AUTH_ENABLED=False))


def test_default_bind_host_is_loopback():
    # `python main.py` binds settings.HOST. A 0.0.0.0 default exposed a directly-run backend to
    # the whole network. Docker is unaffected: its CMD passes --host itself and publishes
    # 127.0.0.1 only.
    from core.config import Settings
    assert Settings.model_fields["HOST"].default == "127.0.0.1"


def test_error_names_the_setting_but_never_the_value():
    with pytest.raises(RuntimeError) as exc:
        assert_secure_config(cfg(ADMIN_PASSWORD="grc-admin-2026", VIEWER_PASSWORD="tiny"))
    msg = str(exc.value)
    assert "ADMIN_PASSWORD" in msg and "VIEWER_PASSWORD" in msg
    assert "grc-admin-2026" not in msg and "tiny" not in msg


# ── Database posture guard (Secrets_DB_Privilege_refactor.md §5.4) ──────────────────────
from core.security_config import PROTECTED_TABLES, assert_db_posture_facts, db_posture_problems  # noqa: E402


def facts(**overrides):
    base = {
        "flags": {"rolsuper": False, "rolcreaterole": False, "rolcreatedb": False, "rolbypassrls": False},
        "owned_objects": 0,
        "tables": {t: {"update": True, "delete": True, "truncate": True, "chain": True}
                   for t in PROTECTED_TABLES},
    }
    base.update(overrides)
    return base


def test_least_privilege_posture_passes():
    assert db_posture_problems(facts()) == []
    assert_db_posture_facts(facts())  # does not raise


@pytest.mark.parametrize("flag", ["rolsuper", "rolcreaterole", "rolcreatedb", "rolbypassrls"])
def test_privileged_role_is_refused(flag):
    f = facts()
    f["flags"][flag] = True
    with pytest.raises(RuntimeError, match=flag):
        assert_db_posture_facts(f)


def test_role_that_owns_objects_is_refused():
    with pytest.raises(RuntimeError, match="owns"):
        assert_db_posture_facts(facts(owned_objects=3))


@pytest.mark.parametrize("table", PROTECTED_TABLES)
@pytest.mark.parametrize("check", ["update", "delete", "truncate", "chain"])
def test_missing_or_disabled_trigger_is_refused(table, check):
    f = facts()
    f["tables"][table][check] = False
    with pytest.raises(RuntimeError, match=table):
        assert_db_posture_facts(f)


def test_missing_table_is_refused():
    f = facts()
    del f["tables"]["security_events"]
    with pytest.raises(RuntimeError, match="security_events"):
        assert_db_posture_facts(f)


def test_six_protected_tables():
    # risk_events added 2026-11-08 (Risk_Register_refactor.md T1). Changing this set is a
    # reviewed decision, which is why it's pinned here.
    assert set(PROTECTED_TABLES) == {"audit_logs", "evidence_chain", "security_events",
                                     "risk_acceptances", "stage_evidence_links", "risk_events"}
