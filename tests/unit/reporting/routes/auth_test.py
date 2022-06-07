from reporting.app import create_app
from reporting.exceptions import UserCreationError


def test_login_client_mode(mocker):
    mocker.patch("reporting.settings.AUTH_MODE", "client")
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.post("/api/v1/login", follow_redirects=False)
    assert ret.status_code == 200
    assert ret.json == {
        "protocol": "bolt+s",
        "port": 7687,
        "hostname": "localhost",
        "auth_mode": "client",
    }


def test_login_auto_mode(mocker):
    mocker.patch("reporting.settings.AUTH_MODE", "auto")
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.auth.authnz.get_email",
        return_value="test@example.com",
    )
    mocker.patch(
        "reporting.routes.auth.reporting_neo4j.renew_user",
        return_value="password",
    )
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.post("/api/v1/login", follow_redirects=False)
    assert ret.status_code == 200
    assert ret.json == {
        "protocol": "bolt+s",
        "port": 7687,
        "hostname": "localhost",
        "username": "test@example.com",
        "password": "password",
        "auth_mode": "auto",
    }


def test_login_auto_mode_user_creation_failure(mocker):
    mocker.patch("reporting.settings.AUTH_MODE", "auto")
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    mocker.patch(
        "reporting.routes.auth.authnz.get_email",
        return_value="test@example.com",
    )
    mocker.patch(
        "reporting.routes.auth.reporting_neo4j.renew_user",
        side_effect=UserCreationError(),
    )
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.post("/api/v1/login", follow_redirects=False)
    assert ret.status_code == 403
    assert ret.json == {
        "error": "Failed to login.",
    }


def test_login_no_csrf(mocker):
    mocker.patch("reporting.settings.AUTH_MODE", "client")
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.post("/api/v1/login", follow_redirects=False)
    assert ret.status_code == 403


def test_login_auto_mode_with_csrf(mocker, helpers):
    mocker.patch("reporting.settings.AUTH_MODE", "auto")
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    mocker.patch(
        "reporting.routes.auth.authnz.get_email",
        return_value="test@example.com",
    )
    mocker.patch(
        "reporting.routes.auth.reporting_neo4j.renew_user",
        return_value="password",
    )
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    with app.test_client() as client:
        # Get a CSRF cookie
        ret = client.get("/index.html")
        cookie_name = app.config["CSRF_COOKIE_NAME"]
        cookie_header = app.config["CSRF_HEADER_NAME"]
        cookie = helpers.get_cookie(ret, cookie_name)
        # Make a call with the cookie set in the headers
        ret = client.post(
            "/api/v1/login",
            headers={
                cookie_header: cookie,
                "Referer": "https://localhost",
            },
            follow_redirects=False,
        )
        assert ret.status_code == 200
        assert ret.json == {
            "protocol": "bolt+s",
            "port": 7687,
            "hostname": "localhost",
            "username": "test@example.com",
            "password": "password",
            "auth_mode": "auto",
        }
