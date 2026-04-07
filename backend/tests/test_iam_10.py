import requests
import time

BASE_URL = "http://localhost:8001/api/v1"

def test_iam_10_agent_sync():
    print("--- IAM-10: Strategic Agent Policy Sync Smoke Test ---")
    
    # 1. Login as Admin to manage policies
    print("[1] Logging in as Admin...")
    admin_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "grc-admin-2026"})
    admin_tokens = admin_login.json()
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    
    # 2. Login as Analyst to test access
    print("[2] Logging in as Analyst...")
    analyst_login = requests.post(f"{BASE_URL}/auth/login", json={"username": "analyst", "password": "grc-analyst-2026"})
    analyst_tokens = analyst_login.json()
    analyst_headers = {"Authorization": f"Bearer {analyst_tokens['access_token']}"}

    # 3. Test RAG_QUERY (Initially Analyst)
    print("[3] Verifying Analyst access to RAG_QUERY...")
    rag_test = requests.post(f"{BASE_URL}/chat", json={"query": "test"}, headers=analyst_headers)
    if rag_test.status_code == 200:
        print("SUCCESS: Analyst authorized for RAG_QUERY.")
    else:
        print(f"FAIL: Analyst denied RAG_QUERY ({rag_test.status_code})")

    # 4. Elevate RAG_QUERY to Admin Only
    print("[4] Elevating RAG_QUERY dependency to 'admin' only...")
    policies = requests.get(f"{BASE_URL}/admin/policies", headers=admin_headers).json()
    rag_policy = next(p for p in policies if p["name"] == "RAG_QUERY")
    update_res = requests.put(f"{BASE_URL}/admin/policies/{rag_policy['id']}", 
                             json={"required_role": "admin", "is_active": True},
                             headers=admin_headers)
    
    if update_res.status_code == 200:
        print("SUCCESS: RAG_QUERY policy elevated.")
    
    # 5. Verify Analyst is now DENIED
    print("[5] Verifying Analyst is now DENIED RAG_QUERY...")
    rag_test_denied = requests.post(f"{BASE_URL}/chat", json={"query": "test"}, headers=analyst_headers)
    if rag_test_denied.status_code == 403:
        print("SUCCESS: Analyst correctly denied by dynamic policy.")
    else:
        print(f"FAIL: Analyst still has access! Status: {rag_test_denied.status_code}")

    # 6. Test AGENT_EXECUTE
    print("[6] Verifying AGENT_EXECUTE for Analyst (Default: admin)...")
    agent_test = requests.post(f"{BASE_URL}/run-agent", json={"agent_name": "compliance_checker"}, headers=analyst_headers)
    if agent_test.status_code == 403:
        print("SUCCESS: Analyst correctly denied execute (Default Policy).")
    else:
        print(f"FAIL: Analyst can execute agent! Status: {agent_test.status_code}")

    # 7. Restore RAG_QUERY for analysts
    print("[7] Restoring analyst access...")
    requests.put(f"{BASE_URL}/admin/policies/{rag_policy['id']}", 
                json={"required_role": "analyst", "is_active": True},
                headers=admin_headers)
    
    print("Test Complete.")

if __name__ == "__main__":
    test_iam_10_agent_sync()
