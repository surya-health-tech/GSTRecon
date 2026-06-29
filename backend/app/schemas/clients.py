from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.clients import GSTIN_RE, validate_purchase_system_type


class ClientOut(BaseModel):
    id: int
    client_name: str
    gst_number: str
    purchase_system_type: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=255)
    gst_number: str = Field(min_length=15, max_length=15)
    purchase_system_type: str

    @field_validator("client_name")
    @classmethod
    def check_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Client name is required")
        return cleaned

    @field_validator("gst_number")
    @classmethod
    def check_gst(cls, v: str) -> str:
        gst = v.strip().upper()
        if not GSTIN_RE.match(gst):
            raise ValueError("Invalid GST Number format. Expected a valid 15-character GSTIN.")
        return gst

    @field_validator("purchase_system_type")
    @classmethod
    def check_system(cls, v: str) -> str:
        return validate_purchase_system_type(v)


class ClientUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=255)
    gst_number: str | None = Field(default=None, min_length=15, max_length=15)
    purchase_system_type: str | None = None

    @field_validator("client_name")
    @classmethod
    def check_name(cls, v: str | None) -> str | None:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Client name is required")
            return cleaned
        return v

    @field_validator("gst_number")
    @classmethod
    def check_gst(cls, v: str | None) -> str | None:
        if v is not None:
            gst = v.strip().upper()
            if not GSTIN_RE.match(gst):
                raise ValueError("Invalid GST Number format. Expected a valid 15-character GSTIN.")
            return gst
        return v

    @field_validator("purchase_system_type")
    @classmethod
    def check_system(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_purchase_system_type(v)
        return v
