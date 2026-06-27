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
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_API_URL,
    TELEGRAM_CHAT_ID,
    send_message,
    edit_message,
    broadcast_to_web_ui,
    send_invoice_status,
)
from telegram_conversation import (
    start_conversation, get_conversation_state, get_conversation_data,
    update_conversation_data, end_conversation,
    STATE_IDLE, STATE_ADD_USERNAME, STATE_ADD_EMAIL, STATE_ADD_PASSWORD, STATE_ADD_ROLE,
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
    return bool(TELEGRAM_CHAT_ID) and str(chat_id) == str(TELEGRAM_CHAT_ID)


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

    # ── Edit the original Telegram message to remove buttons ──────────────────
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "error", "msg": "TELEGRAM_BOT_TOKEN not configured"}

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": response_text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": []},
            },
        )
        await client.post(
            f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
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

    # Edit the original Telegram approval message if we stored its ID
    telegram_info = {}
    if isinstance(result.invoice.signatures, dict):
        telegram_info = result.invoice.signatures.get("telegram", {})

    tg_chat_id = telegram_info.get("chat_id")
    tg_message_id = telegram_info.get("message_id")
    response_text = (
        f"✅ <b>Approved</b> invoice {result.invoice.invoice_number}.\n\nInventory updated."
        if action == "approve"
        else f"❌ <b>Rejected</b> invoice {result.invoice.invoice_number}."
    )

    if tg_chat_id and tg_message_id:
        await edit_message(
            chat_id=str(tg_chat_id),
            message_id=int(tg_message_id),
            text=response_text,
            reply_markup={"inline_keyboard": []},
        )
    else:
        await send_message(response_text)

    return {
        "status": "ok",
        "invoice": result.invoice,
        "product_updates": result.product_updates,
        "processed_by": result.processed_by,
    }


# ── Account management commands ───────────────────────────────────────────────

async def handle_account_command(text: str, chat_id: int, db: Session) -> dict:
    if not _is_authorized_chat(chat_id):
        return {"status": "unauthorized"}

    command, _ = _parse_command(text)
    current_state = get_conversation_state(chat_id)

    # Cancel any active conversation
    if command == "/cancel" or text.strip().lower() == "cancel":
        end_conversation(chat_id)
        await send_message("❌ Operation cancelled.", chat_id=str(chat_id))
        return {"status": "ok"}

    # Top-level commands
    if command in ("/help", "/start", ""):
        end_conversation(chat_id)
        await send_message(USAGE_TEXT, chat_id=str(chat_id))
        return {"status": "ok"}

    if command == "/listaccount":
        end_conversation(chat_id)
        users = db.query(User).order_by(User.created_at.asc()).all()
        if not users:
            msg = "No accounts found."
        else:
            admins = [u for u in users if u.is_admin]
            standard = [u for u in users if not u.is_admin]
            
            msg = "<b>👥 Accounts Overview</b>\n\n"
            msg += "<b>👑 Admin Accounts</b>\n"
            if admins:
                msg += "\n".join([f"• {u.username} | {u.email} | {'✅ Active' if u.is_active else '❌ Inactive'}" for u in admins])
            else:
                msg += "<i>None</i>"
                
            msg += "\n\n<b>👤 Standard Users</b>\n"
            if standard:
                msg += "\n".join([f"• {u.username} | {u.email} | {'✅ Active' if u.is_active else '❌ Inactive'}" for u in standard])
            else:
                msg += "<i>None</i>"
                
        await send_message(msg, chat_id=str(chat_id))
        return {"status": "ok"}

    if command == "/listinvoices":
        end_conversation(chat_id)
        invoices = db.query(Invoice).order_by(Invoice.created_at.desc()).limit(50).all()
        if not invoices:
            msg = "📄 <b>No invoices found</b>"
        else:
            STATUS_EMOJI = {"pending": "⏳", "verified": "✅", "rejected": "❌", "synced": "📤"}
            lines = ["📄 <b>All Invoices</b>\n"]
            for inv in invoices:
                date_str = inv.invoice_date.strftime("%d/%m/%Y") if inv.invoice_date else "N/A"
                emoji = STATUS_EMOJI.get(inv.status, "❓")
                lines.append(
                    f"{emoji} <b>{inv.invoice_number}</b>\n"
                    f"   └─ Buyer: {inv.buyer_name}\n"
                    f"   └─ Amount: {inv.total_amount:,.0f} VND | {date_str}\n"
                )
            msg = "\n".join(lines)
        await send_message(msg, chat_id=str(chat_id))
        return {"status": "ok"}

    if command == "/listproducts":
        end_conversation(chat_id)
        products = (
            db.query(Product)
            .filter(Product.quantity_in_stock > 0)
            .order_by(Product.created_at.desc())
            .limit(50)
            .all()
        )
        if not products:
            msg = "📦 <b>No active products found</b>"
        else:
            lines = ["📦 <b>Active Products (Stock > 0)</b>\n"]
            for p in products:
                lines.append(
                    f"• <b>{p.name}</b>\n"
                    f"   └─ Price: {p.price:,.0f} VND | Stock: {p.quantity_in_stock}\n"
                )
            msg = "\n".join(lines)
        await send_message(msg, chat_id=str(chat_id))
        return {"status": "ok"}

    # Multi-step flows
    if command == "/addaccount" or current_state in (
        STATE_ADD_USERNAME, STATE_ADD_EMAIL, STATE_ADD_PASSWORD, STATE_ADD_ROLE
    ):
        return await _add_account_flow(text, chat_id, db)

    if command == "/deleteaccount" or current_state == STATE_DELETE_USERNAME:
        return await _delete_account_flow(text, chat_id, db)

    if command == "/changepassword" or current_state in (
        STATE_CHANGE_USERNAME, STATE_CHANGE_PASSWORD
    ):
        return await _change_password_flow(text, chat_id, db)

    if current_state == STATE_IDLE:
        await send_message(
            f"❓ Unknown command: <b>{command}</b>\n\n{USAGE_TEXT}",
            chat_id=str(chat_id),
        )
    return {"status": "unknown_command"}


# ── Multi-step account flows ──────────────────────────────────────────────────

async def _add_account_flow(text: str, chat_id: int, db: Session) -> dict:
    state = get_conversation_state(chat_id)

    if state == STATE_IDLE:
        start_conversation(chat_id, STATE_ADD_USERNAME)
        await send_message(
            "📝 <b>Add New Account</b>\n\nStep 1️⃣: Enter the <b>username</b>",
            chat_id=str(chat_id),
        )
        return {"status": "ok"}

    if state == STATE_ADD_USERNAME:
        username = text.strip()
        if len(username) < 3:
            await send_message("❌ Username must be at least 3 characters.\n\nPlease try again:", chat_id=str(chat_id))
            return {"status": "invalid"}
        if db.query(User).filter(User.username == username).first():
            await send_message(f"❌ Username '<b>{username}</b>' already exists.\n\nTry another:", chat_id=str(chat_id))
            return {"status": "exists"}
        update_conversation_data(chat_id, "username", username)
        start_conversation(chat_id, STATE_ADD_EMAIL, get_conversation_data(chat_id))
        await send_message(f"✅ Username: <b>{username}</b>\n\nStep 2️⃣: Enter the <b>email address</b>", chat_id=str(chat_id))
        return {"status": "ok"}

    if state == STATE_ADD_EMAIL:
        email = text.strip()
        if "@" not in email or "." not in email:
            await send_message("❌ Please enter a valid email address.\n\nTry again:", chat_id=str(chat_id))
            return {"status": "invalid"}
        if db.query(User).filter(User.email == email).first():
            await send_message(f"❌ Email '<b>{email}</b>' already exists.\n\nTry another:", chat_id=str(chat_id))
            return {"status": "exists"}
        update_conversation_data(chat_id, "email", email)
        start_conversation(chat_id, STATE_ADD_PASSWORD, get_conversation_data(chat_id))
        await send_message(f"✅ Email: <b>{email}</b>\n\nStep 3️⃣: Enter the <b>password</b>", chat_id=str(chat_id))
        return {"status": "ok"}

    if state == STATE_ADD_PASSWORD:
        password = text.strip()
        if len(password) < 4:
            await send_message("❌ Password must be at least 4 characters.\n\nTry again:", chat_id=str(chat_id))
            return {"status": "invalid"}
        update_conversation_data(chat_id, "password", password)
        start_conversation(chat_id, STATE_ADD_ROLE, get_conversation_data(chat_id))
        
        # Create an inline keyboard to choose the role (or just text reply)
        # We will just ask for text reply for simplicity and consistency with other states.
        await send_message(
            f"✅ Password set\n\nStep 4️⃣: Should this account be an Admin?\nReply with <b>yes</b> or <b>no</b>:", 
            chat_id=str(chat_id)
        )
        return {"status": "ok"}
        
    if state == STATE_ADD_ROLE:
        role_resp = text.strip().lower()
        if role_resp not in ("yes", "no", "y", "n"):
            await send_message("❌ Please reply with 'yes' or 'no':", chat_id=str(chat_id))
            return {"status": "invalid"}
            
        is_admin = role_resp in ("yes", "y")
        
        data = get_conversation_data(chat_id)
        new_user = User(
            username=data["username"],
            email=data["email"],
            hashed_password=hash_password(data["password"]),
            is_active=True,
            is_admin=is_admin,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        end_conversation(chat_id)
        
        role_str = "👑 Admin" if is_admin else "👤 Standard User"
        await send_message(
            f"✅ <b>Account Created!</b>\n\nUsername: <b>{data['username']}</b>\nEmail: <b>{data['email']}</b>\nRole: <b>{role_str}</b>",
            chat_id=str(chat_id),
        )
        return {"status": "ok", "user_id": new_user.id}

    return {"status": "error"}


async def _delete_account_flow(text: str, chat_id: int, db: Session) -> dict:
    state = get_conversation_state(chat_id)

    if state == STATE_IDLE:
        start_conversation(chat_id, STATE_DELETE_USERNAME)
        await send_message("🗑 <b>Delete Account</b>\n\nStep 1️⃣: Enter the <b>username</b> to delete", chat_id=str(chat_id))
        return {"status": "ok"}

    if state == STATE_DELETE_USERNAME:
        username = text.strip()
        user = db.query(User).filter(User.username == username).first()
        if not user:
            await send_message(f"❌ User '<b>{username}</b>' not found.\n\nTry again or /cancel:", chat_id=str(chat_id))
            return {"status": "not_found"}
        user.is_active = False
        db.commit()
        end_conversation(chat_id)
        await send_message(f"✅ <b>Account Deactivated!</b>\n\nUser '<b>{username}</b>' is now inactive.", chat_id=str(chat_id))
        return {"status": "ok"}

    return {"status": "error"}


async def _change_password_flow(text: str, chat_id: int, db: Session) -> dict:
    state = get_conversation_state(chat_id)

    if state == STATE_IDLE:
        start_conversation(chat_id, STATE_CHANGE_USERNAME)
        await send_message("🔑 <b>Change Password</b>\n\nStep 1️⃣: Enter the <b>username</b>", chat_id=str(chat_id))
        return {"status": "ok"}

    if state == STATE_CHANGE_USERNAME:
        username = text.strip()
        user = db.query(User).filter(User.username == username).first()
        if not user:
            await send_message(f"❌ User '<b>{username}</b>' not found.\n\nTry again or /cancel:", chat_id=str(chat_id))
            return {"status": "not_found"}
        update_conversation_data(chat_id, "username", username)
        start_conversation(chat_id, STATE_CHANGE_PASSWORD, get_conversation_data(chat_id))
        await send_message(f"✅ Username: <b>{username}</b>\n\nStep 2️⃣: Enter the <b>new password</b>", chat_id=str(chat_id))
        return {"status": "ok"}

    if state == STATE_CHANGE_PASSWORD:
        password = text.strip()
        if len(password) < 4:
            await send_message("❌ Password must be at least 4 characters.\n\nTry again:", chat_id=str(chat_id))
            return {"status": "invalid"}
        data = get_conversation_data(chat_id)
        user = db.query(User).filter(User.username == data.get("username")).first()
        if not user:
            end_conversation(chat_id)
            await send_message("❌ User not found. Operation cancelled.", chat_id=str(chat_id))
            return {"status": "not_found"}
        user.hashed_password = hash_password(password)
        db.commit()
        end_conversation(chat_id)
        await send_message(f"✅ <b>Password Updated!</b>\n\nPassword for '<b>{data['username']}</b>' has been changed.", chat_id=str(chat_id))
        return {"status": "ok"}

    return {"status": "error"}
