from fastapi import FastAPI, BackgroundTasks, Request, Response, HTTPException, Depends, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import uuid
import csv
import io
import json
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Import core modules
from core.config import settings
from core.logger import logger, request_id_var
from core.rag import rag_engine
from core.agent import agent_runner
from core.database import audit_logger
from data_service import data_service
from notebook_service import notebook_service
from core.auth import (
    authenticate_user, 
    create_access_token, 
    authorize, 
    get_current_user, 
    verify_token,
    AuthMiddleware,
    get_password_hash, 
    verify_password,
    create_refresh_token, 
    rotate_refresh_token, 
    revoke_session, 
    log_security_event
)
from core.ws import manager
from core.tprm import router as tprm_router   # also registers TPRM models on Base.metadata
from schemas import (
    StatusResponse, GRCQuery, ChatResponse, PolicyItem, 
    JobItem, ExecutiveStats, NotebookItem, AgentResult, HealthResponse,
    LoginRequest, TokenResponse, TokenRefreshRequest, DocumentItem, DashboardStats,
    FrameworkMappingResponse, EvidenceRecord, IngestionStatus, ReadinessResponse,
    ChangePasswordRequest, PolicyModel, PolicyUpdate, AgentRunRequest
)

@asynccontextmanager
async def lifespan(app):
    logger.info("System startup", version=settings.VERSION, mode="POSTGRES_V2")
    
    # Initialize PostgreSQL schema + SECURITY DEFINER triggers
    await audit_logger.init_db()
    
    # Seed user registry (Phase 2 Hardening) — use async methods directly
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from core.models import User as UserModel, Policy as PolicyModel
        
        # Seed each user independently — prevents partial-seed gaps from prior boots
        for uname, upass, urole in [
            (settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD, "admin"),
            (settings.ANALYST_USERNAME, settings.ANALYST_PASSWORD, "analyst"),
            (settings.VIEWER_USERNAME, settings.VIEWER_PASSWORD, "viewer"),
        ]:
            result = await session.execute(select(UserModel).where(UserModel.username == uname))
            if not result.scalar_one_or_none():
                logger.info("Security: Seeding user", user=uname, role=urole)
                session.add(UserModel(username=uname, hashed_password=get_password_hash(upass), role=urole))
        await session.commit()

        # Seed Strategic Policy Engine (IAM-09)
        policies = [
            ("AUDIT_VIEW",      "Review the security identity audit trail",          "admin"),
            ("INGEST_CONTROL",  "Trigger global database and document ingestion",     "admin"),
            ("AGENT_EXECUTE",   "Trigger autonomous AI agent execution",              "admin"),
            ("RAG_QUERY",       "Interact with the RAG Co-Pilot system",             "analyst"),
            ("EVIDENCE_VIEW",   "View the chain-of-custody evidence records",        "admin"),
            ("EVIDENCE_EXPORT", "Export and download compliance audit evidence",      "admin"),
            ("NOTEBOOK_SYNC",   "Synchronize analyst notebooks with the RAG core",   "admin"),
            ("SYSTEM_REPORTS",  "Generate and export compliance reports",            "analyst"),
            ("USER_MANAGEMENT", "Administratively manage system users",              "admin"),
            ("SYSTEM_AUDIT",    "Access high-level security audit logs",             "admin"),
            ("TPRM_VIEW",       "View third-party risk assessments",                 "analyst"),
            ("TPRM_ASSESS",     "Create/score integrations and submit stages",       "analyst"),
            ("TPRM_SIGNOFF",    "Sign risk acceptances and approve integrations",    "admin"),
        ]
        for name, desc, role in policies:
            result = await session.execute(select(PolicyModel).where(PolicyModel.name == name))
            if not result.scalar_one_or_none():
                logger.info("Policy Engine: Seeding baseline policy", name=name, role=role)
                session.add(PolicyModel(name=name, description=desc, required_role=role, created_by="system"))
        await session.commit()

    # Seed TPRM assessment stages (idempotent reference data) — same convention
    # as the user/policy seeding above, so no manual `docker exec ... seed` step
    # is required, even on a fresh DB volume. data/seed_tprm_stages.py remains the
    # single source of truth and is still runnable standalone for CI/manual use.
    try:
        from data.seed_tprm_stages import seed as seed_tprm_stages
        await seed_tprm_stages()
    except Exception as e:
        logger.error("TPRM stage seeding failed at startup", error=str(e))

    yield
    # Dispose engine connections on shutdown
    from core.database import engine as db_engine
    await db_engine.dispose()
    logger.info("System shutdown")

# Rate Limiter Setup
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Correlation ID Middleware
class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(CorrelationMiddleware)
app.add_middleware(AuthMiddleware)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS, 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- TPRM MODULE ROUTER ---
app.include_router(tprm_router, prefix="/api/v1/tprm", tags=["tprm"])

# --- WEBSOCKET STREAM ---

@app.websocket("/api/v1/stream")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """
    Real-time telemetry stream for analyst terminals.
    Validates IAM-10 credentials during handshake.
    """
    if not token or not verify_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            # Main data flow is outbound (broadcast); keep connection open
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)

# --- BASE ENDPOINTS ---

@app.get("/", response_model=StatusResponse)
def read_root():
    return {
        "status": "active",
        "system": "Agentic GRC Orchestrator v1.0",
        "engine": "Groq (Llama 3.3 70B)"
    }

@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """Detailed system health check with subsystem visibility."""
    # Probe PostgreSQL connectivity
    db_status = "healthy"
    try:
        from core.database import _run_async, AsyncSessionLocal
        from sqlalchemy import text as sa_text
        async def _probe():
            async with AsyncSessionLocal() as session:
                await session.execute(sa_text("SELECT 1"))
        _run_async(_probe())
    except Exception:
        db_status = "degraded"

    checks = {
        "api": "healthy",
        "rag": "healthy" if rag_engine.api_key else "degraded",
        "agent_registry": "healthy" if len(agent_runner.get_approved_agents()) > 0 else "error",
        "database": db_status,
        "faiss_index": "healthy" if os.path.exists("faiss_index") else "not_indexed",
        "auth": "enforced" if settings.AUTH_ENABLED else "disabled",
        "ingestion": rag_engine.ingestion_state.status,
    }
    status = "healthy" if all(v in ("healthy", "enforced", "idle", "completed") for v in checks.values()) else "degraded"
    return {
        "status": status,
        "checks": checks,
        "request_id": request_id_var.get()
    }

@app.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request):
    """
    Token-based auth using the centralized user registry.
    Phase 3: Returns both a short-lived access token and a rotating refresh token.
    """
    
    user = authenticate_user(payload.username, payload.password)
    if user:
        access_token = create_access_token(data={
            "sub": user["username"], 
            "role": user["role"],
            "mcp": user.get("must_change_password", False)
        })
        refresh_token = create_refresh_token(user_id=user["id"])
        
        log_security_event(request, "LOGIN_SUCCESS", f"Authentication successful for user '{user['username']}'", user_override=user['username'])
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            must_change_password=user.get("must_change_password", False)
        )
    
    log_security_event(request, "LOGIN_FAIL", f"Failed authentication attempt for user '{payload.username}'", user_override=payload.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
async def refresh_token(payload: TokenRefreshRequest, request: Request):
    """
    Renews session tokens using rotation.
    Invalidates the old refresh token and issues a fresh pair.
    """
    new_tokens = rotate_refresh_token(payload.refresh_token)
    if not new_tokens:
        log_security_event(request, "REFRESH_FAIL", "Refresh token rotation failed or token revoked")
        raise HTTPException(status_code=401, detail="Invalid session or revoked token")
        
    log_security_event(request, "REFRESH_ROTATE", f"Session extension via token rotation")
    return TokenResponse(**new_tokens)

@app.post("/api/v1/auth/logout", response_model=StatusResponse)
async def logout(payload: TokenRefreshRequest, request: Request):
    """
    Invalidates the provided refresh token to end the session.
    """
    success = revoke_session(payload.refresh_token)
    if success:
        log_security_event(request, "LOGOUT", "Proactive session termination")
        return StatusResponse(status="success", message="Session revoked")
    raise HTTPException(status_code=400, detail="Invalid token or already revoked")

@app.get("/api/v1/auth/me", response_model=Dict[str, Any])
async def get_me(request: Request):
    """Identity discovery endpoint for the frontend."""
    return {
        "username": request.state.user,
        "role": request.state.user_role,
        "must_change_password": request.state.must_change_password
    }

@app.post("/api/v1/auth/change-password", response_model=StatusResponse)
async def change_password(request: Request, payload: ChangePasswordRequest):
    """Self-service password rotation with old-password verification."""
    username = request.state.user
    user = audit_logger.get_user_by_username(username)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not verify_password(payload.old_password, user["hashed_password"]):
        logger.warn("Security: Password change failed - old password incorrect", user=username)
        raise HTTPException(status_code=400, detail="Incorrect old password")
        
    new_hashed = get_password_hash(payload.new_password)
    if audit_logger.update_password(user["id"], new_hashed):
        log_security_event(request, "PASSWORD_CHANGE", "Self-service credential rotation successful")
        return StatusResponse(status="success", message="Password updated successfully. Please re-login if session persists.")
        
    raise HTTPException(status_code=500, detail="Database update failed")

@app.post("/api/v1/admin/users/{user_id}/reset-password", response_model=StatusResponse, dependencies=[Depends(authorize("USER_MANAGEMENT"))])
async def admin_reset_password(user_id: int, request: Request):
    """Administrative override to force a password change on next login."""
    if audit_logger.set_must_change_password(user_id, True):
        log_security_event(request, "PASSWORD_RESET", f"Administrative forced reset on user_id={user_id}")
        return StatusResponse(status="success", message="User marked for mandatory password reset.")
    raise HTTPException(status_code=404, detail="User not found")

@app.get("/api/v1/admin/audit/security", response_model=List[Dict[str, Any]], dependencies=[Depends(authorize("SYSTEM_AUDIT"))])
async def get_security_audit(
    request: Request,
    limit: int = 50, 
    offset: int = 0, 
    event_type: Optional[str] = None, 
    user: Optional[str] = None
):
    """Exposes the security identity audit trail for administrative review."""
    return audit_logger.get_security_events(limit=limit, offset=offset, event_type=event_type, user=user)

@app.get("/api/v1/admin/policies", response_model=List[PolicyModel], dependencies=[Depends(authorize("SYSTEM_AUDIT"))])
async def list_policies(request: Request):
    """Retrieve the full dynamic access policy registry for management."""
    return audit_logger.list_policies()

class PolicyUpdateRequest(BaseModel):
    required_role: str
    is_active: bool
    source_doc: Optional[str] = None

@app.put("/api/v1/admin/policies/{policy_id}", response_model=StatusResponse, dependencies=[Depends(authorize("SYSTEM_AUDIT"))])
async def update_policy(policy_id: int, payload: PolicyUpdateRequest, request: Request):
    """Administratively update a system policy."""
    user = get_current_user(request)
    if audit_logger.update_policy(
        policy_id=policy_id, 
        required_role=payload.required_role, 
        is_active=payload.is_active, 
        modified_by=user["username"],
        source_doc=payload.source_doc
    ):
        log_security_event(request, "POLICY_CHANGE", f"User '{user['username']}' updated policy ID {policy_id} to role={payload.required_role} (Active={payload.is_active})")
        return StatusResponse(status="success", message="Policy updated successfully")
    raise HTTPException(status_code=400, detail="Failed to update policy")

# --- RAG ENDPOINTS ---

@app.post("/api/v1/ingest", response_model=StatusResponse, dependencies=[Depends(authorize("INGEST_CONTROL"))])
@limiter.limit("5/minute")
async def trigger_ingest(request: Request, background_tasks: BackgroundTasks):
    """Admin-only: Triggers the knowledge vault rebuild and signs the manifest."""
    background_tasks.add_task(rag_engine.initialize_index)
    
    # Live Broadcast: Signal ingestion start
    await manager.broadcast({
        "type": "INGEST_STATUS",
        "status": "STARTED",
        "message": "Vault rebuild initiated across 18,337 potential splits."
    })
    
    return {"status": "started", "message": "Knowledge ingestion initiated."}

@app.get("/api/v1/ingest/status", response_model=IngestionStatus, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_ingestion_status():
    """Real-time ingestion progress tracker."""
    return rag_engine.get_ingestion_status()

@app.get("/api/v1/readiness", response_model=ReadinessResponse)
def readiness_check():
    """Deep readiness probe for all subsystems."""
    checks = {}

    # 1. Database (PostgreSQL)
    try:
        from core.database import _run_async, AsyncSessionLocal
        from sqlalchemy import text as sa_text
        async def _probe_pg():
            async with AsyncSessionLocal() as session:
                await session.execute(sa_text("SELECT 1"))
        _run_async(_probe_pg())
        checks["database"] = {"status": "ready", "detail": "PostgreSQL 16 OK"}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    # 2. FAISS Index
    if os.path.exists("faiss_index"):
        integrity_ok = rag_engine._verify_index_hash("faiss_index")
        checks["faiss_index"] = {
            "status": "ready" if integrity_ok else "degraded",
            "detail": "Index present & verified" if integrity_ok else "Integrity check failed"
        }
    else:
        checks["faiss_index"] = {"status": "not_ready", "detail": "No index found — run ingestion"}

    # 3. API Key
    if rag_engine.api_key:
        checks["llm_api_key"] = {"status": "ready", "detail": "Groq API key configured"}
    else:
        checks["llm_api_key"] = {"status": "not_ready", "detail": "GROQ_API_KEY missing"}

    # 4. Auth
    checks["authentication"] = {
        "status": "ready" if settings.AUTH_ENABLED else "degraded",
        "detail": "JWT enforcement active" if settings.AUTH_ENABLED else "AUTH_ENABLED=False — not enforced"
    }

    # Overall
    statuses = [c["status"] for c in checks.values()]
    if all(s == "ready" for s in statuses):
        overall = "ready"
    elif any(s == "error" for s in statuses):
        overall = "error"
    else:
        overall = "degraded"

    return ReadinessResponse(overall=overall, checks=checks)

@app.post("/api/v1/chat", response_model=ChatResponse, dependencies=[Depends(authorize("RAG_QUERY"))])
async def chat_endpoint(request: Request, payload: GRCQuery, background_tasks: BackgroundTasks):
    try:
        result = await rag_engine.query(payload.query)
        
        # Log interaction in background for audit compliance
        background_tasks.add_task(
            audit_logger.log_interaction,
            request_id=request_id_var.get(),
            query=payload.query,
            response=result.get("answer"),
            context=result.get("context", ""),
            sources=result.get("sources", [])
        )

        return ChatResponse(
            response=result.get("answer", "I could not find an answer."),
            sources=result.get("sources", [])
        )
    except Exception as e:
        logger.error("Chat endpoint error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal processing error")

AGENT_TASK_LABELS = {
    "active-auditor": "NIST AI RMF Audit",
    "policy-analyzer": "Policy Gap Analysis",
}

@app.post("/api/v1/run-agent", response_model=AgentResult, dependencies=[Depends(authorize("AGENT_EXECUTE"))])
@limiter.limit("10/minute")
async def run_agent_endpoint(request: Request, payload: AgentRunRequest):
    user = get_current_user(request)
    logger.info("Registry Agent execution requested", agent=payload.agent_id, user=user["username"])

    run_id = audit_logger.create_agent_run(payload.agent_id, payload.args, user["username"])

    # Internal execution via the Zero-Trust Registry
    result = await agent_runner.execute_agent(payload.agent_id, payload.args)

    status = "success" if "error" not in result else "failed"
    final_status = "COMPLETED" if status == "success" else "FAILED"
    audit_logger.finish_agent_run(
        run_id,
        status=final_status,
        result=result if status == "success" else None,
        error=result.get("error") if status == "failed" else None,
    )

    log_security_event(
        request, "AGENT_EXECUTE",
        f"User '{user['username']}' executed agent '{payload.agent_id}' -> {final_status} (run_id={run_id})"
    )
    await manager.broadcast({"type": "JOB_STATUS"})

    return AgentResult(
        status=status,
        agent=payload.agent_id,
        result=result,
        run_id=run_id
    )

# --- COMPLIANCE ENDPOINTS ---

@app.get("/api/v1/compliance/policies", response_model=List[PolicyItem], dependencies=[Depends(authorize("RAG_QUERY"))])
def get_compliance_policies():
    """Retrieve the main compliance policy grid (Analyst-facing)."""
    return data_service.get_compliance_policies()

@app.get("/api/v1/compliance/export", dependencies=[Depends(authorize("EVIDENCE_EXPORT"))])
def export_compliance_csv():
    """Export compliance policies as a downloadable CSV file."""
    policies = data_service.get_compliance_policies()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Policy ID", "Name", "Type", "Status", "Compliance %", "Last Scan"])
    
    # Data rows
    for p in policies:
        writer.writerow([p["id"], p["name"], p["type"], p["status"], p["compliance"], p["last_scan"]])
    
    # Add framework mappings
    writer.writerow([])
    writer.writerow(["--- FRAMEWORK MAPPINGS ---"])
    writer.writerow(["Policy ID", "Framework", "Control ID", "Control Description", "Status"])
    
    all_mappings = data_service.get_framework_mappings()
    for policy_id, mapping in all_mappings.items():
        for fw in mapping.get("frameworks", []):
            writer.writerow([policy_id, fw["name"], fw["id"], fw["control"], fw["status"]])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=grc_compliance_report.csv"}
    )

@app.get("/api/v1/compliance/frameworks/{policy_id}", response_model=FrameworkMappingResponse, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_frameworks_for_policy(policy_id: str):
    frameworks = data_service.get_framework_mappings(policy_id)
    # Ensure it returns the correct structure expected by the schema
    # If get_framework_mappings returns List[FrameworkControl], we need to wrap it.
    return FrameworkMappingResponse(policy_id=policy_id, frameworks=frameworks)

# --- OPERATIONS ENDPOINTS ---

@app.get("/api/v1/ops/jobs", response_model=List[JobItem], dependencies=[Depends(authorize("RAG_QUERY"))])
def get_ops_jobs():
    runs = audit_logger.list_agent_runs()
    jobs = []
    for r in runs:
        if r.completed_at:
            elapsed = (r.completed_at - r.started_at).total_seconds()
            duration = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        else:
            duration = "—"
        jobs.append(JobItem(
            id=f"RUN_{r.id}",
            agent=r.agent_id,
            task=AGENT_TASK_LABELS.get(r.agent_id, r.agent_id),
            status=r.status,
            duration=duration,
            cpu="N/A",
            ram="N/A",
            result=json.loads(r.result_json) if r.result_json else None,
            error=r.error,
        ))
    return jobs

# --- EXECUTIVE ENDPOINTS ---

@app.get("/api/v1/executive/stats", response_model=ExecutiveStats, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_executive_stats():
    return data_service.get_executive_stats()

@app.get("/api/v1/executive/dashboard", response_model=DashboardStats, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_dashboard_stats():
    # Real metrics override the fixture values; trend_data stays fixture-backed and is
    # labelled ILLUSTRATIVE in the UI (no historical KPI storage exists to compute it).
    # See ExecutiveHonesty_refactor.md.
    return {**data_service.get_dashboard_stats(), **audit_logger.get_dashboard_metrics()}

# --- KNOWLEDGE ENDPOINTS ---

@app.get("/api/v1/notebook/structure", response_model=List[NotebookItem], dependencies=[Depends(authorize("RAG_QUERY"))])
def get_notebook_structure():
    return notebook_service.get_structure()

@app.post("/api/v1/ingest/notes", response_model=StatusResponse, dependencies=[Depends(authorize("NOTEBOOK_SYNC"))])
async def ingest_notes_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(rag_engine.ingest_notes, notebook_service.root_path)
    return {"status": "started", "message": "Notebook indexing initiated."}

@app.get("/api/v1/knowledge/documents", response_model=List[DocumentItem], dependencies=[Depends(authorize("RAG_QUERY"))])
def get_knowledge_documents():
    return data_service.get_knowledge_documents()

@app.get("/api/v1/knowledge/evidence", response_model=List[EvidenceRecord], dependencies=[Depends(authorize("EVIDENCE_VIEW"))])
def get_evidence_chain():
    return audit_logger.get_evidence_records()

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
