"""
GRC Command Center — TPRM Module Tests (Auth + RBAC + lifecycle + immutability)

Integration-style, consistent with test_iam_*.py / test_auth.py: exercises the
live backend on localhost:8001. Run with either:

    pytest tests/test_tprm.py -v
    python tests/test_tprm.py

Requires the stack up (docker compose -f docker-compose-v2.yml up) and the
assessment_stages table seeded (python -m data.seed_tprm_stages).

Tests skip (not fail) when the backend is unreachable, so a bare `pytest` run
without the stack does not produce false red.
"""
import os
import uuid
import subprocess
from datetime import datetime, timezone

import pytest
import requests

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8001")
V1 = f"{BASE}/api/v1"

CREDS = {
    "admin":   ("admin",   "grc-admin-2026"),
    "analyst": ("analyst", "grc-analyst-2026"),
    "viewer":  ("viewer",  "grc-viewer-2026"),
}


# ─── Helpers ────────────────────────────────────────────────────────────────
def _require_backend():
    try:
        requests.get(f"{V1}/health", timeout=10)
    except requests.ConnectionError:
        pytest.skip("backend not reachable on :8001 — start the stack to run TPRM tests")


def _login(role):
    user, pwd = CREDS[role]
    try:
        r = requests.post(f"{V1}/auth/login", json={"username": user, "password": pwd}, timeout=30)
    except requests.ConnectionError:
        pytest.skip("backend not reachable on :8001 — start the stack to run TPRM tests")
    if r.status_code != 200:
        pytest.skip(f"cannot login as {role} ({r.status_code}) — is the DB seeded?")
    return r.json()["access_token"]


def _headers(role):
    return {"Authorization": f"Bearer {_login(role)}"}


def _create_integration(headers, direction="egress", classification="PII",
                        volume=0, regulated="none", vendor_id=None):
    if vendor_id is None:
        v = requests.post(
            f"{V1}/tprm/vendors", headers=headers,
            json={"name": f"pytest-vendor-{uuid.uuid4().hex[:8]}",
                  "contact_email": "pytest@example.com"}, timeout=30)
        assert v.status_code == 200, f"vendor create: {v.status_code} {v.text}"
        vendor_id = v.json()["id"]

    r = requests.post(
        f"{V1}/tprm/integrations", headers=headers,
        json={"vendor_id": vendor_id, "name": f"pytest-integ-{uuid.uuid4().hex[:8]}",
              "direction": direction, "transfer_method": "file",
              "data_classification": classification, "volume_per_transfer": volume,
              "involves_regulated_data": regulated}, timeout=30)
    assert r.status_code == 200, f"integration create: {r.status_code} {r.text}"
    return r.json()


def _get_vendor(headers, vendor_id):
    r = requests.get(f"{V1}/tprm/vendors", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    match = next((v for v in r.json() if v["id"] == vendor_id), None)
    assert match is not None, f"vendor {vendor_id} not found in list"
    return match


def _stages(headers, integ_id):
    r = requests.get(f"{V1}/tprm/integrations/{integ_id}/stages", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _set_stage(headers, integ_id, stage_id, status):
    r = requests.post(f"{V1}/tprm/integrations/{integ_id}/stages/{stage_id}",
                      headers=headers, json={"status": status}, timeout=30)
    assert r.status_code == 200, r.text


# ─── Authentication / RBAC boundaries ───────────────────────────────────────
def test_tprm_requires_authentication():
    _require_backend()
    r = requests.get(f"{V1}/tprm/integrations", timeout=30)  # no token
    assert r.status_code == 401, f"unauthenticated access should be 401, got {r.status_code}"


def test_tprm_viewer_denied_view():
    # TPRM_VIEW requires analyst; viewer is below that.
    r = requests.get(f"{V1}/tprm/integrations", headers=_headers("viewer"), timeout=30)
    assert r.status_code == 403, f"viewer should be 403, got {r.status_code}"


def test_tprm_analyst_can_view():
    r = requests.get(f"{V1}/tprm/integrations", headers=_headers("analyst"), timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_tprm_signoff_requires_admin():
    """Analyst may assess but must NOT approve or sign risk acceptances."""
    integ = _create_integration(_headers("admin"))
    a = _headers("analyst")

    r_approve = requests.post(f"{V1}/tprm/integrations/{integ['id']}/approve", headers=a, timeout=30)
    assert r_approve.status_code == 403, f"analyst approve should be 403, got {r_approve.status_code}"

    r_accept = requests.post(
        f"{V1}/tprm/integrations/{integ['id']}/risk-acceptances", headers=a,
        json={"stage_id": str(uuid.uuid4()), "gap_description": "x",
              "compensating_control": "x"}, timeout=30)
    assert r_accept.status_code == 403, f"analyst risk-acceptance should be 403, got {r_accept.status_code}"


# ─── Risk tiering (server-computed, not client-chosen) ──────────────────────
def test_tprm_risk_tiering():
    h = _headers("admin")
    assert _create_integration(h, classification="PHI", regulated="HIPAA")["computed_risk_tier"] == "critical"
    assert _create_integration(h, classification="PII", volume=50000)["computed_risk_tier"] == "high"
    assert _create_integration(h, classification="PII")["computed_risk_tier"] == "medium"
    assert _create_integration(h, classification="public")["computed_risk_tier"] == "low"


# ─── Vendor-level risk rollup (Tier 2.3) ────────────────────────────────────
def test_tprm_vendor_rollup():
    h = _headers("admin")
    low = _create_integration(h, classification="public")
    vendor_id = low["vendor_id"]
    assert _get_vendor(h, vendor_id)["overall_risk_tier"] == "low"

    _create_integration(h, classification="PHI", regulated="HIPAA", vendor_id=vendor_id)
    assert _get_vendor(h, vendor_id)["overall_risk_tier"] == "critical"

    # A later, lower-tier integration must not downgrade the vendor's rollup.
    _create_integration(h, classification="public", vendor_id=vendor_id)
    assert _get_vendor(h, vendor_id)["overall_risk_tier"] == "critical"


# ─── Deny-by-default approval ───────────────────────────────────────────────
def test_tprm_deny_by_default_then_clean_approve():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    assert integ["status"] == "under_assessment"

    # Cannot approve while stages are unreviewed.
    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 409, f"pending approval should be 409, got {r.status_code}"

    stages = _stages(h, iid)
    assert len(stages) == 13, f"egress should have 13 stages, got {len(stages)}"
    for s in stages:
        _set_stage(h, iid, s["stage_id"], "pass")

    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


def test_tprm_gap_requires_acceptance_to_approve():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)

    gap_stage = stages[0]["stage_id"]
    _set_stage(h, iid, gap_stage, "gap")
    for s in stages[1:]:
        _set_stage(h, iid, s["stage_id"], "pass")

    # Open gap with no acceptance → blocked.
    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 409, f"uncovered gap should block approval, got {r.status_code}"

    # Admin signs the acceptance for that gap.
    ra = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": gap_stage, "gap_description": "pytest gap",
              "compensating_control": "pytest control", "expires_in_days": 30}, timeout=30)
    assert ra.status_code == 200, ra.text
    assert ra.json()["integration_status"] == "approved_with_exceptions"

    # Now the gap is covered → approval succeeds as an exception.
    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved_with_exceptions"

    sm = requests.get(f"{V1}/tprm/integrations/{iid}/summary", headers=h, timeout=30).json()
    assert sm["open_gaps"] == 1


# ─── Input & target validation ──────────────────────────────────────────────
def test_tprm_input_validation():
    h = _headers("admin")
    v = requests.post(f"{V1}/tprm/vendors", headers=h,
                      json={"name": f"pytest-vendor-{uuid.uuid4().hex[:8]}"}, timeout=30)
    vid = v.json()["id"]

    # Invalid enum value for direction → 422.
    bad_dir = requests.post(f"{V1}/tprm/integrations", headers=h, json={
        "vendor_id": vid, "name": "x", "direction": "sideways",
        "transfer_method": "file", "data_classification": "PII"}, timeout=30)
    assert bad_dir.status_code == 422

    # Missing required data_classification → 422.
    missing = requests.post(f"{V1}/tprm/integrations", headers=h, json={
        "vendor_id": vid, "name": "x", "direction": "egress",
        "transfer_method": "file"}, timeout=30)
    assert missing.status_code == 422


def test_tprm_risk_acceptance_target_validation():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)

    # Stage that isn't part of this integration → 404.
    r_foreign = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": str(uuid.uuid4()), "gap_description": "x",
              "compensating_control": "x"}, timeout=30)
    assert r_foreign.status_code == 404

    # Real stage but not a GAP (still not_started) → 409.
    r_notgap = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": stages[0]["stage_id"], "gap_description": "x",
              "compensating_control": "x"}, timeout=30)
    assert r_notgap.status_code == 409


# ─── Append-only immutability (parity with audit_logs / evidence_chain) ──────
def test_tprm_risk_acceptance_immutable():
    """A signed risk acceptance must be UPDATE/DELETE-proof at the DB layer."""
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    gap_stage = stages[0]["stage_id"]
    _set_stage(h, iid, gap_stage, "gap")

    ra = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": gap_stage, "gap_description": "immutability probe",
              "compensating_control": "x", "expires_in_days": 30}, timeout=30)
    assert ra.status_code == 200, ra.text

    try:
        probe = subprocess.run(
            ["docker", "exec", "grc-db-pg", "psql", "-U", "grc_admin", "-d", "grc_audit",
             "-c", "UPDATE risk_acceptances SET gap_description = 'TAMPER' "
                   "WHERE id = (SELECT id FROM risk_acceptances LIMIT 1);"],
            capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        pytest.skip("docker not on PATH — cannot probe DB trigger directly")

    combined = probe.stdout + probe.stderr
    assert "ERROR" in combined and "immutable" in combined.lower(), \
        f"UPDATE on risk_acceptances was NOT blocked: {combined[:200]}"


# ─── Tier 1: read-back, cadence, audit trail, TRUNCATE hardening ─────────────
def test_tprm_risk_acceptance_readback():
    """The acceptances table must be readable, not just write-only."""
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    gap_stage = stages[0]["stage_id"]
    _set_stage(h, iid, gap_stage, "gap")

    ra = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": gap_stage, "gap_description": "readback probe",
              "compensating_control": "pytest control", "expires_in_days": 30}, timeout=30)
    assert ra.status_code == 200, ra.text

    listed = requests.get(f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h, timeout=30)
    assert listed.status_code == 200, listed.text
    items = listed.json()
    assert len(items) == 1
    assert items[0]["stage_id"] == gap_stage
    assert items[0]["gap_description"] == "readback probe"
    assert items[0]["accepted_by"] == "admin"


def test_tprm_stage_readback_includes_review_metadata():
    """Widened StageOut must surface evidence_notes/reviewed_by/reviewed_at."""
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    target = stages[0]["stage_id"]

    r = requests.post(f"{V1}/tprm/integrations/{iid}/stages/{target}", headers=h,
                      json={"status": "pass", "evidence_notes": "pytest evidence"}, timeout=30)
    assert r.status_code == 200, r.text

    refreshed = _stages(h, iid)
    updated = next(s for s in refreshed if s["stage_id"] == target)
    assert updated["evidence_notes"] == "pytest evidence"
    assert updated["reviewed_by"] == "admin"
    assert updated["reviewed_at"] is not None


def test_tprm_expiring_acceptances_endpoint_smoke():
    """Behavioral smoke test only — a real expiry can't elapse inside a test run."""
    h = _headers("admin")
    r = requests.get(f"{V1}/tprm/acceptances/expiring", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)


# ─── CSV export (Tier 3.2) ───────────────────────────────────────────────────
def test_tprm_export_csv():
    h = _headers("admin")
    _create_integration(h, classification="PII")  # ensure at least one row exists
    r = requests.get(f"{V1}/tprm/export", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    assert "--- INTEGRATIONS ---" in body
    assert "--- STAGE ASSESSMENTS ---" in body
    assert "--- RISK ACCEPTANCES ---" in body


def test_tprm_export_csv_requires_evidence_export_capability():
    # EVIDENCE_EXPORT is admin-only; analyst (TPRM_VIEW/ASSESS) must not have it.
    r = requests.get(f"{V1}/tprm/export", headers=_headers("analyst"), timeout=30)
    assert r.status_code == 403, f"analyst export should be 403, got {r.status_code}"


# ─── Stage evidence linkage (Tier 3.3) ───────────────────────────────────────
def test_tprm_evidence_upload_and_readback():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stage_id = _stages(h, iid)[0]["stage_id"]

    r = requests.post(
        f"{V1}/tprm/integrations/{iid}/stages/{stage_id}/evidence", headers=h,
        files={"file": ("evidence.txt", b"pytest evidence contents", "text/plain")}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "evidence linked"
    assert "file_hash" in body and len(body["file_hash"]) == 64  # sha256 hex digest

    listing = requests.get(f"{V1}/tprm/integrations/{iid}/stages/{stage_id}/evidence", headers=h, timeout=30)
    assert listing.status_code == 200, listing.text
    entries = listing.json()
    assert len(entries) == 1
    assert entries[0]["filename"] == "evidence.txt"
    assert entries[0]["file_hash"] == body["file_hash"]
    assert entries[0]["linked_by"] == "admin"


def test_tprm_evidence_upload_requires_assess():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stage_id = _stages(h, iid)[0]["stage_id"]

    r = requests.post(
        f"{V1}/tprm/integrations/{iid}/stages/{stage_id}/evidence", headers=_headers("viewer"),
        files={"file": ("x.txt", b"content", "text/plain")}, timeout=30)
    assert r.status_code == 403, f"viewer upload should be 403, got {r.status_code}"


def test_tprm_evidence_upload_rejects_empty_file():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stage_id = _stages(h, iid)[0]["stage_id"]

    r = requests.post(
        f"{V1}/tprm/integrations/{iid}/stages/{stage_id}/evidence", headers=h,
        files={"file": ("empty.txt", b"", "text/plain")}, timeout=30)
    assert r.status_code == 422, f"empty file should be 422, got {r.status_code}"


def test_tprm_evidence_link_immutable():
    """UPDATE must be blocked by the row-level trigger, same guarantee as risk_acceptances."""
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stage_id = _stages(h, iid)[0]["stage_id"]
    r = requests.post(
        f"{V1}/tprm/integrations/{iid}/stages/{stage_id}/evidence", headers=h,
        files={"file": ("immutable_probe.txt", b"immutability probe", "text/plain")}, timeout=30)
    assert r.status_code == 200, r.text

    try:
        probe = subprocess.run(
            ["docker", "exec", "grc-db-pg", "psql", "-U", "grc_admin", "-d", "grc_audit",
             "-c", "UPDATE stage_evidence_links SET linked_by = 'tampered';"],
            capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        pytest.skip("docker not on PATH — cannot probe DB trigger directly")

    combined = probe.stdout + probe.stderr
    assert "ERROR" in combined and "immutable" in combined.lower(), \
        f"UPDATE on stage_evidence_links was NOT blocked: {combined[:200]}"


def test_tprm_reassessment_cadence_by_tier():
    h = _headers("admin")
    now = datetime.now(timezone.utc)

    critical = _create_integration(h, classification="PHI", regulated="HIPAA")
    assert critical["computed_risk_tier"] == "critical"
    due = datetime.fromisoformat(critical["reassessment_due"].replace("Z", "+00:00"))
    days_out = (due - now).days
    assert 88 <= days_out <= 91, f"CRITICAL reassessment_due should be ~90 days out, got {days_out}"

    low = _create_integration(h, classification="public")
    assert low["computed_risk_tier"] == "low"
    due_low = datetime.fromisoformat(low["reassessment_due"].replace("Z", "+00:00"))
    days_out_low = (due_low - now).days
    assert 363 <= days_out_low <= 366, f"LOW reassessment_due should be ~365 days out, got {days_out_low}"


def test_tprm_security_events_logged_on_approve():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    for s in stages:
        _set_stage(h, iid, s["stage_id"], "pass")

    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 200, r.text

    events = requests.get(f"{V1}/admin/audit/security", headers=h,
                          params={"event_type": "TPRM_APPROVE", "limit": 20}, timeout=30)
    assert events.status_code == 200, events.text
    matches = [e for e in events.json() if iid in (e.get("detail") or "")]
    assert matches, f"expected a TPRM_APPROVE security event referencing integration {iid}"


def test_tprm_risk_acceptance_truncate_blocked():
    """TRUNCATE must be blocked by the statement-level trigger too, not just UPDATE/DELETE."""
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    gap_stage = stages[0]["stage_id"]
    _set_stage(h, iid, gap_stage, "gap")

    ra = requests.post(
        f"{V1}/tprm/integrations/{iid}/risk-acceptances", headers=h,
        json={"stage_id": gap_stage, "gap_description": "truncate probe",
              "compensating_control": "x", "expires_in_days": 30}, timeout=30)
    assert ra.status_code == 200, ra.text

    try:
        probe = subprocess.run(
            ["docker", "exec", "grc-db-pg", "psql", "-U", "grc_admin", "-d", "grc_audit",
             "-c", "TRUNCATE risk_acceptances;"],
            capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        pytest.skip("docker not on PATH — cannot probe DB trigger directly")

    combined = probe.stdout + probe.stderr
    assert "ERROR" in combined and "immutable" in combined.lower(), \
        f"TRUNCATE on risk_acceptances was NOT blocked: {combined[:200]}"


# ─── Tier 2 (2.4): method applicability + Not Applicable status ──────────────
def test_tprm_stage_fanout_by_method():
    h = _headers("admin")
    api_integ = _create_integration(h)
    api_integ_id = api_integ["id"]
    # _create_integration hardcodes transfer_method="file"; build an API one directly
    # to exercise the fan-out filter (egress stages #4/#6 are file-only).
    v = requests.post(f"{V1}/tprm/vendors", headers=h,
                      json={"name": f"pytest-vendor-{uuid.uuid4().hex[:8]}"}, timeout=30)
    r = requests.post(f"{V1}/tprm/integrations", headers=h, json={
        "vendor_id": v.json()["id"], "name": f"pytest-api-integ-{uuid.uuid4().hex[:8]}",
        "direction": "egress", "transfer_method": "api",
        "data_classification": "PII", "volume_per_transfer": 0, "involves_regulated_data": "none",
    }, timeout=30)
    assert r.status_code == 200, r.text
    api_stages = _stages(h, r.json()["id"])
    assert len(api_stages) == 11, f"API egress should exclude the 2 file-only stages, got {len(api_stages)}"

    file_stages = _stages(h, api_integ_id)
    assert len(file_stages) == 13, f"file egress should include all 13 stages, got {len(file_stages)}"


def test_tprm_not_applicable_requires_justification():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    target = stages[0]["stage_id"]

    no_note = requests.post(f"{V1}/tprm/integrations/{iid}/stages/{target}",
                            headers=h, json={"status": "not_applicable"}, timeout=30)
    assert no_note.status_code == 422, no_note.text

    with_note = requests.post(f"{V1}/tprm/integrations/{iid}/stages/{target}", headers=h,
                              json={"status": "not_applicable", "evidence_notes": "pytest justification"}, timeout=30)
    assert with_note.status_code == 200, with_note.text


def test_tprm_not_applicable_resolves_and_allows_approval():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)

    na_stage = stages[0]["stage_id"]
    requests.post(f"{V1}/tprm/integrations/{iid}/stages/{na_stage}", headers=h,
                 json={"status": "not_applicable", "evidence_notes": "pytest justification"}, timeout=30)
    for s in stages[1:]:
        _set_stage(h, iid, s["stage_id"], "pass")

    r = requests.post(f"{V1}/tprm/integrations/{iid}/approve", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    sm = requests.get(f"{V1}/tprm/integrations/{iid}/summary", headers=h, timeout=30).json()
    assert sm["completed_stages"] == sm["total_stages"], "N/A stage should count as completed"


def test_tprm_not_applicable_audited():
    h = _headers("admin")
    integ = _create_integration(h)
    iid = integ["id"]
    stages = _stages(h, iid)
    target = stages[0]["stage_id"]

    r = requests.post(f"{V1}/tprm/integrations/{iid}/stages/{target}", headers=h,
                      json={"status": "not_applicable", "evidence_notes": "pytest audit probe"}, timeout=30)
    assert r.status_code == 200, r.text

    events = requests.get(f"{V1}/admin/audit/security", headers=h,
                          params={"event_type": "TPRM_STAGE_NOT_APPLICABLE", "limit": 20}, timeout=30)
    assert events.status_code == 200, events.text
    matches = [e for e in events.json() if iid in (e.get("detail") or "")]
    assert matches, f"expected a TPRM_STAGE_NOT_APPLICABLE event referencing integration {iid}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
