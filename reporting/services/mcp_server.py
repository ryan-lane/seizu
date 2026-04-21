"""MCP server for Seizu — exposes toolsets and tools as MCP tools.

The server is wired into the FastAPI app via a pure ASGI middleware
(_MCPMiddleware in reporting/app.py) that intercepts /api/v1/mcp* paths before
FastAPI's router runs.  Authentication is enforced by _MCPAuthMiddleware which
validates the Bearer token using the same JWT logic as the rest of the API.
The session manager lifespan is managed by the FastAPI app's lifespan context.
"""
import asyncio
import contextvars
import json
import logging
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import FrozenSet
from typing import List
from typing import Optional
from typing import Tuple

import jwt
from jwt import PyJWKClient
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent
from mcp.types import Tool
from starlette.requests import Request
from starlette.responses import JSONResponse as StarletteJSONResponse
from starlette.types import ASGIApp
from starlette.types import Receive
from starlette.types import Scope
from starlette.types import Send

from reporting import settings
from reporting.authnz import CurrentUser
from reporting.routes.query import _serialize_neo4j_value
from reporting.schema.mcp_config import validate_tool_arguments
from reporting.services import report_store
from reporting.services import reporting_neo4j
from reporting.services.mcp_builtins import find_builtin
from reporting.services.mcp_builtins import list_builtin_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-scoped context
# ---------------------------------------------------------------------------

# Resolved permission set for the current MCP request. Set by
# _MCPAuthMiddleware.
_mcp_permissions: contextvars.ContextVar[FrozenSet[str]] = contextvars.ContextVar(
    "_mcp_permissions", default=frozenset()
)

# The resolved CurrentUser for the current MCP request. Set by
# _MCPAuthMiddleware. Built-ins that create/update records rely on this to
# populate created_by / updated_by.
_mcp_current_user: contextvars.ContextVar[
    Optional[CurrentUser]
] = contextvars.ContextVar("_mcp_current_user", default=None)


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


def _text(payload: Any) -> List[TextContent]:
    """Serialize *payload* to JSON and wrap it as a single MCP TextContent."""
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _missing_permissions(required: List[str], granted: FrozenSet[str]) -> List[str]:
    return [p for p in required if p not in granted]


def _build_mcp_server() -> Server:
    server: Server = Server("seizu")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        tools: List[Tool] = []
        perms = _mcp_permissions.get()

        # Built-in tools registered by reporting/services/mcp_builtins
        for builtin in list_builtin_tools(settings.MCP_ENABLED_BUILTINS):
            # Only surface tools the caller has permission for; this keeps
            # Claude from seeing admin-only write tools when logged in as a
            # viewer.
            if _missing_permissions(builtin.required_permissions, perms):
                continue
            tools.append(
                Tool(
                    name=builtin.name,
                    description=builtin.description,
                    inputSchema=builtin.input_schema,
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
        perms = _mcp_permissions.get()

        # Built-in tool dispatch
        builtin = find_builtin(name, settings.MCP_ENABLED_BUILTINS)
        if builtin is not None:
            missing = _missing_permissions(builtin.required_permissions, perms)
            if missing:
                return _text({"error": f"Permission denied: {', '.join(missing)}"})
            try:
                result = await builtin.handler(args, _mcp_current_user.get())
                return _text(result)
            except Exception:
                logger.exception("Failed to execute built-in MCP tool %s", name)
                return _text({"error": f"Failed to execute tool '{name}'"})

        # User-defined tool — look up by namespaced name
        if "tools:call" not in perms:
            return _text({"error": "Permission denied: tools:call"})
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
                return _text({"error": f"Tool '{name}' not found"})

            arg_errors = validate_tool_arguments(target_tool.parameters, args)
            if arg_errors:
                return _text({"errors": arg_errors})

            # Apply parameter defaults so optional params are passed as null
            # rather than absent — Neo4j raises ParameterMissing if a $param
            # referenced in the query is not present at all.
            params_with_defaults = {p.name: p.default for p in target_tool.parameters}
            params_with_defaults.update(args)

            results = await reporting_neo4j.run_query(
                target_tool.cypher, parameters=params_with_defaults
            )
            serialized = [
                {key: _serialize_neo4j_value(value) for key, value in record.items()}
                for record in results
            ]
            return _text(serialized)
        except Exception:
            logger.exception("Failed to execute MCP tool %s", name)
            return _text({"error": f"Failed to execute tool '{name}'"})

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


async def _build_dev_current_user() -> CurrentUser:
    """Return a synthetic CurrentUser for dev mode (auth disabled)."""
    from reporting.authnz.permissions import ALL_PERMISSIONS

    email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
    user = await report_store.get_or_create_user(
        sub=email,
        iss="dev",
        email=email,
        display_name=None,
    )
    return CurrentUser(
        user=user,
        jwt_claims={"email": email, "display_name": None, "token_iat": None},
        permissions=ALL_PERMISSIONS,
    )


async def _build_current_user_from_jwt(payload: Dict[str, Any]) -> CurrentUser:
    """Resolve a CurrentUser from an already-validated JWT payload."""
    from reporting.authnz.permissions import resolve_permissions

    raw_iat = payload.get("iat")
    token_iat = (
        datetime.fromtimestamp(raw_iat, tz=timezone.utc)
        if raw_iat is not None
        else None
    )
    jwt_claims = {
        "email": payload[settings.JWT_EMAIL_CLAIM],
        "display_name": payload.get("name"),
        "token_iat": token_iat,
    }
    user = await report_store.get_or_create_user(
        sub=payload[settings.JWT_SUB_CLAIM],
        iss=payload[settings.JWT_ISS_CLAIM],
        email=payload[settings.JWT_EMAIL_CLAIM],
        display_name=payload.get("name"),
    )
    permissions = await resolve_permissions(payload)
    return CurrentUser(user=user, jwt_claims=jwt_claims, permissions=permissions)


class _MCPAuthMiddleware:
    """ASGI middleware that validates Bearer tokens before passing to the MCP app."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
            # Auth disabled in dev — grant all permissions and synthesize a user
            current_user = await _build_dev_current_user()
            perm_token = _mcp_permissions.set(current_user.permissions)
            user_token = _mcp_current_user.set(current_user)
            try:
                await self._app(scope, receive, send)
            finally:
                _mcp_permissions.reset(perm_token)
                _mcp_current_user.reset(user_token)
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

        bearer_token = auth_str[7:].strip()
        try:
            client = _get_jwks_client()
            signing_key = await asyncio.to_thread(
                client.get_signing_key_from_jwt, bearer_token
            )
            decode_kwargs: Dict[str, Any] = {
                "algorithms": settings.ALLOWED_JWT_ALGORITHMS,
            }
            if settings.JWT_ISSUER:
                decode_kwargs["issuer"] = settings.JWT_ISSUER
            if settings.JWT_AUDIENCE:
                decode_kwargs["audience"] = settings.JWT_AUDIENCE
            payload = jwt.decode(bearer_token, signing_key.key, **decode_kwargs)
        except jwt.PyJWTError:
            await self._send_401(scope, receive, send)
            return

        current_user = await _build_current_user_from_jwt(payload)

        perm_token = _mcp_permissions.set(current_user.permissions)
        user_token = _mcp_current_user.set(current_user)
        try:
            await self._app(scope, receive, send)
        finally:
            _mcp_permissions.reset(perm_token)
            _mcp_current_user.reset(user_token)

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
# Inner dispatcher: routes OAuth metadata, passes everything else to MCP
# ---------------------------------------------------------------------------


class _MCPDispatcher:
    """Routes OAuth metadata requests; forwards everything else to the MCP app."""

    def __init__(self, mcp_asgi_app: ASGIApp) -> None:
        self._mcp_app = mcp_asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and path.endswith(_WELL_KNOWN_PATH):
            request = Request(scope, receive)
            response = await _oauth_metadata_handler(request)
            await response(scope, receive, send)
            return
        await self._mcp_app(scope, receive, send)


# ---------------------------------------------------------------------------
# ASGI app factory
# ---------------------------------------------------------------------------


def get_mcp_app() -> Tuple[StreamableHTTPSessionManager, ASGIApp]:
    """Return (session_manager, mcp_asgi_app) for integration into the FastAPI app.

    The caller must:
    1. Store session_manager and start it with ``async with session_manager.run()``
       during the application lifespan (e.g., FastAPI lifespan context).
    2. Route /api/v1/mcp* requests to the returned mcp_asgi_app (e.g., via
       _MCPMiddleware in reporting/app.py).

    Auth and OAuth metadata routing are handled internally by the returned app.
    """
    mcp_server = _build_mcp_server()
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=True,
        stateless=True,
    )
    mcp_asgi = StreamableHTTPASGIApp(session_manager)
    return session_manager, _MCPAuthMiddleware(_MCPDispatcher(mcp_asgi))
