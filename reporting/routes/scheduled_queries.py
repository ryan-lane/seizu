import logging
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from flask import blueprints
from flask import g
from flask import jsonify
from flask import request
from flask import Response
from pydantic import ValidationError

from reporting import authnz
from reporting import scheduled_query_modules
from reporting.schema.report_config import CreateScheduledQueryRequest
from reporting.services import report_store
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
blueprint = blueprints.Blueprint("scheduled_queries", __name__)


def _validate_action_configs(
    actions: List[Dict[str, Any]],
) -> Optional[str]:
    """Validate each action's config against the module's declared schema.

    Returns an error message string if validation fails, or None if valid.
    """
    schemas = scheduled_query_modules.get_action_schemas()
    for action in actions:
        action_type = action.get("action_type", "")
        action_config = action.get("action_config", {})
        if action_type not in schemas:
            continue
        for field in schemas[action_type]:
            if not field.required:
                continue
            value = action_config.get(field.name)
            if value is None or value == "" or value == []:
                return f"Action type '{action_type}' is missing required field '{field.name}'."
    return None


@blueprint.route("/api/v1/scheduled-queries", methods=["GET"])
@authnz.require_auth
def list_scheduled_queries() -> Response:
    items = report_store.list_scheduled_queries()
    return jsonify(scheduled_queries=[i.model_dump() for i in items])


@blueprint.route("/api/v1/scheduled-queries/<sq_id>", methods=["GET"])
@authnz.require_auth
def get_scheduled_query(sq_id: str) -> Response:
    item = report_store.get_scheduled_query(sq_id)
    if not item:
        resp = jsonify(error="Scheduled query not found")
        resp.status_code = 404
        return resp
    return jsonify(item.model_dump())


@blueprint.route("/api/v1/scheduled-queries", methods=["POST"])
@authnz.require_auth
def create_scheduled_query() -> Response:
    if not request.is_json:
        resp = jsonify(error="Request must be JSON")
        resp.status_code = 400
        return resp
    try:
        body = CreateScheduledQueryRequest.model_validate(request.get_json())
    except ValidationError as e:
        resp = jsonify(error="Invalid request", details=e.errors())
        resp.status_code = 400
        return resp
    err = _validate_action_configs(body.actions)
    if err:
        resp = jsonify(error=err)
        resp.status_code = 400
        return resp
    validation = validate_query(body.cypher)
    if validation.has_errors:
        resp = jsonify(errors=validation.errors, warnings=validation.warnings)
        resp.status_code = 400
        return resp
    item = report_store.create_scheduled_query(
        name=body.name,
        cypher=body.cypher,
        params=body.params,
        frequency=body.frequency,
        watch_scans=body.watch_scans,
        enabled=body.enabled,
        actions=body.actions,
        created_by=g.current_user.user_id,
    )
    resp = jsonify(item.model_dump())
    resp.status_code = 201
    return resp


@blueprint.route("/api/v1/scheduled-queries/<sq_id>", methods=["PUT"])
@authnz.require_auth
def update_scheduled_query(sq_id: str) -> Response:
    if not request.is_json:
        resp = jsonify(error="Request must be JSON")
        resp.status_code = 400
        return resp
    try:
        body = CreateScheduledQueryRequest.model_validate(request.get_json())
    except ValidationError as e:
        resp = jsonify(error="Invalid request", details=e.errors())
        resp.status_code = 400
        return resp
    err = _validate_action_configs(body.actions)
    if err:
        resp = jsonify(error=err)
        resp.status_code = 400
        return resp
    validation = validate_query(body.cypher)
    if validation.has_errors:
        resp = jsonify(errors=validation.errors, warnings=validation.warnings)
        resp.status_code = 400
        return resp
    item = report_store.update_scheduled_query(
        sq_id=sq_id,
        name=body.name,
        cypher=body.cypher,
        params=body.params,
        frequency=body.frequency,
        watch_scans=body.watch_scans,
        enabled=body.enabled,
        actions=body.actions,
        updated_by=g.current_user.user_id,
        comment=body.comment,
    )
    if not item:
        resp = jsonify(error="Scheduled query not found")
        resp.status_code = 404
        return resp
    return jsonify(item.model_dump())


@blueprint.route("/api/v1/scheduled-queries/<sq_id>/versions", methods=["GET"])
@authnz.require_auth
def list_scheduled_query_versions(sq_id: str) -> Response:
    item = report_store.get_scheduled_query(sq_id)
    if not item:
        resp = jsonify(error="Scheduled query not found")
        resp.status_code = 404
        return resp
    versions = report_store.list_scheduled_query_versions(sq_id)
    return jsonify(versions=[v.model_dump() for v in versions])


@blueprint.route(
    "/api/v1/scheduled-queries/<sq_id>/versions/<int:version>", methods=["GET"]
)
@authnz.require_auth
def get_scheduled_query_version(sq_id: str, version: int) -> Response:
    v = report_store.get_scheduled_query_version(sq_id, version)
    if not v:
        resp = jsonify(error="Scheduled query version not found")
        resp.status_code = 404
        return resp
    return jsonify(v.model_dump())


@blueprint.route("/api/v1/scheduled-queries/<sq_id>", methods=["DELETE"])
@authnz.require_auth
def delete_scheduled_query(sq_id: str) -> Response:
    ok = report_store.delete_scheduled_query(sq_id)
    if not ok:
        resp = jsonify(error="Scheduled query not found")
        resp.status_code = 404
        return resp
    resp = jsonify(scheduled_query_id=sq_id)
    resp.status_code = 200
    return resp
