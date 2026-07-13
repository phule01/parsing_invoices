"""
Invoice router — HTTP boundary only.

This file handles:
  - Authentication / dependency injection
  - Parsing and validating HTTP input
  - Delegating to InvoiceService
  - Translating service results into HTTP responses
  - Firing side effects (WebSocket, Telegram) as BackgroundTasks so they
    never block the HTTP response

What this file does NOT contain:
  - Any database queries beyond what get_db provides
  - Inventory update logic
  - Notification formatting

Files this replaces (safe to delete after migration):
  - invoices_v2.py
  - invoices_actions.py
  - The invoice-related sections of sync.py
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
)
from sqlalchemy.orm import Session

from database import get_db
from models import Invoice, InvoiceItem, Product
from auth_schemas import (
    InvoiceCreate, InvoiceResponse, InvoiceListResponse,
    InvoiceUpdate, ScanLookupRequest, ScanLookupResponse,
)
from app.core.security import decode_token
from websocket_manager import connection_manager
from app.services.telegram_service import (
    broadcast_to_web_ui,
    send_message as send_telegram_message,
    send_invoice_approval_request,
)
from app.services.invoice_service import InvoiceService, ProductUpdate
from app.services.mysql_sync import sync_invoice_to_mysql

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/invoices", tags=["invoices"])

def _invoice_to_dict(invoice: Invoice) -> dict:
    """Helper to convert Invoice SQLAlchemy object to dict for background tasks."""
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_series": invoice.invoice_series,
        "invoice_date": invoice.invoice_date,
        "seller_name": invoice.seller_name,
        "buyer_name": invoice.buyer_name,
        "total_amount": float(invoice.total_amount) if invoice.total_amount is not None else 0,
        "status": invoice.status,
        "items": [
            {
                "id": item.id,
                "item_name": item.item_name,
                "quantity": float(item.quantity) if item.quantity is not None else 0,
                "unit_price": float(item.unit_price) if item.unit_price is not None else 0,
                "total_price": float(item.total_price) if item.total_price is not None else 0
            }
            for item in getattr(invoice, 'items', [])
        ]
    }


# ── Shared dependency ─────────────────────────────────────────────────────────

def _current_user_data(request: Request, db: Session = Depends(get_db)) -> dict:
    """Extract and verify the JWT, return the token data. Raises 401 on failure."""
    from app.core.security import SECRET_KEY
    internal_secret = request.headers.get("X-Internal-Secret")
    if internal_secret and internal_secret == SECRET_KEY:
        from models import User
        owner = db.query(User).filter(User.is_active == True).first()
        if owner:
            return {"user_id": owner.id, "username": owner.username, "is_admin": owner.is_admin}
        raise HTTPException(status_code=500, detail="No active users found for internal task.")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )
    return decode_token(auth.split(" ", 1)[1])

def _current_user_id(request: Request, db: Session = Depends(get_db)) -> int:
    """Extract and verify the JWT, return the user_id. Raises 401 on failure."""
    return _current_user_data(request, db)["user_id"]


# ── Background notification helper ────────────────────────────────────────────

async def _notify(
    event_type: str,
    invoice_number: str,
    invoice_id: int,
    product_updates: list[ProductUpdate] | None = None,
) -> None:
    """
    Fire WebSocket + Telegram notifications after an invoice action.
    Always runs as a BackgroundTask — never blocks the HTTP response.
    """
    titles = {
        "invoice_approved": "✅ Invoice approved",
        "invoice_rejected": "❌ Invoice rejected",
        "invoice_deleted":  "🗑️ Invoice deleted",
    }
    tg_messages = {
        "invoice_approved": (
            f"✅ Invoice {invoice_number} approved\n"
            f"📦 {len(product_updates or [])} product(s) updated"
        ),
        "invoice_rejected": f"❌ Invoice {invoice_number} rejected",
        "invoice_deleted":  f"🗑️ Invoice {invoice_number} deleted",
    }

    ws_payload: dict = {
        "type": event_type,
        "title": titles.get(event_type, event_type),
        "message": invoice_number,
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "severity": "success" if "approved" in event_type else "error",
    }
    if product_updates:
        ws_payload["product_updates"] = [
            {"name": u.name, "new_quantity": u.new_quantity}
            for u in product_updates
        ]

    await broadcast_to_web_ui(ws_payload)
    
    # Update Telegram status
    from app.services.telegram_service import sync_invoice_notifications, send_invoice_status
    import asyncio
    
    if event_type in ("invoice_approved", "invoice_rejected"):
        action = "approve" if event_type == "invoice_approved" else "reject"
        # 1. Send the new status message to the specific user
        await send_invoice_status(
            action,
            invoice_number,
            note="Inventory updated" if action == "approve" else "",
        )
        
        # 2. Edit the original notification message(s) to remove buttons
        response_text = (
            f"✅ <b>Approved</b> invoice {invoice_number}.\n\nInventory updated."
            if action == "approve"
            else f"❌ <b>Rejected</b> invoice {invoice_number}."
        )
        # We fire-and-forget the sync task so it doesn't block the endpoint
        asyncio.create_task(sync_invoice_notifications(invoice_id, response_text))


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[InvoiceListResponse])
async def list_invoices(
    status_filter: str = Query(None, alias="status"),
    search: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    target_user_id: int = Query(None),
    token_data: dict = Depends(_current_user_data),
    db: Session = Depends(get_db),
):
    query = db.query(Invoice)
    
    # Multi-tenancy isolation
    is_admin = token_data.get("is_admin", False)
    user_id = token_data["user_id"]
    
    if not is_admin:
        # Standard users only see their own invoices
        query = query.filter(Invoice.user_id == user_id)
    elif target_user_id:
        # Admins can filter by a specific user
        query = query.filter(Invoice.user_id == target_user_id)
        
    if status_filter:
        query = query.filter(Invoice.status == status_filter)
    if search:
        query = query.filter(
            Invoice.invoice_number.ilike(f"%{search}%")
            | Invoice.buyer_name.ilike(f"%{search}%")
        )
    return (
        query.order_by(Invoice.invoice_date.desc()).offset(skip).limit(limit).all()
    )


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: int,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/{invoice_id}/file")
async def get_invoice_file(
    invoice_id: int,
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse, RedirectResponse
    from pathlib import Path
    import httpx
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found in database")
        
    # Real-Time Web UI Viewing (The "Triệu hồi" Algorithm)
    if getattr(invoice, 'telegram_file_id', None):
        # We need the user's bot token
        from models import User
        user = db.query(User).filter(User.id == invoice.user_id, User.is_active == True).first()
        if not user or not user.telegram_bot_token:
            # Fallback to global config
            from app.services.telegram_service import get_telegram_config
            bot_token, _ = get_telegram_config()
        else:
            bot_token = user.telegram_bot_token.strip()
            
        if not bot_token:
            raise HTTPException(status_code=500, detail="Telegram bot token not configured")
            
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={invoice.telegram_file_id}")
                resp.raise_for_status()
                data = resp.json()
                if data.get("ok"):
                    file_path = data.get("result", {}).get("file_path")
                    if file_path:
                        download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                        return RedirectResponse(url=download_url, status_code=302)
        except Exception as e:
            logger.error(f"Error fetching file from Telegram: {e}")
            raise HTTPException(status_code=502, detail="Failed to retrieve file from Cloud CDN")
            
    # Legacy fallback: local file
    if not invoice.raw_file_path:
        raise HTTPException(status_code=404, detail="File not found in database")
        
    file_path = Path(invoice.raw_file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    media_type = "application/pdf"
    if file_path.suffix.lower() == ".xml":
        media_type = "application/xml"
    elif file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        media_type = f"image/{file_path.suffix.lower().lstrip('.')}"
        
    return FileResponse(
        path=file_path, 
        filename=file_path.name,
        media_type=media_type
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    invoice_data: InvoiceCreate,
    background_tasks: BackgroundTasks,
    token_data: dict = Depends(_current_user_data),
    db: Session = Depends(get_db),
):
    user_id = token_data["user_id"]
    is_admin = token_data.get("is_admin", False)
    
    # If caller is admin and provided a user_id, use it (for email listener)
    if is_admin and invoice_data.user_id is not None:
        final_user_id = invoice_data.user_id
    else:
        final_user_id = user_id
    full_number = (
        f"{invoice_data.invoice_series}/{invoice_data.invoice_number}"
        if invoice_data.invoice_series
        else None
    )
    if full_number:
        existing = db.query(Invoice).filter(
            Invoice.full_invoice_number == full_number
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Invoice {full_number} already exists",
            )

    total_before_tax = invoice_data.total_before_tax or sum(
        i.quantity * i.unit_price for i in invoice_data.items
    )
    vat_amount = invoice_data.vat_amount or (
        total_before_tax * (invoice_data.vat_rate or 0) / 100
    )
    total_amount = invoice_data.total_amount or (total_before_tax + vat_amount)

    db_invoice = Invoice(
        invoice_series=invoice_data.invoice_series,
        invoice_number=invoice_data.invoice_number,
        full_invoice_number=full_number,
        invoice_date=invoice_data.invoice_date,
        seller_name=invoice_data.seller_name,
        seller_tax_code=invoice_data.seller_tax_code,
        seller_phone=invoice_data.seller_phone,
        seller_address=invoice_data.seller_address,
        buyer_name=invoice_data.buyer_name,
        buyer_tax_code=invoice_data.buyer_tax_code,
        buyer_address=invoice_data.buyer_address,
        total_before_tax=total_before_tax,
        vat_rate=invoice_data.vat_rate,
        vat_amount=vat_amount,
        total_amount=total_amount,
        source_type=getattr(invoice_data, "source_type", None),
        source_email=getattr(invoice_data, "source_email", None),
        raw_file_path=getattr(invoice_data, "raw_file_path", None),
        file_format=getattr(invoice_data, "file_format", None),
        ai_confidence=getattr(invoice_data, "ai_confidence", 0),
        signatures=getattr(invoice_data, "signatures", None),
        status="pending",
        user_id=final_user_id,
    )
    db.add(db_invoice)
    db.flush()

    for idx, item in enumerate(invoice_data.items, 1):
        db.add(InvoiceItem(
            invoice_id=db_invoice.id,
            product_id=item.product_id,
            item_name=item.item_name,
            unit=item.unit,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=item.quantity * item.unit_price,
            vat_rate=item.vat_rate,
            line_number=idx,
        ))

    db.commit()
    db.refresh(db_invoice)

    # Send Telegram approval request as a background task
    items_payload = [
        {
            "item_name": i.item_name,
            "quantity": float(i.quantity),
            "unit_price": float(i.unit_price),
            "total_price": float(i.total_price),
        }
        for i in db_invoice.items
    ]
    background_tasks.add_task(
        send_invoice_approval_request,
        invoice_id=db_invoice.id,
        invoice_number=db_invoice.full_invoice_number or db_invoice.invoice_number,
        seller_name=db_invoice.seller_name or "Unknown",
        total_amount=float(db_invoice.total_amount),
        num_items=len(db_invoice.items),
        items=items_payload,
        raw_file_path=db_invoice.raw_file_path,
    )
    background_tasks.add_task(sync_invoice_to_mysql, _invoice_to_dict(db_invoice))

    return db_invoice


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice_data.status is not None:
        invoice.status = invoice_data.status
    if invoice_data.buyer_name is not None:
        invoice.buyer_name = invoice_data.buyer_name
    if invoice_data.buyer_address is not None:
        invoice.buyer_address = invoice_data.buyer_address

    if invoice_data.items is not None:
        db.query(InvoiceItem).filter(InvoiceItem.invoice_id == invoice_id).delete()
        for idx, item in enumerate(invoice_data.items, 1):
            db.add(InvoiceItem(
                invoice_id=invoice.id,
                item_name=item.item_name,
                unit=item.unit,
                quantity=item.quantity,
                unit_price=item.unit_price,
                total_price=item.quantity * item.unit_price,
                vat_rate=item.vat_rate,
                line_number=idx,
            ))

    db.commit()
    db.refresh(invoice)
    background_tasks.add_task(sync_invoice_to_mysql, _invoice_to_dict(invoice))
    return invoice


# ── Approve ───────────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    result = InvoiceService(db).approve(invoice_id, source="web")

    if not result.ok and not result.already_processed:
        raise HTTPException(status_code=404, detail=result.message)

    if result.already_processed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "conflict",
                "message": result.message,
                "processed_by": result.processed_by,
            },
        )

    background_tasks.add_task(
        _notify,
        "invoice_approved",
        result.invoice.invoice_number,
        result.invoice.id,
        result.product_updates,
    )
    background_tasks.add_task(sync_invoice_to_mysql, _invoice_to_dict(result.invoice))
    return {
        "status": "success",
        "message": result.message,
        "product_updates": [
            {
                "name": u.name,
                "qty_added": u.quantity_change,
                "new_quantity": u.new_quantity,
            }
            for u in result.product_updates
        ],
    }


# ── Reject ────────────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/reject")
async def reject_invoice(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    result = InvoiceService(db).reject(invoice_id, source="web")

    if not result.ok and not result.already_processed:
        raise HTTPException(status_code=404, detail=result.message)

    if result.already_processed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "conflict",
                "message": result.message,
                "processed_by": result.processed_by,
            },
        )

    background_tasks.add_task(
        _notify,
        "invoice_rejected",
        result.invoice.invoice_number,
        result.invoice.id,
    )
    background_tasks.add_task(sync_invoice_to_mysql, _invoice_to_dict(result.invoice))
    return {"status": "success", "message": result.message}


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{invoice_id}")
async def delete_invoice(
    invoice_id: int,
    cascade_delete: bool = Query(False),
    background_tasks: BackgroundTasks = None,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    # Capture the invoice number before deletion for the notification
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_number = invoice.invoice_number  # save before delete

    result = InvoiceService(db).delete(invoice_id, cascade=cascade_delete)

    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "message": result.message,
            },
        )

    background_tasks.add_task(
        _notify,
        "invoice_deleted",
        invoice_number,
        invoice_id,
        result.product_updates,
    )
    return {"status": "success", "message": result.message}


# ── Scan / lookup (unchanged from invoices_v2.py) ─────────────────────────────

@router.post("/scan/lookup", response_model=ScanLookupResponse)
async def scan_lookup(
    scan_data: ScanLookupRequest,
    user_id: int = Depends(_current_user_id),
    db: Session = Depends(get_db),
):
    code = scan_data.code.strip()

    invoice = db.query(Invoice).filter(
        (Invoice.invoice_number == code) | (Invoice.full_invoice_number == code)
    ).first()
    if invoice:
        return ScanLookupResponse(
            found=True,
            entity_type="invoice",
            data=InvoiceResponse.from_orm(invoice).dict(),
            message="Invoice found in system",
        )

    product = None
    if scan_data.type in {"auto", "barcode"}:
        product = db.query(Product).filter(Product.barcode == code).first()
    if not product:
        product = db.query(Product).filter(Product.sku == code).first()
    if not product and code.isdigit():
        product = db.query(Product).filter(Product.id == int(code)).first()

    if product:
        return ScanLookupResponse(
            found=True,
            entity_type="product",
            data={
                "id": product.id,
                "name": product.name,
                "sku": product.sku,
                "barcode": product.barcode,
                "price": float(product.price),
                "quantity_in_stock": product.quantity_in_stock,
            },
            message="Product found in system",
        )

    return ScanLookupResponse(
        found=False,
        entity_type=None,
        data={"code": code},
        message="Item not found in system — ready to add from email",
    )
