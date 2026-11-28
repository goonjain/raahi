import datetime
import hashlib
import re
import secrets
import uuid
from typing import Optional
from urllib.parse import urlparse

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import User, UserSession

# Argon2id password hasher (OWASP recommended parameters)
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email_format(email: str) -> str:
    norm = normalize_email(email)
    if not norm or len(norm) > 255 or not EMAIL_REGEX.match(norm):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please enter a valid email address.",
        )
    return norm


def validate_password_strength(password: str) -> None:
    if not password or len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters long.",
        )
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must include at least one letter and one number.",
        )


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    if not password or not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _as_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def create_user_session(db: Session, user: User) -> tuple[str, UserSession]:
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=settings.SESSION_TTL_HOURS)
    raw_token = secrets.token_urlsafe(32)
    session = UserSession(
        id=f"sess_{uuid.uuid4().hex}",
        token_hash=hash_session_token(raw_token),
        user_id=user.id,
        created_at=now,
        expires_at=expires_at,
        revoked_at=None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return raw_token, session


def get_session_user(db: Session, raw_token: Optional[str]) -> Optional[User]:
    if not raw_token:
        return None
    token_hash = hash_session_token(raw_token)
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    if not session:
        return None
    if session.revoked_at is not None:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    if _as_utc(session.expires_at) <= now:
        return None
    return session.user


def revoke_session_by_token(db: Session, raw_token: Optional[str]) -> None:
    if not raw_token:
        return
    token_hash = hash_session_token(raw_token)
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()


def set_session_cookie(response: Response, raw_token: str) -> None:
    samesite = settings.COOKIE_SAMESITE if settings.COOKIE_SAMESITE in ("lax", "strict", "none") else "lax"
    secure = settings.COOKIE_SECURE or samesite == "none"
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=settings.SESSION_TTL_HOURS * 3600,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def clear_session_cookie(response: Response) -> None:
    samesite = settings.COOKIE_SAMESITE if settings.COOKIE_SAMESITE in ("lax", "strict", "none") else "lax"
    secure = settings.COOKIE_SECURE or samesite == "none"
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        domain=settings.COOKIE_DOMAIN,
        secure=secure,
        httponly=True,
        samesite=samesite,
    )


def _origin_allowed(origin_or_referer: str) -> bool:
    parsed = urlparse(origin_or_referer)
    if not parsed.scheme or not parsed.netloc:
        return False
    origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    allowed = {o.rstrip("/") for o in settings.CORS_ORIGINS}
    if origin in allowed:
        return True
    # Allow any localhost/127.0.0.1 port in local development
    if parsed.hostname in ("localhost", "127.0.0.1") and parsed.scheme == "http":
        return True
    return False


def verify_csrf_origin(request: Request) -> None:
    """Protect cookie-authenticated state-changing endpoints against cross-site request forgery."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("origin")
    if origin:
        if not _origin_allowed(origin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin request blocked by CSRF protection.",
            )
        return
    referer = request.headers.get("referer")
    if referer:
        if not _origin_allowed(referer):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-origin referer blocked by CSRF protection.",
            )
        return
    sec_fetch_site = (request.headers.get("sec-fetch-site") or "").lower()
    if sec_fetch_site == "cross-site":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site request blocked by CSRF protection.",
        )


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    return get_session_user(db, raw_token)


def require_authenticated_user(
    request: Request,
    user: Optional[User] = Depends(get_optional_current_user),
) -> User:
    verify_csrf_origin(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in to continue.",
        )
    return user


def require_admin(
    user: User = Depends(require_authenticated_user),
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrator privileges required.",
        )
    return user

