from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, get_tenant_context, require_tenant_admin
from app.models import Tenant
from app.schemas.tenant import TenantFirmUpdate, TenantFirmView

router = APIRouter()


@router.get("/tenant", response_model=TenantFirmView)
def get_firm_profile(ctx: TenantContext = Depends(get_tenant_context)) -> Tenant:
    return ctx.tenant


@router.patch("/tenant", response_model=TenantFirmView)
def update_firm_profile(
    body: TenantFirmUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_tenant_admin),
) -> Tenant:
    tenant = db.get(Tenant, ctx.tenant.id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    data = body.model_dump(exclude_unset=True)
    for key, val in data.items():
        setattr(tenant, key, val)
    db.commit()
    db.refresh(tenant)
    return tenant
