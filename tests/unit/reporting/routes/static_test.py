from reporting.app import create_app


def test_healthcheck(helpers):
    settings = {"PREFERRED_URL_SCHEME": "http"}
    app = create_app(settings)
    client = app.test_client()
    ret = client.get("/healthcheck", follow_redirects=False)
    cookie = helpers.get_cookie(ret, app.config["CSRF_COOKIE_NAME"])
    assert not cookie
    assert ret.status_code == 200
    assert ret.json == {"success": True}


def test_index(mocker, helpers):
    mocker.patch("reporting.settings.STATIC_FOLDER", "public")
    mocker.patch("reporting.settings.CSRF_DISABLE", False)
    mocker.patch("reporting.settings.SECRET_KEY", "fake")
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.get("/", follow_redirects=False)
    cookie = helpers.get_cookie(ret, app.config["CSRF_COOKIE_NAME"])
    assert cookie
    assert ret.status_code == 200
    ret = client.get(
        "/static/images/logo-horizontal-with-text-white.png", follow_redirects=False
    )
    assert ret.status_code == 200
    ret = client.get("/favicon.png", follow_redirects=False)
    assert ret.status_code == 200
    ret = client.get("/static/nonexistent.js", follow_redirects=False)
    assert ret.status_code == 404
