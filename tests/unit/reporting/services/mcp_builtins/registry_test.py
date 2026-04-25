"""Tests for the MCP built-in registry (filtering + group resolution)."""
import json

import mcp.types as mcp_types
import pytest

from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.services.mcp_builtins import all_group_names
from reporting.services.mcp_builtins import find_builtin
from reporting.services.mcp_builtins import list_builtin_tools
from reporting.services.mcp_server import _build_mcp_server
from reporting.services.mcp_server import _mcp_permissions


def test_all_group_names_includes_known_groups():
    groups = all_group_names()
    assert "graph" in groups
    assert "reports" in groups
    assert "scheduled_queries" in groups
    assert "toolsets" in groups
    assert "roles" in groups


def test_list_builtin_tools_empty_filter_returns_all():
    # An empty / None filter means "all groups" — matches the default in
    # settings.py when the env var is unset.
    all_tools = list_builtin_tools(None)
    assert {t.group for t in all_tools} == set(all_group_names())


def test_list_builtin_tools_filters_by_group():
    tools = list_builtin_tools(["graph"])
    assert {t.group for t in tools} == {"graph"}
    assert {t.name for t in tools} == {"graph__schema", "graph__query"}


def test_find_builtin_returns_tool():
    tool = find_builtin("reports__list")
    assert tool is not None
    assert tool.group == "reports"


def test_find_builtin_respects_group_filter():
    # Reports group disabled — lookup should miss even though the tool exists.
    assert find_builtin("reports__list", ["graph"]) is None


def test_find_builtin_unknown_name_returns_none():
    assert find_builtin("nonexistent__tool") is None


def test_every_builtin_has_required_permissions():
    # A tool without any permission requirement would bypass RBAC entirely —
    # guard against accidentally adding one.
    for tool in list_builtin_tools():
        assert tool.required_permissions, f"{tool.name} is missing required_permissions"


@pytest.mark.parametrize(
    "tool",
    list_builtin_tools(),
    ids=lambda t: t.name,
)
async def test_each_builtin_enforces_its_required_permission(tool):
    """Calling a tool without its required permission returns Permission denied."""
    insufficient = frozenset(ALL_PERMISSIONS) - frozenset(tool.required_permissions)
    server = _build_mcp_server()
    handler = server.request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name=tool.name, arguments={}),
    )
    tok = _mcp_permissions.set(insufficient)
    try:
        result = await handler(req)
    finally:
        _mcp_permissions.reset(tok)
    data = json.loads(result.root.content[0].text)
    assert (
        "Permission denied" in data["error"]
    ), f"{tool.name}: expected permission denial for {tool.required_permissions}, got: {data}"
