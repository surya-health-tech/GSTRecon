"""Auto-match GSTR-2B GST portal column headers to master field codes."""

from __future__ import annotations

import re

from app.services.column_auto_match import Confidence, _normalize_header, _pattern_score

GSTR2B_FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "company_gstin": (
        "company gstin",
        "gstin of recipient",
        "recipient gstin",
        "gstin",
    ),
    "supplier_name": (
        "trade/legal name",
        "trade legal name",
        "legal name",
        "supplier name",
        "name of supplier",
    ),
    "supplier_gstin": (
        "gstin of supplier",
        "supplier gstin",
        "gstin",
    ),
    "supplier_invoice_no": (
        "invoice number",
        "invoice no",
        "note number",
        "document number",
        "document no",
        "invoice #",
        "number",
    ),
    "supplier_invoice_date": (
        "invoice date",
        "note date",
        "document date",
        "date",
    ),
    "taxable_amount": (
        "taxable value (₹)",
        "taxable value",
        "taxable amount",
        "taxable value(rs)",
    ),
    "igst": (
        "integrated tax(₹)",
        "integrated tax",
        "igst",
        "integrated tax amount",
    ),
    "sgst": (
        "state/ut tax(₹)",
        "state/ut tax",
        "state tax",
        "sgst",
        "state/ut tax amount",
    ),
    "cgst": (
        "central tax(₹)",
        "central tax",
        "cgst",
        "central tax amount",
    ),
    "total_tax": (
        "total tax",
        "tax amount",
        "total gst",
        "total tax(₹)",
    ),
    "grand_total": (
        "invoice value(₹)",
        "invoice value",
        "note value (₹)",
        "note value",
        "document value(₹)",
        "document value",
        "grand total",
        "total invoice value",
    ),
}

AMENDMENT_TABS = frozenset({"B2BA", "B2B-CDNRA", "ECOA", "ISDA", "IMPGA", "IMPSEZA"})

NOTE_TYPE_PATTERNS: tuple[str, ...] = (
    "note type",
    "note type ",
    "credit/debit note type",
    "credit debit note type",
    "type of note",
)


def _match_single_field(
    patterns: tuple[str, ...],
    excel_columns: list[str],
    used_columns: set[str],
) -> tuple[str | None, Confidence, int]:
    normalized_columns = {col: _normalize_header(col) for col in excel_columns}
    best_column: str | None = None
    best_score = 0
    for col, norm_col in normalized_columns.items():
        if col in used_columns:
            continue
        for pattern in patterns:
            score = _pattern_score(norm_col, pattern)
            if score > best_score:
                best_score = score
                best_column = col
    if best_column and best_score >= 80:
        return best_column, "high", best_score
    if best_column and best_score >= 60:
        return best_column, "low", best_score
    return None, "none", 0


def _prefer_amendment_column(
    field_code: str,
    matched: str | None,
    excel_columns: list[str],
    tab: str | None,
) -> str | None:
    if not matched or not tab or tab not in AMENDMENT_TABS:
        return matched
    if field_code not in {
        "supplier_invoice_no",
        "supplier_invoice_date",
        "igst",
        "cgst",
        "sgst",
        "grand_total",
        "note_type",
    }:
        return matched
    base = matched.replace(" (2)", "").strip()
    for col in excel_columns:
        if col.startswith(base) and "(2)" in col:
            return col
    return matched


def auto_match_gstr2b_columns(
    field_codes: list[str],
    excel_columns: list[str],
    *,
    include_note_type: bool = False,
    tab: str | None = None,
) -> tuple[dict[str, str | None], dict[str, Confidence]]:
    used_columns: set[str] = set()
    mappings: dict[str, str | None] = {}
    confidence: dict[str, Confidence] = {}

    for field_code in field_codes:
        patterns = GSTR2B_FIELD_PATTERNS.get(field_code, ())
        col, conf, _ = _match_single_field(patterns, excel_columns, used_columns)
        col = _prefer_amendment_column(field_code, col, excel_columns, tab)
        mappings[field_code] = col
        confidence[field_code] = conf
        if col:
            used_columns.add(col)

    if include_note_type:
        col, conf, _ = _match_single_field(NOTE_TYPE_PATTERNS, excel_columns, used_columns)
        col = _prefer_amendment_column("note_type", col, excel_columns, tab)
        mappings["note_type"] = col
        confidence["note_type"] = conf
        if col:
            used_columns.add(col)

    return mappings, confidence
