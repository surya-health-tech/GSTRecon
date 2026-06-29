from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    plan_key: Mapped[str] = mapped_column(String(32), default="starter", nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_clients: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, default=10240, nullable=False)
    max_email_accounts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["TenantMembership"]] = relationship(
        "TenantMembership", back_populates="tenant"
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        "Invitation", back_populates="tenant"
    )
