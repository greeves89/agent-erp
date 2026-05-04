"""ERP Schema - Core business entities

Revision ID: erp_001_core_schema
Revises: z0t1u2v3w4x5
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "erp_001_core_schema"
down_revision = "z0t1u2v3w4x5"
branch_labels = None
depends_on = None

def upgrade():
    # Customers
    op.create_table('erp_customers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('customer_number', sa.String(50), unique=True, nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('contact_person', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('address_street', sa.String(255)),
        sa.Column('address_city', sa.String(100)),
        sa.Column('address_zip', sa.String(20)),
        sa.Column('address_country', sa.String(100), server_default='Deutschland'),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('payment_terms_days', sa.Integer, server_default='30'),
        sa.Column('notes', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

    # Suppliers
    op.create_table('erp_suppliers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('supplier_number', sa.String(50), unique=True, nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('contact_person', sa.String(255)),
        sa.Column('email', sa.String(255)),
        sa.Column('phone', sa.String(50)),
        sa.Column('address_street', sa.String(255)),
        sa.Column('address_city', sa.String(100)),
        sa.Column('address_zip', sa.String(20)),
        sa.Column('address_country', sa.String(100), server_default='Deutschland'),
        sa.Column('tax_id', sa.String(50)),
        sa.Column('payment_terms_days', sa.Integer, server_default='30'),
        sa.Column('notes', sa.Text),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

    # Articles / Products
    op.create_table('erp_articles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('article_number', sa.String(50), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('category', sa.String(100)),
        sa.Column('unit', sa.String(20), server_default='Stück'),
        sa.Column('purchase_price', sa.Numeric(12, 2)),
        sa.Column('selling_price', sa.Numeric(12, 2)),
        sa.Column('tax_rate', sa.Numeric(5, 2), server_default='19.00'),
        sa.Column('stock_quantity', sa.Numeric(12, 2), server_default='0'),
        sa.Column('min_stock_quantity', sa.Numeric(12, 2), server_default='0'),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('erp_suppliers.id'), nullable=True),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Orders (Purchase & Sales)
    op.create_table('erp_orders',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('order_number', sa.String(50), unique=True, nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),  # 'purchase' or 'sales'
        sa.Column('status', sa.String(20), server_default='draft'),  # draft, confirmed, shipped, delivered, cancelled
        sa.Column('customer_id', UUID(as_uuid=True), sa.ForeignKey('erp_customers.id'), nullable=True),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('erp_suppliers.id'), nullable=True),
        sa.Column('order_date', sa.Date, server_default=sa.func.current_date()),
        sa.Column('delivery_date', sa.Date, nullable=True),
        sa.Column('subtotal', sa.Numeric(12, 2), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), server_default='0'),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

    # Order Items
    op.create_table('erp_order_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('erp_orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('erp_articles.id'), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('tax_rate', sa.Numeric(5, 2), server_default='19.00'),
        sa.Column('line_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('position', sa.Integer, server_default='1'),
    )

    # Invoices
    op.create_table('erp_invoices',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('invoice_number', sa.String(50), unique=True, nullable=False),
        sa.Column('invoice_type', sa.String(20), nullable=False),  # 'incoming' or 'outgoing'
        sa.Column('status', sa.String(20), server_default='draft'),  # draft, sent, paid, overdue, cancelled
        sa.Column('order_id', UUID(as_uuid=True), sa.ForeignKey('erp_orders.id'), nullable=True),
        sa.Column('customer_id', UUID(as_uuid=True), sa.ForeignKey('erp_customers.id'), nullable=True),
        sa.Column('supplier_id', UUID(as_uuid=True), sa.ForeignKey('erp_suppliers.id'), nullable=True),
        sa.Column('invoice_date', sa.Date, server_default=sa.func.current_date()),
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('subtotal', sa.Numeric(12, 2), server_default='0'),
        sa.Column('tax_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('total', sa.Numeric(12, 2), server_default='0'),
        sa.Column('paid_amount', sa.Numeric(12, 2), server_default='0'),
        sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

    # Invoice Items
    op.create_table('erp_invoice_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('invoice_id', UUID(as_uuid=True), sa.ForeignKey('erp_invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('article_id', UUID(as_uuid=True), sa.ForeignKey('erp_articles.id'), nullable=True),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('tax_rate', sa.Numeric(5, 2), server_default='19.00'),
        sa.Column('line_total', sa.Numeric(12, 2), nullable=False),
        sa.Column('position', sa.Integer, server_default='1'),
    )

    # Bookings / Journal Entries (Buchungen)
    op.create_table('erp_bookings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('booking_number', sa.String(50), unique=True, nullable=False),
        sa.Column('booking_date', sa.Date, server_default=sa.func.current_date()),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('debit_account', sa.String(20), nullable=False),
        sa.Column('credit_account', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('reference_type', sa.String(50)),  # 'invoice', 'order', 'manual'
        sa.Column('reference_id', UUID(as_uuid=True), nullable=True),
        sa.Column('is_cancelled', sa.Boolean, server_default='false'),
        sa.Column('cancelled_by_booking_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
    )

    # ERP Audit Log (GoBD-compliant)
    op.create_table('erp_audit_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('record_id', UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),  # INSERT, UPDATE, DELETE
        sa.Column('old_values', JSONB, nullable=True),
        sa.Column('new_values', JSONB, nullable=True),
        sa.Column('changed_fields', JSONB, nullable=True),
        sa.Column('performed_by', sa.String(255)),  # user email or agent name
        sa.Column('performed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('session_id', sa.String(255), nullable=True),
    )
    op.create_index('ix_erp_audit_log_table_record', 'erp_audit_log', ['table_name', 'record_id'])
    op.create_index('ix_erp_audit_log_performed_at', 'erp_audit_log', ['performed_at'])

def downgrade():
    op.drop_index('ix_erp_audit_log_performed_at')
    op.drop_index('ix_erp_audit_log_table_record')
    op.drop_table('erp_audit_log')
    op.drop_table('erp_bookings')
    op.drop_table('erp_invoice_items')
    op.drop_table('erp_invoices')
    op.drop_table('erp_order_items')
    op.drop_table('erp_orders')
    op.drop_table('erp_articles')
    op.drop_table('erp_suppliers')
    op.drop_table('erp_customers')
