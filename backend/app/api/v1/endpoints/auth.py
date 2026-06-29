import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_access_token_payload, get_current_user, get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    safe_decode_token,
    verify_password,
)
from app.models import Invitation, Tenant, TenantMembership, User
from app.services.firm_auth import membership_for_firm_login, resolve_firm_login_user
from app.services.firm_users import LOGIN_METHOD_EMAIL
from app.services.platform_tenant_access import (
    CLAIM_ACCESS_SESSION_ID,
    CLAIM_PLATFORM_TENANT_ACCESS,
    CLAIM_TENANT_ID,
    get_active_session,
    resolve_access_claims_from_refresh,
    tenant_admin_permissions,
)
from app.services.role_permissions import get_permissions_for_member
from app.schemas.auth import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
)
from app.services import password_reset as password_reset_service
from app.schemas.platform_access import PlatformTenantAccessMe

log = logging.getLogger(__name__)

router = APIRouter()


def _hash_invite_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _firm_access_pair(db: Session, user: User) -> tuple[Tenant, TenantMembership] | None:
    m = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.is_active.is_(True),
        )
        .first()
    )
    if m is None:
        return None
    t = db.get(Tenant, m.tenant_id)
    if t is None or t.status not in ("active", "trial"):
        return None
    return t, m


def _token_claims_for_user(
    db: Session, user: User, *, tenant_slug: str | None = None
) -> dict:
    if user.is_platform_super_admin:
        return {"is_platform_super_admin": True}
    pair = membership_for_firm_login(db, user, tenant_slug=tenant_slug)
    if pair is None:
        return {"is_platform_super_admin": False}
    tenant, membership = pair
    return {
        "is_platform_super_admin": False,
        "tenant_id": tenant.id,
        "role": membership.role,
    }


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = resolve_firm_login_user(
        db, login_id=body.login_id, tenant_slug=body.tenant_slug
    )
    if user is None or not user.hashed_password or not verify_password(
        body.password, user.hashed_password
    ):
        log.info("Login failed for login_id=%s***", body.login_id[:3])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not user.is_platform_super_admin:
        pair = membership_for_firm_login(db, user, tenant_slug=body.tenant_slug)
        if pair is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No active workspace membership for this account.",
            )
    claims = _token_claims_for_user(db, user, tenant_slug=body.tenant_slug)
    access = create_access_token(str(user.id), extra_claims=claims)
    refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    payload = safe_decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    sub = payload.get("sub")
    try:
        user_id = int(sub) if sub is not None else -1
    except (TypeError, ValueError):
        user_id = -1
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    refresh_payload = safe_decode_token(body.refresh_token) or {}
    claims = resolve_access_claims_from_refresh(db, user, refresh_payload)
    access = create_access_token(str(user.id), extra_claims=claims)
    refresh_claims: dict = {}
    if claims.get(CLAIM_ACCESS_SESSION_ID):
        refresh_claims[CLAIM_ACCESS_SESSION_ID] = claims[CLAIM_ACCESS_SESSION_ID]
    new_refresh = create_refresh_token(str(user.id), extra_claims=refresh_claims or None)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.get("/me", response_model=MeResponse)
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_access_token_payload),
) -> MeResponse:
    if user.is_platform_super_admin and payload.get(CLAIM_PLATFORM_TENANT_ACCESS):
        try:
            session_id = int(payload[CLAIM_ACCESS_SESSION_ID])
            tenant_id = int(payload[CLAIM_TENANT_ID])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant portal access session is invalid.",
            )
        session = get_active_session(db, session_id, user.id, tenant_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tenant portal access session expired.",
            )
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant not found")
        perms = tenant_admin_permissions(db, tenant.id)
        return MeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_platform_super_admin=True,
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            role="tenant_admin",
            permissions=perms,
            platform_tenant_access=PlatformTenantAccessMe(
                session_id=session.id,
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                started_at=session.started_at,
                platform_admin_name=user.full_name,
                platform_admin_email=user.email,
            ),
        )

    if user.is_platform_super_admin:
        return MeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_platform_super_admin=True,
        )
    pair = _firm_access_pair(db, user)
    if pair is None:
        return MeResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_platform_super_admin=False,
        )
    tenant, membership = pair
    perms = get_permissions_for_member(db, tenant.id, membership.role)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_platform_super_admin=False,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        role=membership.role,
        permissions=perms,
        login_method=user.login_method,
        phone=user.phone,
        phone_country_code=user.phone_country_code,
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    body: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    password_reset_service.request_firm_password_reset(db, email=body.email)
    return ForgotPasswordResponse(message=password_reset_service.GENERIC_FIRM_MESSAGE)


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    body: ResetPasswordRequest, db: Session = Depends(get_db)
) -> ResetPasswordResponse:
    user = password_reset_service.confirm_firm_password_reset(
        db, raw_token=body.token, new_password=body.password
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one from the sign-in page.",
        )
    return ResetPasswordResponse(message="Your password has been updated. You can sign in now.")


@router.post("/accept-invitation", response_model=AcceptInvitationResponse)
def accept_invitation(
    body: AcceptInvitationRequest, db: Session = Depends(get_db)
) -> AcceptInvitationResponse:
    token_hash = _hash_invite_token(body.token)
    inv = db.query(Invitation).filter(Invitation.token_hash == token_hash).first()
    if inv is None or inv.accepted_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation")
    exp = inv.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitation expired")

    email = inv.email.lower()
    user = db.query(User).filter(User.email == email).first()
    existing_membership = None
    if user is not None:
        existing_membership = (
            db.query(TenantMembership)
            .filter(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == inv.tenant_id,
            )
            .first()
        )

    message = "Invitation accepted"

    if user is None:
        user = User(
            email=email,
            full_name=inv.full_name,
            hashed_password=hash_password(body.password),
            is_active=True,
            is_platform_super_admin=False,
        )
        db.add(user)
        db.flush()
    elif user.hashed_password:
        if existing_membership is not None and existing_membership.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have access to this firm; log in instead",
            )
        # Same email from a prior tenant (e.g. firm deleted and recreated): link to new tenant.
        user.full_name = inv.full_name
        user.is_active = True
        message = "Invitation accepted. Sign in with your existing password."
    else:
        user.full_name = inv.full_name
        user.hashed_password = hash_password(body.password)
        user.is_active = True
        user.login_method = LOGIN_METHOD_EMAIL

    if existing_membership is None:
        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=inv.tenant_id,
                role=inv.role,
                is_active=True,
            )
        )
    else:
        existing_membership.role = inv.role
        existing_membership.is_active = True

    inv.accepted_at = datetime.now(timezone.utc)
    db.commit()

    return AcceptInvitationResponse(message=message, email=user.email)
