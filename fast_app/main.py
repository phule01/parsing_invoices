"""
FastAPI application entry point.

Router registration changes in this refactor
─────────────────────────────────────────────
REMOVED (safe to delete the source files after confirming this works):
  - invoices_v2.py         → replaced by app/routers/invoices.py
  - invoices_actions.py    → merged into app/routers/invoices.py
  - sync.py (invoice part) → invoice endpoints removed; keep sync.py only
                              if you still use its non-invoice routes

ADDED:
  - app.routers.invoices   → single unified invoice router
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import logging
import time
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError
import httpx

from database import engine, Base

# ── Routers ───────────────────────────────────────────────────────────────────
# Import the new unified invoice router first so it is explicit.
from app.routers.invoices import router as invoices_router

# These routers are unchanged — kept as-is until their own refactor pass.
from router import (
    reports,
    emails,
    auth_router,
    products_v2,
    websocket_router,
    telegram_router,
    settings,
)

from telegram_utils import get_telegram_status

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# ── Database setup ────────────────────────────────────────────────────────────

def create_tables_with_retry(max_retries: int = 10, retry_delay: int = 2) -> None:
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables ready")
            return
        except OperationalError as exc:
            if attempt < max_retries - 1:
                logger.warning(
                    "⏳ DB connection attempt %d/%d failed — retrying in %ds: %s",
                    attempt + 1, max_retries, retry_delay, str(exc)[:100],
                )
                time.sleep(retry_delay)
            else:
                logger.error("❌ Could not connect to database after %d attempts", max_retries)
                raise


create_tables_with_retry()


# ── Application ───────────────────────────────────────────────────────────────

async def setup_telegram_webhook():
    """
    Try to set up the Telegram webhook on startup.
    This is optional — if it fails, the app continues to work (though callbacks won't arrive).
    For local development, you may need to use ngrok or another tunneling service.
    """
    from app.services.telegram_service import TELEGRAM_API_URL
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        logger.debug("⏭️  Skipping Telegram webhook setup — no bot token configured")
        return

    webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
    if not webhook_url:
        logger.warning(
            "⚠️  TELEGRAM_WEBHOOK_URL not set. Telegram callbacks won't work.\n"
            "   Set TELEGRAM_WEBHOOK_URL in .env to enable (e.g., https://your-domain.com/api/telegram/webhook)"
        )
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{TELEGRAM_API_URL}/bot{bot_token}/setWebhook",
                json={"url": webhook_url},
            )
            data = resp.json()
            if data.get("ok"):
                logger.info(f"✅ Telegram webhook set to: {webhook_url}")
            else:
                logger.error(f"❌ Failed to set Telegram webhook: {data.get('description')}")
    except Exception as exc:
        logger.error(f"❌ Error setting up Telegram webhook: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    await setup_telegram_webhook()
    yield
    logger.info("Application shutting down...")


api = FastAPI(
    title="Tool ORC Invoice API",
    description="Invoice management system with email integration",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# ── IMPORTANT: the FastAPI instance is named `api`, not `app`.
# The name `app` is reserved for the app/ Python package
# (app/core/security.py, app/services/invoice_service.py, etc.).
# uvicorn is told to use "main:api" in the CMD below.

# CORS
_cors_origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:8080",
]
# Add dynamic origins from environment (e.g., Cloudflare Tunnel domain)
for _env_key in ("FRONTEND_URL", "CORS_ALLOWED_ORIGIN", "REACT_APP_API_URL"):
    _val = os.getenv(_env_key, "")
    if _val and _val not in _cors_origins:
        _cors_origins.append(_val)

api.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router registration ───────────────────────────────────────────────────────

api.include_router(auth_router.router,      tags=["Authentication"])
api.include_router(invoices_router,         tags=["Invoices"])
api.include_router(products_v2.router,      tags=["Products"])
api.include_router(websocket_router.router, tags=["WebSocket"])
api.include_router(telegram_router.router,  tags=["Telegram"])
api.include_router(settings.router,         tags=["Settings"])
api.include_router(reports.router,   prefix="/api/reports",  tags=["Reports"])
api.include_router(emails.router,    prefix="/api/emails",   tags=["Emails"])

# ── Static files ──────────────────────────────────────────────────────────────

static_dir = Path(__file__).parent.parent / "web_ui"
if static_dir.exists():
    api.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")


# ── Standard endpoints ────────────────────────────────────────────────────────

@api.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Tool ORC Invoice API"}


@api.get("/api/telegram/status")
async def telegram_status():
    return await get_telegram_status()


@api.get("/")
async def root():
    return {
        "message": "Tool ORC Invoice API",
        "version": "2.0.0",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:api",   # ← was "main:app"
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("DEBUG", "False").lower() == "true",
    )
