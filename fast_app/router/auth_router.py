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
from auth_schemas import TokenResponse, UserLogin, UserRegister, AdminRegister, UserResponse
from app.core.security import (
    authenticate_user,
    create_access_token,
    decode_token,
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
        is_admin=user.is_admin,
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Register ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register a new standard user. Restricted to Admins only.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create new users",
        )

    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        is_admin=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(db, user_id=current_user.id, action="CREATE_USER",
              details=f"Admin {current_user.username} created user {user_data.username}")

    return new_user


# ── Admin Setup ───────────────────────────────────────────────────────────────

@router.post("/admin-setup", response_model=TokenResponse)
async def admin_setup(admin_data: AdminRegister, db: Session = Depends(get_db)):
    """
    Admin setup/registration with all system credentials.
    Only allowed if no admin exists yet (first-time setup).
    """
    # Check if admin already exists
    existing_admin = db.query(User).filter(User.is_admin == True).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account already exists. Contact the current admin to manage users."
        )

    if db.query(User).filter(User.username == admin_data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    if db.query(User).filter(User.email == admin_data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create admin user with all credentials
    admin_user = User(
        username=admin_data.username,
        email=admin_data.email,
        hashed_password=hash_password(admin_data.password),
        is_active=True,
        is_admin=True,
        email_password=admin_data.email_password,
        gemini_api_key=admin_data.gemini_api_key,
        telegram_bot_token=admin_data.telegram_bot_token,
        telegram_chat_id=admin_data.telegram_chat_id,
        imap_server=admin_data.imap_server,
        smtp_server=admin_data.smtp_server,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    log_audit(db, user_id=admin_user.id, action="ADMIN_SETUP",
              details="Admin account created with system credentials")

    # Save credentials to .env file and os.environ so the system can actually use them
    try:
        from dotenv import set_key
        from pathlib import Path
        import os
        
        env_file = Path(__file__).parent.parent / ".env"
        env_updates = {
            "EMAIL_ADDRESS": admin_data.email,
            "EMAIL_PASSWORD": admin_data.email_password,
            "GEMINI_API_KEY": admin_data.gemini_api_key,
            "TELEGRAM_BOT_TOKEN": admin_data.telegram_bot_token,
            "TELEGRAM_CHAT_ID": admin_data.telegram_chat_id,
            "IMAP_SERVER": admin_data.imap_server,
            "SMTP_SERVER": admin_data.smtp_server,
        }
        
        from app.core.env_utils import update_env_file_in_place
        update_env_file_in_place(str(env_file), env_updates)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to update .env during admin setup: {e}")
        # Delete the admin user so they can try again once permissions are fixed
        db.delete(admin_user)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admin account was NOT created because the server prevented writing to the .env file! Please run 'sudo chown 1000:1000 .env' on your server to fix Linux permissions. Technical error: {str(e)}"
        )

    token = create_access_token(
        user_id=admin_user.id, 
        username=admin_user.username,
        is_admin=admin_user.is_admin
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=admin_user.id,
        username=admin_user.username,
        is_admin=admin_user.is_admin,
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
    return {"valid": True, "user_id": data["user_id"], "is_admin": data.get("is_admin", False)}


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
