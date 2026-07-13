"""
telegram_handlers.py

Handles two kinds of Telegram input:
  1. Callback queries — user clicked an inline button (approve / reject invoice)
  2. Text commands    — /listaccount, /addaccount, /deleteaccount, etc.

What changed in this refactor:
  REMOVED: _process_invoice_action() — 110-line function that duplicated
           the inventory update logic now owned by InvoiceService.
           Both handle_invoice_callback and process_invoice_action_from_web
           now call InvoiceService(db).approve/reject directly.

  CHANGED: Imports updated from telegram_utils → app.services.telegram_service
"""
from __future__ import annotations

import logging
import os
from typing import Tuple

import httpx
from sqlalchemy.orm import Session

from models import User, Invoice, Product
from app.core.security import hash_password
from app.services.invoice_service import InvoiceService
from app.services.telegram_service import (
    TELEGRAM_API_URL,
    send_message,
    edit_message,
    broadcast_to_web_ui,
    send_invoice_status,
)
from telegram_conversation import (
    start_conversation, get_conversation_state, get_conversation_data,
    update_conversation_data, end_conversation,
    STATE_IDLE, STATE_ADD_USERNAME, STATE_ADD_PASSWORD, STATE_ADD_ROLE,
    STATE_DELETE_USERNAME, STATE_CHANGE_USERNAME, STATE_CHANGE_PASSWORD,
)

logger = logging.getLogger(__name__)

USAGE_TEXT = (
    "<b>Available commands</b>\n\n"
    "<b>👤 Account Management</b>\n"
    "📋 <b>/listaccount</b> - Show all accounts\n"
    "➕ <b>/addaccount</b> - Add new account (interactive)\n"
    "🗑 <b>/deleteaccount</b> - Delete account (interactive)\n"
    "🔑 <b>/changepassword</b> - Change password (interactive)\n\n"
    "<b>📦 Inventory Management</b>\n"
    "📄 <b>/listinvoices</b> - Show all invoices\n"
    "📋 <b>/listproducts</b> - Show all products\n\n"
    "<i>Each command will guide you through the process step by step</i>"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_authorized_chat(chat_id: int) -> bool:
    configured_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return bool(configured_chat_id) and str(chat_id) == configured_chat_id


def _parse_command(text: str) -> Tuple[str, list]:
    parts = text.strip().split()
    if not parts:
        return "", []
    return parts[0].split("@", 1)[0].lower(), parts[1:]


# ── Invoice callbacks ─────────────────────────────────────────────────────────

async def handle_invoice_callback(
    callback_data: str,
    callback_id: str,
    chat_id: int,
    message_id: int,
    db: Session,
) -> dict:
    """
    Process an approve / reject button press from Telegram.

    Delegates entirely to InvoiceService — no inventory logic here.
    """
    parts = callback_data.split("_")
    if len(parts) < 3:
        return {"status": "error", "msg": "Invalid callback data format"}

    action = parts[1]   # "approve" or "reject"
    try:
        invoice_id = int(parts[2])
    except ValueError:
        return {"status": "error", "msg": "Invalid invoice ID"}

    # ── Business logic: delegate to the service ──────────────────────────────
    if action == "approve":
        result = InvoiceService(db).approve(invoice_id, source="telegram")
    elif action == "reject":
        result = InvoiceService(db).reject(invoice_id, source="telegram")
    else:
        return {"status": "error", "msg": f"Unknown action: {action}"}

    # ── Build response text ───────────────────────────────────────────────────
    if not result.ok and not result.already_processed:
        response_text = f"❌ Error: {result.message}"
    elif result.already_processed:
        response_text = (
            f"⚠️ Invoice already processed by {result.processed_by}."
        )
    elif action == "approve":
        response_text = (
            f"✅ <b>Approved</b> invoice {result.invoice.invoice_number}.\n\n"
            f"📦 {len(result.product_updates)} product(s) updated."
        )
    else:
        response_text = f"❌ <b>Rejected</b> invoice {result.invoice.invoice_number}."

    # ── Side effects: notify Web UI ───────────────────────────────────────────
    if result.ok and not result.already_processed:
        event = "invoice_approved" if action == "approve" else "invoice_rejected"
        await broadcast_to_web_ui({
            "type": event,
            "title": "✅ Invoice Approved" if action == "approve" else "❌ Invoice Rejected",
            "message": f"Invoice {result.invoice.invoice_number} processed via Telegram.",
            "entity_type": "invoice",
            "entity_id": result.invoice.id,
            "processed_by": "telegram",
            "severity": "success" if action == "approve" else "error",
        })

        if action == "approve":
            for update in result.product_updates:
                await broadcast_to_web_ui({
                    "type": "product_updated_from_invoice",
                    "title": "📦 Product Updated",
                    "message": (
                        f"'{update.name}': "
                        f"{update.old_quantity} → {update.new_quantity}"
                    ),
                    "entity_type": "product",
                    "entity_id": update.product_id,
                    "severity": "success",
                })

        await send_invoice_status(
            action,
            result.invoice.invoice_number,
            note="Inventory updated" if action == "approve" else "",
        )

    # ── Edit all related Telegram notifications to remove buttons ──────────────────
    from app.services.telegram_service import sync_invoice_notifications
    import asyncio
    
    asyncio.create_task(sync_invoice_notifications(invoice_id, response_text))

    # Still need to answer the callback query for the user who clicked it
    # We can use the current bot_token for this user
    from models import InvoiceNotification
    notif = db.query(InvoiceNotification).filter(
        InvoiceNotification.invoice_id == invoice_id,
        InvoiceNotification.chat_id == str(chat_id)
    ).first()
    
    bot_token = notif.bot_token if notif else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if bot_token:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{TELEGRAM_API_URL}/bot{bot_token}/answerCallbackQuery",
                json={"callback_query_id": callback_id},
            )

    logger.info("Telegram callback handled — invoice %s %sd", invoice_id, action)
    return {"status": "ok"}


async def process_invoice_action_from_web(
    invoice_id: int,
    action: str,
    db: Session,
) -> dict:
    """
    Called by the web router when a user acts on an invoice from the Web UI.
    Delegates to InvoiceService and optionally edits the Telegram message.

    Returns a dict for backward compatibility with callers that check
    result["status"] and result["invoice"].
    """
    if action == "approve":
        result = InvoiceService(db).approve(invoice_id, source="web")
    else:
        result = InvoiceService(db).reject(invoice_id, source="web")

    # Translate typed result back to dict for backward compatibility
    if not result.ok and not result.already_processed:
        return {"status": "error", "msg": result.message}

    if result.already_processed:
        return {
            "status": "already_processed",
            "msg": result.message,
            "invoice": result.invoice,
            "processed_by": result.processed_by,
        }

    # Side effects
    event = "invoice_approved" if action == "approve" else "invoice_rejected"
    await broadcast_to_web_ui({
        "type": event,
        "title": "✅ Invoice Approved" if action == "approve" else "❌ Invoice Rejected",
        "message": f"Invoice {result.invoice.invoice_number} processed from Web UI.",
        "entity_type": "invoice",
        "entity_id": result.invoice.id,
        "processed_by": "web",
        "severity": "success" if action == "approve" else "error",
    })

    await send_invoice_status(
        action,
        result.invoice.invoice_number,
        note="Inventory updated" if action == "approve" else "",
    )

    # Edit all Telegram approval messages
    from app.services.telegram_service import sync_invoice_notifications
    import asyncio
    
    response_text = (
        f"✅ <b>Approved</b> invoice {result.invoice.invoice_number}.\n\nInventory updated."
        if action == "approve"
        else f"❌ <b>Rejected</b> invoice {result.invoice.invoice_number}."
    )
    
    asyncio.create_task(sync_invoice_notifications(invoice_id, response_text))

    return {
        "status": "ok",
        "invoice": result.invoice,
        "product_updates": result.product_updates,
        "processed_by": result.processed_by,
    }


# ── Account management commands ───────────────────────────────────────────────

async def handle_account_command(text: str, chat_id: int, db: Session) -> dict:
    command, _ = _parse_command(text)
    
    if command in ("/help", "/start", ""):
        await send_message("Welcome to the Tool ORC Telegram Bot!\nThis bot will notify you of invoice updates.", chat_id=str(chat_id))
        return {"status": "ok"}
        
    await send_message("❓ Unknown command.", chat_id=str(chat_id))
    return {"status": "unknown_command"}

