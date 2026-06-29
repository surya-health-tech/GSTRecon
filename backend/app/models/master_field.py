from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReconciliationMasterField(Base):
    __tablename__ = "reconciliation_master_fields"
    __table_args__ = (
        UniqueConstraint("tenant_id", "field_name", name="uq_master_field_tenant_name"),
        UniqueConstraint("tenant_id", "field_code", name="uq_master_field_tenant_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_code: Mapped[str] = mapped_column(String(80), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    applicable_source: Mapped[str] = mapped_column(String(32), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
