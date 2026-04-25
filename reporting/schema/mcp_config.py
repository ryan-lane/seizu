from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def _coerce_decimal(value: Any) -> Any:
    """Recursively convert Decimal to int/float."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {k: _coerce_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce_decimal(v) for v in value]
    return value


class ToolParamDef(BaseModel):
    """Definition of a single parameter accepted by an MCP tool."""

    name: str
    type: Literal["string", "integer", "float", "boolean"]
    description: str = ""
    required: bool = True
    default: Any | None = None


class ToolsetListItem(BaseModel):
    """Lightweight summary of a toolset for list views."""

    toolset_id: str
    name: str
    description: str = ""
    enabled: bool = True
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str | None = None

    @field_validator("current_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v) if v is not None else 0


class ToolsetVersion(BaseModel):
    """A point-in-time snapshot of a toolset's metadata."""

    toolset_id: str
    name: str
    description: str = ""
    enabled: bool = True
    version: int
    created_at: str
    created_by: str
    comment: str | None = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v)


class ToolItem(BaseModel):
    """A tool record stored in the database."""

    tool_id: str
    toolset_id: str
    name: str
    description: str = ""
    cypher: str
    parameters: list[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: str | None = None

    @field_validator("current_version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v) if v is not None else 0

    @field_validator("parameters", mode="before")
    @classmethod
    def coerce_parameters(cls, v: Any) -> list[dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class ToolVersion(BaseModel):
    """A point-in-time snapshot of a tool's configuration."""

    tool_id: str
    toolset_id: str
    name: str
    description: str = ""
    cypher: str
    parameters: list[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
    version: int
    created_at: str
    created_by: str
    comment: str | None = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v)

    @field_validator("parameters", mode="before")
    @classmethod
    def coerce_parameters(cls, v: Any) -> list[dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class ToolsetListResponse(BaseModel):
    toolsets: list[ToolsetListItem]


class ToolsetVersionListResponse(BaseModel):
    versions: list[ToolsetVersion]


class ToolsetIdResponse(BaseModel):
    toolset_id: str


class ToolListResponse(BaseModel):
    tools: list[ToolItem]


class ToolVersionListResponse(BaseModel):
    versions: list[ToolVersion]


class ToolIdResponse(BaseModel):
    tool_id: str


def validate_tool_arguments(parameters: list["ToolParamDef"], arguments: dict[str, Any]) -> list[str]:
    """Validate *arguments* against the tool's parameter definitions.

    Returns a list of error strings; empty means the arguments are valid.
    Checks:
    - All required parameters (with no default) are present.
    - Each supplied value is the correct type.
    """
    errors: list[str] = []
    _TYPE_CHECK: dict[str, type] = {
        "string": str,
        "boolean": bool,
    }
    for param in parameters:
        value = arguments.get(param.name)
        if value is None:
            if param.required and param.default is None:
                errors.append(f"Required parameter '{param.name}' is missing")
            continue
        if param.type in _TYPE_CHECK:
            expected = _TYPE_CHECK[param.type]
            if not isinstance(value, expected):
                errors.append(f"Parameter '{param.name}' must be a {param.type}, got {type(value).__name__}")
        elif param.type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(f"Parameter '{param.name}' must be an integer, got {type(value).__name__}")
        elif param.type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"Parameter '{param.name}' must be a number, got {type(value).__name__}")
    return errors


class CallToolRequest(BaseModel):
    """Request body for POST /api/v1/toolsets/<id>/tools/<id>/call."""

    arguments: dict[str, Any] = Field(default_factory=dict)


class CallToolResponse(BaseModel):
    """Response returned by a tool call."""

    results: list[Any]


class CreateToolsetRequest(BaseModel):
    """Request body for POST /api/v1/toolsets."""

    name: str
    description: str = ""
    enabled: bool = True


class UpdateToolsetRequest(BaseModel):
    """Request body for PUT /api/v1/toolsets/<id>."""

    name: str
    description: str = ""
    enabled: bool = True
    comment: str | None = None


class CreateToolRequest(BaseModel):
    """Request body for POST /api/v1/toolsets/<id>/tools."""

    name: str
    description: str = ""
    cypher: str
    parameters: list[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True


class UpdateToolRequest(BaseModel):
    """Request body for PUT /api/v1/toolsets/<id>/tools/<id>."""

    name: str
    description: str = ""
    cypher: str
    parameters: list[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
    comment: str | None = None
