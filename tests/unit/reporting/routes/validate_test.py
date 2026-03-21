from reporting.app import create_app
from reporting.schema.report_config import User
from reporting.services.query_validator import ValidationResult

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="test@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)


def _app_settings():
    return {
        "PREFERRED_URL_SCHEME": "https",
    }


def _mock_validate(mocker, errors=None, warnings=None):
    result = ValidationResult(
        errors=errors if errors is not None else [],
        warnings=warnings if warnings is not None else [],
    )
    mocker.patch(
        "reporting.routes.validate.validate_query",
        return_value=result,
    )
    return result


def test_validate_success(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"query": "MATCH (n) RETURN n"},
    )
    assert ret.status_code == 200
    assert ret.json["errors"] == []
    assert ret.json["warnings"] == []


def test_validate_with_errors_still_returns_200(mocker):
    """Validation errors are returned in the body with 200; 400 is for bad requests."""
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker, errors=["Write queries are not allowed"])

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"query": "CREATE (n) RETURN n"},
    )
    assert ret.status_code == 200
    assert ret.json["errors"] == ["Write queries are not allowed"]
    assert ret.json["warnings"] == []


def test_validate_with_warnings(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker, warnings=["Unknown label: Foo", "Unknown property: bar"])

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"query": "MATCH (n:Foo) WHERE n.bar = 1 RETURN n"},
    )
    assert ret.status_code == 200
    assert ret.json["errors"] == []
    assert len(ret.json["warnings"]) == 2


def test_validate_with_errors_and_warnings(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(
        mocker,
        errors=["Write queries are not allowed"],
        warnings=["Unknown label: Foo"],
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"query": "CREATE (n:Foo) RETURN n"},
    )
    assert ret.status_code == 200
    assert len(ret.json["errors"]) == 1
    assert len(ret.json["warnings"]) == 1


def test_validate_no_json_body(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        data="not json",
        content_type="text/plain",
    )
    assert ret.status_code == 400
    assert "Request must be JSON" in ret.json["error"]


def test_validate_missing_query_field(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"params": {"name": "Alice"}},
    )
    assert ret.status_code == 400
    assert "Invalid request" in ret.json["error"]


def test_validate_no_csrf(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )

    app = create_app(_app_settings())
    client = app.test_client()
    ret = client.post(
        "/api/v1/validate",
        json={"query": "MATCH (n) RETURN n"},
    )
    assert ret.status_code == 403


def test_validate_with_csrf(mocker, helpers):
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    mocker.patch(
        "reporting.routes.validate.authnz.get_user",
        return_value=_FAKE_USER,
    )
    _mock_validate(mocker)

    app = create_app(_app_settings())
    with app.test_client() as client:
        ret = client.get("/index.html")
        cookie_name = app.config["CSRF_COOKIE_NAME"]
        cookie_header = app.config["CSRF_HEADER_NAME"]
        cookie = helpers.get_cookie(ret, cookie_name)
        ret = client.post(
            "/api/v1/validate",
            json={"query": "MATCH (n) RETURN n"},
            headers={
                cookie_header: cookie,
                "Referer": "https://localhost",
            },
        )
        assert ret.status_code == 200
