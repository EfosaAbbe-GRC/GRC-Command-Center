import requests
import time
import os

BASE_URL = "http://localhost:8001/api/v1"

def test_iam_05():
    print("--- 🧪 PHASE 5 SECURITY TEST: IAM-05 ---")
    
    # 1. Login to get token
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "admin", "password": "grc-admin-2026"}
    resp = requests.post(login_url, json=login_data)
    assert resp.status_code == 200, f"Initial Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = data["access_token"]
    refresh_token = data["refresh_token"]
    assert "must_change_password" in data, "must_change_password missing from response"
    print("✅ Initial login successful & contains mcp flag")

    # 2. Force reset as admin
    reset_url = f"{BASE_URL}/admin/users/1/reset-password"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(reset_url, headers=headers)
    assert resp.status_code == 200, "Admin reset failed"
    print("✅ Admin forced password reset on user 1")

    # 3. Login again to get MCP=True token
    resp = requests.post(login_url, json=login_data)
    data = resp.json()
    assert data["must_change_password"] is True, "User not marked for reset after admin action"
    mcp_token = data["access_token"]
    print("✅ User now in forced-reset state (MCP=True)")

    # 4. Verify gating: Should NOT be able to call /chat
    chat_url = f"{BASE_URL}/chat"
    headers = {"Authorization": f"Bearer {mcp_token}"}
    resp = requests.post(chat_url, headers=headers, json={"query": "test"})
    assert resp.status_code == 403, "Gating FAILED: User allowed to chat during forced reset"
    assert resp.json().get("code") == "PASSWORD_RESET_REQUIRED"
    print("✅ Gating ACTIVE: Non-essential requests blocked")

    # 5. Verify essential paths: Should be able to call /auth/me
    me_url = f"{BASE_URL}/auth/me"
    resp = requests.get(me_url, headers=headers)
    assert resp.status_code == 200, "Essential path /auth/me blocked"
    print("✅ Bypass ACTIVE: Essential path /auth/me accessible")

    # 6. Change password to clear flag
    change_url = f"{BASE_URL}/auth/change-password"
    change_data = {
        "old_password": "grc-admin-2026",
        "new_password": "grc-admin-new-2026"
    }
    resp = requests.post(change_url, headers=headers, json=change_data)
    assert resp.status_code == 200, "Password change failed"
    print("✅ User successfully updated password")

    # 7. Verify flag cleared (login again)
    login_data_new = {"username": "admin", "password": "grc-admin-new-2026"}
    resp = requests.post(login_url, json=login_data_new)
    data = resp.json()
    assert data["must_change_password"] is False, "Flag not cleared after password change"
    print("✅ Password lifecycle cycle COMPLETE")

if __name__ == "__main__":
    test_iam_05()
