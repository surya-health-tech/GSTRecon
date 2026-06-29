"""Firm login: email or phone (password; OTP reserved for future)."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import Tenant, TenantMembership, User
from app.services.firm_users import LOGIN_METHOD_EMAIL, LOGIN_METHOD_PHONE_PASSWORD, PHONE_LOGIN_METHODS
from app.services.phone import phone_login_digits


def _normalize_login_id(raw: str) -> tuple[str, str]:
    s = raw.strip()
    if "@" in s:
        email = s.lower()
        if email.startswith("@") or email.endswith("@"):
            raise ValueError("Invalid email")
        return email, "email"
    digits = re.sub(r"\D", "", s)
    digits = digits.lstrip("0") or digits
    if len(digits) < 6:
        raise ValueError("Enter a valid phone number or email address")
    return digits, "phone"


def resolve_firm_login_user(
    db: Session,
    *,
    login_id: str,
    tenant_slug: str | None = None,
) -> User | None:
    """Find user for firm login. Phone logins may require tenant_slug when ambiguous."""
    try:
        normalized, kind = _normalize_login_id(login_id)
    except ValueError:
        return None

    if kind == "email":
        user = db.query(User).filter(User.email == normalized).first()
        if user is None:
            return None
        if user.is_platform_super_admin:
            return user
        if user.login_method != LOGIN_METHOD_EMAIL:
            return None
        return user

    q = db.query(User).filter(
        User.phone_login_digits == normalized,
        User.login_method.in_(PHONE_LOGIN_METHODS),
        User.is_active.is_(True),
    )
    candidates = q.all()
    if not candidates:
        return None
    if len(candidates) == 1 and not tenant_slug:
        return candidates[0]

    slug = (tenant_slug or "").strip().lower()
    if not slug:
        if len(candidates) > 1:
            return None
        return candidates[0]

    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if tenant is None:
        return None

    for user in candidates:
        m = (
            db.query(TenantMembership)
            .filter(
                TenantMembership.user_id == user.id,
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.is_active.is_(True),
            )
            .first()
        )
        if m is not None:
            return user
    return None


def membership_for_firm_login(
    db: Session, user: User, *, tenant_slug: str | None = None
) -> tuple[Tenant, TenantMembership] | None:
    """Pick tenant membership after successful password check."""
    q = (
        db.query(Tenant, TenantMembership)
        .join(TenantMembership, TenantMembership.tenant_id == Tenant.id)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.is_active.is_(True),
            Tenant.status.in_(("active", "trial")),
        )
    )
    slug = (tenant_slug or "").strip().lower()
    if slug:
        q = q.filter(Tenant.slug == slug)
    row = q.order_by(TenantMembership.id.asc()).first()
    if row is None:
        return None
    return row
