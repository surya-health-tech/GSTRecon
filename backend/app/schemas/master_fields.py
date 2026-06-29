from pydantic import BaseModel, Field, field_validator

from app.services.master_fields import APPLICABLE_SOURCES, DATA_TYPES, field_name_to_code


class MasterFieldOut(BaseModel):
    id: int
    field_name: str
    field_code: str
    data_type: str
    is_required: bool
    applicable_source: str
    is_system: bool
    is_active: bool
    display_order: int

    model_config = {"from_attributes": True}


class MasterFieldCreate(BaseModel):
    field_name: str = Field(min_length=1, max_length=255)
    field_code: str | None = Field(default=None, max_length=80)
    data_type: str
    is_required: bool = True
    applicable_source: str
    is_active: bool = True
    display_order: int = Field(default=0, ge=0)

    @field_validator("data_type")
    @classmethod
    def check_data_type(cls, v: str) -> str:
        if v not in DATA_TYPES:
            raise ValueError("Invalid data type")
        return v

    @field_validator("applicable_source")
    @classmethod
    def check_source(cls, v: str) -> str:
        if v not in APPLICABLE_SOURCES:
            raise ValueError("Invalid applicable source")
        return v

    def resolved_field_code(self) -> str:
        if self.field_code and self.field_code.strip():
            return self.field_code.strip().lower()
        return field_name_to_code(self.field_name)


class MasterFieldUpdate(BaseModel):
    field_name: str | None = Field(default=None, min_length=1, max_length=255)
    field_code: str | None = Field(default=None, max_length=80)
    data_type: str | None = None
    is_required: bool | None = None
    applicable_source: str | None = None
    is_active: bool | None = None
    display_order: int | None = Field(default=None, ge=0)

    @field_validator("data_type")
    @classmethod
    def check_data_type(cls, v: str | None) -> str | None:
        if v is not None and v not in DATA_TYPES:
            raise ValueError("Invalid data type")
        return v

    @field_validator("applicable_source")
    @classmethod
    def check_source(cls, v: str | None) -> str | None:
        if v is not None and v not in APPLICABLE_SOURCES:
            raise ValueError("Invalid applicable source")
        return v
