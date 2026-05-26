import json
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
        self.calls: list[tuple[dict[str, Any], dict[str, Any], str]] = []

    async def astream(
        self,
        input: dict[str, Any],
        config: dict[str, Any],
        *,
        stream_mode: str,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append((input, config, stream_mode))
        yield {"kind": "token", "content": "Hello"}
        yield {"kind": "token", "content": " there"}


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

    graph_input, config, stream_mode = fake_graph.calls[0]
    assert config["configurable"]["thread_id"] == "user:test-user-id:thread:thread-1"
    assert config["configurable"]["current_user"].user.user_id == "test-user-id"
    assert stream_mode == "custom"
    assert graph_input["messages"][0].content == "Hi"


async def test_chat_stream_with_real_graph_emits_tokens(mocker):
    """Exercise the real compiled LangGraph so a change in LangGraph's custom
    stream output shape (which the FakeChatGraph can't catch) is detected."""
    from langgraph.checkpoint.memory import MemorySaver

    from reporting.services.chat_graph import build_chat_graph

    graph = build_chat_graph(MemorySaver())
    mocker.patch("reporting.routes.chat.get_chat_graph", return_value=graph)

    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hi", "thread_id": "thread-real"},
        )

    assert response.status_code == 200
    body = response.text
    # The mock agent streams "I received your message: Hi" in 8-char chunks.
    deltas = "".join(
        json.loads(line[len("data: ") :])["delta"]
        for line in body.splitlines()
        if line.startswith("data: ") and '"text-delta"' in line
    )
    assert deltas == "I received your message: Hi"
    assert '"finishReason":"stop"' in body


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


async def test_chat_history_round_trips_persisted_messages(mocker):
    """Stream a turn, then fetch history from the same checkpoint-backed graph."""
    from langgraph.checkpoint.memory import MemorySaver

    from reporting.services.chat_graph import build_chat_graph

    graph = build_chat_graph(MemorySaver())
    # The stream endpoint and load_thread_messages resolve get_chat_graph
    # through different module bindings; patch both so they share one graph.
    mocker.patch("reporting.routes.chat.get_chat_graph", return_value=graph)
    mocker.patch("reporting.services.chat_graph.get_chat_graph", return_value=graph)

    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stream = await client.post(
            "/api/v1/chat/stream",
            json={"message": "Hi", "thread_id": "thread-hist"},
        )
        assert stream.status_code == 200
        history = await client.get("/api/v1/chat/history", params={"thread_id": "thread-hist"})

    assert history.status_code == 200
    messages = history.json()["messages"]
    assert messages[0]["role"] == "user"
    assert messages[0]["text"] == "Hi"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["text"] == "I received your message: Hi"
    assert all(message["id"] for message in messages)


async def test_chat_history_isolated_per_user(mocker):
    """A thread id is scoped to the user, so another user sees no history."""
    from langgraph.checkpoint.memory import MemorySaver

    from reporting.services.chat_graph import build_chat_graph

    graph = build_chat_graph(MemorySaver())
    mocker.patch("reporting.routes.chat.get_chat_graph", return_value=graph)
    mocker.patch("reporting.services.chat_graph.get_chat_graph", return_value=graph)

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        app.dependency_overrides[get_current_user] = lambda: _current_user()
        await client.post("/api/v1/chat/stream", json={"message": "Hi", "thread_id": "shared"})

        other = CurrentUser(
            user=User(
                user_id="other-user-id",
                sub="sub-other",
                iss="https://idp.example.com",
                email="other@example.com",
                created_at="2024-01-01T00:00:00+00:00",
                last_login="2024-01-01T00:00:00+00:00",
            ),
            jwt_claims={},
            permissions=ALL_PERMISSIONS,
        )
        app.dependency_overrides[get_current_user] = lambda: other
        history = await client.get("/api/v1/chat/history", params={"thread_id": "shared"})

    assert history.status_code == 200
    assert history.json()["messages"] == []


async def test_chat_stream_command_is_not_persisted(mocker):
    """A slash command streams its result but leaves the thread empty."""
    from langgraph.checkpoint.memory import MemorySaver

    from reporting.services.chat_graph import build_chat_graph

    graph = build_chat_graph(MemorySaver())
    mocker.patch("reporting.routes.chat.get_chat_graph", return_value=graph)
    mocker.patch("reporting.services.chat_graph.get_chat_graph", return_value=graph)
    mocker.patch(
        "reporting.services.chat_graph.mcp_runtime.list_tools_for_user",
        return_value=[],
    )

    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stream = await client.post(
            "/api/v1/chat/stream",
            json={"message": "/tools", "thread_id": "thread-cmd"},
        )
        assert stream.status_code == 200
        deltas = "".join(
            json.loads(line[len("data: ") :])["delta"]
            for line in stream.text.splitlines()
            if line.startswith("data: ") and '"text-delta"' in line
        )
        assert deltas == "No MCP tools are available to this chat session."

        history = await client.get("/api/v1/chat/history", params={"thread_id": "thread-cmd"})

    assert history.status_code == 200
    assert history.json()["messages"] == []


def test_chat_routes_registered_when_enabled():
    paths = {getattr(route, "path", None) for route in create_app().routes}
    assert "/api/v1/chat/stream" in paths
    assert "/api/v1/chat/history" in paths


def test_chat_routes_absent_when_disabled(mocker):
    mocker.patch("reporting.settings.CHAT_ENABLED", False)
    paths = {getattr(route, "path", None) for route in create_app().routes}
    assert "/api/v1/chat/stream" not in paths
    assert "/api/v1/chat/history" not in paths


async def test_chat_history_requires_chat_permission(mocker):
    mocker.patch("reporting.routes.chat.get_chat_graph")
    app = _make_app(_current_user(frozenset()))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/history", params={"thread_id": "thread-1"})

    assert response.status_code == 403
