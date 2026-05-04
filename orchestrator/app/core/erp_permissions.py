"""ERP permission checks — role defaults + per-user overrides.

Role defaults:
  ADMIN:   full access to everything
  MANAGER: read/create/update on all resources, delete on customers/articles/orders
  MEMBER:  read on all, create on customers/orders
  VIEWER:  read-only on customers, articles, orders, dashboard

Per-user overrides in erp_permissions table take precedence.
"""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.erp import ErpPermission
from app.models.user import UserRole

ROLE_DEFAULTS: dict[UserRole, dict[str, dict[str, bool]]] = {
    UserRole.ADMIN: {
        "customers":  {"read": True, "create": True, "update": True, "delete": True},
        "articles":   {"read": True, "create": True, "update": True, "delete": True},
        "orders":     {"read": True, "create": True, "update": True, "delete": True},
        "invoices":   {"read": True, "create": True, "update": True, "delete": True},
        "dashboard":  {"read": True, "create": False, "update": False, "delete": False},
        "audit_log":  {"read": True, "create": False, "update": False, "delete": False},
    },
    UserRole.MANAGER: {
        "customers":  {"read": True, "create": True, "update": True, "delete": True},
        "articles":   {"read": True, "create": True, "update": True, "delete": True},
        "orders":     {"read": True, "create": True, "update": True, "delete": False},
        "invoices":   {"read": True, "create": True, "update": True, "delete": False},
        "dashboard":  {"read": True, "create": False, "update": False, "delete": False},
        "audit_log":  {"read": True, "create": False, "update": False, "delete": False},
    },
    UserRole.MEMBER: {
        "customers":  {"read": True, "create": True, "update": False, "delete": False},
        "articles":   {"read": True, "create": False, "update": False, "delete": False},
        "orders":     {"read": True, "create": True, "update": False, "delete": False},
        "invoices":   {"read": True, "create": True, "update": False, "delete": False},
        "dashboard":  {"read": True, "create": False, "update": False, "delete": False},
        "audit_log":  {"read": False, "create": False, "update": False, "delete": False},
    },
    UserRole.VIEWER: {
        "customers":  {"read": True, "create": False, "update": False, "delete": False},
        "articles":   {"read": True, "create": False, "update": False, "delete": False},
        "orders":     {"read": True, "create": False, "update": False, "delete": False},
        "invoices":   {"read": True, "create": False, "update": False, "delete": False},
        "dashboard":  {"read": True, "create": False, "update": False, "delete": False},
        "audit_log":  {"read": False, "create": False, "update": False, "delete": False},
    },
}

ALL_RESOURCES = ["customers", "articles", "orders", "invoices", "dashboard", "audit_log"]
ALL_ACTIONS = ["read", "create", "update", "delete"]


async def get_user_erp_permissions(user, db: AsyncSession) -> dict[str, dict[str, bool]]:
    """Build the effective permission map for a user: role defaults merged with overrides."""
    role = getattr(user, "role", None)
    defaults = ROLE_DEFAULTS.get(role, ROLE_DEFAULTS[UserRole.VIEWER])

    result = {res: dict(perms) for res, perms in defaults.items()}

    if hasattr(user, "id") and user.id != "__anonymous__":
        rows = await db.execute(
            select(ErpPermission).where(ErpPermission.user_id == user.id)
        )
        for perm in rows.scalars().all():
            if perm.resource in result:
                result[perm.resource] = {
                    "read": perm.can_read,
                    "create": perm.can_create,
                    "update": perm.can_update,
                    "delete": perm.can_delete,
                }

    return result


async def check_erp_permission(
    user, db: AsyncSession, resource: str, action: str
) -> None:
    """Raise 403 if user lacks the specified permission."""
    perms = await get_user_erp_permissions(user, db)
    resource_perms = perms.get(resource, {})
    if not resource_perms.get(action, False):
        raise HTTPException(
            status_code=403,
            detail=f"ERP permission denied: {resource}.{action}",
        )


def erp_permission(resource: str, action: str):
    """FastAPI dependency factory for ERP permission checks.

    Usage: user=Depends(erp_permission("customers", "read"))
    Returns the authenticated user if permitted, raises 403 otherwise.
    """
    async def _check(
        request,
        db: AsyncSession = Depends(get_db),
    ):
        user = await get_current_user(request, db)
        await check_erp_permission(user, db, resource, action)
        return user

    return _check
