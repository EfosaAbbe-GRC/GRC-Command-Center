import os
from typing import Dict, Any, Callable, Awaitable
from core.logger import logger
from core.rag import rag_engine
from core.database import audit_logger

# --- GRC.OS AGENT REGISTRY (Rule #2) ---
# Hardcoded mapping of safe identifiers to Python callables.
# This is the single source of truth for all autonomous capabilities.

NIST_AI_RMF_AUDIT_QUESTIONS = [
    "What are the four core functions of the NIST AI Risk Management Framework?",
    "What does the NIST AI RMF recommend for governance and accountability of AI systems?",
    "What does the NIST AI RMF say about mapping and categorizing AI risk?",
    "What does the NIST AI RMF recommend for measuring and monitoring AI system risk?",
]

# Every non-answer `rag_engine.query()` can return. These are engine/infrastructure
# failures, NOT audit outcomes -- an auditor must not draw a conclusion from them.
# Kept in sync with core/rag.py's query() error returns.
_ENGINE_FAILURE_MARKERS = (
    "i encountered an error processing your request",   # generic exception path
    "security alert: knowledge base integrity check failed",
    "error loading index:",
    "rag engine not initialized",
)


def _is_engine_failure(answer: str) -> bool:
    if not answer or not answer.strip():
        return True
    low = answer.lower()
    return any(m in low for m in _ENGINE_FAILURE_MARKERS)


async def active_auditor_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """NIST AI RMF Active Auditor: runs a fixed set of canonical NIST AI RMF
    questions through the real RAG pipeline (the same engine behind /chat,
    measured at 92% accuracy on the 50-query benchmark) and aggregates real,
    source-cited findings. Severity reflects corpus coverage: an audit that
    can't substantiate a core RMF function from the ingested corpus is
    itself a real finding, not a canned one."""
    findings = []
    all_sources = set()
    unanswered = 0
    errored = 0
    for question in NIST_AI_RMF_AUDIT_QUESTIONS:
        result = await rag_engine.query(question)
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        all_sources.update(sources)
        if _is_engine_failure(answer):
            errored += 1
        elif "INSUFFICIENT_DATA" in answer:
            unanswered += 1
        findings.append({"question": question, "answer": answer, "sources": sources})

    total = len(NIST_AI_RMF_AUDIT_QUESTIONS)

    # An engine failure is NOT an audit finding, and must never be reported as one.
    # Before 2026-08-17 an errored answer fell through to the `unanswered == 0` branch,
    # so a dead LLM produced "4/4 core functions substantiated from corpus, severity
    # LOW" -- a favourable audit opinion backed by nothing. Verified live against the
    # retired Groq model. See RAG_Model_Outage_refactor.md.
    if errored:
        logger.error("active-auditor aborted: RAG engine failure",
                     errored=errored, total=total)
        return {
            "status": "error",
            "msg": (f"NIST AI RMF Audit could not run — the RAG engine failed on "
                    f"{errored}/{total} queries. No audit conclusion is available. "
                    f"Check GET /api/v1/readiness (is the configured LLM model still "
                    f"available?) before trusting any result from this agent."),
            "engine_failures": errored,
            "evidence_cited": False,
            "sources": sorted(all_sources),
            "findings": findings,
        }

    if unanswered == 0:
        severity = "LOW"
    elif unanswered < total / 2:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    return {
        "status": "success",
        "msg": f"NIST AI RMF Audit Complete — {total - unanswered}/{total} core functions substantiated from corpus",
        "findings_severity": severity,
        "evidence_cited": len(all_sources) > 0,
        "sources": sorted(all_sources),
        "findings": findings,
    }

async def policy_analyzer_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    """Policy gap analysis: inspects the real RBAC Policy table (the
    platform's own access-control capabilities) for governance gaps --
    missing framework citations and disabled capabilities -- instead of
    returning a canned "0 gaps found"."""
    policies = audit_logger.list_policies()
    total = len(policies)
    missing_source_doc = [p["name"] for p in policies if not p.get("source_doc")]
    inactive = [p["name"] for p in policies if not p.get("is_active")]
    gap_count = len(missing_source_doc) + len(inactive)

    return {
        "status": "success",
        "msg": f"Strategic analysis complete: {gap_count} gap(s) found across {total} active-policy-set entries",
        "total_policies": total,
        "missing_source_doc": missing_source_doc,
        "inactive_policies": inactive,
    }

# Registry mapping: Explicit, Zero-Trust dispatch table
AGENT_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
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

    async def execute_agent(self, agent_id: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
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
            result = await handler(args or {})
            return result
        except Exception as e:
            logger.error("Internal Agent Execution Fault", agent_id=agent_id, error=str(e))
            return {"error": f"Internal Execution Error: {str(e)}"}

    def get_approved_agents(self) -> list:
        """Returns the list of currently registered zero-trust agent identifiers."""
        return list(self._registry.keys())

# Singleton Instance for application-wide injection
agent_runner = InternalAgentRunner(AGENT_REGISTRY)
