import requests
import sqlite3
import time
import os

# 1. Trigger Hallucination Test
url = "http://localhost:8001/api/v1/chat"
payload = {"query": "What is the specific policy regarding using a golden dragon as a company mascot?"}
print(f"Sending query: {payload['query']}")

response = requests.post(url, json=payload)
data = response.json()

print("\nResponse Received:")
print(f"Status: {response.status_code}")
print(f"Answer: {data.get('response')}")

# 2. Verify Audit Log
print("\nWaiting for background task to complete (2s)...")
time.sleep(2)

db_path = "backend/data/grc_audit.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
row = cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
conn.close()

if row:
    print("\n[SUCCESS] Audit Log Found:")
    print(f"ID: {row[0]}")
    print(f"Request ID: {row[1]}")
    print(f"Timestamp: {row[2]}")
    print(f"Query: {row[3]}")
    print(f"Response: {row[4][:50]}...")
    print(f"Context Length: {len(row[5])}")
    print(f"Sources: {row[6]}")
else:
    print("\n[ERROR] No audit log row found in database.")
