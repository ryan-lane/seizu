"""Tests for the MCP built-in registry (filtering + group resolution)."""
from reporting.services.mcp_builtins import all_group_names
from reporting.services.mcp_builtins import find_builtin
from reporting.services.mcp_builtins import list_builtin_tools


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
