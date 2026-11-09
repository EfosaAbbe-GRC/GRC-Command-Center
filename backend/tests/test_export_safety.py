"""Every CSV export neutralises spreadsheet formulas in data cells (Client_Export_Hardening_refactor.md F1).

A cell starting with = + - @, tab or CR runs as a formula when the file is opened in Excel (CSV
injection). Section markers like "--- INTEGRATIONS ---" are written by the app itself and must stay
as they are (RA1). Integration: test stack (:8002) only, since it creates a vendor.
"""
import csv
import io
import os
import uuid

import pytest
import requests

from tests._creds import ADMIN_PASS

pytestmark = pytest.mark.integration

BASE = os.environ.get("GRC_TEST_BASE", "http://localhost:8002")
V1 = f"{BASE}/api/v1"
if ":8002" not in BASE:
    pytest.skip("creates a vendor: test stack (:8002) only", allow_module_level=True)

EVIL = '=HYPERLINK("http://example.invalid","click")'


@pytest.fixture(scope="module")
def admin():
    try:
        r = requests.post(f"{V1}/auth/login", json={"username": "admin", "password": ADMIN_PASS}, timeout=30)
    except requests.ConnectionError:
        pytest.skip("test stack not reachable")
    if r.status_code != 200:
        pytest.skip(f"cannot log in ({r.status_code})")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


def test_tprm_export_neutralises_formulas(admin):
    name = f"{EVIL} {uuid.uuid4().hex[:6]}"
    v = requests.post(f"{V1}/tprm/vendors", headers=admin, json={"name": name}, timeout=30)
    assert v.status_code == 200, v.text
    i = requests.post(f"{V1}/tprm/integrations", headers=admin, timeout=30, json={
        "vendor_id": v.json()["id"], "name": "-SUM(1,1)", "direction": "egress",
        "transfer_method": "file", "data_classification": "public"})
    assert i.status_code == 200, i.text
    r = requests.get(f"{V1}/tprm/export", headers=admin, timeout=60)
    assert r.status_code == 200
    rows = _rows(r.text)
    mine = [row for row in rows if row and name in row[0]]
    assert mine, "exported vendor row not found"
    assert all(row[0].startswith("'=") for row in mine), mine
    assert all(row[1] == "'-SUM(1,1)" for row in mine), mine
    data_cells = [c for row in rows if row and not row[0].startswith("---") for c in row]
    assert not any(c.startswith(("=", "+", "@")) for c in data_cells)


def test_tprm_export_section_markers_unchanged(admin):
    rows = _rows(requests.get(f"{V1}/tprm/export", headers=admin, timeout=60).text)
    markers = [row[0] for row in rows if row and row[0].lstrip("'").startswith("---")]
    assert markers == ["--- INTEGRATIONS ---", "--- STAGE ASSESSMENTS ---", "--- RISK ACCEPTANCES ---"]


def test_compliance_export_section_markers_unchanged(admin):
    r = requests.get(f"{V1}/compliance/export", headers=admin, timeout=60)
    assert r.status_code == 200
    rows = _rows(r.text)
    assert ["--- FRAMEWORK MAPPINGS ---"] in rows
    assert not any(c.startswith("'") for row in rows for c in row), "plain fixture text was altered"
