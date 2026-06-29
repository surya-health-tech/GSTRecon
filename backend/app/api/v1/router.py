from fastapi import APIRouter

from app.api.v1.endpoints import (
    app_clients,
    app_gstr2b_mappings,
    app_master_fields,
    app_purchase_register_mappings,
    app_reconciliation_cases,
    app_role_permissions,
    app_settings,
    app_team,
    auth,
    platform_email,
    platform_tenant_access,
    platform_tenant_delete,
    platform_tenants,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(platform_tenants.router, prefix="/platform", tags=["platform"])
api_router.include_router(platform_tenant_access.router, prefix="/platform", tags=["platform"])
api_router.include_router(platform_email.router, prefix="/platform", tags=["platform"])
api_router.include_router(platform_tenant_delete.router, prefix="/platform", tags=["platform"])
api_router.include_router(app_settings.router, prefix="/app", tags=["app"])
api_router.include_router(app_role_permissions.router, prefix="/app", tags=["app"])
api_router.include_router(app_team.router, prefix="/app", tags=["app"])
api_router.include_router(app_master_fields.router, prefix="/app", tags=["app"])
api_router.include_router(app_purchase_register_mappings.router, prefix="/app", tags=["app"])
api_router.include_router(app_gstr2b_mappings.router, prefix="/app", tags=["app"])
api_router.include_router(app_clients.router, prefix="/app", tags=["app"])
api_router.include_router(app_reconciliation_cases.router, prefix="/app", tags=["app"])
