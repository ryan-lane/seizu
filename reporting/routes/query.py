import logging
from typing import Any

import neo4j.exceptions
from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import JSONResponse
from neo4j.graph import Node
from neo4j.graph import Path
from neo4j.graph import Relationship

from reporting.authnz import CurrentUser
from reporting.authnz import require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.query import QueryRequest
from reporting.schema.query import QueryResponse
from reporting.services import report_store
from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)
router = APIRouter()


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
            "start_node_id": value.start_node.id
            if value.start_node is not None
            else None,
            "end_node_id": value.end_node.id if value.end_node is not None else None,
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


@router.post("/api/v1/query", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    current: CurrentUser = Depends(require_permission(Permission.QUERY_EXECUTE)),
) -> Any:
    """Execute a validated read-only Cypher query."""
    validation = await validate_query(body.query, params=body.params)

    if validation.has_errors:
        return JSONResponse(
            content={
                "errors": [str(err) for err in validation.errors],
                "warnings": [str(w) for w in validation.warnings],
            },
            status_code=400,
        )

    try:
        results = await reporting_neo4j.run_query(body.query, parameters=body.params)
        serialized = [
            {key: _serialize_neo4j_value(value) for key, value in record.items()}
            for record in results
        ]
        if body.save_history:
            try:
                await report_store.save_query_history(
                    user_id=current.user.user_id,
                    query=body.query,
                )
            except Exception:
                logger.warning("Failed to save query history", exc_info=True)
        return {
            "results": serialized,
            "warnings": [str(w) for w in validation.warnings],
            "errors": [],
        }
    except neo4j.exceptions.Neo4jError as e:
        logger.exception("Query execution failed")
        return JSONResponse(
            content={
                "error": "Query execution failed",
                "code": e.code,
                "details": e.message,
            },
            status_code=500,
        )
    except Exception:
        logger.exception("Query execution failed")
        return JSONResponse(
            content={"error": "Query execution failed"},
            status_code=500,
        )
