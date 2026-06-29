"""GSTR-2B column mapping CRUD, validation, and version activation."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Gstr2bMapping, ReconciliationMasterField
from app.services.gstr2b_auto_match import auto_match_gstr2b_columns
from app.services.gstr2b_excel import (
    CDNR_TABS,
    SUPPORTED_GSTR2B_TABS,
    list_workbook_sheets,
    map_workbook_sheets,
    parse_sheet_data,
)
from app.services.master_fields import ensure_default_master_fields

OPTIONAL_FIELD_CODES = frozenset({"company_gstin", "total_tax"})
DERIVED_TOTAL_TAX_SOURCES = frozenset({"igst", "cgst", "sgst"})
NA_MAPPING_VALUE = "__NA__"


def _is_na_mapping(value: str | None) -> bool:
    return value == NA_MAPPING_VALUE


def _is_mapped_column(value: str | None) -> bool:
    return bool(value) and not _is_na_mapping(value)


def get_gstr2b_mapping(db: Session, tenant_id: int, mapping_id: int) -> Gstr2bMapping:
    row = (
        db.query(Gstr2bMapping)
        .filter(Gstr2bMapping.tenant_id == tenant_id, Gstr2bMapping.id == mapping_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mapping not found")
    return row


def list_master_fields_for_gstr2b(db: Session, tenant_id: int) -> list[ReconciliationMasterField]:
    ensure_default_master_fields(db, tenant_id)
    return (
        db.query(ReconciliationMasterField)
        .filter(
            ReconciliationMasterField.tenant_id == tenant_id,
            ReconciliationMasterField.is_active.is_(True),
            ReconciliationMasterField.applicable_source.in_(("gstr_2b", "both")),
        )
        .order_by(
            ReconciliationMasterField.display_order.asc(),
            ReconciliationMasterField.field_name.asc(),
        )
        .all()
    )


def _duplicate_version(
    db: Session, tenant_id: int, name: str, version: str, exclude_id: int | None = None
) -> bool:
    q = db.query(Gstr2bMapping).filter(
        Gstr2bMapping.tenant_id == tenant_id,
        Gstr2bMapping.mapping_name.ilike(name.strip()),
        Gstr2bMapping.version.ilike(version.strip()),
    )
    if exclude_id is not None:
        q = q.filter(Gstr2bMapping.id != exclude_id)
    return q.first() is not None


def validate_mapping_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mapping name is required")
    if len(cleaned) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mapping name is too long")
    return cleaned


def validate_version(version: str) -> str:
    cleaned = version.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version is required")
    if len(cleaned) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version is too long")
    return cleaned


def parse_sheet_mappings_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sheet mappings must be valid JSON",
        ) from exc
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sheet mappings must be a JSON object",
        )
    return data


def _clean_column_mappings(raw: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, val in raw.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        if not isinstance(val, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each column mapping value must be a string",
            )
        result[str(key)] = val.strip()
    return result


def _field_required(field_code: str, mappings: dict[str, str]) -> bool:
    if _is_na_mapping(mappings.get(field_code)):
        return False
    if field_code in OPTIONAL_FIELD_CODES:
        return False
    if field_code == "total_tax":
        if _is_mapped_column(mappings.get(field_code)):
            return False
        return not all(_is_mapped_column(mappings.get(src)) for src in DERIVED_TOTAL_TAX_SOURCES)
    return True


def _mapping_resolved(mappings: dict[str, str], field_code: str) -> bool:
    return field_code in mappings and bool(mappings[field_code])


def validate_sheet_mappings(
    db: Session,
    tenant_id: int,
    sheet_mappings: dict[str, Any],
) -> None:
    master_fields = list_master_fields_for_gstr2b(db, tenant_id)
    allowed_codes = {f.field_code for f in master_fields}
    required_codes = {f.field_code for f in master_fields if f.is_required}

    found_any = False
    errors: list[str] = []

    for tab in SUPPORTED_GSTR2B_TABS:
        tab_data = sheet_mappings.get(tab)
        if not isinstance(tab_data, dict):
            continue
        if not tab_data.get("found"):
            continue

        found_any = True
        columns = tab_data.get("columns") or []
        if not isinstance(columns, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid columns for tab {tab}",
            )
        column_set = set(columns)

        raw_mappings = tab_data.get("column_mappings") or {}
        if not isinstance(raw_mappings, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid column mappings for tab {tab}",
            )
        mappings = _clean_column_mappings(raw_mappings)

        extra_keys = set(mappings.keys()) - allowed_codes - {"note_type"}
        if extra_keys:
            errors.append(f"{tab}: unknown field codes {', '.join(sorted(extra_keys))}")

        invalid_cols = sorted(
            {c for c in mappings.values() if _is_mapped_column(c) and c not in column_set}
        )
        if invalid_cols:
            errors.append(f"{tab}: columns not in sheet: {', '.join(invalid_cols)}")

        seen: dict[str, str] = {}
        for field_code, col in mappings.items():
            if not _is_mapped_column(col):
                continue
            if col in seen:
                errors.append(
                    f"{tab}: column '{col}' mapped to both {seen[col]} and {field_code}"
                )
            seen[col] = field_code

        for code in required_codes:
            if code in OPTIONAL_FIELD_CODES:
                continue
            if not _field_required(code, mappings):
                continue
            if not _mapping_resolved(mappings, code):
                errors.append(f"{tab}: required field '{code}' is not mapped")

        if tab in CDNR_TABS and not _mapping_resolved(mappings, "note_type"):
            errors.append(f"{tab}: Note Type must be mapped or marked N/A")

    if not found_any:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one supported GSTR-2B sheet must be found in the uploaded file.",
        )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )


def deactivate_all_mappings(db: Session, tenant_id: int, exclude_id: int | None = None) -> None:
    q = db.query(Gstr2bMapping).filter(
        Gstr2bMapping.tenant_id == tenant_id,
        Gstr2bMapping.is_active.is_(True),
    )
    if exclude_id is not None:
        q = q.filter(Gstr2bMapping.id != exclude_id)
    for row in q.all():
        row.is_active = False


def activate_mapping(db: Session, tenant_id: int, mapping_id: int) -> Gstr2bMapping:
    row = get_gstr2b_mapping(db, tenant_id, mapping_id)
    deactivate_all_mappings(db, tenant_id, exclude_id=row.id)
    row.is_active = True
    return row


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip()
    return cleaned or "upload.xlsx"


def _mapping_storage_dir(tenant_id: int, mapping_id: int) -> Path:
    settings = get_settings()
    return Path(settings.file_storage_dir) / str(tenant_id) / "gstr-2b" / str(mapping_id)


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


def read_stored_mapping_file(stored_file_path: str | None) -> bytes | None:
    if not stored_file_path:
        return None
    path = Path(get_settings().file_storage_dir) / stored_file_path
    if not path.exists():
        return None
    return path.read_bytes()


async def read_upload_file(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel file is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    return file.filename, content


def _build_tab_mapping(
    db: Session,
    tenant_id: int,
    content: bytes,
    filename: str,
    tab: str,
    excel_sheet_name: str | None,
) -> dict[str, Any]:
    if not excel_sheet_name:
        return {"found": False, "tab": tab, "excel_sheet_name": None}

    columns, sample_row = parse_sheet_data(content, filename, excel_sheet_name)
    master_fields = list_master_fields_for_gstr2b(db, tenant_id)
    field_codes = [f.field_code for f in master_fields]
    suggested, confidence = auto_match_gstr2b_columns(
        field_codes,
        columns,
        include_note_type=tab in CDNR_TABS,
        tab=tab,
    )
    return {
        "found": True,
        "tab": tab,
        "excel_sheet_name": excel_sheet_name,
        "columns": columns,
        "sample_row": sample_row,
        "column_mappings": suggested,
        "auto_match_confidence": confidence,
    }


def build_parse_result(db: Session, tenant_id: int, content: bytes, filename: str) -> dict[str, Any]:
    excel_sheets = list_workbook_sheets(content, filename)
    tab_to_sheet = map_workbook_sheets(excel_sheets)
    master_fields = list_master_fields_for_gstr2b(db, tenant_id)

    tabs: dict[str, Any] = {}
    found_count = 0
    for tab in SUPPORTED_GSTR2B_TABS:
        tab_data = _build_tab_mapping(db, tenant_id, content, filename, tab, tab_to_sheet.get(tab))
        tabs[tab] = tab_data
        if tab_data.get("found"):
            found_count += 1

    if found_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported GSTR-2B sheets were found. Expected tabs such as B2B, B2BA, B2B-CDNR, etc.",
        )

    return {
        "excel_sheets": excel_sheets,
        "tabs": tabs,
        "master_fields": master_fields,
    }


def normalize_sheet_mappings_for_storage(
    db: Session,
    tenant_id: int,
    content: bytes,
    filename: str,
    sheet_mappings: dict[str, Any],
) -> dict[str, Any]:
    """Ensure stored sheet mappings include columns/sample rows from file."""
    stored: dict[str, Any] = {}

    for tab in SUPPORTED_GSTR2B_TABS:
        tab_data = sheet_mappings.get(tab)
        if not isinstance(tab_data, dict):
            stored[tab] = {"found": False, "tab": tab}
            continue

        if not tab_data.get("found"):
            stored[tab] = {"found": False, "tab": tab, "excel_sheet_name": tab_data.get("excel_sheet_name")}
            continue

        excel_sheet = tab_data.get("excel_sheet_name")
        if not excel_sheet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tab {tab} is marked found but has no Excel sheet name",
            )

        columns, sample_row = parse_sheet_data(content, filename, str(excel_sheet))
        mappings = _clean_column_mappings(tab_data.get("column_mappings") or {})
        validate_sheet_mappings(
            db,
            tenant_id,
            {tab: {"found": True, "columns": columns, "column_mappings": mappings}},
        )

        stored[tab] = {
            "found": True,
            "tab": tab,
            "excel_sheet_name": excel_sheet,
            "columns": columns,
            "sample_row": sample_row,
            "column_mappings": mappings,
        }

    return stored
