"""
GRC Command Center — Executive endpoint tests (live-data honesty)

Regression coverage for the fabricated-KPI bug found 2026-08-17 during the
5-terminal empty-state audit: /executive/dashboard used to return
fixtures.json's `dashboard` block verbatim -- 8 open findings, 98% policy
coverage and **142 active users**, against 3 real accounts -- presented in the
Executive terminal as live governance metrics. See ExecutiveHonesty_refactor.md.

These assert the three footer metrics are now computed from real system state.
They deliberately do NOT assert exact literals (the numbers move as the dev
stack's data changes); they assert agreement with the DB and the absence of the
specific fixture values, which is what actually distinguishes real from canned.

Integration-style, consistent with test_tprm.py / test_iam_*.py: exercises a
live backend, by default the isolated test stack on localhost:8002. Set
GRC_TEST_BASE to target a different stack. Tests skip (not fail) when the
backend is unreachable.
"""
import os
import subprocess

import pytest
import requests

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")
V1 = f"{BASE}/api/v1"

_is_test_stack = ":8002" in BASE
DB_CONTAINER = os.environ.get(
    "GRC_TEST_DB_CONTAINER", "grc-db-pg-test" if _is_test_stack else "grc-db-pg")
DB_NAME = os.environ.get(
    "GRC_TEST_DB_NAME", "grc_audit_test" if _is_test_stack else "grc_audit")

# The exact values that used to be served from fixtures.json.
FIXTURE_OPEN_FINDINGS = 8
FIXTURE_POLICY_COVERAGE = 98
FIXTURE_ACTIVE_USERS = 142


def _login(role="admin"):
    creds = {"admin": ("admin", "grc-admin-2026")}[role]
    try:
        r = requests.post(f"{V1}/auth/login",
                          json={"username": creds[0], "password": creds[1]}, timeout=30)
    except requests.ConnectionError:
        pytest.skip("backend not reachable — start the stack to run executive tests")
    if r.status_code != 200:
        pytest.skip(f"cannot login as {role} ({r.status_code}) — is the DB seeded?")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _dashboard():
    r = requests.get(f"{V1}/executive/dashboard", headers=_login(), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _db_scalar(sql):
    """Query the DB directly so the assertion is against reality, not the API's
    own claim about reality."""
    try:
        out = subprocess.run(
            ["docker", "exec", DB_CONTAINER, "psql", "-U", "grc_admin", "-d", DB_NAME,
             "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        pytest.skip("docker/psql unavailable — cannot cross-check against the DB")
    if out.returncode != 0:
        pytest.skip(f"psql failed: {out.stderr.strip()}")
    return int(out.stdout.strip())


def test_dashboard_active_users_is_real_not_fixture():
    """The headline case: 142 fabricated users vs the real users table."""
    body = _dashboard()
    real = _db_scalar("SELECT COUNT(*) FROM users;")
    assert body["active_users"] == real, (
        f"active_users {body['active_users']} != real user count {real}")
    # Guard against a future fixture regression coincidentally matching.
    if real != FIXTURE_ACTIVE_USERS:
        assert body["active_users"] != FIXTURE_ACTIVE_USERS, (
            "active_users still returning the fixture value 142")


def test_dashboard_open_findings_counts_unresolved_gaps():
    """open_findings must be TPRM GAP stages with no risk acceptance."""
    body = _dashboard()
    real = _db_scalar("""
        SELECT COUNT(*) FROM stage_responses sr
        WHERE sr.status = 'GAP'
          AND NOT EXISTS (
              SELECT 1 FROM risk_acceptances ra
              WHERE ra.stage_id = sr.stage_id
                AND ra.integration_id = sr.integration_id
          );
    """)
    assert body["open_findings"] == real, (
        f"open_findings {body['open_findings']} != real unresolved gaps {real}")


def test_dashboard_policy_coverage_is_computed():
    """policy_coverage must be the real % of policies citing a framework source_doc."""
    body = _dashboard()
    total = _db_scalar("SELECT COUNT(*) FROM policies;")
    sourced = _db_scalar(
        "SELECT COUNT(*) FROM policies WHERE source_doc IS NOT NULL AND source_doc <> '';")
    expected = round((sourced / total) * 100) if total else 0
    assert body["policy_coverage"] == expected, (
        f"policy_coverage {body['policy_coverage']} != computed {expected} "
        f"({sourced}/{total} policies with source_doc)")


def test_dashboard_still_satisfies_response_model():
    """trend_data stays fixture-backed (labelled ILLUSTRATIVE in the UI) -- the
    merge must not drop schema-required keys."""
    body = _dashboard()
    for key in ("open_findings", "policy_coverage", "active_users", "trend_data"):
        assert key in body, f"missing required key {key}"
    assert isinstance(body["trend_data"], list)


def test_executive_stats_unchanged_shape():
    """The KPI block is knowingly illustrative and labelled as such in the UI;
    this only pins its shape so the Executive terminal cannot crash on it."""
    r = requests.get(f"{V1}/executive/stats", headers=_login(), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("compliance", "risk_score", "vulnerabilities", "audit_readiness",
                "budget", "alerts"):
        assert key in body, f"missing required key {key}"
    for kpi in ("compliance", "risk_score", "vulnerabilities", "audit_readiness"):
        assert "value" in body[kpi] and "trend" in body[kpi]
