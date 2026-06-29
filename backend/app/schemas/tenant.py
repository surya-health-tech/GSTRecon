from pydantic import BaseModel, Field, field_validator

from app.services.tenant_timezone import validate_tenant_timezone


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")


class TenantResponse(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    legal_name: str | None
    timezone: str
    plan_key: str
    max_users: int
    max_clients: int
    storage_limit_mb: int
    max_email_accounts: int

    model_config = {"from_attributes": True}


class TenantPlatformPatch(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=r"^(active|trial|suspended|cancelled)$",
    )
    plan_key: str | None = Field(default=None, min_length=1, max_length=32)
    max_users: int | None = Field(default=None, ge=1, le=100000)
    max_clients: int | None = Field(default=None, ge=1, le=1000000)
    storage_limit_mb: int | None = Field(default=None, ge=1)
    max_email_accounts: int | None = Field(default=None, ge=1, le=1000)


class TenantFirmView(BaseModel):
    id: int
    name: str
    slug: str
    status: str
    legal_name: str | None
    timezone: str
    plan_key: str
    max_users: int
    max_clients: int
    storage_limit_mb: int
    max_email_accounts: int

    model_config = {"from_attributes": True}


class TenantFirmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def check_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_tenant_timezone(v)


class InvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="staff", pattern=r"^(tenant_admin|manager|staff)$")

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("Invalid email")
        return v


class InvitationCreatedResponse(BaseModel):
    invitation_id: int
    email: str
    expires_at: str
    invite_token: str
    invite_url: str
    email_sent: bool
    email_error: str | None = None
    resent: bool = False
