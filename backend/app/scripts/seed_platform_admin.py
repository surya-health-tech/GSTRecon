"""Create the initial platform super admin user (idempotent)."""

import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


def _resolve_platform_admin(db, target_email: str) -> User | None:
    """Pick one user to be platform admin; avoid duplicate-email updates."""
    by_email = db.scalar(select(User).where(User.email == target_email))
    by_flag = db.scalar(select(User).where(User.is_platform_super_admin.is_(True)))

    if by_email and by_flag and by_email.id != by_flag.id:
        by_flag.is_platform_super_admin = False
        return by_email
    return by_email or by_flag


def main() -> None:
    from app.core.config import get_settings

    cfg = get_settings()
    email = os.environ.get("PLATFORM_ADMIN_EMAIL", cfg.platform_admin_email).strip().lower()
    password = os.environ.get("PLATFORM_ADMIN_PASSWORD", cfg.platform_admin_password)
    name = os.environ.get("PLATFORM_ADMIN_NAME", cfg.platform_admin_name)

    db = SessionLocal()
    try:
        admin = _resolve_platform_admin(db, email)
        if admin is None:
            admin = User(
                email=email,
                full_name=name,
                hashed_password=hash_password(password),
                is_active=True,
                is_platform_super_admin=True,
            )
            db.add(admin)
            db.commit()
            print(f"Created platform admin {email}")
            return

        if admin.email != email:
            conflict = db.scalar(select(User).where(User.email == email))
            if conflict is not None and conflict.id != admin.id:
                admin.is_platform_super_admin = False
                admin = conflict
            else:
                admin.email = email

        admin.full_name = name
        admin.is_platform_super_admin = True
        admin.is_active = True
        admin.hashed_password = hash_password(password)
        db.commit()
        print(f"Platform admin ready: {admin.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
