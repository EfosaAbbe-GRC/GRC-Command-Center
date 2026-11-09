"""Risk register API (Risk_Register_refactor.md §2 threats T1-T9, §5 tests).

Integration: runs against the isolated test stack on localhost:8002 by default. Risks can't be
deleted (T2), so this suite writes ONLY to the test stack and refuses to run its writes on dev.
"""
import csv
import io
import os
import uuid

import pytest
import requests

from tests._creds import ADMIN_PASS, ANALYST_PASS, VIEWER_PASS

pytestmark = pytest.mark.integration

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")
V1 = f"{BASE}/api/v1"
CREDS = {"admin": ADMIN_PASS, "analyst": ANALYST_PASS, "viewer": VIEWER_PASS}

if ":8002" not in BASE:
    pytest.skip("risk register writes are permanent: test stack (:8002) only", allow_module_level=True)

_TOKENS = {}


def _h(role):
    if role not in _TOKENS:
        try:
            r = requests.post(f"{V1}/auth/login", json={"username": role, "password": CREDS[role]}, timeout=30)
        except requests.ConnectionError:
            pytest.skip("test stack not reachable on :8002")
        if r.status_code != 200:
            pytest.skip(f"cannot log in as {role} ({r.status_code})")
        _TOKENS[role] = r.json()["access_token"]
    return {"Authorization": f"Bearer {_TOKENS[role]}"}


def _entity(role="analyst", **kw):
    body = {"name": f"pytest-process-{uuid.uuid4().hex[:8]}", "entity_type": "process"}
    body.update(kw)
    r = requests.post(f"{V1}/entities", headers=_h(role), json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _risk(role="analyst", **kw):
    body = {
        "title": f"pytest risk {uuid.uuid4().hex[:6]}",
        "statement": "Because backups are untested, a ransomware event could cause prolonged data loss.",
        "category": "information_security",
        "entity_id": _entity()["id"],
        "owner": "Head of IT",
        "inherent_likelihood": 4, "inherent_impact": 4,
    }
    body.update(kw)
    r = requests.post(f"{V1}/risks", headers=_h(role), json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _detail(risk_id, role="viewer"):
    r = requests.get(f"{V1}/risks/{risk_id}", headers=_h(role), timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _patch(risk, role="analyst", reason="pytest change", **fields):
    return requests.patch(f"{V1}/risks/{risk['id']}", headers=_h(role),
                          json={"version": risk["version"], "reason": reason, **fields}, timeout=30)


def _post(path, role, body):
    return requests.post(f"{V1}{path}", headers=_h(role), json=body, timeout=30)


# ── T8: roles ──────────────────────────────────────────────────────────────────────────
def test_no_token_is_refused():
    assert requests.get(f"{V1}/risks", timeout=30).status_code == 401


def test_viewer_reads_but_cannot_write():
    assert requests.get(f"{V1}/risks", headers=_h("viewer"), timeout=30).status_code == 200
    assert requests.get(f"{V1}/entities", headers=_h("viewer"), timeout=30).status_code == 200
    r = requests.post(f"{V1}/risks", headers=_h("viewer"), json={}, timeout=30)
    assert r.status_code == 403
    r = requests.post(f"{V1}/entities", headers=_h("viewer"), json={}, timeout=30)
    assert r.status_code == 403


# ── T5: no invented scores ─────────────────────────────────────────────────────────────
def test_client_sent_score_is_rejected():
    r = requests.post(f"{V1}/risks", headers=_h("analyst"), json={
        "title": "x", "statement": "x", "category": "operational", "entity_id": _entity()["id"],
        "owner": "x", "inherent_likelihood": 1, "inherent_impact": 1, "inherent_score": 25}, timeout=30)
    assert r.status_code == 422


@pytest.mark.parametrize("field, value", [("inherent_likelihood", 0), ("inherent_impact", 6)])
def test_out_of_range_rating_is_rejected(field, value):
    r = requests.post(f"{V1}/risks", headers=_h("analyst"), json={
        "title": "x", "statement": "x", "category": "operational", "entity_id": _entity()["id"],
        "owner": "x", "inherent_likelihood": 3, "inherent_impact": 3, field: value}, timeout=30)
    assert r.status_code == 422


def test_residual_above_inherent_is_rejected():
    r = requests.post(f"{V1}/risks", headers=_h("analyst"), json={
        "title": "x", "statement": "x", "category": "operational", "entity_id": _entity()["id"],
        "owner": "x", "inherent_likelihood": 2, "inherent_impact": 2,
        "residual_likelihood": 3, "residual_impact": 3}, timeout=30)
    assert r.status_code == 422


def test_text_length_is_limited():
    r = requests.post(f"{V1}/risks", headers=_h("analyst"), json={
        "title": "x" * 201, "statement": "x", "category": "operational", "entity_id": _entity()["id"],
        "owner": "x", "inherent_likelihood": 1, "inherent_impact": 1}, timeout=30)
    assert r.status_code == 422


def test_scores_bands_and_status_are_computed():
    risk = _risk()
    assert risk["inherent_score"] == 16 and risk["inherent_band"] == "high"
    assert risk["residual_score"] is None and risk["status"] == "identified"
    assert risk["ref"].startswith("R-") and risk["review_due"]
    risk = _risk(residual_likelihood=2, residual_impact=3)
    assert risk["residual_score"] == 6 and risk["residual_band"] == "medium"
    assert risk["status"] == "assessed"


# ── T1: every change is kept ───────────────────────────────────────────────────────────
def test_create_and_edit_write_history_with_before_and_after():
    risk = _risk()
    r = _patch(risk, reason="Owner moved to the CIO", owner="CIO")
    assert r.status_code == 200, r.text
    assert r.json()["version"] == risk["version"] + 1
    events = _detail(risk["id"])["events"]
    assert [e["event_type"] for e in events] == ["CREATED", "UPDATED"]
    assert events[0]["actor"] == "analyst"
    assert events[1]["changes"]["owner"] == {"before": "Head of IT", "after": "CIO"}
    assert events[1]["reason"] == "Owner moved to the CIO"


def test_edit_needs_a_reason():
    risk = _risk()
    r = requests.patch(f"{V1}/risks/{risk['id']}", headers=_h("analyst"),
                       json={"version": risk["version"], "owner": "CIO"}, timeout=30)
    assert r.status_code == 422


# ── T6: no silent overwrite ────────────────────────────────────────────────────────────
def test_stale_version_is_a_conflict():
    risk = _risk()
    assert _patch(risk, owner="A").status_code == 200
    assert _patch(risk, owner="B").status_code == 409   # same (now stale) version


# ── T2: nothing is deleted ─────────────────────────────────────────────────────────────
def test_no_delete_route():
    risk = _risk()
    r = requests.delete(f"{V1}/risks/{risk['id']}", headers=_h("admin"), timeout=30)
    assert r.status_code == 405


def test_close_needs_reason_then_freezes_until_reopened():
    risk = _risk()
    assert _post(f"/risks/{risk['id']}/close", "analyst", {"version": risk["version"]}).status_code == 422
    r = _post(f"/risks/{risk['id']}/close", "analyst", {"version": risk["version"], "reason": "Process retired"})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    closed = r.json()
    assert _patch(closed, owner="X").status_code == 409
    r = _post(f"/risks/{risk['id']}/reopen", "analyst", {"version": closed["version"], "reason": "Process back"})
    assert r.status_code == 200 and r.json()["status"] == "identified"


# ── T3/T4/T7: acceptance ───────────────────────────────────────────────────────────────
def _propose(risk, role="analyst", days=365):
    return _post(f"/risks/{risk['id']}/propose-acceptance", role,
                 {"version": risk["version"], "days": days, "reason": "Within appetite"})


def test_acceptance_needs_a_residual_rating():
    assert _propose(_risk()).status_code == 422


def test_critical_residual_cannot_be_accepted():
    risk = _risk(inherent_likelihood=5, inherent_impact=5, residual_likelihood=4, residual_impact=5)
    assert _propose(risk).status_code == 422


def test_high_residual_acceptance_is_capped_at_180_days():
    risk = _risk(inherent_likelihood=5, inherent_impact=5, residual_likelihood=3, residual_impact=4)
    assert _propose(risk, days=181).status_code == 422
    assert _propose(risk, days=180).status_code == 200


def test_analyst_cannot_record_an_acceptance():
    risk = _risk(residual_likelihood=2, residual_impact=2)
    proposed = _propose(risk).json()
    r = _post(f"/risks/{risk['id']}/accept", "analyst",
              {"version": proposed["version"], "accepted_by_owner": "Head of IT", "reason": "Owner agreed by email"})
    assert r.status_code == 403


def test_proposer_cannot_record_their_own_acceptance():
    risk = _risk(residual_likelihood=2, residual_impact=2)
    proposed = _propose(risk, role="admin").json()
    r = _post(f"/risks/{risk['id']}/accept", "admin",
              {"version": proposed["version"], "accepted_by_owner": "Head of IT", "reason": "Owner agreed by email"})
    assert r.status_code == 403


def test_acceptance_must_name_the_risk_owner():
    risk = _risk(residual_likelihood=2, residual_impact=2)
    proposed = _propose(risk).json()
    r = _post(f"/risks/{risk['id']}/accept", "admin",
              {"version": proposed["version"], "accepted_by_owner": "Someone Else", "reason": "Owner agreed by email"})
    assert r.status_code == 422
    assert "risk owner" in r.json()["detail"]


def test_owner_acceptance_recorded_by_admin():
    risk = _risk(residual_likelihood=2, residual_impact=2)
    proposed = _propose(risk, days=90).json()
    r = _post(f"/risks/{risk['id']}/accept", "admin",
              {"version": proposed["version"], "accepted_by_owner": " head of it ", "reason": "Signed by email"})
    assert r.status_code == 200, r.text
    accepted = r.json()
    assert accepted["status"] == "accepted" and accepted["acceptance_expires_at"]
    last = _detail(risk["id"])["events"][-1]
    assert last["event_type"] == "ACCEPTED" and last["actor"] == "admin"
    assert last["accepted_by_owner"] == "head of it" and last["expires_at"]


def test_changing_the_ratings_voids_an_acceptance():
    # R4: the acceptance belonged to the old facts.
    risk = _risk(residual_likelihood=2, residual_impact=2)
    proposed = _propose(risk).json()
    accepted = _post(f"/risks/{risk['id']}/accept", "admin",
                     {"version": proposed["version"], "accepted_by_owner": "Head of IT", "reason": "Owner agreed by email"}).json()
    r = _patch(accepted, reason="Re-rated after incident", residual_likelihood=3)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "assessed" and r.json()["acceptance_expires_at"] is None
    last = _detail(risk["id"])["events"][-1]
    assert "acceptance_expires_at" in last["changes"]


# ── T9: export can't carry a formula ───────────────────────────────────────────────────
def test_export_neutralises_formulas_and_is_admin_only():
    _risk(title='=HYPERLINK("http://example.invalid","x")')
    assert requests.get(f"{V1}/risks/export", headers=_h("analyst"), timeout=30).status_code == 403
    r = requests.get(f"{V1}/risks/export", headers=_h("admin"), timeout=30)
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][:3] == ["Ref", "Title", "Entity"]
    titles = [row[1] for row in rows[1:]]
    assert any(t.startswith("'=HYPERLINK") for t in titles)
    assert not any(t.startswith("=") for t in titles)


# ── views and entities ─────────────────────────────────────────────────────────────────
def test_heatmap_is_five_by_five():
    _risk()
    r = requests.get(f"{V1}/risks/heatmap?basis=inherent", headers=_h("viewer"), timeout=30)
    assert r.status_code == 200
    grid = r.json()["grid"]
    assert len(grid) == 5 and all(len(row) == 5 for row in grid)
    assert sum(map(sum, grid)) >= 1


def test_list_filters_by_band():
    _risk(inherent_likelihood=1, inherent_impact=2)
    r = requests.get(f"{V1}/risks?band=low", headers=_h("viewer"), timeout=30)
    assert r.status_code == 200 and r.json()
    assert all((x["residual_band"] or x["inherent_band"]) == "low" for x in r.json())


def test_entity_names_are_unique_per_type():
    e = _entity()
    r = requests.post(f"{V1}/entities", headers=_h("analyst"),
                      json={"name": e["name"], "entity_type": "process"}, timeout=30)
    assert r.status_code == 409


def test_vendor_entity_needs_a_real_vendor():
    r = requests.post(f"{V1}/entities", headers=_h("analyst"),
                      json={"name": f"v-{uuid.uuid4().hex[:6]}", "entity_type": "vendor",
                            "vendor_id": str(uuid.uuid4())}, timeout=30)
    assert r.status_code == 422
