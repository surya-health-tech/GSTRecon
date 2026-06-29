from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import ReconciliationMasterField
from app.schemas.master_fields import MasterFieldCreate, MasterFieldOut, MasterFieldUpdate
from app.services.master_fields import (
    _duplicate_code,
    _duplicate_name,
    ensure_default_master_fields,
    get_master_field,
    validate_field_payload,
)

router = APIRouter()


@router.get("/data-mapping/master-fields", response_model=list[MasterFieldOut])
def list_master_fields(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.access")),
    search: str | None = None,
    applicable_source: str | None = None,
    data_type: str | None = None,
    is_required: bool | None = None,
    is_active: bool | None = None,
    is_system: bool | None = None,
) -> list[ReconciliationMasterField]:
    ensure_default_master_fields(db, ctx.tenant.id)
    db.commit()

    q = db.query(ReconciliationMasterField).filter(
        ReconciliationMasterField.tenant_id == ctx.tenant.id
    )
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.filter(
            or_(
                ReconciliationMasterField.field_name.ilike(term),
                ReconciliationMasterField.field_code.ilike(term),
            )
        )
    if applicable_source:
        q = q.filter(ReconciliationMasterField.applicable_source == applicable_source)
    if data_type:
        q = q.filter(ReconciliationMasterField.data_type == data_type)
    if is_required is not None:
        q = q.filter(ReconciliationMasterField.is_required.is_(is_required))
    if is_active is not None:
        q = q.filter(ReconciliationMasterField.is_active.is_(is_active))
    if is_system is not None:
        q = q.filter(ReconciliationMasterField.is_system.is_(is_system))

    return q.order_by(
        ReconciliationMasterField.display_order.asc(),
        ReconciliationMasterField.field_name.asc(),
    ).all()


@router.post(
    "/data-mapping/master-fields",
    response_model=MasterFieldOut,
    status_code=status.HTTP_201_CREATED,
)
def create_master_field(
    body: MasterFieldCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> ReconciliationMasterField:
    field_code = body.resolved_field_code()
    validate_field_payload(
        field_name=body.field_name,
        field_code=field_code,
        data_type=body.data_type,
        applicable_source=body.applicable_source,
        display_order=body.display_order,
    )
    if _duplicate_name(db, ctx.tenant.id, body.field_name):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field name already exists")
    if _duplicate_code(db, ctx.tenant.id, field_code):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field code already exists")

    row = ReconciliationMasterField(
        tenant_id=ctx.tenant.id,
        field_name=body.field_name.strip(),
        field_code=field_code,
        data_type=body.data_type,
        is_required=body.is_required,
        applicable_source=body.applicable_source,
        is_system=False,
        is_active=body.is_active,
        display_order=body.display_order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/data-mapping/master-fields/{field_id}", response_model=MasterFieldOut)
def update_master_field(
    field_id: int,
    body: MasterFieldUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> ReconciliationMasterField:
    row = get_master_field(db, ctx.tenant.id, field_id)
    data = body.model_dump(exclude_unset=True)

    if row.is_system:
        allowed = {"display_order", "is_active"}
        disallowed = set(data.keys()) - allowed
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="System fields can only change display order and active status",
            )
        if "field_code" in data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="System field code cannot be changed",
            )
    elif "field_code" in data and data["field_code"] is not None:
        data["field_code"] = data["field_code"].strip().lower()

    validate_field_payload(
        field_name=data.get("field_name"),
        field_code=data.get("field_code"),
        data_type=data.get("data_type"),
        applicable_source=data.get("applicable_source"),
        display_order=data.get("display_order"),
    )

    if "field_name" in data and _duplicate_name(
        db, ctx.tenant.id, data["field_name"], exclude_id=row.id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field name already exists")
    if "field_code" in data and data["field_code"] and _duplicate_code(
        db, ctx.tenant.id, data["field_code"], exclude_id=row.id
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Field code already exists")

    for key, val in data.items():
        if key == "field_name" and val is not None:
            setattr(row, key, val.strip())
        else:
            setattr(row, key, val)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/data-mapping/master-fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_master_field(
    field_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("data_mapping.manage")),
) -> None:
    row = get_master_field(db, ctx.tenant.id, field_id)
    if row.is_system:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System default fields cannot be deleted",
        )
    db.delete(row)
    db.commit()
