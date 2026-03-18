import logging

from flask import blueprints
from flask import jsonify
from flask import request
from flask import Response
from pydantic import ValidationError

from reporting import authnz
from reporting.schema.report_config import CreateReportRequest
from reporting.schema.report_config import CreateVersionRequest
from reporting.services import report_store

logger = logging.getLogger(__name__)
blueprint = blueprints.Blueprint("reports", __name__)


@blueprint.route("/api/v1/reports", methods=["GET"])
def list_reports() -> Response:
    authnz.get_email()
    reports = report_store.list_reports()
    return jsonify(reports=[r.model_dump() for r in reports])


@blueprint.route("/api/v1/reports/dashboard", methods=["GET"])
def get_dashboard_report() -> Response:
    authnz.get_email()
    report = report_store.get_dashboard_report()
    if not report:
        resp = jsonify(error="No dashboard report configured")
        resp.status_code = 404
        return resp
    return jsonify(report.model_dump())


@blueprint.route("/api/v1/reports/<report_id>/dashboard", methods=["PUT"])
def set_dashboard_report(report_id: str) -> Response:
    authnz.get_email()
    ok = report_store.set_dashboard_report(report_id)
    if not ok:
        resp = jsonify(error="Report not found")
        resp.status_code = 404
        return resp
    return jsonify(report_id=report_id)


@blueprint.route("/api/v1/reports/<report_id>", methods=["GET"])
def get_report(report_id: str) -> Response:
    authnz.get_email()
    report = report_store.get_report_latest(report_id)
    if not report:
        resp = jsonify(error="Report not found")
        resp.status_code = 404
        return resp
    return jsonify(report.model_dump())


@blueprint.route("/api/v1/reports/<report_id>/versions", methods=["GET"])
def list_versions(report_id: str) -> Response:
    authnz.get_email()
    versions = report_store.list_report_versions(report_id)
    if not versions:
        resp = jsonify(error="Report not found")
        resp.status_code = 404
        return resp
    return jsonify(versions=[v.model_dump() for v in versions])


@blueprint.route(
    "/api/v1/reports/<report_id>/versions/<int:version_num>", methods=["GET"]
)
def get_version(report_id: str, version_num: int) -> Response:
    authnz.get_email()
    version = report_store.get_report_version(report_id, version_num)
    if not version:
        resp = jsonify(error="Version not found")
        resp.status_code = 404
        return resp
    return jsonify(version.model_dump())


@blueprint.route("/api/v1/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id: str) -> Response:
    authnz.get_email()
    ok = report_store.delete_report(report_id)
    if not ok:
        resp = jsonify(error="Report not found")
        resp.status_code = 404
        return resp
    resp = jsonify(report_id=report_id)
    resp.status_code = 200
    return resp


@blueprint.route("/api/v1/reports", methods=["POST"])
def create_report() -> Response:
    created_by = authnz.get_email()

    if not request.is_json:
        resp = jsonify(error="Request must be JSON")
        resp.status_code = 400
        return resp

    try:
        body = CreateReportRequest.model_validate(request.get_json())
    except ValidationError as e:
        resp = jsonify(error="Invalid request", details=e.errors())
        resp.status_code = 400
        return resp

    report = report_store.create_report(
        name=body.name,
        created_by=created_by,
    )
    resp = jsonify(report.model_dump())
    resp.status_code = 201
    return resp


@blueprint.route("/api/v1/reports/<report_id>/versions", methods=["POST"])
def create_version(report_id: str) -> Response:
    created_by = authnz.get_email()

    if not request.is_json:
        resp = jsonify(error="Request must be JSON")
        resp.status_code = 400
        return resp

    try:
        body = CreateVersionRequest.model_validate(request.get_json())
    except ValidationError as e:
        resp = jsonify(error="Invalid request", details=e.errors())
        resp.status_code = 400
        return resp

    version = report_store.save_report_version(
        report_id=report_id,
        config=body.config,
        created_by=created_by,
        comment=body.comment,
    )
    if not version:
        resp = jsonify(error="Report not found")
        resp.status_code = 404
        return resp

    resp = jsonify(version.model_dump())
    resp.status_code = 201
    return resp
