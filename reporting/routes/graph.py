import logging
from typing import Any

import neo4j.exceptions
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.query import GraphSchemaResponse
from reporting.services import reporting_neo4j

logger = logging.getLogger(__name__)
router = APIRouter()

_LABELS_QUERY = "CALL db.labels() YIELD label RETURN label ORDER BY label"
_RELS_QUERY = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type ORDER BY type"
_PROPS_QUERY = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS key ORDER BY key"


@router.get("/api/v1/graph/schema", response_model=GraphSchemaResponse)
async def get_graph_schema(
    current: CurrentUser = Depends(require_permission(Permission.QUERY_EXECUTE)),
) -> Any:
    """Return node labels, relationship types, and property keys from the graph.

    Runs fixed introspection queries without saving to query history.
    Requires query:execute permission (same as the ad-hoc query console).
    """
    try:
        labels_result = await reporting_neo4j.run_query(_LABELS_QUERY)
        rels_result = await reporting_neo4j.run_query(_RELS_QUERY)
        props_result = await reporting_neo4j.run_query(_PROPS_QUERY)
        return GraphSchemaResponse(
            labels=[str(r["label"]) for r in labels_result],
            relationship_types=[str(r["type"]) for r in rels_result],
            property_keys=[str(r["key"]) for r in props_result],
        )
    except neo4j.exceptions.Neo4jError:
        logger.exception("Graph schema query failed")
        return JSONResponse(content={"error": "Graph schema query failed"}, status_code=500)
    except Exception:
        logger.exception("Graph schema query failed")
        return JSONResponse(content={"error": "Graph schema query failed"}, status_code=500)
