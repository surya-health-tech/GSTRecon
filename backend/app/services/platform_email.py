"""Platform-level outbound email (tenant invites) via OAuth or env SMTP fallback."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.brand import BRAND_NAME
from app.core.config import Settings, get_settings
from app.models import PlatformEmailConnection
from app.services.gmail_send import _gmail_api_send_raw, build_plain_reply_mime
from app.services.oauth_http import http_json_get, http_post_form, http_post_json
from app.services.transactional_email import platform_smtp_configured, send_platform_smtp

log = logging.getLogger(__name__)


def get_platform_email_connection(db: Session) -> PlatformEmailConnection | None:
    return db.query(PlatformEmailConnection).order_by(PlatformEmailConnection.id.desc()).first()


def platform_oauth_configured(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    if s.google_oauth_client_id and s.google_oauth_client_secret and s.google_oauth_redirect_uri:
        return True
    if (
        s.microsoft_oauth_client_id
        and s.microsoft_oauth_client_secret
        and s.microsoft_oauth_redirect_uri
    ):
        return True
    return False


def platform_email_configured(db: Session, settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    conn = get_platform_email_connection(db)
    if conn is not None and conn.oauth_refresh_token:
        return True
    return platform_smtp_configured(s)


def platform_email_status(db: Session, settings: Settings | None = None) -> dict:
    s = settings or get_settings()
    conn = get_platform_email_connection(db)
    if conn is not None and conn.oauth_refresh_token:
        return {
            "configured": True,
            "delivery": "oauth",
            "provider": conn.provider,
            "from_address": conn.account_email,
            "from_name": conn.from_display_name or s.platform_email_from_name,
        }
    if platform_smtp_configured(s):
        return {
            "configured": True,
            "delivery": "smtp",
            "provider": "smtp",
            "from_address": s.platform_email_from.strip(),
            "from_name": s.platform_email_from_name.strip() or BRAND_NAME,
        }
    return {
        "configured": False,
        "delivery": None,
        "provider": None,
        "from_address": None,
        "from_name": s.platform_email_from_name.strip() or BRAND_NAME,
    }


def _refresh_gmail(conn: PlatformEmailConnection, settings: Settings) -> None:
    payload = http_post_form(
        "https://oauth2.googleapis.com/token",
        {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "refresh_token": conn.oauth_refresh_token or "",
            "grant_type": "refresh_token",
        },
    )
    _apply_token_payload(conn, payload)


def _refresh_microsoft(conn: PlatformEmailConnection, settings: Settings) -> None:
    payload = http_post_form(
        f"https://login.microsoftonline.com/{settings.microsoft_oauth_tenant_id}/oauth2/v2.0/token",
        {
            "client_id": settings.microsoft_oauth_client_id,
            "client_secret": settings.microsoft_oauth_client_secret,
            "refresh_token": conn.oauth_refresh_token or "",
            "grant_type": "refresh_token",
        },
    )
    _apply_token_payload(conn, payload)


def _apply_token_payload(conn: PlatformEmailConnection, payload: dict) -> None:
    access = payload.get("access_token")
    if not access:
        raise RuntimeError(
            str(payload.get("error_description") or payload.get("error") or "token refresh failed")
        )
    conn.oauth_access_token = str(access).strip()
    expires_in = int(payload.get("expires_in") or 3600)
    conn.oauth_token_expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
        seconds=max(120, expires_in - 60)
    )
    new_rt = payload.get("refresh_token")
    if isinstance(new_rt, str) and new_rt.strip():
        conn.oauth_refresh_token = new_rt.strip()


def _ensure_fresh_token(db: Session, conn: PlatformEmailConnection, settings: Settings) -> None:
    expired = (
        conn.oauth_token_expires_at is None
        or conn.oauth_token_expires_at <= datetime.now(timezone.utc)
    )
    missing = not (conn.oauth_access_token or "").strip()
    if not conn.oauth_refresh_token:
        raise RuntimeError("Platform email OAuth has no refresh token. Connect again.")
    if missing or expired:
        if conn.provider == "gmail":
            _refresh_gmail(conn, settings)
        elif conn.provider == "microsoft365":
            _refresh_microsoft(conn, settings)
        else:
            raise RuntimeError(f"Unsupported platform email provider: {conn.provider}")
        db.commit()


def _send_gmail(conn: PlatformEmailConnection, *, to_email: str, subject: str, body: str, settings: Settings) -> None:
    from_name = conn.from_display_name.strip() or settings.platform_email_from_name.strip() or BRAND_NAME
    raw = build_plain_reply_mime(
        from_email=conn.account_email,
        from_display=from_name,
        to_email=to_email,
        subject=subject,
        body=body,
        in_reply_to=None,
    )
    _gmail_api_send_raw(conn.oauth_access_token or "", raw)


def _send_microsoft_graph(
    conn: PlatformEmailConnection, *, to_email: str, subject: str, body: str
) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": True,
    }
    http_post_json(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        payload,
        bearer_token=conn.oauth_access_token or "",
    )


def send_platform_email(
    db: Session,
    *,
    to_email: str,
    subject: str,
    body: str,
    settings: Settings | None = None,
) -> None:
    s = settings or get_settings()
    conn = get_platform_email_connection(db)
    if conn is not None and conn.oauth_refresh_token:
        _ensure_fresh_token(db, conn, s)
        if conn.provider == "gmail":
            _send_gmail(conn, to_email=to_email, subject=subject, body=body, settings=s)
            log.info("Platform email sent via Gmail OAuth to %s", to_email)
            return
        if conn.provider == "microsoft365":
            _send_microsoft_graph(conn, to_email=to_email, subject=subject, body=body)
            log.info("Platform email sent via Microsoft 365 OAuth to %s", to_email)
            return
    if platform_smtp_configured(s):
        send_platform_smtp(to_email=to_email, subject=subject, body=body, settings=s)
        log.info("Platform email sent via SMTP to %s", to_email)
        return
    raise RuntimeError(
        "Platform email is not configured. Connect Gmail or Microsoft 365 under Platform console, "
        "or set PLATFORM_SMTP_HOST and PLATFORM_EMAIL_FROM."
    )


def save_platform_oauth_connection(
    db: Session,
    *,
    provider: str,
    account_email: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
    from_display_name: str | None = None,
) -> PlatformEmailConnection:
    settings = get_settings()
    row = get_platform_email_connection(db)
    if row is None:
        row = PlatformEmailConnection(
            provider=provider,
            account_email=account_email.strip().lower(),
            from_display_name=from_display_name or settings.platform_email_from_name or BRAND_NAME,
        )
        db.add(row)
    else:
        row.provider = provider
        row.account_email = account_email.strip().lower()
        if from_display_name:
            row.from_display_name = from_display_name
    row.oauth_access_token = access_token.strip()
    if refresh_token:
        row.oauth_refresh_token = refresh_token.strip()
    if expires_in is not None:
        row.oauth_token_expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(
            seconds=max(120, int(expires_in) - 60)
        )
    row.from_display_name = row.from_display_name or settings.platform_email_from_name or BRAND_NAME
    db.commit()
    db.refresh(row)
    return row


def clear_platform_email_connection(db: Session) -> None:
    row = get_platform_email_connection(db)
    if row is not None:
        db.delete(row)
        db.commit()


def platform_gmail_oauth_scope() -> str:
    return (
        "openid email offline_access "
        "https://www.googleapis.com/auth/gmail.send "
        "https://www.googleapis.com/auth/userinfo.email"
    )


def platform_microsoft_oauth_scope() -> str:
    return "openid offline_access email https://graph.microsoft.com/Mail.Send"


def resolve_platform_account_email_gmail(token_data: dict) -> str:
    access = token_data.get("access_token")
    if access:
        profile = http_json_get(
            "https://www.googleapis.com/oauth2/v2/userinfo", bearer_token=str(access)
        )
        email = profile.get("email")
        if isinstance(email, str) and email.strip():
            return email.strip().lower()
    raise RuntimeError("Could not read Gmail address after sign-in.")


def resolve_platform_account_email_microsoft(token_data: dict) -> str:
    access = token_data.get("access_token")
    if access:
        profile = http_json_get("https://graph.microsoft.com/v1.0/me", bearer_token=str(access))
        mail = profile.get("mail") or profile.get("userPrincipalName")
        if isinstance(mail, str) and "@" in mail:
            return mail.strip().lower()
    raise RuntimeError("Could not read Microsoft 365 mailbox address after sign-in.")


def complete_platform_email_oauth(db: Session, *, provider: str, code: str) -> None:
    """Exchange authorization code and persist platform mail OAuth (shared redirect URI with email sync)."""
    s = get_settings()
    if provider == "gmail":
        token_data = http_post_form(
            "https://oauth2.googleapis.com/token",
            {
                "code": code,
                "client_id": s.google_oauth_client_id,
                "client_secret": s.google_oauth_client_secret,
                "redirect_uri": s.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        account_email = resolve_platform_account_email_gmail(token_data)
    elif provider == "microsoft365":
        token_data = http_post_form(
            f"https://login.microsoftonline.com/{s.microsoft_oauth_tenant_id}/oauth2/v2.0/token",
            {
                "code": code,
                "client_id": s.microsoft_oauth_client_id,
                "client_secret": s.microsoft_oauth_client_secret,
                "redirect_uri": s.microsoft_oauth_redirect_uri,
                "grant_type": "authorization_code",
                "scope": platform_microsoft_oauth_scope(),
            },
        )
        account_email = resolve_platform_account_email_microsoft(token_data)
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    if not access_token:
        raise RuntimeError("Sign-in did not return an access token. Try Connect again.")
    if not refresh_token:
        raise RuntimeError(
            "No refresh token returned. Revoke this app under your account security settings "
            "and connect again with consent."
        )
    expires_in = token_data.get("expires_in")
    try:
        exp = int(expires_in) if expires_in is not None else None
    except (TypeError, ValueError):
        exp = None
    save_platform_oauth_connection(
        db,
        provider=provider,
        account_email=account_email,
        access_token=str(access_token),
        refresh_token=str(refresh_token),
        expires_in=exp,
    )
