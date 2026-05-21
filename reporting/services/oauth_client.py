"""OAuth/OIDC client for the BFF auth flow.

Thin facade over authlib's ``AsyncOAuth2Client`` plus a hand-rolled
discovery cache. Authlib handles the RFC 6749 / 7636 / OIDC token-endpoint
mechanics (PKCE, multiple ``token_endpoint_auth_method`` styles, error
parsing per RFC 6749 §5.2). We keep three things outside authlib:

- **Discovery fetching** — so we can use ``OIDC_INTERNAL_AUTHORITY`` for
  the server-side fetch while exposing the public ``OIDC_AUTHORITY`` to
  the browser.
- **``rewrite_to_external_origin``** — for IDPs that base discovery URLs
  on the request Host header and lack an explicit "browser host" setting.
- **``end_session``** — RP-initiated logout isn't standardized the way
  the token endpoint is, and authlib doesn't ship a helper.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.httpx_client import AsyncOAuth2Client

from reporting import settings

logger = logging.getLogger(__name__)

_OIDC_DISCOVERY_TIMEOUT = 10.0
_OIDC_REQUEST_TIMEOUT = 30.0


class OAuthClientError(RuntimeError):
    """Raised when an interaction with the IDP fails."""


@dataclass(frozen=True)
class OIDCMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    end_session_endpoint: str | None
    jwks_uri: str | None


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int | None
    refresh_expires_in: int | None
    id_token: str | None
    token_type: str
    scope: str | None


_metadata_cache: OIDCMetadata | None = None
_metadata_lock = asyncio.Lock()


def _authority_for_discovery() -> str:
    authority = (settings.OIDC_INTERNAL_AUTHORITY or settings.OIDC_AUTHORITY).rstrip("/")
    if not authority:
        raise OAuthClientError("OIDC_AUTHORITY (or OIDC_INTERNAL_AUTHORITY) must be configured")
    return authority


def rewrite_to_external_origin(url: str) -> str:
    """Swap an internal-authority origin for the externally-reachable one.

    Authentik (and some other IDPs) base discovery-document URLs on the
    request's Host header. In split-hostname docker-dev setups, the server
    fetches discovery from ``OIDC_INTERNAL_AUTHORITY`` (e.g.
    ``http://authentik-server:9000``) and gets back URLs with that
    docker-internal hostname — which the browser can't reach. For any URL
    we hand to the browser (currently just the authorize URL), rewrite the
    scheme+host+port to match ``OIDC_AUTHORITY``. URLs already on the
    external origin, or with no internal/external split configured, are
    returned unchanged.
    """
    internal_raw = settings.OIDC_INTERNAL_AUTHORITY
    external_raw = settings.OIDC_AUTHORITY
    if not internal_raw or not external_raw or internal_raw == external_raw:
        return url
    internal = urlparse(internal_raw)
    external = urlparse(external_raw)
    internal_origin = f"{internal.scheme}://{internal.netloc}"
    external_origin = f"{external.scheme}://{external.netloc}"
    if url.startswith(internal_origin):
        return external_origin + url[len(internal_origin) :]
    return url


async def get_metadata() -> OIDCMetadata:
    """Fetch and cache the IDP's OIDC discovery document."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache
    async with _metadata_lock:
        if _metadata_cache is not None:
            return _metadata_cache
        url = f"{_authority_for_discovery()}/.well-known/openid-configuration"
        try:
            async with httpx.AsyncClient(timeout=_OIDC_DISCOVERY_TIMEOUT) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                doc = resp.json()
        except httpx.HTTPError as exc:
            raise OAuthClientError(f"Failed to fetch OIDC discovery from {url}: {exc}") from exc

        try:
            metadata = OIDCMetadata(
                issuer=doc["issuer"],
                authorization_endpoint=doc["authorization_endpoint"],
                token_endpoint=doc["token_endpoint"],
                end_session_endpoint=doc.get("end_session_endpoint"),
                jwks_uri=doc.get("jwks_uri"),
            )
        except KeyError as exc:
            raise OAuthClientError(f"OIDC discovery document missing required field: {exc}") from exc
        _metadata_cache = metadata
        return metadata


def reset_metadata_cache() -> None:
    """Clear the cached discovery document (used in tests)."""
    global _metadata_cache
    _metadata_cache = None


def _coerce_token(data: Any) -> TokenResponse:
    """Convert authlib's OAuth2Token (a dict subclass) into our TokenResponse."""
    try:
        access_token = data["access_token"]
    except (KeyError, TypeError) as exc:
        raise OAuthClientError("IDP token response missing access_token") from exc
    return TokenResponse(
        access_token=access_token,
        refresh_token=data.get("refresh_token"),
        expires_in=data.get("expires_in"),
        refresh_expires_in=data.get("refresh_expires_in"),
        id_token=data.get("id_token"),
        token_type=data.get("token_type", "Bearer"),
        scope=data.get("scope"),
    )


def _build_oauth_client() -> AsyncOAuth2Client:
    if not settings.OIDC_CLIENT_ID:
        raise OAuthClientError("OIDC_CLIENT_ID must be configured")
    # token_endpoint_auth_method="none" → public client + PKCE; no client_secret.
    return AsyncOAuth2Client(
        client_id=settings.OIDC_CLIENT_ID,
        token_endpoint_auth_method="none",
        timeout=_OIDC_REQUEST_TIMEOUT,
    )


async def exchange_code(*, code: str, code_verifier: str, redirect_uri: str) -> TokenResponse:
    """Exchange an authorization code (with PKCE verifier) for tokens."""
    metadata = await get_metadata()
    async with _build_oauth_client() as client:
        try:
            token = await client.fetch_token(
                url=metadata.token_endpoint,
                grant_type="authorization_code",
                code=code,
                code_verifier=code_verifier,
                redirect_uri=redirect_uri,
            )
        except AuthlibBaseError as exc:
            raise OAuthClientError(f"Token exchange failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OAuthClientError(f"Token endpoint request failed: {exc}") from exc
    return _coerce_token(token)


async def refresh_tokens(*, refresh_token: str) -> TokenResponse:
    """Exchange a refresh token for a new access (and possibly refresh) token."""
    metadata = await get_metadata()
    async with _build_oauth_client() as client:
        try:
            token = await client.refresh_token(
                url=metadata.token_endpoint,
                refresh_token=refresh_token,
            )
        except AuthlibBaseError as exc:
            raise OAuthClientError(f"Token refresh failed: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OAuthClientError(f"Token endpoint request failed: {exc}") from exc
    return _coerce_token(token)


async def end_session(
    *,
    id_token_hint: str | None = None,
    refresh_token: str | None = None,
    post_logout_redirect_uri: str | None = None,
) -> None:
    """Call the IDP's RP-initiated logout endpoint.

    Best-effort: any failure is logged and swallowed so the user's local
    logout always succeeds. The endpoint may not exist on every IDP — in
    that case ``get_metadata().end_session_endpoint`` is ``None`` and this
    function is a no-op. Authlib doesn't ship an RP-initiated-logout
    helper, so this stays hand-rolled.
    """
    try:
        metadata = await get_metadata()
    except OAuthClientError as exc:
        logger.warning("Skipping end_session — discovery unavailable: %s", exc)
        return
    if not metadata.end_session_endpoint:
        logger.info("IDP advertises no end_session_endpoint; skipping RP-initiated logout")
        return

    params: dict[str, str] = {}
    if settings.OIDC_CLIENT_ID:
        params["client_id"] = settings.OIDC_CLIENT_ID
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    if refresh_token:
        # Some IDPs (Keycloak, Authentik) accept a refresh_token to revoke the
        # whole grant; ignored by others.
        params["refresh_token"] = refresh_token
    if post_logout_redirect_uri:
        params["post_logout_redirect_uri"] = post_logout_redirect_uri

    try:
        async with httpx.AsyncClient(timeout=_OIDC_REQUEST_TIMEOUT) as client:
            await client.post(metadata.end_session_endpoint, data=params)
    except httpx.HTTPError as exc:
        logger.warning("end_session_endpoint call failed (continuing logout): %s", exc)
