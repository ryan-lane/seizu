"""Encrypted session cookie carrying the IDP refresh token.

The cookie is the entire BFF session — there is no server-side session store.
After AES-GCM decryption, the payload is a JSON object with four fields:

- ``rt``       — the opaque IDP refresh token
- ``id_token`` — the ID token from login, used only as an RP logout hint
- ``iat``      — unix timestamp the session was first established
- ``abs_exp``  — unix timestamp upper bound; rolling refreshes never extend
                 the cookie past this point. Set at login time to the IDP
                 refresh token's own ``refresh_expires_in`` (or, if the IDP
                 doesn't advertise one, ``iat`` + 30 days).

Wire format: ``base64url(nonce || ciphertext_and_tag)`` where the plaintext
is the JSON-encoded payload above. AES-GCM provides authenticated encryption,
so tampering with any byte yields a decryption error.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from reporting import settings

_KEY_BYTES = 32
_NONCE_BYTES = 12
_GCM_TAG_BYTES = 16


class SessionCookieError(ValueError):
    """Raised when a session cookie is malformed, tampered with, or expired."""


@dataclass(frozen=True)
class SessionPayload:
    refresh_token: str
    iat: int
    abs_exp: int
    id_token: str | None = None


def _get_key() -> bytes:
    raw = settings.SESSION_TOKEN_ENCRYPTION_KEY
    if not raw:
        raise RuntimeError("SESSION_TOKEN_ENCRYPTION_KEY must be configured (32 random bytes, base64-encoded)")
    try:
        key = base64.b64decode(raw, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("SESSION_TOKEN_ENCRYPTION_KEY must be valid base64") from exc
    if len(key) != _KEY_BYTES:
        raise RuntimeError(f"SESSION_TOKEN_ENCRYPTION_KEY must decode to {_KEY_BYTES} bytes (got {len(key)})")
    return key


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encrypt(payload: SessionPayload) -> str:
    """Encrypt a SessionPayload into the cookie wire value."""
    plaintext = json.dumps(
        {
            "rt": payload.refresh_token,
            "id_token": payload.id_token,
            "iat": payload.iat,
            "abs_exp": payload.abs_exp,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    aesgcm = AESGCM(_get_key())
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return _b64url_encode(nonce + ciphertext)


def decrypt(cookie_value: str, *, now: int | None = None) -> SessionPayload:
    """Decrypt and validate a cookie wire value.

    Raises SessionCookieError if the cookie is malformed, fails AEAD
    authentication, has an invalid payload shape, or has passed its
    ``abs_exp`` upper bound. The HTTP-level Max-Age expiry is enforced by the
    browser (cookie not sent); ``abs_exp`` is enforced here as defense in
    depth for the rolling-refresh path.
    """
    try:
        blob = _b64url_decode(cookie_value)
    except (ValueError, binascii.Error) as exc:
        raise SessionCookieError("Malformed session cookie") from exc
    if len(blob) < _NONCE_BYTES + _GCM_TAG_BYTES:
        raise SessionCookieError("Session cookie too short")
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    aesgcm = AESGCM(_get_key())
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise SessionCookieError("Session cookie integrity check failed") from exc

    try:
        data = json.loads(plaintext)
    except json.JSONDecodeError as exc:
        raise SessionCookieError("Session cookie payload is not valid JSON") from exc
    if not isinstance(data, dict):
        raise SessionCookieError("Session cookie payload is not an object")

    try:
        rt = data["rt"]
        id_token = data.get("id_token")
        iat = int(data["iat"])
        abs_exp = int(data["abs_exp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SessionCookieError("Session cookie payload is missing required fields") from exc
    if not isinstance(rt, str) or not rt:
        raise SessionCookieError("Session cookie payload has an invalid refresh token")
    if id_token is not None and (not isinstance(id_token, str) or not id_token):
        raise SessionCookieError("Session cookie payload has an invalid ID token")

    current = int(time.time()) if now is None else now
    if abs_exp <= current:
        raise SessionCookieError("Session cookie has passed its absolute expiry")

    return SessionPayload(refresh_token=rt, id_token=id_token, iat=iat, abs_exp=abs_exp)


def compute_cookie_max_age(abs_exp: int, *, now: int | None = None) -> int:
    """Return the cookie Max-Age to set on a (rolling) refresh response.

    The cookie's lifetime is the *minimum* of the configured rolling window
    and the time remaining until ``abs_exp``. Never negative.
    """
    current = int(time.time()) if now is None else now
    remaining = max(0, abs_exp - current)
    return min(settings.SESSION_COOKIE_MAX_AGE_SECONDS, remaining)
