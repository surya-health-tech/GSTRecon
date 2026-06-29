from pydantic import BaseModel, Field, field_validator

from app.schemas.platform_access import PlatformTenantAccessMe
from app.schemas.tokens import TokenResponse  # noqa: F401 — re-exported for callers


class LoginRequest(BaseModel):
    login_id: str = Field(min_length=3, max_length=320, description="Email or local phone number")
    password: str = Field(min_length=8)
    tenant_slug: str | None = Field(
        default=None,
        max_length=80,
        description="Workspace slug (required when the same phone exists in multiple firms)",
    )

    @field_validator("login_id")
    @classmethod
    def strip_login_id(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Login ID is required")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class MeResponse(BaseModel):
    id: int
    email: str | None = None
    full_name: str
    login_method: str = "email"
    phone: str | None = None
    phone_country_code: str | None = None
    is_platform_super_admin: bool
    tenant_id: int | None = None
    tenant_name: str | None = None
    role: str | None = None
    location_id: int | None = None
    permissions: dict[str, bool] | None = None
    platform_tenant_access: PlatformTenantAccessMe | None = None


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=32)
    password: str = Field(min_length=8)


class AcceptInvitationResponse(BaseModel):
    message: str
    email: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or "@" not in v:
            raise ValueError("Enter a valid email address")
        return v


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32)
    password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str
