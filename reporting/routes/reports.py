import logging
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from reporting.authnz import CurrentUser
from reporting.authnz import require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import CreateReportRequest
from reporting.schema.report_config import CreateVersionRequest
from reporting.schema.report_config import ReportIdResponse
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportListResponse
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import ReportVersionListResponse
from reporting.services import report_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/v1/reports", response_model=ReportListResponse)
async def list_reports(
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> ReportListResponse:
    """List all reports."""
    return ReportListResponse(reports=await report_store.list_reports())


@router.get("/api/v1/reports/dashboard", response_model=ReportVersion)
async def get_dashboard_report(
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> ReportVersion:
    """Return the latest version of the dashboard report."""
    report = await report_store.get_dashboard_report()
    if not report:
        raise HTTPException(status_code=404, detail="No dashboard report configured")
    return report


@router.put("/api/v1/reports/{report_id}/dashboard", response_model=ReportIdResponse)
async def set_dashboard_report(
    report_id: str,
    current: CurrentUser = Depends(
        require_permission(Permission.REPORTS_SET_DASHBOARD)
    ),
) -> ReportIdResponse:
    """Set a report as the default dashboard."""
    ok = await report_store.set_dashboard_report(report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportIdResponse(report_id=report_id)


@router.get("/api/v1/reports/{report_id}", response_model=ReportVersion)
async def get_report(
    report_id: str,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> ReportVersion:
    """Return the latest version of a report."""
    report = await report_store.get_report_latest(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get(
    "/api/v1/reports/{report_id}/versions", response_model=ReportVersionListResponse
)
async def list_versions(
    report_id: str,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> ReportVersionListResponse:
    """List all versions of a report."""
    versions = await report_store.list_report_versions(report_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportVersionListResponse(versions=versions)


@router.get(
    "/api/v1/reports/{report_id}/versions/{version_num}",
    response_model=ReportVersion,
)
async def get_version(
    report_id: str,
    version_num: int,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> ReportVersion:
    """Return a specific version of a report."""
    version = await report_store.get_report_version(report_id, version_num)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.delete("/api/v1/reports/{report_id}", response_model=ReportIdResponse)
async def delete_report(
    report_id: str,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_DELETE)),
) -> ReportIdResponse:
    """Delete a report and all its versions."""
    ok = await report_store.delete_report(report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportIdResponse(report_id=report_id)


@router.post("/api/v1/reports", response_model=ReportListItem, status_code=201)
async def create_report(
    body: CreateReportRequest,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_WRITE)),
) -> Any:
    """Create a new report."""
    return await report_store.create_report(
        name=body.name,
        created_by=current.user.user_id,
    )


@router.post(
    "/api/v1/reports/{report_id}/versions",
    response_model=ReportVersion,
    status_code=201,
)
async def create_version(
    report_id: str,
    body: CreateVersionRequest,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_WRITE)),
) -> Any:
    """Save a new version of a report."""
    version = await report_store.save_report_version(
        report_id=report_id,
        config=body.config,
        created_by=current.user.user_id,
        comment=body.comment,
    )
    if not version:
        raise HTTPException(status_code=404, detail="Report not found")
    return version
