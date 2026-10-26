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
