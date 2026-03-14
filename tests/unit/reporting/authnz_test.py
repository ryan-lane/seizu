import base64

import jwt
from jwt.api_jwk import PyJWK

import reporting.authnz
from reporting.app import create_app

# JWK that matches the private key
FAKE_KEY = {
    "kty": "EC",
    "use": "sig",
    "crv": "P-256",
    "kid": "-1gFFsnhuTW7Ym6yznOcZrpRiXiLQZ3NB6SvF6Wq1Eg",
    "x": "jCRyJB_B2VGnPTP6eHowt0W0OO6L4PUJrBiuQXIcnRY",
    "y": "6Tlze188qIGiwksLOMrzlV_OzSjvYM5kAEDC7rIFzBY",
    "alg": "ES256",
}

# This key is technically valid for encoding JWTs, but it's been generated only for development, and
# isn't used elsewhere.
FAKE_PRIVATE_KEY = (
    "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1FRUNBUUF3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRUp6QWxBZ0VCQkNDb0dLd"
    "C9ET0VkQU4xS2xvQ3EKeG5VU3RZV0FBd3c0dnpacWtHaGtWQ2dyY3c9PQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0t"
)


def _make_mock_signing_key(mocker):
    """Return a mock signing key backed by the fake EC public key."""
    signing_key = mocker.MagicMock()
    signing_key.key = PyJWK(FAKE_KEY).key
    return signing_key


def _make_mock_client(mocker, signing_key):
    """Return a mock PyJWKClient that returns the given signing key."""
    mock_client = mocker.MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = signing_key
    return mock_client


def test__get_jwt_payload_bearer(mocker):
    """JWT is read from an Authorization: Bearer header by default."""
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    app = create_app({"PREFERRED_URL_SCHEME": "https"})
    with app.test_request_context(
        headers={"Authorization": f"Bearer {encoded}"}
    ):
        assert reporting.authnz._get_jwt_payload() == {"email": "test@example.com"}


def test__get_jwt_payload_custom_header(mocker):
    """JWT is read from a custom header when JWT_HEADER_NAME is overridden."""
    mocker.patch("reporting.settings.JWT_HEADER_NAME", "x-amzn-oidc-data")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    app = create_app({"PREFERRED_URL_SCHEME": "https"})
    with app.test_request_context(
        headers={"x-amzn-oidc-data": encoded}
    ):
        assert reporting.authnz._get_jwt_payload() == {"email": "test@example.com"}


def test__get_jwt_payload_custom_email_claim(mocker):
    """Email is read from a configurable claim."""
    mocker.patch("reporting.settings.JWT_EMAIL_CLAIM", "preferred_username")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"preferred_username": "user@example.com"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    app = create_app({"PREFERRED_URL_SCHEME": "https"})
    with app.test_request_context(
        headers={"Authorization": f"Bearer {encoded}"}
    ):
        reporting.authnz._get_jwt_payload()


def test_get_email(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch(
        "reporting.authnz._get_jwt_payload",
        return_value={"email": "test@example.com"},
    )
    assert reporting.authnz.get_email() == "test@example.com"


def test_get_email_custom_claim(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.JWT_EMAIL_CLAIM", "preferred_username")
    mocker.patch(
        "reporting.authnz._get_jwt_payload",
        return_value={"preferred_username": "user@example.com"},
    )
    assert reporting.authnz.get_email() == "user@example.com"


def test_get_email_auth_disabled(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    mocker.patch(
        "reporting.settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL",
        "test@example.com",
    )
    assert reporting.authnz.get_email() == "test@example.com"
