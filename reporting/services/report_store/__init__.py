import logging
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting.schema.report_config import PanelStat
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
