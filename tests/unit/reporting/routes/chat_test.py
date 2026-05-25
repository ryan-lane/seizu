from collections.abc import AsyncIterator
from typing import Any

from httpx import ASGITransport, AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser, get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import User

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="test@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)


class FakeChatGraph:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], dict[str, Any], str, str]] = []

    async def astream_events(
        self,
        input: dict[str, Any],
        config: dict[str, Any],
        *,
        version: str,
        stream_mode: str,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append((input, config, version, stream_mode))
        yield {
            "event": "on_chain_stream",
            "data": {"chunk": {"kind": "token", "content": "Hello"}},
            "parent_ids": [],
        }
        yield {
            "event": "on_chain_stream",
            "data": {"chunk": {"kind": "token", "content": " there"}},
            "parent_ids": [],
        }


def _current_user(permissions: frozenset[str] = ALL_PERMISSIONS) -> CurrentUser:
    return CurrentUser(user=_FAKE_USER, jwt_claims={}, permissions=permissions)


def _make_app(current: CurrentUser | None = None):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current or _current_user()
    return app


async def test_chat_stream_success(mocker):
    fake_graph = FakeChatGraph()
    mocker.patch("reporting.routes.chat.get_chat_graph", return_value=fake_graph)

    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hi", "thread_id": "thread-1"},
        )

    assert response.status_code == 200
    assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
    body = response.text
    assert '"type":"start"' in body
    assert '"type":"text-start"' in body
    assert '"delta":"Hello"' in body
    assert '"delta":" there"' in body
    assert '"finishReason":"stop"' in body
    assert "data: [DONE]" in body

    graph_input, config, version, stream_mode = fake_graph.calls[0]
    assert config["configurable"]["thread_id"] == "user:test-user-id:thread:thread-1"
    assert config["configurable"]["current_user"].user.user_id == "test-user-id"
    assert version == "v2"
    assert stream_mode == "custom"
    assert graph_input["messages"][0].content == "Hi"


async def test_chat_stream_requires_chat_permission(mocker):
    mocker.patch("reporting.routes.chat.get_chat_graph")
    app = _make_app(_current_user(frozenset()))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hi", "thread_id": "thread-1"},
        )

    assert response.status_code == 403


async def test_chat_stream_validates_body(mocker):
    mocker.patch("reporting.routes.chat.get_chat_graph")
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "", "thread_id": "thread-1"},
        )

    assert response.status_code == 422
