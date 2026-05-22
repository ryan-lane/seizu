import pytest

from reporting.services import oauth_client
from reporting.services.oauth_client import rewrite_to_external_origin


@pytest.fixture(autouse=True)
def _split_authority_env(mocker):
    """The browser-vs-server hostname split docker-dev runs with."""
    mocker.patch("reporting.settings.OIDC_AUTHORITY", "http://localhost:9000/application/o/seizu")
    mocker.patch(
        "reporting.settings.OIDC_INTERNAL_AUTHORITY",
        "http://authentik-server:9000/application/o/seizu",
    )


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
    mocker.patch("reporting.settings.OIDC_CLIENT_ID", "seizu")

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
