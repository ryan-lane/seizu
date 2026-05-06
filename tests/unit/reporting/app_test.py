import asyncio
from typing import Any

from reporting.app import _TIMEOUT_RESPONSE_BODY, _TimeoutMiddleware


async def test_timeout_middleware_returns_504_for_slow_http_request():
    sent_messages: list[dict[str, Any]] = []

    async def slow_app(scope, receive, send):
        await asyncio.sleep(0.01)

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent_messages.append(message)

    middleware = _TimeoutMiddleware(slow_app, timeout=0.001)
    await middleware({"type": "http", "path": "/", "method": "GET"}, receive, send)

    assert sent_messages[0]["type"] == "http.response.start"
    assert sent_messages[0]["status"] == 504
    assert sent_messages[0]["headers"] == [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(_TIMEOUT_RESPONSE_BODY)).encode()),
    ]
    assert sent_messages[1]["type"] == "http.response.body"
    assert sent_messages[1]["body"] == _TIMEOUT_RESPONSE_BODY
    assert sent_messages[1]["more_body"] is False


async def test_timeout_middleware_passes_through_non_http_scope():
    called = False

    async def passthrough_app(scope, receive, send):
        nonlocal called
        called = True

    async def receive() -> dict[str, Any]:
        raise AssertionError("receive should not be called")

    async def send(message: dict[str, Any]) -> None:
        raise AssertionError("send should not be called")

    middleware = _TimeoutMiddleware(passthrough_app, timeout=0.001)
    await middleware({"type": "lifespan"}, receive, send)

    assert called is True
