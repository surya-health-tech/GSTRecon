"""Tenant-scoped role permission keys, defaults, and resolution."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy.orm import Session

from app.models import TenantRolePermission

FIRM_ROLES = ("tenant_admin", "manager", "staff")

PERMISSION_GROUPS: dict[str, list[str]] = {
    "reconciliation": [
        "reconciliation.access",
        "reconciliation.run",
        "reconciliation.view_reports",
        "cases.access",
        "cases.manage",
    ],
    "data_mapping": [
        "data_mapping.access",
        "data_mapping.manage",
    ],
    "clients": [
        "clients.access",
        "clients.manage",
    ],
    "team": [
        "team.view",
        "team.add",
        "team.edit",
        "team.remove",
        "team.assign_roles",
    ],
    "settings": [
        "settings.access",
        "settings.manage_company",
        "settings.manage_role_permissions",
    ],
}

ALL_PERMISSION_KEYS: tuple[str, ...] = tuple(
    key for keys in PERMISSION_GROUPS.values() for key in keys
)


def _all_true() -> dict[str, bool]:
    return {k: True for k in ALL_PERMISSION_KEYS}


def _defaults_tenant_admin() -> dict[str, bool]:
    return _all_true()


def _defaults_manager() -> dict[str, bool]:
    d = _all_true()
    d["settings.manage_role_permissions"] = False
    d["team.assign_roles"] = False
    d["team.remove"] = False
    return d


def _defaults_staff() -> dict[str, bool]:
    d = {k: False for k in ALL_PERMISSION_KEYS}
    d["reconciliation.access"] = True
    d["reconciliation.view_reports"] = True
    d["cases.access"] = True
    d["data_mapping.access"] = True
    d["clients.access"] = True
    return d


DEFAULT_PERMISSIONS_BY_ROLE: dict[str, dict[str, bool]] = {
    "tenant_admin": _defaults_tenant_admin(),
    "manager": _defaults_manager(),
    "staff": _defaults_staff(),
}


def default_permissions_for_role(role: str) -> dict[str, bool]:
    base = DEFAULT_PERMISSIONS_BY_ROLE.get(role, _defaults_staff())
    return copy.deepcopy(base)


def enforce_role_policy(role: str, perms: dict[str, bool]) -> dict[str, bool]:
    out = dict(perms)
    if role != "tenant_admin":
        out["settings.manage_role_permissions"] = False
        out["team.assign_roles"] = False
        out["team.remove"] = False
    else:
        out["settings.manage_role_permissions"] = True
        out["settings.access"] = True
        out["team.assign_roles"] = True
        out["team.remove"] = True
    return out


def merge_permissions(stored: dict[str, Any] | None, role: str) -> dict[str, bool]:
    out = default_permissions_for_role(role)
    if not stored:
        return enforce_role_policy(role, out)
    for key in ALL_PERMISSION_KEYS:
        if key in stored and isinstance(stored[key], bool):
            out[key] = stored[key]
    return enforce_role_policy(role, out)


def ensure_tenant_role_permissions(db: Session, tenant_id: int) -> None:
    for role in FIRM_ROLES:
        existing = (
            db.query(TenantRolePermission)
            .filter(
                TenantRolePermission.tenant_id == tenant_id,
                TenantRolePermission.role == role,
            )
            .first()
        )
        if existing is None:
            db.add(
                TenantRolePermission(
                    tenant_id=tenant_id,
                    role=role,
                    permissions_json=default_permissions_for_role(role),
                )
            )


def get_role_permissions_map(db: Session, tenant_id: int) -> dict[str, dict[str, bool]]:
    ensure_tenant_role_permissions(db, tenant_id)
    db.flush()
    rows = (
        db.query(TenantRolePermission)
        .filter(TenantRolePermission.tenant_id == tenant_id)
        .all()
    )
    by_role = {r.role: merge_permissions(r.permissions_json, r.role) for r in rows}
    for role in FIRM_ROLES:
        by_role.setdefault(role, default_permissions_for_role(role))
    return by_role


def get_permissions_for_member(db: Session, tenant_id: int, role: str) -> dict[str, bool]:
    ensure_tenant_role_permissions(db, tenant_id)
    row = (
        db.query(TenantRolePermission)
        .filter(
            TenantRolePermission.tenant_id == tenant_id,
            TenantRolePermission.role == role,
        )
        .first()
    )
    if row is None:
        return default_permissions_for_role(role)
    return merge_permissions(row.permissions_json, role)


def has_permission(perms: dict[str, bool], key: str) -> bool:
    return bool(perms.get(key, False))


def can_manage_role_permissions(perms: dict[str, bool]) -> bool:
    return has_permission(perms, "settings.manage_role_permissions")


def validate_permissions_payload(role: str, payload: dict[str, bool]) -> dict[str, bool]:
    merged = merge_permissions(payload, role)
    return {k: bool(merged[k]) for k in ALL_PERMISSION_KEYS}


def apply_admin_safety(
    editor_role: str,
    editor_user_id: int,
    all_roles: dict[str, dict[str, bool]],
    updates: dict[str, dict[str, bool]],
) -> dict[str, dict[str, bool]]:
    out = {role: dict(perms) for role, perms in updates.items()}
    if editor_role != "tenant_admin":
        return out
    ta = out.get("tenant_admin", all_roles.get("tenant_admin", {}))
    if not ta.get("settings.manage_role_permissions"):
        ta = dict(all_roles.get("tenant_admin", default_permissions_for_role("tenant_admin")))
        ta["settings.manage_role_permissions"] = True
        ta["settings.access"] = True
        out["tenant_admin"] = ta
    return out
