"""Platform console outbound email OAuth (Gmail / Microsoft 365 for tenant invites)."""

from __future__ import annotations

import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_platform_super_admin_console
from app.core.config import get_settings
from app.core.security import create_access_token, safe_decode_token
from app.models import User
from app.services.platform_email import (
    clear_platform_email_connection,
    complete_platform_email_oauth,
    platform_email_status,
    platform_gmail_oauth_scope,
    platform_microsoft_oauth_scope,
    platform_oauth_configured,
)

router = APIRouter()
settings = get_settings()
log = logging.getLogger(__name__)

def _provider_health(fields: dict[str, str]) -> dict[str, object]:
    missing = [k for k, v in fields.items() if not v]
    return {"configured": len(missing) == 0, "missing_fields": missing}


class PlatformEmailStatusResponse(BaseModel):
    configured: bool
    delivery: str | None = None
    provider: str | None = None
    from_address: str | None = None
    from_name: str | None = None
    oauth_available: bool = False


class PlatformEmailOAuthStartOut(BaseModel):
    auth_url: str


class PlatformEmailOAuthHealthOut(BaseModel):
    google: dict[str, object]
    microsoft365: dict[str, object]


@router.get("/email-status", response_model=PlatformEmailStatusResponse)
def get_platform_email_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> PlatformEmailStatusResponse:
    st = platform_email_status(db)
    return PlatformEmailStatusResponse(
        configured=bool(st["configured"]),
        delivery=st.get("delivery"),
        provider=st.get("provider"),
        from_address=st.get("from_address"),
        from_name=st.get("from_name"),
        oauth_available=platform_oauth_configured(),
    )


@router.get("/email/oauth/health", response_model=PlatformEmailOAuthHealthOut)
def platform_email_oauth_health(
    _: User = Depends(require_platform_super_admin_console),
) -> PlatformEmailOAuthHealthOut:
    g = _provider_health(
        {
            "google_oauth_client_id": settings.google_oauth_client_id,
            "google_oauth_client_secret": settings.google_oauth_client_secret,
            "google_oauth_redirect_uri": settings.google_oauth_redirect_uri,
        }
    )
    m = _provider_health(
        {
            "microsoft_oauth_client_id": settings.microsoft_oauth_client_id,
            "microsoft_oauth_client_secret": settings.microsoft_oauth_client_secret,
            "microsoft_oauth_tenant_id": settings.microsoft_oauth_tenant_id,
            "microsoft_oauth_redirect_uri": settings.microsoft_oauth_redirect_uri,
        }
    )
    return PlatformEmailOAuthHealthOut(google=g, microsoft365=m)  # type: ignore[arg-type]


@router.get("/email/oauth/start", response_model=PlatformEmailOAuthStartOut)
def platform_email_oauth_start(
    provider: str = Query(..., pattern=r"^(gmail|microsoft365)$"),
    user: User = Depends(require_platform_super_admin_console),
) -> PlatformEmailOAuthStartOut:
    if provider == "gmail":
        missing = _provider_health(
            {
                "google_oauth_client_id": settings.google_oauth_client_id,
                "google_oauth_client_secret": settings.google_oauth_client_secret,
                "google_oauth_redirect_uri": settings.google_oauth_redirect_uri,
            }
        )["missing_fields"]
        redirect_uri = settings.google_oauth_redirect_uri
    else:
        missing = _provider_health(
            {
                "microsoft_oauth_client_id": settings.microsoft_oauth_client_id,
                "microsoft_oauth_client_secret": settings.microsoft_oauth_client_secret,
                "microsoft_oauth_tenant_id": settings.microsoft_oauth_tenant_id,
                "microsoft_oauth_redirect_uri": settings.microsoft_oauth_redirect_uri,
            }
        )["missing_fields"]
        redirect_uri = settings.microsoft_oauth_redirect_uri
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider '{provider}' is not configured: {', '.join(missing)}",
        )

    state = create_access_token(
        str(user.id),
        extra_claims={"purpose": "platform_email_oauth", "provider": provider},
    )
    if provider == "gmail":
        params = {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": platform_gmail_oauth_scope(),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    else:
        params = {
            "client_id": settings.microsoft_oauth_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": platform_microsoft_oauth_scope(),
            "prompt": "consent",
            "state": state,
        }
        auth_url = (
            f"https://login.microsoftonline.com/{settings.microsoft_oauth_tenant_id}/oauth2/v2.0/authorize?"
            + urllib.parse.urlencode(params)
        )
    return PlatformEmailOAuthStartOut(auth_url=auth_url)


@router.delete("/email/oauth", status_code=status.HTTP_200_OK)
def disconnect_platform_email(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> dict[str, str]:
    clear_platform_email_connection(db)
    return {"status": "disconnected"}


@router.get("/email/oauth/callback")
def platform_email_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    front_base = f"{settings.frontend_app_url.rstrip('/')}/platform"
    if error:
        return RedirectResponse(url=f"{front_base}?oauth=error&message={urllib.parse.quote(error)}")
    if not code or not state:
        return RedirectResponse(url=f"{front_base}?oauth=error&message=missing_code_or_state")

    payload = safe_decode_token(state)
    if payload is None or payload.get("purpose") != "platform_email_oauth":
        return RedirectResponse(url=f"{front_base}?oauth=error&message=invalid_state")

    provider = payload.get("provider")
    if provider not in ("gmail", "microsoft365"):
        return RedirectResponse(url=f"{front_base}?oauth=error&message=invalid_state_payload")

    try:
        complete_platform_email_oauth(db, provider=provider, code=code)
    except Exception as exc:
        log.warning("Platform email OAuth failed (%s): %s", provider, exc, exc_info=True)
        return RedirectResponse(
            url=f"{front_base}?oauth=error&message={urllib.parse.quote(str(exc))}"
        )
    return RedirectResponse(url=f"{front_base}?oauth=success&provider={provider}")
