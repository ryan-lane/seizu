from reporting.app import create_app
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


def _app_settings():
    return {
        "PREFERRED_URL_SCHEME": "https",
        "SECRET_KEY": "fake",
    }


def _make_app(mocker, synced_user=_FAKE_USER):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.me.authnz.get_user",
        return_value=_FAKE_USER,
    )
    mocker.patch(
        "reporting.routes.me.authnz.sync_user_profile",
        return_value=synced_user,
    )
    return create_app(_app_settings())


def test_get_current_user_success(mocker):
    app = _make_app(mocker)
    ret = app.test_client().get("/api/v1/me")
    assert ret.status_code == 200
    assert ret.json["user_id"] == "uid1"
    assert ret.json["email"] == "alice@example.com"
    assert ret.json["display_name"] == "Alice Smith"
    assert ret.json["sub"] == "sub123"
    assert ret.json["iss"] == "https://idp.example.com"
    assert ret.json["archived_at"] is None


def test_get_current_user_returns_synced_profile(mocker):
    """The route should return the result of sync_user_profile, not the raw lookup."""
    updated_user = _FAKE_USER.model_copy(
        update={"email": "alice-new@example.com", "display_name": "Alice Updated"}
    )
    app = _make_app(mocker, synced_user=updated_user)
    ret = app.test_client().get("/api/v1/me")
    assert ret.status_code == 200
    assert ret.json["email"] == "alice-new@example.com"
    assert ret.json["display_name"] == "Alice Updated"
