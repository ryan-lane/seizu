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


def test__get_key(mocker):
    mocker.patch("reporting.settings.JWKS_URL_FOR_ALB", True)
    mocker.patch("jwt.get_unverified_header", return_value={"kid": FAKE_KEY["kid"]})
    get_mock = mocker.MagicMock()
    get_mock.content = "-----BEGIN PUBLIC KEY-----...\n"
    mocker.patch("reporting.authnz.requests.get", return_value=get_mock)
    key = reporting.authnz._get_key("fake_token")
    assert key == "-----BEGIN PUBLIC KEY-----...\n"


def test__get_key_not_alb(mocker):
    mocker.patch("reporting.settings.JWKS_URL_FOR_ALB", False)
    mocker.patch("jwt.get_unverified_header", return_value={"kid": FAKE_KEY["kid"]})
    get_mock = mocker.MagicMock()
    get_mock.json.return_value = {"keys": [FAKE_KEY]}
    mocker.patch("reporting.authnz.requests.get", return_value=get_mock)
    key = reporting.authnz._get_key("fake_token")
    assert key.key_size == 256


def test__get_jwt_payload(mocker):
    key = PyJWK(FAKE_KEY).key
    mocker.patch("reporting.authnz._get_key", return_value=key)
    encoded = jwt.encode(
        {"email": "test@example.com"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    settings = {
        "PREFERRED_URL_SCHEME": "https",
    }
    app = create_app(settings)
    with app.test_request_context(headers={"x-amzn-oidc-data": encoded}):
        assert reporting.authnz._get_jwt_payload() == {"email": "test@example.com"}


def test_get_email(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch(
        "reporting.authnz._get_jwt_payload",
        return_value={"email": "test@example.com"},
    )
    assert reporting.authnz.get_email() == "test@example.com"


def test_get_email_auth_disabled(mocker):
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    mocker.patch(
        "reporting.settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL",
        "test@example.com",
    )
    assert reporting.authnz.get_email() == "test@example.com"
