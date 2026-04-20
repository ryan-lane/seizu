from unittest.mock import AsyncMock

from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import User

_FAKE_USER = User(
    user_id="uid1",
    sub="sub123",
    iss="https://idp.example.com",
    email="alice@example.com",
    display_name="Alice Smith",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)

_FAKE_CURRENT_USER = CurrentUser(
    user=_FAKE_USER, jwt_claims={}, permissions=ALL_PERMISSIONS
)


def _make_app(get_user_return=_FAKE_USER):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _FAKE_CURRENT_USER
    return app, get_user_return


async def test_get_user_success(mocker):
    mocker.patch(
        "reporting.routes.users.report_store.get_user",
        new=AsyncMock(return_value=_FAKE_USER),
    )
    app, _ = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/users/uid1")
    assert ret.status_code == 200
    assert ret.json()["user_id"] == "uid1"
    assert ret.json()["email"] == "alice@example.com"
    assert ret.json()["display_name"] == "Alice Smith"
    assert ret.json()["sub"] == "sub123"
    assert ret.json()["iss"] == "https://idp.example.com"
    assert ret.json()["archived_at"] is None


async def test_get_user_not_found(mocker):
    mocker.patch(
        "reporting.routes.users.report_store.get_user",
        new=AsyncMock(return_value=None),
    )
    app, _ = _make_app(get_user_return=None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/users/nonexistent")
    assert ret.status_code == 404
