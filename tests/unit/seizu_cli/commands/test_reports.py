"""Tests for seizu_cli.commands.reports."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from seizu_cli.client import APIError
from seizu_cli.commands.reports import app

runner = CliRunner()


@pytest.fixture
def mock_client(mocker: pytest.MonkeyPatch) -> MagicMock:
    mc = MagicMock()
    mocker.patch("seizu_cli.state.get_client", return_value=mc)
    return mc


def _report_item(
    report_id: str = "r1",
    name: str = "My Report",
    current_version: int = 1,
    updated_at: str = "2024-01-01T00:00:00Z",
) -> dict:
    return {
        "report_id": report_id,
        "name": name,
        "current_version": current_version,
        "updated_at": updated_at,
    }


def _report_detail(
    report_id: str = "r1",
    name: str = "My Report",
    version: int = 1,
    created_by: str = "user@example.com",
    created_at: str = "2024-01-01T00:00:00Z",
    comment: str = "",
) -> dict:
    return {
        "report_id": report_id,
        "name": name,
        "version": version,
        "created_by": created_by,
        "created_at": created_at,
        "comment": comment,
    }


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_reports_empty(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"reports": []}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No reports found" in result.output


def test_list_reports_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"reports": [_report_item()]}
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "My Report" in result.output


def test_list_reports_json(mock_client: MagicMock) -> None:
    payload = {"reports": [_report_item()]}
    mock_client.get.return_value = payload
    result = runner.invoke(app, ["list", "--output", "json"])
    assert result.exit_code == 0
    assert '"report_id"' in result.output
    assert "r1" in result.output


def test_list_reports_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(500, "server error")
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_report_table(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _report_detail()
    result = runner.invoke(app, ["get", "r1"])
    assert result.exit_code == 0
    assert "r1" in result.output
    assert "My Report" in result.output


def test_get_report_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _report_detail()
    result = runner.invoke(app, ["get", "r1", "--output", "json"])
    assert result.exit_code == 0
    assert '"report_id"' in result.output


def test_get_report_shows_comment(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _report_detail(comment="Initial version")
    result = runner.invoke(app, ["get", "r1"])
    assert result.exit_code == 0
    assert "Initial version" in result.output


def test_get_report_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["get", "r1"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_report(mock_client: MagicMock) -> None:
    mock_client.post.return_value = {"report_id": "r-new", "name": "New Report"}
    result = runner.invoke(app, ["create", "New Report"])
    assert result.exit_code == 0
    assert "r-new" in result.output
    assert "New Report" in result.output
    mock_client.post.assert_called_once_with("/api/v1/reports", json={"name": "New Report"})


def test_create_report_api_error(mock_client: MagicMock) -> None:
    mock_client.post.side_effect = APIError(422, "validation error")
    result = runner.invoke(app, ["create", "Bad Report"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_report_with_yes_flag(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["delete", "r1", "--yes"])
    assert result.exit_code == 0
    assert "r1" in result.output
    mock_client.delete.assert_called_once_with("/api/v1/reports/r1")


def test_delete_report_api_error(mock_client: MagicMock) -> None:
    mock_client.delete.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["delete", "r1", "--yes"])
    assert result.exit_code == 1


def test_delete_report_prompts_without_yes_flag(mock_client: MagicMock) -> None:
    mock_client.delete.return_value = None
    result = runner.invoke(app, ["delete", "r1"], input="y\n")
    assert result.exit_code == 0
    mock_client.delete.assert_called_once()


def test_delete_report_aborts_on_no(mock_client: MagicMock) -> None:
    result = runner.invoke(app, ["delete", "r1"], input="n\n")
    assert result.exit_code != 0
    mock_client.delete.assert_not_called()


# ---------------------------------------------------------------------------
# set-dashboard
# ---------------------------------------------------------------------------


def test_set_dashboard(mock_client: MagicMock) -> None:
    mock_client.put.return_value = {}
    result = runner.invoke(app, ["set-dashboard", "r1"])
    assert result.exit_code == 0
    assert "r1" in result.output
    mock_client.put.assert_called_once_with("/api/v1/reports/r1/dashboard")


def test_set_dashboard_api_error(mock_client: MagicMock) -> None:
    mock_client.put.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["set-dashboard", "r1"])
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
                "comment": "first",
            }
        ]
    }
    result = runner.invoke(app, ["versions", "r1"])
    assert result.exit_code == 0
    assert "user@example.com" in result.output
    mock_client.get.assert_called_once_with("/api/v1/reports/r1/versions")


def test_list_versions_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = {"versions": []}
    result = runner.invoke(app, ["versions", "r1", "--output", "json"])
    assert result.exit_code == 0
    assert '"versions"' in result.output


def test_list_versions_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["versions", "r1"])
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# version-get
# ---------------------------------------------------------------------------


def test_get_version(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _report_detail(version=2)
    result = runner.invoke(app, ["version-get", "r1", "2"])
    assert result.exit_code == 0
    assert "r1" in result.output
    mock_client.get.assert_called_once_with("/api/v1/reports/r1/versions/2")


def test_get_version_json(mock_client: MagicMock) -> None:
    mock_client.get.return_value = _report_detail(version=2)
    result = runner.invoke(app, ["version-get", "r1", "2", "--output", "json"])
    assert result.exit_code == 0
    assert '"report_id"' in result.output


def test_get_version_api_error(mock_client: MagicMock) -> None:
    mock_client.get.side_effect = APIError(404, "not found")
    result = runner.invoke(app, ["version-get", "r1", "99"])
    assert result.exit_code == 1
