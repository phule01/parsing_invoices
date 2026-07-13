"""
routers/products_v2.py

The only change from the original is the removal of the locally-defined
get_current_user_id function, which duplicated the one now in app/core/security.py.
All business logic and endpoints are otherwise identical.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import Product
from auth_schemas import ProductCreate, ProductUpdate, ProductResponse
from app.core.security import get_current_user
from websocket_manager import connection_manager
from app.services.telegram_service import broadcast_to_web_ui

router = APIRouter(prefix="/api/products", tags=["products"])


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[ProductResponse])
async def list_products(
    category: str = Query(None),
    search: str = Query(None),
    low_stock: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    target_user_id: int = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(Product.user_id == current_user.id)
        
    if category:
        query = query.filter(Product.category == category)
    if search:
        query = query.filter(
            Product.name.ilike(f"%{search}%")
            | Product.sku.ilike(f"%{search}%")
            | Product.barcode.ilike(f"%{search}%")
        )
    if low_stock:
        query = query.filter(Product.quantity_in_stock < 10)
    return query.order_by(Product.name).offset(skip).limit(limit).all()


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories")
async def get_categories(
    target_user_id: int = Query(None),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product.category).distinct().filter(
        Product.category.isnot(None),
        Product.user_id == current_user.id
    )
        
    categories = query.all()
    return {"categories": [c[0] for c in categories]}


# ── Get ───────────────────────────────────────────────────────────────────────

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
        
    product = query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query_sku = db.query(Product).filter(Product.sku == product_data.sku, Product.user_id == current_user.id)
    query_bc = db.query(Product).filter(Product.barcode == product_data.barcode, Product.user_id == current_user.id)

    if product_data.sku:
        if query_sku.first():
            raise HTTPException(status_code=400, detail="SKU already exists")
    if product_data.barcode:
        if query_bc.first():
            raise HTTPException(status_code=400, detail="Barcode already exists")

    product = Product(**product_data.model_dump(), user_id=current_user.id)
    db.add(product)
    db.commit()
    db.refresh(product)

    await broadcast_to_web_ui({
        "type": "product_created",
        "title": "✅ Product Created",
        "message": f"Product '{product.name}' created.",
        "entity_type": "product",
        "entity_id": product.id,
        "severity": "success",
    })
    return product


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
        
    product = query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    changes = {}
    for field, value in product_data.model_dump(exclude_unset=True).items():
        old = getattr(product, field)
        if old != value:
            changes[field] = {"old": old, "new": value}
            setattr(product, field, value)

    db.commit()
    db.refresh(product)

    if changes:
        await connection_manager.notify_product_updated(
            product_id=product.id, changes=changes,
            user_id=current_user.id, source="web",
        )
    return product


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
        
    product = query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    name = product.name
    db.delete(product)
    db.commit()

    await broadcast_to_web_ui({
        "type": "product_deleted",
        "title": "✅ Product Deleted",
        "message": f"Product '{name}' deleted.",
        "entity_type": "product",
        "entity_id": product_id,
        "severity": "success",
    })
    return {"message": "Product deleted successfully"}


# ── Stock patch ───────────────────────────────────────────────────────────────

@router.patch("/{product_id}/update-stock")
async def update_stock(
    product_id: int,
    quantity_change: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == current_user.id
    )
        
    product = query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    old_stock = product.quantity_in_stock
    product.quantity_in_stock += quantity_change
    if product.quantity_in_stock < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    db.commit()
    db.refresh(product)

    await connection_manager.notify_product_updated(
        product_id=product.id,
        changes={"quantity_in_stock": {"old": old_stock, "new": product.quantity_in_stock}},
        user_id=current_user.id, source="web",
    )
    return {"message": "Stock updated", "new_stock": product.quantity_in_stock}


# ── Zero-stock cleanup ────────────────────────────────────────────────────────

@router.post("/cleanup/zero-stock")
async def cleanup_zero_stock(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Product).filter(
        ((Product.quantity_in_stock <= 0) | Product.quantity_in_stock.is_(None)),
        Product.user_id == current_user.id
    )
        
    zero = query.all()
    names = [p.name for p in zero]
    for p in zero:
        db.delete(p)
    db.commit()
    return {"deleted_count": len(names), "deleted_products": names}
