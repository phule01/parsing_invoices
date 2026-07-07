from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Credentials for email and integrations (only used by admin)
    email_password = Column(String(255), nullable=True)  # Gmail App Password
    gemini_api_key = Column(String(500), nullable=True)
    telegram_bot_token = Column(String(500), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    imap_server = Column(String(100), nullable=True)
    smtp_server = Column(String(100), nullable=True)

    invoices = relationship("Invoice", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


class AuditLog(Base):
    """Audit trail for security and access control logging."""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # LOGIN, API_ACCESS, CREATE, UPDATE, DELETE, etc.
    resource = Column(String(50), nullable=True, index=True)  # INVOICE, USER, PRODUCT, etc.
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    status_code = Column(Integer, default=200)
    timestamp = Column(DateTime, default=datetime.utcnow, server_default=func.now(), index=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    
    user = relationship("User", back_populates="audit_logs")

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    sku = Column(String(100), nullable=True)
    barcode = Column(String(100), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    quantity_in_stock = Column(Integer, default=0)
    category = Column(String(100), nullable=True)
    supplier = Column(String(200), nullable=True)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    invoice_items = relationship("InvoiceItem", back_populates="product", cascade="all, delete-orphan")

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    
    # Invoice Identification
    invoice_series = Column(String(50), nullable=True, index=True)  # Ký hiệu hóa đơn
    invoice_number = Column(String(50), nullable=False, index=True)
    full_invoice_number = Column(String(100), unique=True, nullable=True, index=True)  # series/number
    invoice_date = Column(DateTime, nullable=True, index=True)
    
    # Lookup & Tax Authority Codes
    lookup_code = Column(String(100), nullable=True)  # Mã tra cứu
    tax_authority_code = Column(String(100), nullable=True)  # Mã CQ Thuế
    
    # Seller Information
    seller_name = Column(String(255), nullable=True)
    seller_tax_code = Column(String(50), nullable=True)
    seller_phone = Column(String(20), nullable=True)  # NEW
    seller_address = Column(Text, nullable=True)  # NEW
    
    # Buyer Information
    buyer_name = Column(String(255), nullable=True)
    buyer_tax_code = Column(String(50), nullable=True)
    buyer_address = Column(Text, nullable=True)
    
    # Invoice amounts
    total_before_tax = Column(Numeric(12, 2), nullable=False, default=0)
    vat_rate = Column(Numeric(5, 2), nullable=False, default=0)
    vat_amount = Column(Numeric(12, 2), nullable=False, default=0)
    total_amount = Column(Numeric(12, 2), nullable=False, default=0)
    
    # Processing Information
    status = Column(String(20), default="pending", index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source_email = Column(String(255), nullable=True, index=True)
    source_type = Column(String(50), nullable=True)  # "attachment", "link", etc.
    raw_file_path = Column(Text, nullable=True)
    file_format = Column(String(20), nullable=True)  # "pdf", "xml"  # NEW
    ai_confidence = Column(Numeric(5, 2), nullable=False, default=0)  # 0-100
    
    # Signature Information (JSON)
    signatures = Column(JSON, nullable=True)  # NEW - Contains seller and tax authority signatures
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime, nullable=True)  # NEW

    user = relationship("User", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    signature_records = relationship("Signature", back_populates="invoice", cascade="all, delete-orphan", overlaps="signatures")

class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Item details (from email/parser)
    item_name = Column(String(500), nullable=False)  # Extended length for full product names
    unit = Column(String(50), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(12, 2), nullable=False)
    vat_rate = Column(Numeric(5, 2), nullable=False, default=0)
    line_number = Column(Integer, nullable=True)  # Position in invoice  # NEW
    created_at = Column(DateTime, server_default=func.now())

    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")

class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True)
    email_from = Column(String(255), nullable=True)  # NEW
    email_subject = Column(String(500), nullable=True)  # NEW - Extended length
    attachment_name = Column(String(255), nullable=True)  # NEW
    file_url = Column(Text, nullable=True)  # NEW
    message_id = Column(String(255), unique=True, nullable=True)  # NEW - Gmail Message-ID
    status = Column(String(50), default="pending", index=True)  # Changed from "string(20)"
    error_message = Column(Text, nullable=True)  # NEW
    processed_at = Column(DateTime, nullable=True)  # NEW
    created_at = Column(DateTime, server_default=func.now())


class Signature(Base):
    __tablename__ = "signatures"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    signer_name = Column(String(255), nullable=True)
    signer_role = Column(String(100), nullable=True)  # "seller", "tax_authority"
    signature_date = Column(DateTime, nullable=True)
    certificate_cn = Column(String(500), nullable=True)  # For tax authority (CN=...)
    is_valid = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    invoice = relationship("Invoice", back_populates="signature_records")


class InventoryAuditLog(Base):
    """Tracks all inventory changes for audit trail and analytics"""
    __tablename__ = "inventory_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Change details
    action = Column(String(50), nullable=False)  # "add", "update", "approve_invoice"
    quantity_change = Column(Integer, nullable=False)  # How much was added/changed
    old_quantity = Column(Integer, nullable=False)  # Quantity before change
    new_quantity = Column(Integer, nullable=False)  # Quantity after change
    old_price = Column(Numeric(10, 2), nullable=True)  # Price before change
    new_price = Column(Numeric(10, 2), nullable=True)  # Price after change
    
    # Metadata
    reason = Column(Text, nullable=True)  # Why the change was made
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), index=True)
    
    product = relationship("Product")
    invoice = relationship("Invoice")
