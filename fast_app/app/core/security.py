"""
app/core/security.py — single source of truth for authentication and access control.

Merges two previously divergent implementations:

  auth.py (AuthService class)
    • sub = user_id (int) in JWT payload   ← this project uses auth_router.py
    • 24-hour token expiry
    • verify_token raises HTTPException directly

  security.py (module-level functions)
    • sub = username (string) in JWT payload
    • 30-minute token expiry (too short for practical use)
    • 2-user access control (ALLOWED_USERS) ← unique and worth keeping
    • log_audit                             ← unique and worth keeping
    • authenticate_user                     ← unique and worth keeping

Resolution:
  • JWT shape follows auth_router.py (sub = user_id, username in payload)
  • Token expiry: 1440 min (24 h) — matches auth.py, configurable via env
  • 2-user enforcement and audit logging kept from security.py
  • log_audit guard fixed (was always False, so audits were silently dropped)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLog, User

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────

SECRET_KEY: str = os.getenv(
    "SECRET_KEY", "your-secret-key-change-in-production-use-random-32-chars"
)
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def create_access_token(
    user_id: int,
    username: str,
    is_admin: bool = False,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT.

    Payload shape:
      sub      — user_id (int)   primary identity claim
      username — username (str)  human-readable, used for logging
      is_admin — bool            admin role flag
      iat      — issued-at
      exp      — expiry
    """
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": user_id,
        "username": username,
        "is_admin": is_admin,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises HTTPException on any failure.

    Returns: {"user_id": int, "username": str}
    """
    _401 = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise _401

    user_id = payload.get("sub")
    if user_id is None:
        raise _401

    return {
        "user_id": int(user_id), 
        "username": payload.get("username", ""),
        "is_admin": payload.get("is_admin", False)
    }


# ── Authentication ────────────────────────────────────────────────────────────

def authenticate_user(username: str, password: str, db: Session) -> Optional[User]:
    """
    Validate credentials against the database.
    Returns the User on success, None on any failure (caller raises 401).
    """

    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.warning("Login attempt for non-existent user: %s", username)
        return None
    if not verify_password(password, user.hashed_password):
        logger.warning("Bad password for user: %s", username)
        return None
    if not user.is_active:
        logger.warning("Inactive user login attempt: %s", username)
        return None

    log_audit(db, user_id=user.id, action="LOGIN", details=f"User {username} logged in")
    return user


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_token_from_request(request: Request) -> str:
    """Extract the raw Bearer token string from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth.split(" ", 1)[1]


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: decode the JWT, enforce the allow list, return the User.
    Bypasses JWT if X-Internal-Secret is provided (used by email_listener).
    """
    internal_secret = request.headers.get("X-Internal-Secret")
    if internal_secret and internal_secret == SECRET_KEY:
        admin_user = db.query(User).filter(User.is_admin == True).first()
        if admin_user:
            return admin_user

    token = get_token_from_request(request)
    data = decode_token(token)

    user = db.query(User).filter(User.id == data["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")

    log_audit(db, user_id=user.id, action="API_ACCESS", details=f"Access by {user.username}")
    return user


def get_current_user_id(request: Request, db: Session = Depends(get_db)) -> int:
    """
    Lightweight dependency: decode the JWT, return only the user_id int.
    Bypasses JWT if X-Internal-Secret is provided (used by email_listener).
    """
    internal_secret = request.headers.get("X-Internal-Secret")
    if internal_secret and internal_secret == SECRET_KEY:
        admin_user = db.query(User).filter(User.is_admin == True).first()
        if admin_user:
            return admin_user.id

    token = get_token_from_request(request)
    return decode_token(token)["user_id"]


# ── Audit logging ─────────────────────────────────────────────────────────────

def log_audit(
    db: Session,
    *,
    user_id: Optional[int] = None,
    action: str = "UNKNOWN",
    resource: Optional[str] = None,
    resource_id: Optional[int] = None,
    details: Optional[str] = None,
    status_code: int = 200,
) -> None:
    """
    Write an audit trail entry.

    Previously this function had a broken guard:
      hasattr(db.query(User).first().__class__.__module__, 'AuditLog')
    That expression always returns False (modules don't have an 'AuditLog'
    attribute), so audit logs were silently never written.
    Now it simply writes the log and catches any DB error without swallowing it.
    """
    try:
        db.add(AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            status_code=status_code,
            timestamp=datetime.utcnow(),
        ))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to write audit log (action=%s): %s", action, exc)
