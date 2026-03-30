import logging
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolsetListItem
from reporting.schema.mcp_config import ToolsetVersion
from reporting.schema.mcp_config import ToolVersion
from reporting.schema.rbac import RoleItem
from reporting.schema.rbac import RoleVersion
from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import QueryHistoryItem
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.report_config import ScheduledQueryVersion
from reporting.schema.report_config import User
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

_store: Optional[ReportStore] = None


def get_store() -> ReportStore:
    """Return the configured report store singleton.

    The backend is selected by the REPORT_STORE_BACKEND setting (default: ``dynamodb``).
    """
    global _store
    if _store is None:
        from reporting import settings

        backend = settings.REPORT_STORE_BACKEND
        if backend == "dynamodb":
            from reporting.services.report_store.dynamodb import DynamoDBReportStore

            _store = DynamoDBReportStore()
        elif backend == "sqlmodel":
            from reporting.services.report_store.sql import SQLModelReportStore

            _store = SQLModelReportStore()
        else:
            raise ValueError(f"Unknown report store backend: {backend!r}")
    return _store


# ---------------------------------------------------------------------------
# Module-level convenience functions — delegate to the configured store so
# callers can use ``report_store.list_reports()`` without calling get_store().
# ---------------------------------------------------------------------------


async def initialize() -> None:
    await get_store().initialize()


async def list_reports() -> List[ReportListItem]:
    return await get_store().list_reports()


async def get_report_latest(report_id: str) -> Optional[ReportVersion]:
    return await get_store().get_report_latest(report_id)


async def get_report_version(report_id: str, version: int) -> Optional[ReportVersion]:
    return await get_store().get_report_version(report_id, version)


async def list_report_versions(report_id: str) -> List[ReportVersion]:
    return await get_store().list_report_versions(report_id)


async def create_report(
    name: str,
    created_by: str,
) -> ReportListItem:
    return await get_store().create_report(
        name=name,
        created_by=created_by,
    )


async def save_report_version(
    report_id: str,
    config: Dict[str, Any],
    created_by: str,
    comment: Optional[str] = None,
) -> Optional[ReportVersion]:
    return await get_store().save_report_version(
        report_id=report_id,
        config=config,
        created_by=created_by,
        comment=comment,
    )


async def delete_report(report_id: str) -> bool:
    return await get_store().delete_report(report_id)


async def get_dashboard_report_id() -> Optional[str]:
    return await get_store().get_dashboard_report_id()


async def set_dashboard_report(report_id: str) -> bool:
    return await get_store().set_dashboard_report(report_id)


async def get_dashboard_report() -> Optional[ReportVersion]:
    return await get_store().get_dashboard_report()


async def get_or_create_user(
    sub: str,
    iss: str,
    email: str,
    display_name: Optional[str] = None,
) -> User:
    return await get_store().get_or_create_user(
        sub=sub,
        iss=iss,
        email=email,
        display_name=display_name,
    )


async def update_user_profile(
    user_id: str,
    email: str,
    display_name: Optional[str] = None,
    token_iat: Optional[datetime] = None,
) -> User:
    return await get_store().update_user_profile(
        user_id=user_id,
        email=email,
        display_name=display_name,
        token_iat=token_iat,
    )


async def get_user(user_id: str) -> Optional[User]:
    return await get_store().get_user(user_id)


async def archive_user(user_id: str) -> bool:
    return await get_store().archive_user(user_id)


async def list_panel_stats() -> List[PanelStat]:
    return await get_store().list_panel_stats()


async def list_scheduled_queries() -> List[ScheduledQueryItem]:
    return await get_store().list_scheduled_queries()


async def get_scheduled_query(sq_id: str) -> Optional[ScheduledQueryItem]:
    return await get_store().get_scheduled_query(sq_id)


async def create_scheduled_query(
    name: str,
    cypher: str,
    params: List[Dict[str, Any]],
    frequency: Optional[int],
    watch_scans: List[Dict[str, Any]],
    enabled: bool,
    actions: List[Dict[str, Any]],
    created_by: str,
) -> ScheduledQueryItem:
    return await get_store().create_scheduled_query(
        name=name,
        cypher=cypher,
        params=params,
        frequency=frequency,
        watch_scans=watch_scans,
        enabled=enabled,
        actions=actions,
        created_by=created_by,
    )


async def update_scheduled_query(
    sq_id: str,
    name: str,
    cypher: str,
    params: List[Dict[str, Any]],
    frequency: Optional[int],
    watch_scans: List[Dict[str, Any]],
    enabled: bool,
    actions: List[Dict[str, Any]],
    updated_by: str,
    comment: Optional[str] = None,
) -> Optional[ScheduledQueryItem]:
    return await get_store().update_scheduled_query(
        sq_id=sq_id,
        name=name,
        cypher=cypher,
        params=params,
        frequency=frequency,
        watch_scans=watch_scans,
        enabled=enabled,
        actions=actions,
        updated_by=updated_by,
        comment=comment,
    )


async def delete_scheduled_query(sq_id: str) -> bool:
    return await get_store().delete_scheduled_query(sq_id)


async def list_scheduled_query_versions(sq_id: str) -> List[ScheduledQueryVersion]:
    return await get_store().list_scheduled_query_versions(sq_id)


async def get_scheduled_query_version(
    sq_id: str, version: int
) -> Optional[ScheduledQueryVersion]:
    return await get_store().get_scheduled_query_version(sq_id, version)


# ---------------------------------------------------------------------------
# Toolset convenience functions
# ---------------------------------------------------------------------------


async def list_toolsets() -> List[ToolsetListItem]:
    return await get_store().list_toolsets()


async def get_toolset(toolset_id: str) -> Optional[ToolsetListItem]:
    return await get_store().get_toolset(toolset_id)


async def create_toolset(
    name: str,
    description: str,
    enabled: bool,
    created_by: str,
) -> ToolsetListItem:
    return await get_store().create_toolset(
        name=name,
        description=description,
        enabled=enabled,
        created_by=created_by,
    )


async def update_toolset(
    toolset_id: str,
    name: str,
    description: str,
    enabled: bool,
    updated_by: str,
    comment: Optional[str] = None,
) -> Optional[ToolsetListItem]:
    return await get_store().update_toolset(
        toolset_id=toolset_id,
        name=name,
        description=description,
        enabled=enabled,
        updated_by=updated_by,
        comment=comment,
    )


async def delete_toolset(toolset_id: str) -> bool:
    return await get_store().delete_toolset(toolset_id)


async def list_toolset_versions(toolset_id: str) -> List[ToolsetVersion]:
    return await get_store().list_toolset_versions(toolset_id)


async def get_toolset_version(
    toolset_id: str, version: int
) -> Optional[ToolsetVersion]:
    return await get_store().get_toolset_version(toolset_id, version)


# ---------------------------------------------------------------------------
# Tool convenience functions
# ---------------------------------------------------------------------------


async def list_tools(toolset_id: str) -> List[ToolItem]:
    return await get_store().list_tools(toolset_id)


async def get_tool(tool_id: str) -> Optional[ToolItem]:
    return await get_store().get_tool(tool_id)


async def create_tool(
    toolset_id: str,
    name: str,
    description: str,
    cypher: str,
    parameters: List[Dict[str, Any]],
    enabled: bool,
    created_by: str,
) -> Optional[ToolItem]:
    return await get_store().create_tool(
        toolset_id=toolset_id,
        name=name,
        description=description,
        cypher=cypher,
        parameters=parameters,
        enabled=enabled,
        created_by=created_by,
    )


async def update_tool(
    tool_id: str,
    name: str,
    description: str,
    cypher: str,
    parameters: List[Dict[str, Any]],
    enabled: bool,
    updated_by: str,
    comment: Optional[str] = None,
) -> Optional[ToolItem]:
    return await get_store().update_tool(
        tool_id=tool_id,
        name=name,
        description=description,
        cypher=cypher,
        parameters=parameters,
        enabled=enabled,
        updated_by=updated_by,
        comment=comment,
    )


async def delete_tool(tool_id: str) -> bool:
    return await get_store().delete_tool(tool_id)


async def list_tool_versions(tool_id: str) -> List[ToolVersion]:
    return await get_store().list_tool_versions(tool_id)


async def get_tool_version(tool_id: str, version: int) -> Optional[ToolVersion]:
    return await get_store().get_tool_version(tool_id, version)


async def list_enabled_tools() -> List[ToolItem]:
    return await get_store().list_enabled_tools()


# ---------------------------------------------------------------------------
# Query history convenience functions
# ---------------------------------------------------------------------------


async def save_query_history(user_id: str, query: str) -> QueryHistoryItem:
    return await get_store().save_query_history(user_id=user_id, query=query)


async def list_query_history(
    user_id: str, page: int, per_page: int
) -> tuple[List[QueryHistoryItem], int]:
    return await get_store().list_query_history(
        user_id=user_id, page=page, per_page=per_page
    )


# ---------------------------------------------------------------------------
# Role convenience functions
# ---------------------------------------------------------------------------


async def list_roles() -> List[RoleItem]:
    return await get_store().list_roles()


async def get_role(role_id: str) -> Optional[RoleItem]:
    return await get_store().get_role(role_id)


async def get_role_by_name(name: str) -> Optional[RoleItem]:
    return await get_store().get_role_by_name(name)


async def create_role(
    name: str,
    description: str,
    permissions: List[str],
    created_by: str,
) -> RoleItem:
    return await get_store().create_role(
        name=name,
        description=description,
        permissions=permissions,
        created_by=created_by,
    )


async def update_role(
    role_id: str,
    name: str,
    description: str,
    permissions: List[str],
    updated_by: str,
    comment: Optional[str] = None,
) -> Optional[RoleItem]:
    return await get_store().update_role(
        role_id=role_id,
        name=name,
        description=description,
        permissions=permissions,
        updated_by=updated_by,
        comment=comment,
    )


async def delete_role(role_id: str) -> bool:
    return await get_store().delete_role(role_id)


async def list_role_versions(role_id: str) -> List[RoleVersion]:
    return await get_store().list_role_versions(role_id)


async def get_role_version(role_id: str, version: int) -> Optional[RoleVersion]:
    return await get_store().get_role_version(role_id, version)
