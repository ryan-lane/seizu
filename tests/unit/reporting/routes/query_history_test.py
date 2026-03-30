from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import QueryHistoryItem
from reporting.schema.report_config import User

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="test@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)

_OTHER_USER = User(
    user_id="other-user-id",
    sub="sub456",
    iss="https://idp.example.com",
    email="other@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)

_FAKE_CURRENT_USER = CurrentUser(
    user=_FAKE_USER, jwt_claims={}, permissions=ALL_PERMISSIONS
)
_OTHER_CURRENT_USER = CurrentUser(
    user=_OTHER_USER, jwt_claims={}, permissions=ALL_PERMISSIONS
)


def _make_app(current_user: CurrentUser = _FAKE_CURRENT_USER) -> object:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: current_user
    return app


def _make_history_item(
    history_id: str = "123",
    user_id: str = "test-user-id",
    query: str = "MATCH (n) RETURN n LIMIT 1",
    executed_at: str = "2024-01-01T00:00:00+00:00",
) -> QueryHistoryItem:
    return QueryHistoryItem(
        history_id=history_id,
        user_id=user_id,
        query=query,
        executed_at=executed_at,
    )


async def test_list_query_history_empty(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query_history.report_store.list_query_history",
        new=AsyncMock(return_value=([], 0)),
    )

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/query-history")

    assert ret.status_code == 200
    body = ret.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["per_page"] == 20


async def test_list_query_history_returns_items(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    item = _make_history_item()
    mocker.patch(
        "reporting.routes.query_history.report_store.list_query_history",
        new=AsyncMock(return_value=([item], 1)),
    )

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/query-history")

    assert ret.status_code == 200
    body = ret.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["history_id"] == "123"
    assert body["items"][0]["query"] == "MATCH (n) RETURN n LIMIT 1"
    assert body["total"] == 1


async def test_list_query_history_pagination_params(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mock_list = mocker.patch(
        "reporting.routes.query_history.report_store.list_query_history",
        new=AsyncMock(return_value=([], 0)),
    )

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/query-history?page=2&per_page=10")

    assert ret.status_code == 200
    body = ret.json()
    assert body["page"] == 2
    assert body["per_page"] == 10
    mock_list.assert_awaited_once_with(
        user_id="test-user-id",
        page=2,
        per_page=10,
    )


async def test_list_query_history_scoped_to_current_user(mocker):
    """The route must pass the current user's ID, not any other user's."""
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mock_list = mocker.patch(
        "reporting.routes.query_history.report_store.list_query_history",
        new=AsyncMock(return_value=([], 0)),
    )

    # Use a different authenticated user.
    app = _make_app(current_user=_OTHER_CURRENT_USER)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/api/v1/query-history")

    mock_list.assert_awaited_once_with(
        user_id="other-user-id",
        page=1,
        per_page=20,
    )


async def test_list_query_history_invalid_page(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/query-history?page=0")

    assert ret.status_code == 422


async def test_list_query_history_per_page_too_large(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/query-history?per_page=101")

    assert ret.status_code == 422


@pytest.mark.parametrize("per_page", [1, 20, 100])
async def test_list_query_history_valid_per_page_values(mocker, per_page):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.query_history.report_store.list_query_history",
        new=AsyncMock(return_value=([], 0)),
    )

    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/query-history?per_page={per_page}")

    assert ret.status_code == 200
