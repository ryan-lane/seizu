"""Tests for seizu_cli.state."""
from unittest.mock import MagicMock

import pytest

import seizu_cli.state as state_mod
from seizu_cli.client import SeizuClient


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Ensure module-level state is clean before and after each test."""
    original_client = state_mod._client
    original_api_url = state_mod.api_url
    original_token = state_mod.token
    yield
    state_mod._client = original_client
    state_mod.api_url = original_api_url
    state_mod.token = original_token


def test_get_client_creates_instance_on_first_call(mocker: pytest.MonkeyPatch) -> None:
    state_mod._client = None
    state_mod.api_url = "http://localhost:8080"
    state_mod.token = None
    mock_instance = MagicMock(spec=SeizuClient)
    mocker.patch("seizu_cli.client.SeizuClient", return_value=mock_instance)

    result = state_mod.get_client()

    assert result is mock_instance


def test_get_client_returns_cached_instance(mocker: pytest.MonkeyPatch) -> None:
    existing = MagicMock(spec=SeizuClient)
    state_mod._client = existing

    result = state_mod.get_client()

    assert result is existing


def test_get_client_passes_api_url_and_token(mocker: pytest.MonkeyPatch) -> None:
    state_mod._client = None
    state_mod.api_url = "https://seizu.example.com"
    state_mod.token = "bearer-tok"
    mock_cls = mocker.patch("seizu_cli.client.SeizuClient")

    state_mod.get_client()

    mock_cls.assert_called_once_with("https://seizu.example.com", "bearer-tok")


def test_reset_client_clears_cache() -> None:
    state_mod._client = MagicMock(spec=SeizuClient)
    state_mod.reset_client()
    assert state_mod._client is None


def test_get_client_recreates_after_reset(mocker: pytest.MonkeyPatch) -> None:
    state_mod._client = MagicMock(spec=SeizuClient)
    state_mod.reset_client()

    new_instance = MagicMock(spec=SeizuClient)
    mocker.patch("seizu_cli.client.SeizuClient", return_value=new_instance)

    result = state_mod.get_client()
    assert result is new_instance
