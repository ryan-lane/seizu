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


def _make_app(mocker, get_user_return=_FAKE_USER):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.users.authnz.get_user",
        return_value=_FAKE_USER,
    )
    mocker.patch(
        "reporting.routes.users.report_store.get_user",
        return_value=get_user_return,
    )
    return create_app(_app_settings())


def test_get_user_success(mocker):
    app = _make_app(mocker)
    ret = app.test_client().get("/api/v1/users/uid1")
    assert ret.status_code == 200
    assert ret.json["user_id"] == "uid1"
    assert ret.json["email"] == "alice@example.com"
    assert ret.json["display_name"] == "Alice Smith"
    assert ret.json["sub"] == "sub123"
    assert ret.json["iss"] == "https://idp.example.com"
    assert ret.json["archived_at"] is None


def test_get_user_not_found(mocker):
    app = _make_app(mocker, get_user_return=None)
    ret = app.test_client().get("/api/v1/users/nonexistent")
    assert ret.status_code == 404
