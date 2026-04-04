from datetime import datetime, timedelta
import uuid
from typing import Optional, Dict
from jose import JWTError, jwt
from fastapi import Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from core.config import settings
from core.logger import logger

# Public routes that never require auth
PUBLIC_ROUTES = {
    "/",
    "/api/v1/health",
    "/api/v1/readiness",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/docs",
    "/openapi.json",
    "/favicon.ico",
}

import bcrypt
from core.database import audit_logger

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Securely compare a plain password with its hashed version."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate a high-entropy bcrypt hash for a plain password."""
    # Bcrypt 72-byte limit handled by native encode('utf-8')
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# --- SSO AUTHENTICATOR STUB (PHASE 4) ---
# This is currently inert but provides the integration hook for OIDC/SAML.
class SSOAuthenticator:
    def __init__(self):
        self.enabled = False
    
    def authenticate(self, sso_token: str):
        if not self.enabled:
            return None
        # Future OIDC logic here
        return None

sso_auth = SSOAuthenticator()

def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Verify credentials against the persistent database-backed identity store."""
    user = audit_logger.get_user_by_username(username)
    if not user:
        return None
    
    if user.get("status") != "enabled":
        logger.warn("Security: Attempt to login to disabled account", user=username)
        return None

    if verify_password(password, user["hashed_password"]):
        # Update last login on success
        audit_logger.update_last_login(username)
        # Surface lifecycle fields
        return user
    return None

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a JWT token with user identity and role."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def create_refresh_token(user_id: int) -> str:
    """Issue a persistent refresh token stored in the database."""
    jti = str(uuid.uuid4())
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    
    # Persistent record
    if not audit_logger.create_refresh_token(jti, user_id, expire):
        raise HTTPException(status_code=500, detail="Identity store error")
        
    to_encode = {"jti": jti, "sub": str(user_id), "type": "refresh"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_refresh_token(token: str) -> Optional[dict]:
    """Validate a refresh token against the database and check revocation status."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
            
        jti = payload.get("jti")
        token_record = audit_logger.get_refresh_token(jti)
        
        if not token_record or token_record["revoked"]:
            logger.warn("Security: Attempt to use revoked or missing refresh token", jti=jti)
            return None
            
        # Check expiry
        expiry = datetime.fromisoformat(token_record["expires_at"])
        if datetime.utcnow() > expiry:
            logger.warn("Security: Refresh token expired", jti=jti)
            return None
            
        return {"jti": jti, "user_id": token_record["user_id"]}
    except JWTError:
        return None

def rotate_refresh_token(old_token: str) -> Optional[dict]:
    """Execute refresh token rotation: invalidate old JTI and issue new pair."""
    token_data = verify_refresh_token(old_token)
    if not token_data:
        return None
        
    jti = token_data["jti"]
    user_id = token_data["user_id"]
    
    # 1. Revoke the old token (One-time-use policy)
    audit_logger.revoke_refresh_token(jti)
    
    # 2. Fetch user to verify they are still enabled and get roles
    user = audit_logger.get_user_by_id(user_id)
    if not user or user.get("status") != "enabled":
        logger.warn("Security: Refresh attempt for disabled or missing user", user_id=user_id)
        return None
    
    # 3. Issue new pair
    new_access_token = create_access_token(data={
        "sub": user["username"], 
        "role": user["role"],
        "mcp": user.get("must_change_password", False)
    })
    new_refresh_token = create_refresh_token(user_id)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token
    }

def revoke_session(refresh_token: str) -> bool:
    """Explicit session termination: invalidate the provided refresh token."""
    try:
        payload = jwt.decode(refresh_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        jti = payload.get("jti")
        if jti:
            return audit_logger.revoke_refresh_token(jti)
        return False
    except JWTError:
        return False

def get_current_user(request: Request) -> dict:
    """
    Extract the authenticated user from request state.
    Returns a dict with 'username' and 'role' keys.
    """
    username = getattr(request.state, "user", "anonymous")
    role = getattr(request.state, "user_role", "viewer")
    return {"username": username, "role": role}

def log_security_event(request: Request, event_type: str, detail: str, user_override: str = None):
    """Structured security logging for core audit compliance (writes to DB)."""
    user = user_override or getattr(request.state, "user", "anonymous")
    role = getattr(request.state, "user_role", "none")
    ip_address = request.client.host if request.client else "unknown"
    
    # 1. Stdout logging
    logger.warn(
        f"Security Event: {event_type}",
        user=user,
        role=role,
        endpoint=request.url.path,
        detail=detail,
        method=request.method
    )
    
    # 2. Database persistent audit
    audit_logger.log_security_event(
        event_type=event_type,
        user=user,
        ip_address=ip_address,
        detail=detail
    )

def authorize(action_name: str):
    """
    Strategic Policy Engine (IAM-09):
    Enforces dynamic access control based on active policies in the database.
    MANDATORY: Follows DENY_BY_DEFAULT - missing or inactive policy = 403.
    """
    async def policy_checker(request: Request):
        # 1. Bypass if auth is disabled
        if not settings.AUTH_ENABLED:
            return
        
        # 2. Check if user is authenticated at all (via middleware)
        user_role = getattr(request.state, "user_role", None)
        if user_role is None:
            log_security_event(request, "FORBIDDEN", f"Unauthenticated access attempt to '{action_name}'")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # 3. Policy Lookup (IAM-09)
        # Deny by default if policy is missing or inactive
        policy = audit_logger.get_policy(action_name)
        if not policy or not policy.get("is_active"):
            log_security_event(request, "FORBIDDEN", f"Policy DENIED: No active rule for '{action_name}'")
            raise HTTPException(status_code=403, detail="Access denied: No active policy for this action")

        # 4. Role hierarchy verification
        required_role = policy["required_role"]
        role_hierarchy = {"admin": 3, "analyst": 2, "viewer": 1}
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            log_security_event(
                request, 
                "FORBIDDEN", 
                f"Policy VIOLATION: Role '{user_role}' denied '{action_name}'. Policy requires '{required_role}' (v{policy.get('version', 1)})"
            )
            raise HTTPException(status_code=403, detail="Forbidden: Insufficient privileges for this policy")
            
    return policy_checker

from fastapi.responses import JSONResponse

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Global authentication middleware.
    Validates JWT tokens on every protected request before reaching the endpoint.
    """
    async def dispatch(self, request: Request, call_next):
        try:
            if not settings.AUTH_ENABLED:
                return await call_next(request)

            if request.url.path in PUBLIC_ROUTES:
                return await call_next(request)

            # Allow OPTIONS for CORS preflight
            if request.method == "OPTIONS":
                return await call_next(request)

            # 1. Extraction
            auth_header = request.headers.get("Authorization", "")
            if not auth_header:
                logger.warn("Auth: Missing Authorization header", path=request.url.path)
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Missing authentication token"}
                )

            token = auth_header.replace("Bearer ", "") if "Bearer " in auth_header else auth_header
                
            if not token:
                logger.warn("Auth: Empty token", path=request.url.path)
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Empty authentication token"}
                )

            # 2. Validation
            payload = verify_token(token)
            if not payload:
                logger.warn("Auth: Invalid or expired token", path=request.url.path)
                return JSONResponse(
                    status_code=401, 
                    content={"detail": "Invalid session or expired token"}
                )

            # 3. State Attachment
            request.state.user = payload.get("sub", "unknown")
            request.state.user_role = payload.get("role", "viewer")
            request.state.must_change_password = payload.get("mcp", False)
            
            # 4. Forced Reset Gate
            # If user must change password, block all non-essential actions
            if request.state.must_change_password:
                essential_paths = {
                    "/api/v1/auth/change-password",
                    "/api/v1/auth/logout",
                    "/api/v1/auth/me",
                    "/api/v1/health",
                    "/api/v1/readiness"
                }
                if request.url.path not in essential_paths:
                    log_security_event(request, "FORBIDDEN", f"Access blocked: password reset mandatory for user '{request.state.user}'")
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Password reset required",
                            "code": "PASSWORD_RESET_REQUIRED"
                        }
                    )
            
            return await call_next(request)
        except Exception as e:
            # Fallback for error reporting if request is partially initialized
            path = getattr(request, 'url', {}).path if 'request' in locals() else "unknown"
            logger.error("AuthMiddleware: Unexpected crash", error=str(e), path=path)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal security middleware error"}
            )
