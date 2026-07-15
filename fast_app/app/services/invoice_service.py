"""
Invoice service — single source of truth for approve / reject / delete.

Previously these three actions were scattered across:
  - invoices_v2.py      (approve, reject, delete — full inventory logic)
  - invoices_actions.py (approve, reject, delete — different implementation)
  - sync.py             (approve, reject, delete — third implementation)
  - telegram_handlers.py (_process_invoice_action — fourth implementation)

They are now consolidated here. The web router, Telegram callback handler,
and any future trigger (webhook, scheduled job) all call this service,
guaranteeing identical behaviour regardless of source.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy.orm import Session

from models import Invoice, Product, InventoryAuditLog, EmailLog

logger = logging.getLogger(__name__)


# ── Result types ─────────────────────────────────────────────────────────────
# Using plain dataclasses instead of dicts so callers get type hints and
# IDE autocompletion rather than string-keyed access.

@dataclass
class ProductUpdate:
    product_id: int
    name: str
    quantity_change: int   # positive = added, negative = reverted
    old_quantity: int
    new_quantity: int
    unit_price: float


@dataclass
class InvoiceActionResult:
    ok: bool
    invoice: Optional[Invoice] = None
    message: str = ""
    already_processed: bool = False
    processed_by: str = ""
    product_updates: list[ProductUpdate] = field(default_factory=list)


# ── Service ───────────────────────────────────────────────────────────────────

class InvoiceService:
    """
    Stateless service — receive a db Session on construction, call one method,
    get a typed result back. No HTTP, no WebSocket, no Telegram here.
    Side effects (notifications, broadcasts) belong in the router layer.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Public API ────────────────────────────────────────────────────────────

    def approve(self, invoice_id: int, source: str = "web") -> InvoiceActionResult:
        """
        Approve an invoice and update inventory.

        Steps:
          1. Acquire a row-level lock — prevents the simultaneous web +
             Telegram double-click race condition that existed before.
          2. Guard against re-processing (idempotency).
          3. Mark invoice as 'verified', stamp processed_at.
          4. Upsert each line item into the products table.
          5. Write an InventoryAuditLog row per product touched.
          6. Persist workflow metadata so the other platform can detect it.
        """
        invoice = self._locked_invoice(invoice_id)
        if invoice is None:
            return InvoiceActionResult(ok=False, message="Invoice not found")

        conflict = self._check_already_processed(invoice)
        if conflict:
            return conflict

        invoice.status = "verified"
        invoice.processed_at = datetime.utcnow()

        product_updates = self._upsert_inventory(invoice)
        self._stamp_workflow(invoice, source)

        self._db.commit()
        self._db.refresh(invoice)

        logger.info(
            "Invoice %s approved by %s — %d product(s) updated",
            invoice.invoice_number, source, len(product_updates),
        )
        return InvoiceActionResult(
            ok=True,
            invoice=invoice,
            message=f"Invoice {invoice.invoice_number} approved",
            processed_by=source,
            product_updates=product_updates,
        )

    def reject(self, invoice_id: int, source: str = "web") -> InvoiceActionResult:
        """Reject an invoice without touching inventory."""
        invoice = self._locked_invoice(invoice_id)
        if invoice is None:
            return InvoiceActionResult(ok=False, message="Invoice not found")

        conflict = self._check_already_processed(invoice)
        if conflict:
            return conflict

        invoice.status = "rejected"
        invoice.processed_at = datetime.utcnow()
        self._stamp_workflow(invoice, source)

        self._db.commit()
        self._db.refresh(invoice)

        logger.info("Invoice %s rejected by %s", invoice.invoice_number, source)
        return InvoiceActionResult(
            ok=True,
            invoice=invoice,
            message=f"Invoice {invoice.invoice_number} rejected",
            processed_by=source,
        )

    def delete(self, invoice_id: int, cascade: bool = False) -> InvoiceActionResult:
        """
        Delete an invoice.

        cascade=False — remove the invoice record only; inventory untouched.
        cascade=True  — verify revert feasibility, revert inventory quantities,
                        then delete.

        Returns ok=False with a descriptive message when cascade=True but
        stock is insufficient; the caller should translate this to a 400.
        """
        # No row lock needed here — deletion is not subject to the same
        # double-processing race as approve/reject.
        invoice = self._db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice is None:
            return InvoiceActionResult(ok=False, message="Invoice not found")

        reverted: list[ProductUpdate] = []

        if cascade:
            insufficient = self._check_revert_feasibility(invoice)
            if insufficient:
                details = ", ".join(
                    f"{i['product_name']} (need {i['required']}, have {i['available']})"
                    for i in insufficient
                )
                return InvoiceActionResult(
                    ok=False,
                    message=f"Insufficient inventory to revert: {details}",
                )
            reverted = self._revert_inventory(invoice)

        invoice_number = invoice.invoice_number
        
        # If the invoice came from an email, delete its log to allow re-scanning
        if invoice.source_type == "email" and invoice.source_email:
            self._db.query(EmailLog).filter(EmailLog.message_id == invoice.source_email).delete()
            logger.info("Deleted email log for message %s to allow re-scanning", invoice.source_email)
            
        self._db.delete(invoice)
        self._db.commit()

        logger.info(
            "Invoice %s deleted (cascade=%s, %d product(s) reverted)",
            invoice_number, cascade, len(reverted),
        )
        return InvoiceActionResult(
            ok=True,
            message=(
                f"Invoice {invoice_number} deleted"
                + (" and inventory reverted" if cascade else "")
            ),
            product_updates=reverted,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _locked_invoice(self, invoice_id: int) -> Optional[Invoice]:
        """SELECT … FOR UPDATE prevents concurrent approve/reject races."""
        return (
            self._db.query(Invoice)
            .filter(Invoice.id == invoice_id)
            .with_for_update()
            .first()
        )

    def _check_already_processed(self, invoice: Invoice) -> Optional[InvoiceActionResult]:
        if invoice.status not in {"verified", "rejected"}:
            return None  # still pending — safe to proceed
        workflow = (invoice.signatures or {}).get("workflow", {})
        processed_by = workflow.get("processed_by", "unknown")
        return InvoiceActionResult(
            ok=False,
            already_processed=True,
            invoice=invoice,
            message=f"Invoice already {invoice.status}",
            processed_by=processed_by,
        )

    def _upsert_inventory(self, invoice: Invoice) -> list[ProductUpdate]:
        """Create or update a Product row for every line item on the invoice."""
        updates: list[ProductUpdate] = []

        for item in invoice.items:
            if not item.item_name or not item.quantity:
                continue

            qty = int(float(item.quantity))
            price = float(item.unit_price or 0)

            product = (
                self._db.query(Product)
                .filter(Product.name == item.item_name, Product.user_id == invoice.user_id)
                .first()
            )

            if product:
                old_qty = product.quantity_in_stock or 0
                old_price = float(product.price or 0)
                product.quantity_in_stock = old_qty + qty
                product.price = price  # update to latest invoice price

                self._db.add(InventoryAuditLog(
                    product_id=product.id,
                    invoice_id=invoice.id,
                    action="approve_invoice",
                    quantity_change=qty,
                    old_quantity=old_qty,
                    new_quantity=product.quantity_in_stock,
                    old_price=old_price,
                    new_price=price,
                    reason=f"Invoice {invoice.invoice_number} approved",
                ))
                updates.append(ProductUpdate(
                    product_id=product.id,
                    name=product.name,
                    quantity_change=qty,
                    old_quantity=old_qty,
                    new_quantity=product.quantity_in_stock,
                    unit_price=price,
                ))
            else:
                new_product = Product(
                    name=item.item_name,
                    quantity_in_stock=qty,
                    price=price,
                    description=f"From invoice {invoice.invoice_number}",
                    user_id=invoice.user_id,
                )
                self._db.add(new_product)
                self._db.flush()  # populate new_product.id before the audit log

                self._db.add(InventoryAuditLog(
                    product_id=new_product.id,
                    invoice_id=invoice.id,
                    action="add",
                    quantity_change=qty,
                    old_quantity=0,
                    new_quantity=qty,
                    old_price=None,
                    new_price=price,
                    reason=f"New product from invoice {invoice.invoice_number}",
                ))
                updates.append(ProductUpdate(
                    product_id=new_product.id,
                    name=new_product.name,
                    quantity_change=qty,
                    old_quantity=0,
                    new_quantity=qty,
                    unit_price=price,
                ))

        return updates

    def _check_revert_feasibility(self, invoice: Invoice) -> list[dict]:
        """Return a list of items that cannot be reverted due to insufficient stock."""
        insufficient = []
        for item in invoice.items:
            if not item.item_name or not item.quantity:
                continue
            qty = int(float(item.quantity))
            product = (
                self._db.query(Product)
                .filter(Product.name == item.item_name, Product.user_id == invoice.user_id)
                .first()
            )
            if product and (product.quantity_in_stock or 0) < qty:
                insufficient.append({
                    "product_name": product.name,
                    "required": qty,
                    "available": product.quantity_in_stock,
                })
        return insufficient

    def _revert_inventory(self, invoice: Invoice) -> list[ProductUpdate]:
        """Subtract invoice quantities back out of inventory."""
        reverted: list[ProductUpdate] = []
        for item in invoice.items:
            if not item.item_name or not item.quantity:
                continue
            qty = int(float(item.quantity))
            product = (
                self._db.query(Product)
                .filter(Product.name == item.item_name, Product.user_id == invoice.user_id)
                .first()
            )
            if not product:
                continue

            old_qty = product.quantity_in_stock or 0
            new_qty = max(0, old_qty - qty)
            product.quantity_in_stock = new_qty

            self._db.add(InventoryAuditLog(
                product_id=product.id,
                invoice_id=invoice.id,
                action="revert",
                quantity_change=-qty,
                old_quantity=old_qty,
                new_quantity=new_qty,
                old_price=float(product.price or 0),
                new_price=float(product.price or 0),
                reason=f"Invoice {invoice.invoice_number} deleted with cascade",
            ))
            reverted.append(ProductUpdate(
                product_id=product.id,
                name=product.name,
                quantity_change=-qty,
                old_quantity=old_qty,
                new_quantity=new_qty,
                unit_price=float(product.price or 0),
            ))
        return reverted

    def _stamp_workflow(self, invoice: Invoice, source: str) -> None:
        """
        Write processing metadata into invoice.signatures['workflow'].
        This is how each platform tells the other 'I already handled this'.
        """
        meta = dict(invoice.signatures or {})
        meta["workflow"] = {
            "processed_by": source,
            "processed_at": (
                invoice.processed_at.isoformat() if invoice.processed_at else None
            ),
        }
        invoice.signatures = meta
