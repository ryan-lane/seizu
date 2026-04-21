"""Unit tests for reporting/services/mcp_server.py."""
import json
from unittest.mock import AsyncMock
from unittest.mock import patch

from mcp import types as mcp_types

from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolParamDef
from reporting.schema.mcp_config import ToolsetListItem
from reporting.services import mcp_server as mcp_module
from reporting.services.mcp_server import _build_mcp_server
from reporting.services.mcp_server import _build_oauth_metadata
from reporting.services.mcp_server import _mcp_permissions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = "2024-01-01T00:00:00+00:00"


def _toolset(toolset_id: str = "ts1", name: str = "mytoolset", enabled: bool = True):
    return ToolsetListItem(
        toolset_id=toolset_id,
        name=name,
        description="",
        enabled=enabled,
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
        created_by="user@example.com",
    )


def _tool(
    tool_id: str = "t1",
    toolset_id: str = "ts1",
    name: str = "mytool",
    enabled: bool = True,
    parameters=None,
    cypher: str = "MATCH (n) RETURN n LIMIT 1",
):
    return ToolItem(
        tool_id=tool_id,
        toolset_id=toolset_id,
        name=name,
        description="A test tool",
        cypher=cypher,
        parameters=parameters or [],
        enabled=enabled,
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
        created_by="user@example.com",
    )


async def _list_tools(server, permissions=ALL_PERMISSIONS):
    """Call the registered list_tools handler."""
    handler = server.request_handlers[mcp_types.ListToolsRequest]
    req = mcp_types.ListToolsRequest(method="tools/list", params=None)
    token = _mcp_permissions.set(permissions)
    try:
        result = await handler(req)
    finally:
        _mcp_permissions.reset(token)
    return result.root.tools


async def _call_tool(server, name, arguments=None, permissions=ALL_PERMISSIONS):
    """Call the registered call_tool handler and return the text content list."""
    handler = server.request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name=name, arguments=arguments or {}),
    )
    token = _mcp_permissions.set(permissions)
    try:
        result = await handler(req)
    finally:
        _mcp_permissions.reset(token)
    return result.root.content


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------


async def test_list_tools_includes_builtin_schema_tool():
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        server = _build_mcp_server()
        tools = await _list_tools(server)
        names = [t.name for t in tools]
        assert "graph__schema" in names
        assert "graph__query" in names


async def test_list_tools_includes_user_defined_tool():
    ts = _toolset()
    tool = _tool()
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[tool],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[ts],
        ),
    ):
        server = _build_mcp_server()
        tools = await _list_tools(server)
        names = [t.name for t in tools]
        assert "mytoolset__mytool" in names


async def test_list_tools_with_parameters_builds_schema():
    ts = _toolset()
    tool = _tool(
        parameters=[
            ToolParamDef(
                name="limit",
                type="integer",
                description="Max rows",
                required=True,
            )
        ]
    )
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[tool],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[ts],
        ),
    ):
        server = _build_mcp_server()
        tools = await _list_tools(server)
        user_tool = next(t for t in tools if t.name == "mytoolset__mytool")
        assert "limit" in user_tool.inputSchema["properties"]
        assert user_tool.inputSchema["required"] == ["limit"]


async def test_list_tools_store_error_returns_builtins_only():
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        server = _build_mcp_server()
        tools = await _list_tools(server)
        names = [t.name for t in tools]
        assert "graph__schema" in names
        assert "graph__query" in names
        # All tool names follow the <group>__<action> convention — no user
        # tools were added because the store raised.
        assert all("__" in n for n in names)
        # Every surfaced tool is from a built-in group.
        from reporting.services.mcp_builtins import list_builtin_tools

        builtin_names = {t.name for t in list_builtin_tools()}
        assert set(names) <= builtin_names


# ---------------------------------------------------------------------------
# call_tool — graph__query
# ---------------------------------------------------------------------------


async def test_call_tool_query_empty_query_string():
    # MCP library validates required params; an empty-string query bypasses that
    # and triggers our own guard inside the handler.
    server = _build_mcp_server()
    result = await _call_tool(server, "graph__query", {"query": "  "})
    data = json.loads(result[0].text)
    assert "error" in data


async def test_call_tool_query_validation_error():
    from reporting.services.query_validator import ValidationResult

    with patch(
        "reporting.services.mcp_builtins.graph.validate_query",
        new_callable=AsyncMock,
        return_value=ValidationResult(errors=["syntax error"], warnings=[]),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "graph__query", {"query": "BAD CYPHER"})
        data = json.loads(result[0].text)
        assert "errors" in data
        assert "syntax error" in data["errors"]


async def test_call_tool_query_success():
    from reporting.services.query_validator import ValidationResult

    with (
        patch(
            "reporting.services.mcp_builtins.graph.validate_query",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ),
        patch(
            "reporting.services.mcp_builtins.graph.reporting_neo4j.run_query",
            new_callable=AsyncMock,
            return_value=[{"n": 1}],
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(
            server, "graph__query", {"query": "MATCH (n) RETURN n"}
        )
        data = json.loads(result[0].text)
        assert "results" in data
        assert data["results"][0]["n"] == 1


async def test_call_tool_query_execution_error():
    from reporting.services.query_validator import ValidationResult

    with (
        patch(
            "reporting.services.mcp_builtins.graph.validate_query",
            new_callable=AsyncMock,
            return_value=ValidationResult(errors=[], warnings=[]),
        ),
        patch(
            "reporting.services.mcp_builtins.graph.reporting_neo4j.run_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError("neo4j down"),
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(
            server, "graph__query", {"query": "MATCH (n) RETURN n"}
        )
        data = json.loads(result[0].text)
        assert "error" in data


# ---------------------------------------------------------------------------
# call_tool — graph__schema
# ---------------------------------------------------------------------------


async def test_call_tool_schema_success():
    with patch(
        "reporting.services.mcp_builtins.graph.reporting_neo4j.run_query",
        new_callable=AsyncMock,
        side_effect=[
            [{"label": "Person"}],
            [{"type": "KNOWS"}],
            [{"key": "name"}],
        ],
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "graph__schema", {})
        data = json.loads(result[0].text)
        assert data["labels"] == ["Person"]
        assert data["relationship_types"] == ["KNOWS"]
        assert data["property_keys"] == ["name"]


async def test_call_tool_schema_error():
    with patch(
        "reporting.services.mcp_builtins.graph.reporting_neo4j.run_query",
        new_callable=AsyncMock,
        side_effect=RuntimeError("neo4j down"),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "graph__schema", {})
        data = json.loads(result[0].text)
        assert "error" in data


# ---------------------------------------------------------------------------
# call_tool — user-defined tool
# ---------------------------------------------------------------------------


async def test_call_tool_user_defined_not_found():
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "unknown__tool", {})
        data = json.loads(result[0].text)
        assert "error" in data
        assert "not found" in data["error"]


async def test_call_tool_user_defined_argument_validation_error():
    # MCP validates input schema before our handler; wrong type → plain text error
    ts = _toolset()
    tool = _tool(
        parameters=[
            ToolParamDef(
                name="limit",
                type="integer",
                required=True,
            )
        ]
    )
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[tool],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[ts],
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "mytoolset__mytool", {"limit": "not-an-int"})
        assert len(result) == 1
        assert "integer" in result[0].text or "validation" in result[0].text.lower()


async def test_call_tool_user_defined_success():
    ts = _toolset()
    tool = _tool()
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[tool],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[ts],
        ),
        patch(
            "reporting.services.mcp_server.reporting_neo4j.run_query",
            new_callable=AsyncMock,
            return_value=[{"n": "value"}],
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "mytoolset__mytool", {})
        data = json.loads(result[0].text)
        assert data[0]["n"] == "value"


async def test_call_tool_user_defined_execution_error():
    ts = _toolset()
    tool = _tool()
    with (
        patch(
            "reporting.services.mcp_server.report_store.list_enabled_tools",
            new_callable=AsyncMock,
            return_value=[tool],
        ),
        patch(
            "reporting.services.mcp_server.report_store.list_toolsets",
            new_callable=AsyncMock,
            return_value=[ts],
        ),
        patch(
            "reporting.services.mcp_server.reporting_neo4j.run_query",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db error"),
        ),
    ):
        server = _build_mcp_server()
        result = await _call_tool(server, "mytoolset__mytool", {})
        data = json.loads(result[0].text)
        assert "error" in data


# ---------------------------------------------------------------------------
# _build_oauth_metadata
# ---------------------------------------------------------------------------


def test_build_oauth_metadata_returns_none_when_not_configured():
    with (
        patch.object(mcp_module.settings, "MCP_OAUTH_AUTHORIZATION_ENDPOINT", ""),
        patch.object(mcp_module.settings, "MCP_OAUTH_TOKEN_ENDPOINT", ""),
    ):
        assert _build_oauth_metadata() is None


def test_build_oauth_metadata_returns_dict_when_configured():
    with (
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_AUTHORIZATION_ENDPOINT",
            "https://idp.example.com/authorize",
        ),
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_TOKEN_ENDPOINT",
            "https://idp.example.com/token",
        ),
        patch.object(
            mcp_module.settings, "MCP_OAUTH_ISSUER", "https://idp.example.com"
        ),
        patch.object(mcp_module.settings, "JWT_ISSUER", ""),
        patch.object(mcp_module.settings, "OIDC_SCOPE", "openid email"),
        patch.object(mcp_module.settings, "JWKS_URL", ""),
    ):
        result = _build_oauth_metadata()
        assert result is not None
        assert result["authorization_endpoint"] == "https://idp.example.com/authorize"
        assert result["token_endpoint"] == "https://idp.example.com/token"
        assert result["issuer"] == "https://idp.example.com"
        assert "S256" in result["code_challenge_methods_supported"]


def test_build_oauth_metadata_falls_back_to_jwt_issuer():
    with (
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_AUTHORIZATION_ENDPOINT",
            "https://idp.example.com/authorize",
        ),
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_TOKEN_ENDPOINT",
            "https://idp.example.com/token",
        ),
        patch.object(mcp_module.settings, "MCP_OAUTH_ISSUER", ""),
        patch.object(
            mcp_module.settings, "JWT_ISSUER", "https://idp.example.com/fallback"
        ),
        patch.object(mcp_module.settings, "OIDC_SCOPE", "openid email"),
        patch.object(mcp_module.settings, "JWKS_URL", ""),
    ):
        result = _build_oauth_metadata()
        assert result is not None
        assert result["issuer"] == "https://idp.example.com/fallback"


def test_build_oauth_metadata_includes_jwks_uri_when_set():
    with (
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_AUTHORIZATION_ENDPOINT",
            "https://idp.example.com/authorize",
        ),
        patch.object(
            mcp_module.settings,
            "MCP_OAUTH_TOKEN_ENDPOINT",
            "https://idp.example.com/token",
        ),
        patch.object(
            mcp_module.settings, "MCP_OAUTH_ISSUER", "https://idp.example.com"
        ),
        patch.object(mcp_module.settings, "JWT_ISSUER", ""),
        patch.object(mcp_module.settings, "OIDC_SCOPE", "openid email"),
        patch.object(mcp_module.settings, "JWKS_URL", "https://idp.example.com/jwks"),
    ):
        result = _build_oauth_metadata()
        assert result is not None
        assert result["jwks_uri"] == "https://idp.example.com/jwks"


# ---------------------------------------------------------------------------
# _MCPAuthMiddleware
# ---------------------------------------------------------------------------


async def test_auth_middleware_passes_through_when_auth_disabled():
    from reporting.services.mcp_server import _MCPAuthMiddleware

    inner = AsyncMock()
    middleware = _MCPAuthMiddleware(inner)

    with patch.object(mcp_module.settings, "DEVELOPMENT_ONLY_REQUIRE_AUTH", False):
        scope = {"type": "http", "path": "/mcp"}
        await middleware(scope, AsyncMock(), AsyncMock())

    inner.assert_called_once()


async def test_auth_middleware_passes_well_known_unauthenticated():
    from reporting.services.mcp_server import _MCPAuthMiddleware

    inner = AsyncMock()
    middleware = _MCPAuthMiddleware(inner)

    with patch.object(mcp_module.settings, "DEVELOPMENT_ONLY_REQUIRE_AUTH", True):
        scope = {
            "type": "http",
            "path": "/.well-known/oauth-authorization-server",
            "headers": [],
        }
        await middleware(scope, AsyncMock(), AsyncMock())

    inner.assert_called_once()


async def test_auth_middleware_returns_401_when_no_token():
    from reporting.services.mcp_server import _MCPAuthMiddleware

    inner = AsyncMock()
    middleware = _MCPAuthMiddleware(inner)

    with patch.object(mcp_module.settings, "DEVELOPMENT_ONLY_REQUIRE_AUTH", True):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mcp",
            "headers": [],
            "query_string": b"",
        }
        receive = AsyncMock(return_value={"type": "http.request", "body": b""})
        sent = []

        async def capture_send(message):
            sent.append(message)

        await middleware(scope, receive, capture_send)

    status_messages = [m for m in sent if m.get("type") == "http.response.start"]
    assert any(m.get("status") == 401 for m in status_messages)


async def test_auth_middleware_passes_non_http_scope():
    from reporting.services.mcp_server import _MCPAuthMiddleware

    inner = AsyncMock()
    middleware = _MCPAuthMiddleware(inner)

    scope = {"type": "lifespan"}
    await middleware(scope, AsyncMock(), AsyncMock())

    inner.assert_called_once()
