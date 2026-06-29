from pydantic import BaseModel, Field


class RolePermissionsOut(BaseModel):
    roles: dict[str, dict[str, bool]] = Field(
        description="Map of role -> permission key -> enabled"
    )
    groups: dict[str, list[str]]


class RolePermissionsUpdate(BaseModel):
    roles: dict[str, dict[str, bool]]
