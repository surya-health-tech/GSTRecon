"""Platform super-admin: enter / exit firm tenant portal with tenant-admin privileges."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import (
    get_access_token_payload,
    get_db,
    require_platform_super_admin,
    require_platform_super_admin_console,
)
from app.models import User
from app.schemas.tokens import TokenResponse
from app.schemas.platform_access import PlatformTenantAccessStartResponse
from app.services.platform_tenant_access import end_tenant_access, start_tenant_access

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    if request.client:
        return request.client.host
    return None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


@router.post(
    "/tenants/{tenant_id}/tenant-access",
    response_model=PlatformTenantAccessStartResponse,
)
def start_platform_tenant_access(
    tenant_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_super_admin_console),
) -> PlatformTenantAccessStartResponse:
    tokens, session = start_tenant_access(
        db,
        admin=admin,
        tenant_id=tenant_id,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    from app.models import Tenant

    tenant = db.get(Tenant, tenant_id)
    return PlatformTenantAccessStartResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        tenant_id=tenant_id,
        tenant_name=tenant.name if tenant else "",
        access_session_id=session.id,
    )


@router.post("/tenant-access/end", response_model=TokenResponse)
def end_platform_tenant_access(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_platform_super_admin),
    payload: dict = Depends(get_access_token_payload),
) -> TokenResponse:
    raw_sid = payload.get("platform_access_session_id")
    session_id: int | None = None
    if raw_sid is not None:
        try:
            session_id = int(raw_sid)
        except (TypeError, ValueError):
            session_id = None
    return end_tenant_access(
        db,
        admin=admin,
        session_id=session_id,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
