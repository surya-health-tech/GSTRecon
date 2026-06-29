"""Platform super-admin secure access into firm tenant portals."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token
from app.models import PlatformAuditLog, PlatformTenantAccessSession, Tenant, User
from app.schemas.tokens import TokenResponse
from app.services.role_permissions import get_permissions_for_member

CLAIM_PLATFORM_TENANT_ACCESS = "platform_tenant_access"
CLAIM_ACCESS_SESSION_ID = "platform_access_session_id"
CLAIM_TENANT_ID = "tenant_id"
CLAIM_EFFECTIVE_ROLE = "effective_role"

TENANT_ACCESS_ALLOWED_STATUSES = ("active", "trial")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def platform_audit(
    db: Session,
    *,
    platform_admin_user_id: int,
    action: str,
    tenant_id: int | None = None,
    access_session_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        PlatformAuditLog(
            platform_admin_user_id=platform_admin_user_id,
            tenant_id=tenant_id,
            access_session_id=access_session_id,
            action=action,
            detail=detail,
            ip_address=ip_address,
            user_agent=(user_agent[:512] if user_agent else None),
        )
    )


def end_active_sessions_for_admin(
    db: Session,
    *,
    admin_user_id: int,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> list[PlatformTenantAccessSession]:
    """End all open tenant-access sessions for this platform admin."""
    now = _now()
    rows = (
        db.query(PlatformTenantAccessSession)
        .filter(
            PlatformTenantAccessSession.platform_admin_user_id == admin_user_id,
            PlatformTenantAccessSession.ended_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.ended_at = now
        tenant = db.get(Tenant, row.tenant_id)
        platform_audit(
            db,
            platform_admin_user_id=admin_user_id,
            tenant_id=row.tenant_id,
            access_session_id=row.id,
            action="tenant_access_ended",
            detail=f"session ended (switch or exit); tenant={tenant.name if tenant else row.tenant_id}",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    return rows


def get_active_session(
    db: Session, session_id: int, admin_user_id: int, tenant_id: int
) -> PlatformTenantAccessSession | None:
    return (
        db.query(PlatformTenantAccessSession)
        .filter(
            PlatformTenantAccessSession.id == session_id,
            PlatformTenantAccessSession.platform_admin_user_id == admin_user_id,
            PlatformTenantAccessSession.tenant_id == tenant_id,
            PlatformTenantAccessSession.ended_at.is_(None),
        )
        .first()
    )


def require_tenant_for_access(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.status not in TENANT_ACCESS_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This tenant is not active. Activate the tenant before opening its portal.",
        )
    return tenant


def token_claims_for_platform_tenant_access(
    *, session_id: int, tenant_id: int
) -> dict:
    return {
        "is_platform_super_admin": True,
        CLAIM_PLATFORM_TENANT_ACCESS: True,
        CLAIM_ACCESS_SESSION_ID: session_id,
        CLAIM_TENANT_ID: tenant_id,
        CLAIM_EFFECTIVE_ROLE: "tenant_admin",
    }


def token_claims_platform_console() -> dict:
    return {"is_platform_super_admin": True}


def issue_tokens_for_user(db: Session, user: User, *, access_claims: dict) -> TokenResponse:
    refresh_claims: dict = {}
    if access_claims.get(CLAIM_ACCESS_SESSION_ID):
        refresh_claims[CLAIM_ACCESS_SESSION_ID] = access_claims[CLAIM_ACCESS_SESSION_ID]
    access = create_access_token(str(user.id), extra_claims=access_claims)
    refresh = create_refresh_token(str(user.id), extra_claims=refresh_claims or None)
    return TokenResponse(access_token=access, refresh_token=refresh)


def start_tenant_access(
    db: Session,
    *,
    admin: User,
    tenant_id: int,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[TokenResponse, PlatformTenantAccessSession]:
    if not admin.is_platform_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin only")
    tenant = require_tenant_for_access(db, tenant_id)
    end_active_sessions_for_admin(
        db, admin_user_id=admin.id, ip_address=ip_address, user_agent=user_agent
    )
    session = PlatformTenantAccessSession(
        platform_admin_user_id=admin.id,
        tenant_id=tenant.id,
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
    )
    db.add(session)
    db.flush()
    platform_audit(
        db,
        platform_admin_user_id=admin.id,
        tenant_id=tenant.id,
        access_session_id=session.id,
        action="tenant_access_started",
        detail=f"Platform admin opened tenant portal: {tenant.name}",
        ip_address=ip_address,
        user_agent=user_agent,
    )
    claims = token_claims_for_platform_tenant_access(session_id=session.id, tenant_id=tenant.id)
    tokens = issue_tokens_for_user(db, admin, access_claims=claims)
    db.commit()
    db.refresh(session)
    return tokens, session


def end_tenant_access(
    db: Session,
    *,
    admin: User,
    session_id: int | None,
    ip_address: str | None,
    user_agent: str | None,
) -> TokenResponse:
    if not admin.is_platform_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin only")
    now = _now()
    if session_id is not None:
        row = (
            db.query(PlatformTenantAccessSession)
            .filter(
                PlatformTenantAccessSession.id == session_id,
                PlatformTenantAccessSession.platform_admin_user_id == admin.id,
                PlatformTenantAccessSession.ended_at.is_(None),
            )
            .first()
        )
        if row is not None:
            row.ended_at = now
            tenant = db.get(Tenant, row.tenant_id)
            platform_audit(
                db,
                platform_admin_user_id=admin.id,
                tenant_id=row.tenant_id,
                access_session_id=row.id,
                action="tenant_access_ended",
                detail=f"Platform admin exited tenant portal: {tenant.name if tenant else row.tenant_id}",
                ip_address=ip_address,
                user_agent=user_agent,
            )
    else:
        end_active_sessions_for_admin(
            db, admin_user_id=admin.id, ip_address=ip_address, user_agent=user_agent
        )
    tokens = issue_tokens_for_user(db, admin, access_claims=token_claims_platform_console())
    db.commit()
    return tokens


def resolve_access_claims_from_refresh(
    db: Session, user: User, refresh_payload: dict
) -> dict:
    """Rebuild access-token claims after refresh, preserving active tenant access if valid."""
    if not user.is_platform_super_admin:
        return {"is_platform_super_admin": False}
    raw_sid = refresh_payload.get(CLAIM_ACCESS_SESSION_ID)
    if raw_sid is None:
        return token_claims_platform_console()
    try:
        session_id = int(raw_sid)
    except (TypeError, ValueError):
        return token_claims_platform_console()
    row = (
        db.query(PlatformTenantAccessSession)
        .filter(
            PlatformTenantAccessSession.id == session_id,
            PlatformTenantAccessSession.platform_admin_user_id == user.id,
            PlatformTenantAccessSession.ended_at.is_(None),
        )
        .first()
    )
    if row is None:
        return token_claims_platform_console()
    tenant = db.get(Tenant, row.tenant_id)
    if tenant is None or tenant.status not in TENANT_ACCESS_ALLOWED_STATUSES:
        row.ended_at = _now()
        db.commit()
        return token_claims_platform_console()
    return token_claims_for_platform_tenant_access(session_id=row.id, tenant_id=row.tenant_id)


def tenant_admin_permissions(db: Session, tenant_id: int) -> dict[str, bool]:
    return get_permissions_for_member(db, tenant_id, "tenant_admin")
