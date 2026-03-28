"""Tests for seizu_cli.commands.scheduled_queries."""
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from seizu_cli.client import APIError
from seizu_cli.commands.scheduled_queries import app

runner = CliRunner()


@pytest.fixture
def mock_client(mocker: pytest.MonkeyPatch) -> MagicMock:
    mc = MagicMock()
    mocker.patch("seizu_cli.state.get_client", return_value=mc)
    return mc


def _sq_item(
    scheduled_query_id: str = "sq1",
    name: str = "My Query",
    enabled: bool = True,
    frequency: int = 3600,
    current_version: int = 1,
    updated_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    return {
        "scheduled_query_id": scheduled_query_id,
        "name": name,
        "enabled": enabled,
        "frequency": frequency,
        "current_version": current_version,
        "updated_at": updated_at,
    }


def _sq_detail(
    scheduled_query_id: str = "sq1",
    name: str = "My Query",
    enabled: bool = True,
    frequency: int = 3600,
    version: int = 1,
    created_by: str = "user@example.com",
    cypher: str = "MATCH (n) RETURN n",
) -> dict:
    return {
        "scheduled_query_id": scheduled_query_id,
        "name": name,
        "enabled": enabled,
        "frequency": frequency,
        "version": version,
        "created_by": created_by,
        "cypher": cypher,
    }


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_scheduled_queries_empty(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"scheduled_queries": []}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No scheduled queries found" in result.output


def test_list_scheduled_queries_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"scheduled_queries": [_sq_item()]}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "sq1" in result.output
    assert "My Query" in result.output


def test_list_scheduled_queries_disabled_shows_no(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"scheduled_queries": [_sq_item(enabled=False)]}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "no" in result.output


def test_list_scheduled_queries_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"scheduled_queries": [_sq_item()]}
    result = runner.invoke(app, ["list", "--output", "json"])
    assert result.exit_code == 0
    assert '"scheduled_query_id"' in result.output


def test_list_scheduled_queries_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(500, "server error")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_scheduled_query_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _sq_detail()
    result = runner.invoke(app, ["get", "sq1"])
    assert result.exit_code == 0
    assert "sq1" in result.output
    assert "My Query" in result.output
    assert "MATCH (n) RETURN n" in result.output
    mock_client.get.assert_called_once_with("/api/v1/scheduled-queries/sq1")


def test_get_scheduled_query_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _sq_detail()
    result = runner.invoke(app, ["get", "sq1", "--output", "json"])
    assert result.exit_code == 0
    assert '"scheduled_query_id"' in result.output


def test_get_scheduled_query_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["get", "sq1"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_scheduled_query_with_yes(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["delete", "sq1", "--yes"])
    assert result.exit_code == 0
    assert "sq1" in result.output
    mock_client.delete.assert_called_once_with("/api/v1/scheduled-queries/sq1")


def test_delete_scheduled_query_prompts_without_yes(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["delete", "sq1"], input="y\n")
    assert result.exit_code == 0
    mock_client.delete.assert_called_once()


def test_delete_scheduled_query_aborts_on_no(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["delete", "sq1"], input="n\n")
    assert result.exit_code != 0
    mock_client.delete.assert_not_called()


def test_delete_scheduled_query_api_error(mock_client: MagicMock) -> None:
    mock_client.delete.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["delete", "sq1", "--yes"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# versions
# ---------------------------------------------------------------------------


def test_list_versions(mock_client: MagicMock) -> None:
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
    result = runner.invoke(app, ["versions", "sq1"])
    assert result.exit_code == 0
    assert "user@example.com" in result.output
    mock_client.get.assert_called_once_with("/api/v1/scheduled-queries/sq1/versions")


def test_list_versions_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"versions": []}
    result = runner.invoke(app, ["versions", "sq1", "--output", "json"])
    assert result.exit_code == 0
    assert '"versions"' in result.output


def test_list_versions_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["versions", "sq1"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# version-get
# ---------------------------------------------------------------------------


def test_get_version(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _sq_detail(version=2)
    result = runner.invoke(app, ["version-get", "sq1", "2"])
    assert result.exit_code == 0
    assert "sq1" in result.output
    mock_client.get.assert_called_once_with("/api/v1/scheduled-queries/sq1/versions/2")


def test_get_version_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _sq_detail(version=2)
    result = runner.invoke(app, ["version-get", "sq1", "2", "--output", "json"])
    assert result.exit_code == 0
    assert '"scheduled_query_id"' in result.output


def test_get_version_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["version-get", "sq1", "99"])
    assert result.exit_code == 1
