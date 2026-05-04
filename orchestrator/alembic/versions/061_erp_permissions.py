"""ERP user permissions table for RBAC.

Revision ID: erp_002_permissions
Revises: erp_001_core_schema
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa

revision = "erp_002_permissions"
down_revision = "erp_001_core_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "erp_permissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resource", sa.String(50), nullable=False),
        sa.Column("can_read", sa.Boolean, server_default="false", nullable=False),
        sa.Column("can_create", sa.Boolean, server_default="false", nullable=False),
        sa.Column("can_update", sa.Boolean, server_default="false", nullable=False),
        sa.Column("can_delete", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "resource", name="uq_erp_perm_user_resource"),
        comment="Per-user ERP permission overrides",
    )


def downgrade() -> None:
    op.drop_table("erp_permissions")
