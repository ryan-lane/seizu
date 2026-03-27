import http.cookies
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from typing import AsyncIterator
from urllib.parse import urlparse

import secure
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette_csrf import CSRFMiddleware

from reporting import settings
from reporting.routes import config as config_routes
from reporting.routes import me as me_routes
from reporting.routes import query as query_routes
from reporting.routes import reports as reports_routes
from reporting.routes import scheduled_queries as sq_routes
from reporting.routes import static as static_routes
from reporting.routes import toolsets as toolsets_routes
from reporting.routes import users as users_routes
from reporting.routes import validate as validate_routes
from reporting.services import report_store


def _build_csp_policy() -> str:
    connect_src = ["'self'"]
    if settings.OIDC_AUTHORITY:
        parsed = urlparse(settings.OIDC_AUTHORITY)
        oidc_origin = f"{parsed.scheme}://{parsed.netloc}"  # noqa: E231
        if oidc_origin not in connect_src:
            connect_src.append(oidc_origin)
    directives = [
        "default-src 'self'",
        f"connect-src {' '.join(connect_src)}",
        # issues in material-ui
        "style-src 'self' 'unsafe-inline'",
        "script-src-elem 'self'",
    ]
    if settings.OIDC_AUTHORITY:
        parsed = urlparse(settings.OIDC_AUTHORITY)
        oidc_origin = f"{parsed.scheme}://{parsed.netloc}"  # noqa: E231
        directives.append(f"frame-src {oidc_origin}")
    return "; ".join(directives)


class _CSRFMiddleware(CSRFMiddleware):
    """CSRFMiddleware that returns JSON errors and self-heals stale cookies.

    starlette-csrf's default error response is plain text, which breaks JSON
    clients.  Additionally, if the browser holds a stale cookie from a prior
    implementation (e.g. Flask-SeaSurf), the signature check fails with
    BadSignature.  This subclass detects that case and expires the stale
    cookie so the next safe-method response will issue a fresh valid token.
    """

    def _get_error_response(self, request: Request) -> Response:
        headers: dict = {}
        csrf_cookie = request.cookies.get(self.cookie_name)
        if csrf_cookie is not None:
            # If the cookie exists but can't be deserialized it is stale/from a
            # different implementation.  Clear it so the next GET sets a fresh one.
            try:
                self.serializer.loads(csrf_cookie)
            except BadSignature:
                morsel: http.cookies.SimpleCookie = http.cookies.SimpleCookie()
                morsel[self.cookie_name] = ""
                morsel[self.cookie_name]["max-age"] = 0
                morsel[self.cookie_name]["path"] = self.cookie_path
                headers["set-cookie"] = morsel.output(header="").strip()
        return JSONResponse(
            {"error": "CSRF validation failed"},
            status_code=403,
            headers=headers,
        )


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply security headers to every response."""

    def __init__(self, app: Any, secure_headers: secure.Secure) -> None:
        super().__init__(app)
        self._secure_headers = secure_headers

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        self._secure_headers.set_headers(response)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    should_init = settings.DYNAMODB_CREATE_TABLE or (
        settings.REPORT_STORE_BACKEND == "sqlmodel"
    )
    if should_init:
        await report_store.initialize()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Seizu",
        version="1.0.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # Security headers middleware
    hsts = None
    if settings.TALISMAN_FORCE_HTTPS:
        hsts = secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
    csp_policy = _build_csp_policy()
    secure_headers = secure.Secure(
        server=secure.Server().set(""),
        hsts=hsts,
        csp=secure.ContentSecurityPolicy().set(csp_policy),
    )
    app.add_middleware(_SecurityHeadersMiddleware, secure_headers=secure_headers)

    # CSRF middleware — skip on healthcheck and config (GET, no state-change risk)
    # Also exempt /api/v1/mcp since MCP clients are not browsers and use Bearer auth.
    if not settings.CSRF_DISABLE:
        app.add_middleware(
            _CSRFMiddleware,
            secret=settings.SECRET_KEY or "",
            cookie_name=settings.CSRF_COOKIE_NAME,
            header_name=settings.CSRF_HEADER_NAME,
            cookie_secure=settings.CSRF_COOKIE_SECURE,
            cookie_httponly=settings.CSRF_COOKIE_HTTPONLY,
            cookie_samesite=settings.CSRF_COOKIE_SAMESITE,
            cookie_domain=settings.CSRF_COOKIE_DOMAIN,
            cookie_path=settings.CSRF_COOKIE_PATH,
            exempt_urls=[re.compile(r"^/api/v1/mcp")],
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc.detail) if exc.detail else str(exc.status_code),
            },
        )

    # API routers
    for router_module in [
        config_routes,
        me_routes,
        query_routes,
        reports_routes,
        sq_routes,
        toolsets_routes,
        users_routes,
        validate_routes,
        static_routes,
    ]:
        app.include_router(router_module.router)

    # MCP server — mounted before the SPA catch-all so /api/v1/mcp/* routes are handled
    if settings.MCP_ENABLED:
        from reporting.services.mcp_server import get_mcp_app

        app.mount("/api/v1/mcp", get_mcp_app())

    # Static files from the React build
    static_folder = settings.STATIC_FOLDER
    static_dir = os.path.join(static_folder, "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Root-level static files (manifest.json, favicon, etc.) and SPA catch-all
    _register_static_routes(app, static_folder)

    return app


_ROOT_STATIC_FILES = {
    "manifest.json",
    "asset-manifest.json",
    "favicon.png",
    "favicon.svg",
}


def _register_static_routes(app: FastAPI, static_folder: str) -> None:
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> Response:
        # Strip leading slashes from path
        path = full_path.lstrip("/")

        # Serve known root-level static files directly
        if path in _ROOT_STATIC_FILES:
            # Use basename to prevent path traversal even though path is already
            # validated against the fixed set of known filenames.
            file_path = os.path.join(static_folder, os.path.basename(path))
            if os.path.isfile(file_path):
                return FileResponse(file_path)

        # Fall back to serving index.html for all other paths (SPA)
        index_path = os.path.join(static_folder, "index.html")
        if os.path.isfile(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                },
            )
        # If no index.html exists (dev mode without a frontend build), return 404
        return JSONResponse(content={"error": "Not found"}, status_code=404)
