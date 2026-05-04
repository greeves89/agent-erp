"""ERP API — customers, articles, orders, invoices, dashboard, audit log.

All monetary values use Decimal (Numeric(12,2) in DB).
UUID primary keys, GoBD-compliant audit logging on every mutation.
"""

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.core.erp_permissions import erp_permission, get_user_erp_permissions
from app.dependencies import require_auth
from app.models.erp import (
    ErpPermission,
    ErpArticle,
    ErpAuditLog,
    ErpCustomer,
    ErpInvoice,
    ErpInvoiceItem,
    ErpOrder,
    ErpOrderItem,
    InvoiceStatus,
    InvoiceType,
    OrderStatus,
    OrderType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/erp", tags=["erp"])


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════


def _user_email(user) -> str:
    """Extract an identifier string from the authenticated user object."""
    return getattr(user, "email", None) or str(getattr(user, "id", "system"))


def _audit(
    db: AsyncSession,
    *,
    table_name: str,
    record_id: uuid.UUID,
    action: str,
    performed_by: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    changed_fields: dict | None = None,
) -> None:
    """Add an ERP audit log entry to the session (flushed on commit)."""
    db.add(ErpAuditLog(
        table_name=table_name,
        record_id=record_id,
        action=action,
        old_values=old_values,
        new_values=new_values,
        changed_fields=changed_fields,
        performed_by=performed_by,
        performed_at=datetime.now(timezone.utc),
    ))


def _serialize_decimal(v):
    """Safely convert Decimal / None to float for JSON serialization."""
    if v is None:
        return None
    return float(v)


def _next_number(prefix: str, current_max: str | None) -> str:
    """Generate next sequential number like K-00001, A-00001, B-00001, etc."""
    if current_max and "-" in current_max:
        num = int(current_max.split("-")[1]) + 1
    else:
        num = 1
    return f"{prefix}-{num:05d}"


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Customers
# ══════════════════════════════════════════════════════════════════════════════


class CustomerCreate(BaseModel):
    company_name: str
    customer_number: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_zip: str | None = None
    address_country: str | None = "Deutschland"
    tax_id: str | None = None
    payment_terms_days: int | None = 30
    notes: str | None = None


class CustomerUpdate(BaseModel):
    company_name: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_zip: str | None = None
    address_country: str | None = None
    tax_id: str | None = None
    payment_terms_days: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class CustomerResponse(BaseModel):
    id: str
    customer_number: str
    company_name: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    address_street: str | None = None
    address_city: str | None = None
    address_zip: str | None = None
    address_country: str | None = None
    tax_id: str | None = None
    payment_terms_days: int | None = None
    notes: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Articles
# ══════════════════════════════════════════════════════════════════════════════


class ArticleCreate(BaseModel):
    name: str
    article_number: str | None = None
    description: str | None = None
    category: str | None = None
    unit: str | None = "Stück"
    purchase_price: float | None = None
    selling_price: float | None = None
    tax_rate: float | None = 19.00
    stock_quantity: float | None = 0
    min_stock_quantity: float | None = 0
    supplier_id: str | None = None


class ArticleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    unit: str | None = None
    purchase_price: float | None = None
    selling_price: float | None = None
    tax_rate: float | None = None
    stock_quantity: float | None = None
    min_stock_quantity: float | None = None
    supplier_id: str | None = None
    is_active: bool | None = None


class ArticleResponse(BaseModel):
    id: str
    article_number: str
    name: str
    description: str | None = None
    category: str | None = None
    unit: str | None = None
    purchase_price: float | None = None
    selling_price: float | None = None
    tax_rate: float | None = None
    stock_quantity: float | None = None
    min_stock_quantity: float | None = None
    supplier_id: str | None = None
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Orders
# ══════════════════════════════════════════════════════════════════════════════


class OrderItemCreate(BaseModel):
    article_id: str
    quantity: float = 1
    unit_price: float | None = None  # None = use article selling_price
    tax_rate: float | None = None    # None = use article tax_rate


class OrderCreate(BaseModel):
    order_type: str = "sales"  # "sales" or "purchase"
    customer_id: str | None = None
    supplier_id: str | None = None
    order_date: str | None = None  # ISO date string, defaults to today
    delivery_date: str | None = None
    notes: str | None = None
    items: list[OrderItemCreate] = []


class OrderStatusUpdate(BaseModel):
    status: str  # draft, confirmed, shipped, delivered, cancelled


class OrderItemResponse(BaseModel):
    id: str
    article_id: str
    article_name: str | None = None
    quantity: float
    unit_price: float
    tax_rate: float | None = None
    line_total: float
    position: int | None = None


class OrderResponse(BaseModel):
    id: str
    order_number: str
    order_type: str
    status: str
    customer_id: str | None = None
    customer_name: str | None = None
    supplier_id: str | None = None
    order_date: str | None = None
    delivery_date: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total: float | None = None
    notes: str | None = None
    items: list[OrderItemResponse] = []
    created_at: str | None = None
    updated_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Invoices
# ══════════════════════════════════════════════════════════════════════════════


class InvoiceFromOrderCreate(BaseModel):
    order_id: str
    due_date: str | None = None  # ISO date, defaults to order_date + payment_terms_days
    notes: str | None = None


class InvoiceItemResponse(BaseModel):
    id: str
    article_id: str | None = None
    description: str
    quantity: float
    unit_price: float
    tax_rate: float | None = None
    line_total: float
    position: int | None = None


class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    invoice_type: str
    status: str
    order_id: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    supplier_id: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total: float | None = None
    paid_amount: float | None = None
    notes: str | None = None
    items: list[InvoiceItemResponse] = []
    created_at: str | None = None
    updated_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Dashboard
# ══════════════════════════════════════════════════════════════════════════════


class DashboardResponse(BaseModel):
    total_customers: int = 0
    total_articles: int = 0
    total_orders: int = 0
    open_orders: int = 0
    total_invoices: int = 0
    overdue_invoices: int = 0
    revenue_total: float = 0
    revenue_this_month: float = 0
    open_receivables: float = 0


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — Audit Log
# ══════════════════════════════════════════════════════════════════════════════


class AuditLogEntryResponse(BaseModel):
    id: str
    table_name: str
    record_id: str
    action: str
    old_values: dict | None = None
    new_values: dict | None = None
    changed_fields: dict | None = None
    performed_by: str | None = None
    performed_at: str | None = None


# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════


def _serialize_customer(c: ErpCustomer) -> dict:
    return {
        "id": str(c.id),
        "customer_number": c.customer_number,
        "company_name": c.company_name,
        "contact_person": c.contact_person,
        "email": c.email,
        "phone": c.phone,
        "address_street": c.address_street,
        "address_city": c.address_city,
        "address_zip": c.address_zip,
        "address_country": c.address_country,
        "tax_id": c.tax_id,
        "payment_terms_days": c.payment_terms_days,
        "notes": c.notes,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _serialize_article(a: ErpArticle) -> dict:
    return {
        "id": str(a.id),
        "article_number": a.article_number,
        "name": a.name,
        "description": a.description,
        "category": a.category,
        "unit": a.unit,
        "purchase_price": _serialize_decimal(a.purchase_price),
        "selling_price": _serialize_decimal(a.selling_price),
        "tax_rate": _serialize_decimal(a.tax_rate),
        "stock_quantity": _serialize_decimal(a.stock_quantity),
        "min_stock_quantity": _serialize_decimal(a.min_stock_quantity),
        "supplier_id": str(a.supplier_id) if a.supplier_id else None,
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _serialize_order_item(item: ErpOrderItem) -> dict:
    article_name = None
    if hasattr(item, "article") and item.article:
        article_name = item.article.name
    return {
        "id": str(item.id),
        "article_id": str(item.article_id),
        "article_name": article_name,
        "quantity": _serialize_decimal(item.quantity),
        "unit_price": _serialize_decimal(item.unit_price),
        "tax_rate": _serialize_decimal(item.tax_rate),
        "line_total": _serialize_decimal(item.line_total),
        "position": item.position,
    }


def _serialize_order(o: ErpOrder) -> dict:
    customer_name = None
    if hasattr(o, "customer") and o.customer:
        customer_name = o.customer.company_name
    items = []
    if hasattr(o, "items") and o.items:
        items = [_serialize_order_item(i) for i in o.items]
    return {
        "id": str(o.id),
        "order_number": o.order_number,
        "order_type": o.order_type,
        "status": o.status,
        "customer_id": str(o.customer_id) if o.customer_id else None,
        "customer_name": customer_name,
        "supplier_id": str(o.supplier_id) if o.supplier_id else None,
        "order_date": o.order_date.isoformat() if o.order_date else None,
        "delivery_date": o.delivery_date.isoformat() if o.delivery_date else None,
        "subtotal": _serialize_decimal(o.subtotal),
        "tax_amount": _serialize_decimal(o.tax_amount),
        "total": _serialize_decimal(o.total),
        "notes": o.notes,
        "items": items,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


def _serialize_invoice_item(item: ErpInvoiceItem) -> dict:
    return {
        "id": str(item.id),
        "article_id": str(item.article_id) if item.article_id else None,
        "description": item.description,
        "quantity": _serialize_decimal(item.quantity),
        "unit_price": _serialize_decimal(item.unit_price),
        "tax_rate": _serialize_decimal(item.tax_rate),
        "line_total": _serialize_decimal(item.line_total),
        "position": item.position,
    }


def _serialize_invoice(inv: ErpInvoice) -> dict:
    customer_name = None
    if hasattr(inv, "customer") and inv.customer:
        customer_name = inv.customer.company_name
    items = []
    if hasattr(inv, "items") and inv.items:
        items = [_serialize_invoice_item(i) for i in inv.items]
    return {
        "id": str(inv.id),
        "invoice_number": inv.invoice_number,
        "invoice_type": inv.invoice_type,
        "status": inv.status,
        "order_id": str(inv.order_id) if inv.order_id else None,
        "customer_id": str(inv.customer_id) if inv.customer_id else None,
        "customer_name": customer_name,
        "supplier_id": str(inv.supplier_id) if inv.supplier_id else None,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "subtotal": _serialize_decimal(inv.subtotal),
        "tax_amount": _serialize_decimal(inv.tax_amount),
        "total": _serialize_decimal(inv.total),
        "paid_amount": _serialize_decimal(inv.paid_amount),
        "notes": inv.notes,
        "items": items,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }


def _serialize_audit_entry(e: ErpAuditLog) -> dict:
    return {
        "id": str(e.id),
        "table_name": e.table_name,
        "record_id": str(e.record_id),
        "action": e.action,
        "old_values": e.old_values,
        "new_values": e.new_values,
        "changed_fields": e.changed_fields,
        "performed_by": e.performed_by,
        "performed_at": e.performed_at.isoformat() if e.performed_at else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/customers")
async def list_customers(
    q: str | None = Query(None, description="Search by name, email, or customer number"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(erp_permission("customers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List customers with optional search and pagination."""
    query = select(ErpCustomer)

    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                ErpCustomer.company_name.ilike(pattern),
                ErpCustomer.contact_person.ilike(pattern),
                ErpCustomer.email.ilike(pattern),
                ErpCustomer.customer_number.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.where(ErpCustomer.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(ErpCustomer.company_name).offset(offset).limit(limit)
    )
    customers = result.scalars().all()

    return {
        "customers": [_serialize_customer(c) for c in customers],
        "total": total or 0,
    }


@router.post("/customers", status_code=201)
async def create_customer(
    body: CustomerCreate,
    user=Depends(erp_permission("customers", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new customer."""
    # Auto-generate customer number if not provided
    customer_number = body.customer_number
    if not customer_number:
        max_num = await db.scalar(
            select(func.max(ErpCustomer.customer_number))
        )
        customer_number = _next_number("K", max_num)

    customer = ErpCustomer(
        customer_number=customer_number,
        company_name=body.company_name,
        contact_person=body.contact_person,
        email=body.email,
        phone=body.phone,
        address_street=body.address_street,
        address_city=body.address_city,
        address_zip=body.address_zip,
        address_country=body.address_country,
        tax_id=body.tax_id,
        payment_terms_days=body.payment_terms_days,
        notes=body.notes,
    )
    db.add(customer)
    await db.flush()

    _audit(
        db,
        table_name="erp_customers",
        record_id=customer.id,
        action="INSERT",
        performed_by=_user_email(user),
        new_values=_serialize_customer(customer),
    )

    await db.commit()
    await db.refresh(customer)

    logger.info(f"ERP: Customer created {customer.customer_number} by {_user_email(user)}")
    return _serialize_customer(customer)


@router.get("/customers/{customer_id}")
async def get_customer(
    customer_id: str,
    user=Depends(erp_permission("customers", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single customer by ID."""
    customer = await db.get(ErpCustomer, uuid.UUID(customer_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _serialize_customer(customer)


@router.put("/customers/{customer_id}")
async def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    user=Depends(erp_permission("customers", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing customer."""
    customer = await db.get(ErpCustomer, uuid.UUID(customer_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    old_values = _serialize_customer(customer)
    changed = {}
    update_data = body.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        old_val = getattr(customer, field, None)
        if old_val != value:
            changed[field] = {"old": old_val, "new": value}
            setattr(customer, field, value)

    if changed:
        _audit(
            db,
            table_name="erp_customers",
            record_id=customer.id,
            action="UPDATE",
            performed_by=_user_email(user),
            old_values=old_values,
            new_values=_serialize_customer(customer),
            changed_fields=changed,
        )
        await db.commit()
        await db.refresh(customer)

    return _serialize_customer(customer)


# ══════════════════════════════════════════════════════════════════════════════
# ARTICLES
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/articles")
async def list_articles(
    q: str | None = Query(None, description="Search by name, SKU, or category"),
    category: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(erp_permission("articles", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List articles with optional search and pagination."""
    query = select(ErpArticle)

    if q:
        pattern = f"%{q}%"
        query = query.where(
            or_(
                ErpArticle.name.ilike(pattern),
                ErpArticle.article_number.ilike(pattern),
                ErpArticle.description.ilike(pattern),
                ErpArticle.category.ilike(pattern),
            )
        )
    if category:
        query = query.where(ErpArticle.category == category)
    if is_active is not None:
        query = query.where(ErpArticle.is_active == is_active)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(ErpArticle.name).offset(offset).limit(limit)
    )
    articles = result.scalars().all()

    return {
        "articles": [_serialize_article(a) for a in articles],
        "total": total or 0,
    }


@router.post("/articles", status_code=201)
async def create_article(
    body: ArticleCreate,
    user=Depends(erp_permission("articles", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new article."""
    article_number = body.article_number
    if not article_number:
        max_num = await db.scalar(
            select(func.max(ErpArticle.article_number))
        )
        article_number = _next_number("A", max_num)

    article = ErpArticle(
        article_number=article_number,
        name=body.name,
        description=body.description,
        category=body.category,
        unit=body.unit,
        purchase_price=Decimal(str(body.purchase_price)) if body.purchase_price is not None else None,
        selling_price=Decimal(str(body.selling_price)) if body.selling_price is not None else None,
        tax_rate=Decimal(str(body.tax_rate)) if body.tax_rate is not None else None,
        stock_quantity=Decimal(str(body.stock_quantity)) if body.stock_quantity is not None else None,
        min_stock_quantity=Decimal(str(body.min_stock_quantity)) if body.min_stock_quantity is not None else None,
        supplier_id=uuid.UUID(body.supplier_id) if body.supplier_id else None,
    )
    db.add(article)
    await db.flush()

    _audit(
        db,
        table_name="erp_articles",
        record_id=article.id,
        action="INSERT",
        performed_by=_user_email(user),
        new_values=_serialize_article(article),
    )

    await db.commit()
    await db.refresh(article)

    logger.info(f"ERP: Article created {article.article_number} by {_user_email(user)}")
    return _serialize_article(article)


# ══════════════════════════════════════════════════════════════════════════════
# ORDERS
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/orders")
async def list_orders(
    order_type: str | None = Query(None, description="Filter: sales or purchase"),
    status: str | None = Query(None, description="Filter by status"),
    customer_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(erp_permission("orders", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List orders with optional filters and pagination."""
    query = select(ErpOrder).options(
        selectinload(ErpOrder.customer),
        selectinload(ErpOrder.items).selectinload(ErpOrderItem.article),
    )

    if order_type:
        query = query.where(ErpOrder.order_type == order_type)
    if status:
        query = query.where(ErpOrder.status == status)
    if customer_id:
        query = query.where(ErpOrder.customer_id == uuid.UUID(customer_id))

    total = await db.scalar(
        select(func.count()).select_from(
            select(ErpOrder.id).where(
                *([ErpOrder.order_type == order_type] if order_type else []),
                *([ErpOrder.status == status] if status else []),
                *([ErpOrder.customer_id == uuid.UUID(customer_id)] if customer_id else []),
            ).subquery()
        )
    )

    result = await db.execute(
        query.order_by(desc(ErpOrder.created_at)).offset(offset).limit(limit)
    )
    orders = result.scalars().unique().all()

    return {
        "orders": [_serialize_order(o) for o in orders],
        "total": total or 0,
    }


@router.post("/orders", status_code=201)
async def create_order(
    body: OrderCreate,
    user=Depends(erp_permission("orders", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new order with line items.

    For sales orders, customer_id is expected.
    For purchase orders, supplier_id is expected.
    If item unit_price or tax_rate is not set, the article's values are used.
    """
    # Validate order type
    valid_types = {e.value for e in OrderType}
    if body.order_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_type. Must be one of: {sorted(valid_types)}",
        )

    # Generate order number
    prefix = "SO" if body.order_type == "sales" else "PO"
    max_num = await db.scalar(
        select(func.max(ErpOrder.order_number)).where(
            ErpOrder.order_type == body.order_type,
        )
    )
    order_number = _next_number(prefix, max_num)

    # Parse dates
    order_date = date.fromisoformat(body.order_date) if body.order_date else date.today()
    delivery_date = date.fromisoformat(body.delivery_date) if body.delivery_date else None

    order = ErpOrder(
        order_number=order_number,
        order_type=body.order_type,
        status=OrderStatus.DRAFT.value,
        customer_id=uuid.UUID(body.customer_id) if body.customer_id else None,
        supplier_id=uuid.UUID(body.supplier_id) if body.supplier_id else None,
        order_date=order_date,
        delivery_date=delivery_date,
        notes=body.notes,
    )
    db.add(order)
    await db.flush()

    # Add items
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    position = 1

    for item_data in body.items:
        article = await db.get(ErpArticle, uuid.UUID(item_data.article_id))
        if not article:
            raise HTTPException(
                status_code=400,
                detail=f"Article {item_data.article_id} not found",
            )

        qty = Decimal(str(item_data.quantity))

        # Use provided price or fall back to article price
        if item_data.unit_price is not None:
            unit_price = Decimal(str(item_data.unit_price))
        elif body.order_type == "purchase" and article.purchase_price:
            unit_price = article.purchase_price
        elif article.selling_price:
            unit_price = article.selling_price
        else:
            unit_price = Decimal("0")

        tax_rate = Decimal(str(item_data.tax_rate)) if item_data.tax_rate is not None else (article.tax_rate or Decimal("19"))

        line_total = qty * unit_price
        line_tax = line_total * tax_rate / Decimal("100")

        order_item = ErpOrderItem(
            order_id=order.id,
            article_id=article.id,
            quantity=qty,
            unit_price=unit_price,
            tax_rate=tax_rate,
            line_total=line_total,
            position=position,
        )
        db.add(order_item)

        subtotal += line_total
        tax_total += line_tax
        position += 1

    order.subtotal = subtotal
    order.tax_amount = tax_total
    order.total = subtotal + tax_total

    _audit(
        db,
        table_name="erp_orders",
        record_id=order.id,
        action="INSERT",
        performed_by=_user_email(user),
        new_values={"order_number": order_number, "total": float(order.total)},
    )

    await db.commit()

    # Re-fetch with relationships
    result = await db.execute(
        select(ErpOrder)
        .options(
            selectinload(ErpOrder.customer),
            selectinload(ErpOrder.items).selectinload(ErpOrderItem.article),
        )
        .where(ErpOrder.id == order.id)
    )
    order = result.scalars().first()

    logger.info(f"ERP: Order created {order_number} by {_user_email(user)}")
    return _serialize_order(order)


@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    user=Depends(erp_permission("orders", "update")),
    db: AsyncSession = Depends(get_db),
):
    """Update the status of an order.

    Valid transitions: draft -> confirmed -> shipped -> delivered
    Cancellation is allowed from any non-delivered status.
    """
    valid_statuses = {e.value for e in OrderStatus}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {sorted(valid_statuses)}",
        )

    order = await db.get(ErpOrder, uuid.UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status

    # Validate state transition
    allowed_transitions = {
        "draft": {"confirmed", "cancelled"},
        "confirmed": {"shipped", "cancelled"},
        "shipped": {"delivered", "cancelled"},
        "delivered": set(),
        "cancelled": set(),
    }
    if body.status not in allowed_transitions.get(old_status, set()):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{old_status}' to '{body.status}'",
        )

    order.status = body.status

    _audit(
        db,
        table_name="erp_orders",
        record_id=order.id,
        action="UPDATE",
        performed_by=_user_email(user),
        changed_fields={"status": {"old": old_status, "new": body.status}},
    )

    await db.commit()
    await db.refresh(order)

    logger.info(
        f"ERP: Order {order.order_number} status {old_status} -> {body.status} "
        f"by {_user_email(user)}"
    )
    return {"id": str(order.id), "order_number": order.order_number, "status": order.status}


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/invoices")
async def list_invoices(
    status: str | None = Query(None),
    invoice_type: str | None = Query(None),
    customer_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user=Depends(erp_permission("invoices", "read")),
    db: AsyncSession = Depends(get_db),
):
    """List invoices with optional filters and pagination."""
    query = select(ErpInvoice).options(
        selectinload(ErpInvoice.customer),
        selectinload(ErpInvoice.items),
    )

    if status:
        query = query.where(ErpInvoice.status == status)
    if invoice_type:
        query = query.where(ErpInvoice.invoice_type == invoice_type)
    if customer_id:
        query = query.where(ErpInvoice.customer_id == uuid.UUID(customer_id))

    total = await db.scalar(
        select(func.count()).select_from(
            select(ErpInvoice.id).where(
                *([ErpInvoice.status == status] if status else []),
                *([ErpInvoice.invoice_type == invoice_type] if invoice_type else []),
                *([ErpInvoice.customer_id == uuid.UUID(customer_id)] if customer_id else []),
            ).subquery()
        )
    )

    result = await db.execute(
        query.order_by(desc(ErpInvoice.created_at)).offset(offset).limit(limit)
    )
    invoices = result.scalars().unique().all()

    return {
        "invoices": [_serialize_invoice(inv) for inv in invoices],
        "total": total or 0,
    }


@router.post("/invoices", status_code=201)
async def create_invoice_from_order(
    body: InvoiceFromOrderCreate,
    user=Depends(erp_permission("invoices", "create")),
    db: AsyncSession = Depends(get_db),
):
    """Create an invoice from an existing order.

    Copies all order items as invoice items. Sets invoice_type based on
    order_type (sales -> outgoing, purchase -> incoming).
    """
    # Fetch order with items
    result = await db.execute(
        select(ErpOrder)
        .options(
            selectinload(ErpOrder.items).selectinload(ErpOrderItem.article),
            selectinload(ErpOrder.customer),
        )
        .where(ErpOrder.id == uuid.UUID(body.order_id))
    )
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatus.CANCELLED.value:
        raise HTTPException(status_code=400, detail="Cannot invoice a cancelled order")

    # Determine invoice type from order type
    inv_type = InvoiceType.OUTGOING.value if order.order_type == OrderType.SALES.value else InvoiceType.INCOMING.value

    # Generate invoice number
    prefix = "RE" if inv_type == "outgoing" else "ER"
    max_num = await db.scalar(
        select(func.max(ErpInvoice.invoice_number)).where(
            ErpInvoice.invoice_type == inv_type,
        )
    )
    invoice_number = _next_number(prefix, max_num)

    # Calculate due date
    if body.due_date:
        due_date = date.fromisoformat(body.due_date)
    else:
        payment_days = 30
        if order.customer and order.customer.payment_terms_days:
            payment_days = order.customer.payment_terms_days
        due_date = date.today() + timedelta(days=payment_days)

    invoice = ErpInvoice(
        invoice_number=invoice_number,
        invoice_type=inv_type,
        status=InvoiceStatus.DRAFT.value,
        order_id=order.id,
        customer_id=order.customer_id,
        supplier_id=order.supplier_id,
        invoice_date=date.today(),
        due_date=due_date,
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        total=order.total,
        notes=body.notes,
    )
    db.add(invoice)
    await db.flush()

    # Copy order items to invoice items
    position = 1
    for oi in order.items:
        article_name = oi.article.name if oi.article else ""
        inv_item = ErpInvoiceItem(
            invoice_id=invoice.id,
            article_id=oi.article_id,
            description=article_name,
            quantity=oi.quantity,
            unit_price=oi.unit_price,
            tax_rate=oi.tax_rate,
            line_total=oi.line_total,
            position=position,
        )
        db.add(inv_item)
        position += 1

    _audit(
        db,
        table_name="erp_invoices",
        record_id=invoice.id,
        action="INSERT",
        performed_by=_user_email(user),
        new_values={
            "invoice_number": invoice_number,
            "order_number": order.order_number,
            "total": float(invoice.total) if invoice.total else 0,
        },
    )

    await db.commit()

    # Re-fetch with relationships
    result = await db.execute(
        select(ErpInvoice)
        .options(
            selectinload(ErpInvoice.customer),
            selectinload(ErpInvoice.items),
        )
        .where(ErpInvoice.id == invoice.id)
    )
    invoice = result.scalars().first()

    logger.info(f"ERP: Invoice {invoice_number} created from order {order.order_number} by {_user_email(user)}")
    return _serialize_invoice(invoice)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/dashboard")
async def erp_dashboard(
    user=Depends(erp_permission("dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    """ERP dashboard with key metrics.

    Returns totals for customers, articles, orders, plus revenue and
    overdue invoice counts.
    """
    total_customers = await db.scalar(
        select(func.count()).select_from(ErpCustomer).where(ErpCustomer.is_active == True)  # noqa: E712
    ) or 0

    total_articles = await db.scalar(
        select(func.count()).select_from(ErpArticle).where(ErpArticle.is_active == True)  # noqa: E712
    ) or 0

    total_orders = await db.scalar(
        select(func.count()).select_from(ErpOrder)
    ) or 0

    open_orders = await db.scalar(
        select(func.count()).select_from(ErpOrder).where(
            ErpOrder.status.in_([
                OrderStatus.DRAFT.value,
                OrderStatus.CONFIRMED.value,
                OrderStatus.SHIPPED.value,
            ])
        )
    ) or 0

    total_invoices = await db.scalar(
        select(func.count()).select_from(ErpInvoice)
    ) or 0

    overdue_invoices = await db.scalar(
        select(func.count()).select_from(ErpInvoice).where(
            ErpInvoice.status == InvoiceStatus.OVERDUE.value,
        )
    ) or 0

    # Also count sent invoices past due date as overdue
    overdue_invoices_by_date = await db.scalar(
        select(func.count()).select_from(ErpInvoice).where(
            ErpInvoice.status == InvoiceStatus.SENT.value,
            ErpInvoice.due_date < date.today(),
        )
    ) or 0
    overdue_invoices += overdue_invoices_by_date

    # Revenue: sum of paid outgoing invoices
    revenue_total = await db.scalar(
        select(func.coalesce(func.sum(ErpInvoice.total), 0)).where(
            ErpInvoice.invoice_type == InvoiceType.OUTGOING.value,
            ErpInvoice.status == InvoiceStatus.PAID.value,
        )
    ) or 0

    # Revenue this month
    first_of_month = date.today().replace(day=1)
    revenue_this_month = await db.scalar(
        select(func.coalesce(func.sum(ErpInvoice.total), 0)).where(
            ErpInvoice.invoice_type == InvoiceType.OUTGOING.value,
            ErpInvoice.status == InvoiceStatus.PAID.value,
            ErpInvoice.invoice_date >= first_of_month,
        )
    ) or 0

    # Open receivables: sum of outgoing invoices not yet paid
    open_receivables = await db.scalar(
        select(func.coalesce(func.sum(ErpInvoice.total - ErpInvoice.paid_amount), 0)).where(
            ErpInvoice.invoice_type == InvoiceType.OUTGOING.value,
            ErpInvoice.status.in_([InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value]),
        )
    ) or 0

    return {
        "total_customers": total_customers,
        "total_articles": total_articles,
        "total_orders": total_orders,
        "open_orders": open_orders,
        "total_invoices": total_invoices,
        "overdue_invoices": overdue_invoices,
        "revenue_total": float(revenue_total),
        "revenue_this_month": float(revenue_this_month),
        "open_receivables": float(open_receivables),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ══════════════════════════════════════════════════════════════════════════════


@router.get("/audit-log")
async def list_audit_log(
    table_name: str | None = Query(None, description="Filter by table (e.g. erp_customers)"),
    record_id: str | None = Query(None, description="Filter by record UUID"),
    action: str | None = Query(None, description="Filter by action (INSERT, UPDATE, DELETE)"),
    since: Optional[datetime] = Query(None, description="Return entries after this timestamp"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user=Depends(erp_permission("audit_log", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Query the ERP audit log. GoBD-compliant, immutable entries."""
    query = select(ErpAuditLog)

    if table_name:
        query = query.where(ErpAuditLog.table_name == table_name)
    if record_id:
        query = query.where(ErpAuditLog.record_id == uuid.UUID(record_id))
    if action:
        query = query.where(ErpAuditLog.action == action)
    if since:
        query = query.where(ErpAuditLog.performed_at >= since)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    result = await db.execute(
        query.order_by(desc(ErpAuditLog.performed_at)).offset(offset).limit(limit)
    )
    entries = result.scalars().all()

    return {
        "entries": [_serialize_audit_entry(e) for e in entries],
        "total": total or 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════


class PermissionSet(BaseModel):
    resource: str
    can_read: bool = False
    can_create: bool = False
    can_update: bool = False
    can_delete: bool = False


class SetPermissionsBody(BaseModel):
    user_id: str
    permissions: list[PermissionSet]


@router.get("/permissions/me")
async def my_erp_permissions(
    user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Return the effective ERP permissions for the current user."""
    perms = await get_user_erp_permissions(user, db)
    return {"permissions": perms, "role": getattr(user, "role", None)}


@router.get("/permissions/{user_id}")
async def get_user_permissions(
    user_id: str,
    user=Depends(erp_permission("audit_log", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Return effective permissions for a specific user (admin/manager only)."""
    from app.models.user import User
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    perms = await get_user_erp_permissions(target, db)
    return {
        "user_id": user_id,
        "name": target.name,
        "role": target.role,
        "permissions": perms,
    }


@router.put("/permissions")
async def set_user_permissions(
    body: SetPermissionsBody,
    user=Depends(erp_permission("audit_log", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Set per-user ERP permission overrides (admin/manager only)."""
    from app.models.user import User, UserRole
    if getattr(user, "role", None) not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(status_code=403, detail="Only admin/manager can manage permissions")

    target = await db.get(User, body.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await db.execute(
        select(ErpPermission).where(ErpPermission.user_id == body.user_id)
    )
    for row in existing.scalars().all():
        await db.delete(row)

    for perm in body.permissions:
        db.add(ErpPermission(
            user_id=body.user_id,
            resource=perm.resource,
            can_read=perm.can_read,
            can_create=perm.can_create,
            can_update=perm.can_update,
            can_delete=perm.can_delete,
        ))

    _audit(
        db,
        table_name="erp_permissions",
        record_id=uuid.uuid5(uuid.NAMESPACE_URL, body.user_id),
        action="UPDATE",
        performed_by=_user_email(user),
        new_values={"user_id": body.user_id, "permissions": [p.model_dump() for p in body.permissions]},
    )

    await db.commit()
    return {"status": "ok", "user_id": body.user_id, "overrides": len(body.permissions)}


@router.delete("/permissions/{user_id}")
async def reset_user_permissions(
    user_id: str,
    user=Depends(erp_permission("audit_log", "read")),
    db: AsyncSession = Depends(get_db),
):
    """Remove all per-user overrides, resetting to role defaults (admin only)."""
    from app.models.user import UserRole
    if getattr(user, "role", None) != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can reset permissions")

    existing = await db.execute(
        select(ErpPermission).where(ErpPermission.user_id == user_id)
    )
    count = 0
    for row in existing.scalars().all():
        await db.delete(row)
        count += 1

    _audit(
        db,
        table_name="erp_permissions",
        record_id=uuid.uuid5(uuid.NAMESPACE_URL, user_id),
        action="DELETE",
        performed_by=_user_email(user),
        old_values={"user_id": user_id, "overrides_removed": count},
    )

    await db.commit()
    return {"status": "ok", "user_id": user_id, "overrides_removed": count}
