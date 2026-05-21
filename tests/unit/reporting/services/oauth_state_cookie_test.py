import base64
import os

import pytest

from reporting.services.oauth_state_cookie import (
    OAuthStateCookieError,
    OAuthStatePayload,
    decrypt,
    encrypt,
    is_safe_return_to,
)


@pytest.fixture(autouse=True)
def _configure_key(mocker):
    mocker.patch(
        "reporting.settings.SESSION_TOKEN_ENCRYPTION_KEY",
        base64.b64encode(os.urandom(32)).decode("ascii"),
    )


def _payload(**overrides):
    base = {
        "state": "state-abc",
        "verifier": "verifier-xyz",
        "return_to": "/reports/123",
        "exp": 10**12,
    }
    base.update(overrides)
    return OAuthStatePayload(**base)


async def test_encrypt_then_decrypt_roundtrips():
    payload = _payload()
    out = decrypt(encrypt(payload))
    assert out == payload


async def test_decrypt_rejects_tampered_ciphertext():
    cookie = encrypt(_payload())
    raw = bytearray(base64.urlsafe_b64decode(cookie + "=" * (-len(cookie) % 4)))
    raw[-1] ^= 0x01
    tampered = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode("ascii")
    with pytest.raises(OAuthStateCookieError, match="integrity check failed"):
        decrypt(tampered)


async def test_decrypt_rejects_expired_state():
    cookie = encrypt(_payload(exp=500))
    with pytest.raises(OAuthStateCookieError, match="expired"):
        decrypt(cookie, now=1_000)


async def test_decrypt_rejects_blank_state_or_verifier():
    cookie = encrypt(_payload(state="", verifier="v"))
    with pytest.raises(OAuthStateCookieError, match="invalid state/verifier"):
        decrypt(cookie)


async def test_is_safe_return_to_accepts_simple_path():
    assert is_safe_return_to("/")
    assert is_safe_return_to("/reports/123")
    assert is_safe_return_to("/reports?id=1&v=2")
    assert is_safe_return_to("/reports#section")


async def test_is_safe_return_to_rejects_external_urls():
    assert not is_safe_return_to("")
    assert not is_safe_return_to("http://evil.com/")
    assert not is_safe_return_to("https://evil.com/")
    assert not is_safe_return_to("//evil.com/path")  # protocol-relative
    assert not is_safe_return_to("/\\evil.com/path")  # browser-quirk backslash variant
    assert not is_safe_return_to("javascript:alert(1)")  # not even path-shaped


async def test_is_safe_return_to_rejects_control_chars():
    assert not is_safe_return_to("/reports\n/123")
    assert not is_safe_return_to("/reports\r\nLocation: http://x")
