import requests
import time

try:
    print("Triggering Ingestion...")
    response = requests.post("http://localhost:8000/api/ingest")
    print("Status:", response.status_code)
    print("Response:", response.json())
except Exception as e:
    print("Error:", e)
