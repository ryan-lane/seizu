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
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient
from mcp.server.fastmcp.server import StreamableHTTPASGIApp
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.requests import Request
from starlette.responses import JSONResponse as StarletteJSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from reporting import settings
from reporting.authnz import CurrentUser
from reporting.routes.query import _serialize_neo4j_value
from reporting.schema.mcp_config import validate_tool_arguments
from reporting.services import report_store, reporting_neo4j
from reporting.services.mcp_builtins import find_builtin, list_builtin_tools

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-scoped context
# ---------------------------------------------------------------------------

# Resolved permission set for the current MCP request. Set by
# _MCPAuthMiddleware.
_mcp_permissions: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar(
    "_mcp_permissions", default=frozenset()
)

# The resolved CurrentUser for the current MCP request. Set by
# _MCPAuthMiddleware. Built-ins that create/update records rely on this to
# populate created_by / updated_by.
_mcp_current_user: contextvars.ContextVar[CurrentUser | None] = contextvars.ContextVar(
    "_mcp_current_user", default=None
)


# ---------------------------------------------------------------------------
# Parameter schema conversion
# ---------------------------------------------------------------------------

_PARAM_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
}


def _build_input_schema(parameters: list[Any]) -> dict[str, Any]:
    """Convert a list of ToolParamDef to a JSON Schema object."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in parameters:
        schema_type = _PARAM_TYPE_MAP.get(p.type, "string")
        prop: dict[str, Any] = {"type": schema_type}
        if p.description:
            prop["description"] = p.description
        if p.default is not None:
            prop["default"] = p.default
        properties[p.name] = prop
        if p.required:
            required.append(p.name)
    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


def _text(payload: Any) -> list[TextContent]:
    """Serialize *payload* to JSON and wrap it as a single MCP TextContent."""
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _missing_permissions(required: list[str], granted: frozenset[str]) -> list[str]:
    return [p for p in required if p not in granted]


def _build_mcp_server() -> Server:
    server: Server = Server("seizu")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools: list[Tool] = []
        perms = _mcp_permissions.get()

        # Built-in tools registered by reporting/services/mcp_builtins
        for builtin in list_builtin_tools():
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
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        args = arguments or {}
        perms = _mcp_permissions.get()

        # Built-in tool dispatch
        builtin = find_builtin(name)
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

            results = await reporting_neo4j.run_query(target_tool.cypher, parameters=params_with_defaults)
            serialized = [{key: _serialize_neo4j_value(value) for key, value in record.items()} for record in results]
            return _text(serialized)
        except Exception:
            logger.exception("Failed to execute MCP tool %s", name)
            return _text({"error": f"Failed to execute tool '{name}'"})

    return server


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_jwks_client_cache: PyJWKClient | None = None


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


async def _build_current_user_from_jwt(payload: dict[str, Any]) -> CurrentUser:
    """Resolve a CurrentUser from an already-validated JWT payload."""
    from reporting.authnz.permissions import resolve_permissions

    raw_iat = payload.get("iat")
    token_iat = datetime.fromtimestamp(raw_iat, tz=UTC) if raw_iat is not None else None
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

        # OAuth metadata endpoints must be reachable before auth — client has no token yet.
        # Match any URL form: in-path (/api/v1/mcp/.well-known/oauth-*),
        # origin-based (/.well-known/oauth-*), or RFC 8414 suffix (/.well-known/oauth-*/path).
        path = scope.get("path", "")
        if "/.well-known/oauth-" in path:
            await self._app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header: bytes | None = headers.get(b"authorization")
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
            signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, bearer_token)
            decode_kwargs: dict[str, Any] = {
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

        try:
            current_user = await _build_current_user_from_jwt(payload)
        except Exception:
            logger.exception("Failed to resolve user from JWT claims")
            await self._send_401(scope, receive, send)
            return

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

        www_auth = "Bearer"
        if settings.MCP_RESOURCE_URL and (settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT or settings.OIDC_AUTHORITY):
            resource_metadata_url = f"{settings.MCP_RESOURCE_URL}/.well-known/oauth-protected-resource"
            www_auth = f'Bearer resource_metadata="{resource_metadata_url}"'

        response = JSONResponse(
            {"error": "Not authenticated"},
            status_code=401,
            headers={"WWW-Authenticate": www_auth},
        )
        await response(scope, receive, send)


# ---------------------------------------------------------------------------
# OAuth 2.0 Authorization Server Metadata (RFC 8414) and
# Protected Resource Metadata (RFC 9728)
# ---------------------------------------------------------------------------

_WELL_KNOWN_PATH = "/.well-known/oauth-authorization-server"
_WELL_KNOWN_PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"
_WELL_KNOWN_REGISTRATION_PATH = "/.well-known/oauth-registration"


async def _fetch_oidc_discovery(authority: str) -> dict[str, Any] | None:
    """Fetch {authority}/.well-known/openid-configuration, return parsed JSON or None."""
    url = f"{authority.rstrip('/')}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.warning("Failed to fetch OIDC discovery from %s", url)
        return None


async def _build_oauth_metadata() -> dict[str, Any] | None:
    """Return the RFC 8414 metadata dict, or None if OAuth cannot be configured.

    This document is served at {MCP_RESOURCE_URL}/.well-known/oauth-authorization-server.
    RFC 8414 requires issuer to equal the URL from which the document is served
    (minus the well-known suffix), so we set issuer = MCP_RESOURCE_URL.
    MCP_OAUTH_ISSUER overrides this for setups where an RFC 8414-compliant IdP
    serves the metadata directly.

    Authorization/token endpoints are derived from OIDC discovery when not
    explicitly set via MCP_OAUTH_AUTHORIZATION_ENDPOINT / MCP_OAUTH_TOKEN_ENDPOINT.
    OIDC_INTERNAL_AUTHORITY is used for the server-side fetch (avoids docker
    split-hostname issues); the returned endpoint origins are rewritten to the
    external OIDC_AUTHORITY origin so MCP clients outside docker can reach them.
    """
    oidc_authority = settings.OIDC_AUTHORITY
    auth_endpoint = settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT
    token_endpoint = settings.MCP_OAUTH_TOKEN_ENDPOINT
    jwks_uri: str | None = None

    if oidc_authority and (not auth_endpoint or not token_endpoint):
        discovery_authority = settings.OIDC_INTERNAL_AUTHORITY or oidc_authority
        discovery = await _fetch_oidc_discovery(discovery_authority)
        if discovery:
            raw_auth = auth_endpoint or discovery.get("authorization_endpoint", "")
            raw_token = token_endpoint or discovery.get("token_endpoint", "")
            raw_jwks = discovery.get("jwks_uri", "")
            # When fetching via an internal authority, endpoints use the internal
            # hostname. Rewrite the origin so MCP clients outside docker can reach them.
            if settings.OIDC_INTERNAL_AUTHORITY and discovery_authority != oidc_authority:
                from urllib.parse import urlparse

                int_origin = "{0.scheme}://{0.netloc}".format(urlparse(discovery_authority))
                ext_origin = "{0.scheme}://{0.netloc}".format(urlparse(oidc_authority))
                raw_auth = raw_auth.replace(int_origin, ext_origin, 1)
                raw_token = raw_token.replace(int_origin, ext_origin, 1)
                raw_jwks = raw_jwks.replace(int_origin, ext_origin, 1)
            auth_endpoint = raw_auth
            token_endpoint = raw_token
            jwks_uri = raw_jwks or None

    # RFC 8414: issuer must equal the URL from which this document is served.
    # We serve it at {MCP_RESOURCE_URL}/.well-known/oauth-authorization-server,
    # so MCP_RESOURCE_URL is the correct issuer. MCP_OAUTH_ISSUER overrides this
    # for setups with an external RFC 8414-compliant authorization server.
    metadata_issuer = settings.MCP_OAUTH_ISSUER or settings.MCP_RESOURCE_URL

    if not metadata_issuer or not auth_endpoint or not token_endpoint:
        return None

    scopes = settings.OIDC_SCOPE.split() if settings.OIDC_SCOPE else ["openid", "email"]
    metadata: dict[str, Any] = {
        "issuer": metadata_issuer,
        "authorization_endpoint": auth_endpoint,
        "token_endpoint": token_endpoint,
        "scopes_supported": scopes,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        # "none" allows public clients (e.g. Claude Desktop) without a client secret
        "token_endpoint_auth_methods_supported": ["none"],
    }
    if jwks_uri:
        metadata["jwks_uri"] = jwks_uri

    # RFC 7591: advertise dynamic client registration so MCP clients (e.g.
    # Claude Desktop) don't reject the auth server. Use the explicit override
    # if set; otherwise derive from MCP_RESOURCE_URL when OIDC_CLIENT_ID is
    # available (our built-in lightweight DCR endpoint).
    registration_endpoint: str | None = settings.MCP_OAUTH_REGISTRATION_ENDPOINT
    if not registration_endpoint and settings.MCP_RESOURCE_URL and settings.OIDC_CLIENT_ID:
        registration_endpoint = f"{settings.MCP_RESOURCE_URL}{_WELL_KNOWN_REGISTRATION_PATH}"
    if registration_endpoint:
        metadata["registration_endpoint"] = registration_endpoint

    return metadata


async def _oauth_metadata_handler(request: Request) -> StarletteJSONResponse:
    metadata = await _build_oauth_metadata()
    if metadata is None:
        return StarletteJSONResponse({"error": "Not found"}, status_code=404)
    return StarletteJSONResponse(metadata)


async def _oauth_registration_handler(request: Request) -> StarletteJSONResponse:
    """RFC 7591 dynamic client registration endpoint.

    MCP clients (e.g. Claude Desktop) require a registration_endpoint in the
    OAuth metadata. Most OIDC providers (including Authentik) don't support DCR,
    so Seizu serves its own lightweight endpoint that returns the pre-configured
    OIDC_CLIENT_ID. The caller gets a stable public-client registration back
    without a real DCR-capable IdP.

    The MCP SDK validates the response body and requires redirect_uris to be
    echoed back as an array, so we read the request body and forward it.
    """
    if request.method != "POST":
        return StarletteJSONResponse({"error": "method_not_allowed"}, status_code=405)
    client_id = settings.OIDC_CLIENT_ID
    if not client_id:
        return StarletteJSONResponse({"error": "client_registration_not_supported"}, status_code=400)
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    redirect_uris: list[str] = body.get("redirect_uris") or []
    return StarletteJSONResponse(
        {
            "client_id": client_id,
            "redirect_uris": redirect_uris,
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
        status_code=201,
    )


def _build_protected_resource_metadata() -> dict[str, Any] | None:
    """Return RFC 9728 protected resource metadata, or None if OAuth not configured.

    authorization_servers points to our own MCP endpoint, which serves a valid
    RFC 8414 document at /.well-known/oauth-authorization-server. This sidesteps
    IdPs (like Authentik) that only expose OIDC discovery and not RFC 8414.
    MCP_OAUTH_ISSUER overrides this for setups with an RFC 8414-compliant IdP.
    """
    if not settings.MCP_RESOURCE_URL:
        return None
    # Only advertise OAuth discovery if OIDC/OAuth is actually configured
    if not settings.OIDC_AUTHORITY and not settings.MCP_OAUTH_AUTHORIZATION_ENDPOINT and not settings.MCP_OAUTH_ISSUER:
        return None
    auth_server = settings.MCP_OAUTH_ISSUER or settings.MCP_RESOURCE_URL
    return {
        "resource": settings.MCP_RESOURCE_URL,
        "authorization_servers": [auth_server],
    }


# ---------------------------------------------------------------------------
# Inner dispatcher: routes OAuth metadata, passes everything else to MCP
# ---------------------------------------------------------------------------


class _MCPDispatcher:
    """Routes OAuth metadata requests; forwards everything else to the MCP app."""

    def __init__(self, mcp_asgi_app: ASGIApp) -> None:
        self._mcp_app = mcp_asgi_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http":
            # Match any URL form the client may construct:
            #   in-path:      /api/v1/mcp/.well-known/oauth-authorization-server
            #   origin-based: /.well-known/oauth-authorization-server
            #   RFC 8414:     /.well-known/oauth-authorization-server/api/v1/mcp
            if _WELL_KNOWN_PATH in path:
                request = Request(scope, receive)
                response = await _oauth_metadata_handler(request)
                await response(scope, receive, send)
                return
            if _WELL_KNOWN_PROTECTED_RESOURCE_PATH in path:
                metadata = _build_protected_resource_metadata()
                if metadata is None:
                    response = StarletteJSONResponse({"error": "Not found"}, status_code=404)
                else:
                    response = StarletteJSONResponse(metadata)
                await response(scope, receive, send)
                return
            if _WELL_KNOWN_REGISTRATION_PATH in path:
                request = Request(scope, receive)
                response = await _oauth_registration_handler(request)
                await response(scope, receive, send)
                return
        await self._mcp_app(scope, receive, send)


# ---------------------------------------------------------------------------
# ASGI app factory
# ---------------------------------------------------------------------------


def get_mcp_app() -> tuple[StreamableHTTPSessionManager, ASGIApp]:
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
