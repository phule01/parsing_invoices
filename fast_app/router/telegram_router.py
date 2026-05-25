import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from database import get_db
from telegram_handlers import handle_account_command, handle_invoice_callback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Telegram webhook endpoint.
    Handles callback queries (invoice approve/reject) and admin account commands.
    """
    data = await request.json()

    if "callback_query" in data:
        callback = data["callback_query"]
        callback_data = callback.get("data", "")
        callback_id = callback.get("id", "")
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")

        if not (callback_data and callback_id and chat_id and message_id):
            return {"status": "error", "msg": "Invalid callback payload"}

        return await handle_invoice_callback(
            callback_data=callback_data,
            callback_id=callback_id,
            chat_id=chat_id,
            message_id=message_id,
            db=db,
        )

    if "message" in data:
        message = data["message"]
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not (text and chat_id):
            return {"status": "ignored"}

        return await handle_account_command(text=text, chat_id=chat_id, db=db)

    return {"status": "ignored"}
