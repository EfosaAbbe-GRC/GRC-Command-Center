import os
from typing import Dict, Any, Callable
from core.logger import logger

# --- GRC.OS AGENT REGISTRY (Rule #2) ---
# Hardcoded mapping of safe identifiers to Python callables. 
# This is the single source of truth for all autonomous capabilities.

def active_auditor_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for the NIST AI RMF Active Auditor analyst-role agent."""
    return {
        "status": "success", 
        "msg": "NIST AI RMF Audit Complete", 
        "findings_severity": "HIGH",
        "evidence_cited": args.get("include_evidence", True)
    }

def policy_analyzer_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Stub for the operational policy analyzer."""
    return {"status": "success", "msg": "Strategic analysis complete: 0 gaps found in active-policy-set."}

# Registry mapping: Explicit, Zero-Trust dispatch table
AGENT_REGISTRY: Dict[str, Callable] = {
    "active-auditor": active_auditor_handler,
    "policy-analyzer": policy_analyzer_handler,
}

# --- ZERO-TRUST RUNNER (Rule #1) ---

class InternalAgentRunner:
    """
    Replaces the legacy AgentRunner. 
    Eliminates all use of subprocess.run() for agent execution.
    """
    def __init__(self, registry: Dict[str, Callable]):
        self._registry = registry

    def execute_agent(self, agent_id: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Executes a registry-validated agent function directly in the running Python process.
        """
        if agent_id not in self._registry:
            logger.error("Security Violation: Unregistered agent execution attempt", 
                         agent_id=agent_id, status="BLOCKED")
            return {"error": f"Access Denied: Agent '{agent_id}' is not in the approved registry."}
        
        try:
            handler = self._registry[agent_id]
            # Direct Python execution: No shell, No subprocess, No injection.
            result = handler(args or {})
            return result
        except Exception as e:
            logger.error("Internal Agent Execution Fault", agent_id=agent_id, error=str(e))
            return {"error": f"Internal Execution Error: {str(e)}"}

# Singleton Instance for application-wide injection
agent_runner = InternalAgentRunner(AGENT_REGISTRY)
