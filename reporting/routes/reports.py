import logging
from typing import Any

from apiflask import abort
from apiflask import APIBlueprint
from flask import g

from reporting import authnz  # noqa: F401
from reporting.authnz import bearer_auth
from reporting.schema.report_config import CreateReportRequest
from reporting.schema.report_config import CreateVersionRequest
from reporting.schema.report_config import ReportIdResponse
from reporting.schema.report_config import ReportListResponse
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import ReportVersionListResponse
from reporting.services import report_store

logger = logging.getLogger(__name__)
blueprint = APIBlueprint("reports", __name__)


@blueprint.get("/api/v1/reports")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportListResponse)
def list_reports() -> ReportListResponse:
    """List all reports."""
    return ReportListResponse(reports=report_store.list_reports())


@blueprint.get("/api/v1/reports/dashboard")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportVersion)
def get_dashboard_report() -> ReportVersion:
    """Return the latest version of the dashboard report."""
    report = report_store.get_dashboard_report()
    if not report:
        abort(404, message="No dashboard report configured")
    return report


@blueprint.put("/api/v1/reports/<report_id>/dashboard")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportIdResponse)
def set_dashboard_report(report_id: str) -> ReportIdResponse:
    """Set a report as the default dashboard."""
    ok = report_store.set_dashboard_report(report_id)
    if not ok:
        abort(404, message="Report not found")
    return ReportIdResponse(report_id=report_id)


@blueprint.get("/api/v1/reports/<report_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportVersion)
def get_report(report_id: str) -> ReportVersion:
    """Return the latest version of a report."""
    report = report_store.get_report_latest(report_id)
    if not report:
        abort(404, message="Report not found")
    return report


@blueprint.get("/api/v1/reports/<report_id>/versions")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportVersionListResponse)
def list_versions(report_id: str) -> ReportVersionListResponse:
    """List all versions of a report."""
    versions = report_store.list_report_versions(report_id)
    if not versions:
        abort(404, message="Report not found")
    return ReportVersionListResponse(versions=versions)


@blueprint.get("/api/v1/reports/<report_id>/versions/<int:version_num>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportVersion)
def get_version(report_id: str, version_num: int) -> ReportVersion:
    """Return a specific version of a report."""
    version = report_store.get_report_version(report_id, version_num)
    if not version:
        abort(404, message="Version not found")
    return version


@blueprint.delete("/api/v1/reports/<report_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ReportIdResponse)
def delete_report(report_id: str) -> ReportIdResponse:
    """Delete a report and all its versions."""
    ok = report_store.delete_report(report_id)
    if not ok:
        abort(404, message="Report not found")
    return ReportIdResponse(report_id=report_id)


@blueprint.post("/api/v1/reports")
@blueprint.auth_required(bearer_auth)
@blueprint.input(CreateReportRequest, arg_name="body")
@blueprint.output(ReportVersion, status_code=201)
def create_report(body: CreateReportRequest) -> Any:
    """Create a new report."""
    return report_store.create_report(
        name=body.name,
        created_by=g.current_user.user_id,
    )


@blueprint.post("/api/v1/reports/<report_id>/versions")
@blueprint.auth_required(bearer_auth)
@blueprint.input(CreateVersionRequest, arg_name="body")
@blueprint.output(ReportVersion, status_code=201)
def create_version(report_id: str, body: CreateVersionRequest) -> Any:
    """Save a new version of a report."""
    version = report_store.save_report_version(
        report_id=report_id,
        config=body.config,
        created_by=g.current_user.user_id,
        comment=body.comment,
    )
    if not version:
        abort(404, message="Report not found")
    return version
