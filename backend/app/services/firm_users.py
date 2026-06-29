"""Create and update firm team members (email invite or phone password login)."""

from __future__ import annotations

import logging
import secrets
import string
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Tenant, TenantMembership, User
from app.schemas.tenant import InvitationCreate, InvitationCreatedResponse
from app.schemas.users import (
    CreateFirmUserRequest,
    CreateFirmUserResponse,
    FirmUserOut,
    UpdateFirmUserRequest,
)
from app.services.invitations import active_firm_member_exists, create_invitation
from app.services.phone import (
    DEFAULT_FIRM_COUNTRY_CODE,
    is_valid_phone_pair,
    merge_phone_fields,
    phone_login_digits,
)
from app.services.phone_user_emails import send_phone_account_created_to_tenant_admins
from app.services.team import FIRM_ROLES, count_active_admins

log = logging.getLogger(__name__)

LOGIN_METHOD_EMAIL = "email"
LOGIN_METHOD_PHONE_PASSWORD = "phone_password"
# Reserved for future SMS OTP login (not implemented).
LOGIN_METHOD_PHONE_OTP = "phone_otp"

PHONE_LOGIN_METHODS = (LOGIN_METHOD_PHONE_PASSWORD, LOGIN_METHOD_PHONE_OTP)


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def generate_temporary_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def firm_user_out(m: TenantMembership, u: User, db: Session | None = None) -> FirmUserOut:
    _ = db
    return FirmUserOut(
        user_id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=m.role,
        membership_active=m.is_active,
        login_method=u.login_method,
        phone=u.phone,
        phone_country_code=u.phone_country_code,
    )


def active_phone_member_exists(
    db: Session,
    tenant_id: int,
    phone_digits: str,
    *,
    exclude_user_id: int | None = None,
) -> bool:
    q = (
        db.query(TenantMembership.id)
        .join(User, User.id == TenantMembership.user_id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.is_active.is_(True),
            User.is_active.is_(True),
            User.phone_login_digits == phone_digits,
            User.login_method.in_(PHONE_LOGIN_METHODS),
        )
    )
    if exclude_user_id is not None:
        q = q.filter(User.id != exclude_user_id)
    return q.first() is not None


def _assert_phone_unique_in_tenant(
    db: Session, tenant_id: int, digits: str, *, exclude_user_id: int | None = None
) -> None:
    if active_phone_member_exists(db, tenant_id, digits, exclude_user_id=exclude_user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another active team member already uses this phone number in your firm.",
        )


def _apply_phone_fields(u: User, *, country_code: str | None, phone: str | None) -> None:
    cc, loc = merge_phone_fields(phone_country_code=country_code, phone=phone)
    if not is_valid_phone_pair(cc, loc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid phone number and country code.",
        )
    digits = phone_login_digits(cc, loc)
    if not digits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid phone number.",
        )
    u.phone_country_code = cc
    u.phone = loc
    u.phone_login_digits = digits


def create_firm_user(
    db: Session,
    *,
    tenant_id: int,
    body: CreateFirmUserRequest,
    actor_user_id: int,
) -> CreateFirmUserResponse:
    """Create member via email invitation or phone password account."""
    if body.role not in FIRM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    if body.login_method == LOGIN_METHOD_EMAIL:
        if not body.email or not body.email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required when login method is Email.",
            )
        inv = InvitationCreate(
            email=body.email.strip().lower(),
            full_name=body.full_name.strip(),
            role=body.role,
        )
        inv_resp = create_invitation(db, tenant_id, inv)
        return CreateFirmUserResponse(mode="invitation", invitation=inv_resp)

    if body.login_method != LOGIN_METHOD_PHONE_PASSWORD:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid login method")

    if not body.phone or not body.phone.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required when login method is Phone Number.",
        )
    cc = body.phone_country_code or DEFAULT_FIRM_COUNTRY_CODE
    cc_norm, loc = merge_phone_fields(phone_country_code=cc, phone=body.phone)
    if not is_valid_phone_pair(cc_norm, loc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid phone number and country code.",
        )
    digits = phone_login_digits(cc_norm, loc)
    assert digits
    _assert_phone_unique_in_tenant(db, tenant_id, digits)

    email_norm = body.email.strip().lower() if body.email and body.email.strip() else None
    if email_norm and active_firm_member_exists(db, tenant_id, email_norm):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already on your team.",
        )
    if email_norm:
        existing = db.query(User).filter(User.email == email_norm).first()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already registered. Use a different email or leave it blank.",
            )

    temp_password = generate_temporary_password()
    user = User(
        email=email_norm,
        full_name=body.full_name.strip(),
        hashed_password=hash_password(temp_password),
        is_active=True,
        is_platform_super_admin=False,
        login_method=LOGIN_METHOD_PHONE_PASSWORD,
        must_change_password=True,
        phone_country_code=cc_norm,
        phone=loc,
        phone_login_digits=digits,
    )
    db.add(user)
    db.flush()
    db.add(
        TenantMembership(
            user_id=user.id,
            tenant_id=tenant_id,
            role=body.role,
            is_active=True,
        )
    )
    db.flush()

    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else "your firm"
    first, last = _split_name(user.full_name)
    admin_password = temp_password
    del temp_password

    db.commit()
    db.refresh(user)

    try:
        email_sent, email_error = send_phone_account_created_to_tenant_admins(
            db,
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            user_first_name=first,
            user_last_name=last,
            user_full_name=user.full_name,
            phone_country_code=cc_norm or "",
            phone_local=loc or "",
            phone_login_digits=digits,
            temporary_password=admin_password,
        )
    except Exception:
        log.exception(
            "Phone account created (user_id=%s) but admin notification email failed",
            user.id,
        )
        email_sent, email_error = False, "Admin notification email could not be sent."
    finally:
        del admin_password
    m = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    assert m is not None
    log.info(
        "Phone-login firm user created tenant_id=%s user_id=%s actor_user_id=%s",
        tenant_id,
        user.id,
        actor_user_id,
    )
    return CreateFirmUserResponse(
        mode="user",
        user=firm_user_out(m, user, db),
        phone_account_email_sent=email_sent,
        phone_account_email_error=email_error,
    )


def update_firm_user(
    db: Session,
    *,
    tenant_id: int,
    user_id: int,
    body: UpdateFirmUserRequest,
    actor_user_id: int,
) -> FirmUserOut:
    row = (
        db.query(TenantMembership, User)
        .join(User, User.id == TenantMembership.user_id)
        .filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not in this firm")
    membership, user = row

    if body.login_method == LOGIN_METHOD_PHONE_OTP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMS OTP login is not available yet.",
        )

    if body.full_name is not None and body.full_name.strip():
        user.full_name = body.full_name.strip()

    if body.role is not None:
        if body.role not in FIRM_ROLES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
        if membership.role == "tenant_admin" and body.role != "tenant_admin":
            if count_active_admins(db, tenant_id, exclude_user_id=user_id) < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change the role of the last firm administrator.",
                )
        membership.role = body.role

    old_method = user.login_method
    target_method = body.login_method if body.login_method is not None else old_method
    notify_phone_admin = False
    temp_password: str | None = None

    if target_method == LOGIN_METHOD_EMAIL:
        email_norm = body.email if body.email is not None else user.email
        if not email_norm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required when login method is Email.",
            )
        if active_firm_member_exists(db, tenant_id, email_norm) and user.email != email_norm:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already on your team.",
            )
        user.email = email_norm
        user.login_method = LOGIN_METHOD_EMAIL
        user.phone = None
        user.phone_country_code = None
        user.phone_login_digits = None
    elif target_method in PHONE_LOGIN_METHODS:
        cc_in = (
            body.phone_country_code
            if body.phone_country_code is not None
            else user.phone_country_code or DEFAULT_FIRM_COUNTRY_CODE
        )
        ph_in = body.phone if body.phone is not None else user.phone
        if not ph_in or not str(ph_in).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is required when login method is Phone Number.",
            )
        _apply_phone_fields(user, country_code=cc_in, phone=ph_in)
        _assert_phone_unique_in_tenant(
            db, tenant_id, user.phone_login_digits or "", exclude_user_id=user.id
        )
        if body.email is not None:
            if body.email and active_firm_member_exists(db, tenant_id, body.email) and user.email != body.email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This email is already on your team.",
                )
            user.email = body.email
        if old_method == LOGIN_METHOD_EMAIL or body.login_method == LOGIN_METHOD_PHONE_PASSWORD:
            temp_password = generate_temporary_password()
            user.hashed_password = hash_password(temp_password)
            user.must_change_password = True
            notify_phone_admin = True
        user.login_method = LOGIN_METHOD_PHONE_PASSWORD
    elif body.email is not None:
        if user.login_method == LOGIN_METHOD_EMAIL and not body.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required when login method is Email.",
            )
        if body.email and active_firm_member_exists(db, tenant_id, body.email) and user.email != body.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already on your team.",
            )
        user.email = body.email

    db.commit()
    db.refresh(user)
    db.refresh(membership)

    if notify_phone_admin and temp_password:
        tenant = db.get(Tenant, tenant_id)
        tenant_name = tenant.name if tenant else "your firm"
        first, last = _split_name(user.full_name)
        admin_password = temp_password
        del temp_password
        try:
            send_phone_account_created_to_tenant_admins(
                db,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                user_first_name=first,
                user_last_name=last,
                user_full_name=user.full_name,
                phone_country_code=user.phone_country_code or "",
                phone_local=user.phone or "",
                phone_login_digits=user.phone_login_digits or "",
                temporary_password=admin_password,
            )
        except Exception:
            log.exception(
                "User %s switched to phone login but admin notification email failed",
                user_id,
            )
        finally:
            del admin_password

    log.info("Firm user updated tenant_id=%s user_id=%s actor_user_id=%s", tenant_id, user_id, actor_user_id)
    return firm_user_out(membership, user, db)
