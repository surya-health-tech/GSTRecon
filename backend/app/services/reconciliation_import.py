"""Import and normalize GSTR-2B portal and purchase register records for reconciliation."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException, status

from app.services.gstr2b_excel import CDNR_TABS, parse_sheet_all_rows
from app.services.gstr2b_mappings import NA_MAPPING_VALUE
from app.services.purchase_register_excel import parse_sheet_all_rows as parse_pr_all_rows

NUMERIC_FIELDS = frozenset(
    {
        "taxable_amount",
        "igst",
        "sgst",
        "cgst",
        "total_tax",
        "grand_total",
    }
)

STRING_FIELDS = frozenset(
    {
        "voucher_number",
        "company_gstin",
        "supplier_name",
        "supplier_gstin",
        "supplier_invoice_no",
        "supplier_invoice_date",
        "note_type",
    }
)


def _is_na(value: str | None) -> bool:
    return value == NA_MAPPING_VALUE


def _parse_amount(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"-", "na", "n/a", "nil", "null"}:
        return 0.0
    text = re.sub(r"[₹$,]", "", text)
    text = text.replace(" ", "")
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _is_credit_note(note_type: str) -> bool:
    t = note_type.strip().lower()
    return t in {"c", "cn", "credit", "credit note", "cr", "creditnote"}


def _is_debit_note(note_type: str) -> bool:
    t = note_type.strip().lower()
    return t in {"d", "dn", "debit", "debit note", "dr", "debitnote"}


def _apply_note_sign(record: dict[str, Any], note_type: str, tab: str | None) -> dict[str, Any]:
    if tab not in CDNR_TABS:
        return record
    if not note_type:
        return record
    if _is_credit_note(note_type):
        sign = -1.0
    elif _is_debit_note(note_type):
        sign = 1.0
    else:
        return record
    out = dict(record)
    for field in NUMERIC_FIELDS:
        if field in out:
            out[field] = float(out[field]) * sign
    return out


def _normalize_row(
    raw_row: dict[str, str],
    column_mappings: dict[str, str],
    *,
    source: str,
    source_tab: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {code: "" for code in STRING_FIELDS}
    for code in NUMERIC_FIELDS:
        record[code] = 0.0

    note_type_value = ""
    for field_code, excel_col in column_mappings.items():
        if not excel_col or _is_na(excel_col):
            continue
        raw_val = raw_row.get(excel_col, "")
        if field_code == "note_type":
            note_type_value = _normalize_string(raw_val)
            record["note_type"] = note_type_value
        elif field_code in NUMERIC_FIELDS:
            record[field_code] = _parse_amount(raw_val)
        elif field_code in STRING_FIELDS:
            record[field_code] = _normalize_string(raw_val)

    igst = float(record.get("igst") or 0)
    cgst = float(record.get("cgst") or 0)
    sgst = float(record.get("sgst") or 0)
    computed_tax = igst + cgst + sgst
    total_tax = float(record.get("total_tax") or 0)
    if total_tax == 0 and computed_tax != 0:
        record["total_tax"] = computed_tax
    elif total_tax == 0:
        record["total_tax"] = computed_tax

    record["source"] = source
    if source_tab:
        record["source_tab"] = source_tab

    if source_tab in CDNR_TABS:
        record = _apply_note_sign(record, note_type_value, source_tab)

    return record


def _is_meaningful_record(record: dict[str, Any]) -> bool:
    if record.get("supplier_gstin") or record.get("supplier_invoice_no"):
        return True
    for field in NUMERIC_FIELDS:
        if float(record.get(field) or 0) != 0:
            return True
    return False


def import_gstr2b_records(
    content: bytes,
    filename: str,
    sheet_mappings: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    found_tabs = 0
    for tab, tab_cfg in sheet_mappings.items():
        if not isinstance(tab_cfg, dict) or not tab_cfg.get("found"):
            continue
        excel_sheet = tab_cfg.get("excel_sheet_name")
        if not excel_sheet:
            continue
        found_tabs += 1
        column_mappings = tab_cfg.get("column_mappings") or {}
        if not any(v for v in column_mappings.values() if v and not _is_na(v)):
            continue
        try:
            _columns, rows = parse_sheet_all_rows(content, filename, excel_sheet)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not read GSTR-2B sheet '{excel_sheet}': {exc}",
            ) from exc
        for row in rows:
            normalized = _normalize_row(row, column_mappings, source="portal", source_tab=tab)
            if _is_meaningful_record(normalized):
                records.append(normalized)

    if found_tabs == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported GSTR-2B sheets were found in the uploaded file.",
        )
    return records


def import_purchase_register_records(
    content: bytes,
    filename: str,
    *,
    sheet_name: str | None,
    column_mappings: dict[str, str],
) -> list[dict[str, Any]]:
    if not any(v for v in column_mappings.values() if v and not _is_na(v)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase Register mapping has no mapped columns.",
        )
    try:
        _columns, rows = parse_pr_all_rows(content, filename, sheet_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read Purchase Register file: {exc}",
        ) from exc

    records: list[dict[str, Any]] = []
    for row in rows:
        normalized = _normalize_row(row, column_mappings, source="books")
        if _is_meaningful_record(normalized):
            records.append(normalized)
    return records
