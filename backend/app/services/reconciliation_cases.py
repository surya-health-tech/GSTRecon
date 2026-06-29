"""Reconciliation case CRUD, file storage, and processing."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Client,
    Gstr2bMapping,
    PurchaseRegisterMapping,
    ReconciliationCase,
    ReconciliationCaseRecord,
)
from app.services.purchase_register_excel import SUPPORTED_EXTENSIONS
from app.services.reconciliation_engine import compute_summary_counts, reconcile_records
from app.services.reconciliation_import import import_gstr2b_records, import_purchase_register_records

CASE_STATUSES = frozenset(
    {
        "draft",
        "files_uploaded",
        "processing",
        "processed",
        "review_pending",
        "completed",
        "error",
    }
)


def get_case(db: Session, tenant_id: int, case_id: int) -> ReconciliationCase:
    row = (
        db.query(ReconciliationCase)
        .filter(ReconciliationCase.tenant_id == tenant_id, ReconciliationCase.id == case_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return row


def validate_case_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case Name is required")
    if len(cleaned) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Case Name is too long")
    return cleaned


def validate_tax_period(month: int, year: int) -> tuple[int, int]:
    if month < 1 or month > 12:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tax Period month must be 1–12")
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tax Period year is invalid")
    return month, year


def get_active_gstr2b_mapping(db: Session, tenant_id: int) -> Gstr2bMapping | None:
    return (
        db.query(Gstr2bMapping)
        .filter(Gstr2bMapping.tenant_id == tenant_id, Gstr2bMapping.is_active.is_(True))
        .first()
    )


def list_pr_mappings_for_source(db: Session, tenant_id: int, source: str | None) -> list[PurchaseRegisterMapping]:
    q = db.query(PurchaseRegisterMapping).filter(PurchaseRegisterMapping.tenant_id == tenant_id)
    if source:
        q = q.filter(PurchaseRegisterMapping.source == source)
    return q.order_by(PurchaseRegisterMapping.mapping_name.asc()).all()


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]", "_", base).strip()
    return cleaned or "upload.xlsx"


def _case_storage_dir(tenant_id: int, case_id: int) -> Path:
    settings = get_settings()
    return Path(settings.file_storage_dir) / str(tenant_id) / "cases" / str(case_id)


def save_case_file(tenant_id: int, case_id: int, filename: str, content: bytes, kind: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a .xls or .xlsx file.",
        )
    dest_dir = _case_storage_dir(tenant_id, case_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    dest_path = dest_dir / f"{kind}_{safe_name}"
    dest_path.write_bytes(content)
    return str(dest_path.relative_to(get_settings().file_storage_dir))


def read_case_file(stored_path: str | None) -> bytes | None:
    if not stored_path:
        return None
    path = Path(get_settings().file_storage_dir) / stored_path
    if not path.exists():
        return None
    return path.read_bytes()


def delete_case_storage(tenant_id: int, case_id: int) -> None:
    dest_dir = _case_storage_dir(tenant_id, case_id)
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)


async def read_upload_file(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel file is required")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Upload a .xls or .xlsx file.",
        )
    return file.filename, content


def resolve_client(db: Session, tenant_id: int, client_id: int | None) -> Client | None:
    if client_id is None:
        return None
    client = (
        db.query(Client)
        .filter(Client.tenant_id == tenant_id, Client.id == client_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


def resolve_pr_mapping(
    db: Session,
    tenant_id: int,
    mapping_id: int | None,
    client: Client | None,
) -> PurchaseRegisterMapping | None:
    if mapping_id is not None:
        row = (
            db.query(PurchaseRegisterMapping)
            .filter(PurchaseRegisterMapping.tenant_id == tenant_id, PurchaseRegisterMapping.id == mapping_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase Register mapping not found")
        return row
    if client:
        mappings = list_pr_mappings_for_source(db, tenant_id, client.purchase_system_type)
        if len(mappings) == 1:
            return mappings[0]
    return None


def _update_status_after_files(case: ReconciliationCase) -> None:
    if case.gstr2b_stored_path and case.pr_stored_path:
        case.status = "files_uploaded"
    else:
        case.status = "draft"


def process_case(db: Session, tenant_id: int, case_id: int) -> ReconciliationCase:
    case = get_case(db, tenant_id, case_id)

    if not case.gstr2b_stored_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GSTR-2B file is required before processing")
    if not case.pr_stored_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchase Register file is required before processing",
        )

    gstr2b_mapping = get_active_gstr2b_mapping(db, tenant_id)
    if not gstr2b_mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active GSTR-2B mapping exists. Configure and activate a GSTR-2B mapping first.",
        )

    client = None
    if case.client_id:
        client = resolve_client(db, tenant_id, case.client_id)

    pr_mapping = resolve_pr_mapping(db, tenant_id, case.pr_mapping_id, client)
    if not pr_mapping:
        source_hint = client.purchase_system_type if client else "the selected source"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No Purchase Register mapping exists for {source_hint}. Select or create a mapping first.",
        )

    gstr2b_content = read_case_file(case.gstr2b_stored_path)
    pr_content = read_case_file(case.pr_stored_path)
    if not gstr2b_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GSTR-2B file could not be read")
    if not pr_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Purchase Register file could not be read")

    case.status = "processing"
    case.error_message = None
    db.commit()

    try:
        portal_records = import_gstr2b_records(
            gstr2b_content,
            case.gstr2b_original_filename or "gstr2b.xlsx",
            gstr2b_mapping.sheet_mappings or {},
        )
        book_records = import_purchase_register_records(
            pr_content,
            case.pr_original_filename or "purchase_register.xlsx",
            sheet_name=pr_mapping.sheet_name,
            column_mappings=pr_mapping.column_mappings or {},
        )
        if not portal_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No records were found in the GSTR-2B file using the active mapping.",
            )
        if not book_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No records were found in the Purchase Register file using the selected mapping.",
            )

        results = reconcile_records(portal_records, book_records)
        summary = compute_summary_counts(portal_records, book_records, results)

        db.query(ReconciliationCaseRecord).filter(ReconciliationCaseRecord.case_id == case.id).delete()

        for result in results:
            db.add(
                ReconciliationCaseRecord(
                    case_id=case.id,
                    category=result.category,
                    match_status=result.match_status,
                    remarks=result.remarks,
                    portal_data=result.portal_data,
                    book_data=result.book_data,
                    normalized=result.normalized,
                )
            )

        case.gstr2b_mapping_id = gstr2b_mapping.id
        case.gstr2b_mapping_name = gstr2b_mapping.mapping_name
        case.pr_mapping_id = pr_mapping.id
        case.pr_mapping_name = pr_mapping.mapping_name
        case.summary_counts = summary
        case.status = "processed"
        case.error_message = None
        db.commit()
        db.refresh(case)
        return case
    except HTTPException as exc:
        case.status = "error"
        case.error_message = str(exc.detail) if isinstance(exc.detail, str) else "Processing failed"
        db.commit()
        raise
    except Exception as exc:
        case.status = "error"
        case.error_message = f"Processing failed: {exc}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing failed. Check files and mappings, then try again.",
        ) from exc


def build_process_context(db: Session, tenant_id: int, case: ReconciliationCase) -> dict[str, Any]:
    client = resolve_client(db, tenant_id, case.client_id) if case.client_id else None
    active_gstr2b = get_active_gstr2b_mapping(db, tenant_id)
    source = client.purchase_system_type if client else None
    pr_mappings = list_pr_mappings_for_source(db, tenant_id, source)
    return {
        "active_gstr2b_mapping": (
            {
                "id": active_gstr2b.id,
                "mapping_name": active_gstr2b.mapping_name,
                "version": active_gstr2b.version,
            }
            if active_gstr2b
            else None
        ),
        "purchase_register_mappings": [
            {"id": m.id, "mapping_name": m.mapping_name, "source": m.source} for m in pr_mappings
        ],
        "suggested_pr_mapping_id": (
            pr_mappings[0].id if client and len(pr_mappings) == 1 else case.pr_mapping_id
        ),
        "client_purchase_system_type": source,
    }
