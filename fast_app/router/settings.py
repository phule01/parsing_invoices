"""
Settings router - allows admins to configure environment variables via API.
"""
from fastapi import APIRouter, Depends, HTTPException, status
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
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


def _is_admin(db: Session, user_id: int) -> bool:
    """Check if user is admin (username is 'admin')"""
    user = db.query(User).filter(User.id == user_id).first()
    return user and user.username.lower() == "admin"


class SettingsUpdate:
    """Settings that can be updated"""
    EMAIL_ADDRESS: str = None
    EMAIL_PASSWORD: str = None
    GEMINI_API_KEY: str = None
    TELEGRAM_BOT_TOKEN: str = None
    TELEGRAM_CHAT_ID: str = None


@router.get("/")
async def get_settings(request, db: Session = Depends(get_db)):
    """Get current settings (admins only)"""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    data = decode_token(token)
    
    if not _is_admin(db, data["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view settings"
        )
    
    return {
        "EMAIL_ADDRESS": os.getenv("EMAIL_ADDRESS", ""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID", ""),
        "IMAP_SERVER": os.getenv("IMAP_SERVER", ""),
        "SMTP_SERVER": os.getenv("SMTP_SERVER", ""),
    }


@router.post("/update")
async def update_settings(
    data: dict,
    request,
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
        # Update .env file with new values
        for key, value in data.items():
            if value:  # Only update if value is provided
                set_key(ENV_FILE, key, str(value))
                os.environ[key] = str(value)
                logger.info(f"✅ Updated setting: {key}")
        
        return {
            "status": "success",
            "message": "Settings updated successfully",
            "updated_keys": list(data.keys())
        }
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating settings: {str(e)}"
        )


@router.post("/test-telegram")
async def test_telegram(request, db: Session = Depends(get_db)):
    """Send test Telegram message (admins only)"""
    from app.core.security import get_token_from_request, decode_token
    from app.services.telegram_service import send_message
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    if not _is_admin(db, decoded["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can test Telegram"
        )
    
    try:
        result = await send_message("✅ Test message from Invoice System")
        if result:
            return {"status": "success", "message": "Test message sent!"}
        else:
            return {"status": "error", "message": "Failed to send test message"}
    except Exception as e:
        logger.error(f"Error testing Telegram: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )


@router.post("/test-email")
async def test_email(
    email_address: str,
    request,
    db: Session = Depends(get_db)
):
    """Send test email (admins only)"""
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
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("EMAIL_ADDRESS")
        sender_password = os.getenv("EMAIL_PASSWORD")
        
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = email_address
        msg["Subject"] = "Test Email from Invoice System"
        
        body = "This is a test email to verify your email configuration is working correctly."
        msg.attach(MIMEText(body, "plain"))
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        logger.info(f"✅ Test email sent to {email_address}")
        return {"status": "success", "message": f"Test email sent to {email_address}"}
    except Exception as e:
        logger.error(f"Error sending test email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}"
        )
