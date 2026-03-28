"""MCP server for Seizu — exposes toolsets and tools as MCP tools.

The server is mounted as a Starlette ASGI sub-application inside the FastAPI app
at /api/v1/mcp.  Authentication is enforced by a thin ASGI middleware that validates
the Bearer token using the same JWT logic as the rest of the API.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from typing import AsyncIterator
from typing import Dict
from typing import List
from typing import Optional

import jwt
from jwt import PyJWKClient
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent
from mcp.types import Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse as StarletteJSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from reporting import settings
from reporting.routes.query import _serialize_neo4j_value
from reporting.schema.mcp_config import validate_tool_arguments
from reporting.services import report_store
from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in seizu toolset
# ---------------------------------------------------------------------------

_BUILTIN_SCHEMA_TOOL_NAME = "seizu__schema"
_BUILTIN_QUERY_TOOL_NAME = "seizu__query"

_LABELS_QUERY = "CALL db.labels() YIELD label RETURN label ORDER BY label"
_RELS_QUERY = (
    "CALL db.relationshipTypes() YIELD relationshipType "
    "RETURN relationshipType AS type ORDER BY type"
)
_PROPS_QUERY = (
    "CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey AS key ORDER BY key"
)

# ---------------------------------------------------------------------------
# Parameter schema conversion
# ---------------------------------------------------------------------------

_PARAM_TYPE_MAP: Dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
}


def _build_input_schema(parameters: List[Any]) -> Dict[str, Any]:
    """Convert a list of ToolParamDef to a JSON Schema object."""
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for p in parameters:
        schema_type = _PARAM_TYPE_MAP.get(p.type, "string")
        prop: Dict[str, Any] = {"type": schema_type}
        if p.description:
            prop["description"] = p.description
        if p.default is not None:
            prop["default"] = p.default
        properties[p.name] = prop
        if p.required:
            required.append(p.name)
    result: Dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


def _build_mcp_server() -> Server:
    server: Server = Server("seizu")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        tools: List[Tool] = []

        # Built-in seizu toolset — always available
        tools.append(
            Tool(
                name=_BUILTIN_SCHEMA_TOOL_NAME,
                description=(
                    "Returns the available node labels, relationship types, and property "
                    "keys in the Neo4j graph database."
                ),
                inputSchema={"type": "object", "properties": {}},
            )
        )
        tools.append(
            Tool(
                name=_BUILTIN_QUERY_TOOL_NAME,
                description=(
                    "Execute an ad-hoc read-only Cypher query against the Neo4j graph "
                    "database. The query is validated before execution — write operations "
                    "are not permitted."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "A read-only Cypher query to execute.",
                        }
                    },
                    "required": ["query"],
                },
            )
        )

        # User-defined tools from the store
        try:
            enabled_tools = await report_store.list_enabled_tools()
            toolsets = await report_store.list_toolsets()
            toolset_names = {ts.toolset_id: ts.name for ts in toolsets}

            for tool in enabled_tools:
                ts_name = toolset_names.get(tool.toolset_id, tool.toolset_id)
                mcp_name = f"{ts_name}__{tool.name}"
                description = tool.description or f"{tool.name} tool"
                tools.append(
                    Tool(
                        name=mcp_name,
                        description=description,
                        inputSchema=_build_input_schema(tool.parameters),
                    )
                )
        except Exception:
            logger.exception("Failed to load tools from store for MCP listing")

        return tools

    @server.call_tool()
    async def call_tool(
        name: str, arguments: Optional[Dict[str, Any]]
    ) -> List[TextContent]:
        args = arguments or {}

        # Built-in ad-hoc query tool
        if name == _BUILTIN_QUERY_TOOL_NAME:
            cypher = str(args.get("query", "")).strip()
            if not cypher:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "query parameter is required"}),
                    )
                ]
            validation = await validate_query(cypher)
            if validation.has_errors:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "errors": validation.errors,
                                "warnings": validation.warnings,
                            }
                        ),
                    )
                ]
            try:
                results = await reporting_neo4j.run_query(cypher)
                serialized = [
                    {
                        key: _serialize_neo4j_value(value)
                        for key, value in record.items()
                    }
                    for record in results
                ]
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"results": serialized, "warnings": validation.warnings},
                            indent=2,
                        ),
                    )
                ]
            except Exception:
                logger.exception("Failed to execute seizu__query tool")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Query execution failed"}),
                    )
                ]

        # Built-in schema tool
        if name == _BUILTIN_SCHEMA_TOOL_NAME:
            try:
                labels_results = await reporting_neo4j.run_query(_LABELS_QUERY)
                rels_results = await reporting_neo4j.run_query(_RELS_QUERY)
                props_results = await reporting_neo4j.run_query(_PROPS_QUERY)
                schema = {
                    "labels": [r["label"] for r in labels_results],
                    "relationship_types": [r["type"] for r in rels_results],
                    "property_keys": [r["key"] for r in props_results],
                }
                return [TextContent(type="text", text=json.dumps(schema, indent=2))]
            except Exception:
                logger.exception("Failed to execute schema tool")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": "Failed to retrieve schema"}),
                    )
                ]

        # User-defined tool — look up by namespaced name
        try:
            enabled_tools = await report_store.list_enabled_tools()
            toolsets = await report_store.list_toolsets()
            toolset_names = {ts.toolset_id: ts.name for ts in toolsets}

            target_tool = None
            for tool in enabled_tools:
                ts_name = toolset_names.get(tool.toolset_id, tool.toolset_id)
                mcp_name = f"{ts_name}__{tool.name}"
                if mcp_name == name:
                    target_tool = tool
                    break

            if target_tool is None:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"error": f"Tool '{name}' not found"}),
                    )
                ]

            arg_errors = validate_tool_arguments(target_tool.parameters, args)
            if arg_errors:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"errors": arg_errors}),
                    )
                ]

            results = await reporting_neo4j.run_query(
                target_tool.cypher, parameters=args
            )
            serialized = [
                {key: _serialize_neo4j_value(value) for key, value in record.items()}
                for record in results
            ]
            return [TextContent(type="text", text=json.dumps(serialized, indent=2))]
        except Exception:
            logger.exception("Failed to execute MCP tool %s", name)
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"error": f"Failed to execute tool '{name}'"}),
                )
            ]

    return server


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_jwks_client_cache: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client_cache
    if _jwks_client_cache is None:
        _jwks_client_cache = PyJWKClient(settings.JWKS_URL, cache_keys=True)
    return _jwks_client_cache


class _MCPAuthMiddleware:
    """ASGI middleware that validates Bearer tokens before passing to the MCP app."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
            # Auth disabled in dev — pass through
            await self._app(scope, receive, send)
            return

        # OAuth metadata must be reachable before auth — client has no token yet
        if scope.get("path", "").endswith(_WELL_KNOWN_PATH):
            await self._app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header: Optional[bytes] = headers.get(b"authorization")
        if not auth_header:
            await self._send_401(scope, receive, send)
            return

        auth_str = auth_header.decode("latin-1")
        if not auth_str.lower().startswith("bearer "):
            await self._send_401(scope, receive, send)
            return

        token = auth_str[7:].strip()
        try:
            client = _get_jwks_client()
            signing_key = await asyncio.to_thread(
                client.get_signing_key_from_jwt, token
            )
            decode_kwargs: Dict[str, Any] = {
                "algorithms": settings.ALLOWED_JWT_ALGORITHMS,
            }
            if settings.JWT_ISSUER:
                decode_kwargs["issuer"] = settings.JWT_ISSUER
            if settings.JWT_AUDIENCE:
                decode_kwargs["audience"] = settings.JWT_AUDIENCE
            jwt.decode(token, signing_key.key, **decode_kwargs)
        except jwt.PyJWTError:
            await self._send_401(scope, receive, send)
            return

        await self._app(scope, receive, send)

    @staticmethod
    async def _send_401(scope: Scope, receive: Receive, send: Send) -> None:
        from starlette.responses import JSONResponse

        response = JSONResponse(
            {"error": "Not authenticated"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)


# ---------------------------------------------------------------------------
# OAuth 2.0 Authorization Server Metadata (RFC 8414)
# ---------------------------------------------------------------------------

_WELL_KNOWN_PATH = "/.well-known/oauth-authorization-server"


def _build_oauth_metadata() -> Optional[Dict[str, Any]]:
    """Return the RFC 8414 metadata dict, or None if not configured."""
    auth_endpoint = settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT
    token_endpoint = settings.MCP_OAUTH_TOKEN_ENDPOINT
    if not auth_endpoint or not token_endpoint:
        return None
    issuer = settings.MCP_OAUTH_ISSUER or settings.JWT_ISSUER
    scopes = settings.OIDC_SCOPE.split() if settings.OIDC_SCOPE else ["openid", "email"]
    metadata: Dict[str, Any] = {
        "issuer": issuer,
        "authorization_endpoint": auth_endpoint,
        "token_endpoint": token_endpoint,
        "scopes_supported": scopes,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        # "none" allows public clients (e.g. Claude Desktop) without a client secret
        "token_endpoint_auth_methods_supported": ["none"],
    }
    if settings.JWKS_URL:
        metadata["jwks_uri"] = settings.JWKS_URL
    return metadata


async def _oauth_metadata_handler(request: Request) -> StarletteJSONResponse:
    metadata = _build_oauth_metadata()
    if metadata is None:
        return StarletteJSONResponse({"error": "Not found"}, status_code=404)
    return StarletteJSONResponse(metadata)


# ---------------------------------------------------------------------------
# ASGI app factory
# ---------------------------------------------------------------------------


def get_mcp_app() -> ASGIApp:
    """Return the MCP ASGI application wrapped with auth middleware."""
    mcp_server = _build_mcp_server()
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=True,
        stateless=True,
    )
    asgi_app = StreamableHTTPASGIApp(session_manager)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    starlette_app = Starlette(
        routes=[
            # OAuth metadata must be reachable before auth — no token yet during discovery
            Route(
                _WELL_KNOWN_PATH,
                endpoint=_oauth_metadata_handler,
                methods=["GET"],
            ),
            Route(
                "/{path:path}",
                endpoint=asgi_app,
                methods=["POST"],
            ),
        ],
        lifespan=lifespan,
    )

    return _MCPAuthMiddleware(starlette_app)
