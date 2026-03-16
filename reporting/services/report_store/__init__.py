import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
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


def initialize() -> None:
    get_store().initialize()


def list_reports() -> List[ReportListItem]:
    return get_store().list_reports()


def get_report_latest(report_id: str) -> Optional[ReportVersion]:
    return get_store().get_report_latest(report_id)


def get_report_version(report_id: str, version: int) -> Optional[ReportVersion]:
    return get_store().get_report_version(report_id, version)


def list_report_versions(report_id: str) -> List[ReportVersion]:
    return get_store().list_report_versions(report_id)


def create_report(
    config: Dict[str, Any],
    created_by: str,
    comment: Optional[str] = None,
) -> ReportVersion:
    return get_store().create_report(
        config=config,
        created_by=created_by,
        comment=comment,
    )


def save_report_version(
    report_id: str,
    config: Dict[str, Any],
    created_by: str,
    comment: Optional[str] = None,
) -> Optional[ReportVersion]:
    return get_store().save_report_version(
        report_id=report_id,
        config=config,
        created_by=created_by,
        comment=comment,
    )


def get_dashboard_report_id() -> Optional[str]:
    return get_store().get_dashboard_report_id()


def set_dashboard_report(report_id: str) -> bool:
    return get_store().set_dashboard_report(report_id)


def get_dashboard_report() -> Optional[ReportVersion]:
    return get_store().get_dashboard_report()
