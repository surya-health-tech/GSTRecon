from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReconciliationCaseCreate(BaseModel):
    case_name: str
    tax_period_month: int = Field(ge=1, le=12)
    tax_period_year: int = Field(ge=2000, le=2100)
    client_id: int | None = None
    pr_mapping_id: int | None = None


class ReconciliationCaseUpdate(BaseModel):
    case_name: str | None = None
    tax_period_month: int | None = Field(default=None, ge=1, le=12)
    tax_period_year: int | None = Field(default=None, ge=2000, le=2100)
    client_id: int | None = None
    pr_mapping_id: int | None = None


class ReconciliationCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_name: str
    client_id: int | None
    client_name: str | None = None
    tax_period_month: int
    tax_period_year: int
    status: str
    gstr2b_original_filename: str | None
    pr_original_filename: str | None
    gstr2b_mapping_id: int | None
    pr_mapping_id: int | None
    gstr2b_mapping_name: str | None
    pr_mapping_name: str | None
    summary_counts: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ReconciliationCaseRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    match_status: str | None
    remarks: str | None
    portal_data: dict | None
    book_data: dict | None
    normalized: dict


class ProcessContextOut(BaseModel):
    active_gstr2b_mapping: dict | None
    purchase_register_mappings: list[dict]
    suggested_pr_mapping_id: int | None
    client_purchase_system_type: str | None


class ReconciliationCaseDetailOut(ReconciliationCaseOut):
    process_context: ProcessContextOut | None = None
