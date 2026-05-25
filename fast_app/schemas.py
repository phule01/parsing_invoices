from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Product Schemas
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    quantity_in_stock: int = 0

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    quantity_in_stock: Optional[int] = None

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Invoice Schemas (must be defined before InvoiceItemResponse)
class InvoiceBase(BaseModel):
    # Invoice Identification
    invoice_series: Optional[str] = None  # NEW
    invoice_number: str
    full_invoice_number: Optional[str] = None  # NEW
    invoice_date: Optional[datetime] = None
    
    # Lookup & Tax Authority Codes
    lookup_code: Optional[str] = None  # NEW
    tax_authority_code: Optional[str] = None  # NEW
    
    # Seller Information
    seller_name: Optional[str] = None
    seller_tax_code: Optional[str] = None
    seller_phone: Optional[str] = None  # NEW
    seller_address: Optional[str] = None  # NEW
    
    # Buyer Information
    buyer_name: Optional[str] = None
    buyer_tax_code: Optional[str] = None
    buyer_address: Optional[str] = None
    
    # Invoice Amounts
    total_before_tax: Optional[float] = 0
    vat_rate: Optional[float] = 0
    vat_amount: Optional[float] = 0
    total_amount: Optional[float] = 0
    
    # Processing Information
    source_email: Optional[str] = None
    source_type: Optional[str] = None
    raw_file_path: Optional[str] = None
    file_format: Optional[str] = None  # NEW
    ai_confidence: Optional[float] = 0
    
    # Signature Information
    signatures: Optional[Dict[str, Any]] = None  # NEW

class InvoiceCreate(InvoiceBase):
    items: Optional[List["InvoiceItemCreate"]] = None

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    signatures: Optional[Dict[str, Any]] = None
    processed_at: Optional[datetime] = None

class InvoiceResponse(InvoiceBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None
    items: List["InvoiceItemResponse"] = []

    class Config:
        from_attributes = True

class InvoiceItemResponse(BaseModel):
    id: int
    invoice_id: int
    product_id: Optional[int] = None
    item_name: str
    unit: Optional[str] = None
    quantity: float
    unit_price: float
    total_price: float
    vat_rate: float = 0
    line_number: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class InvoiceItemCreate(BaseModel):
    item_name: str
    unit: Optional[str] = None
    quantity: float
    unit_price: float
    total_price: float
    vat_rate: float = 0
    line_number: Optional[int] = None

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# Email Log Schemas
class EmailLogResponse(BaseModel):
    id: int
    invoice_id: Optional[int] = None  # NEW
    email_from: Optional[str] = None  # NEW
    email_subject: Optional[str] = None  # NEW - Changed from "subject"
    attachment_name: Optional[str] = None  # NEW
    file_url: Optional[str] = None  # NEW
    message_id: Optional[str] = None  # NEW
    status: str
    error_message: Optional[str] = None  # NEW
    processed_at: Optional[datetime] = None  # NEW
    created_at: datetime

    class Config:
        from_attributes = True


# Signature Schema (NEW)
class SignatureResponse(BaseModel):
    id: int
    invoice_id: int
    signer_name: Optional[str] = None
    signer_role: Optional[str] = None
    signature_date: Optional[datetime] = None
    certificate_cn: Optional[str] = None
    is_valid: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Rebuild models to resolve forward references
InvoiceResponse.model_rebuild()
InvoiceCreate.model_rebuild()
