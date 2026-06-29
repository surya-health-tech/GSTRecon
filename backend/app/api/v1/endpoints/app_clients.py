from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, get_db, require_permission
from app.models import Client
from app.schemas.clients import ClientCreate, ClientOut, ClientUpdate
from app.services.clients import (
    _duplicate_gst,
    get_client,
    validate_client_name,
    validate_gst_number,
    validate_purchase_system_type,
)

router = APIRouter()


@router.get("/clients", response_model=list[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("clients.access")),
    search: str | None = None,
    purchase_system_type: str | None = None,
) -> list[Client]:
    q = db.query(Client).filter(Client.tenant_id == ctx.tenant.id)
    if search and search.strip():
        raw = search.strip()
        term = f"%{raw.lower()}%"
        gst_term = f"%{raw.upper()}%"
        q = q.filter(
            or_(
                Client.client_name.ilike(term),
                Client.gst_number.ilike(gst_term),
            )
        )
    if purchase_system_type:
        q = q.filter(Client.purchase_system_type == validate_purchase_system_type(purchase_system_type))
    return q.order_by(Client.client_name.asc(), Client.id.desc()).all()


@router.get("/clients/{client_id}", response_model=ClientOut)
def get_client_detail(
    client_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("clients.access")),
) -> Client:
    return get_client(db, ctx.tenant.id, client_id)


@router.post("/clients", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("clients.manage")),
) -> Client:
    name = validate_client_name(body.client_name)
    gst = validate_gst_number(body.gst_number)
    system = validate_purchase_system_type(body.purchase_system_type)

    if _duplicate_gst(db, ctx.tenant.id, gst):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="GST Number already exists")

    row = Client(
        tenant_id=ctx.tenant.id,
        client_name=name,
        gst_number=gst,
        purchase_system_type=system,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    body: ClientUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("clients.manage")),
) -> Client:
    row = get_client(db, ctx.tenant.id, client_id)
    data = body.model_dump(exclude_unset=True)

    if "client_name" in data and data["client_name"] is not None:
        row.client_name = validate_client_name(data["client_name"])
    if "gst_number" in data and data["gst_number"] is not None:
        gst = validate_gst_number(data["gst_number"])
        if _duplicate_gst(db, ctx.tenant.id, gst, exclude_id=row.id):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="GST Number already exists")
        row.gst_number = gst
    if "purchase_system_type" in data and data["purchase_system_type"] is not None:
        row.purchase_system_type = validate_purchase_system_type(data["purchase_system_type"])

    db.commit()
    db.refresh(row)
    return row


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(require_permission("clients.manage")),
) -> None:
    row = get_client(db, ctx.tenant.id, client_id)
    db.delete(row)
    db.commit()
