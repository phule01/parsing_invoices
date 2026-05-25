"""
routers/auth_router.py

Authentication endpoints. Imports exclusively from app.core.security
so there is a single source of truth for hashing, token creation, and
token decoding.

Files this no longer imports:
  - auth.py (AuthService class)     → merged into app/core/security.py
  - security.py (module functions)  → merged into app/core/security.py
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth_schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.core.security import (
    authenticate_user,
    create_access_token,
    decode_token,
    enforce_2user_limit,
    get_allowed_usernames,
    get_current_user,
    get_token_from_request,
    hash_password,
    log_audit,
    verify_password,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# ── Login ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate and return a JWT.
    Enforces the 2-user allow-list defined in APP env vars.
    """
    user = authenticate_user(credentials.username, credentials.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user. Restricted to the two usernames in ALLOWED_USERS.
    """
    u1, u2 = get_allowed_usernames()
    if user_data.username.lower() not in {u1.lower(), u2.lower()}:
        log_audit(
            db,
            action="UNAUTHORIZED_REGISTRATION",
            details=f"Attempted registration of non-allowed user: {user_data.username}",
            status_code=403,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the two configured users may register",
        )

    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    if not enforce_2user_limit(db):
        raise HTTPException(status_code=403, detail="Maximum user count (2) reached")

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(db, user_id=new_user.id, action="REGISTRATION",
              details=f"User {user_data.username} registered")

    token = create_access_token(user_id=new_user.id, username=new_user.username)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=new_user.id,
        username=new_user.username,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Current user ──────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile. Token is verified by the dependency."""
    return user


# ── Token validation ──────────────────────────────────────────────────────────

@router.get("/validate-token")
@router.post("/validate-token")
async def validate_token(request: Request):
    """Lightweight check that a token is still valid. Used by the frontend on load."""
    token = get_token_from_request(request)
    data = decode_token(token)       # raises 401 on failure
    return {"valid": True, "user_id": data["user_id"]}


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout():
    """JWT is stateless — just signal the client to discard the token."""
    return {"message": "Logged out successfully"}


# ── Change password ───────────────────────────────────────────────────────────

@router.post("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(old_password, user.hashed_password):
        log_audit(db, user_id=user.id, action="FAILED_PASSWORD_CHANGE",
                  details="Incorrect old password", status_code=401)
        raise HTTPException(status_code=401, detail="Incorrect old password")

    user.hashed_password = hash_password(new_password)
    db.commit()
    log_audit(db, user_id=user.id, action="PASSWORD_CHANGED",
              details="Password successfully changed")
    return {"message": "Password changed successfully"}
