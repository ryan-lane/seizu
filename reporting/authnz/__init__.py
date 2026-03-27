import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Dict
from typing import Optional

import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from jwt import PyJWKClient

from reporting import settings
from reporting.schema.report_config import User

logger = logging.getLogger(__name__)

_jwks_client: Optional[PyJWKClient] = None

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user: User
    jwt_claims: Dict


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.JWKS_URL, cache_keys=True)
    return _jwks_client


async def _get_jwt_payload(token: str) -> Dict:
    """
    Get the JWT payload from a Bearer token string.

    Makes a potentially blocking HTTP call (JWKS fetch) in a thread pool.
    """
    client = _get_jwks_client()
    signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)

    decode_kwargs: Dict = {
        "algorithms": settings.ALLOWED_JWT_ALGORITHMS,
    }
    if settings.JWT_ISSUER:
        decode_kwargs["issuer"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        decode_kwargs["audience"] = settings.JWT_AUDIENCE

    logger.debug("Decoding JWT")
    return jwt.decode(token, signing_key.key, **decode_kwargs)


def get_email() -> str:
    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
        logger.warning(
            "Authentication is disabled",
            extra={"type": "AUDIT", "user": email},
        )
        return email
    raise RuntimeError(
        "get_email() called in auth-required mode without a request context. "
        "Use get_current_user() instead."
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> CurrentUser:
    """Validate the JWT and return a CurrentUser.

    In development mode (auth disabled) a synthetic dev user is returned.
    """
    from reporting.services import report_store

    if not settings.DEVELOPMENT_ONLY_REQUIRE_AUTH:
        email = settings.DEVELOPMENT_ONLY_AUTH_USER_EMAIL
        logger.warning(
            "Authentication is disabled",
            extra={"type": "AUDIT", "user": email},
        )
        user = await report_store.get_or_create_user(
            sub=email,
            iss="dev",
            email=email,
            display_name=None,
        )
        return CurrentUser(
            user=user,
            jwt_claims={"email": email, "display_name": None, "token_iat": None},
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = await _get_jwt_payload(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    raw_iat = payload.get("iat")
    token_iat = (
        datetime.fromtimestamp(raw_iat, tz=timezone.utc)
        if raw_iat is not None
        else None
    )
    jwt_claims = {
        "email": payload[settings.JWT_EMAIL_CLAIM],
        "display_name": payload.get("name"),
        "token_iat": token_iat,
    }

    user = await report_store.get_or_create_user(
        sub=payload[settings.JWT_SUB_CLAIM],
        iss=payload[settings.JWT_ISS_CLAIM],
        email=payload[settings.JWT_EMAIL_CLAIM],
        display_name=payload.get("name"),
    )

    return CurrentUser(user=user, jwt_claims=jwt_claims)


async def sync_user_profile(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Update mutable profile fields for an already-authenticated user.

    Should be called only from routes where a profile sync is appropriate
    (e.g. ``GET /api/v1/me``).  Delegates to the store, which skips the
    write entirely if nothing has changed.
    """
    from reporting.services import report_store

    claims = current.jwt_claims
    updated_user = await report_store.update_user_profile(
        user_id=current.user.user_id,
        email=claims["email"],
        display_name=claims.get("display_name"),
        token_iat=claims.get("token_iat"),
    )
    return CurrentUser(user=updated_user, jwt_claims=claims)
