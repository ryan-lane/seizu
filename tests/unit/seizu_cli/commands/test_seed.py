"""Tests for seizu_cli.commands.seed helpers."""

from unittest.mock import MagicMock

import pytest

from seizu_cli.commands import seed


@pytest.fixture
def mock_client(mocker: pytest.MonkeyPatch) -> MagicMock:
    mc = MagicMock()
    mocker.patch("seizu_cli.state.get_client", return_value=mc)
    return mc


def test_publish_report_uses_visibility_endpoint(mock_client: MagicMock) -> None:
    seed._publish_report("r1")

    mock_client.put.assert_called_once_with(
        "/api/v1/reports/r1/visibility",
        json={"access": {"scope": "public"}},
    )
