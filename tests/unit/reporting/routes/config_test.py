from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app


def _make_app(mocker):
    mocker.patch("reporting.settings.CSRF_DISABLE", True)
    return create_app()


async def test_config(mocker):
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    assert ret.status_code == 200
    ret_json = ret.json()
    assert "auth_required" in ret_json
    assert ret_json["config"] == {}
    assert "reports" not in ret_json["config"].keys()
    assert "dashboard" not in ret_json["config"].keys()
    assert "$schema" in ret_json["schema"].keys()


async def test_config_auth_required_true(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    assert ret.json()["auth_required"] is True


async def test_config_auth_required_false(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    assert ret.json()["auth_required"] is False


async def test_config_oidc_included_when_auth_required(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://idp.example.com/o/app")
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "myapp")
    mocker.patch(
        "reporting.settings.OIDC_REDIRECT_URI",
        "https://app.example.com/auth/callback",
    )
    mocker.patch("reporting.settings.OIDC_SCOPE", "openid email")
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    oidc = ret.json()["oidc"]
    assert oidc["authority"] == "https://idp.example.com/o/app"
    assert oidc["client_id"] == "myapp"
    assert oidc["redirect_uri"] == "https://app.example.com/auth/callback"
    assert oidc["scope"] == "openid email"


async def test_config_oidc_included_when_auth_not_required(mocker):
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
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    assert ret.json()["oidc"]["authority"] == "https://idp.example.com/o/app"


async def test_config_oidc_null_when_authority_not_configured(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "")
    app = _make_app(mocker)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/config")
    assert ret.json()["oidc"] is None


# ---------------------------------------------------------------------------
# _build_csp_policy
# ---------------------------------------------------------------------------


def test_csp_policy_no_oidc_authority(mocker):
    from reporting.app import _build_csp_policy

    mocker.patch("reporting.settings.OIDC_AUTHORITY", "")
    policy = _build_csp_policy()
    assert "'self'" in policy
    assert "connect-src" in policy


def test_csp_policy_with_oidc_authority(mocker):
    from reporting.app import _build_csp_policy

    mocker.patch(
        "reporting.settings.OIDC_AUTHORITY",
        "https://idp.example.com/application/o/seizu",
    )
    policy = _build_csp_policy()
    assert "https://idp.example.com" in policy


def test_csp_policy_oidc_origin_not_duplicated(mocker):
    """self and oidc origin must each appear exactly once."""
    from reporting.app import _build_csp_policy

    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://idp.example.com/o/app")
    policy = _build_csp_policy()
    assert policy.count("https://idp.example.com") == 1
