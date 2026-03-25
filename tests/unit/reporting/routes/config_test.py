from reporting.app import _build_csp_policy
from reporting.app import create_app


def test_config():
    settings = {
        "PREFERRED_URL_SCHEME": "https",
        "SECRET_KEY": "fake",
    }
    app = create_app(settings)
    client = app.test_client()
    ret = client.get("/api/v1/config", follow_redirects=False)
    assert ret.status_code == 200
    ret_json = ret.json
    assert "auth_required" in ret_json
    assert ret_json["config"] == {}
    assert "reports" not in ret_json["config"].keys()
    assert "dashboard" not in ret_json["config"].keys()
    assert "$schema" in ret_json["schema"].keys()


def test_config_auth_required_true(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["auth_required"] is True


def test_config_auth_required_false(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["auth_required"] is False


def test_config_oidc_included_when_auth_required(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://idp.example.com/o/app")
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "myapp")
    mocker.patch(
        "reporting.settings.OIDC_REDIRECT_URI",
        "https://app.example.com/auth/callback",
    )
    mocker.patch("reporting.settings.OIDC_SCOPE", "openid email")
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    oidc = ret.json["oidc"]
    assert oidc["authority"] == "https://idp.example.com/o/app"
    assert oidc["client_id"] == "myapp"
    assert oidc["redirect_uri"] == "https://app.example.com/auth/callback"
    assert oidc["scope"] == "openid email"


def test_config_oidc_included_when_auth_not_required(mocker):
    """oidc config is returned regardless of auth_required so the frontend
    can self-configure even in no-auth dev mode."""
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://idp.example.com/o/app")
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "myapp")
    mocker.patch(
        "reporting.settings.OIDC_REDIRECT_URI",
        "https://app.example.com/auth/callback",
    )
    mocker.patch("reporting.settings.OIDC_SCOPE", "openid email")
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["oidc"]["authority"] == "https://idp.example.com/o/app"


def test_config_oidc_null_when_authority_not_configured(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "")
    app = create_app({"PREFERRED_URL_SCHEME": "https", "SECRET_KEY": "fake"})
    ret = app.test_client().get("/api/v1/config", follow_redirects=False)
    assert ret.json["oidc"] is None


# ---------------------------------------------------------------------------
# _build_csp_policy
# ---------------------------------------------------------------------------


def test_csp_policy_no_oidc_authority(mocker):
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "")
    policy = _build_csp_policy()
    assert policy["connect-src"] == ["'self'"]


def test_csp_policy_with_oidc_authority(mocker):
    mocker.patch(
        "reporting.settings.OIDC_AUTHORITY",
        "https://idp.example.com/application/o/seizu",
    )
    policy = _build_csp_policy()
    assert "'self'" in policy["connect-src"]
    assert "https://idp.example.com" in policy["connect-src"]


def test_csp_policy_oidc_origin_not_duplicated(mocker):
    """self and oidc origin must each appear exactly once."""
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://idp.example.com/o/app")
    policy = _build_csp_policy()
    assert policy["connect-src"].count("'self'") == 1
    assert policy["connect-src"].count("https://idp.example.com") == 1


def test_csp_policy_self_not_added_as_oidc_origin(mocker):
    """If OIDC_AUTHORITY is on the same origin, connect-src stays as just 'self'."""
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "'self'/o/app")
    policy = _build_csp_policy()
    # Parsed origin of "'self'/o/app" is "'self'" which matches the existing entry
    assert policy["connect-src"].count("'self'") == 1
