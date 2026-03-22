from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional

from pydantic import BaseModel
from pydantic import Field
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


class PanelStat(BaseModel):
    """Pre-computed stat descriptor extracted from a report panel.

    Written to the store on every ``save_report_version`` call so that
    ``dashboard_stats`` can fetch just the panels that require metric emission
    without loading every full report config on each loop.
    """

    report_id: str
    metric: str
    panel_type: str  # "count" or "progress"
    cypher: str  # resolved Cypher string (key already looked up against report.queries)
    static_params: Dict[str, Any] = Field(default_factory=dict)
    input_param_name: Optional[str] = None  # param name for the single input, if any
    input_cypher: Optional[str] = None  # Cypher that produces input values

    @field_validator("static_params", mode="before")
    @classmethod
    def coerce_static_params(cls, v: Any) -> Dict[str, Any]:
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


class ScheduledQueryItem(BaseModel):
    """A scheduled query record stored in the database."""

    scheduled_query_id: str
    name: str
    cypher: str
    params: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: Optional[int] = None
    watch_scans: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None

    @field_validator("current_version", mode="before")
    @classmethod
    def coerce_current_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v) if v is not None else 0

    @field_validator("params", "watch_scans", "actions", mode="before")
    @classmethod
    def coerce_json_fields(cls, v: Any) -> List[Dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class ScheduledQueryVersion(BaseModel):
    """A point-in-time snapshot of a scheduled query's configuration."""

    scheduled_query_id: str
    name: str
    version: int
    cypher: str
    params: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: Optional[int] = None
    watch_scans: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    created_by: str
    comment: Optional[str] = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v)

    @field_validator("params", "watch_scans", "actions", mode="before")
    @classmethod
    def coerce_json_fields(cls, v: Any) -> List[Dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class CreateScheduledQueryRequest(BaseModel):
    """Request body for POST/PUT /api/v1/scheduled-queries."""

    name: str
    cypher: str
    params: List[Dict[str, Any]] = Field(default_factory=list)
    frequency: Optional[int] = None
    watch_scans: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    comment: Optional[str] = None


class ActionConfigFieldDef(BaseModel):
    """Describes a single field in an action module's config schema."""

    name: str
    label: str
    type: Literal["string", "text", "number", "boolean", "string_list", "select"]
    required: bool = False
    description: Optional[str] = None
    default: Optional[Any] = None
    options: Optional[List[str]] = None
