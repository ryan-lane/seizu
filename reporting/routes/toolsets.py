import logging
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from reporting.authnz import CurrentUser
from reporting.authnz import require_permission
from reporting.authnz.permissions import Permission
from reporting.routes.query import _serialize_neo4j_value
from reporting.schema.mcp_config import CallToolRequest
from reporting.schema.mcp_config import CallToolResponse
from reporting.schema.mcp_config import CreateToolRequest
from reporting.schema.mcp_config import CreateToolsetRequest
from reporting.schema.mcp_config import ToolIdResponse
from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolListResponse
from reporting.schema.mcp_config import ToolsetIdResponse
from reporting.schema.mcp_config import ToolsetListItem
from reporting.schema.mcp_config import ToolsetListResponse
from reporting.schema.mcp_config import ToolsetVersion
from reporting.schema.mcp_config import ToolsetVersionListResponse
from reporting.schema.mcp_config import ToolVersion
from reporting.schema.mcp_config import ToolVersionListResponse
from reporting.schema.mcp_config import UpdateToolRequest
from reporting.schema.mcp_config import UpdateToolsetRequest
from reporting.schema.mcp_config import validate_tool_arguments
from reporting.services import report_store
from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Toolsets
# ---------------------------------------------------------------------------


@router.get("/api/v1/toolsets", response_model=ToolsetListResponse)
async def list_toolsets(
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_READ)),
) -> ToolsetListResponse:
    """List all toolsets."""
    return ToolsetListResponse(toolsets=await report_store.list_toolsets())


@router.post("/api/v1/toolsets", response_model=ToolsetListItem, status_code=201)
async def create_toolset(
    body: CreateToolsetRequest,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_WRITE)),
) -> ToolsetListItem:
    """Create a new toolset."""
    return await report_store.create_toolset(
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        created_by=current.user.user_id,
    )


@router.get("/api/v1/toolsets/{toolset_id}", response_model=ToolsetListItem)
async def get_toolset(
    toolset_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_READ)),
) -> ToolsetListItem:
    """Return a toolset by ID."""
    item = await report_store.get_toolset(toolset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Toolset not found")
    return item


@router.put("/api/v1/toolsets/{toolset_id}", response_model=ToolsetListItem)
async def update_toolset(
    toolset_id: str,
    body: UpdateToolsetRequest,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_WRITE)),
) -> Any:
    """Update a toolset (creates a new version)."""
    item = await report_store.update_toolset(
        toolset_id=toolset_id,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        updated_by=current.user.user_id,
        comment=body.comment,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Toolset not found")
    return item


@router.delete("/api/v1/toolsets/{toolset_id}", response_model=ToolsetIdResponse)
async def delete_toolset(
    toolset_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_DELETE)),
) -> ToolsetIdResponse:
    """Delete a toolset and all its tools."""
    ok = await report_store.delete_toolset(toolset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Toolset not found")
    return ToolsetIdResponse(toolset_id=toolset_id)


@router.get(
    "/api/v1/toolsets/{toolset_id}/versions",
    response_model=ToolsetVersionListResponse,
)
async def list_toolset_versions(
    toolset_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_READ)),
) -> ToolsetVersionListResponse:
    """List all versions of a toolset."""
    item = await report_store.get_toolset(toolset_id)
    if not item:
        raise HTTPException(status_code=404, detail="Toolset not found")
    versions = await report_store.list_toolset_versions(toolset_id)
    return ToolsetVersionListResponse(versions=versions)


@router.get(
    "/api/v1/toolsets/{toolset_id}/versions/{version}",
    response_model=ToolsetVersion,
)
async def get_toolset_version(
    toolset_id: str,
    version: int,
    current: CurrentUser = Depends(require_permission(Permission.TOOLSETS_READ)),
) -> ToolsetVersion:
    """Return a specific version of a toolset."""
    v = await report_store.get_toolset_version(toolset_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Toolset version not found")
    return v


# ---------------------------------------------------------------------------
# Tools (nested under toolsets)
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/toolsets/{toolset_id}/tools",
    response_model=ToolListResponse,
)
async def list_tools(
    toolset_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_READ)),
) -> ToolListResponse:
    """List all tools in a toolset."""
    ts = await report_store.get_toolset(toolset_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Toolset not found")
    return ToolListResponse(tools=await report_store.list_tools(toolset_id))


@router.post(
    "/api/v1/toolsets/{toolset_id}/tools",
    response_model=ToolItem,
    status_code=201,
)
async def create_tool(
    toolset_id: str,
    body: CreateToolRequest,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_WRITE)),
) -> Any:
    """Create a new tool within a toolset."""
    validation = await validate_query(body.cypher)
    if validation.has_errors:
        return JSONResponse(
            content={
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
            status_code=400,
        )
    tool = await report_store.create_tool(
        toolset_id=toolset_id,
        name=body.name,
        description=body.description,
        cypher=body.cypher,
        parameters=[p.model_dump() for p in body.parameters],
        enabled=body.enabled,
        created_by=current.user.user_id,
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Toolset not found")
    return tool


@router.get(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}",
    response_model=ToolItem,
)
async def get_tool(
    toolset_id: str,
    tool_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_READ)),
) -> ToolItem:
    """Return a tool by ID."""
    tool = await report_store.get_tool(tool_id)
    if not tool or tool.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}",
    response_model=ToolItem,
)
async def update_tool(
    toolset_id: str,
    tool_id: str,
    body: UpdateToolRequest,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_WRITE)),
) -> Any:
    """Update a tool (creates a new version)."""
    existing = await report_store.get_tool(tool_id)
    if not existing or existing.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool not found")
    validation = await validate_query(body.cypher)
    if validation.has_errors:
        return JSONResponse(
            content={
                "errors": validation.errors,
                "warnings": validation.warnings,
            },
            status_code=400,
        )
    tool = await report_store.update_tool(
        tool_id=tool_id,
        name=body.name,
        description=body.description,
        cypher=body.cypher,
        parameters=[p.model_dump() for p in body.parameters],
        enabled=body.enabled,
        updated_by=current.user.user_id,
        comment=body.comment,
    )
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.delete(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}",
    response_model=ToolIdResponse,
)
async def delete_tool(
    toolset_id: str,
    tool_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_DELETE)),
) -> ToolIdResponse:
    """Delete a tool."""
    existing = await report_store.get_tool(tool_id)
    if not existing or existing.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool not found")
    ok = await report_store.delete_tool(tool_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ToolIdResponse(tool_id=tool_id)


@router.post(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}/call",
    response_model=CallToolResponse,
)
async def call_tool(
    toolset_id: str,
    tool_id: str,
    body: CallToolRequest,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_CALL)),
) -> Any:
    """Execute a tool's Cypher query with the provided arguments."""
    tool = await report_store.get_tool(tool_id)
    if not tool or tool.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool not found")
    if not tool.enabled:
        raise HTTPException(status_code=400, detail="Tool is disabled")
    errors = validate_tool_arguments(tool.parameters, body.arguments)
    if errors:
        return JSONResponse(content={"errors": errors}, status_code=400)
    try:
        results = await reporting_neo4j.run_query(
            tool.cypher, parameters=body.arguments
        )
        serialized = [
            {key: _serialize_neo4j_value(value) for key, value in record.items()}
            for record in results
        ]
        return CallToolResponse(results=serialized)
    except Exception:
        logger.exception("Tool execution failed: %s", tool_id)
        raise HTTPException(status_code=500, detail="Tool execution failed")


@router.get(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions",
    response_model=ToolVersionListResponse,
)
async def list_tool_versions(
    toolset_id: str,
    tool_id: str,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_READ)),
) -> ToolVersionListResponse:
    """List all versions of a tool."""
    tool = await report_store.get_tool(tool_id)
    if not tool or tool.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool not found")
    versions = await report_store.list_tool_versions(tool_id)
    return ToolVersionListResponse(versions=versions)


@router.get(
    "/api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions/{version}",
    response_model=ToolVersion,
)
async def get_tool_version(
    toolset_id: str,
    tool_id: str,
    version: int,
    current: CurrentUser = Depends(require_permission(Permission.TOOLS_READ)),
) -> ToolVersion:
    """Return a specific version of a tool."""
    v = await report_store.get_tool_version(tool_id, version)
    if not v or v.toolset_id != toolset_id:
        raise HTTPException(status_code=404, detail="Tool version not found")
    return v
