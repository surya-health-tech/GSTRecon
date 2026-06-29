"""Invitation emails for team and platform onboarding."""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy.orm import Session

from app.core.brand import BRAND_NAME
from app.core.config import get_settings
from app.models import Tenant, User
from app.services.email_format import decorate_email_body, tenant_team_signer
from app.services.firm_outbound_email import deliver_firm_email
from app.services.platform_email import platform_email_configured, send_platform_email

log = logging.getLogger(__name__)

InviteChannel = Literal["firm", "platform"]

_ROLE_LABELS = {
    "tenant_admin": "firm admin",
    "manager": "manager",
    "staff": "staff member",
}


def build_accept_invite_url(raw_token: str) -> str:
    base = get_settings().frontend_app_url.rstrip("/")
    return f"{base}/accept-invite?token={raw_token}"


def build_firm_reset_password_url(raw_token: str) -> str:
    base = get_settings().frontend_app_url.rstrip("/")
    return f"{base}/reset-password?token={raw_token}"


def _role_label(role: str) -> str:
    return _ROLE_LABELS.get(role, role.replace("_", " "))


def send_team_invitation_email(
    db: Session,
    *,
    tenant_id: int,
    tenant_name: str,
    to_email: str,
    to_name: str,
    role: str,
    raw_token: str,
    channel: InviteChannel,
) -> tuple[bool, str | None]:
    invite_url = build_accept_invite_url(raw_token)
    settings = get_settings()
    expire_days = settings.invitation_expire_days
    role_text = _role_label(role)

    if channel == "platform":
        subject = f"You're invited to set up {tenant_name} on {BRAND_NAME}"
        body = (
            f"You have been invited to join {tenant_name} on {BRAND_NAME} as the firm's {role_text}.\n\n"
            f"Accept your invitation and create your password:\n{invite_url}\n\n"
            f"This link expires in {expire_days} days and can only be used once.\n\n"
            "If you weren't expecting this, you can ignore this email.\n"
        )
        body = decorate_email_body(
            body,
            recipient_name=to_name,
            signer_name=settings.platform_email_from_name.strip() or BRAND_NAME,
        )
        if not platform_email_configured(db, settings):
            return (
                False,
                "Platform email is not configured. Connect Gmail or Microsoft 365 on the Platform page, "
                "or set PLATFORM_SMTP_HOST and PLATFORM_EMAIL_FROM.",
            )
        try:
            send_platform_email(db, to_email=to_email, subject=subject, body=body, settings=settings)
            return True, None
        except Exception as exc:  # noqa: BLE001
            log.warning("Platform invite email failed for %s: %s", to_email, exc)
            return False, str(exc)

    subject = f"You're invited to join {tenant_name} on {BRAND_NAME}"
    body = (
        f"You have been invited to join {tenant_name} on {BRAND_NAME} as a {role_text}.\n\n"
        f"Accept your invitation and create your password:\n{invite_url}\n\n"
        f"This link expires in {expire_days} days and can only be used once.\n\n"
        "If you weren't expecting this, you can ignore this email.\n"
    )
    body = decorate_email_body(
        body,
        recipient_name=to_name,
        signer_name=tenant_team_signer(tenant_name),
    )
    return deliver_firm_email(
        db,
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        to_email=to_email,
        subject=subject,
        body=body,
    )


def send_firm_password_reset_email(
    db: Session,
    *,
    user: User,
    tenant: Tenant | None,
    raw_token: str,
    ttl_minutes: int,
) -> tuple[bool, str | None]:
    if not user.email:
        return False, "User has no email address"
    reset_url = build_firm_reset_password_url(raw_token)
    settings = get_settings()
    subject = f"Reset your {BRAND_NAME} password"
    body = (
        f"We received a request to reset the password for your {BRAND_NAME} account.\n\n"
        f"Choose a new password:\n{reset_url}\n\n"
        f"This link expires in {ttl_minutes} minutes and can only be used once.\n\n"
        "If you didn't request this, you can ignore this email.\n"
    )

    if user.is_platform_super_admin or tenant is None:
        body = decorate_email_body(
            body,
            recipient_name=user.full_name,
            signer_name=settings.platform_email_from_name.strip() or BRAND_NAME,
        )
        if not platform_email_configured(db, settings):
            return False, "Platform email is not configured."
        try:
            send_platform_email(
                db, to_email=user.email.strip(), subject=subject, body=body, settings=settings
            )
            return True, None
        except Exception as exc:  # noqa: BLE001
            log.warning("Platform password reset email failed for %s: %s", user.email, exc)
            return False, str(exc)

    body = decorate_email_body(
        body,
        recipient_name=user.full_name,
        signer_name=tenant_team_signer(tenant.name),
    )
    return deliver_firm_email(
        db,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        to_email=user.email.strip(),
        subject=subject,
        body=body,
    )
