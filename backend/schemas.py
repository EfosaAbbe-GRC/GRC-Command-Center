from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None
    system: Optional[str] = None
    engine: Optional[str] = None

class GRCQuery(BaseModel):
    query: str
    context_filter: Optional[List[str]] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str]

class PolicyItem(BaseModel):
    id: str
    name: str
    status: str
    type: str
    compliance: int
    last_scan: str

class JobItem(BaseModel):
    id: str
    agent: str
    task: str
    status: str
    duration: str
    cpu: str
    ram: str

class KPIValue(BaseModel):
    value: Any
    trend: str

class BudgetInfo(BaseModel):
    spent: float
    total: float

class AlertItem(BaseModel):
    level: str
    msg: str
    time: str

class ExecutiveStats(BaseModel):
    compliance: KPIValue
    risk_score: KPIValue
    vulnerabilities: KPIValue
    audit_readiness: KPIValue
    budget: BudgetInfo
    alerts: List[AlertItem]

class NotebookItem(BaseModel):
    name: str
    type: str
    path: Optional[str] = None
    children: Optional[List['NotebookItem']] = None

class AgentResult(BaseModel):
    status: str
    agent: str
    result: Dict[str, Any]

class HealthSubsystem(BaseModel):
    status: str
    details: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    checks: Dict[str, str]
    request_id: str

class DocumentItem(BaseModel):
    id: str
    name: str
    type: str
    size: str
    indexed: str
    status: str

class FrameworkControl(BaseModel):
    id: str
    name: str
    control: str
    status: str

class FrameworkMappingResponse(BaseModel):
    policy_id: str
    frameworks: List[FrameworkControl]

class EvidenceRecord(BaseModel):
    filename: str
    file_hash: str
    file_size: int
    timestamp: str
    ingested_by: str
    status: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    must_change_password: bool = False

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TrendPoint(BaseModel):
    month: str
    score: int

class DashboardStats(BaseModel):
    open_findings: int
    policy_coverage: int
    active_users: int
    trend_data: List[TrendPoint]

class IngestionStatus(BaseModel):
    status: str
    total_files: int
    processed_files: int
    progress_pct: int
    errors: List[str]
    elapsed_seconds: float
    split_count: int

class ReadinessCheck(BaseModel):
    status: str
    detail: Optional[str] = None

class ReadinessResponse(BaseModel):
    overall: str
    checks: Dict[str, ReadinessCheck]

# --- STRATEGIC POLICY SCHEMAS (IAM-09) ---

class PolicyModel(BaseModel):
    id: int
    name: str
    description: str
    required_role: str
    is_active: bool
    version: int
    policy_version: int
    source_doc: Optional[str] = None
    created_at: str
    modified_at: str
    created_by: str
    modified_by: str

class PolicyUpdate(BaseModel):
    required_role: str
    is_active: bool

class AgentRequest(BaseModel):
    agent_name: str
    args: Optional[Dict[str, Any]] = {}
