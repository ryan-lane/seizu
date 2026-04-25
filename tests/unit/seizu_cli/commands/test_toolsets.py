"""Tests for seizu_cli.commands.toolsets (toolsets + nested tools)."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from seizu_cli.client import APIError
from seizu_cli.commands.toolsets import app

runner = CliRunner()


@pytest.fixture
def mock_client(mocker: pytest.MonkeyPatch) -> MagicMock:
    mc = MagicMock()
    mocker.patch("seizu_cli.state.get_client", return_value=mc)
    return mc


def _toolset_item(
    toolset_id: str = "ts1",
    name: str = "My Toolset",
    description: str = "A toolset",
    enabled: bool = True,
    current_version: int = 1,
    updated_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    return {
        "toolset_id": toolset_id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "current_version": current_version,
        "updated_at": updated_at,
    }


def _toolset_detail(
    toolset_id: str = "ts1",
    name: str = "My Toolset",
    description: str = "A toolset",
    enabled: bool = True,
    version: int = 1,
    created_by: str = "user@example.com",
) -> dict:
    return {
        "toolset_id": toolset_id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "version": version,
        "created_by": created_by,
    }


def _tool_item(
    tool_id: str = "tool1",
    name: str = "My Tool",
    description: str = "A tool",
    enabled: bool = True,
    current_version: int = 1,
    updated_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    return {
        "tool_id": tool_id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "current_version": current_version,
        "updated_at": updated_at,
    }


def _tool_detail(
    tool_id: str = "tool1",
    toolset_id: str = "ts1",
    name: str = "My Tool",
    description: str = "A tool",
    enabled: bool = True,
    version: int = 1,
    created_by: str = "user@example.com",
    cypher: str = "MATCH (n) RETURN n",
    parameters: list = None,
) -> dict:
    return {
        "tool_id": tool_id,
        "toolset_id": toolset_id,
        "name": name,
        "description": description,
        "enabled": enabled,
        "version": version,
        "created_by": created_by,
        "cypher": cypher,
        "parameters": parameters or [],
    }


# ===========================================================================
# Toolset commands
# ===========================================================================


def test_list_toolsets_empty(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"toolsets": []}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No toolsets found" in result.output


def test_list_toolsets_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"toolsets": [_toolset_item()]}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "ts1" in result.output
    assert "My Toolset" in result.output


def test_list_toolsets_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"toolsets": [_toolset_item()]}
    result = runner.invoke(app, ["list", "--output", "json"])
    assert result.exit_code == 0
    assert '"toolset_id"' in result.output


def test_list_toolsets_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(500, "server error")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 1


def test_get_toolset_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _toolset_detail()
    result = runner.invoke(app, ["get", "ts1"])
    assert result.exit_code == 0
    assert "ts1" in result.output
    assert "My Toolset" in result.output
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1")


def test_get_toolset_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _toolset_detail()
    result = runner.invoke(app, ["get", "ts1", "--output", "json"])
    assert result.exit_code == 0
    assert '"toolset_id"' in result.output


def test_get_toolset_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["get", "ts1"])
    assert result.exit_code == 1


def test_create_toolset(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"toolset_id": "ts-new", "name": "New Toolset"}
    result = runner.invoke(app, ["create", "New Toolset", "--description", "Desc"])
    assert result.exit_code == 0
    assert "ts-new" in result.output
    mock_client.post.assert_called_once_with(
        "/api/v1/toolsets",
        json={"name": "New Toolset", "description": "Desc", "enabled": True},
    )


def test_create_toolset_disabled(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"toolset_id": "ts-new", "name": "Disabled"}
    runner.invoke(app, ["create", "Disabled", "--disabled"])
    _, call_kwargs = mock_client.post.call_args
    assert call_kwargs["json"]["enabled"] is False


def test_create_toolset_api_error(mock_client: MagicMock) -> None:
    mock_client.post.side_effect = APIError(422, "error")
    result = runner.invoke(app, ["create", "Bad"])
    assert result.exit_code == 1


def test_update_toolset(mock_client: MagicMock) -> None:
    mock_client.put.return_value = _toolset_detail(name="Updated")
    result = runner.invoke(app, ["update", "ts1", "--name", "Updated"])
    assert result.exit_code == 0
    mock_client.put.assert_called_once_with(
        "/api/v1/toolsets/ts1",
        json={
            "name": "Updated",
            "description": "",
            "enabled": True,
            "comment": None,
        },
    )


def test_update_toolset_with_comment(mock_client: MagicMock) -> None:
    mock_client.put.return_value = _toolset_detail()
    runner.invoke(app, ["update", "ts1", "--name", "x", "--comment", "my note"])
    _, call_kwargs = mock_client.put.call_args
    assert call_kwargs["json"]["comment"] == "my note"


def test_delete_toolset_with_yes(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["delete", "ts1", "--yes"])
    assert result.exit_code == 0
    assert "ts1" in result.output
    mock_client.delete.assert_called_once_with("/api/v1/toolsets/ts1")


def test_delete_toolset_aborts_on_no(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["delete", "ts1"], input="n\n")
    assert result.exit_code != 0
    mock_client.delete.assert_not_called()


def test_toolset_versions(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {
        "versions": [
            {
                "version": 1,
                "created_by": "user@example.com",
                "created_at": "2024-01-01T00:00:00Z",
                "comment": "",
            }
        ]
    }
    result = runner.invoke(app, ["versions", "ts1"])
    assert result.exit_code == 0
    assert "user@example.com" in result.output
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/versions")


def test_toolset_version_get(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _toolset_detail(version=2)
    result = runner.invoke(app, ["version-get", "ts1", "2"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/versions/2")


# ===========================================================================
# Tool commands (nested under "tools")
# ===========================================================================


def test_list_tools_empty(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"tools": []}
    result = runner.invoke(app, ["tools", "list", "ts1"])
    assert result.exit_code == 0
    assert "No tools found" in result.output


def test_list_tools_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"tools": [_tool_item()]}
    result = runner.invoke(app, ["tools", "list", "ts1"])
    assert result.exit_code == 0
    assert "tool1" in result.output
    assert "My Tool" in result.output
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/tools")


def test_list_tools_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"tools": [_tool_item()]}
    result = runner.invoke(app, ["tools", "list", "ts1", "--output", "json"])
    assert result.exit_code == 0
    assert '"tool_id"' in result.output


def test_list_tools_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["tools", "list", "ts1"])
    assert result.exit_code == 1


def test_get_tool_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _tool_detail()
    result = runner.invoke(app, ["tools", "get", "ts1", "tool1"])
    assert result.exit_code == 0
    assert "tool1" in result.output
    assert "MATCH (n) RETURN n" in result.output
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/tools/tool1")


def test_get_tool_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _tool_detail()
    result = runner.invoke(app, ["tools", "get", "ts1", "tool1", "--output", "json"])
    assert result.exit_code == 0
    assert '"tool_id"' in result.output


def test_create_tool(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"tool_id": "t-new", "name": "New Tool"}
    result = runner.invoke(
        app,
        [
            "tools",
            "create",
            "ts1",
            "--name",
            "New Tool",
            "--cypher",
            "MATCH (n) RETURN n",
            "--description",
            "Desc",
        ],
    )
    assert result.exit_code == 0
    assert "t-new" in result.output
    mock_client.post.assert_called_once_with(
        "/api/v1/toolsets/ts1/tools",
        json={
            "name": "New Tool",
            "description": "Desc",
            "cypher": "MATCH (n) RETURN n",
            "parameters": [],
            "enabled": True,
        },
    )


def test_create_tool_with_parameters(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"tool_id": "t-new", "name": "Parameterized"}
    params_json = '[{"name": "limit", "type": "integer"}]'
    runner.invoke(
        app,
        [
            "tools",
            "create",
            "ts1",
            "--name",
            "Parameterized",
            "--cypher",
            "MATCH (n) RETURN n LIMIT $limit",
            "--parameters",
            params_json,
        ],
    )
    _, call_kwargs = mock_client.post.call_args
    assert call_kwargs["json"]["parameters"] == [{"name": "limit", "type": "integer"}]


def test_create_tool_invalid_parameters_json(mock_client: MagicMock) -> None:
    result = runner.invoke(
        app,
        [
            "tools",
            "create",
            "ts1",
            "--name",
            "Bad",
            "--cypher",
            "MATCH (n) RETURN n",
            "--parameters",
            "not-json",
        ],
    )
    assert result.exit_code == 1
    mock_client.post.assert_not_called()


def test_create_tool_api_error(mock_client: MagicMock) -> None:
    mock_client.post.side_effect = APIError(422, "validation error")
    result = runner.invoke(
        app,
        ["tools", "create", "ts1", "--name", "x", "--cypher", "MATCH (n) RETURN n"],
    )
    assert result.exit_code == 1


def test_update_tool(mock_client: MagicMock) -> None:
    mock_client.put.return_value = _tool_detail(name="Updated Tool")
    result = runner.invoke(
        app,
        [
            "tools",
            "update",
            "ts1",
            "tool1",
            "--name",
            "Updated Tool",
            "--cypher",
            "MATCH (n) RETURN n LIMIT 10",
        ],
    )
    assert result.exit_code == 0
    mock_client.put.assert_called_once_with(
        "/api/v1/toolsets/ts1/tools/tool1",
        json={
            "name": "Updated Tool",
            "description": "",
            "cypher": "MATCH (n) RETURN n LIMIT 10",
            "parameters": [],
            "enabled": True,
            "comment": None,
        },
    )


def test_delete_tool_with_yes(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["tools", "delete", "ts1", "tool1", "--yes"])
    assert result.exit_code == 0
    assert "tool1" in result.output
    mock_client.delete.assert_called_once_with("/api/v1/toolsets/ts1/tools/tool1")


def test_delete_tool_aborts_on_no(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["tools", "delete", "ts1", "tool1"], input="n\n")
    assert result.exit_code != 0
    mock_client.delete.assert_not_called()


def test_call_tool_no_args(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"results": []}
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1"])
    assert result.exit_code == 0
    assert "No results" in result.output
    mock_client.post.assert_called_once_with(
        "/api/v1/toolsets/ts1/tools/tool1/call",
        json={"arguments": {}},
    )


def test_call_tool_with_arg(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"results": [{"name": "Alice", "count": 5}]}
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1", "--arg", "limit=10"])
    assert result.exit_code == 0
    assert "Alice" in result.output
    _, call_kwargs = mock_client.post.call_args
    assert call_kwargs["json"]["arguments"] == {"limit": 10}


def test_call_tool_with_string_arg(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"results": []}
    runner.invoke(app, ["tools", "call", "ts1", "tool1", "--arg", "name=alice"])
    _, call_kwargs = mock_client.post.call_args
    # Non-JSON value treated as plain string
    assert call_kwargs["json"]["arguments"]["name"] == "alice"


def test_call_tool_with_args_json(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"results": []}
    runner.invoke(
        app,
        ["tools", "call", "ts1", "tool1", "--args-json", '{"limit": 5, "name": "x"}'],
    )
    _, call_kwargs = mock_client.post.call_args
    assert call_kwargs["json"]["arguments"] == {"limit": 5, "name": "x"}


def test_call_tool_invalid_args_json(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1", "--args-json", "not-json"])
    assert result.exit_code == 1
    mock_client.post.assert_not_called()


def test_call_tool_invalid_arg_format(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1", "--arg", "no-equals-sign"])
    assert result.exit_code == 1
    mock_client.post.assert_not_called()


def test_call_tool_json_output(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"results": [{"name": "Alice"}]}
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1", "--output", "json"])
    assert result.exit_code == 0
    assert '"results"' in result.output


def test_call_tool_api_error(mock_client: MagicMock) -> None:
    mock_client.post.side_effect = APIError(500, "server error")
    result = runner.invoke(app, ["tools", "call", "ts1", "tool1"])
    assert result.exit_code == 1


def test_tool_versions(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {
        "versions": [
            {
                "version": 1,
                "created_by": "user@example.com",
                "created_at": "2024-01-01T00:00:00Z",
                "comment": "",
            }
        ]
    }
    result = runner.invoke(app, ["tools", "versions", "ts1", "tool1"])
    assert result.exit_code == 0
    assert "user@example.com" in result.output
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/tools/tool1/versions")


def test_tool_version_get(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _tool_detail(version=3)
    result = runner.invoke(app, ["tools", "version-get", "ts1", "tool1", "3"])
    assert result.exit_code == 0
    mock_client.get.assert_called_once_with("/api/v1/toolsets/ts1/tools/tool1/versions/3")
