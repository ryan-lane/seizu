import logging
from typing import Any

from flask import blueprints
from flask import jsonify
from flask import request
from flask import Response
from neo4j.graph import Node
from neo4j.graph import Path
from neo4j.graph import Relationship
from pydantic import ValidationError

from reporting import authnz
from reporting.schema.query import QueryRequest
from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
blueprint = blueprints.Blueprint("query", __name__)


def _serialize_neo4j_value(value: Any) -> Any:
    if isinstance(value, Node):
        return {
            "id": value.id,
            "labels": list(value.labels),
            "properties": {k: _serialize_neo4j_value(v) for k, v in value.items()},
        }
    elif isinstance(value, Relationship):
        return {
            "id": value.id,
            "type": value.type,
            "start_node_id": value.start_node.id,
            "end_node_id": value.end_node.id,
            "properties": {k: _serialize_neo4j_value(v) for k, v in value.items()},
        }
    elif isinstance(value, Path):
        return {
            "nodes": [_serialize_neo4j_value(n) for n in value.nodes],
            "relationships": [_serialize_neo4j_value(r) for r in value.relationships],
        }
    elif isinstance(value, dict):
        return {k: _serialize_neo4j_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_serialize_neo4j_value(v) for v in value]
    elif isinstance(value, (int, float, str, bool, type(None))):
        return value
    else:
        return str(value)


@blueprint.route("/api/v1/query", methods=["POST"])
def query() -> Response:
    authnz.get_email()

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

    if validation.has_errors:
        resp = jsonify(
            errors=[str(err) for err in validation.errors],
            warnings=[str(w) for w in validation.warnings],
        )
        resp.status_code = 400
        return resp

    try:
        results = reporting_neo4j.run_query(
            query_request.query, parameters=query_request.params
        )
        logger.info(results)
        serialized = [
            {key: _serialize_neo4j_value(value) for key, value in record.items()}
            for record in results
        ]
        resp = jsonify(
            results=serialized,
            warnings=[str(w) for w in validation.warnings],
            errors=[],
        )
        return resp
    except Exception as e:
        logger.exception("Query execution failed")
        resp = jsonify(error="Query execution failed", details=str(e))
        resp.status_code = 500
        return resp
