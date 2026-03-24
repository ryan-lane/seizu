import logging
from typing import Any
from typing import Dict
from typing import List

from apiflask import abort
from apiflask import APIBlueprint
from flask import g
from flask import jsonify
from flask import make_response

from reporting import authnz  # noqa: F401
from reporting import scheduled_query_modules
from reporting.authnz import bearer_auth
from reporting.schema.report_config import CreateScheduledQueryRequest
from reporting.schema.report_config import ScheduledQueryIdResponse
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.report_config import ScheduledQueryListResponse
from reporting.schema.report_config import ScheduledQueryVersion
from reporting.schema.report_config import ScheduledQueryVersionListResponse
from reporting.services import report_store
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
blueprint = APIBlueprint("scheduled_queries", __name__)


def _validate_action_configs(
    actions: List[Dict[str, Any]],
) -> str | None:
    """Validate each action's config against the module's declared schema.

    Returns an error message string if validation fails, or None if valid.
    """
    schemas = scheduled_query_modules.get_action_schemas()
    for action in actions:
        action_type = action.get("action_type", "")
        action_config = action.get("action_config", {})
        if action_type not in schemas:
            return (
                f"Unknown action type '{action_type}'. Valid types: {sorted(schemas)}."
            )
        for field in schemas[action_type]:
            if not field.required:
                continue
            value = action_config.get(field.name)
            if value is None or value == "" or value == []:
                return f"Action type '{action_type}' is missing required field '{field.name}'."
    return None


@blueprint.get("/api/v1/scheduled-queries")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ScheduledQueryListResponse)
def list_scheduled_queries() -> ScheduledQueryListResponse:
    """List all scheduled queries."""
    return ScheduledQueryListResponse(
        scheduled_queries=report_store.list_scheduled_queries()
    )


@blueprint.get("/api/v1/scheduled-queries/<sq_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ScheduledQueryItem)
def get_scheduled_query(sq_id: str) -> ScheduledQueryItem:
    """Return a scheduled query by ID."""
    item = report_store.get_scheduled_query(sq_id)
    if not item:
        abort(404, message="Scheduled query not found")
    return item


@blueprint.post("/api/v1/scheduled-queries")
@blueprint.auth_required(bearer_auth)
@blueprint.input(CreateScheduledQueryRequest, arg_name="body")
@blueprint.output(ScheduledQueryItem, status_code=201)
def create_scheduled_query(body: CreateScheduledQueryRequest) -> Any:
    """Create a new scheduled query."""
    err = _validate_action_configs(body.actions)
    if err:
        abort(400, message=err)
    validation = validate_query(body.cypher)
    if validation.has_errors:
        return make_response(
            jsonify(errors=validation.errors, warnings=validation.warnings), 400
        )
    return report_store.create_scheduled_query(
        name=body.name,
        cypher=body.cypher,
        params=body.params,
        frequency=body.frequency,
        watch_scans=body.watch_scans,
        enabled=body.enabled,
        actions=body.actions,
        created_by=g.current_user.user_id,
    )


@blueprint.put("/api/v1/scheduled-queries/<sq_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.input(CreateScheduledQueryRequest, arg_name="body")
@blueprint.output(ScheduledQueryItem)
def update_scheduled_query(sq_id: str, body: CreateScheduledQueryRequest) -> Any:
    """Update a scheduled query."""
    err = _validate_action_configs(body.actions)
    if err:
        abort(400, message=err)
    validation = validate_query(body.cypher)
    if validation.has_errors:
        return make_response(
            jsonify(errors=validation.errors, warnings=validation.warnings), 400
        )
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
        abort(404, message="Scheduled query not found")
    return item


@blueprint.get("/api/v1/scheduled-queries/<sq_id>/versions")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ScheduledQueryVersionListResponse)
def list_scheduled_query_versions(sq_id: str) -> ScheduledQueryVersionListResponse:
    """List all versions of a scheduled query."""
    item = report_store.get_scheduled_query(sq_id)
    if not item:
        abort(404, message="Scheduled query not found")
    versions = report_store.list_scheduled_query_versions(sq_id)
    return ScheduledQueryVersionListResponse(versions=versions)


@blueprint.get("/api/v1/scheduled-queries/<sq_id>/versions/<int:version>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ScheduledQueryVersion)
def get_scheduled_query_version(sq_id: str, version: int) -> ScheduledQueryVersion:
    """Return a specific version of a scheduled query."""
    v = report_store.get_scheduled_query_version(sq_id, version)
    if not v:
        abort(404, message="Scheduled query version not found")
    return v


@blueprint.delete("/api/v1/scheduled-queries/<sq_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(ScheduledQueryIdResponse)
def delete_scheduled_query(sq_id: str) -> ScheduledQueryIdResponse:
    """Delete a scheduled query."""
    ok = report_store.delete_scheduled_query(sq_id)
    if not ok:
        abort(404, message="Scheduled query not found")
    return ScheduledQueryIdResponse(scheduled_query_id=sq_id)
