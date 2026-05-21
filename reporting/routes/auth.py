"""BFF auth routes.

Browser-only auth flow that keeps the IDP refresh token out of JavaScript:

- ``GET  /api/v1/auth/login``     — start an Authorization Code + PKCE flow
- ``GET  /api/v1/auth/callback``  — IDP redirects here; we exchange code, set cookie
- ``POST /api/v1/auth/refresh``   — silent renewal; returns a new access token
- ``POST /api/v1/auth/logout``    — clear cookie + best-effort RP-initiated logout

The session cookie itself is the entire session state; see
``reporting/services/session_cookie.py``. The browser only ever holds the
short-lived access token in memory.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from reporting import settings
from reporting.services import oauth_client, oauth_state_cookie, session_cookie

logger = logging.getLogger(__name__)

router = APIRouter()

# Authentik's default refresh-token lifetime is 30 days; if the IDP doesn't
# advertise refresh_expires_in, we use this as the absolute upper bound.
_DEFAULT_REFRESH_EXPIRES_IN_SECONDS = 30 * 24 * 60 * 60


class LoginResponse(BaseModel):
    """Body returned by GET /api/v1/auth/login — SPA reads ``authorize_url`` and navigates to it."""

    authorize_url: str


class RefreshResponse(BaseModel):
    """Body returned by POST /api/v1/auth/refresh — new short-lived access token."""

    access_token: str
    expires_in: int | None
    token_type: str


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _generate_pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` per RFC 7636 S256."""
    verifier = _b64url(secrets.token_bytes(64))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def _build_callback_url(request: Request) -> str:
    """Compute the redirect_uri to register with the IDP for this request.

    Uses settings.OIDC_REDIRECT_URI when set (production / explicit config);
    otherwise derives ``<scheme>://<host>/api/v1/auth/callback`` from the
    incoming request URL, which is what dev environments need.
    """
    if settings.OIDC_REDIRECT_URI:
        return settings.OIDC_REDIRECT_URI
    return str(request.url_for("auth_callback"))


def _set_session_cookie(response: Response, payload: session_cookie.SessionPayload) -> None:
    max_age = session_cookie.compute_cookie_max_age(payload.abs_exp)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_cookie.encrypt(payload),
        max_age=max_age,
        httponly=True,
        secure=settings.TALISMAN_FORCE_HTTPS,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.TALISMAN_FORCE_HTTPS,
        samesite="strict",
    )


def _set_state_cookie(response: Response, payload: oauth_state_cookie.OAuthStatePayload) -> None:
    response.set_cookie(
        key=oauth_state_cookie.STATE_COOKIE_NAME,
        value=oauth_state_cookie.encrypt(payload),
        max_age=oauth_state_cookie.STATE_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.TALISMAN_FORCE_HTTPS,
        # Lax is required: the IDP redirects back via a top-level cross-site
        # navigation, and Strict would suppress the cookie on that hop.
        samesite="lax",
        path="/",
    )


def _clear_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=oauth_state_cookie.STATE_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.TALISMAN_FORCE_HTTPS,
        samesite="lax",
    )


def _safe_return_to(value: str | None) -> str:
    """Coerce ``value`` to a same-origin path or fall back to ``/``."""
    if value and oauth_state_cookie.is_safe_return_to(value):
        return value
    return "/"


@router.get("/api/v1/auth/login", response_model=LoginResponse)
async def auth_login(
    request: Request,
    response: Response,
    return_to: Annotated[str | None, Query()] = None,
) -> LoginResponse:
    """Begin a PKCE-protected Authorization Code flow.

    Sets a short-lived ``seizu_oauth_state`` cookie carrying the PKCE
    verifier, the OAuth ``state`` value, and the validated ``return_to`` URL.
    Returns the IDP's authorize URL; the SPA top-level-navigates to it.
    """
    if not settings.OIDC_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC is not configured on this server",
        )

    try:
        metadata = await oauth_client.get_metadata()
    except oauth_client.OAuthClientError as exc:
        logger.error("OIDC discovery failed in /auth/login: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC provider unavailable",
        ) from exc

    verifier, challenge = _generate_pkce_pair()
    state = _b64url(secrets.token_bytes(32))
    safe_return_to = _safe_return_to(return_to)
    redirect_uri = _build_callback_url(request)

    state_payload = oauth_state_cookie.OAuthStatePayload(
        state=state,
        verifier=verifier,
        return_to=safe_return_to,
        exp=int(time.time()) + oauth_state_cookie.STATE_COOKIE_MAX_AGE_SECONDS,
    )
    _set_state_cookie(response, state_payload)

    params = {
        "response_type": "code",
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": settings.OIDC_SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return LoginResponse(authorize_url=f"{metadata.authorization_endpoint}?{urlencode(params)}")


@router.get("/api/v1/auth/callback", name="auth_callback", include_in_schema=False)
async def auth_callback(
    request: Request,
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
    seizu_oauth_state: Annotated[str | None, Cookie()] = None,
) -> Response:
    """Handle the IDP's redirect back to us.

    Verifies ``state`` against the state cookie, exchanges ``code`` (with
    PKCE verifier) for tokens at the IDP, sets the session cookie, and 302s
    to the validated ``return_to``. The state cookie is cleared in all
    outcomes (success or error) so it can't be replayed.
    """
    if error:
        logger.warning("IDP returned error on callback: %s (%s)", error, error_description)
        response = RedirectResponse(url="/?auth_error=" + error, status_code=status.HTTP_302_FOUND)
        _clear_state_cookie(response)
        return response

    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code or state")

    if not seizu_oauth_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth state cookie")

    try:
        state_payload = oauth_state_cookie.decrypt(seizu_oauth_state)
    except oauth_state_cookie.OAuthStateCookieError as exc:
        logger.warning("Invalid state cookie on callback: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc

    if not secrets.compare_digest(state_payload.state, state):
        logger.warning("State mismatch on OAuth callback")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state mismatch")

    try:
        token_response = await oauth_client.exchange_code(
            code=code,
            code_verifier=state_payload.verifier,
            redirect_uri=_build_callback_url(request),
        )
    except oauth_client.OAuthClientError as exc:
        logger.warning("Token exchange failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange failed") from exc

    if not token_response.refresh_token:
        # offline_access scope wasn't honored, or the IDP refused to issue
        # a refresh token. We can't run a BFF session without one.
        logger.error("IDP did not return a refresh token; check OIDC_SCOPE includes offline_access")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IDP did not return a refresh token",
        )

    now = int(time.time())
    refresh_expires_in = token_response.refresh_expires_in or _DEFAULT_REFRESH_EXPIRES_IN_SECONDS
    abs_exp = now + refresh_expires_in
    session_payload = session_cookie.SessionPayload(
        refresh_token=token_response.refresh_token,
        iat=now,
        abs_exp=abs_exp,
    )

    response = RedirectResponse(url=state_payload.return_to, status_code=status.HTTP_302_FOUND)
    _set_session_cookie(response, session_payload)
    _clear_state_cookie(response)
    return response


def _unauthenticated_response(detail: str, *, clear_cookie: bool) -> JSONResponse:
    """Return a 401 JSONResponse, optionally clearing the session cookie.

    Returning a Response directly bypasses the global HTTPException handler,
    which otherwise rebuilds the response and would drop our Set-Cookie.
    """
    response = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"error": detail})
    if clear_cookie:
        _clear_session_cookie(response)
    return response


@router.post("/api/v1/auth/refresh", response_model=RefreshResponse)
async def auth_refresh(
    response: Response,
    seizu_session: Annotated[str | None, Cookie(alias="seizu_session")] = None,
) -> RefreshResponse | JSONResponse:
    """Exchange the cookie's refresh token for a new access token.

    Re-issues the session cookie with a rolling Max-Age. Returns 401 (and
    clears the cookie) if the cookie is invalid or the IDP rejects the
    refresh token — that's the path where the user is logged out and must
    re-authenticate.
    """
    # NB: ``seizu_session`` is a static parameter name because FastAPI's Cookie
    # extractor needs a literal name; we keep settings.SESSION_COOKIE_NAME for
    # consistency on the *set* side, but reads here are by the default name.
    if not seizu_session:
        return _unauthenticated_response("No session", clear_cookie=False)

    try:
        session_payload = session_cookie.decrypt(seizu_session)
    except session_cookie.SessionCookieError as exc:
        logger.info("Invalid session cookie on refresh: %s", exc)
        return _unauthenticated_response("Invalid session", clear_cookie=True)

    try:
        token_response = await oauth_client.refresh_tokens(refresh_token=session_payload.refresh_token)
    except oauth_client.OAuthClientError as exc:
        logger.info("IDP rejected refresh token: %s", exc)
        return _unauthenticated_response("Session expired", clear_cookie=True)

    new_refresh_token = token_response.refresh_token or session_payload.refresh_token
    new_payload = session_cookie.SessionPayload(
        refresh_token=new_refresh_token,
        iat=session_payload.iat,
        abs_exp=session_payload.abs_exp,
    )
    _set_session_cookie(response, new_payload)

    return RefreshResponse(
        access_token=token_response.access_token,
        expires_in=token_response.expires_in,
        token_type=token_response.token_type,
    )


@router.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout(
    response: Response,
    seizu_session: Annotated[str | None, Cookie(alias="seizu_session")] = None,
) -> Response:
    """Drop the session cookie and (optionally) call the IDP's end_session_endpoint.

    Always succeeds from the user's perspective. Best-effort IDP logout
    failures are logged but never block the local logout.
    """
    refresh_token: str | None = None
    if seizu_session:
        try:
            refresh_token = session_cookie.decrypt(seizu_session).refresh_token
        except session_cookie.SessionCookieError:
            refresh_token = None

    if settings.OIDC_END_SESSION_ON_LOGOUT and refresh_token:
        try:
            await oauth_client.end_session(refresh_token=refresh_token)
        except Exception as exc:  # noqa: BLE001 — defensive: never let logout fail
            logger.warning("IDP end_session failed (continuing logout): %s", exc)

    _clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
