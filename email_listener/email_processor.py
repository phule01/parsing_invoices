"""
Email Processor (Simplified) – Extract PDF/XML → Gemini → Database

Simple flow:
1. Connect to Gmail IMAP, get unread emails
2. Extract PDF/XML attachments only (no Selenium)
3. Send each file to Gemini API for parsing
4. Store as PENDING invoices in database
5. Wait for approval in Telegram/Web UI before creating products
6. Mark email as read, loop every 5 minutes
"""

import asyncio
import imaplib
import logging
import os
import time
import uuid
from datetime import datetime
from email import message_from_bytes
from email.header import decode_header
from typing import Optional

import httpx
from dotenv import load_dotenv

from attachment_handler import extract_attachments_from_email, get_email_body
from ai_parser import parse_invoice_file
from pipeline_manager import AsyncPipeline, FileStatus

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("email_processor")

# ── Config ────────────────────────────────────────────────────────────────────
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", 300))  # 5 minutes
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/invoices")
API_BASE_URL = os.getenv("API_BASE_URL", "http://fastapi:8000")
API_USERNAME = os.getenv("API_USERNAME", "admin")
API_PASSWORD = os.getenv("API_PASSWORD", "admin")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ── Global Pipeline Instance ─────────────────────────────────────────────────
# Sequential parsing: Parse → Notify → (user approves via Telegram) → Add Products
pipeline = AsyncPipeline(max_parsing_workers=1, max_product_workers=1)


class APIClient:
    """Simple API client for FastAPI backend."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = None

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def authenticate(self) -> bool:
        """Get access token from API."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/auth/login",
                    json={"username": self.username, "password": self.password},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("access_token")
                    logger.info(f"✅ Authentication successful")
                    return True
                logger.error(f"❌ Auth failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return False
    async def get_system_settings(self) -> dict:
        """Fetch system settings (email, token, etc) from the database."""
        try:
            expected_secret = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-use-random-32-chars")
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/api/settings/system",
                    headers={"X-Internal-Secret": expected_secret},
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Failed to fetch system settings: [{resp.status_code}]")
        except Exception as e:
            logger.error(f"Error fetching system settings: {e}")
        return {}
    async def get_processed_message_ids(self) -> set:
        """Get list of already-processed email message IDs."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/api/emails/logs?limit=10000",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    logs = resp.json()
                    return {log.get("message_id") for log in logs if log.get("message_id")}
        except Exception as e:
            logger.warning(f"Failed to fetch processed message IDs: {e}")
        return set()

    async def create_email_log(self, log_data: dict) -> int | None:
        """Log email processing attempt."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/emails/log",
                    json=log_data,
                    headers=self._headers(),
                )
                if resp.status_code in (200, 201):
                    return resp.json().get("id")
        except Exception as e:
            logger.warning(f"Failed to create email log: {e}")
        return None

    async def create_invoice(self, invoice_data: dict) -> dict | None:
        """Create pending invoice (status='pending')."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/invoices/",
                    json=invoice_data,
                    headers=self._headers(),
                )
                if resp.status_code in (200, 201):
                    logger.info(f"✅ Invoice created: {invoice_data.get('invoice_number')}")
                    return resp.json()
                if resp.status_code == 400 and "already exists" in resp.text:
                    logger.info(f"ℹ️  Invoice already exists: {invoice_data.get('invoice_number')}")
                    return None
                logger.error(f"❌ Create invoice failed [{resp.status_code}]: {resp.text}")
        except Exception as e:
            logger.error(f"API error: {e}")
        return None

    async def notify_invoice_received(self, invoice_number: str, seller: str, amount: float, invoice_id: int, items: list = None) -> bool:
        """Send Telegram and Web UI notification for new invoice with approval buttons and item details."""
        try:
            # Format items for display
            items_text = ""
            if items:
                items_text = "\n\n📦 Items:\n"
                for item in items[:3]:  # Show first 3 items
                    name = item.get("item_name", "Unknown")[:40]  # Truncate long names
                    qty = item.get("quantity", 0)
                    price = item.get("total_price", 0)
                    items_text += f"  • {name}\n    Qty: {qty}, Price: ${price:,.0f}\n"
                if len(items) > 3:
                    items_text += f"  ... and {len(items) - 3} more items"
            
            message = f"Invoice {invoice_number} from {seller}\nTotal: ${amount:,.2f}{items_text}"
            
            notification_data = {
                "type": "invoice_received",
                "title": "📬 New Invoice - Pending Approval",
                "message": message,
                "invoice_number": invoice_number,
                "seller": seller,
                "amount": amount,
                "invoice_id": invoice_id,
                "items": items,
                "severity": "warning",
                "action_required": True
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/emails/notifications/broadcast",
                    json=notification_data,
                    headers=self._headers(),
                )
                if resp.status_code in (200, 201):
                    logger.info(f"✅ Notification with approval buttons sent for invoice {invoice_number}")
                    return True
                logger.warning(f"⚠️  Notification failed [{resp.status_code}]")
        except Exception as e:
            logger.warning(f"Notification error: {e}")
        return False
    
    async def notify_file_failure(self, notification_data: dict) -> bool:
        """Send failure notification to user."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/api/emails/notifications/broadcast",
                    json=notification_data,
                    headers=self._headers(),
                )
                if resp.status_code in (200, 201):
                    logger.info(f"✅ Failure notification sent")
                    return True
                logger.warning(f"⚠️  Failure notification failed [{resp.status_code}]")
        except Exception as e:
            logger.warning(f"Notification error: {e}")
        return False


def normalize_vietnamese(s: str) -> str:
    """Remove accents and normalize string for robust matching."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace('đ', 'd').replace('Đ', 'D').lower()

def _is_invoice_email(subject: str, body: str, has_attachments: bool = False) -> bool:
    """
    Check if email is likely an invoice based on subject keywords.
    Returns True ONLY if email has PDF/XML attachments AND subject matches.
    """
    if not has_attachments:
        return False
        
    DEFAULT_KEYWORDS = "hóa đơn,hoa don,hoadon,hoa_don,hóa đơn điện tử,hoa don dien tu,hoadondientu,hđđt,hddt,invoice,einvoice,e-invoice,receipt,ebill,e-bill,biên lai,bien lai,bienlai,thanh toán,thanh toan,thanhtoan,cước,cuoc,vat,gtgt,chứng từ,chung tu"
    keywords_str = os.getenv("INVOICE_SUBJECT_KEYWORDS", DEFAULT_KEYWORDS)
    if keywords_str:
        keywords = [normalize_vietnamese(k.strip()) for k in keywords_str.split(",") if k.strip()]
        if keywords:
            subject_normalized = normalize_vietnamese(subject)
            if not any(k in subject_normalized for k in keywords):
                return False
                
    return True


def decode_subject(subject_header):
    """Decode email subject."""
    if not subject_header:
        return ""
    try:
        decoded = decode_header(str(subject_header))
        result = ""
        for part, encoding in decoded:
            if isinstance(part, bytes):
                result += part.decode(encoding or "utf-8", errors="ignore")
            else:
                result += str(part)
        return result
    except Exception:
        return str(subject_header)


def _has_invoice_attachments(msg) -> bool:
    """Check if email has PDF/XML attachments that could be invoices."""
    try:
        attachment_count = 0
        invoice_attachment_count = 0
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            filename = part.get_filename()
            if filename:
                attachment_count += 1
                ext = filename.lower().split('.')[-1]
                if ext in ('pdf', 'xml', 'zip', 'png', 'jpg', 'jpeg', 'tiff', 'bmp', 'gif'):
                    invoice_attachment_count += 1
                    logger.debug(f"Found invoice attachment: {filename}")
        
        if invoice_attachment_count > 0:
            return True
        
        if attachment_count > 0:
            logger.debug(f"Email has {attachment_count} attachment(s) but no PDF/XML/ZIP files")
    except Exception as e:
        logger.debug(f"Error checking attachments: {e}")
    return False



# ── Pipeline Callbacks ────────────────────────────────────────────────────────

async def on_file_parsed(file_path: str, parsed_data: dict):
    """Callback invoked when a file is successfully parsed by the pipeline."""
    logger.info(f"✅ Pipeline: file parsed successfully: {os.path.basename(file_path)}")


async def on_file_failed(file_path: str, error: Exception):
    """Callback invoked when a file exhausts all parse retries."""
    logger.error(f"❌ Pipeline: file failed permanently: {os.path.basename(file_path)} — {error}")
    api = APIClient(API_BASE_URL, API_USERNAME, API_PASSWORD)
    await api.notify_file_failure(
        {
            "type": "parse_failure",
            "title": "📄 Invoices Can't Parsing",
            "message": f"Can't parsing {os.path.basename(file_path)}",
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "error_message": str(error),
            "severity": "error",
            "action_required": False,
        }
    )


# ── Pipeline Worker Functions ─────────────────────────────────────────────────

async def send_invoice_notification(invoice_data: dict) -> bool:
    """
    Notify worker function: create invoice in DB, then send approval notification.
    Called by the pipeline notification worker after parsing succeeds.
    
    Returns:
        bool: True if invoice was successfully created, False otherwise.
              If False, the pipeline will NOT enqueue for product addition.
    """
    api = APIClient(API_BASE_URL, API_USERNAME, API_PASSWORD)
    if not await api.authenticate():
        logger.error("send_invoice_notification: failed to authenticate")
        return False
    
    # Step 1: Create invoice in database
    seller = invoice_data.get("seller") or {}
    buyer = invoice_data.get("buyer") or {}
    
    invoice_create_data = {
        "invoice_series": invoice_data.get("invoice_series"),
        "invoice_number": invoice_data.get("invoice_number", "N/A"),
        "invoice_date": invoice_data.get("invoice_date"),
        "lookup_code": invoice_data.get("lookup_code"),
        "tax_authority_code": invoice_data.get("tax_authority_code"),
        "seller_name": seller.get("name") or invoice_data.get("seller_name"),
        "seller_tax_code": seller.get("tax_code"),
        "seller_phone": seller.get("phone"),
        "seller_address": seller.get("address"),
        "buyer_name": buyer.get("name") or invoice_data.get("buyer_name"),
        "buyer_tax_code": buyer.get("tax_code"),
        "buyer_address": buyer.get("address"),
        "total_before_tax": invoice_data.get("total_before_tax", 0),
        "vat_rate": invoice_data.get("vat_rate", 0),
        "vat_amount": invoice_data.get("vat_amount", 0),
        "total_amount": invoice_data.get("total_amount", 0),
        "source_type": "email",
        "items": invoice_data.get("items", []),
    }
    
    created_invoice = await api.create_invoice(invoice_create_data)
    if created_invoice:
        invoice_id = created_invoice.get("id")
        logger.info(f"✅ Invoice saved to DB with ID {invoice_id} and approval notification sent")
        return True  # Success: proceed to product addition on user approval
    else:
        logger.warning(f"⚠️  Failed to save invoice {invoice_data.get('invoice_number')} to DB")
        return False  # Failure: do NOT proceed to product addition
    
    # NOTE: Telegram/Web notification is automatically sent by the create_invoice endpoint,
    # so we don't call api.notify_invoice_received() separately to avoid duplicate notifications


async def add_invoice_products(invoice_data: dict):
    """
    Product worker function: called after user approves an invoice via Telegram/Web UI.
    Extend this with your backend product-creation API calls as needed.
    """
    invoice_number = invoice_data.get("invoice_number", "N/A")
    items = invoice_data.get("items", [])
    logger.info(f"📦 Adding {len(items)} product(s) for approved invoice {invoice_number}")
    # TODO: call your product-creation endpoint here, e.g.:
    # api = APIClient(API_BASE_URL, API_USERNAME, API_PASSWORD)
    # await api.authenticate()
    # for item in items:
    #     await api.create_product(item)


# ── Email Fetching & Processing ───────────────────────────────────────────────

async def fetch_unread_emails(mail, processed_ids: set) -> list:
    """
    Search for UNSEEN (unread) emails in the open IMAP connection and return those
    that look like invoice emails and have not been processed before.

    Returns a list of (eid, message_id, sender, subject, msg) tuples.
    """
    emails = []
    skipped_already_processed = 0
    skipped_no_attachments = 0
    try:
        try:
            # Try Gmail-specific search first to exclude spam tabs
            status, email_ids = mail.search(None, 'X-GM-RAW', '"-category:promotions -category:social"')
            if status != "OK":
                # Fallback to standard ALL if X-GM-RAW fails
                status, email_ids = mail.search(None, "ALL")
        except Exception:
            status, email_ids = mail.search(None, "ALL")
            
        if status != "OK":
            logger.warning("IMAP search returned non-OK status")
            return emails

        email_list = email_ids[0].split()[-10:]  # Get last 10 emails (most recent)
        logger.info(f"📬 {len(email_list)} emails found (checking against processed list)")

        for eid in email_list:
            try:
                # 1. Fetch only headers first to save bandwidth
                status, header_data = mail.fetch(eid, "(BODY.PEEK[HEADER])")
                if status != "OK":
                    logger.debug(f"Failed to fetch headers for email {eid.decode()}")
                    continue

                header_msg = message_from_bytes(header_data[0][1])
                message_id = header_msg.get("Message-ID", f"<no-id-{eid.decode()}>")

                if message_id in processed_ids:
                    logger.debug(f"Skipping already-processed: {message_id}")
                    skipped_already_processed += 1
                    continue

                sender = header_msg.get("From", "")
                subject = decode_subject(header_msg.get("Subject", ""))

                # 2. Fast rejection: Check subject BEFORE downloading huge attachments
                if not _is_invoice_email(subject, "", has_attachments=True):
                    skipped_no_attachments += 1
                    logger.info(f"⏭️  Skip (subject mismatch): {subject[:60]}")
                    continue

                # 3. Only if subject matches, download the FULL email to get attachments
                status, full_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    logger.warning(f"Failed to fetch full body for email {eid.decode()}")
                    continue
                    
                msg = message_from_bytes(full_data[0][1])
                body = get_email_body(msg)
                has_attachments = _has_invoice_attachments(msg)

                if has_attachments:
                    emails.append((eid, message_id, sender, subject, msg))
                    logger.info(f"✅ Found invoice email: {subject[:60]} from {sender[:40]}")
                else:
                    skipped_no_attachments += 1
                    logger.info(f"⏭️  Skip (subject matched but no attachments): {subject[:60]}")

            except Exception as e:
                logger.error(f"Error fetching email id={eid}: {e}")

    except Exception as e:
        logger.error(f"IMAP search error: {e}")

    logger.info(f"📊 Email scan summary: {len(emails)} invoice emails | {skipped_already_processed} already processed | {skipped_no_attachments} no attachments")
    return emails


def _check_and_store_file_hash(file_path: str) -> bool:
    """
    Check if the SHA-256 hash of the file exists in the persistent JSON storage.
    If it does, return True (is duplicate).
    If it doesn't, add it and return False (is new).
    """
    import hashlib
    import json
    
    hash_file = "/app/invoices/processed_hashes.json"
    
    try:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()
        
        hashes = []
        if os.path.exists(hash_file):
            try:
                with open(hash_file, "r") as f:
                    hashes = json.load(f)
            except Exception:
                hashes = []
                
        if file_hash in hashes:
            return True
            
        hashes.append(file_hash)
        with open(hash_file, "w") as f:
            json.dump(hashes, f)
            
        return False
    except Exception as e:
        logger.error(f"Error in file hashing: {e}")
        return False

async def process_single_email(eid, message_id: str, sender: str, subject: str, msg, mail, api: APIClient):
    """
    Full processing pipeline for one email:
      1. Log the email to the backend
      2. Extract PDF/XML attachments
      3. Queue each file for parsing in the async pipeline
      4. Mark the email as read so the listener can continue immediately
    """
    # 1. Log email
    log_data = {
        "message_id": message_id,
        "sender": sender,
        "subject": subject,
        "status": "processing",
        "received_at": datetime.utcnow().isoformat(),
    }
    log_id = await api.create_email_log(log_data)

    # 2. Extract attachments
    files = extract_attachments_from_email(msg, message_id)
    if not files:
        logger.info(f"No invoice attachments in: {subject[:60]}")
        mail.store(eid, "+FLAGS", "\\Seen")
        return

    # 3. Queue files for asynchronous parsing so one bad file does not block the mail loop
    for file_path in files:
        if _check_and_store_file_hash(file_path):
            logger.info(f"⏭️  Duplicate file skipped (hash already processed): {os.path.basename(file_path)}")
            continue
            
        try:
            await pipeline.enqueue_file(
                file_path,
                metadata={
                    "message_id": message_id,
                    "sender": sender,
                    "subject": subject,
                    "email_log_id": log_id,
                },
            )
            logger.info(f"📥 Queued for parsing: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"Error queueing {file_path}: {e}", exc_info=True)

    # 6. Mark email as read
    mail.store(eid, "+FLAGS", "\\Seen")


async def main_loop(api: APIClient):
    """Vòng lặp chính quản lý kết nối và quét email định kỳ."""
    logger.info(f"🚀 Bắt đầu vòng lặp quét email (Chu kỳ: {SCAN_INTERVAL}s)")
    
    while True:
        # 1. Fetch system settings from DB instead of .env
        settings = await api.get_system_settings()
        if not settings:
            # If API fails or backend is restarting, sleep and retry
            logger.warning("Failed to fetch system settings from API. Retrying in 10s...")
            await asyncio.sleep(10)
            continue
        
        # 2. Check for missing critical configuration
        gemini_key = settings.get("GEMINI_API_KEY", "")
        bot_token = settings.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = settings.get("TELEGRAM_CHAT_ID", "")
        email_pass = settings.get("EMAIL_PASSWORD", "")
        
        if not gemini_key or not bot_token or not email_pass:
            logger.warning("⏳ System not fully configured yet! Missing Gemini API Key, Telegram Token, or Email Password in Database. Pausing scan for 60s...")
            await asyncio.sleep(60)
            continue
            
        # 3. Update global connection variables dynamically
        global IMAP_SERVER, IMAP_PORT, EMAIL_ADDRESS, EMAIL_PASSWORD
        IMAP_SERVER = settings.get("IMAP_SERVER", "imap.gmail.com")
        IMAP_PORT = int(settings.get("IMAP_PORT", 993))
        EMAIL_ADDRESS = settings.get("EMAIL_ADDRESS", "")
        EMAIL_PASSWORD = email_pass
        
        # Store API keys in environment for ai_parser to pick up dynamically
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
        os.environ["TELEGRAM_CHAT_ID"] = str(chat_id)

        mail = None
        try:
            # 4. Kết nối tới Gmail IMAP
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            folders_to_scan = ["INBOX", '"[Gmail]/Spam"', "Spam"]
            
            for folder in folders_to_scan:
                try:
                    status, _ = mail.select(folder)
                    if status != "OK":
                        continue
                        
                    logger.info(f"📂 Quét thư mục: {folder}")
                    
                    # 2. Lấy danh sách ID đã xử lý
                    processed_ids = await api.get_processed_message_ids()
                    
                    # 3. Quét email và đẩy vào pipeline
                    emails = await fetch_unread_emails(mail, processed_ids)
                    if emails:
                        logger.info(f"🔄 Processing {len(emails)} emails from {folder}...")
                    
                    for eid, message_id, sender, subject, msg in emails:
                        try:
                            logger.info(f"🔸 Starting to process email: {subject[:50]}")
                            await process_single_email(eid, message_id, sender, subject, msg, mail, api)
                            logger.info(f"✅ Completed processing: {subject[:50]}")
                        except Exception as e:
                            logger.error(f"❌ Error in process_single_email: {e}", exc_info=True)
                except Exception as e:
                    logger.warning(f"⚠️ Lỗi khi quét thư mục {folder}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Lỗi trong vòng lặp quét mail: {e}")
            await asyncio.sleep(10)
        finally:
            if mail:
                try:
                    mail.logout()
                except Exception:
                    pass
        
        # 4. Chờ đến chu kỳ quét tiếp theo
        await asyncio.sleep(SCAN_INTERVAL)


async def main():
    """Initialize and start."""
    api = APIClient(API_BASE_URL, API_USERNAME, API_PASSWORD)

    # Authenticate
    if not await api.authenticate():
        logger.error("❌ Failed to authenticate with API")
        return

    # SỬ DỤNG BIẾN PIPELINE GLOBAL (đã khai báo ở dòng 42)
    global pipeline

    # Setup pipeline callbacks
    pipeline.on_parsed = on_file_parsed
    pipeline.on_failed = on_file_failed
    
    logger.info("🚀 Starting email listener pipeline...")
    
    # Start background workers
    parse_worker_task = asyncio.create_task(
        pipeline.start_parsing_worker(
            parse_func=parse_invoice_file,
            retry_backoff_seconds=60,
            max_retries=3,
        )
    )
    
    notify_worker_task = asyncio.create_task(
        pipeline.start_notification_worker(
            notify_func=send_invoice_notification,
        )
    )
    
    product_worker_task = asyncio.create_task(
        pipeline.start_product_worker(
            add_func=add_invoice_products,  # LƯU Ý: Phải đảm bảo hàm này đã được import ở đầu file!
        )
    )
    
    # Khởi động vòng lặp quét mail độc lập
    main_loop_task = asyncio.create_task(main_loop(api))
    
    logger.info("✅ All workers started")
    
    # Run all tasks concurrently
    try:
        await asyncio.gather(
            parse_worker_task,
            notify_worker_task,
            product_worker_task,
            main_loop_task,
        )
    except KeyboardInterrupt:
        logger.info("⏹️ Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")

async def run_once(api: APIClient = None, search_criterion: str = "UNSEEN") -> dict:
    """
    Run a single email scan (called by FastAPI endpoint).
    
    Args:
        api: APIClient instance (created if not provided)
        search_criterion: "UNSEEN" or "ALL"
    
    Returns:
        dict with scan results: {"emails": count, "processed": count, "status": status}
    """
    if api is None:
        api = APIClient(API_BASE_URL, API_USERNAME, API_PASSWORD)
        if not await api.authenticate():
            return {"status": "error", "emails": 0, "processed": 0, "message": "Failed to authenticate"}
    
    mail = None
    try:
        # Connect to Gmail
        logger.info(f"🔗 Connecting to Gmail for one-time scan (criterion: {search_criterion})...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=10)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("INBOX")
        logger.info("✅ Connected to Gmail")

        # Get processed message IDs
        processed_ids = await api.get_processed_message_ids()
        logger.debug(f"Already processed: {len(processed_ids)} emails")

        # Fetch emails based on criterion
        results = []
        try:
            status, email_ids = mail.search(None, search_criterion)
            if status != "OK":
                logger.warning(f"❌ Failed to search emails with criterion: {search_criterion}")
                return {"status": "error", "emails": 0, "processed": 0, "message": "IMAP search failed"}

            email_list = email_ids[0].split()[:50]  # Limit to 50 emails
            if not email_list:
                logger.info(f"ℹ️  No emails matching criterion: {search_criterion}")
                return {"status": "ok", "emails": 0, "processed": 0, "message": "No emails to process"}

            logger.info(f"📧 Found {len(email_list)} emails to scan")

            # Process each email
            for eid in email_list:
                try:
                    status, data = mail.fetch(eid, "(RFC822)")
                    if status != "OK":
                        continue

                    msg = message_from_bytes(data[0][1])
                    message_id = msg.get("Message-ID", f"<no-id-{eid.decode()}>")

                    # Skip if already processed
                    if message_id in processed_ids:
                        logger.debug(f"Skipping already-processed email: {message_id}")
                        continue

                    sender = msg.get("From", "")
                    subject = decode_subject(msg.get("Subject", ""))
                    body = get_email_body(msg)

                    # Check if it's an invoice email
                    if not _is_invoice_email(subject, body):
                        logger.debug(f"Skipping non-invoice: {subject[:50]}")
                        continue

                    results.append((eid, message_id, sender, subject, msg))

                except Exception as e:
                    logger.error(f"Error processing email {eid}: {e}")

            # Process all collected emails
            for eid, message_id, sender, subject, msg in results:
                try:
                    await process_single_email(eid, message_id, sender, subject, msg, mail, api)
                except Exception as e:
                    logger.error(f"Error in process_single_email: {e}")

            logger.info(f"✅ Scan complete. Processed {len(results)} emails")
            return {
                "status": "ok",
                "emails": len(email_list),
                "processed": len(results),
                "criterion": search_criterion,
            }

        except Exception as e:
            logger.error(f"Error during email fetch: {e}")
            return {"status": "error", "emails": 0, "processed": 0, "message": str(e)}

    except Exception as e:
        logger.error(f"❌ Scan error: {e}")
        return {"status": "error", "emails": 0, "processed": 0, "message": str(e)}

    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass