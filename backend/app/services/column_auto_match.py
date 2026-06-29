"""Auto-match Excel column headers to reconciliation master field codes."""

from __future__ import annotations

import re

FIELD_HEADER_PATTERNS: dict[str, tuple[str, ...]] = {
    "voucher_number": (
        "voucher no",
        "voucher number",
        "voucher #",
        "vch no",
        "voucher",
    ),
    "company_gstin": (
        "company gstin",
        "gstin",
        "company gst no",
        "company gstin no",
        "gstin/uin",
    ),
    "supplier_name": (
        "supplier name",
        "vendor name",
        "party account",
        "party name",
        "vendor",
        "supplier",
    ),
    "supplier_gstin": (
        "supplier gstin",
        "vendor gstin",
        "party gstin",
        "gstin of supplier",
        "supplier gst no",
        "vendor gst no",
    ),
    "supplier_invoice_no": (
        "supplier invoice no",
        "supplier bill no",
        "invoice #",
        "invoice number",
        "bill no",
        "invoice no",
        "bill number",
        "supplier inv no",
    ),
    "supplier_invoice_date": (
        "supplier invoice date",
        "supplier bill date",
        "invoice date",
        "bill date",
        "inv date",
    ),
    "taxable_amount": (
        "taxable amount",
        "gst taxable value",
        "taxable value",
        "sub total",
        "subtotal",
        "taxable amt",
    ),
    "igst": ("igst", "integrated tax", "igst amount"),
    "sgst": ("sgst", "state tax", "state/ut tax", "state gst"),
    "cgst": ("cgst", "central tax", "central gst"),
    "total_tax": ("total tax", "tax amount", "total gst"),
    "grand_total": (
        "grand total",
        "net amount",
        "total",
        "invoice value",
        "bill amount",
        "total amount",
    ),
}

Confidence = str  # "high" | "low" | "none"


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _pattern_score(normalized_header: str, pattern: str) -> int:
    norm_pattern = _normalize_header(pattern)
    if not norm_pattern:
        return 0
    if normalized_header == norm_pattern:
        return 100
    if normalized_header.endswith(norm_pattern) or normalized_header.startswith(norm_pattern):
        return 80
    if norm_pattern in normalized_header or normalized_header in norm_pattern:
        return 60
    return 0


def auto_match_columns(
    field_codes: list[str],
    excel_columns: list[str],
) -> tuple[dict[str, str | None], dict[str, Confidence]]:
    """Return suggested column per field and match confidence."""
    used_columns: set[str] = set()
    mappings: dict[str, str | None] = {}
    confidence: dict[str, Confidence] = {}

    normalized_columns = {col: _normalize_header(col) for col in excel_columns}

    for field_code in field_codes:
        patterns = FIELD_HEADER_PATTERNS.get(field_code, ())
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
            mappings[field_code] = best_column
            confidence[field_code] = "high"
            used_columns.add(best_column)
        elif best_column and best_score >= 60:
            mappings[field_code] = best_column
            confidence[field_code] = "low"
            used_columns.add(best_column)
        else:
            mappings[field_code] = None
            confidence[field_code] = "none"

    return mappings, confidence
