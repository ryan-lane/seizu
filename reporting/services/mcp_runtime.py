"""In-process MCP runtime helpers shared by MCP transport and chat agents."""

import json
import logging
from typing import Any

from mcp.types import GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent, Tool

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.routes.query import _serialize_neo4j_value
from reporting.schema.mcp_config import render_skill_prompt, validate_tool_arguments
from reporting.services import report_store, reporting_neo4j
from reporting.services.mcp_builtins import find_builtin, list_builtin_tools

logger = logging.getLogger(__name__)

_PARAM_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
}

# Non-mutating permissions: reads/inspection, skill rendering (returns text),
# and tool calls (user-defined tools run Cypher that is validated read-only at
# create/update time — strictly more constrained than the arbitrary read
# queries QUERY_EXECUTE already allows). A built-in is exposed to chat only
# when *every* permission it requires is in this set, so a newly added tool
# guarded by a write/delete (or any unrecognised) permission is excluded from
# chat by default. This is fail-closed: forgetting to classify a new mutating
# tool hides it from chat rather than silently exposing it, which a denylist
# would.
_CHAT_SAFE_PERMISSIONS: frozenset[str] = frozenset(
    {
        Permission.REPORTS_READ.value,
        Permission.QUERY_EXECUTE.value,
        Permission.QUERY_VALIDATE.value,
        Permission.QUERY_HISTORY_READ.value,
        Permission.TOOLSETS_READ.value,
        Permission.TOOLS_READ.value,
        Permission.TOOLS_CALL.value,
        Permission.SKILLSETS_READ.value,
        Permission.SKILLS_READ.value,
        Permission.SKILLS_RENDER.value,
        Permission.SCHEDULED_QUERIES_READ.value,
        Permission.USERS_READ.value,
        Permission.ROLES_READ.value,
    }
)


def build_input_schema(parameters: list[Any]) -> dict[str, Any]:
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


def text_response(payload: Any) -> list[TextContent]:
    """Serialize *payload* to JSON and wrap it as a single MCP TextContent."""
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def missing_permissions(required: list[str], granted: frozenset[str]) -> list[str]:
    return [p for p in required if p not in granted]


def parse_user_defined_name(name: str) -> tuple[str, str] | None:
    parts = name.split("__", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def _is_chat_safe_builtin(required_permissions: list[str]) -> bool:
    return bool(required_permissions) and set(required_permissions) <= _CHAT_SAFE_PERMISSIONS


def _permissions(current_user: CurrentUser | None, permissions: frozenset[str] | None) -> frozenset[str]:
    if permissions is not None:
        return permissions
    return current_user.permissions if current_user is not None else frozenset()


async def list_tools_for_user(
    current_user: CurrentUser | None,
    *,
    gate_permission: Permission | None = None,
    permissions: frozenset[str] | None = None,
    chat_safe_only: bool = False,
) -> list[Tool]:
    perms = _permissions(current_user, permissions)
    if gate_permission and gate_permission.value not in perms:
        return []

    tools: list[Tool] = []
    for builtin in list_builtin_tools():
        if chat_safe_only and not _is_chat_safe_builtin(builtin.required_permissions):
            continue
        if missing_permissions(builtin.required_permissions, perms):
            continue
        tools.append(
            Tool(
                name=builtin.name,
                description=builtin.description,
                inputSchema=builtin.input_schema,
            )
        )

    try:
        enabled_tools = await report_store.list_enabled_tools()
        for tool in enabled_tools:
            tools.append(
                Tool(
                    name=f"{tool.toolset_id}__{tool.tool_id}",
                    description=tool.description or f"{tool.name} tool",
                    inputSchema=build_input_schema(tool.parameters),
                )
            )
    except Exception:
        logger.exception("Failed to load tools from store for MCP listing")

    return tools


async def call_tool_for_user(
    current_user: CurrentUser | None,
    name: str,
    arguments: dict[str, Any] | None,
    *,
    gate_permission: Permission | None = None,
    permissions: frozenset[str] | None = None,
    chat_safe_only: bool = False,
    result_max_rows: int | None = None,
    result_max_bytes: int | None = None,
) -> list[TextContent]:
    args = arguments or {}
    perms = _permissions(current_user, permissions)
    if gate_permission and gate_permission.value not in perms:
        return text_response({"error": f"Permission denied: {gate_permission.value}"})

    builtin = find_builtin(name)
    if builtin is not None:
        if chat_safe_only and not _is_chat_safe_builtin(builtin.required_permissions):
            return text_response({"error": f"Tool '{name}' is not available to chat"})
        missing = missing_permissions(builtin.required_permissions, perms)
        if missing:
            return text_response({"error": f"Permission denied: {', '.join(missing)}"})
        try:
            result = await builtin.handler(args, current_user)
            return _bounded_text_response(
                result,
                max_rows=result_max_rows,
                max_bytes=result_max_bytes,
            )
        except Exception:
            logger.exception("Failed to execute built-in MCP tool %s", name)
            return text_response({"error": f"Failed to execute tool '{name}'"})

    if Permission.TOOLS_CALL.value not in perms:
        return text_response({"error": f"Permission denied: {Permission.TOOLS_CALL.value}"})
    try:
        parsed_name = parse_user_defined_name(name)
        target_tool = await report_store.get_enabled_tool(parsed_name[0], parsed_name[1]) if parsed_name else None
        if target_tool is None:
            return text_response({"error": f"Tool '{name}' not found"})

        arg_errors = validate_tool_arguments(target_tool.parameters, args)
        if arg_errors:
            return text_response({"errors": arg_errors})

        params_with_defaults = {p.name: p.default for p in target_tool.parameters}
        params_with_defaults.update(args)

        results = await reporting_neo4j.run_query(target_tool.cypher, parameters=params_with_defaults)
        serialized = [{key: _serialize_neo4j_value(value) for key, value in record.items()} for record in results]
        return _bounded_text_response(
            serialized,
            max_rows=result_max_rows,
            max_bytes=result_max_bytes,
        )
    except Exception:
        logger.exception("Failed to execute MCP tool %s", name)
        return text_response({"error": f"Failed to execute tool '{name}'"})


async def list_prompts_for_user(
    current_user: CurrentUser | None,
    *,
    gate_permission: Permission | None = None,
    permissions: frozenset[str] | None = None,
) -> list[Prompt]:
    perms = _permissions(current_user, permissions)
    if gate_permission and gate_permission.value not in perms:
        return []
    if Permission.SKILLS_RENDER.value not in perms:
        return []

    prompts: list[Prompt] = []
    try:
        enabled_skills = await report_store.list_enabled_skills()
        for skill in enabled_skills:
            prompts.append(
                Prompt(
                    name=f"{skill.skillset_id}__{skill.skill_id}",
                    title=skill.name,
                    description=skill.description or f"{skill.name} skill",
                    arguments=[
                        PromptArgument(
                            name=p.name,
                            description=p.description or None,
                            required=p.required and p.default is None,
                        )
                        for p in skill.parameters
                    ],
                )
            )
    except Exception:
        logger.exception("Failed to load skills from store for MCP prompt listing")
    return prompts


async def get_prompt_for_user(
    current_user: CurrentUser | None,
    name: str,
    arguments: dict[str, str] | None,
    *,
    gate_permission: Permission | None = None,
    permissions: frozenset[str] | None = None,
) -> GetPromptResult:
    perms = _permissions(current_user, permissions)
    if gate_permission and gate_permission.value not in perms:
        return _permission_denied_prompt(gate_permission.value)
    if Permission.SKILLS_RENDER.value not in perms:
        return _permission_denied_prompt(Permission.SKILLS_RENDER.value)

    try:
        parsed_name = parse_user_defined_name(name)
        target_skill = await report_store.get_enabled_skill(parsed_name[0], parsed_name[1]) if parsed_name else None
        if target_skill is None:
            return GetPromptResult(
                description="Skill not found",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=f"Skill '{name}' not found"),
                    )
                ],
            )
        rendered, errors = render_skill_prompt(
            target_skill.parameters,
            target_skill.template,
            arguments or {},
            target_skill.triggers,
            target_skill.tools_required,
        )
        text = rendered if rendered is not None else json.dumps({"errors": errors}, indent=2)
        return GetPromptResult(
            description=target_skill.description or target_skill.name,
            messages=[PromptMessage(role="user", content=TextContent(type="text", text=text))],
        )
    except Exception:
        logger.exception("Failed to render MCP prompt %s", name)
        return GetPromptResult(
            description="Skill render failed",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=f"Failed to render skill '{name}'"),
                )
            ],
        )


def _permission_denied_prompt(permission: str) -> GetPromptResult:
    return GetPromptResult(
        description="Permission denied",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(type="text", text=f"Permission denied: {permission}"),
            )
        ],
    )


def _bounded_text_response(
    payload: Any,
    *,
    max_rows: int | None,
    max_bytes: int | None,
) -> list[TextContent]:
    bounded = payload
    if max_rows is not None and max_rows > 0 and isinstance(payload, list) and len(payload) > max_rows:
        bounded = {
            "results": payload[:max_rows],
            "truncated": True,
            "truncated_reason": "row_limit",
            "max_rows": max_rows,
        }

    text = json.dumps(bounded, indent=2, default=str)
    if max_bytes is not None and max_bytes > 0 and len(text.encode("utf-8")) > max_bytes:
        bounded = {
            "error": "Tool result exceeded chat size limit",
            "truncated": True,
            "truncated_reason": "byte_limit",
            "max_bytes": max_bytes,
        }
        text = json.dumps(bounded, indent=2, default=str)
    return [TextContent(type="text", text=text)]
