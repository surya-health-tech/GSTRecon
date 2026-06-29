"""Tenant-scoped GSTR-2B reconciliation master field definitions."""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import ReconciliationMasterField

DATA_TYPES = frozenset({"text", "decimal", "date", "number", "boolean"})
APPLICABLE_SOURCES = frozenset({"gstr_2b", "purchase_register", "both"})

DEFAULT_MASTER_FIELDS: tuple[dict, ...] = (
    {
        "field_name": "Voucher Number",
        "field_code": "voucher_number",
        "data_type": "text",
        "is_required": True,
        "applicable_source": "purchase_register",
        "display_order": 1,
    },
    {
        "field_name": "Company GSTIN",
        "field_code": "company_gstin",
        "data_type": "text",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 2,
    },
    {
        "field_name": "Supplier Name",
        "field_code": "supplier_name",
        "data_type": "text",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 3,
    },
    {
        "field_name": "Supplier GSTIN",
        "field_code": "supplier_gstin",
        "data_type": "text",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 4,
    },
    {
        "field_name": "Supplier Invoice No",
        "field_code": "supplier_invoice_no",
        "data_type": "text",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 5,
    },
    {
        "field_name": "Supplier Invoice Date",
        "field_code": "supplier_invoice_date",
        "data_type": "date",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 6,
    },
    {
        "field_name": "Taxable Amount",
        "field_code": "taxable_amount",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 7,
    },
    {
        "field_name": "IGST",
        "field_code": "igst",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 8,
    },
    {
        "field_name": "SGST",
        "field_code": "sgst",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 9,
    },
    {
        "field_name": "CGST",
        "field_code": "cgst",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 10,
    },
    {
        "field_name": "Total Tax",
        "field_code": "total_tax",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 11,
    },
    {
        "field_name": "Grand Total",
        "field_code": "grand_total",
        "data_type": "decimal",
        "is_required": True,
        "applicable_source": "both",
        "display_order": 12,
    },
)


def field_name_to_code(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    return slug.strip("_") or "field"


def ensure_default_master_fields(db: Session, tenant_id: int) -> None:
    existing_codes = {
        row[0]
        for row in db.query(ReconciliationMasterField.field_code)
        .filter(ReconciliationMasterField.tenant_id == tenant_id)
        .all()
    }
    for spec in DEFAULT_MASTER_FIELDS:
        if spec["field_code"] in existing_codes:
            continue
        db.add(
            ReconciliationMasterField(
                tenant_id=tenant_id,
                is_system=True,
                is_active=True,
                **spec,
            )
        )


def _duplicate_name(
    db: Session, tenant_id: int, field_name: str, *, exclude_id: int | None = None
) -> bool:
    q = db.query(ReconciliationMasterField.id).filter(
        ReconciliationMasterField.tenant_id == tenant_id,
        ReconciliationMasterField.field_name == field_name.strip(),
    )
    if exclude_id is not None:
        q = q.filter(ReconciliationMasterField.id != exclude_id)
    return q.first() is not None


def _duplicate_code(
    db: Session, tenant_id: int, field_code: str, *, exclude_id: int | None = None
) -> bool:
    q = db.query(ReconciliationMasterField.id).filter(
        ReconciliationMasterField.tenant_id == tenant_id,
        ReconciliationMasterField.field_code == field_code.strip().lower(),
    )
    if exclude_id is not None:
        q = q.filter(ReconciliationMasterField.id != exclude_id)
    return q.first() is not None


def get_master_field(db: Session, tenant_id: int, field_id: int) -> ReconciliationMasterField:
    row = (
        db.query(ReconciliationMasterField)
        .filter(
            ReconciliationMasterField.tenant_id == tenant_id,
            ReconciliationMasterField.id == field_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master field not found")
    return row


def validate_field_payload(
    *,
    field_name: str | None = None,
    field_code: str | None = None,
    data_type: str | None = None,
    applicable_source: str | None = None,
    display_order: int | None = None,
) -> None:
    if field_name is not None and not field_name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field name is required")
    if field_code is not None:
        code = field_code.strip().lower()
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Field code is required")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field code must be snake_case (lowercase letters, numbers, underscores)",
            )
    if data_type is not None and data_type not in DATA_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data type")
    if applicable_source is not None and applicable_source not in APPLICABLE_SOURCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid applicable source")
    if display_order is not None and display_order < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display order must be zero or greater",
        )
