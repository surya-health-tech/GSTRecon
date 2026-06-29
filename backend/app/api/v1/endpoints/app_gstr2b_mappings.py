from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import Gstr2bMapping
from app.schemas.gstr2b_mappings import (
    Gstr2bMappingListItem,
    Gstr2bMappingOut,
    Gstr2bMappingUpdate,
    Gstr2bParseResult,
    Gstr2bTabMappingOut,
    MasterFieldSummary,
)
from app.services.gstr2b_mappings import (
    _duplicate_version,
    activate_mapping,
    build_parse_result,
    deactivate_all_mappings,
    delete_mapping_storage,
    get_gstr2b_mapping,
    normalize_sheet_mappings_for_storage,
    parse_sheet_mappings_json,
    read_stored_mapping_file,
    read_upload_file,
    save_mapping_file,
    validate_mapping_name,
    validate_sheet_mappings,
    validate_version,
)

router = APIRouter()


@router.get("/data-mapping/gstr-2b-mappings", response_model=list[Gstr2bMappingListItem])
def list_gstr2b_mappings(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.access")),
    search: str | None = None,
) -> list[Gstr2bMapping]:
    q = db.query(Gstr2bMapping).filter(Gstr2bMapping.tenant_id == ctx.tenant.id)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.filter(
            or_(
                Gstr2bMapping.mapping_name.ilike(term),
                Gstr2bMapping.version.ilike(term),
            )
        )
    return q.order_by(Gstr2bMapping.is_active.desc(), Gstr2bMapping.created_at.desc()).all()


@router.get("/data-mapping/gstr-2b-mappings/{mapping_id}", response_model=Gstr2bMappingOut)
def get_gstr2b_mapping_detail(
    mapping_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.access")),
) -> Gstr2bMapping:
    return get_gstr2b_mapping(db, ctx.tenant.id, mapping_id)


@router.post("/data-mapping/gstr-2b-mappings/parse-excel", response_model=Gstr2bParseResult)
async def parse_gstr2b_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> Gstr2bParseResult:
    filename, content = await read_upload_file(file)
    result = build_parse_result(db, ctx.tenant.id, content, filename)
    tabs = {k: Gstr2bTabMappingOut.model_validate(v) for k, v in result["tabs"].items()}
    return Gstr2bParseResult(
        excel_sheets=result["excel_sheets"],
        tabs=tabs,
        master_fields=[MasterFieldSummary.model_validate(f) for f in result["master_fields"]],
    )


@router.post(
    "/data-mapping/gstr-2b-mappings",
    response_model=Gstr2bMappingOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_gstr2b_mapping(
    mapping_name: str = Form(...),
    version: str = Form(...),
    sheet_mappings: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> Gstr2bMapping:
    name = validate_mapping_name(mapping_name)
    ver = validate_version(version)
    raw_mappings = parse_sheet_mappings_json(sheet_mappings)

    if _duplicate_version(db, ctx.tenant.id, name, ver):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A mapping with this name and version already exists",
        )

    filename, content = await read_upload_file(file)
    stored_mappings = normalize_sheet_mappings_for_storage(
        db, ctx.tenant.id, content, filename, raw_mappings
    )

    deactivate_all_mappings(db, ctx.tenant.id)

    row = Gstr2bMapping(
        tenant_id=ctx.tenant.id,
        mapping_name=name,
        version=ver,
        is_active=True,
        original_filename=filename,
        sheet_mappings=stored_mappings,
    )
    db.add(row)
    db.flush()
    row.stored_file_path = save_mapping_file(ctx.tenant.id, row.id, filename, content)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/data-mapping/gstr-2b-mappings/{mapping_id}", response_model=Gstr2bMappingOut)
async def update_gstr2b_mapping(
    mapping_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> Gstr2bMapping:
    row = get_gstr2b_mapping(db, ctx.tenant.id, mapping_id)
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        mapping_name = form.get("mapping_name")
        version = form.get("version")
        sheet_mappings_raw = form.get("sheet_mappings")
        upload = form.get("file")

        if mapping_name is not None:
            name = validate_mapping_name(str(mapping_name))
            ver = row.version if version is None else validate_version(str(version))
            if _duplicate_version(db, ctx.tenant.id, name, ver, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A mapping with this name and version already exists",
                )
            row.mapping_name = name

        if version is not None:
            ver = validate_version(str(version))
            if _duplicate_version(db, ctx.tenant.id, row.mapping_name, ver, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A mapping with this name and version already exists",
                )
            row.version = ver

        filename = row.original_filename or "upload.xlsx"
        content: bytes | None = None

        if upload is not None and hasattr(upload, "filename") and upload.filename:
            filename, content = await read_upload_file(upload)
            row.original_filename = filename
            row.stored_file_path = save_mapping_file(ctx.tenant.id, row.id, filename, content)

        if sheet_mappings_raw is not None:
            raw_mappings = parse_sheet_mappings_json(str(sheet_mappings_raw))
            if content is not None:
                row.sheet_mappings = normalize_sheet_mappings_for_storage(
                    db, ctx.tenant.id, content, filename, raw_mappings
                )
            else:
                stored_content = read_stored_mapping_file(row.stored_file_path)
                if stored_content:
                    row.sheet_mappings = normalize_sheet_mappings_for_storage(
                        db, ctx.tenant.id, stored_content, filename, raw_mappings
                    )
                else:
                    validate_sheet_mappings(db, ctx.tenant.id, raw_mappings)
                    row.sheet_mappings = raw_mappings
    else:
        body = Gstr2bMappingUpdate.model_validate(await request.json())
        data = body.model_dump(exclude_unset=True)

        if "mapping_name" in data and data["mapping_name"] is not None:
            name = validate_mapping_name(data["mapping_name"])
            ver = data.get("version") or row.version
            if _duplicate_version(db, ctx.tenant.id, name, ver, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A mapping with this name and version already exists",
                )
            row.mapping_name = name

        if "version" in data and data["version"] is not None:
            ver = validate_version(data["version"])
            if _duplicate_version(db, ctx.tenant.id, row.mapping_name, ver, exclude_id=row.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A mapping with this name and version already exists",
                )
            row.version = ver

        if "sheet_mappings" in data and data["sheet_mappings"] is not None:
            validate_sheet_mappings(db, ctx.tenant.id, data["sheet_mappings"])
            row.sheet_mappings = data["sheet_mappings"]

    db.commit()
    db.refresh(row)
    return row


@router.post("/data-mapping/gstr-2b-mappings/{mapping_id}/activate", response_model=Gstr2bMappingOut)
def mark_gstr2b_mapping_active(
    mapping_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> Gstr2bMapping:
    row = activate_mapping(db, ctx.tenant.id, mapping_id)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/data-mapping/gstr-2b-mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gstr2b_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> None:
    row = get_gstr2b_mapping(db, ctx.tenant.id, mapping_id)
    if row.is_active:
        other_count = (
            db.query(Gstr2bMapping)
            .filter(Gstr2bMapping.tenant_id == ctx.tenant.id, Gstr2bMapping.id != row.id)
            .count()
        )
        if other_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the only GSTR-2B mapping version. Create another version first.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the active mapping. Mark another version as active first.",
        )
    delete_mapping_storage(ctx.tenant.id, row.id)
    db.delete(row)
    db.commit()
