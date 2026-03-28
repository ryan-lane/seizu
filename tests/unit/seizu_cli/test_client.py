"""Tests for seizu_cli.client.SeizuClient."""
from unittest.mock import MagicMock

import pytest

from seizu_cli.client import APIError
from seizu_cli.client import SeizuClient


@pytest.fixture
def session_mock(mocker: pytest.MonkeyPatch) -> MagicMock:
    """Patch requests.Session and stub out _bootstrap_csrf."""
    mock = MagicMock()
    mocker.patch("seizu_cli.client.requests.Session", return_value=mock)
    mocker.patch.object(SeizuClient, "_bootstrap_csrf", return_value="")
    return mock


def _make_response(
    ok: bool = True,
    status_code: int = 200,
    json_data: object = None,
    text: str = "",
    content: bytes = b"{}",
) -> MagicMock:
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.text = text
    resp.content = content
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


def test_strips_trailing_slash(session_mock: MagicMock) -> None:
    client = SeizuClient("http://localhost:8080/")
    assert client.base_url == "http://localhost:8080"


def test_sets_bearer_token(session_mock: MagicMock) -> None:
    SeizuClient("http://localhost:8080", token="tok-abc")
    session_mock.headers.update.assert_called_once_with(
        {"Authorization": "Bearer tok-abc"}
    )


def test_no_auth_header_without_token(session_mock: MagicMock) -> None:
    SeizuClient("http://localhost:8080")
    session_mock.headers.update.assert_not_called()


def test_csrf_token_stored_on_init(mocker: pytest.MonkeyPatch) -> None:
    mock_session = MagicMock()
    config_resp = MagicMock()
    config_resp.raise_for_status.return_value = None
    mock_session.get.return_value = config_resp
    mock_session.cookies.get.return_value = "csrf-from-cookie"
    mocker.patch("seizu_cli.client.requests.Session", return_value=mock_session)

    client = SeizuClient("http://localhost:8080")

    assert client._csrf_token == "csrf-from-cookie"
    mock_session.get.assert_called_once_with(
        "http://localhost:8080/api/v1/config", timeout=10
    )


def test_bootstrap_csrf_silently_ignores_request_errors(
    mocker: pytest.MonkeyPatch,
) -> None:
    import requests as req_mod

    mock_session = MagicMock()
    mock_session.get.side_effect = req_mod.ConnectionError("refused")
    mock_session.cookies.get.return_value = None
    mocker.patch("seizu_cli.client.requests.Session", return_value=mock_session)

    client = SeizuClient("http://localhost:8080")
    assert client._csrf_token == ""


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------


def test_get_returns_json(session_mock: MagicMock) -> None:
    session_mock.get.return_value = _make_response(json_data={"items": [1, 2]})
    client = SeizuClient("http://localhost:8080")
    result = client.get("/api/v1/test")
    assert result == {"items": [1, 2]}
    session_mock.get.assert_called_once_with(
        "http://localhost:8080/api/v1/test", timeout=30
    )


def test_get_raises_api_error_on_404(session_mock: MagicMock) -> None:
    session_mock.get.return_value = _make_response(
        ok=False, status_code=404, json_data={"error": "not found"}
    )
    client = SeizuClient("http://localhost:8080")
    with pytest.raises(APIError) as exc_info:
        client.get("/api/v1/missing")
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value)


def test_get_raises_api_error_401_with_login_hint(session_mock: MagicMock) -> None:
    session_mock.get.return_value = _make_response(ok=False, status_code=401)
    client = SeizuClient("http://localhost:8080")
    with pytest.raises(APIError) as exc_info:
        client.get("/api/v1/me")
    assert exc_info.value.status_code == 401
    assert "seizu login" in str(exc_info.value)


def test_get_falls_back_to_text_on_non_json_error(session_mock: MagicMock) -> None:
    resp = _make_response(ok=False, status_code=500, text="Internal Server Error")
    resp.json.side_effect = ValueError("no JSON")
    session_mock.get.return_value = resp
    client = SeizuClient("http://localhost:8080")
    with pytest.raises(APIError) as exc_info:
        client.get("/api/v1/test")
    assert "Internal Server Error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------


def test_post_includes_csrf_header(session_mock: MagicMock) -> None:
    client = SeizuClient("http://localhost:8080")
    client._csrf_token = "csrf-xyz"
    session_mock.post.return_value = _make_response(json_data={"id": "new"})

    client.post("/api/v1/reports", json={"name": "test"})

    _, call_kwargs = session_mock.post.call_args
    assert call_kwargs["headers"]["X-CSRFToken"] == "csrf-xyz"


def test_post_no_csrf_header_when_token_empty(session_mock: MagicMock) -> None:
    client = SeizuClient("http://localhost:8080")
    client._csrf_token = ""
    session_mock.post.return_value = _make_response(json_data={})

    client.post("/api/v1/reports", json={})

    _, call_kwargs = session_mock.post.call_args
    assert "X-CSRFToken" not in call_kwargs["headers"]


def test_post_returns_json(session_mock: MagicMock) -> None:
    session_mock.post.return_value = _make_response(json_data={"report_id": "r1"})
    client = SeizuClient("http://localhost:8080")
    result = client.post("/api/v1/reports", json={"name": "x"})
    assert result == {"report_id": "r1"}


def test_post_raises_api_error(session_mock: MagicMock) -> None:
    session_mock.post.return_value = _make_response(
        ok=False, status_code=422, json_data={"message": "validation error"}
    )
    client = SeizuClient("http://localhost:8080")
    with pytest.raises(APIError) as exc_info:
        client.post("/api/v1/reports", json={})
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------


def test_put_returns_json(session_mock: MagicMock) -> None:
    session_mock.put.return_value = _make_response(json_data={"updated": True})
    client = SeizuClient("http://localhost:8080")
    result = client.put("/api/v1/reports/r1/dashboard")
    assert result == {"updated": True}


def test_put_includes_csrf_header(session_mock: MagicMock) -> None:
    client = SeizuClient("http://localhost:8080")
    client._csrf_token = "token-put"
    session_mock.put.return_value = _make_response(json_data={})

    client.put("/api/v1/toolsets/ts1", json={"name": "x"})

    _, call_kwargs = session_mock.put.call_args
    assert call_kwargs["headers"]["X-CSRFToken"] == "token-put"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


def test_delete_returns_none_for_empty_body(session_mock: MagicMock) -> None:
    resp = _make_response(content=b"")
    session_mock.delete.return_value = resp
    client = SeizuClient("http://localhost:8080")
    result = client.delete("/api/v1/reports/r1")
    assert result is None


def test_delete_returns_json_when_body_present(session_mock: MagicMock) -> None:
    resp = _make_response(content=b'{"deleted":true}', json_data={"deleted": True})
    session_mock.delete.return_value = resp
    client = SeizuClient("http://localhost:8080")
    result = client.delete("/api/v1/reports/r1")
    assert result == {"deleted": True}


def test_delete_raises_api_error(session_mock: MagicMock) -> None:
    session_mock.delete.return_value = _make_response(ok=False, status_code=404)
    client = SeizuClient("http://localhost:8080")
    with pytest.raises(APIError) as exc_info:
        client.delete("/api/v1/reports/missing")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# APIError
# ---------------------------------------------------------------------------


def test_api_error_str_includes_status_code() -> None:
    err = APIError(404, "not found")
    assert "404" in str(err)
    assert "not found" in str(err)
