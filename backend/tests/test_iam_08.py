import requests
import time
import requests
import time

BASE_URL = "http://localhost:8001/api/v1"

def test_iam_08():
    print("--- 🧪 PHASE 5 SECURITY TEST: IAM-08 (RESILIENCE) ---")
    
    # 1. Login as admin
    login_url = f"{BASE_URL}/auth/login"
    login_data = {"username": "admin", "password": "grc-admin-2026"}
    resp = requests.post(login_url, json=login_data)
    assert resp.status_code == 200
    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    print("✅ Admin authenticated")

    # 2. Simulate Access Token Expiration (wait or just use refresh manually)
    # The actual server enforces expiration. In a real integration test, we wait.
    # But here, we'll verify the 'refresh' endpoint directly.
    refresh_url = f"{BASE_URL}/auth/refresh"
    resp = requests.post(refresh_url, json={"refresh_token": refresh_token})
    assert resp.status_code == 200, "Silent refresh failed"
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != refresh_token, "Refresh token was not rotated"
    print("✅ Session token manually rotated successfully")
    print("✅ Token rotation verified (IAM-08.3)")

    # 3. Simulate Revocation (Use token once, then try again - JTI replay prevention)
    # Our current backend (main.py:151) rotates on every call.
    # So the old token should now be invalid.
    resp_v4 = requests.post(refresh_url, json={"refresh_token": refresh_token})
    assert resp_v4.status_code == 401, "Replay attack protection FAILED: old refresh token still works"
    print("✅ Replay protection verified (JTI/Rotation Check)")

    # 4. Verify Logout Revocation
    login_data_v2 = {"username": "admin", "password": "grc-admin-2026"}
    resp_v2 = requests.post(login_url, json=login_data_v2)
    new_refresh = resp_v2.json()["refresh_token"]
    
    logout_url = f"{BASE_URL}/auth/logout"
    requests.post(logout_url, json={"refresh_token": new_refresh})
    print("✅ Logout called")
    
    resp_v3 = requests.post(refresh_url, json={"refresh_token": new_refresh})
    assert resp_v3.status_code == 401, "Revocation failed: logged out token still works"
    print("✅ Session revocation verified (IAM-08.5)")

    print("\n🏆 IAM-08 SESSION RESILIENCE VERIFIED")

if __name__ == "__main__":
    test_iam_08()
