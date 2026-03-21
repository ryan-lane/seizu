from flask import blueprints
from flask import jsonify
from flask import request
from flask import Response
from pydantic import ValidationError

from reporting import authnz
from reporting.schema.query import QueryRequest
from reporting.services.query_validator import validate_query

blueprint = blueprints.Blueprint("validate", __name__)


@blueprint.route("/api/v1/validate", methods=["POST"])
@authnz.require_auth
def validate() -> Response:

    if not request.is_json:
        resp = jsonify(error="Request must be JSON")
        resp.status_code = 400
        return resp

    try:
        query_request = QueryRequest.model_validate(request.get_json())
    except ValidationError as e:
        resp = jsonify(error="Invalid request", details=e.errors())
        resp.status_code = 400
        return resp

    validation = validate_query(query_request.query, params=query_request.params)

    resp = jsonify(
        errors=[str(err) for err in validation.errors],
        warnings=[str(w) for w in validation.warnings],
    )
    return resp
