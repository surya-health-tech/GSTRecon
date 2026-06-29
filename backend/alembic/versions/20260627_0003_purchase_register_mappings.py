"""purchase register mappings

Revision ID: 0003
Revises: 0002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "purchase_register_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("mapping_name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("stored_file_path", sa.String(length=1024), nullable=True),
        sa.Column("excel_columns", JSONB(), nullable=False),
        sa.Column("sample_row", JSONB(), nullable=False),
        sa.Column("column_mappings", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "mapping_name", name="uq_pr_mapping_tenant_name"),
    )
    op.create_index(
        "ix_purchase_register_mappings_tenant_id",
        "purchase_register_mappings",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_register_mappings_tenant_id", table_name="purchase_register_mappings")
    op.drop_table("purchase_register_mappings")
