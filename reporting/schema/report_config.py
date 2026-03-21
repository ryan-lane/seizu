from decimal import Decimal
from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import field_validator


def _coerce_decimal(value: Any) -> Any:
    """Recursively convert Decimal to int/float.

    DynamoDB's boto3 resource returns all numbers as Decimal; this normalises
    them back to native Python int/float so Pydantic models can validate them
    without needing to know about Decimal.
    """
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _coerce_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_decimal(v) for v in value]
    return value


class ReportListItem(BaseModel):
    """Lightweight summary of a report for list views."""

    report_id: str
    name: str
    current_version: int
    created_at: str
    updated_at: str

    @field_validator("current_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return v


class ReportVersion(BaseModel):
    """A single versioned report config."""

    report_id: str
    name: str
    version: int
    config: Dict[str, Any]
    created_at: str
    created_by: str
    comment: Optional[str] = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return v

    @field_validator("config", mode="before")
    @classmethod
    def coerce_config(cls, v: Any) -> Dict[str, Any]:
        return _coerce_decimal(v)


class CreateReportRequest(BaseModel):
    """Request body for POST /api/v1/reports."""

    name: str


class CreateVersionRequest(BaseModel):
    """Request body for POST /api/v1/reports/<id>/versions."""

    config: Dict[str, Any]
    comment: Optional[str] = None


class User(BaseModel):
    """A user record, created on first login (JIT provisioning)."""

    user_id: str
    sub: str
    iss: str
    email: str
    display_name: Optional[str] = None
    created_at: str
    last_login: str
    archived_at: Optional[str] = None
