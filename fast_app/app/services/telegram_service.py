"""
app/services/telegram_service.py — Telegram notification utilities.

Extracted from telegram_utils.py. This module's only responsibility is
sending messages through the Telegram Bot API and broadcasting to the
Web UI via WebSocket. It contains no business logic.

What is NOT here:
  - Invoice approval / rejection logic  → app/services/invoice_service.py
  - Telegram command handling           → telegram_handlers.py
  - WebSocket connection management     → utils/websocket_manager.py

Sync wrappers removed:
  The old telegram_utils.py had asyncio.run() wrappers to let async
  notification functions be called from sync FastAPI background tasks.
  FastAPI's BackgroundTasks accepts async callables directly, so those
  wrappers are unnecessary and caused "event loop already running" errors
  in some environments. Routers should pass the async functions directly
  to background_tasks.add_task().
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

TELEGRAM_API_URL: str = "https://api.telegram.org"

def get_telegram_config() -> tuple[str, str]:
    """Fetch telegram bot token and chat ID from database."""
    from database import SessionLocal
    from models import User
    
    try:
        with SessionLocal() as db:
            admin = db.query(User).filter(User.is_admin == True).first()
            if admin:
                bot_token = admin.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
                chat_id = admin.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()
                return bot_token, chat_id
    except Exception as e:
        logger.error(f"Error fetching telegram config from db: {e}")
        
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Lazy-import to avoid circular dependency at module load time
def _get_connection_manager():
    try:
        from websocket_manager import connection_manager
        return connection_manager
    except ImportError:
        return None


# ── Core messaging ────────────────────────────────────────────────────────────

async def send_message(
    text: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> bool:
    """Send a plain HTML message. Returns True on success."""
    result = await send_message_with_metadata(text, chat_id=chat_id, reply_markup=reply_markup)
    return result["ok"]


async def send_message_with_metadata(
    text: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> dict:
    """
    Send a message and return {"ok": bool, "message_id": int|None, "chat_id": str|None}.
    Use this when you need the Telegram message_id to edit it later.
    """
    db_bot_token, db_chat_id = get_telegram_config()
    bot_token = db_bot_token
    chat_id_target = chat_id or db_chat_id
    if not bot_token or not chat_id_target:
        return {"ok": False, "message_id": None, "chat_id": None}

    target = chat_id_target
    payload: dict = {"chat_id": target, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TELEGRAM_API_URL}/bot{bot_token}/sendMessage",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("ok"):
                msg_id = data.get("result", {}).get("message_id")
                logger.info("✅ Telegram message sent (msg_id=%s)", msg_id)
                return {"ok": True, "message_id": msg_id, "chat_id": str(target)}
            logger.error("❌ Telegram API error: %s", data.get("description"))
    except Exception as exc:
        logger.error("❌ Error sending Telegram message: %s", exc)

    return {"ok": False, "message_id": None, "chat_id": str(target) if target else None}


async def send_photo_with_metadata(
    photo_path: str,
    caption: str,
    chat_id: Optional[str] = None,
    reply_markup: Optional[dict] = None,
) -> dict:
    """Send a photo with caption and return message metadata."""
    db_bot_token, db_chat_id = get_telegram_config()
    bot_token = db_bot_token
    chat_id_target = chat_id or db_chat_id
    if not bot_token or not chat_id_target:
        return {"ok": False, "message_id": None, "chat_id": None}

    target = chat_id_target
    
    import aiofiles
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(photo_path, "rb") as f:
                files = {"document": ("preview.jpg", f, "image/jpeg")}
                data = {
                    "chat_id": target,
                    "caption": caption,
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    import json
                    data["reply_markup"] = json.dumps(reply_markup)
                    
                resp = await client.post(
                    f"{TELEGRAM_API_URL}/bot{bot_token}/sendDocument",
                    data=data,
                    files=files
                )
                resp.raise_for_status()
                resp_data = resp.json()
                if resp_data.get("ok"):
                    msg_id = resp_data.get("result", {}).get("message_id")
                    logger.info("✅ Telegram document sent (msg_id=%s)", msg_id)
                    return {"ok": True, "message_id": msg_id, "chat_id": str(target)}
                logger.error("❌ Telegram API error (sendDocument): %s", resp_data.get("description"))
    except Exception as exc:
        logger.error("❌ Error sending Telegram photo: %s", exc)

    return {"ok": False, "message_id": None, "chat_id": str(target) if target else None}


async def edit_message(
    chat_id: str,
    message_id: int,
    text: str,
    reply_markup: Optional[dict] = None,
) -> bool:
    """Edit an existing Telegram message (e.g. to remove inline buttons after action)."""
    bot_token, _ = get_telegram_config()
    if not bot_token:
        return False
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TELEGRAM_API_URL}/bot{bot_token}/editMessageText",
                json=payload,
            )
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("❌ Error editing Telegram message: %s", exc)
        return False


# ── Web UI broadcast ──────────────────────────────────────────────────────────

async def broadcast_to_web_ui(notification: dict) -> None:
    """
    Push a notification to all connected Web UI clients via WebSocket.
    Safe to call even if no clients are connected.
    """
    manager = _get_connection_manager()
    if not manager:
        return
    try:
        await manager.broadcast_to_all({"type": "notification", "notification": notification})
        logger.debug("📢 Web UI broadcast: %s", notification.get("type"))
    except Exception as exc:
        logger.error("❌ WebSocket broadcast error: %s", exc)


# ── Invoice notifications ─────────────────────────────────────────────────────

async def send_invoice_approval_request(
    invoice_id: int,
    invoice_number: str,
    seller_name: str,
    total_amount: float,
    num_items: int = 0,
    items: Optional[list] = None,
    raw_file_path: Optional[str] = None,
) -> bool:
    """
    Send an invoice to Telegram with YES/NO inline buttons.
    Also broadcasts a Web UI notification with approve/reject actions.
    """
    products_section = ""
    if items:
        products_section = "\n<b>📦 Sản phẩm:</b>\n"
        for idx, item in enumerate(items, 1):
            products_section += (
                f"{idx}. {item.get('item_name', 'Unknown')}\n"
                f"   └─ Qty: {item.get('quantity', 0)} "
                f"× {item.get('unit_price', 0):,.0f} VND "
                f"= {item.get('total_price', 0):,.0f} VND\n"
            )

    message = (
        f"📩 <b>Hóa đơn mới</b>\n\n"
        f"<b>Số hóa đơn:</b> {invoice_number}\n"
        f"<b>Công ty:</b> {seller_name}\n"
        f"<b>Số sản phẩm:</b> {num_items}"
        f"{products_section}\n"
        f"<b>Tổng tiền:</b> {total_amount:,.2f} VND\n\n"
        f"👉 <b>Muốn nhập vào tồn kho không?</b>"
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ YES - Nhập tồn kho", "callback_data": f"invoice_approve_{invoice_id}"},
            {"text": "❌ NO - Bỏ qua",         "callback_data": f"invoice_reject_{invoice_id}"},
        ]]
    }

    result = await send_message_with_metadata(message, reply_markup=reply_markup)

    await broadcast_to_web_ui({
        "type": "invoice_received",
        "title": "📬 New Invoice",
        "message": f"Invoice {invoice_number} from {seller_name} — {total_amount:,.2f} VND",
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "invoice_id": invoice_id,
        "action_required": True,
        "severity": "warning",
    })

    return result["ok"]


async def send_invoice_status(
    action: str,         # "approve" | "reject"
    invoice_number: str,
    note: str = "",
) -> bool:
    """
    Send a status update after an invoice is approved or rejected.
    Used by both the web router and telegram_handlers after processing.
    """
    if action == "approve":
        message = (
            f"✅ <b>Hóa đơn đã được nhập</b>\n\n"
            f"<b>Số hóa đơn:</b> {invoice_number}\n"
            f"<b>Hành động:</b> Tồn kho đã được cập nhật"
        )
        notif_type, title, severity = "invoice_approved", "✅ Invoice Approved", "success"
    else:
        message = (
            f"❌ <b>Hóa đơn bị bỏ qua</b>\n\n"
            f"<b>Số hóa đơn:</b> {invoice_number}\n"
            f"<b>Hành động:</b> Không nhập tồn kho"
        )
        notif_type, title, severity = "invoice_rejected", "❌ Invoice Rejected", "error"

    if note:
        message += f"\n<b>Ghi chú:</b> {note}"

    sent = await send_message(message)
    await broadcast_to_web_ui({
        "type": notif_type,
        "title": title,
        "message": f"Invoice {invoice_number} {action}d",
        "entity_type": "invoice",
        "severity": severity,
    })
    return sent


# ── Error / system notifications ──────────────────────────────────────────────

async def send_error_notification(error_message: str, context: str = "") -> bool:
    """Send an error alert to Telegram and the Web UI."""
    message = (
        f"⚠️ <b>LỖI HỆ THỐNG</b>\n\n"
        f"<b>Module:</b> {context or 'Unknown'}\n"
        f"<b>Lỗi:</b> {error_message}"
    )
    sent = await send_message(message)
    await broadcast_to_web_ui({
        "type": "system_error",
        "title": "⚠️ System Error",
        "message": f"[{context}] {error_message}",
        "severity": "error",
    })
    return sent


async def send_parse_failure_notification(file_name: str, error_message: str) -> bool:
    """Notify when AI parsing fails for an invoice file."""
    return await send_error_notification(
        error_message=error_message,
        context=f"AI Parser — {file_name}",
    )


# ── Utility ───────────────────────────────────────────────────────────────────

async def get_telegram_status() -> dict:
    bot_token, chat_id = get_telegram_config()
    
    status = {
        "configured": bool(bot_token and chat_id),
        "bot_token_set": bool(bot_token),
        "chat_id_set": bool(chat_id),
        "chat_id": chat_id or "Not set",
        "api_url": TELEGRAM_API_URL,
        "webhook_info": None
    }
    
    if bot_token:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{TELEGRAM_API_URL}/bot{bot_token}/getWebhookInfo")
                if resp.status_code == 200:
                    status["webhook_info"] = resp.json().get("result")
                else:
                    status["webhook_info"] = {"error": f"HTTP {resp.status_code}", "detail": resp.text}
        except Exception as e:
            status["webhook_info"] = {"error": str(e)}
            
    return status
