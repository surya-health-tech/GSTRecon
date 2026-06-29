"""reconciliation master fields

Revision ID: 0002
Revises: 0001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_master_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_code", sa.String(length=80), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("applicable_source", sa.String(length=32), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "field_name", name="uq_master_field_tenant_name"),
        sa.UniqueConstraint("tenant_id", "field_code", name="uq_master_field_tenant_code"),
    )
    op.create_index(
        "ix_reconciliation_master_fields_tenant_id",
        "reconciliation_master_fields",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reconciliation_master_fields_tenant_id", table_name="reconciliation_master_fields")
    op.drop_table("reconciliation_master_fields")
