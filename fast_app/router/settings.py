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
    """Get current settings for the authenticated user."""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    data = decode_token(token)
    
    current_user = db.query(User).filter(User.id == data["user_id"]).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {
        "EMAIL_ADDRESS": current_user.email or "",
        "GEMINI_API_KEY": current_user.gemini_api_key or "",
        "TELEGRAM_BOT_TOKEN": current_user.telegram_bot_token or "",
        "TELEGRAM_CHAT_ID": current_user.telegram_chat_id or "",
        "IMAP_SERVER": current_user.imap_server or os.getenv("IMAP_SERVER", "imap.gmail.com"),
        "SMTP_SERVER": current_user.smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    }

@router.get("/system")
async def get_system_settings(request: Request, db: Session = Depends(get_db)):
    """Internal endpoint for email_listener to get full credentials for ALL active users."""
    secret = request.headers.get("X-Internal-Secret")
    expected_secret = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-use-random-32-chars")
    if secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        
    users = db.query(User).filter(User.is_active == True, User.email.isnot(None), User.email != "").all()
    
    settings_list = []
    for user in users:
        settings_list.append({
            "user_id": user.id,
            "EMAIL_ADDRESS": user.email or "",
            "EMAIL_PASSWORD": user.email_password or "",
            "GEMINI_API_KEY": user.gemini_api_key or "",
            "TELEGRAM_BOT_TOKEN": user.telegram_bot_token or "",
            "TELEGRAM_CHAT_ID": user.telegram_chat_id or "",
            "IMAP_SERVER": user.imap_server or os.getenv("IMAP_SERVER", "imap.gmail.com"),
            "IMAP_PORT": os.getenv("IMAP_PORT", "993"),
            "SMTP_SERVER": user.smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "SMTP_PORT": os.getenv("SMTP_PORT", "587"),
        })
        
    return settings_list

@router.post("/update")
async def update_settings(
    data: dict,
    request: Request,
    db: Session = Depends(get_db)
):
    """Update settings for the current user in the database"""
    from app.core.security import get_token_from_request, decode_token
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    current_user = db.query(User).filter(User.id == decoded["user_id"]).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    try:
        if "EMAIL_ADDRESS" in data:
            current_user.email = data["EMAIL_ADDRESS"]
        if "EMAIL_PASSWORD" in data and data["EMAIL_PASSWORD"]:
            current_user.email_password = data["EMAIL_PASSWORD"]
        if "GEMINI_API_KEY" in data:
            current_user.gemini_api_key = data["GEMINI_API_KEY"]
        if "TELEGRAM_BOT_TOKEN" in data:
            current_user.telegram_bot_token = data["TELEGRAM_BOT_TOKEN"]
        if "TELEGRAM_CHAT_ID" in data:
            current_user.telegram_chat_id = data["TELEGRAM_CHAT_ID"]
            
        db.commit()
        logger.info(f"✅ Updated settings in database: {list(data.keys())} by user {current_user.username}")
        
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
                                json={"url": f"{webhook_url}/{data['TELEGRAM_BOT_TOKEN']}"},
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
    """Send test Telegram message using provided credentials"""
    from app.core.security import get_token_from_request, decode_token
    import httpx
    
    token = get_token_from_request(request)
    decoded = decode_token(token)
    
    # Users test their own credentials, so no admin check required for their own testing
    
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
    
    # Any user can test their own email
    
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
