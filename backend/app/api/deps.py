from collections.abc import Generator
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.logging_config import set_request_context
from app.core.security import safe_decode_token
from app.db.session import SessionLocal
from app.models import Tenant, TenantMembership, User
from app.services.platform_tenant_access import (
    CLAIM_ACCESS_SESSION_ID,
    CLAIM_PLATFORM_TENANT_ACCESS,
    CLAIM_TENANT_ID,
    get_active_session,
    tenant_admin_permissions,
)
from app.services.role_permissions import get_permissions_for_member, has_permission

security = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_token_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in is required to continue.",
        )
    return credentials.credentials


_SESSION_INVALID = "Your session has expired or is not valid. Please sign in again."


def get_access_token_payload(token: Annotated[str, Depends(get_token_credentials)]) -> dict[str, Any]:
    payload = safe_decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)
    return payload


def get_current_user_id(
    payload: Annotated[dict[str, Any], Depends(get_access_token_payload)],
) -> int:
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)
    set_request_context(user_id=user_id)
    return user_id


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> User:
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def _reject_platform_tenant_access_token(
    payload: Annotated[dict[str, Any], Depends(get_access_token_payload)],
) -> None:
    if payload.get(CLAIM_PLATFORM_TENANT_ACCESS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exit the tenant portal before using the platform console.",
        )


def require_platform_super_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not user.is_platform_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin only")
    return user


def require_platform_super_admin_console(
    user: Annotated[User, Depends(require_platform_super_admin)],
    _: Annotated[None, Depends(_reject_platform_tenant_access_token)],
) -> User:
    return user


class TenantContext:
    def __init__(
        self,
        tenant: Tenant,
        membership: TenantMembership,
        permissions: dict[str, bool] | None = None,
        *,
        platform_access_session_id: int | None = None,
        is_platform_tenant_access: bool = False,
    ):
        self.tenant = tenant
        self.membership = membership
        self.permissions: dict[str, bool] = permissions or {}
        self.platform_access_session_id = platform_access_session_id
        self.is_platform_tenant_access = is_platform_tenant_access


def get_tenant_context(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    payload: Annotated[dict[str, Any], Depends(get_access_token_payload)],
) -> TenantContext:
    if payload.get(CLAIM_PLATFORM_TENANT_ACCESS):
        if not user.is_platform_super_admin:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)
        try:
            session_id = int(payload[CLAIM_ACCESS_SESSION_ID])
            tenant_id = int(payload[CLAIM_TENANT_ID])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)
        session = get_active_session(db, session_id, user.id, tenant_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant portal access session expired. Open the tenant again from the platform console.",
            )
        tenant = db.get(Tenant, tenant_id)
        if tenant is None or tenant.status not in ("active", "trial"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This firm account is not active.",
            )
        synthetic = TenantMembership(
            user_id=user.id,
            tenant_id=tenant.id,
            role="tenant_admin",
            is_active=True,
        )
        perms = tenant_admin_permissions(db, tenant.id)
        set_request_context(
            tenant_id=tenant.id,
            user_id=user.id,
            platform_access_session_id=session.id,
        )
        return TenantContext(
            tenant=tenant,
            membership=synthetic,
            permissions=perms,
            platform_access_session_id=session.id,
            is_platform_tenant_access=True,
        )

    if user.is_platform_super_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the platform console for this account",
        )
    if payload.get(CLAIM_ACCESS_SESSION_ID) is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_SESSION_INVALID)

    membership = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active firm membership",
        )
    tenant = db.get(Tenant, membership.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found")
    if tenant.status not in ("active", "trial"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This firm account is not active. Contact support if you need help.",
        )
    perms = get_permissions_for_member(db, tenant.id, membership.role)
    set_request_context(tenant_id=tenant.id, user_id=user.id)
    return TenantContext(tenant=tenant, membership=membership, permissions=perms)


def require_permission(permission_key: str):
    def _dep(
        ctx: Annotated[TenantContext, Depends(get_tenant_context)],
    ) -> TenantContext:
        if not has_permission(ctx.permissions, permission_key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return ctx

    return _dep


def require_tenant_admin(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    if ctx.membership.role != "tenant_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator role required",
        )
    return ctx


def require_firm_manager(
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> TenantContext:
    if ctx.membership.role not in ("tenant_admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm administrator or manager role required",
        )
    return ctx
