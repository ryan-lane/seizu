import pytest

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
