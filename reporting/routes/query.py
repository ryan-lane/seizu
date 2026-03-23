import logging
from typing import Any

from apiflask import APIBlueprint
from flask import jsonify
from flask import make_response
from neo4j.graph import Node
from neo4j.graph import Path
from neo4j.graph import Relationship

from reporting import authnz  # noqa: F401
from reporting.authnz import bearer_auth
from reporting.schema.query import QueryRequest
from reporting.schema.query import QueryResponse
from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
blueprint = APIBlueprint("query", __name__)


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
            "start_node_id": value.start_node.id,  # type: ignore
            "end_node_id": value.end_node.id,  # type: ignore
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


@blueprint.post("/api/v1/query")
@blueprint.auth_required(bearer_auth)
@blueprint.input(QueryRequest, arg_name="body")
@blueprint.output(QueryResponse)
def query(body: QueryRequest) -> Any:
    """Execute a validated read-only Cypher query."""
    validation = validate_query(body.query, params=body.params)

    if validation.has_errors:
        # Return Cypher validation errors in the original envelope so the
        # frontend can display them inline.  Returning a Response object
        # bypasses APIFlask's @output serialisation wrapper.
        return make_response(
            jsonify(
                errors=[str(err) for err in validation.errors],
                warnings=[str(w) for w in validation.warnings],
            ),
            400,
        )

    try:
        results = reporting_neo4j.run_query(body.query, parameters=body.params)
        serialized = [
            {key: _serialize_neo4j_value(value) for key, value in record.items()}
            for record in results
        ]
        return {
            "results": serialized,
            "warnings": [str(w) for w in validation.warnings],
            "errors": [],
        }
    except Exception as e:
        logger.exception("Query execution failed")
        return make_response(
            jsonify(error="Query execution failed", details=str(e)), 500
        )
