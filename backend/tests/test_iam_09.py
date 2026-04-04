import requests
import json
import time

BASE_URL = "http://localhost:8001/api/v1"

def test_iam_09_policy_engine():
    print("--- IAM-09: Strategic Policy Engine Smoke Test ---")
    
    # 1. Login as Admin
    login_res = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "grc-admin-2026"})
    if login_res.status_code != 200:
        print(f"FAIL: Admin Login Error: {login_res.text}")
        return
    admin_tokens = login_res.json()
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    
    # 2. List Policies
    print("[1] Fetching active policy registry...")
    policies_res = requests.get(f"{BASE_URL}/admin/policies", headers=admin_headers)
    policies = policies_res.json()
    print(f"Found {len(policies)} active policies.")
    
    # Identify CHAT_ACCESS policy
    chat_policy = next((p for p in policies if p['name'] == 'CHAT_ACCESS'), None)
    if not chat_policy:
        print("FAIL: CHAT_ACCESS policy not found")
        return
    
    print(f"CHAT_ACCESS Current Role: {chat_policy['required_role']} (Version: {chat_policy['version']})")
    
    # 3. Test Deny by Default (Create a fake endpoint or try an unmapped one if I had one)
    # Actually, let's test disabling a policy.
    
    # 4. Login as Analyst
    print("[2] Logging in as Analyst...")
    analyst_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "analyst", "password": "grc-analyst-2026"})
    if analyst_login.status_code != 200:
        print(f"FAIL: Analyst Login Error ({analyst_login.status_code}): {analyst_login.text}")
        return
    analyst_tokens = analyst_login.json()
    analyst_headers = {"Authorization": f"Bearer {analyst_tokens['access_token']}"}
    
    # Verify Analyst can Chat (Policy default: analyst)
    print("[2] Verifying Analyst access to CHAT (Default Policy: analyst)...")
    chat_res = requests.post(f"{BASE_URL}/chat", json={"query": "test"}, headers=analyst_headers)
    if chat_res.status_code == 200:
        print("SUCCESS: Analyst can access chat.")
    else:
        print(f"FAIL: Analyst denied chat (Status: {chat_res.status_code})")
    
    # 5. Elevate CHAT_ACCESS to 'admin' only
    print("[3] Elevating CHAT_ACCESS to 'admin' only...")
    update_res = requests.put(
        f"{BASE_URL}/admin/policies/{chat_policy['id']}", 
        json={"required_role": "admin", "is_active": True},
        headers=admin_headers
    )
    if update_res.status_code == 200:
        print("SUCCESS: Policy elevated to admin.")
    else:
        print("FAIL: Failed to update policy.")
        
    # 6. Verify Analyst is now DENIED
    print("[4] Verifying Analyst is now DENIED chat...")
    chat_res = requests.post(f"{BASE_URL}/chat", json={"query": "test"}, headers=analyst_headers)
    if chat_res.status_code == 403:
        print("SUCCESS: Analyst correctly denied by dynamic policy.")
    else:
        print(f"FAIL: Analyst still has access! (Status: {chat_res.status_code})")
        
    # 7. Restore Policy
    print("[5] Restoring analyst access...")
    requests.put(
        f"{BASE_URL}/admin/policies/{chat_policy['id']}", 
        json={"required_role": "analyst", "is_active": True},
        headers=admin_headers
    )
    print("Test Complete.")

if __name__ == "__main__":
    test_iam_09_policy_engine()
