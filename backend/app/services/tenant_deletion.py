from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Tenant, TenantMembership, User

logger = logging.getLogger(__name__)


def delete_tenant_storage(tenant_id: int) -> None:
    """Delete tenant-scoped uploaded files from local storage."""
    root = Path(get_settings().file_storage_dir).resolve()
    tenant_dir = (root / str(tenant_id)).resolve()
    if tenant_dir == root or root not in tenant_dir.parents:
        raise ValueError("Refusing to delete outside tenant storage scope")
    if tenant_dir.exists():
        shutil.rmtree(tenant_dir)


def tenant_storage_exists(tenant_id: int) -> bool:
    root = Path(get_settings().file_storage_dir).resolve()
    tenant_dir = (root / str(tenant_id)).resolve()
    if tenant_dir == root or root not in tenant_dir.parents:
        return False
    return tenant_dir.exists()


def user_ids_exclusive_to_tenant(db: Session, tenant_id: int) -> list[int]:
    """Users who are members of this tenant only (no other firm memberships)."""
    member_ids = [
        row[0]
        for row in db.query(TenantMembership.user_id)
        .filter(TenantMembership.tenant_id == tenant_id)
        .distinct()
        .all()
    ]
    exclusive: list[int] = []
    for user_id in member_ids:
        user = db.get(User, user_id)
        if user is None or user.is_platform_super_admin:
            continue
        other_membership = (
            db.query(TenantMembership.id)
            .filter(
                TenantMembership.user_id == user_id,
                TenantMembership.tenant_id != tenant_id,
            )
            .first()
        )
        if other_membership is None:
            exclusive.append(user_id)
    return exclusive


def delete_tenant_row(db: Session, tenant_id: int) -> None:
    """Delete tenant and all DB rows that cascade from tenants.id."""
    deleted = db.query(Tenant).filter(Tenant.id == tenant_id).delete(synchronize_session=False)
    if deleted == 0:
        raise LookupError("Tenant not found")


def hard_delete_tenant(db: Session, tenant_id: int) -> dict[str, int]:
    """
    Hard-delete a tenant: tenant row (DB cascades), exclusive firm users, then upload files.

    User ids are collected before the tenant row is removed, then those accounts are
    deleted so the same email can accept a fresh invite. Users who also belong to other
    tenants are kept. Platform super-admins are never deleted.
    """
    exclusive_user_ids = user_ids_exclusive_to_tenant(db, tenant_id)
    delete_tenant_row(db, tenant_id)
    users_deleted = 0
    if exclusive_user_ids:
        users_deleted = (
            db.query(User)
            .filter(User.id.in_(exclusive_user_ids), User.is_platform_super_admin.is_(False))
            .delete(synchronize_session=False)
        )
        logger.info("Deleted %s user(s) after tenant_id=%s removal", users_deleted, tenant_id)
    db.commit()

    if tenant_storage_exists(tenant_id=tenant_id):
        try:
            delete_tenant_storage(tenant_id=tenant_id)
        except Exception:
            logger.exception("Failed to delete tenant storage for tenant_id=%s", tenant_id)

    return {"users_deleted": users_deleted}
