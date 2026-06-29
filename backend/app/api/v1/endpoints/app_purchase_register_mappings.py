import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import PurchaseRegisterMapping
from app.schemas.purchase_register_mappings import (
    ExcelParseResult,
    MasterFieldSummary,
    PurchaseRegisterMappingListItem,
    PurchaseRegisterMappingOut,
    PurchaseRegisterMappingUpdate,
)
from app.services.purchase_register_mappings import (
    _duplicate_name,
    build_parse_result,
    delete_mapping_storage,
    get_purchase_register_mapping,
    parse_column_mappings_json,
    read_upload_file,
    save_mapping_file,
    validate_column_mappings,
    validate_mapping_name,
    validate_source,
)

router = APIRouter()


@router.get(
    "/data-mapping/purchase-register-mappings",
    response_model=list[PurchaseRegisterMappingListItem],
)
def list_purchase_register_mappings(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.access")),
    search: str | None = None,
    source: str | None = None,
) -> list[PurchaseRegisterMapping]:
    q = db.query(PurchaseRegisterMapping).filter(
        PurchaseRegisterMapping.tenant_id == ctx.tenant.id
    )
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.filter(
            or_(
                PurchaseRegisterMapping.mapping_name.ilike(term),
                PurchaseRegisterMapping.source.ilike(term),
            )
        )
    if source:
        q = q.filter(PurchaseRegisterMapping.source == source)

    return q.order_by(
        PurchaseRegisterMapping.mapping_name.asc(),
        PurchaseRegisterMapping.id.desc(),
    ).all()


@router.get(
    "/data-mapping/purchase-register-mappings/{mapping_id}",
    response_model=PurchaseRegisterMappingOut,
)
def get_purchase_register_mapping_detail(
    mapping_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.access")),
) -> PurchaseRegisterMapping:
    return get_purchase_register_mapping(db, ctx.tenant.id, mapping_id)


@router.post(
    "/data-mapping/purchase-register-mappings/parse-excel",
    response_model=ExcelParseResult,
)
async def parse_purchase_register_excel(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> ExcelParseResult:
    filename, content = await read_upload_file(file)
    result = build_parse_result(db, ctx.tenant.id, content, filename, sheet_name or None)
    return ExcelParseResult(
        sheets=result["sheets"],
        sheet_name=result["sheet_name"],
        columns=result["columns"],
        sample_row=result["sample_row"],
        master_fields=[MasterFieldSummary.model_validate(f) for f in result["master_fields"]],
        suggested_mappings=result["suggested_mappings"],
        auto_match_confidence=result["auto_match_confidence"],
    )


@router.post(
    "/data-mapping/purchase-register-mappings",
    response_model=PurchaseRegisterMappingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_register_mapping(
    mapping_name: str = Form(...),
    source: str = Form(...),
    sheet_name: str = Form(...),
    column_mappings: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> PurchaseRegisterMapping:
    name = validate_mapping_name(mapping_name)
    src = validate_source(source)
    mappings = parse_column_mappings_json(column_mappings)

    if _duplicate_name(db, ctx.tenant.id, name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mapping name already exists")

    filename, content = await read_upload_file(file)
    parsed = build_parse_result(db, ctx.tenant.id, content, filename, sheet_name or None)
    selected_sheet = parsed["sheet_name"]
    columns = parsed["columns"]
    sample_row = parsed["sample_row"]

    validate_column_mappings(db, ctx.tenant.id, mappings, columns)

    row = PurchaseRegisterMapping(
        tenant_id=ctx.tenant.id,
        mapping_name=name,
        source=src,
        sheet_name=selected_sheet,
        original_filename=filename,
        excel_columns=columns,
        sample_row=sample_row,
        column_mappings=mappings,
    )
    db.add(row)
    db.flush()

    row.stored_file_path = save_mapping_file(ctx.tenant.id, row.id, filename, content)
    db.commit()
    db.refresh(row)
    return row


@router.patch(
    "/data-mapping/purchase-register-mappings/{mapping_id}",
    response_model=PurchaseRegisterMappingOut,
)
async def update_purchase_register_mapping(
    mapping_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> PurchaseRegisterMapping:
    row = get_purchase_register_mapping(db, ctx.tenant.id, mapping_id)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        mapping_name = form.get("mapping_name")
        source = form.get("source")
        sheet_name = form.get("sheet_name")
        column_mappings_raw = form.get("column_mappings")
        upload = form.get("file")

        if mapping_name is not None:
            name = validate_mapping_name(str(mapping_name))
            if _duplicate_name(db, ctx.tenant.id, name, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Mapping name already exists"
                )
            row.mapping_name = name

        if source is not None:
            row.source = validate_source(str(source))

        if upload is not None and hasattr(upload, "filename") and upload.filename:
            filename, content = await read_upload_file(upload)
            parsed = build_parse_result(
                db,
                ctx.tenant.id,
                content,
                filename,
                str(sheet_name) if sheet_name else row.sheet_name,
            )
            row.sheet_name = parsed["sheet_name"]
            row.original_filename = filename
            row.excel_columns = parsed["columns"]
            row.sample_row = parsed["sample_row"]
            row.stored_file_path = save_mapping_file(ctx.tenant.id, row.id, filename, content)
        elif sheet_name is not None:
            row.sheet_name = str(sheet_name) or None

        if column_mappings_raw is not None:
            mappings = parse_column_mappings_json(str(column_mappings_raw))
            validate_column_mappings(db, ctx.tenant.id, mappings, row.excel_columns)
            row.column_mappings = mappings
    else:
        body = PurchaseRegisterMappingUpdate.model_validate(await request.json())
        data = body.model_dump(exclude_unset=True)

        if "mapping_name" in data and data["mapping_name"] is not None:
            name = validate_mapping_name(data["mapping_name"])
            if _duplicate_name(db, ctx.tenant.id, name, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Mapping name already exists"
                )
            row.mapping_name = name

        if "source" in data and data["source"] is not None:
            row.source = validate_source(data["source"])

        if "sheet_name" in data:
            row.sheet_name = data["sheet_name"]

        if "excel_columns" in data and data["excel_columns"] is not None:
            row.excel_columns = data["excel_columns"]
        if "sample_row" in data and data["sample_row"] is not None:
            row.sample_row = data["sample_row"]

        if "column_mappings" in data and data["column_mappings"] is not None:
            validate_column_mappings(db, ctx.tenant.id, data["column_mappings"], row.excel_columns)
            row.column_mappings = data["column_mappings"]

    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/data-mapping/purchase-register-mappings/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_purchase_register_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> None:
    row = get_purchase_register_mapping(db, ctx.tenant.id, mapping_id)
    delete_mapping_storage(ctx.tenant.id, row.id)
    db.delete(row)
    db.commit()
