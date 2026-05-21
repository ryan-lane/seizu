"""OAuth/OIDC client for the BFF auth flow.

Talks to the configured IDP's token endpoint and (optionally) its
end-session endpoint. Discovery is lazy and cached process-wide; the
discovery document is fetched once and re-used for the life of the
process. To re-discover (e.g. after IDP config changes), restart the app.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

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


def _parse_token_response(data: dict[str, Any]) -> TokenResponse:
    try:
        access_token = data["access_token"]
    except KeyError as exc:
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


async def _post_token_endpoint(form: dict[str, str]) -> TokenResponse:
    metadata = await get_metadata()
    try:
        async with httpx.AsyncClient(timeout=_OIDC_REQUEST_TIMEOUT) as client:
            resp = await client.post(metadata.token_endpoint, data=form)
    except httpx.HTTPError as exc:
        raise OAuthClientError(f"Token endpoint request failed: {exc}") from exc
    if resp.status_code != 200:
        # IDPs return RFC 6749 errors as JSON; surface them in the exception
        # but do not log token-endpoint bodies (may contain tokens on success).
        try:
            err = resp.json()
            detail = err.get("error_description") or err.get("error") or "unknown_error"
        except ValueError:
            detail = f"HTTP {resp.status_code}"
        raise OAuthClientError(f"Token endpoint returned error: {detail}")
    return _parse_token_response(resp.json())


async def exchange_code(*, code: str, code_verifier: str, redirect_uri: str) -> TokenResponse:
    """Exchange an authorization code (with PKCE verifier) for tokens."""
    if not settings.OIDC_CLIENT_ID:
        raise OAuthClientError("OIDC_CLIENT_ID must be configured")
    return await _post_token_endpoint(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.OIDC_CLIENT_ID,
            "code_verifier": code_verifier,
        }
    )


async def refresh_tokens(*, refresh_token: str) -> TokenResponse:
    """Exchange a refresh token for a new access (and possibly refresh) token."""
    if not settings.OIDC_CLIENT_ID:
        raise OAuthClientError("OIDC_CLIENT_ID must be configured")
    return await _post_token_endpoint(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.OIDC_CLIENT_ID,
        }
    )


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
    function is a no-op.
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
