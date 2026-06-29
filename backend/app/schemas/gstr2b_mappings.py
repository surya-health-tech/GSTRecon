from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MasterFieldSummary(BaseModel):
    id: int
    field_name: str
    field_code: str
    is_required: bool
    display_order: int

    model_config = {"from_attributes": True}


class Gstr2bTabMappingOut(BaseModel):
    found: bool
    tab: str
    excel_sheet_name: str | None = None
    columns: list[str] = Field(default_factory=list)
    sample_row: dict[str, str] = Field(default_factory=dict)
    column_mappings: dict[str, str | None] = Field(default_factory=dict)
    auto_match_confidence: dict[str, str] = Field(default_factory=dict)


class Gstr2bParseResult(BaseModel):
    excel_sheets: list[str]
    tabs: dict[str, Gstr2bTabMappingOut]
    master_fields: list[MasterFieldSummary]


class Gstr2bMappingListItem(BaseModel):
    id: int
    mapping_name: str
    version: str
    is_active: bool
    original_filename: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Gstr2bMappingOut(BaseModel):
    id: int
    mapping_name: str
    version: str
    is_active: bool
    original_filename: str | None
    sheet_mappings: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Gstr2bMappingUpdate(BaseModel):
    mapping_name: str | None = Field(default=None, min_length=1, max_length=255)
    version: str | None = Field(default=None, min_length=1, max_length=64)
    sheet_mappings: dict[str, Any] | None = None
