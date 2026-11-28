import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.models import User
from backend.app.schemas import AuthLoginRequest, AuthSignupRequest, AuthUserResponse
from backend.app.services.auth import (
    clear_session_cookie,
    create_user_session,
    get_optional_current_user,
    hash_password,
    normalize_email,
    revoke_session_by_token,
    set_session_cookie,
    validate_email_format,
    validate_password_strength,
    verify_csrf_origin,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _to_user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        name=user.username,
        email=user.email or "",
        role=user.role,
        created_at=user.created_at,
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    payload: AuthSignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    verify_csrf_origin(request)

    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name must be at least 2 characters long.",
        )

    norm_email = validate_email_format(payload.email)
    validate_password_strength(payload.password)

    existing = db.query(User).filter(User.email == norm_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Public signup ALWAYS assigns role="tourist" regardless of any client payload
    user = User(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        username=name,
        email=norm_email,
        password_hash=hash_password(payload.password),
        role="tourist",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    raw_token, _ = create_user_session(db, user)
    set_session_cookie(response, raw_token)

    return {"user": _to_user_response(user)}


@router.post("/login")
def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    verify_csrf_origin(request)

    norm_email = normalize_email(payload.email)
    user = db.query(User).filter(User.email == norm_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    raw_token, _ = create_user_session(db, user)
    set_session_cookie(response, raw_token)

    return {"user": _to_user_response(user)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    verify_csrf_origin(request)
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    revoke_session_by_token(db, raw_token)
    clear_session_cookie(response)
    return {"success": True}


@router.get("/me")
def get_me(
    user: User | None = Depends(get_optional_current_user),
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )
    return {"user": _to_user_response(user)}

