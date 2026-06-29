from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import Client, ReconciliationCase, ReconciliationCaseRecord
from app.schemas.reconciliation_cases import (
    ProcessContextOut,
    ReconciliationCaseCreate,
    ReconciliationCaseDetailOut,
    ReconciliationCaseOut,
    ReconciliationCaseRecordOut,
    ReconciliationCaseUpdate,
)
from app.services.reconciliation_case_export import export_case_tab_excel
from app.services.reconciliation_cases import (
    _update_status_after_files,
    build_process_context,
    delete_case_storage,
    get_case,
    process_case,
    read_upload_file,
    resolve_client,
    resolve_pr_mapping,
    save_case_file,
    validate_case_name,
    validate_tax_period,
)

router = APIRouter()


def _client_names(db: Session, tenant_id: int, cases: list[ReconciliationCase]) -> dict[int, str]:
    client_ids = {c.client_id for c in cases if c.client_id}
    if not client_ids:
        return {}
    rows = (
        db.query(Client.id, Client.client_name)
        .filter(Client.tenant_id == tenant_id, Client.id.in_(client_ids))
        .all()
    )
    return {row.id: row.client_name for row in rows}


def _serialize_case(case: ReconciliationCase, client_name: str | None = None) -> ReconciliationCaseOut:
    return ReconciliationCaseOut(
        id=case.id,
        case_name=case.case_name,
        client_id=case.client_id,
        client_name=client_name,
        tax_period_month=case.tax_period_month,
        tax_period_year=case.tax_period_year,
        status=case.status,
        gstr2b_original_filename=case.gstr2b_original_filename,
        pr_original_filename=case.pr_original_filename,
        gstr2b_mapping_id=case.gstr2b_mapping_id,
        pr_mapping_id=case.pr_mapping_id,
        gstr2b_mapping_name=case.gstr2b_mapping_name,
        pr_mapping_name=case.pr_mapping_name,
        summary_counts=case.summary_counts or {},
        error_message=case.error_message,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/reconciliation-cases", response_model=list[ReconciliationCaseOut])
def list_cases(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.access")),
    search: str | None = None,
    status_filter: str | None = None,
    tax_period_month: int | None = None,
    tax_period_year: int | None = None,
) -> list[ReconciliationCaseOut]:
    q = db.query(ReconciliationCase).filter(ReconciliationCase.tenant_id == ctx.tenant.id)

    if search and search.strip():
        raw = search.strip()
        term = f"%{raw.lower()}%"
        client_ids = [
            row.id
            for row in db.query(Client.id)
            .filter(Client.tenant_id == ctx.tenant.id, Client.client_name.ilike(term))
            .all()
        ]
        filters = [ReconciliationCase.case_name.ilike(term)]
        if client_ids:
            filters.append(ReconciliationCase.client_id.in_(client_ids))
        if raw.isdigit():
            month = int(raw)
            if 1 <= month <= 12:
                filters.append(ReconciliationCase.tax_period_month == month)
        q = q.filter(or_(*filters))

    if status_filter:
        q = q.filter(ReconciliationCase.status == status_filter)
    if tax_period_month:
        q = q.filter(ReconciliationCase.tax_period_month == tax_period_month)
    if tax_period_year:
        q = q.filter(ReconciliationCase.tax_period_year == tax_period_year)

    cases = q.order_by(ReconciliationCase.updated_at.desc(), ReconciliationCase.id.desc()).all()
    names = _client_names(db, ctx.tenant.id, cases)
    return [_serialize_case(c, names.get(c.client_id) if c.client_id else None) for c in cases]


@router.get("/reconciliation-cases/{case_id}", response_model=ReconciliationCaseDetailOut)
def get_case_detail(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.access")),
) -> ReconciliationCaseDetailOut:
    case = get_case(db, ctx.tenant.id, case_id)
    client_name = None
    if case.client_id:
        client = resolve_client(db, ctx.tenant.id, case.client_id)
        client_name = client.client_name
    base = _serialize_case(case, client_name)
    context = build_process_context(db, ctx.tenant.id, case)
    return ReconciliationCaseDetailOut(
        **base.model_dump(),
        process_context=ProcessContextOut(**context),
    )


@router.get("/reconciliation-cases/{case_id}/records", response_model=list[ReconciliationCaseRecordOut])
def list_case_records(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.access")),
    category: str | None = None,
) -> list[ReconciliationCaseRecord]:
    get_case(db, ctx.tenant.id, case_id)
    q = db.query(ReconciliationCaseRecord).filter(ReconciliationCaseRecord.case_id == case_id)
    if category:
        q = q.filter(ReconciliationCaseRecord.category == category)
    return q.order_by(ReconciliationCaseRecord.id.asc()).all()


@router.get("/reconciliation-cases/{case_id}/export")
def export_case_tab(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.access")),
    tab: str = Query(..., description="summary, all, or a record category tab key"),
) -> Response:
    case = get_case(db, ctx.tenant.id, case_id)
    client_name = None
    if case.client_id:
        client = resolve_client(db, ctx.tenant.id, case.client_id)
        client_name = client.client_name
    content, filename = export_case_tab_excel(
        db,
        ctx.tenant.id,
        case_id,
        tab,
        client_name=client_name,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/reconciliation-cases", response_model=ReconciliationCaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.manage")),
    case_name: str = Form(...),
    tax_period_month: int = Form(...),
    tax_period_year: int = Form(...),
    client_id: int | None = Form(default=None),
    pr_mapping_id: int | None = Form(default=None),
    gstr2b_file: UploadFile | None = File(default=None),
    purchase_register_file: UploadFile | None = File(default=None),
) -> ReconciliationCaseOut:
    name = validate_case_name(case_name)
    month, year = validate_tax_period(tax_period_month, tax_period_year)
    client = resolve_client(db, ctx.tenant.id, client_id)
    if pr_mapping_id is not None:
        resolve_pr_mapping(db, ctx.tenant.id, pr_mapping_id, client)

    row = ReconciliationCase(
        tenant_id=ctx.tenant.id,
        case_name=name,
        client_id=client.id if client else None,
        tax_period_month=month,
        tax_period_year=year,
        pr_mapping_id=pr_mapping_id,
        status="draft",
        summary_counts={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if gstr2b_file and gstr2b_file.filename:
        filename, content = await read_upload_file(gstr2b_file)
        row.gstr2b_original_filename = filename
        row.gstr2b_stored_path = save_case_file(ctx.tenant.id, row.id, filename, content, "gstr2b")
    if purchase_register_file and purchase_register_file.filename:
        filename, content = await read_upload_file(purchase_register_file)
        row.pr_original_filename = filename
        row.pr_stored_path = save_case_file(ctx.tenant.id, row.id, filename, content, "pr")

    _update_status_after_files(row)
    db.commit()
    db.refresh(row)

    client_name = client.client_name if client else None
    return _serialize_case(row, client_name)


@router.patch("/reconciliation-cases/{case_id}", response_model=ReconciliationCaseOut)
async def update_case(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.manage")),
    case_name: str | None = Form(default=None),
    tax_period_month: int | None = Form(default=None),
    tax_period_year: int | None = Form(default=None),
    client_id: int | None = Form(default=None),
    pr_mapping_id: int | None = Form(default=None),
    gstr2b_file: UploadFile | None = File(default=None),
    purchase_register_file: UploadFile | None = File(default=None),
    clear_gstr2b_file: bool = Form(default=False),
    clear_purchase_register_file: bool = Form(default=False),
) -> ReconciliationCaseOut:
    row = get_case(db, ctx.tenant.id, case_id)
    client = resolve_client(db, ctx.tenant.id, client_id) if client_id is not None else None

    if case_name is not None:
        row.case_name = validate_case_name(case_name)
    if tax_period_month is not None and tax_period_year is not None:
        row.tax_period_month, row.tax_period_year = validate_tax_period(tax_period_month, tax_period_year)
    elif tax_period_month is not None or tax_period_year is not None:
        month = tax_period_month if tax_period_month is not None else row.tax_period_month
        year = tax_period_year if tax_period_year is not None else row.tax_period_year
        row.tax_period_month, row.tax_period_year = validate_tax_period(month, year)
    if client_id is not None:
        row.client_id = client.id if client else None
    if pr_mapping_id is not None:
        resolve_pr_mapping(db, ctx.tenant.id, pr_mapping_id, client)
        row.pr_mapping_id = pr_mapping_id

    files_changed = False
    if clear_gstr2b_file:
        row.gstr2b_original_filename = None
        row.gstr2b_stored_path = None
        files_changed = True
    if clear_purchase_register_file:
        row.pr_original_filename = None
        row.pr_stored_path = None
        files_changed = True

    if gstr2b_file and gstr2b_file.filename:
        filename, content = await read_upload_file(gstr2b_file)
        row.gstr2b_original_filename = filename
        row.gstr2b_stored_path = save_case_file(ctx.tenant.id, row.id, filename, content, "gstr2b")
        files_changed = True
    if purchase_register_file and purchase_register_file.filename:
        filename, content = await read_upload_file(purchase_register_file)
        row.pr_original_filename = filename
        row.pr_stored_path = save_case_file(ctx.tenant.id, row.id, filename, content, "pr")
        files_changed = True

    if files_changed and row.status in {"processed", "review_pending", "completed"}:
        row.status = "files_uploaded"
        row.summary_counts = {}
        row.error_message = None
        db.query(ReconciliationCaseRecord).filter(ReconciliationCaseRecord.case_id == row.id).delete()
    else:
        _update_status_after_files(row)

    db.commit()
    db.refresh(row)

    client_name = None
    if row.client_id:
        c = resolve_client(db, ctx.tenant.id, row.client_id)
        client_name = c.client_name
    return _serialize_case(row, client_name)


@router.post("/reconciliation-cases/{case_id}/process", response_model=ReconciliationCaseOut)
def run_process(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.manage")),
    pr_mapping_id: int | None = Query(default=None),
) -> ReconciliationCaseOut:
    row = get_case(db, ctx.tenant.id, case_id)
    if pr_mapping_id is not None:
        client = resolve_client(db, ctx.tenant.id, row.client_id) if row.client_id else None
        resolve_pr_mapping(db, ctx.tenant.id, pr_mapping_id, client)
        row.pr_mapping_id = pr_mapping_id
        db.commit()
    row = process_case(db, ctx.tenant.id, case_id)
    client_name = None
    if row.client_id:
        c = resolve_client(db, ctx.tenant.id, row.client_id)
        client_name = c.client_name
    return _serialize_case(row, client_name)


@router.delete("/reconciliation-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("cases.manage")),
) -> None:
    row = get_case(db, ctx.tenant.id, case_id)
    delete_case_storage(ctx.tenant.id, row.id)
    db.delete(row)
    db.commit()
