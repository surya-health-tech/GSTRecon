from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.purchase_register_mappings import REGISTER_SOURCES


class MasterFieldSummary(BaseModel):
    id: int
    field_name: str
    field_code: str
    is_required: bool
    display_order: int

    model_config = {"from_attributes": True}


class PurchaseRegisterMappingListItem(BaseModel):
    id: int
    mapping_name: str
    source: str
    original_filename: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PurchaseRegisterMappingOut(BaseModel):
    id: int
    mapping_name: str
    source: str
    sheet_name: str | None
    original_filename: str | None
    excel_columns: list[str]
    sample_row: dict[str, str]
    column_mappings: dict[str, str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExcelParseResult(BaseModel):
    sheets: list[str]
    sheet_name: str
    columns: list[str]
    sample_row: dict[str, str]
    master_fields: list[MasterFieldSummary]
    suggested_mappings: dict[str, str | None]
    auto_match_confidence: dict[str, str]


class PurchaseRegisterMappingUpdate(BaseModel):
    mapping_name: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = None
    sheet_name: str | None = None
    column_mappings: dict[str, str] | None = None
    excel_columns: list[str] | None = None
    sample_row: dict[str, str] | None = None

    @field_validator("source")
    @classmethod
    def check_source(cls, v: str | None) -> str | None:
        if v is not None and v not in REGISTER_SOURCES:
            raise ValueError("Invalid purchase register source")
        return v
