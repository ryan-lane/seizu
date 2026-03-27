import base64
from unittest.mock import AsyncMock

import jwt
import pytest
from jwt.api_jwk import PyJWK

from reporting.authnz import _get_jwt_payload
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user

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


async def test__get_jwt_payload_valid_token(mocker):
    """_get_jwt_payload decodes a valid JWT token."""
    mocker.patch("reporting.settings.JWT_AUDIENCE", "")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    payload = await _get_jwt_payload(encoded)
    assert payload == {"email": "test@example.com"}


async def test__get_jwt_payload_with_audience(mocker):
    """JWT audience claim is accepted when JWT_AUDIENCE matches."""
    mocker.patch("reporting.settings.JWT_AUDIENCE", "myapp")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com", "aud": "myapp"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    payload = await _get_jwt_payload(encoded)
    assert payload["email"] == "test@example.com"


async def test__get_jwt_payload_audience_mismatch(mocker):
    """JWT with wrong audience claim is rejected."""
    mocker.patch("reporting.settings.JWT_AUDIENCE", "myapp")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com", "aud": "other-app"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    with pytest.raises(jwt.exceptions.InvalidAudienceError):
        await _get_jwt_payload(encoded)


async def test__get_jwt_payload_aud_in_token_but_not_configured(mocker):
    """Token with aud claim fails when JWT_AUDIENCE is not set (PyJWT requirement)."""
    mocker.patch("reporting.settings.JWT_AUDIENCE", "")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)
    encoded = jwt.encode(
        {"email": "test@example.com", "aud": "myapp"},
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    with pytest.raises(jwt.exceptions.InvalidAudienceError):
        await _get_jwt_payload(encoded)


async def test_get_current_user_auth_disabled(mocker):
    """In dev mode (auth disabled) a synthetic dev user is returned without a token."""
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", False)
    mocker.patch(
        "reporting.settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL",
        "devuser@example.com",
    )
    from reporting.schema.report_config import User

    fake_user = User(
        user_id="dev-uid",
        sub="devuser@example.com",
        iss="dev",
        email="devuser@example.com",
        created_at="2024-01-01T00:00:00+00:00",
        last_login="2024-01-01T00:00:00+00:00",
    )
    mock_get_or_create = mocker.patch(
        "reporting.services.report_store.get_or_create_user",
        new=AsyncMock(return_value=fake_user),
    )
    result = await get_current_user(credentials=None)
    assert isinstance(result, CurrentUser)
    assert result.user.email == "devuser@example.com"
    mock_get_or_create.assert_called_once_with(
        sub="devuser@example.com",
        iss="dev",
        email="devuser@example.com",
        display_name=None,
    )


async def test_get_current_user_no_credentials_raises(mocker):
    """When auth is required but no credentials provided, 401 is raised."""
    from fastapi import HTTPException

    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None)
    assert exc_info.value.status_code == 401


async def test_get_current_user_extracts_sub_and_iss(mocker):
    """get_current_user extracts sub and iss from JWT and calls get_or_create_user."""
    mocker.patch("reporting.settings.DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
    mocker.patch("reporting.settings.JWT_AUDIENCE", "")
    signing_key = _make_mock_signing_key(mocker)
    mock_client = _make_mock_client(mocker, signing_key)
    mocker.patch("reporting.authnz._get_jwks_client", return_value=mock_client)

    from reporting.schema.report_config import User
    from fastapi.security import HTTPAuthorizationCredentials

    fake_user = User(
        user_id="uid1",
        sub="sub123",
        iss="https://idp.example.com",
        email="alice@example.com",
        display_name="Alice",
        created_at="2024-01-01T00:00:00+00:00",
        last_login="2024-01-01T00:00:00+00:00",
    )
    mock_get_or_create = mocker.patch(
        "reporting.services.report_store.get_or_create_user",
        new=AsyncMock(return_value=fake_user),
    )

    encoded = jwt.encode(
        {
            "email": "alice@example.com",
            "sub": "sub123",
            "iss": "https://idp.example.com",
            "name": "Alice",
            "iat": 1704067200,
        },
        base64.b64decode(FAKE_PRIVATE_KEY),
        algorithm="ES256",
    )
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=encoded)
    result = await get_current_user(credentials=credentials)
    mock_get_or_create.assert_called_once_with(
        sub="sub123",
        iss="https://idp.example.com",
        email="alice@example.com",
        display_name="Alice",
    )
    assert result.user.user_id == "uid1"
