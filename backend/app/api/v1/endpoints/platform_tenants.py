from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_platform_super_admin_console
from app.models import Tenant, User
from app.schemas.tenant import (
    InvitationCreate,
    InvitationCreatedResponse,
    TenantCreate,
    TenantPlatformPatch,
    TenantResponse,
)
from app.services.master_fields import ensure_default_master_fields
from app.services.role_permissions import ensure_tenant_role_permissions
from app.services.invitations import create_invitation, resend_invitation

router = APIRouter()


@router.get("/tenants", response_model=list[TenantResponse])
def list_tenants(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> list[Tenant]:
    return db.query(Tenant).order_by(Tenant.id.desc()).limit(100).all()


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    body: TenantCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> Tenant:
    exists = db.query(Tenant).filter(Tenant.slug == body.slug).first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Slug already in use")
    tenant = Tenant(name=body.name, slug=body.slug, status="active")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    ensure_tenant_role_permissions(db, tenant.id)
    ensure_default_master_fields(db, tenant.id)
    db.commit()
    return tenant


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
def patch_tenant(
    tenant_id: int,
    body: TenantPlatformPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = body.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(tenant, key, val)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.post(
    "/tenants/{tenant_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation_platform(
    tenant_id: int,
    body: InvitationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> InvitationCreatedResponse:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return create_invitation(db, tenant.id, body, invite_channel="platform")


@router.post(
    "/tenants/{tenant_id}/invitations/{invitation_id}/resend",
    response_model=InvitationCreatedResponse,
)
def resend_invitation_platform(
    tenant_id: int,
    invitation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> InvitationCreatedResponse:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return resend_invitation(db, tenant.id, invitation_id, invite_channel="platform")
