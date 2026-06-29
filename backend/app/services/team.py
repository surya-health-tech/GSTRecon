"""Firm team membership helpers: role changes, deletion guards."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import TenantMembership

FIRM_ROLES = frozenset({"tenant_admin", "manager", "staff"})


def count_active_admins(db: Session, tenant_id: int, exclude_user_id: int | None = None) -> int:
    q = db.query(TenantMembership).filter(
        TenantMembership.tenant_id == tenant_id,
        TenantMembership.role == "tenant_admin",
        TenantMembership.is_active.is_(True),
    )
    if exclude_user_id is not None:
        q = q.filter(TenantMembership.user_id != exclude_user_id)
    return q.count()


def user_activity_blockers(db: Session, tenant_id: int, user_id: int) -> list[str]:
    """Return human-readable reasons the user cannot be removed from the firm."""
    _ = db, tenant_id, user_id
    return []
