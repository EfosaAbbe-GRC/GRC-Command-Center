import sys
import os
import asyncio

# Add backend directory to path so we can import core modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.agent import agent_runner
from core.logger import logger

async def run_security_audit():
    logger.info("AUDIT: Starting AgentRunner Security Stress Test")
    
    test_cases = [
        {
            "name": "Approved Agent (Compliance)",
            "agent": "compliance_checker",
            "expected_success": True
        },
        {
            "name": "Unauthorized Agent (Hack)",
            "agent": "malicious_script",
            "expected_success": False
        },
        {
            "name": "Directory Traversal Attempt",
            "agent": "../main",
            "expected_success": False
        },
        {
            "name": "Empty Agent Name",
            "agent": "",
            "expected_success": False
        }
    ]
    
    audit_results = []
    
    for case in test_cases:
        logger.info(f"AUDIT RUN: Testing {case['name']}...")
        result = await agent_runner.execute_agent(case['agent'])
        
        actual_success = "error" not in result
        
        if actual_success == case['expected_success']:
            status = "PASS ✅"
        else:
            status = "FAIL ❌"
            
        audit_results.append({
            "test": case['name'],
            "status": status,
            "details": str(result.get("error", "Execution Started"))[:50]
        })
        
    print("\n" + "="*50)
    print("AGENTRUNNER SECURITY AUDIT REPORT")
    print("="*50)
    for res in audit_results:
        print(f"[{res['status']}] {res['test']}: {res['details']}")
    print("="*50 + "\n")

if __name__ == "__main__":
    # Ensure dummy scripts exist for testing
    agents_path = os.path.join(os.path.dirname(__file__), "..", "agents")
    if not os.path.exists(agents_path):
        os.makedirs(agents_path)
    
    dummy_script = os.path.join(agents_path, "compliance_checker.py")
    if not os.path.exists(dummy_script):
        with open(dummy_script, "w") as f:
            f.write("print('Compliance Check: SUCCESS')")
            
    asyncio.run(run_security_audit())
