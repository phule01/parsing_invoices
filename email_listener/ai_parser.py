import os
import base64
import json
import re
import logging
import asyncio
import time
import io
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import httpx
from pdf2image import convert_from_path
from dotenv import load_dotenv

# Load local .env when running outside container for convenience
load_dotenv()

logger = logging.getLogger(__name__)
# Read model from environment (.env or container env)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
# Optional limit for very large PDFs (0 = no limit)
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "0"))

# Rate limiting configuration
API_CALL_DELAY = float(os.getenv("GEMINI_API_DELAY", "2.0"))  # Seconds between API calls
API_TIMEOUT = int(os.getenv("GEMINI_API_TIMEOUT", "120"))  # Request timeout in seconds
API_MAX_RETRIES = int(os.getenv("GEMINI_API_RETRIES", "3"))  # Number of retries for failed requests
BATCH_MAX_CONCURRENT = int(os.getenv("GEMINI_BATCH_CONCURRENT", "3"))  # Max concurrent requests

FALLBACK_MODELS = [
    "models/gemini-3.1-flash-lite"
]

_current_model_idx = 0

def get_current_model() -> str:
    """Get the current Gemini model to use."""
    env_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    formatted_env_model = f"models/{env_model}" if not env_model.startswith("models/") else env_model
    return formatted_env_model

def advance_model():
    """Advance to the next fallback model when rate limits or quotas are hit."""
    global _current_model_idx
    _current_model_idx += 1
    logger.info(f"🔄 Switched to fallback Gemini model: {get_current_model()}")

# Semaphore for controlling concurrent API calls
_api_semaphore = asyncio.Semaphore(BATCH_MAX_CONCURRENT)
_last_api_call = 0


async def _rate_limit_delay():
    """Ensure minimum delay between API calls to avoid rate limiting."""
    global _last_api_call
    elapsed = time.time() - _last_api_call
    if elapsed < API_CALL_DELAY:
        delay = API_CALL_DELAY - elapsed
        logger.debug(f"Rate limiting: waiting {delay:.2f}s before next API call")
        await asyncio.sleep(delay)
    _last_api_call = time.time()


def _format_date_for_api(date_str: Optional[str]) -> Optional[str]:
    """Normalize invoice dates to YYYY-MM-DD when possible."""
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    formats_to_try = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y"]

    for fmt in formats_to_try:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


async def parse_invoice_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parse invoice file using Gemini API with rate limiting and retry logic.
    
    Args:
        file_path: Path to PDF, image, or XML file
        
    Returns:
        Dictionary with extracted invoice data or None if parsing fails
    """
    logger.info(f"[AI PARSER] Processing with Gemini model {GEMINI_MODEL}: {file_path}")
    
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("[AI PARSER] GEMINI_API_KEY not set in environment")
        return None
    prompt = """Trích xuất hóa đơn từ tài liệu và trả về dữ liệu dưới dạng JSON cấu trúc.
Các trường cần thiết:
{
  "invoice_series": "Ký hiệu hóa đơn (e.g., 1C26TBN)",
  "invoice_number": "Số hóa đơn (e.g., 00000014)",
  "lookup_code": "Mã tra cứu (nếu có)",
  "tax_authority_code": "Mã CQ Thuế (nếu có)",
  "invoice_date": "Ngày hóa đơn (YYYY-MM-DD)",
  "seller": {
    "name": "Tên người bán",
    "tax_code": "Mã số thuế",
        "address": "Địa chỉ"
  },
  "buyer": {
    "name": "Tên người mua",
    "tax_code": "Mã số thuế",
    "address": "Địa chỉ"
  },
  "items": [
    {
      "item_name": "Tên hàng hóa/dịch vụ (GIỮ NGUYÊN TỪNG KÝ TỰ)",
      "unit": "Đơn vị",
      "quantity": "Số lượng (kiểu số)",
      "unit_price": "Đơn giá",
      "total_price": "Thành tiền",
      "vat_rate": "Tỷ lệ VAT (%)"
    }
  ],
  "total_before_tax": "Tổng tiền chưa thuế",
  "vat_rate": "Tỷ lệ VAT chung (%)",
  "vat_amount": "Tổng tiền thuế VAT",
  "total_amount": "Tổng cộng"
}
Quan trọng:
- Giữ tên hàng hóa NGUYÊN VẸN từ tài liệu, không chuẩn hóa hay viết tắt
- Trả về CHỈNH JSON, không thêm giải thích hoặc text khác
- Nếu không tìm thấy trường nào, để trống hoặc null"""
    
    # Build `parts` based on the input file type (PDF → images, image file, or XML/text)
    parts = []
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        logger.info(f"🔄 Converting PDF to images for API: {Path(file_path).name}")
        parts = await _convert_pdf_to_parts(file_path)
        if not parts:
            logger.error(f"❌ PDF conversion returned empty parts list")
            return None
    elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"):
        logger.info(f"🖼️  Processing image file: {Path(file_path).name}")
        parts = await _convert_image_to_parts(file_path)
    elif suffix == ".xml":
        try:
            logger.info(f"📋 Processing XML file: {Path(file_path).name}")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                xml_text = f.read()
            parts = [{"text": xml_text}]
        except Exception as e:
            logger.error(f"Failed to read XML file: {e}")
            parts = []
    else:
        # Fallback: try PDF conversion first, then read as text
        logger.info(f"❓ Unknown file type, attempting PDF conversion: {Path(file_path).name}")
        parts = await _convert_pdf_to_parts(file_path)
        if not parts:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    txt = f.read()
                parts = [{"text": txt}]
            except Exception:
                parts = []

        if not parts:
            logger.error(f"❌ No parsable content found in file: {file_path}")
            return None

    # Prepend the instruction prompt
    parts.insert(0, {"text": prompt})
    
    # Try to parse with retries (increase max retries to account for fallback models)
    max_attempts = max(API_MAX_RETRIES, len(FALLBACK_MODELS) + 2)
    for attempt in range(max_attempts):
        try:
            async with _api_semaphore:
                await _rate_limit_delay()
                parsed = await _call_gemini_api(parts)
                
            if parsed:
                # Validate and clean the parsed data
                parsed = _validate_invoice_data(parsed)
                logger.info(f"[AI PARSER] Successfully parsed: {parsed.get('invoice_number', 'N/A')}")
                return parsed
            else:
                logger.warning(f"[AI PARSER] Attempt {attempt + 1}: Empty response from API")
                
        except asyncio.TimeoutError:
            logger.warning(f"[AI PARSER] Attempt {attempt + 1}: API timeout")
            if attempt < max_attempts - 1:
                await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                
        except Exception as e:
            logger.warning(f"[AI PARSER] Attempt {attempt + 1}: {e}")
            if "RATE_LIMIT_EXCEEDED" in str(e):
                logger.info(f"⏭️  Switching model and retrying immediately...")
                continue # Try immediately with new model
                
            if attempt < max_attempts - 1:
                await asyncio.sleep(3 * (attempt + 1))  # Exponential backoff
    
    logger.error(f"[AI PARSER] Failed to parse after {max_attempts} attempts")
    return None


async def send_image_to_telegram(
    image_bytes: bytes,
    caption: str = "",
    filename: str = "page.jpg",
    as_document: bool = True
) -> bool:
    """Send an image directly to Telegram from memory."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        return False

    method = "sendDocument" if as_document else "sendPhoto"
    field_name = "document" if as_document else "photo"
    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    files = {field_name: (filename, image_bytes, "image/jpeg")}
    data = {"chat_id": chat_id, "caption": caption}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, data=data, files=files)
            if resp.status_code != 200:
                logger.error(f"Failed to send image to Telegram: {resp.text}")
                return False
        return True
    except Exception as e:
        logger.error(f"Error sending image to Telegram: {e}")
        return False


async def send_images_to_telegram(b64_images: list[str], base_caption: str = "Invoice Image Preview") -> None:
    """Send base64 images directly to Telegram as documents."""
    total = len(b64_images)
    for idx, b64 in enumerate(b64_images, start=1):
        image_bytes = base64.b64decode(b64)
        caption = f"{base_caption} - Page {idx}/{total}" if total > 1 else base_caption
        # Send as document so it's not compressed
        await send_image_to_telegram(image_bytes, caption=caption, filename=f"page_{idx}.jpg", as_document=True)


async def _convert_pdf_to_parts(file_path: str) -> list:
    """Convert PDF pages to base64-encoded images."""
    try:
        logger.info(f"📄 Starting PDF conversion: {file_path}")
        images = convert_from_path(file_path, dpi=200)
        logger.info(f"✅ Successfully converted PDF to {len(images)} image(s)")
        
        parts = []
        # Optionally limit pages to avoid huge payloads
        if MAX_PDF_PAGES and len(images) > MAX_PDF_PAGES:
            logger.warning(f"⚠️  PDF has {len(images)} pages, limiting to {MAX_PDF_PAGES} pages")
            images = images[:MAX_PDF_PAGES]

        for idx, img in enumerate(images):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            image_size = len(buf.getvalue())
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(buf.getvalue()).decode("utf-8")
                }
            })
            logger.info(f"✅ Converted PDF page {idx + 1} to JPEG ({image_size} bytes)")
            
        if parts:
            # Send all pages directly to Telegram from memory!
            # We extract the base64 string from the parts list.
            b64_images = [p["inline_data"]["data"] for p in parts]
            import asyncio
            filename = Path(file_path).name
            # Fire and forget sending to avoid blocking
            asyncio.create_task(send_images_to_telegram(b64_images, base_caption=f"📄 Preview: {filename}"))
            
        logger.info(f"✅ PDF conversion complete: {len(parts)} image(s) ready for Gemini API")
        return parts
    except Exception as e:
        logger.error(f"❌ PDF conversion error: {e}", exc_info=True)
        return []


async def _convert_image_to_parts(file_path: str) -> list:
    """Convert image file to base64-encoded data."""
    try:
        ext = Path(file_path).suffix.lower().lstrip('.')
        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return [{
            "inline_data": {
                "mime_type": f"image/{ext}",
                "data": data
            }
        }]
    except Exception as e:
        logger.error(f"Image conversion error: {e}")
        return []


async def _call_gemini_api(parts: list) -> Optional[Dict[str, Any]]:
    """
    Call Gemini API with proper timeout and rate-limit error handling.
    
    This function will raise exceptions for rate limits, timeouts, and network errors
    so that the retry logic in parse_invoice_file can handle them appropriately.
    
    Args:
        parts: List of content parts (text, images, etc.)
        
    Returns:
        Parsed JSON response or None on recoverable parse errors
        
    Raises:
        asyncio.TimeoutError: On API timeout
        httpx.HTTPStatusError: On API HTTP errors (including rate limits)
        Exception: On network and other errors
    """
    model_name = get_current_model()
    # Strip 'models/' prefix if the endpoint URL format requires it, 
    # but the v1beta endpoint actually accepts both `models/gemini-pro` and `gemini-pro`
    # if we insert it directly into the path.
    url_model = model_name if not model_name.startswith("models/") else model_name[7:]
    api_key = os.getenv("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{url_model}:generateContent?key={api_key}"

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json"
        },
    }
    
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=payload,
                timeout=API_TIMEOUT
            )
            
            # Check for rate limit errors (HTTP 429) and re-raise for retry
            if resp.status_code == 429:
                advance_model()
                error_msg = f"Rate limit exceeded [HTTP 429]. RATE_LIMIT_EXCEEDED"
                logger.warning(f"🚫 {error_msg}: {resp.text[:200]}")
                raise Exception(error_msg)  # Will trigger immediate retry in parse_invoice_file
            
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Mask the API key in the URL so it doesn't leak in the logs
                masked_url = str(e.request.url).replace(api_key, "HIDDEN_API_KEY") if api_key else str(e.request.url)
                raise Exception(f"Gemini HTTP Error: {resp.status_code} - {masked_url} - {resp.text[:200]}")
            
            data = resp.json()
            
            # Extract text from response
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                # Clean JSON response (remove markdown code blocks if present)
                text = re.sub(r'```json\s*|```', '', text).strip()
                parsed = json.loads(text)
                if isinstance(parsed, dict) and parsed.get("invoice_date"):
                    parsed["invoice_date"] = _format_date_for_api(parsed["invoice_date"])
                return parsed
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                logger.error(f"Failed to parse API response: {e}")
                logger.debug(f"Raw response: {data}")
                return None
                
    except httpx.TimeoutException as e:
        logger.warning(f"⏱️  Gemini API timeout after {API_TIMEOUT}s: %s", e)
        raise asyncio.TimeoutError(f"API request timeout ({API_TIMEOUT}s)") from e

    except httpx.HTTPStatusError as e:
        # Already logged above when status != 200, rethrow
        logger.error("❌ Gemini HTTPStatusError: %s", e)
        raise

    except Exception as e:
        logger.exception(f"❌ Gemini API call failed: {type(e).__name__}: {e}")
        raise


def _validate_invoice_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean invoice data from API response.
    Preserves item names exactly as provided.
    
    Args:
        data: Raw parsed data from API
        
    Returns:
        Cleaned and validated data
    """
    if not isinstance(data, dict):
        return {}
    
    # Ensure required fields exist
    raw_date = data.get("invoice_date")
    normalized_date = _format_date_for_api(raw_date) if isinstance(raw_date, str) else raw_date
    if normalized_date and isinstance(normalized_date, str) and len(normalized_date) == 10:
        processed_date = f"{normalized_date}T00:00:00"
    else:
        processed_date = normalized_date
    result = {
        "invoice_series": str(data.get("invoice_series", "")).strip() or None,
        "invoice_number": str(data.get("invoice_number", "")).strip(),
        "lookup_code": str(data.get("lookup_code", "")).strip() or None,
        "tax_authority_code": str(data.get("tax_authority_code", "")).strip() or None,
        "invoice_date": processed_date,
    }
    
    # Seller information
    seller = data.get("seller", {}) or {}
    # Prefer nested seller.name, fallback to flat 'seller_name' if provided by model
    seller_name = None
    if isinstance(seller, dict):
        seller_name = str(seller.get("name", "")).strip() or None
    if not seller_name:
        seller_name = str(data.get("seller_name", "")).strip() or None

    result["seller"] = {
        "name": seller_name,
        "tax_code": str(seller.get("tax_code", "")).strip() or None,
        "address": str(seller.get("address", "")).strip() or None,
    }
    
    # Buyer information
    buyer = data.get("buyer", {}) or {}
    buyer_name = None
    if isinstance(buyer, dict):
        buyer_name = str(buyer.get("name", "")).strip() or None
    if not buyer_name:
        buyer_name = str(data.get("buyer_name", "")).strip() or None

    result["buyer"] = {
        "name": buyer_name,
        "tax_code": str(buyer.get("tax_code", "")).strip() or None,
        "address": str(buyer.get("address", "")).strip() or None,
    }
    
    # Items - PRESERVE ITEM NAMES EXACTLY
    items = []
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        items.append({
            "item_name": str(item.get("item_name", "")).strip(),  # Keep exactly as-is
            "unit": str(item.get("unit", "")).strip() or None,
            "quantity": _safe_float(item.get("quantity")),
            "unit_price": _safe_float(item.get("unit_price")),
            "total_price": _safe_float(item.get("total_price")),
            "vat_rate": _safe_float(item.get("vat_rate")),
        })
    result["items"] = items
    
    # Financial information
    result["total_before_tax"] = _safe_float(data.get("total_before_tax"))
    result["vat_rate"] = _safe_float(data.get("vat_rate"))
    result["vat_amount"] = _safe_float(data.get("vat_amount"))
    result["total_amount"] = _safe_float(data.get("total_amount"))
    
    return result


def _safe_float(value: Any) -> float:
    """Safely convert value to float, handling common localized formats."""
    try:
        if value is None:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        s = str(value).strip()
        if not s:
            return 0.0

        # Remove currency symbols/letters while preserving separators and sign
        s = re.sub(r"[^0-9,\.\-]", "", s)
        if not s or s in {"-", ".", ","}:
            return 0.0

        # Handle common localized formats, prioritizing Vietnamese style
        # Vietnamese: dot = thousands separator, comma = decimal separator
        # Examples:
        #  - "300.250" -> 300250.0 (thousands grouping)
        #  - "1.234.567,89" -> 1234567.89
        #  - "300,25" -> 300.25 (comma decimal)

        # If both separators present, assume dot thousands, comma decimal
        if "." in s and "," in s:
            s = s.replace(".", "").replace(",", ".")
            return float(s)

        # If only comma present, treat comma as decimal if fractional part length <= 2
        if "," in s and "." not in s:
            parts = s.split(",")
            if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
                s = s.replace(",", ".")
                return float(s)
            # otherwise comma used as thousands separator
            s = s.replace(",", "")
            return float(s)

        # If only dot present, determine if it's thousands separator (groups of 3)
        if "." in s and "," not in s:
            parts = s.split(".")
            # If last group has exactly 3 digits, it's likely thousands grouping
            if len(parts) > 1 and all(p.isdigit() for p in parts) and len(parts[-1]) == 3:
                s = "".join(parts)
                return float(s)
            # Otherwise treat as decimal point
            return float(s)

        # Fallback
        return float(s)
    except (ValueError, TypeError):
        return 0.0