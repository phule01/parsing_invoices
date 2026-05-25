"""
telegram_utils.py — compatibility shim.

This file re-exports everything that was previously defined here from its
new home in app/services/telegram_service.py.

Purpose: avoid touching every file that imports from telegram_utils
before you are ready to do a final search-and-replace. Once all imports
across the codebase point to app.services.telegram_service, delete this file.

Migration checklist — files still importing from telegram_utils:
  - emails.py                (broadcast_to_web_ui, send_invoice_approval_request,
                               send_telegram_message)
  - invoices_v2.py           (being deleted)
  - products_v2.py           (now imports from app.services.telegram_service)
  - main.py                  (get_telegram_status)
  - sync.py                  (send_invoice_approval_request_sync — removed)
"""

from app.services.telegram_service import (           # noqa: F401
    send_message as send_telegram_message,
    send_message_with_metadata as send_telegram_message_with_result,
    edit_message as edit_telegram_message,
    broadcast_to_web_ui,
    send_invoice_approval_request,
    send_invoice_status as send_invoice_approval_status,
    send_invoice_status as send_invoice_received_notification,
    send_error_notification,
    send_parse_failure_notification,
    get_telegram_status,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_API_URL,
)

# The sync wrappers below are intentionally not re-exported.
# FastAPI's BackgroundTasks.add_task() accepts async callables directly.
# If you have code that calls these, update it to pass the async function:
#
#   OLD:  background_tasks.add_task(send_invoice_approval_request_sync, ...)
#   NEW:  background_tasks.add_task(send_invoice_approval_request, ...)
