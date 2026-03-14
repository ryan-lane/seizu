import logging
from typing import Dict

import jwt
from jwt import PyJWKClient
from flask import request

from reporting import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.JWKS_URL, cache_keys=True)
    return _jwks_client


def _get_jwt_payload() -> Dict:
    """
    Get the JWT payload from the request headers.

    Reads the token from the header specified by JWT_HEADER_NAME. When the
    header is ``Authorization``, the ``Bearer `` prefix is stripped. For any
    other header name the raw value is used as the token (e.g. the AWS ALB
    ``x-amzn-oidc-data`` header).
    """
    header_name = settings.JWT_HEADER_NAME
    header_value = request.headers.get(header_name)
    if not header_value:
        raise ValueError(f"Missing JWT header: {header_name}")

    if header_name.lower() == "authorization":
        if not header_value.startswith("Bearer "):
            raise ValueError("Authorization header must use Bearer scheme")
        token = header_value[7:]
    else:
        token = header_value

    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)

    decode_kwargs: Dict = {
        "algorithms": settings.ALLOWED_JWT_ALGORITHMS,
    }
    if settings.JWT_ISSUER:
        decode_kwargs["issuer"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        decode_kwargs["audience"] = settings.JWT_AUDIENCE

    logger.debug("Decoding JWT", extra={"header": header_name})
    return jwt.decode(token, signing_key.key, **decode_kwargs)


def get_email() -> str:
    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
        logger.warning(
            "Authentication is disabled",
            extra={"type": "AUDIT", "user": email},
        )
        return email
    payload = _get_jwt_payload()
    return payload[settings.JWT_EMAIL_CLAIM]
