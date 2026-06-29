"""Tenant-scoped client CRUD and validation."""

from __future__ import annotations

import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Client

PURCHASE_SYSTEM_TYPES = frozenset({"zoho", "wings_erp", "erpnext", "tally", "other"})

# 15-char GSTIN: 2 digits + 10 PAN chars + entity digit + Z + checksum
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def normalize_gst_number(value: str) -> str:
    return value.strip().upper()


def validate_gst_number(value: str) -> str:
    gst = normalize_gst_number(value)
    if len(gst) != 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GST Number must be exactly 15 characters",
        )
    if not GSTIN_RE.match(gst):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GST Number format. Expected a valid 15-character GSTIN.",
        )
    return gst


def validate_client_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client name is required")
    if len(cleaned) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client name is too long")
    return cleaned


def validate_purchase_system_type(value: str) -> str:
    v = value.strip().lower()
    if v not in PURCHASE_SYSTEM_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid purchase system type")
    return v


def get_client(db: Session, tenant_id: int, client_id: int) -> Client:
    row = (
        db.query(Client)
        .filter(Client.tenant_id == tenant_id, Client.id == client_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return row


def _duplicate_gst(
    db: Session, tenant_id: int, gst_number: str, exclude_id: int | None = None
) -> bool:
    q = db.query(Client).filter(
        Client.tenant_id == tenant_id,
        Client.gst_number == gst_number,
    )
    if exclude_id is not None:
        q = q.filter(Client.id != exclude_id)
    return q.first() is not None
