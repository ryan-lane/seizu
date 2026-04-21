"""Registry of built-in MCP tools.

Each group module (e.g. ``reports``, ``toolsets``) exposes a
``GROUP_DEF: BuiltinGroup``.  The registry flattens them into a single
lookup table keyed by tool name (``<group>__<action>``) and exposes two
helpers used by ``reporting.services.mcp_server``:

* :func:`list_builtin_tools` — tools visible for tool listing, filtered by
  ``MCP_ENABLED_BUILTINS``.
* :func:`find_builtin` — resolve a tool by name, also filtered.
"""
from typing import Dict
from typing import List
from typing import Optional

from reporting.services.mcp_builtins import graph as _graph
from reporting.services.mcp_builtins import reports as _reports
from reporting.services.mcp_builtins import roles as _roles
from reporting.services.mcp_builtins import scheduled_queries as _scheduled_queries
from reporting.services.mcp_builtins import toolsets as _toolsets
from reporting.services.mcp_builtins.base import BuiltinGroup
from reporting.services.mcp_builtins.base import BuiltinTool

# Ordered so ``list_tools`` renders a consistent layout; ``graph`` first
# because it's the ad-hoc catch-all (schema + query), then everything
# alphabetical.
_GROUPS: List[BuiltinGroup] = [
    _graph.GROUP_DEF,
    _reports.GROUP_DEF,
    _roles.GROUP_DEF,
    _scheduled_queries.GROUP_DEF,
    _toolsets.GROUP_DEF,
]

_TOOLS_BY_NAME: Dict[str, BuiltinTool] = {
    tool.name: tool for group in _GROUPS for tool in group.tools
}

_ALL_GROUP_NAMES: List[str] = [g.name for g in _GROUPS]


def all_group_names() -> List[str]:
    """Return every registered group name (for default settings + admin UIs)."""
    return list(_ALL_GROUP_NAMES)


def list_builtin_groups(enabled: Optional[List[str]] = None) -> List[BuiltinGroup]:
    """Return every built-in group that is enabled."""
    allowed = _allowed_groups(enabled)
    if allowed is None:
        return list(_GROUPS)
    return [g for g in _GROUPS if g.name in allowed]


def _allowed_groups(enabled: Optional[List[str]]) -> Optional[set]:
    """Resolve the setting value to a set, or None if all groups are enabled.

    ``None`` or empty list means "all groups" — this is the default in
    ``settings.py``.  A non-empty list restricts to the named groups.
    """
    if not enabled:
        return None
    return set(enabled)


def list_builtin_tools(enabled: Optional[List[str]] = None) -> List[BuiltinTool]:
    """Return every built-in tool whose group is enabled."""
    allowed = _allowed_groups(enabled)
    tools: List[BuiltinTool] = []
    for group in _GROUPS:
        if allowed is not None and group.name not in allowed:
            continue
        tools.extend(group.tools)
    return tools


def find_builtin(
    name: str, enabled: Optional[List[str]] = None
) -> Optional[BuiltinTool]:
    """Look up a built-in tool by name; returns None if the group is disabled."""
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return None
    allowed = _allowed_groups(enabled)
    if allowed is not None and tool.group not in allowed:
        return None
    return tool


__all__ = [
    "BuiltinGroup",
    "BuiltinTool",
    "all_group_names",
    "find_builtin",
    "list_builtin_groups",
    "list_builtin_tools",
]
