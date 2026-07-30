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
    DOCUMENTS_PATH: str = os.getenv("DOCUMENTS_PATH", "GRC_Analyst")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", os.path.join("data", "grc_audit.db"))
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://grc_admin:grc_password_2026@localhost:5432/grc_audit")
    
    # AI
    GOOGLE_API_KEY: str = ""

    # Auth
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-USE-A-REAL-SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    AUTH_ENABLED: bool = True

    # User Registry — set real values in .env (gitignored). These fallbacks are
    # intentionally non-functional placeholders, not working credentials, so a
    # clone that forgets to create .env fails loudly instead of booting with a
    # known password.
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "CHANGE-ME-SET-IN-ENV"
    ANALYST_USERNAME: str = "analyst"
    ANALYST_PASSWORD: str = "CHANGE-ME-SET-IN-ENV"
    VIEWER_USERNAME: str = "viewer"
    VIEWER_PASSWORD: str = "CHANGE-ME-SET-IN-ENV"

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        case_sensitive = True

settings = Settings()
