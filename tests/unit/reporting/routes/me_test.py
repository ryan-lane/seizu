from httpx import ASGITransport, AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser, get_current_user, sync_user_profile
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

_FAKE_CURRENT_USER = CurrentUser(user=_FAKE_USER, jwt_claims={}, permissions=ALL_PERMISSIONS)


def _make_app(synced_user: User = _FAKE_USER) -> object:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _FAKE_CURRENT_USER
    app.dependency_overrides[sync_user_profile] = lambda: CurrentUser(
        user=synced_user, jwt_claims={}, permissions=ALL_PERMISSIONS
    )
    return app


async def test_get_current_user_success(mocker):
    app = _make_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ret = await client.get("/api/v1/me")
    assert ret.status_code == 200
    user = ret.json()["user"]
    assert user["user_id"] == "uid1"
    assert user["email"] == "alice@example.com"
    assert user["display_name"] == "Alice Smith"
    assert user["sub"] == "sub123"
    assert user["iss"] == "https://idp.example.com"
    assert user["archived_at"] is None
    assert isinstance(ret.json()["permissions"], list)


async def test_get_current_user_returns_synced_profile(mocker):
    """The route should return the result of sync_user_profile, not the raw lookup."""
    updated_user = _FAKE_USER.model_copy(update={"email": "alice-new@example.com", "display_name": "Alice Updated"})
    app = _make_app(synced_user=updated_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ret = await client.get("/api/v1/me")
    assert ret.status_code == 200
    assert ret.json()["user"]["email"] == "alice-new@example.com"
    assert ret.json()["user"]["display_name"] == "Alice Updated"
