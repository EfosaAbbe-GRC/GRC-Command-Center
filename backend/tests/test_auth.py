"""
GRC Command Center — Auth & RBAC Enforcement Tests
Run with: python tests/test_auth.py
Requires: backend running on localhost:8001 (python main.py)
"""
import requests
import json
import sys

BASE = "http://localhost:8001"
V1 = f"{BASE}/api/v1"
PASS = 0
FAIL = 0
ERRORS = []

# --- Test User Registry (Must match .env / core/auth.py) ---
USERS = {
    "admin": {"user": "admin", "pass": "grc-admin-2026", "role": "admin"},
    "analyst": {"user": "analyst", "pass": "grc-analyst-2026", "role": "analyst"},
    "viewer": {"user": "viewer", "pass": "grc-viewer-2026", "role": "viewer"},
}

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        msg = f"FAIL {name} — {detail}"
        print(f"  ❌ {msg}")
        ERRORS.append(msg)

def get_tokens(username, password):
    """Login and get a valid token pair for a specific user."""
    try:
        r = requests.post(f"{V1}/auth/login", json={"username": username, "password": password}, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get("access_token"), data.get("refresh_token")
    except:
        pass
    return None, None

def run_rbac_tests():
    global PASS, FAIL

    print("\n" + "=" * 60)
    print("  GRC COMMAND CENTER — RBAC ENFORCEMENT TESTS (+ SESSION LIFESTYLE)")
    print("=" * 60)

    # 1. Public Routes
    print("\n── PUBLIC ROUTES (no token) ──")
    r = requests.get(f"{V1}/health", timeout=30)
    check("Health check is public", r.status_code == 200)

    # 2. Login Logic
    print("\n── USER AUTHENTICATION ──")
    for role, creds in USERS.items():
        access, refresh = get_tokens(creds["user"], creds["pass"])
        check(f"Login as {role} successful", access is not None and refresh is not None)

    # 3. Phase 3: Token Lifecycle & Rotation
    print("\n── SESSION LIFESTYLE (Phase 3) ──")
    # A. Rotation Test
    access_1, refresh_1 = get_tokens(USERS["admin"]["user"], USERS["admin"]["pass"])
    r_refresh = requests.post(f"{V1}/auth/refresh", json={"refresh_token": refresh_1}, timeout=30)
    check("Refresh token rotation successful", r_refresh.status_code == 200)
    
    if r_refresh.status_code == 200:
        access_2 = r_refresh.json().get("access_token")
        refresh_2 = r_refresh.json().get("refresh_token")
        check("Access token updated after refresh", access_1 != access_2)
        check("Refresh token rotated (issued new JTI)", refresh_1 != refresh_2)

        # B. One-Time-Use (Reuse prevention)
        r_reuse = requests.post(f"{V1}/auth/refresh", json={"refresh_token": refresh_1}, timeout=30)
        check("Reuse of old refresh token BLOCKED (401)", r_reuse.status_code == 401)
        
        # C. Logout (Revocation)
        r_logout = requests.post(f"{V1}/auth/logout", json={"refresh_token": refresh_2}, timeout=30)
        check("Logout successful (Status 200)", r_logout.status_code == 200)
        
        r_refresh_after_logout = requests.post(f"{V1}/auth/refresh", json={"refresh_token": refresh_2}, timeout=30)
        check("Refresh after logout BLOCKED (401)", r_refresh_after_logout.status_code == 401)

    # 4. RBAC Boundary: Viewer (Least Privilege)
    print("\n── ROLE BOUNDARY: VIEWER ──")
    v_token, _ = get_tokens(USERS["viewer"]["user"], USERS["viewer"]["pass"])
    v_headers = {"Authorization": f"Bearer {v_token}"}

    r1 = requests.get(f"{V1}/compliance/policies", headers=v_headers, timeout=30)
    check("Viewer can READ policies", r1.status_code == 200)

    r2 = requests.post(f"{V1}/chat", headers=v_headers, json={"query": "test"}, timeout=30)
    check("Viewer DENIED chat access (403)", r2.status_code == 403)

    r3 = requests.post(f"{V1}/run-agent", headers=v_headers, json={"agent_name": "test"}, timeout=30)
    check("Viewer DENIED agent execution (403)", r3.status_code == 403)

    # 5. RBAC Boundary: Analyst (Medium Privilege)
    print("\n── ROLE BOUNDARY: ANALYST ──")
    a_token, _ = get_tokens(USERS["analyst"]["user"], USERS["analyst"]["pass"])
    a_headers = {"Authorization": f"Bearer {a_token}"}

    r4 = requests.post(f"{V1}/chat", headers=a_headers, json={"query": "test"}, timeout=30)
    check("Analyst can ACCESS chat", r4.status_code == 200)

    r5 = requests.get(f"{V1}/compliance/export", headers=a_headers, timeout=30)
    check("Analyst can EXPORT compliance CSV", r5.status_code == 200)

    r6 = requests.post(f"{V1}/ingest", headers=a_headers, timeout=30)
    check("Analyst DENIED ingestion (403)", r6.status_code == 403)

    # 6. RBAC Boundary: Admin (Full Privilege)
    print("\n── ROLE BOUNDARY: ADMIN ──")
    adm_token, _ = get_tokens(USERS["admin"]["user"], USERS["admin"]["pass"])
    adm_headers = {"Authorization": f"Bearer {adm_token}"}

    r7 = requests.post(f"{V1}/ingest/notes", headers=adm_headers, timeout=30)
    check("Admin can TRIGGER notebook ingestion", r7.status_code == 200)

    r8 = requests.get(f"{V1}/knowledge/evidence", headers=adm_headers, timeout=30)
    check("Admin can VIEW evidence records", r8.status_code == 200)

    # 7. Invalid/Expired Token
    print("\n── SECURITY ROBUSTNESS ──")
    bad_headers = {"Authorization": "Bearer not.a.real.token"}
    r9 = requests.get(f"{V1}/compliance/policies", headers=bad_headers, timeout=30)
    check("Invalid token rejected (401)", r9.status_code == 401, f"Got {r9.status_code}")

    # REPORT
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  RESULTS: {PASS}/{total} passed, {FAIL} failed")
    print("=" * 60)

    if FAIL == 0:
        print("\n  🔒 ALL RBAC & SESSION TESTS PASSED — System is production-hardened!")
    else:
        print("\n  🚨 Violations detected. Session rotation or RBAC failing.")

    return FAIL == 0

if __name__ == "__main__":
    success = run_rbac_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    success = run_rbac_tests()
    sys.exit(0 if success else 1)
