import logging
from datetime import datetime
from datetime import timezone
from functools import wraps
from typing import Any
from typing import Callable
from typing import Dict

import jwt
from flask import g
from flask import request
from jwt import PyJWKClient

from reporting import settings
from reporting.schema.report_config import User

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


def get_user() -> User:
    """Validate the JWT and return a persisted User, creating one on first login.

    Extracts ``sub``, ``iss``, ``email``, and optionally ``name`` from the JWT
    payload, then calls the report store's ``get_or_create_user`` to provision
    the user record on first login.  Existing users are returned as-is;
    profile updates (email drift, last_login) are applied only when the caller
    explicitly invokes ``sync_user_profile`` (e.g. the ``/api/v1/me`` route).

    Sets ``flask.g.jwt_claims`` with the relevant JWT fields so routes can
    pass them to ``sync_user_profile`` without re-decoding the token.

    In development mode (auth disabled) a synthetic dev user is returned using
    the configured ``DEVELOPMENT_ONLY_AUTH_USER_EMAIL``.
    """
    from reporting.services import report_store

    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
        logger.warning(
            "Authentication is disabled",
            extra={"type": "AUDIT", "user": email},
        )
        g.jwt_claims = {"email": email, "display_name": None, "token_iat": None}
        return report_store.get_or_create_user(
            sub=email,
            iss="dev",
            email=email,
            display_name=None,
        )
    payload = _get_jwt_payload()
    raw_iat = payload.get("iat")
    token_iat = (
        datetime.fromtimestamp(raw_iat, tz=timezone.utc)
        if raw_iat is not None
        else None
    )
    g.jwt_claims = {
        "email": payload[settings.JWT_EMAIL_CLAIM],
        "display_name": payload.get("name"),
        "token_iat": token_iat,
    }
    return report_store.get_or_create_user(
        sub=payload[settings.JWT_SUB_CLAIM],
        iss=payload[settings.JWT_ISS_CLAIM],
        email=payload[settings.JWT_EMAIL_CLAIM],
        display_name=payload.get("name"),
    )


def sync_user_profile(user: User) -> User:
    """Update mutable profile fields for an already-authenticated user.

    Should be called only from routes where a profile sync is appropriate
    (e.g. ``GET /api/v1/me``).  Reads JWT claims from ``flask.g.jwt_claims``
    populated by ``get_user()`` and delegates to the store, which skips the
    write entirely if nothing has changed.
    """
    from reporting.services import report_store

    claims = g.jwt_claims
    return report_store.update_user_profile(
        user_id=user.user_id,
        email=claims["email"],
        display_name=claims.get("display_name"),
        token_iat=claims.get("token_iat"),
    )


def require_auth(f: Callable) -> Callable:
    """Decorator that validates the JWT and populates ``flask.g.current_user``.

    Apply to any route that requires authentication.  The resolved
    :class:`~reporting.schema.report_config.User` is available inside the
    decorated function as ``g.current_user``.
    """

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        g.current_user = get_user()
        return f(*args, **kwargs)

    return decorated
