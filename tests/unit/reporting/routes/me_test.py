from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.authnz import sync_user_profile
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

_FAKE_CURRENT_USER = CurrentUser(user=_FAKE_USER, jwt_claims={})


def _make_app(synced_user: User = _FAKE_USER) -> object:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _FAKE_CURRENT_USER
    app.dependency_overrides[sync_user_profile] = lambda: CurrentUser(
        user=synced_user, jwt_claims={}
    )
    return app


async def test_get_current_user_success(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/me")
    assert ret.status_code == 200
    assert ret.json()["user_id"] == "uid1"
    assert ret.json()["email"] == "alice@example.com"
    assert ret.json()["display_name"] == "Alice Smith"
    assert ret.json()["sub"] == "sub123"
    assert ret.json()["iss"] == "https://idp.example.com"
    assert ret.json()["archived_at"] is None


async def test_get_current_user_returns_synced_profile(mocker):
    """The route should return the result of sync_user_profile, not the raw lookup."""
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    updated_user = _FAKE_USER.model_copy(
        update={"email": "alice-new@example.com", "display_name": "Alice Updated"}
    )
    app = _make_app(synced_user=updated_user)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/me")
    assert ret.status_code == 200
    assert ret.json()["email"] == "alice-new@example.com"
    assert ret.json()["display_name"] == "Alice Updated"
