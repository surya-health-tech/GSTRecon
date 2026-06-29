"""SMTP delivery for platform and optional firm transactional mail."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email import policy
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.brand import BRAND_NAME
from app.core.config import Settings, get_settings
from app.services.oauth_http import http_ssl_context

log = logging.getLogger(__name__)


def platform_smtp_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.platform_smtp_host.strip() and s.platform_email_from.strip())


def firm_invite_smtp_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return bool(s.firm_invite_smtp_host.strip() and s.firm_invite_email_from.strip())


def send_platform_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not platform_smtp_configured(s):
        raise RuntimeError(
            "Platform email is not configured. Set PLATFORM_SMTP_HOST and PLATFORM_EMAIL_FROM."
        )
    _send_smtp(
        host=s.platform_smtp_host.strip(),
        port=s.platform_smtp_port,
        user=s.platform_smtp_user.strip(),
        password=s.platform_smtp_password,
        use_tls=s.platform_smtp_use_tls,
        verify_ssl=s.http_verify_ssl,
        from_email=s.platform_email_from.strip(),
        from_name=s.platform_email_from_name.strip() or BRAND_NAME,
        to_email=to_email,
        subject=subject,
        body=body,
    )


def send_firm_invite_smtp(
    *,
    to_email: str,
    subject: str,
    body: str,
    from_display: str | None,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    if not firm_invite_smtp_configured(s):
        raise RuntimeError(
            "Firm invite SMTP is not configured. Connect Gmail under Email sync or set FIRM_INVITE_SMTP_HOST."
        )
    from_name = (from_display or "").strip() or s.firm_invite_email_from_name.strip() or BRAND_NAME
    _send_smtp(
        host=s.firm_invite_smtp_host.strip(),
        port=s.firm_invite_smtp_port,
        user=s.firm_invite_smtp_user.strip(),
        password=s.firm_invite_smtp_password,
        use_tls=s.firm_invite_smtp_use_tls,
        verify_ssl=s.firm_invite_smtp_verify_ssl,
        from_email=s.firm_invite_email_from.strip(),
        from_name=from_name,
        to_email=to_email,
        subject=subject,
        body=body,
    )


def _smtp_ssl_context(*, verify_ssl: bool) -> ssl.SSLContext:
    if verify_ssl:
        return ssl.create_default_context()
    log.warning("SMTP TLS certificate verification is disabled")
    return http_ssl_context()


def _send_smtp(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool,
    verify_ssl: bool = True,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = str(Header(subject, "utf-8"))
    msg["From"] = formataddr((from_name, from_email))
    msg["To"] = to_email

    raw = msg.as_bytes(policy=policy.SMTP)
    log.info("Sending SMTP mail to %s via %s:%s", to_email, host, port)
    if use_tls:
        context = _smtp_ssl_context(verify_ssl=verify_ssl)
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.sendmail(from_email, [to_email], raw)
    else:
        with smtplib.SMTP(host, port, timeout=60) as smtp:
            if user:
                smtp.login(user, password)
            smtp.sendmail(from_email, [to_email], raw)
