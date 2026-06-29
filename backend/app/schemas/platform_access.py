from datetime import datetime

from pydantic import BaseModel

from app.schemas.tokens import TokenResponse


class PlatformTenantAccessStartResponse(TokenResponse):
    tenant_id: int
    tenant_name: str
    access_session_id: int


class PlatformTenantAccessMe(BaseModel):
    session_id: int
    tenant_id: int
    tenant_name: str
    started_at: datetime
    platform_admin_name: str
    platform_admin_email: str | None
