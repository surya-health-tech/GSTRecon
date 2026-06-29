"""Transactional email when a phone-login firm user is created."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.brand import BRAND_NAME
from app.models import TenantMembership, User
from app.services.firm_outbound_email import deliver_firm_email
from app.services.email_format import decorate_email_body, tenant_team_signer

log = logging.getLogger(__name__)


def _tenant_admin_recipients(db: Session, tenant_id: int) -> list[tuple[str, str]]:
    rows = (
        db.query(User)
        .join(TenantMembership, TenantMembership.user_id == User.id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role == "tenant_admin",
            TenantMembership.is_active.is_(True),
            User.is_active.is_(True),
            User.email.isnot(None),
        )
        .all()
    )
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for u in rows:
        if not u.email:
            continue
        e = u.email.strip().lower()
        if not e or e in seen:
            continue
        seen.add(e)
        out.append((e, u.full_name))
    return out


def send_phone_account_created_to_tenant_admins(
    db: Session,
    *,
    tenant_id: int,
    tenant_name: str,
    user_first_name: str,
    user_last_name: str,
    user_full_name: str,
    phone_country_code: str,
    phone_local: str,
    phone_login_digits: str,
    temporary_password: str,
) -> tuple[bool, str | None]:
    """Email tenant admins with the one-time temporary password. Never log the password."""
    recipients = _tenant_admin_recipients(db, tenant_id)
    if not recipients:
        log.warning(
            "Phone account created for %s but no tenant admin email found tenant_id=%s",
            user_full_name,
            tenant_id,
        )
        return False, "No tenant administrator email is configured."

    subject = f"A Phone account has been created for the user {user_first_name} {user_last_name}".strip()
    display_phone = f"{phone_country_code} {phone_local}".strip()
    body = (
        f"Hello,\n\n"
        f"A phone-based login account has been created for the following user:\n\n"
        f"User Name: {user_full_name}\n"
        f"Phone Number: {display_phone}\n"
        f"Login Method: Phone Number\n"
        f"Login Phone Number: {phone_login_digits}\n"
        f"Temporary Password: {temporary_password}\n\n"
        f"The user can log in to the tenant portal using their phone number without the country code "
        f"and the temporary password shown above.\n\n"
        f"SMS OTP login for phone users will be added in the future.\n\n"
        f"Thanks,\n{tenant_name} Team"
    )
    signer = tenant_team_signer(tenant_name)
    last_error: str | None = None
    sent_any = False
    for to_email, admin_name in recipients:
        decorated = decorate_email_body(body, recipient_name=admin_name, signer_name=signer)
        ok, err = deliver_firm_email(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_name or BRAND_NAME,
            to_email=to_email,
            subject=subject,
            body=decorated,
        )
        if ok:
            sent_any = True
            log.info(
                "Phone account admin notice sent tenant_id=%s to_admin=%s for_user=%s",
                tenant_id,
                to_email,
                user_full_name,
            )
        else:
            last_error = err
            log.warning(
                "Phone account admin notice failed tenant_id=%s to_admin=%s: %s",
                tenant_id,
                to_email,
                err or "unknown",
            )
    return sent_any, last_error
