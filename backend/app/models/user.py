from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Local number digits for sign-in without country code (unique per firm in app logic).
    phone_login_digits: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    # email | phone_password | phone_otp (TODO: SMS OTP — switch login without schema change)
    login_method: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(
        "TenantMembership", back_populates="user", foreign_keys="TenantMembership.user_id"
    )
