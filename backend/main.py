from fastapi import FastAPI, BackgroundTasks, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
import uuid
import csv
import io
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
    create_refresh_token, 
    rotate_refresh_token, 
    revoke_session, 
    log_security_event
)
from core.ws import manager
from schemas import (
    StatusResponse, GRCQuery, ChatResponse, PolicyItem, 
    JobItem, ExecutiveStats, NotebookItem, AgentResult, HealthResponse,
    LoginRequest, TokenResponse, TokenRefreshRequest, DocumentItem, DashboardStats,
    FrameworkMappingResponse, EvidenceRecord, IngestionStatus, ReadinessResponse,
    ChangePasswordRequest, PolicyModel, PolicyUpdate, AgentRequest
)

@asynccontextmanager
async def lifespan(app):
    logger.info("System startup", version=settings.VERSION, mode="PRODUCTION_READY")
    
    # Seed user registry (Phase 2 Hardening)
    if not audit_logger.get_user_by_username(settings.ADMIN_USERNAME):
        logger.info("Security: Seeding initial user registry from secrets/.env", user=settings.ADMIN_USERNAME)
        audit_logger.create_user(
            settings.ADMIN_USERNAME, 
            get_password_hash(settings.ADMIN_PASSWORD), 
            "admin"
        )
        audit_logger.create_user(
            settings.ANALYST_USERNAME, 
            get_password_hash(settings.ANALYST_PASSWORD), 
            "analyst"
        )
        audit_logger.create_user(
            settings.VIEWER_USERNAME, 
            get_password_hash(settings.VIEWER_PASSWORD), 
            "viewer"
        )

    # Seed Strategic Policy Engine (IAM-09) — runs after DB is guaranteed initialized
    _seed_initial_policies()

    yield
    logger.info("System shutdown")

# Strategic Policy Engine seed — called from inside lifespan() only
def _seed_initial_policies():
    """Establish the baseline Strategic Policy Engine configuration (IAM-09)."""
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
    ]
    for name, desc, role in policies:
        if not audit_logger.get_policy(name):
            logger.info("Policy Engine: Seeding baseline policy", name=name, role=role)
            audit_logger.create_policy(name, desc, role, "system")

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
        "engine": "Gemini Pro"
    }

@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """Detailed system health check with subsystem visibility."""
    checks = {
        "api": "healthy",
        "rag": "healthy" if rag_engine.api_key else "degraded",
        "agent_registry": "healthy" if len(agent_runner.approved_agents) > 0 else "error",
        "database": "healthy" if os.path.exists(audit_logger.db_path) else "degraded",
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
    background_tasks.add_task(rag_engine.process_documents, settings.DOCUMENTS_PATH)
    
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
    import sqlite3
    checks = {}

    # 1. Database
    try:
        db_path = audit_logger.db_path
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.execute("SELECT 1 FROM audit_logs LIMIT 1")
            checks["database"] = {"status": "ready", "detail": f"SQLite OK ({db_path})"}
        else:
            checks["database"] = {"status": "not_ready", "detail": "Database file not found"}
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
        checks["llm_api_key"] = {"status": "ready", "detail": "Google API key configured"}
    else:
        checks["llm_api_key"] = {"status": "not_ready", "detail": "GOOGLE_API_KEY missing"}

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

@app.post("/api/v1/run-agent", response_model=AgentResult, dependencies=[Depends(authorize("AGENT_EXECUTE"))])
@limiter.limit("10/minute")
async def run_agent_endpoint(request: Request, payload: AgentRequest):
    user = get_current_user(request)
    logger.info("Registry Agent execution requested", agent=payload.agent_id, user=user["username"])
    
    # Internal execution via the Zero-Trust Registry
    result = agent_runner.execute_agent(payload.agent_id, payload.args)
    
    status = "success" if "error" not in result else "failed"
    return AgentResult(
        status=status,
        agent=payload.agent_id,
        result=result
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
    return data_service.get_ops_jobs()

# --- EXECUTIVE ENDPOINTS ---

@app.get("/api/v1/executive/stats", response_model=ExecutiveStats, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_executive_stats():
    return data_service.get_executive_stats()

@app.get("/api/v1/executive/dashboard", response_model=DashboardStats, dependencies=[Depends(authorize("RAG_QUERY"))])
def get_dashboard_stats():
    return data_service.get_dashboard_stats()

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
