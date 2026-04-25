"""Built-in ``graph__*`` tools — schema discovery and ad-hoc Cypher."""

from typing import Any

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.routes.query import _serialize_neo4j_value
from reporting.services import reporting_neo4j
from reporting.services.mcp_builtins.base import BuiltinGroup, BuiltinTool
from reporting.services.query_validator import validate_query

GROUP = "graph"

_LABELS_QUERY = "CALL db.labels() YIELD label RETURN label ORDER BY label"
_RELS_QUERY = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type ORDER BY type"
_PROPS_QUERY = "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS key ORDER BY key"


async def _handle_schema(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    labels_results = await reporting_neo4j.run_query(_LABELS_QUERY)
    rels_results = await reporting_neo4j.run_query(_RELS_QUERY)
    props_results = await reporting_neo4j.run_query(_PROPS_QUERY)
    return {
        "labels": [r["label"] for r in labels_results],
        "relationship_types": [r["type"] for r in rels_results],
        "property_keys": [r["key"] for r in props_results],
    }


async def _handle_query(args: dict[str, Any], current_user: CurrentUser | None) -> dict[str, Any]:
    cypher = str(args.get("query", "")).strip()
    if not cypher:
        return {"error": "query parameter is required"}
    validation = await validate_query(cypher)
    if validation.has_errors:
        return {"errors": validation.errors, "warnings": validation.warnings}
    results = await reporting_neo4j.run_query(cypher)
    serialized = [{key: _serialize_neo4j_value(value) for key, value in record.items()} for record in results]
    return {"results": serialized, "warnings": validation.warnings}


GROUP_DEF = BuiltinGroup(
    name=GROUP,
    tools=[
        BuiltinTool(
            name="graph__schema",
            group=GROUP,
            description=(
                "Returns the available node labels, relationship types, and property keys in the Neo4j graph database."
            ),
            input_schema={"type": "object", "properties": {}},
            required_permissions=[Permission.QUERY_EXECUTE.value],
            handler=_handle_schema,
        ),
        BuiltinTool(
            name="graph__query",
            group=GROUP,
            description=(
                "Execute an ad-hoc read-only Cypher query against the Neo4j "
                "graph database. The query is validated before execution — "
                "write operations are not permitted."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A read-only Cypher query to execute.",
                    }
                },
                "required": ["query"],
            },
            required_permissions=[Permission.QUERY_EXECUTE.value],
            handler=_handle_query,
        ),
    ],
)
