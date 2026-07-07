from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# ==================== Authentication Schemas ====================

class UserLogin(BaseModel):
    """User login request."""
    username: str
    password: str

class UserRegister(BaseModel):
    """User registration request."""
    username: str
    password: str

class AdminRegister(BaseModel):
    """Admin setup/registration request with all credentials."""
    username: str
    password: str
    telegram_bot_token: str
    telegram_chat_id: str
    email_address: Optional[str] = None
    email_password: Optional[str] = None
    gemini_api_key: Optional[str] = None

class TokenResponse(BaseModel):
    """Token response."""
    access_token: str
    token_type: str
    user_id: int
    username: str
    is_admin: bool
    expires_in: int  # seconds

class UserResponse(BaseModel):
    """User response (safe to send to frontend)."""
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Invoice Schemas ====================

class InvoiceItemCreate(BaseModel):
    """Create invoice item."""
    product_id: Optional[int] = None
    item_name: str
    unit: str
    quantity: float
    unit_price: float
    vat_rate: float = 0

class InvoiceItemResponse(BaseModel):
    """Invoice item response."""
    id: int
    invoice_id: int
    product_id: Optional[int] = None
    item_name: str
    unit: str
    quantity: float
    unit_price: float
    total_price: float
    vat_rate: float
    line_number: Optional[int] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class InvoiceCreate(BaseModel):
    """Create invoice."""
    invoice_series: Optional[str] = None
    invoice_number: str
    invoice_date: datetime
    seller_name: Optional[str] = None
    seller_tax_code: Optional[str] = None
    seller_phone: Optional[str] = None
    seller_address: Optional[str] = None
    buyer_name: str
    buyer_tax_code: Optional[str] = None
    buyer_address: Optional[str] = None
    items: List[InvoiceItemCreate]
    total_before_tax: float
    vat_rate: float = 0
    vat_amount: float = 0
    total_amount: float

class InvoiceUpdate(BaseModel):
    """Update invoice."""
    status: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_address: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None

class InvoiceResponse(BaseModel):
    """Invoice response."""
    id: int
    invoice_number: str
    invoice_series: Optional[str]
    invoice_date: datetime
    buyer_name: str
    buyer_tax_code: Optional[str]
    status: str
    total_amount: float
    items: List[InvoiceItemResponse]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class InvoiceListResponse(BaseModel):
    """Invoice list item response (minimal)."""
    id: int
    invoice_number: str
    invoice_date: datetime
    buyer_name: str
    status: str
    total_amount: float
    created_at: datetime

# ==================== Product Schemas ====================

class ProductCreate(BaseModel):
    """Create product."""
    name: str
    description: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    price: float
    quantity_in_stock: int = 0
    category: Optional[str] = None
    supplier: Optional[str] = None
    image_url: Optional[str] = None

class ProductUpdate(BaseModel):
    """Update product."""
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    price: Optional[float] = None
    quantity_in_stock: Optional[int] = None
    category: Optional[str] = None
    supplier: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    """Product response."""
    id: int
    name: str
    description: Optional[str]
    sku: Optional[str]
    barcode: Optional[str]
    price: float
    quantity_in_stock: int
    category: Optional[str]
    supplier: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Scan & Lookup Schemas ====================

class ScanLookupRequest(BaseModel):
    """Scan lookup request."""
    code: str  # Barcode, QR, or manual ID
    type: str = "auto"  # auto, barcode, qr, invoice_number, product_sku

class ScanLookupResponse(BaseModel):
    """Scan lookup response."""
    found: bool
    entity_type: Optional[str] = None  # invoice, product, or not_found
    data: Optional[dict] = None
    message: str

# ==================== Activity Log Schemas ====================

class ActivityLogResponse(BaseModel):
    """Activity log response for real-time updates."""
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    user_id: Optional[int]
    changes: dict
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== WebSocket Message Schemas ====================

class WebSocketMessage(BaseModel):
    """WebSocket message."""
    type: str  # connection, message, notification, error
    data: dict
    timestamp: datetime = datetime.utcnow()

class RealTimeNotification(BaseModel):
    """Real-time notification."""
    type: str  # invoice_created, invoice_updated, product_created, etc.
    entity_type: str
    entity_id: int
    data: dict
    user_id: Optional[int] = None
    source: str  # web, telegram, api


# ==================== Email Log Schemas ====================

class EmailLogResponse(BaseModel):
    """Email processing log entry."""
    id: int
    invoice_id: Optional[int] = None
    email_from: Optional[str] = None
    email_subject: Optional[str] = None
    attachment_name: Optional[str] = None
    file_url: Optional[str] = None
    message_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
