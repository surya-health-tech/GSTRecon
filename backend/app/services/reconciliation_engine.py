"""Reconciliation matching and classification engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

AMOUNT_TOLERANCE = 1.0

CATEGORIES = (
    "matched_with_books",
    "amount_mismatch",
    "portal_open",
    "books_open",
)


@dataclass
class ReconciliationResult:
    category: str
    portal_data: dict[str, Any] | None
    book_data: dict[str, Any] | None
    normalized: dict[str, Any]
    match_status: str
    remarks: str | None


def _normalize_gstin(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def _normalize_invoice_no(value: object) -> str:
    text = str(value or "").strip().upper()
    return re.sub(r"\s+", "", text)


def _normalize_date(value: object) -> str:
    return str(value or "").strip()


def _tax_total(record: dict[str, Any]) -> float:
    total = float(record.get("total_tax") or 0)
    if total != 0:
        return total
    return float(record.get("igst") or 0) + float(record.get("cgst") or 0) + float(record.get("sgst") or 0)


def _amounts_close(a: float, b: float, tolerance: float = AMOUNT_TOLERANCE) -> bool:
    return abs(a - b) <= tolerance


def _match_key(record: dict[str, Any]) -> str | None:
    gstin = _normalize_gstin(record.get("supplier_gstin"))
    invoice = _normalize_invoice_no(record.get("supplier_invoice_no"))
    if not gstin or not invoice:
        return None
    return f"{gstin}|{invoice}"


def _company_gstin_compatible(portal: dict[str, Any], book: dict[str, Any]) -> bool:
    p = _normalize_gstin(portal.get("company_gstin"))
    b = _normalize_gstin(book.get("company_gstin"))
    if p and b and p != b:
        return False
    return True


def _dates_compatible(portal: dict[str, Any], book: dict[str, Any]) -> bool:
    p = _normalize_date(portal.get("supplier_invoice_date"))
    b = _normalize_date(book.get("supplier_invoice_date"))
    if not p or not b:
        return True
    return p == b


def _build_normalized(portal: dict[str, Any] | None, book: dict[str, Any] | None) -> dict[str, Any]:
    primary = portal or book or {}
    out = dict(primary)
    out["portal_taxable_amount"] = float((portal or {}).get("taxable_amount") or 0)
    out["book_taxable_amount"] = float((book or {}).get("taxable_amount") or 0)
    out["portal_total_tax"] = _tax_total(portal) if portal else 0.0
    out["book_total_tax"] = _tax_total(book) if book else 0.0
    if portal and book:
        out["source"] = "both"
    elif portal:
        out["source"] = "portal"
    else:
        out["source"] = "books"
    return out


def _classify_pair(portal: dict[str, Any], book: dict[str, Any]) -> tuple[str, str, str | None]:
    p_tax = _tax_total(portal)
    b_tax = _tax_total(book)
    p_taxable = float(portal.get("taxable_amount") or 0)
    b_taxable = float(book.get("taxable_amount") or 0)

    tax_match = _amounts_close(p_tax, b_tax)
    taxable_match = _amounts_close(p_taxable, b_taxable) or p_taxable == 0 or b_taxable == 0

    if tax_match and taxable_match:
        return "matched_with_books", "matched", None
    if not tax_match:
        return "amount_mismatch", "tax_mismatch", f"Portal tax {p_tax:.2f} vs Books tax {b_tax:.2f}"
    return "amount_mismatch", "taxable_mismatch", f"Portal taxable {p_taxable:.2f} vs Books {b_taxable:.2f}"


def reconcile_records(
    portal_records: list[dict[str, Any]],
    book_records: list[dict[str, Any]],
) -> list[ReconciliationResult]:
    books_by_key: dict[str, list[dict[str, Any]]] = {}
    for book in book_records:
        key = _match_key(book)
        if key:
            books_by_key.setdefault(key, []).append(book)

    used_book_ids: set[int] = set()
    results: list[ReconciliationResult] = []

    for portal in portal_records:
        key = _match_key(portal)
        if not key:
            results.append(
                ReconciliationResult(
                    category="portal_open",
                    portal_data=portal,
                    book_data=None,
                    normalized=_build_normalized(portal, None),
                    match_status="unmatched",
                    remarks="Missing supplier GSTIN or invoice number",
                )
            )
            continue

        candidates = books_by_key.get(key, [])
        matched_book: dict[str, Any] | None = None
        for book in candidates:
            book_id = id(book)
            if book_id in used_book_ids:
                continue
            if not _company_gstin_compatible(portal, book):
                continue
            matched_book = book
            used_book_ids.add(book_id)
            break

        if matched_book is None:
            # Try relaxed match: same key but allow date mismatch
            for book in candidates:
                book_id = id(book)
                if book_id in used_book_ids:
                    continue
                if not _company_gstin_compatible(portal, book):
                    continue
                matched_book = book
                used_book_ids.add(book_id)
                break

        if matched_book is None:
            results.append(
                ReconciliationResult(
                    category="portal_open",
                    portal_data=portal,
                    book_data=None,
                    normalized=_build_normalized(portal, None),
                    match_status="unmatched",
                    remarks="Not found in Purchase Register",
                )
            )
            continue

        category, match_status, remarks = _classify_pair(portal, matched_book)
        if not _dates_compatible(portal, matched_book) and category == "matched_with_books":
            remarks = "Matched with date difference"

        results.append(
            ReconciliationResult(
                category=category,
                portal_data=portal,
                book_data=matched_book,
                normalized=_build_normalized(portal, matched_book),
                match_status=match_status,
                remarks=remarks,
            )
        )

    for book in book_records:
        if id(book) in used_book_ids:
            continue
        key = _match_key(book)
        if not key:
            continue
        results.append(
            ReconciliationResult(
                category="books_open",
                portal_data=None,
                book_data=book,
                normalized=_build_normalized(None, book),
                match_status="unmatched",
                remarks="Not found in GSTR-2B Portal data",
            )
        )

    return results


def compute_summary_counts(
    portal_records: list[dict[str, Any]],
    book_records: list[dict[str, Any]],
    results: list[ReconciliationResult],
) -> dict[str, int]:
    counts = {
        "total_gstr2b_records": len(portal_records),
        "total_purchase_register_records": len(book_records),
        "matched_with_books": 0,
        "amount_mismatch": 0,
        "portal_open_items": 0,
        "books_open_items": 0,
    }
    for result in results:
        if result.category == "matched_with_books":
            counts["matched_with_books"] += 1
        elif result.category == "amount_mismatch":
            counts["amount_mismatch"] += 1
        elif result.category == "portal_open":
            counts["portal_open_items"] += 1
        elif result.category == "books_open":
            counts["books_open_items"] += 1
    return counts
