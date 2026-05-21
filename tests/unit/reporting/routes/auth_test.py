import base64
import os
import time
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from reporting.app import create_app
from reporting.services import oauth_client, oauth_state_cookie, session_cookie


@pytest.fixture(autouse=True)
def _auth_env(mocker):
    mocker.patch(
        "reporting.settings.SESSION_TOKEN_ENCRYPTION_KEY",
        base64.b64encode(os.urandom(32)).decode("ascii"),
    )
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "seizu")
    mocker.patch("reporting.settings.OIDC_SCOPE", "openid email offline_access")
    mocker.patch("reporting.settings.OIDC_REDIRECT_URI", "http://test/api/v1/auth/callback")
    mocker.patch("reporting.settings.TALISMAN_FORCE_HTTPS", False)
    mocker.patch("reporting.settings.OIDC_END_SESSION_ON_LOGOUT", True)
    mocker.patch("reporting.settings.SESSION_COOKIE_NAME", "seizu_session")
    mocker.patch("reporting.settings.SESSION_COOKIE_MAX_AGE_SECONDS", 18 * 60 * 60)
    oauth_client.reset_metadata_cache()
    yield
    oauth_client.reset_metadata_cache()


def _mock_metadata():
    return oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint="http://idp.test/end-session",
        jwks_uri="http://idp.test/jwks",
    )


def _mock_token_response(refresh_token: str = "rt-new"):
    return oauth_client.TokenResponse(
        access_token="at-new",
        refresh_token=refresh_token,
        expires_in=300,
        refresh_expires_in=30 * 24 * 60 * 60,
        id_token=None,
        token_type="Bearer",
        scope="openid email offline_access",
    )


async def test_login_returns_authorize_url_and_sets_state_cookie(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/login")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorize_url"].startswith("http://idp.test/authorize?")
    assert "code_challenge=" in body["authorize_url"]
    assert "code_challenge_method=S256" in body["authorize_url"]
    assert "state=" in body["authorize_url"]
    assert oauth_state_cookie.STATE_COOKIE_NAME in resp.cookies


async def test_login_unsafe_return_to_falls_back_to_root(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/login", params={"return_to": "http://evil.com/"})
    state_cookie = resp.cookies.get(oauth_state_cookie.STATE_COOKIE_NAME)
    assert state_cookie is not None
    payload = oauth_state_cookie.decrypt(state_cookie)
    assert payload.return_to == "/"


async def test_login_safe_return_to_is_preserved(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/login", params={"return_to": "/reports/123"})
    payload = oauth_state_cookie.decrypt(resp.cookies[oauth_state_cookie.STATE_COOKIE_NAME])
    assert payload.return_to == "/reports/123"


async def test_login_rewrites_internal_authorize_endpoint_to_external(mocker):
    """When discovery returns an internal-host URL, the SPA-facing authorize URL is externalized."""
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "http://localhost:9000/application/o/seizu")
    mocker.patch(
        "reporting.settings.OIDC_INTERNAL_AUTHORITY",
        "http://authentik-server:9000/application/o/seizu",
    )
    internal_metadata = oauth_client.OIDCMetadata(
        issuer="http://authentik-server:9000/application/o/seizu/",
        authorization_endpoint="http://authentik-server:9000/application/o/authorize/",
        token_endpoint="http://authentik-server:9000/application/o/token/",
        end_session_endpoint="http://authentik-server:9000/application/o/end-session/",
        jwks_uri="http://authentik-server:9000/application/o/seizu/jwks/",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=internal_metadata))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/login")
    assert resp.status_code == 200
    authorize_url = resp.json()["authorize_url"]
    assert authorize_url.startswith("http://localhost:9000/application/o/authorize/?")
    assert "authentik-server" not in authorize_url


async def test_callback_rejects_missing_state_cookie(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/auth/callback", params={"code": "c", "state": "s"})
    assert resp.status_code == 400


async def test_callback_rejects_state_mismatch(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    state_payload = oauth_state_cookie.OAuthStatePayload(
        state="real-state",
        verifier="v",
        return_to="/",
        exp=int(time.time()) + 60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(oauth_state_cookie.STATE_COOKIE_NAME, oauth_state_cookie.encrypt(state_payload))
        resp = await client.get("/api/v1/auth/callback", params={"code": "c", "state": "wrong-state"})
    assert resp.status_code == 400


async def test_callback_exchanges_code_sets_session_cookie_and_redirects(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    mocker.patch(
        "reporting.services.oauth_client.exchange_code",
        AsyncMock(return_value=_mock_token_response(refresh_token="rt-1")),
    )
    state = "matching-state"
    state_payload = oauth_state_cookie.OAuthStatePayload(
        state=state,
        verifier="verifier-1",
        return_to="/reports/abc",
        exp=int(time.time()) + 60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(oauth_state_cookie.STATE_COOKIE_NAME, oauth_state_cookie.encrypt(state_payload))
        resp = await client.get(
            "/api/v1/auth/callback",
            params={"code": "auth-code", "state": state},
            follow_redirects=False,
        )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/reports/abc"
    assert "seizu_session" in resp.cookies
    session_payload = session_cookie.decrypt(resp.cookies["seizu_session"])
    assert session_payload.refresh_token == "rt-1"


async def test_callback_rejects_when_idp_returns_no_refresh_token(mocker):
    mocker.patch("reporting.services.oauth_client.get_metadata", AsyncMock(return_value=_mock_metadata()))
    mocker.patch(
        "reporting.services.oauth_client.exchange_code",
        AsyncMock(return_value=_mock_token_response(refresh_token=None)),
    )
    state = "s"
    state_payload = oauth_state_cookie.OAuthStatePayload(
        state=state, verifier="v", return_to="/", exp=int(time.time()) + 60
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set(oauth_state_cookie.STATE_COOKIE_NAME, oauth_state_cookie.encrypt(state_payload))
        resp = await client.get("/api/v1/auth/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert resp.status_code == 400


async def test_refresh_returns_401_when_no_cookie():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/refresh", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 401


async def test_refresh_returns_new_access_token_and_rolls_cookie(mocker):
    mocker.patch(
        "reporting.services.oauth_client.refresh_tokens",
        AsyncMock(return_value=_mock_token_response(refresh_token="rt-rotated")),
    )
    payload = session_cookie.SessionPayload(
        refresh_token="rt-old",
        iat=int(time.time()) - 60,
        abs_exp=int(time.time()) + 30 * 24 * 60 * 60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("seizu_session", session_cookie.encrypt(payload))
        resp = await client.post("/api/v1/auth/refresh", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "at-new"
    assert body["token_type"] == "Bearer"
    # New cookie carries the rotated refresh token.
    new_payload = session_cookie.decrypt(resp.cookies["seizu_session"])
    assert new_payload.refresh_token == "rt-rotated"


async def test_refresh_clears_cookie_when_idp_rejects(mocker):
    mocker.patch(
        "reporting.services.oauth_client.refresh_tokens",
        AsyncMock(side_effect=oauth_client.OAuthClientError("invalid_grant")),
    )
    payload = session_cookie.SessionPayload(
        refresh_token="rt-revoked",
        iat=int(time.time()) - 60,
        abs_exp=int(time.time()) + 30 * 24 * 60 * 60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("seizu_session", session_cookie.encrypt(payload))
        resp = await client.post("/api/v1/auth/refresh", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 401
    # delete_cookie produces a Set-Cookie that expires the cookie.
    set_cookie = resp.headers.get("set-cookie", "")
    assert "seizu_session=" in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


async def test_logout_clears_cookie_and_calls_end_session(mocker):
    end_session_mock = AsyncMock()
    mocker.patch("reporting.services.oauth_client.end_session", end_session_mock)
    payload = session_cookie.SessionPayload(
        refresh_token="rt-active",
        iat=int(time.time()) - 60,
        abs_exp=int(time.time()) + 30 * 24 * 60 * 60,
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("seizu_session", session_cookie.encrypt(payload))
        resp = await client.post("/api/v1/auth/logout", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 204
    end_session_mock.assert_awaited_once()
    # passed the refresh token
    assert end_session_mock.await_args.kwargs["refresh_token"] == "rt-active"


async def test_logout_succeeds_without_cookie(mocker):
    end_session_mock = AsyncMock()
    mocker.patch("reporting.services.oauth_client.end_session", end_session_mock)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/logout", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 204
    end_session_mock.assert_not_awaited()


async def test_logout_swallows_idp_end_session_errors(mocker):
    mocker.patch(
        "reporting.services.oauth_client.end_session",
        AsyncMock(side_effect=RuntimeError("network down")),
    )
    payload = session_cookie.SessionPayload(refresh_token="rt", iat=int(time.time()), abs_exp=int(time.time()) + 60)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("seizu_session", session_cookie.encrypt(payload))
        resp = await client.post("/api/v1/auth/logout", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 204


async def test_logout_skips_end_session_when_disabled(mocker):
    mocker.patch("reporting.settings.OIDC_END_SESSION_ON_LOGOUT", False)
    end_session_mock = AsyncMock()
    mocker.patch("reporting.services.oauth_client.end_session", end_session_mock)
    payload = session_cookie.SessionPayload(refresh_token="rt", iat=int(time.time()), abs_exp=int(time.time()) + 60)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        client.cookies.set("seizu_session", session_cookie.encrypt(payload))
        resp = await client.post("/api/v1/auth/logout", headers={"X-Seizu-Csrf": "1"})
    assert resp.status_code == 204
    end_session_mock.assert_not_awaited()
