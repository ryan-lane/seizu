"""Pydantic models for RBAC roles."""
from decimal import Decimal
from typing import Any
from typing import List
from typing import Optional

from pydantic import BaseModel
from pydantic import field_validator


def _coerce_decimal(value: Any) -> Any:
    """Recursively convert Decimal to int/float."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _coerce_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_decimal(v) for v in value]
    return value


class RoleItem(BaseModel):
    """A user-defined role stored in the database."""

    role_id: str
    name: str
    description: str = ""
    permissions: List[str] = []
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None

    @field_validator("current_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v) if v is not None else 0


class RoleVersion(BaseModel):
    """A single version snapshot of a user-defined role."""

    role_id: str
    name: str
    description: str = ""
    permissions: List[str] = []
    version: int
    created_at: str
    created_by: str
    comment: Optional[str] = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v) if v is not None else 0


class RoleListResponse(BaseModel):
    roles: List[RoleItem]


class RoleVersionListResponse(BaseModel):
    versions: List[RoleVersion]


class RoleIdResponse(BaseModel):
    role_id: str


class CreateRoleRequest(BaseModel):
    name: str
    description: str = ""
    permissions: List[str]
    comment: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    name: str
    description: str = ""
    permissions: List[str]
    comment: Optional[str] = None
