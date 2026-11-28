import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

def _parse_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip() and o.strip() != "*"]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "https://musafir-seven-xi.vercel.app",
        "https://raahi-seven-xi.vercel.app",
    ]

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./musafir.db")
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "musafir_jaipur_admin_key_2026")
    CORS_ORIGINS: list[str] = _parse_cors_origins()
    # Session & Cookie configuration
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "raahi_session")
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "168"))
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax").lower()
    COOKIE_SECURE: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true" or os.getenv("COOKIE_SAMESITE", "lax").lower() == "none"
    COOKIE_DOMAIN: Optional[str] = os.getenv("COOKIE_DOMAIN", "").strip() or None
    # Rate limit: 1 report per user per place every 45 minutes
    RATE_LIMIT_MINUTES: int = int(os.getenv("RATE_LIMIT_MINUTES", "45"))
    # Reports older than 2 hours (120 minutes) stop affecting the live crowd estimate
    STALE_WINDOW_MINUTES: int = int(os.getenv("STALE_WINDOW_MINUTES", "120"))
    # Daily points cap per user (e.g. 100 points = 5 reports max per 24 hours)
    DAILY_POINTS_CAP: int = int(os.getenv("DAILY_POINTS_CAP", "100"))
    POINTS_PER_CHECKIN: int = int(os.getenv("POINTS_PER_CHECKIN", "20"))
    POINTS_FOR_GEM_APPROVAL: int = int(os.getenv("POINTS_FOR_GEM_APPROVAL", "50"))

settings = Settings()
