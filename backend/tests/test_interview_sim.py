"""
GRC Command Center — TPRM Interview Simulator Tests (Auth + RBAC + session lifecycle)

Integration-style, consistent with test_tprm.py: exercises a live backend, by
default the isolated test stack on localhost:8002. Requires the test stack up
(docker compose -f docker-compose.test.yml up) and assessment_stages seeded
(automatic via lifespan). Set GRC_TEST_BASE to target a different stack.

Tests skip (not fail) when the backend is unreachable.

Deliberately LLM-call-frugal: grading hits the live Groq API and shares the
same 200k-token/day budget as the RAG benchmark and every other LLM feature
(see GRC_Command_Center/HANDOFF.md). Only ONE test in this file submits a
turn response and pays for a real grading call; everything else (session
creation, RBAC, pool-selection edge cases, spoiler redaction, double-submit)
is exercised without triggering the LLM.
"""
import os
import uuid

import pytest
import requests

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")
V1 = f"{BASE}/api/v1"

CREDS = {
    "admin":   ("admin",   "grc-admin-2026"),
    "analyst": ("analyst", "grc-analyst-2026"),
    "viewer":  ("viewer",  "grc-viewer-2026"),
}


def _require_backend():
    try:
        requests.get(f"{V1}/health", timeout=10)
    except requests.ConnectionError:
        pytest.skip("backend not reachable — start the stack to run Interview Simulator tests")


def _login(role):
    user, pwd = CREDS[role]
    try:
        r = requests.post(f"{V1}/auth/login", json={"username": user, "password": pwd}, timeout=30)
    except requests.ConnectionError:
        pytest.skip("backend not reachable — start the stack to run Interview Simulator tests")
    if r.status_code != 200:
        pytest.skip(f"cannot login as {role} ({r.status_code}) — is the DB seeded?")
    return r.json()["access_token"]


def _headers(role):
    return {"Authorization": f"Bearer {_login(role)}"}


def _make_vendor_with_gap(headers):
    """Creates a fresh vendor + integration + drives one stage to GAP, so a
    vendor-scoped interview session has a real, non-empty question pool.
    Mirrors test_tprm.py's _create_integration helper."""
    v = requests.post(f"{V1}/tprm/vendors", headers=headers,
                       json={"name": f"pytest-interview-vendor-{uuid.uuid4().hex[:8]}",
                             "contact_email": "pytest@example.com"}, timeout=30)
    assert v.status_code == 200, f"vendor create: {v.status_code} {v.text}"
    vendor = v.json()

    i = requests.post(f"{V1}/tprm/integrations", headers=headers,
                       json={"vendor_id": vendor["id"], "name": f"pytest-integ-{uuid.uuid4().hex[:8]}",
                             "direction": "egress", "transfer_method": "file",
                             "data_classification": "PII", "volume_per_transfer": 0,
                             "involves_regulated_data": "none"}, timeout=30)
    assert i.status_code == 200, f"integration create: {i.status_code} {i.text}"
    integration = i.json()

    stages = requests.get(f"{V1}/tprm/integrations/{integration['id']}/stages",
                           headers=headers, timeout=30).json()
    assert stages, "no stages seeded for a fresh egress/file integration"
    stage = stages[0]
    s = requests.post(f"{V1}/tprm/integrations/{integration['id']}/stages/{stage['stage_id']}",
                       headers=headers, json={"status": "gap"}, timeout=30)
    assert s.status_code == 200, f"stage gap set: {s.status_code} {s.text}"

    return vendor


# ─── Authentication / RBAC boundaries ───────────────────────────────────────
def test_interview_sim_requires_authentication():
    _require_backend()
    r = requests.get(f"{V1}/interview-sim/sessions", timeout=30)  # no token
    assert r.status_code == 401, f"unauthenticated access should be 401, got {r.status_code}"


def test_interview_sim_viewer_denied():
    # INTERVIEW_RUN requires analyst; viewer is below that.
    r = requests.get(f"{V1}/interview-sim/sessions", headers=_headers("viewer"), timeout=30)
    assert r.status_code == 403, f"viewer should be 403, got {r.status_code}"


# ─── Session creation — validation & real-data grounding ───────────────────
def test_start_session_requires_a_valid_mode():
    headers = _headers("analyst")
    # Neither vendor nor direction/method.
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers, json={}, timeout=30)
    assert r.status_code == 422

    # Both at once.
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"scenario_vendor": "x", "direction": "egress",
                             "transfer_method": "file"}, timeout=30)
    assert r.status_code == 422


def test_start_session_unknown_vendor_404():
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"scenario_vendor": f"no-such-vendor-{uuid.uuid4().hex[:8]}"}, timeout=30)
    assert r.status_code == 404


def test_start_session_vendor_with_no_gaps_409():
    headers = _headers("analyst")
    # A freshly created vendor+integration has every stage NOT_STARTED, not
    # GAP/IN_REVIEW -- the session must refuse rather than inventing content.
    v = requests.post(f"{V1}/tprm/vendors", headers=headers,
                       json={"name": f"pytest-interview-clean-{uuid.uuid4().hex[:8]}"}, timeout=30)
    assert v.status_code == 200
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"scenario_vendor": v.json()["name"]}, timeout=30)
    assert r.status_code == 409


def test_start_session_vendor_scoped_pool_matches_real_gaps():
    headers = _headers("analyst")
    vendor = _make_vendor_with_gap(headers)
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"scenario_vendor": vendor["name"]}, timeout=30)
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["scenario_vendor"] == vendor["name"]
    assert session["total_turns"] == 1  # exactly one stage was driven to GAP
    assert session["status"] == "in_progress"
    # Only the current (first, unanswered) turn's question is revealed.
    assert len(session["turns"]) == 1
    assert session["turns"][0]["question_text"] != "(not yet revealed)"
    assert "GAP" in session["turns"][0]["question_text"]


def test_start_session_method_scoped_uses_real_seed_count():
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"direction": "egress", "transfer_method": "file"}, timeout=30)
    assert r.status_code == 200, r.text
    session = r.json()
    assert session["scenario_vendor"] is None
    assert session["scenario_method"] == "egress/file"
    assert session["total_turns"] > 1  # real seeded stage count, not a fixed constant


def test_get_session_redacts_future_questions():
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"direction": "egress", "transfer_method": "file"}, timeout=30)
    session = r.json()
    assert session["total_turns"] >= 2, "need >=2 turns to prove redaction"

    detail = requests.get(f"{V1}/interview-sim/sessions/{session['id']}", headers=headers, timeout=30).json()
    assert detail["turns"][0]["question_text"] != "(not yet revealed)"
    assert detail["turns"][1]["question_text"] == "(not yet revealed)"


def test_get_session_wrong_owner_404():
    # A session started by analyst must not be readable by admin, even though
    # admin outranks analyst in the role hierarchy -- ownership, not role,
    # gates a personal practice session.
    analyst_headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=analyst_headers,
                       json={"direction": "ingress", "transfer_method": "api"}, timeout=30)
    session_id = r.json()["id"]

    admin_headers = _headers("admin")
    r2 = requests.get(f"{V1}/interview-sim/sessions/{session_id}", headers=admin_headers, timeout=30)
    assert r2.status_code == 404


# ─── Turn response lifecycle (no LLM call) ──────────────────────────────────
def test_respond_to_unknown_turn_404():
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"direction": "egress", "transfer_method": "file"}, timeout=30)
    session_id = r.json()["id"]
    fake_turn_id = str(uuid.uuid4())
    r2 = requests.post(f"{V1}/interview-sim/sessions/{session_id}/turns/{fake_turn_id}/respond",
                        headers=headers, json={"response_text": "anything"}, timeout=30)
    assert r2.status_code == 404


def test_respond_rejects_empty_answer():
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"direction": "egress", "transfer_method": "file"}, timeout=30)
    session = r.json()
    turn_id = session["turns"][0]["id"]
    r2 = requests.post(
        f"{V1}/interview-sim/sessions/{session['id']}/turns/{turn_id}/respond",
        headers=headers, json={"response_text": "   "}, timeout=30)
    assert r2.status_code == 422


# ─── The one LLM-calling test: full grading round trip + honesty contract ──
def test_respond_grades_and_never_fabricates_on_failure():
    """The single live-grading call in this suite. Asserts the contract that
    matters most: IF grading_status == "graded" THEN score/feedback are
    present; IF grading_status == "grading_failed" THEN score is null --
    never a fabricated score standing in for a failed grading call. Both
    outcomes are accepted as passing since this hits a live external API."""
    headers = _headers("analyst")
    r = requests.post(f"{V1}/interview-sim/sessions", headers=headers,
                       json={"direction": "egress", "transfer_method": "file"}, timeout=30)
    session = r.json()
    turn_id = session["turns"][0]["id"]

    r2 = requests.post(
        f"{V1}/interview-sim/sessions/{session['id']}/turns/{turn_id}/respond",
        headers=headers,
        json={"response_text": ("We would request the vendor's most recent SOC 2 Type II report, "
                                 "review the relevant Trust Services Criteria exceptions, and confirm "
                                 "compensating controls are documented with an expiry date.")},
        timeout=60)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    turn = body["turn"]
    assert turn["grading_status"] in ("graded", "grading_failed")
    if turn["grading_status"] == "graded":
        assert turn["score"] is not None and 0 <= turn["score"] <= 100
        assert turn["feedback_text"]
        assert turn["rubric_json"]
    else:
        assert turn["score"] is None
        assert turn["feedback_text"] is None

    # Double-submit on the same turn must be rejected, graded or not.
    r3 = requests.post(
        f"{V1}/interview-sim/sessions/{session['id']}/turns/{turn_id}/respond",
        headers=headers, json={"response_text": "second attempt"}, timeout=30)
    assert r3.status_code == 409


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
