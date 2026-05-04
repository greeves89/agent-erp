"""ERP models - Core business entities for the ERP module."""

import enum
import uuid as _uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderType(str, enum.Enum):
    PURCHASE = "purchase"
    SALES = "sales"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class InvoiceType(str, enum.Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class ErpAuditAction(str, enum.Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

class ErpCustomer(Base, TimestampMixin):
    __tablename__ = "erp_customers"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    customer_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_country: Mapped[str | None] = mapped_column(
        String(100), server_default="Deutschland",
    )
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(
        Integer, server_default="30",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    # Relationships
    orders: Mapped[list["ErpOrder"]] = relationship(
        back_populates="customer", foreign_keys="ErpOrder.customer_id",
    )
    invoices: Mapped[list["ErpInvoice"]] = relationship(
        back_populates="customer", foreign_keys="ErpInvoice.customer_id",
    )


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------

class ErpSupplier(Base, TimestampMixin):
    __tablename__ = "erp_suppliers"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    supplier_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_zip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_country: Mapped[str | None] = mapped_column(
        String(100), server_default="Deutschland",
    )
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(
        Integer, server_default="30",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    # Relationships
    articles: Mapped[list["ErpArticle"]] = relationship(back_populates="supplier")
    orders: Mapped[list["ErpOrder"]] = relationship(
        back_populates="supplier", foreign_keys="ErpOrder.supplier_id",
    )
    invoices: Mapped[list["ErpInvoice"]] = relationship(
        back_populates="supplier", foreign_keys="ErpInvoice.supplier_id",
    )


# ---------------------------------------------------------------------------
# Articles / Products
# ---------------------------------------------------------------------------

class ErpArticle(Base, TimestampMixin):
    __tablename__ = "erp_articles"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    article_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), server_default="Stück")
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    selling_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), server_default="19.00",
    )
    stock_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), server_default="0",
    )
    min_stock_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), server_default="0",
    )
    supplier_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_suppliers.id"), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Relationships
    supplier: Mapped["ErpSupplier | None"] = relationship(back_populates="articles")


# ---------------------------------------------------------------------------
# Orders (Purchase & Sales)
# ---------------------------------------------------------------------------

class ErpOrder(Base, TimestampMixin):
    __tablename__ = "erp_orders"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    customer_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_customers.id"), nullable=True,
    )
    supplier_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_suppliers.id"), nullable=True,
    )
    order_date: Mapped[date | None] = mapped_column(Date, server_default=None)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    # Relationships
    customer: Mapped["ErpCustomer | None"] = relationship(
        back_populates="orders", foreign_keys=[customer_id],
    )
    supplier: Mapped["ErpSupplier | None"] = relationship(
        back_populates="orders", foreign_keys=[supplier_id],
    )
    items: Mapped[list["ErpOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan",
    )
    invoices: Mapped[list["ErpInvoice"]] = relationship(back_populates="order")


# ---------------------------------------------------------------------------
# Order Items
# ---------------------------------------------------------------------------

class ErpOrderItem(Base):
    __tablename__ = "erp_order_items"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    order_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_orders.id", ondelete="CASCADE"), nullable=False,
    )
    article_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_articles.id"), nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), server_default="19.00",
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, server_default="1")

    # Relationships
    order: Mapped["ErpOrder"] = relationship(back_populates="items")
    article: Mapped["ErpArticle"] = relationship()


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

class ErpInvoice(Base, TimestampMixin):
    __tablename__ = "erp_invoices"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    invoice_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")
    order_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_orders.id"), nullable=True,
    )
    customer_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_customers.id"), nullable=True,
    )
    supplier_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_suppliers.id"), nullable=True,
    )
    invoice_date: Mapped[date | None] = mapped_column(Date, server_default=None)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )

    # Relationships
    order: Mapped["ErpOrder | None"] = relationship(back_populates="invoices")
    customer: Mapped["ErpCustomer | None"] = relationship(
        back_populates="invoices", foreign_keys=[customer_id],
    )
    supplier: Mapped["ErpSupplier | None"] = relationship(
        back_populates="invoices", foreign_keys=[supplier_id],
    )
    items: Mapped[list["ErpInvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Invoice Items
# ---------------------------------------------------------------------------

class ErpInvoiceItem(Base):
    __tablename__ = "erp_invoice_items"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    invoice_id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_invoices.id", ondelete="CASCADE"), nullable=False,
    )
    article_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("erp_articles.id"), nullable=True,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), server_default="19.00",
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    position: Mapped[int | None] = mapped_column(Integer, server_default="1")

    # Relationships
    invoice: Mapped["ErpInvoice"] = relationship(back_populates="items")
    article: Mapped["ErpArticle | None"] = relationship()


# ---------------------------------------------------------------------------
# Bookings / Journal Entries (Buchungen)
# ---------------------------------------------------------------------------

class ErpBooking(Base):
    __tablename__ = "erp_bookings"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    booking_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    booking_date: Mapped[date | None] = mapped_column(Date, server_default=None)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    debit_account: Mapped[str] = mapped_column(String(20), nullable=False)
    credit_account: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    is_cancelled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    cancelled_by_booking_id: Mapped[_uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None,
    )
    created_by: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )


# ---------------------------------------------------------------------------
# ERP Audit Log (GoBD-compliant)
# ---------------------------------------------------------------------------

class ErpAuditLog(Base):
    __tablename__ = "erp_audit_log"

    id: Mapped[_uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4,
    )
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[_uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    old_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    changed_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    performed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=None,
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


# ---------------------------------------------------------------------------
# User Permissions (RBAC)
# ---------------------------------------------------------------------------

class ErpResource(str, enum.Enum):
    CUSTOMERS = "customers"
    ARTICLES = "articles"
    ORDERS = "orders"
    INVOICES = "invoices"
    DASHBOARD = "dashboard"
    AUDIT_LOG = "audit_log"


class ErpPermission(Base, TimestampMixin):
    """Per-user permission overrides for ERP resources.

    If no row exists for a user+resource, role-based defaults apply.
    An explicit row overrides the role default for that resource.
    """
    __tablename__ = "erp_permissions"
    __table_args__ = (
        {"comment": "Per-user ERP permission overrides"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    can_create: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    can_update: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
