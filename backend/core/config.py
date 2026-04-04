from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Agentic GRC Command Center"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # API Settings
    PORT: int = 8001
    HOST: str = "0.0.0.0"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173", 
        "http://localhost:3000", 
        "http://localhost:3006"
    ]
    
    # Paths
    DOCUMENTS_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "GRC_Analyst")
    
    # AI
    GOOGLE_API_KEY: str = ""

    # Auth
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    AUTH_ENABLED: bool = True

    # User Registry (loaded from .env — temporary test identities)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "grc-admin-2026"
    ANALYST_USERNAME: str = "analyst"
    ANALYST_PASSWORD: str = "grc-analyst-2026"
    VIEWER_USERNAME: str = "viewer"
    VIEWER_PASSWORD: str = "grc-viewer-2026"

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        case_sensitive = True

settings = Settings()
