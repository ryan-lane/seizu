import logging
from typing import Any

import neo4j.exceptions
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from neo4j.graph import Node, Path, Relationship

from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.query import QueryRequest, QueryResponse, ReportQueryRequest
from reporting.services import report_store, reporting_neo4j
from reporting.services.query_validator import validate_query
from reporting.services.report_query_tokens import resolve_report_query_request

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
            "start_node_id": value.start_node.id if value.start_node is not None else None,
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


async def _execute_query(
    *,
    query: str,
    params: dict[str, Any] | None,
    current: CurrentUser,
    save_history: bool = True,
) -> Any:
    validation = await validate_query(query, params=params)

    if validation.has_errors:
        return JSONResponse(
            content={
                "errors": [str(err) for err in validation.errors],
                "warnings": [str(w) for w in validation.warnings],
            },
            status_code=400,
        )

    try:
        results = await reporting_neo4j.run_query(query, parameters=params)
        serialized = [{key: _serialize_neo4j_value(value) for key, value in record.items()} for record in results]
        if save_history:
            try:
                await report_store.save_query_history(
                    user_id=current.user.user_id,
                    query=query,
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


@router.post("/api/v1/query/adhoc", response_model=QueryResponse)
async def query_adhoc(
    body: QueryRequest,
    current: CurrentUser = Depends(require_permission(Permission.QUERY_EXECUTE)),
) -> Any:
    """Execute a validated read-only ad-hoc Cypher query."""
    return await _execute_query(
        query=body.query,
        params=body.params,
        current=current,
    )


@router.post("/api/v1/query/report", response_model=QueryResponse)
async def query_report(
    body: ReportQueryRequest,
    current: CurrentUser = Depends(require_permission(Permission.REPORTS_READ)),
) -> Any:
    """Execute a validated read-only Cypher query authorized by a signed report token."""
    try:
        query, params = resolve_report_query_request(
            token=body.token,
            current_user=current,
            params=body.params,
        )
    except PermissionError as exc:
        logger.warning("Rejected report query token", exc_info=exc)
        return JSONResponse(content={"error": "Forbidden"}, status_code=403)
    except ValueError as exc:
        logger.warning("Rejected report query token", exc_info=exc)
        return JSONResponse(content={"error": "Invalid report query token"}, status_code=400)

    return await _execute_query(query=query, params=params, current=current, save_history=False)
