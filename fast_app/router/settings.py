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
    
    # We fetch the first admin user to store global settings
    admin_user = db.query(User).filter(User.is_admin == True).first()
    is_admin = _is_admin(db, data["user_id"])
    
    if is_admin:
        return {
            "EMAIL_ADDRESS": admin_user.email if admin_user and admin_user.email else os.getenv("EMAIL_ADDRESS", ""),
            "GEMINI_API_KEY": admin_user.gemini_api_key if admin_user and admin_user.gemini_api_key else os.getenv("GEMINI_API_KEY", ""),
            "TELEGRAM_BOT_TOKEN": admin_user.telegram_bot_token if admin_user and admin_user.telegram_bot_token else os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "TELEGRAM_CHAT_ID": admin_user.telegram_chat_id if admin_user and admin_user.telegram_chat_id else os.getenv("TELEGRAM_CHAT_ID", ""),
            "IMAP_SERVER": admin_user.imap_server if admin_user and admin_user.imap_server else os.getenv("IMAP_SERVER", "imap.gmail.com"),
            "SMTP_SERVER": admin_user.smtp_server if admin_user and admin_user.smtp_server else os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        }
    else:
        # Standard users only see the email address to verify it's working
        return {
            "EMAIL_ADDRESS": admin_user.email if admin_user and admin_user.email else os.getenv("EMAIL_ADDRESS", ""),
            "IMAP_SERVER": admin_user.imap_server if admin_user and admin_user.imap_server else os.getenv("IMAP_SERVER", "imap.gmail.com"),
            "SMTP_SERVER": admin_user.smtp_server if admin_user and admin_user.smtp_server else os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "GEMINI_API_KEY": "",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_CHAT_ID": "",
        }

@router.get("/system")
async def get_system_settings(request: Request, db: Session = Depends(get_db)):
    """Internal endpoint for email_listener to get full credentials including passwords."""
    secret = request.headers.get("X-Internal-Secret")
    expected_secret = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-use-random-32-chars")
    if secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    admin_user = db.query(User).filter(User.is_admin == True).first()
    
    return {
        "EMAIL_ADDRESS": admin_user.email if admin_user and admin_user.email else os.getenv("EMAIL_ADDRESS", ""),
        "EMAIL_PASSWORD": admin_user.email_password if admin_user and admin_user.email_password else os.getenv("EMAIL_PASSWORD", ""),
        "GEMINI_API_KEY": admin_user.gemini_api_key if admin_user and admin_user.gemini_api_key else os.getenv("GEMINI_API_KEY", ""),
        "TELEGRAM_BOT_TOKEN": admin_user.telegram_bot_token if admin_user and admin_user.telegram_bot_token else os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHAT_ID": admin_user.telegram_chat_id if admin_user and admin_user.telegram_chat_id else os.getenv("TELEGRAM_CHAT_ID", ""),
        "IMAP_SERVER": admin_user.imap_server if admin_user and admin_user.imap_server else os.getenv("IMAP_SERVER", "imap.gmail.com"),
        "IMAP_PORT": os.getenv("IMAP_PORT", "993"),
        "SMTP_SERVER": admin_user.smtp_server if admin_user and admin_user.smtp_server else os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
    }

@router.post("/update")
async def update_settings(
    data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update settings (admins only) in the database"""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    if not _is_admin(db, decoded["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update settings"
        )
    
    try:
        admin_user = db.query(User).filter(User.is_admin == True).first()
        if not admin_user:
            raise Exception("No admin user found to save settings to")
            
        # Update admin user fields
        if "EMAIL_ADDRESS" in data:
            admin_user.email = data["EMAIL_ADDRESS"]
        if "EMAIL_PASSWORD" in data and data["EMAIL_PASSWORD"]:
            # Only update password if provided (don't overwrite with empty)
            admin_user.email_password = data["EMAIL_PASSWORD"]
        if "GEMINI_API_KEY" in data:
            admin_user.gemini_api_key = data["GEMINI_API_KEY"]
        if "TELEGRAM_BOT_TOKEN" in data:
            admin_user.telegram_bot_token = data["TELEGRAM_BOT_TOKEN"]
        if "TELEGRAM_CHAT_ID" in data:
            admin_user.telegram_chat_id = data["TELEGRAM_CHAT_ID"]
            
        db.commit()
        logger.info(f"✅ Updated settings in database: {list(data.keys())}")
        
        # If Telegram bot token was updated, re-register the webhook
        if "TELEGRAM_BOT_TOKEN" in data and data["TELEGRAM_BOT_TOKEN"]:
            webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
            if webhook_url:
                import httpx
                import asyncio
                from app.services.telegram_service import TELEGRAM_API_URL
                
                async def _re_register_webhook():
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.post(
                                f"{TELEGRAM_API_URL}/bot{data['TELEGRAM_BOT_TOKEN']}/setWebhook",
                                json={"url": webhook_url},
                            )
                            logger.info(f"Dynamic webhook re-registration from settings: {resp.text}")
                    except Exception as ex:
                        logger.error(f"Dynamic webhook re-registration failed: {ex}")
                        
                asyncio.create_task(_re_register_webhook())

        return {
            "status": "success",
            "message": "Settings updated successfully in database",
            "updated_keys": list(data.keys())
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating settings in database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
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
