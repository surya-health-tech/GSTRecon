from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_platform_super_admin_console
from app.models import Tenant, User
from app.services.tenant_deletion import hard_delete_tenant

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_platform_tenant(
    tenant_id: int,
    confirm_slug: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_super_admin_console),
) -> Response:
    """Hard-delete a tenant, its data (DB cascades), exclusive firm users, and uploaded files."""
    tenant_row = db.get(Tenant, tenant_id)
    if tenant_row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant_pk = tenant_row.id
    if (confirm_slug or "").strip() != tenant_row.slug:
        raise HTTPException(status_code=400, detail="confirm_slug must match tenant.slug exactly")

    try:
        stats = hard_delete_tenant(db, tenant_pk)
        logger.info("Deleted tenant_id=%s stats=%s", tenant_pk, stats)
    except LookupError:
        db.rollback()
        raise HTTPException(status_code=404, detail="Tenant not found") from None
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant delete blocked by related records. Please contact support with server logs.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
