"""Purchase register column mapping CRUD and validation."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import PurchaseRegisterMapping, ReconciliationMasterField
from app.services.column_auto_match import auto_match_columns
from app.services.master_fields import ensure_default_master_fields
from app.services.purchase_register_excel import parse_excel_workbook

REGISTER_SOURCES = frozenset({"zoho", "wings_erp", "erpnext", "other"})


def get_purchase_register_mapping(
    db: Session, tenant_id: int, mapping_id: int
) -> PurchaseRegisterMapping:
    row = (
        db.query(PurchaseRegisterMapping)
        .filter(
            PurchaseRegisterMapping.tenant_id == tenant_id,
            PurchaseRegisterMapping.id == mapping_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    return row


def list_master_fields_for_register(db: Session, tenant_id: int) -> list[ReconciliationMasterField]:
    ensure_default_master_fields(db, tenant_id)
    return (
        db.query(ReconciliationMasterField)
        .filter(
            ReconciliationMasterField.tenant_id == tenant_id,
            ReconciliationMasterField.is_active.is_(True),
            ReconciliationMasterField.applicable_source.in_(("purchase_register", "both")),
        )
        .order_by(
            ReconciliationMasterField.display_order.asc(),
            ReconciliationMasterField.field_name.asc(),
        )
        .all()
    )


def _duplicate_name(db: Session, tenant_id: int, name: str, exclude_id: int | None = None) -> bool:
    q = db.query(PurchaseRegisterMapping).filter(
        PurchaseRegisterMapping.tenant_id == tenant_id,
        PurchaseRegisterMapping.mapping_name.ilike(name.strip()),
    )
    if exclude_id is not None:
        q = q.filter(PurchaseRegisterMapping.id != exclude_id)
    return q.first() is not None


def validate_source(source: str) -> str:
    value = source.strip().lower()
    if value not in REGISTER_SOURCES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid purchase register source")
    return value


def validate_mapping_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mapping name is required")
    if len(cleaned) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mapping name is too long")
    return cleaned


def parse_column_mappings_json(raw: str) -> dict[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column mappings must be valid JSON",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Column mappings must be a JSON object",
        )
    result: dict[str, str] = {}
    for key, val in data.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if not isinstance(val, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each column mapping value must be a string",
            )
        result[str(key)] = val.strip()
    return result


def validate_column_mappings(
    db: Session,
    tenant_id: int,
    column_mappings: dict[str, str],
    excel_columns: list[str],
) -> None:
    master_fields = list_master_fields_for_register(db, tenant_id)
    required_codes = {f.field_code for f in master_fields if f.is_required}
    allowed_codes = {f.field_code for f in master_fields}
    column_set = set(excel_columns)

    unknown = set(column_mappings.keys()) - allowed_codes
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown master field codes in mapping: {', '.join(sorted(unknown))}",
        )

    missing_required = sorted(required_codes - set(column_mappings.keys()))
    if missing_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required master fields must be mapped: {', '.join(missing_required)}",
        )

    invalid_columns = sorted({col for col in column_mappings.values() if col not in column_set})
    if invalid_columns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Mapped columns not found in uploaded sheet: {', '.join(invalid_columns)}",
        )

    seen: dict[str, str] = {}
    for field_code, col in column_mappings.items():
        if col in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Column '{col}' cannot be mapped to multiple master fields "
                f"({seen[col]} and {field_code})",
            )
        seen[col] = field_code


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip()
    return cleaned or "upload.xlsx"


def _mapping_storage_dir(tenant_id: int, mapping_id: int) -> Path:
    settings = get_settings()
    return Path(settings.file_storage_dir) / str(tenant_id) / "purchase-register" / str(mapping_id)


def save_mapping_file(tenant_id: int, mapping_id: int, filename: str, content: bytes) -> str:
    dest_dir = _mapping_storage_dir(tenant_id, mapping_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    dest_path = dest_dir / safe_name
    dest_path.write_bytes(content)
    return str(dest_path.relative_to(get_settings().file_storage_dir))


def delete_mapping_storage(tenant_id: int, mapping_id: int) -> None:
    dest_dir = _mapping_storage_dir(tenant_id, mapping_id)
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)


async def read_upload_file(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel file is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    return file.filename, content


def build_parse_result(
    db: Session,
    tenant_id: int,
    content: bytes,
    filename: str,
    sheet_name: str | None,
) -> dict:
    sheets, selected_sheet, columns, sample_row = parse_excel_workbook(content, filename, sheet_name)
    master_fields = list_master_fields_for_register(db, tenant_id)
    field_codes = [f.field_code for f in master_fields]
    suggested, confidence = auto_match_columns(field_codes, columns)
    return {
        "sheets": sheets,
        "sheet_name": selected_sheet,
        "columns": columns,
        "sample_row": sample_row,
        "master_fields": master_fields,
        "suggested_mappings": suggested,
        "auto_match_confidence": confidence,
    }
