from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PurchaseRegisterMapping(Base):
    __tablename__ = "purchase_register_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mapping_name", name="uq_pr_mapping_tenant_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mapping_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    stored_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    excel_columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sample_row: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    column_mappings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
