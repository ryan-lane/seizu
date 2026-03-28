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
    default: Optional[Any] = None


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
    updated_by: Optional[str] = None

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
    comment: Optional[str] = None

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
    parameters: List[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
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

    @field_validator("parameters", mode="before")
    @classmethod
    def coerce_parameters(cls, v: Any) -> List[Dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class ToolVersion(BaseModel):
    """A point-in-time snapshot of a tool's configuration."""

    tool_id: str
    toolset_id: str
    name: str
    description: str = ""
    cypher: str
    parameters: List[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
    version: int
    created_at: str
    created_by: str
    comment: Optional[str] = None

    @field_validator("version", mode="before")
    @classmethod
    def coerce_version(cls, v: Any) -> int:
        if isinstance(v, Decimal):
            return int(v)
        return int(v)

    @field_validator("parameters", mode="before")
    @classmethod
    def coerce_parameters(cls, v: Any) -> List[Dict[str, Any]]:
        return _coerce_decimal(v) if v is not None else []


class ToolsetListResponse(BaseModel):
    toolsets: List[ToolsetListItem]


class ToolsetVersionListResponse(BaseModel):
    versions: List[ToolsetVersion]


class ToolsetIdResponse(BaseModel):
    toolset_id: str


class ToolListResponse(BaseModel):
    tools: List[ToolItem]


class ToolVersionListResponse(BaseModel):
    versions: List[ToolVersion]


class ToolIdResponse(BaseModel):
    tool_id: str


def validate_tool_arguments(
    parameters: List["ToolParamDef"], arguments: Dict[str, Any]
) -> List[str]:
    """Validate *arguments* against the tool's parameter definitions.

    Returns a list of error strings; empty means the arguments are valid.
    Checks:
    - All required parameters (with no default) are present.
    - Each supplied value is the correct type.
    """
    errors: List[str] = []
    _TYPE_CHECK: Dict[str, type] = {
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
                errors.append(
                    f"Parameter '{param.name}' must be a {param.type}, "
                    f"got {type(value).__name__}"
                )
        elif param.type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                errors.append(
                    f"Parameter '{param.name}' must be an integer, "
                    f"got {type(value).__name__}"
                )
        elif param.type == "float":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(
                    f"Parameter '{param.name}' must be a number, "
                    f"got {type(value).__name__}"
                )
    return errors


class CallToolRequest(BaseModel):
    """Request body for POST /api/v1/toolsets/<id>/tools/<id>/call."""

    arguments: Dict[str, Any] = Field(default_factory=dict)


class CallToolResponse(BaseModel):
    """Response returned by a tool call."""

    results: List[Any]


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
    comment: Optional[str] = None


class CreateToolRequest(BaseModel):
    """Request body for POST /api/v1/toolsets/<id>/tools."""

    name: str
    description: str = ""
    cypher: str
    parameters: List[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True


class UpdateToolRequest(BaseModel):
    """Request body for PUT /api/v1/toolsets/<id>/tools/<id>."""

    name: str
    description: str = ""
    cypher: str
    parameters: List[ToolParamDef] = Field(default_factory=list)
    enabled: bool = True
    comment: Optional[str] = None
