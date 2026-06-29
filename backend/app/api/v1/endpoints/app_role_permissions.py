"""Configure tenant role permissions (Settings > Role Permissions). Firm admin only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_tenant_admin
from app.models import TenantRolePermission
from app.schemas.role_permissions import RolePermissionsOut, RolePermissionsUpdate
from app.services.role_permissions import (
    FIRM_ROLES,
    PERMISSION_GROUPS,
    apply_admin_safety,
    ensure_tenant_role_permissions,
    get_role_permissions_map,
    validate_permissions_payload,
)

router = APIRouter()


@router.get("/role-permissions", response_model=RolePermissionsOut)
def get_role_permissions(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_tenant_admin),
) -> RolePermissionsOut:
    roles = get_role_permissions_map(db, ctx.tenant.id)
    return RolePermissionsOut(roles=roles, groups=PERMISSION_GROUPS)


@router.put("/role-permissions", response_model=RolePermissionsOut)
def put_role_permissions(
    body: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_tenant_admin),
) -> RolePermissionsOut:
    ensure_tenant_role_permissions(db, ctx.tenant.id)
    current = get_role_permissions_map(db, ctx.tenant.id)
    updates: dict[str, dict[str, bool]] = {}
    for role in FIRM_ROLES:
        if role in body.roles:
            updates[role] = validate_permissions_payload(role, body.roles[role])
        else:
            updates[role] = current[role]
    updates = apply_admin_safety(
        ctx.membership.role,
        ctx.membership.user_id,
        current,
        updates,
    )
    for role in FIRM_ROLES:
        row = (
            db.query(TenantRolePermission)
            .filter(
                TenantRolePermission.tenant_id == ctx.tenant.id,
                TenantRolePermission.role == role,
            )
            .first()
        )
        if row is None:
            row = TenantRolePermission(tenant_id=ctx.tenant.id, role=role, permissions_json=updates[role])
            db.add(row)
        else:
            row.permissions_json = updates[role]
    db.commit()
    roles = get_role_permissions_map(db, ctx.tenant.id)
    return RolePermissionsOut(roles=roles, groups=PERMISSION_GROUPS)
