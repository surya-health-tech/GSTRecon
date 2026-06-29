"""Send firm transactional mail via optional SMTP."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.transactional_email import firm_invite_smtp_configured, send_firm_invite_smtp

log = logging.getLogger(__name__)


def deliver_firm_email(
    db: Session,
    *,
    tenant_id: int,
    tenant_name: str,
    to_email: str,
    subject: str,
    body: str,
) -> tuple[bool, str | None]:
    _ = db, tenant_id
    settings = get_settings()
    if not firm_invite_smtp_configured(settings):
        return (
            False,
            "Firm email is not configured. Set FIRM_INVITE_SMTP_HOST and FIRM_INVITE_EMAIL_FROM.",
        )
    try:
        send_firm_invite_smtp(
            to_email=to_email,
            subject=subject,
            body=body,
            from_display=tenant_name,
            settings=settings,
        )
        return True, None
    except Exception as exc:  # noqa: BLE001
        log.warning("Firm invite SMTP failed for %s: %s", to_email, exc)
        return False, str(exc)
