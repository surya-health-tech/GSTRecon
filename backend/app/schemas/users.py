from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FirmUserOut(BaseModel):
    user_id: int
    email: str | None = None
    full_name: str
    role: str
    membership_active: bool
    login_method: str = "email"
    phone: str | None = None
    phone_country_code: str | None = None
    location_id: int | None = None
    location_name: str | None = None
    location_status: str | None = None


TeamMemberKind = Literal["member", "invitation"]
TeamMemberStatus = Literal["active", "inactive", "invited", "expired"]


class TeamMemberRow(BaseModel):
    """Firm team list: active members and outstanding email invitations."""

    kind: TeamMemberKind
    status: TeamMemberStatus
    full_name: str
    email: str | None = None
    role: str
    user_id: int | None = None
    invitation_id: int | None = None
    membership_active: bool | None = None
    login_method: str | None = None
    phone: str | None = None
    phone_country_code: str | None = None
    invitation_expires_at: datetime | None = None
    location_id: int | None = None
    location_name: str | None = None
    location_status: str | None = None


class MembershipStatusUpdate(BaseModel):
    membership_active: bool = Field(description="Whether the user can access this firm")


class MembershipRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(tenant_admin|manager|staff)$")


LoginMethodCreate = Literal["email", "phone_password"]
LoginMethodUpdate = Literal["email", "phone_password", "phone_otp"]


class CreateFirmUserRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(pattern=r"^(tenant_admin|manager|staff)$")
    login_method: LoginMethodCreate
    email: str | None = Field(default=None, max_length=320)
    phone_country_code: str | None = Field(default=None, max_length=8)
    phone: str | None = Field(default=None, max_length=64)
    location_id: int | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        return str(v).strip().lower()


class UpdateFirmUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, pattern=r"^(tenant_admin|manager|staff)$")
    login_method: LoginMethodUpdate | None = None
    email: str | None = Field(default=None, max_length=320)
    phone_country_code: str | None = Field(default=None, max_length=8)
    phone: str | None = Field(default=None, max_length=64)
    location_id: int | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not str(v).strip():
            return None
        return str(v).strip().lower()


class CreateFirmUserResponse(BaseModel):
    mode: Literal["invitation", "user"]
    invitation: "InvitationCreatedResponse | None" = None
    user: FirmUserOut | None = None
    phone_account_email_sent: bool | None = None
    phone_account_email_error: str | None = None


# Avoid circular import at runtime
from app.schemas.tenant import InvitationCreatedResponse  # noqa: E402

CreateFirmUserResponse.model_rebuild()
