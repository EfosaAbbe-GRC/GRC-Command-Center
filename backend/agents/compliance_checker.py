import time
import json
import random
import sys

def run_audit():
    print("--- GRC AGENT: AI_COMPLIANCE_AUDITOR STARTED ---")
    print("[INFO] Loading Policy Definitions: NIST AI RMF 1.0...")
    time.sleep(1)
    
    print("[INFO] Scanning Deployment Manifests...")
    time.sleep(1)
    
    print("[SCAN] Verify Model Card integrity... OK")
    print("[SCAN] Check Training Data Lineage... OK")
    time.sleep(1)
    
    print("[SCAN] Analyzing Bias Metrics (Threshold < 0.05)...")
    time.sleep(2)
    
    # Simulate finding a violation occasionally
    if random.random() > 0.7:
        print("[WARN] Bias Disparity detected in demographic group 'Age_60+'. Delta: 0.08")
        result = "WARNING"
        details = "Bias threshold exceeded in sub-group analysis."
    else:
        print("[INFO] All Fairness Metrics within acceptable range.")
        result = "PASS"
        details = "Deployment is fully compliant."

    print("[INFO] Generating Audit Report...")
    time.sleep(1)
    
    output = {
        "agent": "AI_Model_Compliance_AudITOR",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": result,
        "details": details,
        "scanned_items": 142,
        "duration": "5.2s"
    }
    
    print("--- AUDIT COMPLETE ---")
    # Print JSON at the very end for easier parsing by the runner
    print(json.dumps(output))

if __name__ == "__main__":
    run_audit()
