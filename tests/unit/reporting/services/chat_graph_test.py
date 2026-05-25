from mcp.types import GetPromptResult, Prompt, PromptMessage, TextContent, Tool

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import User
from reporting.services import chat_graph

_NOW = "2024-01-01T00:00:00+00:00"


def _user() -> CurrentUser:
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
        permissions=frozenset(
            {
                Permission.CHAT_TOOLS_CALL.value,
                Permission.TOOLS_CALL.value,
                Permission.CHAT_SKILLS_CALL.value,
                Permission.SKILLS_RENDER.value,
            }
        ),
    )


async def test_chat_graph_lists_mcp_tools_with_chat_gate(mocker):
    list_tools = mocker.patch(
        "reporting.services.chat_graph.mcp_runtime.list_tools_for_user",
        return_value=[Tool(name="security__lookup", description="Lookup data", inputSchema={"type": "object"})],
    )
    current = _user()

    response = await chat_graph._build_response("/tools", current)

    list_tools.assert_awaited_once_with(
        current,
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )
    assert "security__lookup" in response


async def test_chat_graph_calls_mcp_tool_with_chat_gate(mocker):
    call_tool = mocker.patch(
        "reporting.services.chat_graph.mcp_runtime.call_tool_for_user",
        return_value=[TextContent(type="text", text='{"ok": true}')],
    )
    current = _user()

    response = await chat_graph._build_response('/tool security__lookup {"limit": 3}', current)

    call_tool.assert_awaited_once_with(
        current,
        "security__lookup",
        {"limit": 3},
        gate_permission=Permission.CHAT_TOOLS_CALL,
        chat_safe_only=True,
    )
    assert response == '{"ok": true}'


async def test_chat_graph_rejects_non_json_tool_arguments():
    response = await chat_graph._build_response("/tool security__lookup not-json", _user())

    assert response == "Arguments must be a JSON object."


async def test_chat_graph_lists_mcp_skills_with_chat_gate(mocker):
    list_prompts = mocker.patch(
        "reporting.services.chat_graph.mcp_runtime.list_prompts_for_user",
        return_value=[Prompt(name="security__summarize", description="Summarize data", arguments=[])],
    )
    current = _user()

    response = await chat_graph._build_response("/skills", current)

    list_prompts.assert_awaited_once_with(current, gate_permission=Permission.CHAT_SKILLS_CALL)
    assert "security__summarize" in response


async def test_chat_graph_renders_mcp_skill_with_chat_gate(mocker):
    get_prompt = mocker.patch(
        "reporting.services.chat_graph.mcp_runtime.get_prompt_for_user",
        return_value=GetPromptResult(
            messages=[PromptMessage(role="user", content=TextContent(type="text", text="Summarize alerts."))]
        ),
    )
    current = _user()

    response = await chat_graph._build_response('/skill security__summarize {"topic": "alerts"}', current)

    get_prompt.assert_awaited_once_with(
        current,
        "security__summarize",
        {"topic": "alerts"},
        gate_permission=Permission.CHAT_SKILLS_CALL,
    )
    assert response == "Summarize alerts."
