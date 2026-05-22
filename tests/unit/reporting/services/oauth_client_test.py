import pytest

from reporting.services import oauth_client
from reporting.services.oauth_client import rewrite_to_external_origin


@pytest.fixture(autouse=True)
def _split_authority_env(mocker):
    """The browser-vs-server hostname split docker-dev runs with."""
    oauth_client.reset_metadata_cache()
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "http://localhost:9000/application/o/seizu")
    mocker.patch(
        "reporting.settings.OIDC_INTERNAL_AUTHORITY",
        "http://authentik-server:9000/application/o/seizu",
    )
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "seizu")
    mocker.patch("reporting.settings.OIDC_CLIENT_SECRET", "")
    mocker.patch("reporting.settings.OIDC_SCOPE", "openid email offline_access")
    mocker.patch("reporting.settings.OIDC_TOKEN_ENDPOINT_AUTH_METHOD", "none")
    mocker.patch("reporting.settings.OIDC_REVOCATION_ENDPOINT_AUTH_METHOD", "none")
    yield
    oauth_client.reset_metadata_cache()


async def test_rewrites_internal_origin_to_external():
    out = rewrite_to_external_origin("http://authentik-server:9000/application/o/authorize/?x=1")
    assert out == "http://localhost:9000/application/o/authorize/?x=1"


async def test_leaves_external_origin_untouched():
    out = rewrite_to_external_origin("http://localhost:9000/application/o/authorize/?x=1")
    assert out == "http://localhost:9000/application/o/authorize/?x=1"


async def test_leaves_unrelated_origin_untouched():
    # Some IDP-returned URL from a third origin (shouldn't happen with sane
    # Authentik config, but be conservative and not rewrite something we
    # don't recognize).
    out = rewrite_to_external_origin("http://other.example.com/oauth/authorize")
    assert out == "http://other.example.com/oauth/authorize"


async def test_no_rewrite_when_internal_unset(mocker):
    mocker.patch("reporting.settings.OIDC_INTERNAL_AUTHORITY", "")
    out = rewrite_to_external_origin("http://localhost:9000/authorize")
    assert out == "http://localhost:9000/authorize"


async def test_no_rewrite_when_internal_equals_external(mocker):
    mocker.patch("reporting.settings.OIDC_INTERNAL_AUTHORITY", "http://localhost:9000")
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "http://localhost:9000")
    out = rewrite_to_external_origin("http://localhost:9000/authorize")
    assert out == "http://localhost:9000/authorize"


async def test_revoke_refresh_token_posts_to_revocation_endpoint(mocker):
    metadata = oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint="http://idp.test/end-session",
        revocation_endpoint="http://idp.test/revoke",
        jwks_uri="http://idp.test/jwks",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", mocker.AsyncMock(return_value=metadata))
    calls = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeOAuthClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def revoke_token(self, url, token, token_type_hint, body):
            calls.append((url, token, token_type_hint, body))
            return FakeResponse()

    mocker.patch("reporting.services.oauth_client._build_oauth_client", return_value=FakeOAuthClient())

    await oauth_client.revoke_refresh_token(refresh_token="rt-active")

    assert calls == [
        (
            "http://idp.test/revoke",
            "rt-active",
            "refresh_token",
            "client_id=seizu",
        )
    ]


async def test_revoke_refresh_token_omits_public_client_body_for_confidential_revocation(mocker):
    mocker.patch("reporting.settings.OIDC_REVOCATION_ENDPOINT_AUTH_METHOD", "client_secret_basic")
    metadata = oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint="http://idp.test/end-session",
        revocation_endpoint="http://idp.test/revoke",
        jwks_uri="http://idp.test/jwks",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", mocker.AsyncMock(return_value=metadata))

    calls = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeOAuthClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def revoke_token(self, url, token, token_type_hint, body):
            calls.append((url, token, token_type_hint, body))
            return FakeResponse()

    mocker.patch("reporting.services.oauth_client._build_oauth_client", return_value=FakeOAuthClient())

    await oauth_client.revoke_refresh_token(refresh_token="rt-active")

    assert calls == [("http://idp.test/revoke", "rt-active", "refresh_token", "")]


async def test_revoke_refresh_token_skips_when_endpoint_missing(mocker):
    metadata = oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint="http://idp.test/end-session",
        revocation_endpoint=None,
        jwks_uri="http://idp.test/jwks",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", mocker.AsyncMock(return_value=metadata))
    build_client_mock = mocker.patch("reporting.services.oauth_client._build_oauth_client")

    await oauth_client.revoke_refresh_token(refresh_token="rt-active")

    build_client_mock.assert_not_called()


async def test_build_authorize_url_uses_authlib_pkce_builder():
    url = await oauth_client.build_authorize_url(
        authorization_endpoint="http://authentik-server:9000/application/o/authorize/",
        state="state-123",
        code_verifier="verifier-123",
        redirect_uri="http://localhost:3000/api/v1/auth/callback",
    )

    assert url.startswith("http://localhost:9000/application/o/authorize/?")
    assert "state=state-123" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Fapi%2Fv1%2Fauth%2Fcallback" in url


async def test_get_metadata_rejects_unexpected_issuer(mocker):
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "https://expected.example.com/o/seizu")
    mocker.patch("reporting.settings.OIDC_INTERNAL_AUTHORITY", "")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return {
                "issuer": "https://evil.example.com/o/seizu",
                "authorization_endpoint": "https://evil.example.com/authorize",
                "token_endpoint": "https://evil.example.com/token",
                "jwks_uri": "https://evil.example.com/jwks",
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url):
            return FakeResponse()

    mocker.patch("reporting.services.oauth_client.httpx.AsyncClient", FakeAsyncClient)

    with pytest.raises(oauth_client.OAuthClientError, match="issuer mismatch"):
        await oauth_client.get_metadata()


async def test_build_post_logout_url_uses_external_end_session_endpoint(mocker):
    metadata = oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint="http://authentik-server:9000/application/o/seizu/end-session/",
        revocation_endpoint="http://idp.test/revoke",
        jwks_uri="http://idp.test/jwks",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", mocker.AsyncMock(return_value=metadata))

    url = await oauth_client.build_post_logout_url(
        id_token_hint="id-token-1",
        post_logout_redirect_uri="http://localhost:3000/logged-out",
    )

    assert url is not None
    assert url.startswith("http://localhost:9000/application/o/seizu/end-session/?")
    assert "client_id=seizu" in url
    assert "id_token_hint=id-token-1" in url
    assert "post_logout_redirect_uri=http%3A%2F%2Flocalhost%3A3000%2Flogged-out" in url


async def test_build_post_logout_url_skips_when_endpoint_missing(mocker):
    metadata = oauth_client.OIDCMetadata(
        issuer="http://idp.test",
        authorization_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        end_session_endpoint=None,
        revocation_endpoint="http://idp.test/revoke",
        jwks_uri="http://idp.test/jwks",
    )
    mocker.patch("reporting.services.oauth_client.get_metadata", mocker.AsyncMock(return_value=metadata))

    url = await oauth_client.build_post_logout_url(
        id_token_hint=None,
        post_logout_redirect_uri="http://localhost:3000/logged-out",
    )

    assert url is None
