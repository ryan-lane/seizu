import json

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.schema.mcp_config import SkillItem, ToolItem, ToolParamDef
from reporting.schema.report_config import User
from reporting.services import mcp_runtime

_NOW = "2024-01-01T00:00:00+00:00"


def _user(permissions: frozenset[str]) -> CurrentUser:
    return CurrentUser(
        user=User(
            user_id="user-1",
            sub="sub",
            iss="iss",
            email="user@example.com",
            created_at=_NOW,
            last_login=_NOW,
        ),
        jwt_claims={},
        permissions=permissions,
    )


def _tool() -> ToolItem:
    return ToolItem(
        tool_id="lookup",
        toolset_id="security",
        name="Lookup",
        description="Lookup security data",
        cypher="MATCH (n) RETURN n LIMIT $limit",
        parameters=[
            ToolParamDef(
                name="limit",
                type="integer",
                description="Maximum rows",
                required=False,
                default=1,
            )
        ],
        enabled=True,
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
        created_by="user-1",
    )


def _skill() -> SkillItem:
    return SkillItem(
        skill_id="summarize",
        skillset_id="security",
        name="Summarize",
        description="Summarize a topic",
        template="Summarize {% $topic %}.",
        parameters=[ToolParamDef(name="topic", type="string", required=True)],
        enabled=True,
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
        created_by="user-1",
    )


async def test_chat_tool_gate_blocks_listing_before_store_lookup(mocker):
    list_enabled_tools = mocker.patch("reporting.services.mcp_runtime.report_store.list_enabled_tools")
    current = _user(frozenset({Permission.TOOLS_CALL.value}))

    tools = await mcp_runtime.list_tools_for_user(
        current,
        gate_permission=Permission.CHAT_TOOLS_CALL,
    )

    assert tools == []
    list_enabled_tools.assert_not_called()


async def test_chat_tool_gate_blocks_call_before_store_lookup(mocker):
    get_enabled_tool = mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_tool")
    current = _user(frozenset({Permission.TOOLS_CALL.value}))

    result = await mcp_runtime.call_tool_for_user(
        current,
        "security__lookup",
        {},
        gate_permission=Permission.CHAT_TOOLS_CALL,
    )

    assert json.loads(result[0].text) == {"error": "Permission denied: chat:tools:call"}
    get_enabled_tool.assert_not_called()


async def test_tool_call_still_requires_underlying_mcp_permission(mocker):
    get_enabled_tool = mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_tool")
    current = _user(frozenset({Permission.CHAT_TOOLS_CALL.value}))

    result = await mcp_runtime.call_tool_for_user(
        current,
        "security__lookup",
        {},
        gate_permission=Permission.CHAT_TOOLS_CALL,
    )

    assert json.loads(result[0].text) == {"error": "Permission denied: tools:call"}
    get_enabled_tool.assert_not_called()


async def test_chat_tool_call_uses_mcp_acl_and_executes_user_defined_tool(mocker):
    mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_tool", return_value=_tool())
    run_query = mocker.patch(
        "reporting.services.mcp_runtime.reporting_neo4j.run_query",
        return_value=[{"name": "node-1"}],
    )
    current = _user(frozenset({Permission.CHAT_TOOLS_CALL.value, Permission.TOOLS_CALL.value}))

    result = await mcp_runtime.call_tool_for_user(
        current,
        "security__lookup",
        {"limit": 3},
        gate_permission=Permission.CHAT_TOOLS_CALL,
    )

    run_query.assert_awaited_once_with("MATCH (n) RETURN n LIMIT $limit", parameters={"limit": 3})
    assert json.loads(result[0].text) == [{"name": "node-1"}]


async def test_chat_tool_call_applies_row_limit(mocker):
    mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_tool", return_value=_tool())
    mocker.patch(
        "reporting.services.mcp_runtime.reporting_neo4j.run_query",
        return_value=[{"name": "node-1"}, {"name": "node-2"}],
    )
    current = _user(frozenset({Permission.CHAT_TOOLS_CALL.value, Permission.TOOLS_CALL.value}))

    result = await mcp_runtime.call_tool_for_user(
        current,
        "security__lookup",
        {},
        gate_permission=Permission.CHAT_TOOLS_CALL,
        result_max_rows=1,
    )

    assert json.loads(result[0].text) == {
        "results": [{"name": "node-1"}],
        "truncated": True,
        "truncated_reason": "row_limit",
        "max_rows": 1,
    }


async def test_chat_tool_call_applies_byte_limit(mocker):
    mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_tool", return_value=_tool())
    mocker.patch(
        "reporting.services.mcp_runtime.reporting_neo4j.run_query",
        return_value=[{"name": "x" * 100}],
    )
    current = _user(frozenset({Permission.CHAT_TOOLS_CALL.value, Permission.TOOLS_CALL.value}))

    result = await mcp_runtime.call_tool_for_user(
        current,
        "security__lookup",
        {},
        gate_permission=Permission.CHAT_TOOLS_CALL,
        result_max_bytes=20,
    )

    assert json.loads(result[0].text) == {
        "error": "Tool result exceeded chat size limit",
        "truncated": True,
        "truncated_reason": "byte_limit",
        "max_bytes": 20,
    }


async def test_chat_safe_tool_listing_hides_mutating_builtins(mocker):
    mocker.patch("reporting.services.mcp_runtime.report_store.list_enabled_tools", return_value=[])
    current = _user(
        frozenset(
            {
                Permission.CHAT_TOOLS_CALL.value,
                Permission.REPORTS_READ.value,
                Permission.REPORTS_WRITE.value,
            }
        )
    )

    tools = await mcp_runtime.list_tools_for_user(
        current,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )

    names = {tool.name for tool in tools}
    assert "reports__list" in names
    assert "reports__create" not in names


async def test_chat_safe_tool_call_rejects_mutating_builtin_before_handler():
    current = _user(
        frozenset(
            {
                Permission.CHAT_TOOLS_CALL.value,
                Permission.REPORTS_WRITE.value,
            }
        )
    )

    result = await mcp_runtime.call_tool_for_user(
        current,
        "reports__create",
        {},
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )

    assert json.loads(result[0].text) == {"error": "Tool 'reports__create' is not available to chat"}


async def test_chat_skill_gate_blocks_listing_before_store_lookup(mocker):
    list_enabled_skills = mocker.patch("reporting.services.mcp_runtime.report_store.list_enabled_skills")
    current = _user(frozenset({Permission.SKILLS_RENDER.value}))

    prompts = await mcp_runtime.list_prompts_for_user(
        current,
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )

    assert prompts == []
    list_enabled_skills.assert_not_called()


async def test_skill_render_still_requires_underlying_mcp_permission(mocker):
    get_enabled_skill = mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_skill")
    current = _user(frozenset({Permission.CHAT_SKILLS_CALL.value}))

    result = await mcp_runtime.get_prompt_for_user(
        current,
        "security__summarize",
        {"topic": "alerts"},
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )

    assert result.messages[0].content.text == "Permission denied: skills:render"
    get_enabled_skill.assert_not_called()


async def test_chat_skill_render_uses_mcp_acl_and_renders_prompt(mocker):
    mocker.patch("reporting.services.mcp_runtime.report_store.get_enabled_skill", return_value=_skill())
    current = _user(frozenset({Permission.CHAT_SKILLS_CALL.value, Permission.SKILLS_RENDER.value}))

    result = await mcp_runtime.get_prompt_for_user(
        current,
        "security__summarize",
        {"topic": "alerts"},
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )

    assert result.messages[0].content.text == "Summarize alerts."
