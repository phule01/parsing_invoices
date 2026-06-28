"""
Settings router - allows admins to configure environment variables via API.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import os
import logging
from dotenv import load_dotenv, set_key
from pathlib import Path

from database import get_db
from app.core.security import get_current_user
from models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["Settings"])

# Path to .env file
ENV_FILE = Path(__file__).parent.parent / ".env"


def _is_admin(db: Session, user_id: int) -> bool:
    """Check if user is admin"""
    user = db.query(User).filter(User.id == user_id).first()
    return user and user.is_admin


class SettingsUpdate:
    """Settings that can be updated"""
    EMAIL_ADDRESS: str = None
    EMAIL_PASSWORD: str = None
    GEMINI_API_KEY: str = None
    TELEGRAM_BOT_TOKEN: str = None
    TELEGRAM_CHAT_ID: str = None


@router.get("/")
async def get_settings(request: Request, db: Session = Depends(get_db)):
    """Get current settings. Admins see all, standard users see limited info."""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    data = decode_token(token)
    
    is_admin = _is_admin(db, data["user_id"])
    
    if is_admin:
        return {
            "EMAIL_ADDRESS": os.getenv("EMAIL_ADDRESS", ""),
            "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
            "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
            "IMAP_SERVER": os.getenv("IMAP_SERVER", ""),
            "SMTP_SERVER": os.getenv("SMTP_SERVER", ""),
        }
    else:
        # Standard users only see the email address to verify it's working
        return {
            "EMAIL_ADDRESS": os.getenv("EMAIL_ADDRESS", ""),
            "IMAP_SERVER": os.getenv("IMAP_SERVER", ""),
            "SMTP_SERVER": os.getenv("SMTP_SERVER", ""),
            "GEMINI_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
        }


@router.post("/update")
async def update_settings(
    data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update settings (admins only)"""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    if not _is_admin(db, decoded["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update settings"
        )
    
    try:
        # Update .env file with new values using in-place writer to preserve Docker inode
        from app.core.env_utils import update_env_file_in_place
        update_env_file_in_place(str(ENV_FILE), data)
        logger.info(f"✅ Updated settings: {list(data.keys())}")
        
        return {
            "status": "success",
            "message": "Settings updated successfully",
            "updated_keys": list(data.keys())
        }
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Settings were NOT saved because the server prevented writing to the .env file! Please run 'sudo chown 1000:1000 .env' in your project directory on your server to fix Linux permissions. Technical error: {str(e)}"
        )


from pydantic import BaseModel

class TestTelegramRequest(BaseModel):
    bot_token: str
    chat_id: str

@router.post("/test-telegram")
async def test_telegram(
    payload: TestTelegramRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Send test Telegram message using provided credentials (admins only)"""
    from app.core.security import get_token_from_request, decode_token
    import httpx
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    if not _is_admin(db, decoded["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test Telegram"
        )
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{payload.bot_token}/sendMessage",
                json={
                    "chat_id": payload.chat_id,
                    "text": "✅ Test message from Invoice System using temporary settings!",
                    "parse_mode": "HTML"
                },
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {"status": "success", "message": "Test message sent!"}
            else:
                return {"status": "error", "message": data.get("description", "Failed to send test message")}
    except Exception as e:
        logger.error(f"Error testing Telegram: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


class TestEmailRequest(BaseModel):
    target_email: str
    email_address: str
    email_password: str
    smtp_server: str = "smtp.gmail.com"

@router.post("/test-email")
async def test_email(
    payload: TestEmailRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Send test email using provided credentials (admins only)"""
    from app.core.security import get_token_from_request, decode_token
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    if not _is_admin(db, decoded["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test email"
        )
    
    try:
        # Default port 587
        smtp_port = 587
        
        msg = MIMEMultipart()
        msg["From"] = payload.email_address
        msg["To"] = payload.target_email
        msg["Subject"] = "Test Email from Invoice System"
        
        body = "This is a test email to verify your temporary email configuration is working correctly!"
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(payload.smtp_server, smtp_port) as server:
            server.starttls()
            server.login(payload.email_address, payload.email_password)
            server.send_message(msg)
        
        logger.info(f"✅ Test email sent to {payload.target_email}")
        return {"status": "success", "message": f"Test email sent to {payload.target_email}"}
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )
