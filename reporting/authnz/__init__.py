import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from reporting import settings
from reporting.schema.report_config import User

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user: User
    jwt_claims: dict
    permissions: frozenset[str] = field(default_factory=frozenset)


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.JWKS_URL, cache_keys=True, timeout=settings.JWKS_FETCH_TIMEOUT)
    return _jwks_client


async def _get_jwt_payload(token: str) -> dict:
    """
    Get the JWT payload from a Bearer token string.

    Makes a potentially blocking HTTP call (JWKS fetch) in a thread pool.
    """
    client = _get_jwks_client()
    signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)

    decode_kwargs: dict = {
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
        "get_email() called in auth-required mode without a request context. Use get_current_user() instead."
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Validate the JWT and return a CurrentUser.

    In development mode (auth disabled) a synthetic dev user is returned.
    """
    from reporting.authnz.permissions import ALL_PERMISSIONS, resolve_permissions
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
            jwt_claims={"email": email, "display_name": None, "token_iat": None, "token_exp": None},
            permissions=ALL_PERMISSIONS,
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
    token_iat = datetime.fromtimestamp(raw_iat, tz=UTC) if raw_iat is not None else None
    raw_exp = payload.get("exp")
    token_exp = datetime.fromtimestamp(raw_exp, tz=UTC) if raw_exp is not None else None
    jwt_claims = {
        "email": payload[settings.JWT_EMAIL_CLAIM],
        "display_name": payload.get("name"),
        "token_iat": token_iat,
        "token_exp": token_exp,
    }

    user = await report_store.get_or_create_user(
        sub=payload[settings.JWT_SUB_CLAIM],
        iss=payload[settings.JWT_ISS_CLAIM],
        email=payload[settings.JWT_EMAIL_CLAIM],
        display_name=payload.get("name"),
    )

    permissions = await resolve_permissions(payload)

    return CurrentUser(user=user, jwt_claims=jwt_claims, permissions=permissions)


def require_permission(*perms: str) -> Callable:
    """Return a FastAPI dependency that checks the current user has all of the
    specified permissions.  Authentication is still enforced first.

    Usage::

        @router.get("/api/v1/reports")
        async def list_reports(
            current: CurrentUser = Depends(require_permission("reports:read")),
        ) -> ...:
    """

    async def _check(
        current: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing = set(perms) - current.permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(sorted(missing))}",
            )
        return current

    return _check


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
    return CurrentUser(user=updated_user, jwt_claims=claims, permissions=current.permissions)
