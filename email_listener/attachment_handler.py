"""
Attachment Handler – Tải và xử lý file đính kèm PDF/XML từ email.
"""
import os
import logging
import zipfile
import tempfile
from pathlib import Path
from email.message import Message

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/invoices")
ALLOWED_EXTENSIONS = {".pdf", ".xml", ".zip", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}


def save_attachment(part: Message, save_dir: str) -> list[str]:
    """Lưu một attachment từ email, trả về list đường dẫn file."""
    saved = []
    filename = part.get_filename()
    if not filename:
        return saved

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return saved

    os.makedirs(save_dir, exist_ok=True)
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
    
    # Prevent file overwrites by adding timestamp if file already exists
    file_path = os.path.join(save_dir, safe_name)
    if os.path.exists(file_path):
        import time
        name_stem = Path(safe_name).stem
        name_ext = Path(safe_name).suffix
        timestamp = int(time.time() * 1000) % 100000  # Last 5 digits of milliseconds
        safe_name = f"{name_stem}_{timestamp}{name_ext}"
        file_path = os.path.join(save_dir, safe_name)
        logger.info(f"File collision detected, renaming to: {safe_name}")

    with open(file_path, "wb") as f:
        f.write(part.get_payload(decode=True))

    logger.info(f"✅ Lưu attachment: {file_path}")

    # Nếu là ZIP, giải nén và lấy PDF/XML bên trong
    if ext == ".zip":
        extracted = _extract_zip(file_path, save_dir)
        saved.extend(extracted)
        os.remove(file_path)  # Xóa file zip gốc
    else:
        saved.append(file_path)

    return saved


def _extract_zip(zip_path: str, extract_dir: str) -> list[str]:
    """Giải nén ZIP và trả về danh sách file PDF/XML."""
    extracted = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                ext = Path(info.filename).suffix.lower()
                if ext in {".pdf", ".xml", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}:
                    # Extract with collision detection
                    extract_path = os.path.join(extract_dir, info.filename)
                    os.makedirs(os.path.dirname(extract_path), exist_ok=True)
                    
                    # Prevent overwriting
                    if os.path.exists(extract_path):
                        import time
                        name_stem = Path(info.filename).stem
                        name_ext = Path(info.filename).suffix
                        timestamp = int(time.time() * 1000) % 100000
                        new_name = f"{name_stem}_{timestamp}{name_ext}"
                        extract_path = os.path.join(extract_dir, new_name)
                        logger.info(f"ZIP collision: renaming {info.filename} → {new_name}")
                    
                    with zf.open(info) as source:
                        with open(extract_path, "wb") as target:
                            target.write(source.read())
                    
                    extracted.append(extract_path)
                    logger.info(f"✅ Giải nén: {info.filename}")
    except zipfile.BadZipFile as e:
        logger.error(f"ZIP lỗi: {e}")
    return extracted


def extract_attachments_from_email(msg: Message, message_id: str) -> list[str]:
    """
    Trích xuất tất cả file PDF/XML từ một email.
    Trả về list đường dẫn file đã lưu.
    """
    # Create sanitized directory name from message_id
    safe_dir_name = message_id.replace("<", "").replace(">", "").replace("/", "_")[:50]
    save_dir = os.path.join(DOWNLOAD_DIR, safe_dir_name)
    
    # Ensure directory exists with proper permissions
    try:
        os.makedirs(save_dir, mode=0o755, exist_ok=True)
    except PermissionError as e:
        logger.error(f"❌ Permission denied creating directory {save_dir}: {e}")
        # Fallback to flat directory structure without subdirectories
        save_dir = DOWNLOAD_DIR

    all_files = []
    candidate_count = 0
    generated_index = 0
    part_index = 0

    for part in msg.walk():
        part_index += 1
        content_disposition = str(part.get("Content-Disposition", ""))
        filename = part.get_filename()
        content_type = part.get_content_type() or ""
        payload_size = 0
        try:
            payload = part.get_payload(decode=True)
            payload_size = len(payload) if payload else 0
        except Exception:
            payload = None
            payload_size = 0

        logger.debug(f"📄 Part {part_index}: filename={filename} | type={content_type} | disposition={content_disposition[:30]} | size={payload_size} bytes")

        # Count likely attachment parts for diagnostics
        if filename or ("attachment" in content_disposition) or content_type in ("application/pdf", "text/xml", "application/xml", "application/zip") or content_type.startswith("image/"):
            candidate_count += 1

        # Prefer saving parts with filenames first
        if filename or ("attachment" in content_disposition):
            files = save_attachment(part, save_dir)
            if files:
                all_files.extend(files)
                logger.info(f"✅ Saved {len(files)} file(s) from attachment: {filename}")
            else:
                logger.debug(f"⏭️  Skipped (unsupported/empty): filename={filename} content_type={content_type}")
            continue

        # Fallback: if part looks like a PDF/XML binary but has no filename, generate one
        if payload and content_type == "application/pdf":
            generated_index += 1
            gen_name = f"attachment_{generated_index}.pdf"
            file_path = os.path.join(save_dir, gen_name)
            try:
                with open(file_path, "wb") as f:
                    f.write(payload)
                logger.info(f"💾 Đã lưu attachment (generated name): {file_path}")
                all_files.append(file_path)
            except Exception as e:
                logger.error(f"Failed to save generated pdf attachment: {e}")

        elif payload and content_type in ("text/xml", "application/xml"):
            generated_index += 1
            gen_name = f"attachment_{generated_index}.xml"
            file_path = os.path.join(save_dir, gen_name)
            try:
                with open(file_path, "wb") as f:
                    f.write(payload)
                logger.info(f"Đã lưu attachment (generated name): {file_path}")
                all_files.append(file_path)
            except Exception as e:
                logger.error(f"Failed to save generated xml attachment: {e}")
                
        elif payload and content_type.startswith("image/"):
            generated_index += 1
            ext = content_type.split("/")[-1]
            if ext == "jpeg": ext = "jpg"
            gen_name = f"attachment_{generated_index}.{ext}"
            file_path = os.path.join(save_dir, gen_name)
            try:
                with open(file_path, "wb") as f:
                    f.write(payload)
                logger.info(f"Đã lưu attachment (generated image): {file_path}")
                all_files.append(file_path)
            except Exception as e:
                logger.error(f"Failed to save generated image attachment: {e}")

    logger.info(f"📊 Attachment extraction complete: candidates={candidate_count}, saved={len(all_files)} files for message {message_id}")
    return all_files


def get_email_body(msg: Message) -> str:
    """Lấy nội dung text của email (plain hoặc html stripped)."""
    body = ""
    for part in msg.walk():
        content_type = part.get_content_type()
        if content_type == "text/plain":
            try:
                body += part.get_payload(decode=True).decode("utf-8", errors="ignore")
            except Exception:
                pass
        elif content_type == "text/html" and not body:
            try:
                html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                # Strip HTML tags
                import re
                body += re.sub(r"<[^>]+>", " ", html)
            except Exception:
                pass
    return body
