from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import asyncio
from pathlib import Path
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
from pydantic import BaseModel
import logging

from database import get_db
from models import EmailLog
from schemas import EmailLogResponse
from app.core.security import decode_token
from telegram_utils import broadcast_to_web_ui, send_invoice_approval_request, send_telegram_message

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-load email_listener logic from the sibling service
EMAIL_LISTENER_DIR = Path(__file__).resolve().parents[2] / "email_listener"
if str(EMAIL_LISTENER_DIR) not in sys.path:
    sys.path.append(str(EMAIL_LISTENER_DIR))

# Also try mounted path
if "/email_listener" not in sys.path:
    sys.path.append("/email_listener")

APIClient = None
run_once = None

try:
    # Try to import from email_processor
    from email_processor import APIClient as ImportedAPIClient, run_once as imported_run_once  # type: ignore
    APIClient = ImportedAPIClient
    run_once = imported_run_once
    logger.info("✅ Successfully imported email_processor functions")
except Exception as e:
    logger.warning(f"⚠️  Failed to import email_processor: {e}")
    # Provide dummy implementations
    APIClient = None
    run_once = None

SCAN_STATE = {
    "running": False,
    "last_started": None,
    "last_finished": None,
    "last_result": None,
}




class EmailLogCreate(BaseModel):
    invoice_id: int = None
    email_from: str = None
    email_subject: str = None
    attachment_name: str = None
    file_url: str = None
    message_id: str = None
    status: str = "pending"
    error_message: str = None


def _require_auth(request: Request) -> None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = auth_header.split(" ", 1)[1]
    decode_token(token)


async def _scan_async(mode: str) -> dict:
    if APIClient is None or run_once is None:
        raise HTTPException(status_code=500, detail="Email scanner not available")

    api = APIClient(
        base_url=os.getenv("API_BASE_URL", "http://fastapi:8000"),
        username=os.getenv("API_USERNAME", "admin"),
        password=os.getenv("API_PASSWORD", "admin123"),
    )
    try:
        await api.authenticate()
    except Exception:
        # Continue without auth if login fails; email_processor handles this case
        pass

    criterion = "UNSEEN" if mode == "unseen" else "ALL"
    return await run_once(api, search_criterion=criterion)


def _scan_sync(mode: str) -> dict:
    return asyncio.run(_scan_async(mode))


async def _run_scan_in_thread(mode: str) -> dict:
    return await asyncio.to_thread(_scan_sync, mode)


@router.get("/logs", response_model=List[EmailLogResponse])
def get_email_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get email logs with pagination"""
    logs = db.query(EmailLog).offset(skip).limit(limit).all()
    return logs


@router.get("/logs/{log_id}", response_model=EmailLogResponse)
def get_email_log(log_id: int, db: Session = Depends(get_db)):
    """Get a specific email log"""
    log = db.query(EmailLog).filter(EmailLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")
    return log


@router.post("/logs", response_model=EmailLogResponse)
def create_email_log_endpoint(log_data: EmailLogCreate, db: Session = Depends(get_db)):
    """Create a new email log entry"""
    try:
        email_log = EmailLog(
            invoice_id=log_data.invoice_id,
            email_from=log_data.email_from,
            email_subject=log_data.email_subject,
            attachment_name=log_data.attachment_name,
            file_url=log_data.file_url,
            message_id=log_data.message_id,
            status=log_data.status,
            error_message=log_data.error_message,
            processed_at=datetime.utcnow() if log_data.status in ["success", "error"] else None
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        return email_log
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create email log: {str(e)}")


@router.post("/log", response_model=EmailLogResponse)
def create_email_log_simple(log_data: EmailLogCreate, db: Session = Depends(get_db)):
    """Create email log from dict (used by email_processor)"""
    try:
        email_log = EmailLog(
            invoice_id=log_data.invoice_id,
            email_from=log_data.email_from,
            email_subject=log_data.email_subject,
            attachment_name=log_data.attachment_name,
            file_url=log_data.file_url,
            message_id=log_data.message_id,
            status=log_data.status,
            error_message=log_data.error_message,
            processed_at=datetime.utcnow() if log_data.status in ["success", "error"] else None
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)
        return email_log
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create email log: {str(e)}")


@router.post("/send")
def send_email(recipient: str, subject: str, body: str, db: Session = Depends(get_db)):
    """Send an email"""
    email_log = None
    try:
        # Get email address from admin user
        admin = db.query(User).filter(User.is_admin == True).first()
        sender_email = admin.email if admin and admin.email else os.getenv("EMAIL_ADDRESS", "")
        
        # Create email log entry
        email_log = EmailLog(
            email_from=sender_email,
            email_subject=subject,
            status="sending"
        )
        db.add(email_log)
        db.commit()

        # Send email
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        # Note: In production, use proper SMTP configuration
        # server = smtplib.SMTP(admin.smtp_server or "smtp.gmail.com", 587)
        # server.starttls()
        # server.login(sender_email, admin.email_password)
        # server.send_message(msg)
        # server.quit()

        email_log.status = "sent"
        db.commit()

        return {"message": "Email sent successfully", "log_id": email_log.id}

    except Exception as e:
        if email_log:
            email_log.status = "failed"
            email_log.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.delete("/logs/{log_id}")
def delete_email_log(log_id: int, db: Session = Depends(get_db)):
    """Delete an email log"""
    log = db.query(EmailLog).filter(EmailLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")

    db.delete(log)
    db.commit()
    return {"message": "Email log deleted successfully"}


@router.post("/scan-now")
async def scan_now(
    request: Request,
    mode: str = "unseen",
):
    """
    Trigger an immediate email scan (UNSEEN by default).
    Note: Email listener runs continuously, so this is for manual triggers only.
    
    mode: unseen | all
    """
    _require_auth(request)

    if mode not in ["unseen", "all"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'unseen' or 'all'.")

    # Email listener is running continuously in the background
    # Return success status - the listener will pick up emails on its own cycle
    return {
        "status": "queued",
        "message": "Email scan is running in the background. Invoices will appear in the pending list as they are processed.",
        "mode": mode,
        "note": "The email listener scans for new invoices every 5 minutes automatically."
    }


@router.post("/notifications/broadcast")
async def broadcast_notification(notification_data: dict, request: Request):
    """
    Broadcast notification to Telegram (Vietnamese form only).
    This endpoint receives parse completion events from email_listener
    but delegates to send_invoice_approval_request for actual Telegram sending.
    
    Expected data:
    {
        "type": "invoice_received",
        "invoice_number": "INV-123",
        "seller": "Company Name",
        "amount": 1000.00,
        "invoice_id": 1,
        "items": [...],
    }
    """
    try:
        # Authenticate when a bearer token is present; internal callers may skip it.
        try:
            _require_auth(request)
        except HTTPException:
            raise
        except Exception:
            # Allow unauthenticated from internal services
            pass

        notification_type = notification_data.get("type", "unknown")

        if notification_type == "invoice_received":
            invoice_number = notification_data.get("invoice_number") or "N/A"
            seller_name = notification_data.get("seller") or notification_data.get("seller_name") or "Unknown"
            total_amount = float(notification_data.get("amount") or notification_data.get("total_amount") or 0)
            invoice_id = notification_data.get("invoice_id")
            items = notification_data.get("items") or []

            if invoice_id is None:
                raise HTTPException(status_code=400, detail="invoice_id is required for invoice_received notifications")

            sent = await send_invoice_approval_request(
                invoice_id=invoice_id,
                invoice_number=invoice_number,
                seller_name=seller_name,
                total_amount=total_amount,
                num_items=len(items),
                items=items,
            )

            if not sent:
                raise HTTPException(status_code=502, detail="Failed to send approval notification")

            logger.info(f"📬 Approval notification sent for invoice {invoice_number}")
            return {
                "status": "success",
                "message": "Approval notification sent",
                "invoice_number": invoice_number,
                "invoice_id": invoice_id,
            }

        if notification_type in {"parse_failure", "file_failure", "system_error"}:
            file_name = notification_data.get("file_name") or Path(notification_data.get("file_path", "")).name or "unknown file"
            error_message = notification_data.get("error_message") or notification_data.get("message") or "Unknown error"
            title = notification_data.get("title") or "📄 Invoices Can't Parsing"
            web_message = f"Can't parsing {file_name}"

            await send_telegram_message(
                f"📄 <b>{title}</b>\n\n<b>File:</b> {file_name}\n<b>Lỗi:</b> {error_message}"
            )
            await broadcast_to_web_ui({
                "type": notification_type,
                "title": title,
                "message": web_message,
                "entity_type": "invoice",
                "severity": "error",
                "file_name": file_name,
                "file_path": notification_data.get("file_path"),
                "error_message": error_message,
            })

            logger.warning(f"📄 Parse failure notification sent for {file_name}: {error_message}")
            return {
                "status": "success",
                "message": web_message,
                "file_name": file_name,
            }

        logger.info(f"📬 Broadcast notification received for invoice {notification_data.get('invoice_number')} - ignoring unsupported type {notification_type}")

        return {
            "status": "success",
            "message": "Notification ignored",
            "type": notification_type,
        }
        
    except HTTPException as e:
        logger.warning(
            "❌ Broadcast error: %s | type=%s | payload=%s",
            e.detail,
            notification_data.get("type", "unknown"),
            notification_data,
        )
        raise
    except Exception as e:
        logger.exception(
            "❌ Broadcast error: %s | type=%s | payload=%s",
            e,
            notification_data.get("type", "unknown"),
            notification_data,
        )
        return {
            "status": "error",
            "message": str(e) or e.__class__.__name__,
        }