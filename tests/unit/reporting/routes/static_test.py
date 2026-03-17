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


def test_index(mocker, helpers, tmp_path):
    # Create a minimal build fixture so the test doesn't rely on public/index.html
    # existing on disk (Vite uses public/ for static assets, not the HTML entry point)
    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><head>"
        '<meta property="csp-nonce" content="{{ csp_nonce() }}" />'
        '</head><body><div id="root"></div></body></html>'
    )
    (tmp_path / "favicon.png").write_bytes(b"")
    static_images = tmp_path / "static" / "images"
    static_images.mkdir(parents=True)
    (static_images / "logo-horizontal-with-text-white.png").write_bytes(b"")
    mocker.patch("reporting.settings.STATIC_FOLDER", str(tmp_path))
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
