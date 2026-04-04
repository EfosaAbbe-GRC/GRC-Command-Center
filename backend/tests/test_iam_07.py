import requests
import time
import os

BASE_URL = "http://localhost:8001/api/v1"

def test_iam_07():
    print("--- 🧪 PHASE 5 SECURITY TEST: IAM-07 (AUDIT) ---")
    
    # 1. Generate a LOGIN_FAIL event
    login_url = f"{BASE_URL}/auth/login"
    login_data_fail = {"username": "admin", "password": "WRONG_PASSWORD"}
    requests.post(login_url, json=login_data_fail)
    print("✅ Generated LOGIN_FAIL event")

    # 2. Login as admin to access audit
    login_data_admin = {"username": "admin", "password": "grc-admin-final-2026"}
    resp = requests.post(login_url, json=login_data_admin)
    assert resp.status_code == 200, "Admin login failed"
    admin_token = resp.json()["access_token"]
    print("✅ Admin authenticated")

    # 3. Access Security Audit
    audit_url = f"{BASE_URL}/admin/audit/security"
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(audit_url, headers=headers)
    assert resp.status_code == 200, f"Audit access failed: {resp.status_code}"
    events = resp.json()
    assert len(events) > 0, "No events found in audit"
    
    # Verify the fail event we just generated is at the top (or near it)
    # Note: Login fails are logged as 'anonymous' because session state isn't set yet
    found_fail = any(ev["event_type"] == "LOGIN_FAIL" and ev["user"] == "anonymous" for ev in events[:5])
    assert found_fail, f"LOGIN_FAIL event not captured correctly. Events: {events[:3]}"
    print("✅ Audit trail verified with LOGIN_FAIL (anonymous)")

    # 4. Verify Admin-Only Gating (Login as viewer)
    login_data_viewer = {"username": "viewer", "password": "grc-viewer-2026"}
    resp = requests.post(login_url, json=login_data_viewer)
    viewer_token = resp.json()["access_token"]
    
    headers_viewer = {"Authorization": f"Bearer {viewer_token}"}
    resp = requests.get(audit_url, headers=headers_viewer)
    assert resp.status_code == 403, "Gating FAILED: Viewer accessed admin audit"
    print("✅ Gating verified: Viewer denied access to audit")

    # 5. Verify Filtering by event_type
    resp = requests.get(f"{audit_url}?event_type=LOGIN_FAIL", headers=headers)
    filtered = resp.json()
    assert all(ev["event_type"] == "LOGIN_FAIL" for ev in filtered), "Filter by event_type failed"
    print(f"✅ Filter verified: found {len(filtered)} LOGIN_FAIL events")

    # 6. Verify Filtering by user
    resp = requests.get(f"{audit_url}?user=admin", headers=headers)
    filtered_user = resp.json()
    assert all("admin" in ev["user"].lower() for ev in filtered_user), "Filter by user failed"
    print(f"✅ Filter verified: found {len(filtered_user)} events for user 'admin'")

    print("\n🏆 IAM-07 SECURITY AUDIT VERIFIED")

if __name__ == "__main__":
    test_iam_07()
