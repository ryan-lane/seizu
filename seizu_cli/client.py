"""HTTP client wrapper for the Seizu REST API.

Handles Bearer token auth and CSRF token bootstrapping so commands do not
need to think about either concern.
"""
from typing import Any
from typing import Dict
from typing import Optional

import requests


class APIError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class SeizuClient:
    """Thin requests wrapper that handles auth and CSRF tokens."""

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        if token:
            self._session.headers.update({"Authorization": f"Bearer {token}"})
        self._csrf_token = self._bootstrap_csrf()

    def _bootstrap_csrf(self) -> str:
        """GET /api/v1/config to receive the CSRF token cookie."""
        try:
            resp = self._session.get(f"{self.base_url}/api/v1/config", timeout=10)
            resp.raise_for_status()
        except requests.RequestException:
            # Errors will surface on the first real request; bootstrap is best-effort.
            pass
        return self._session.cookies.get("_csrf_token") or ""

    def _csrf_header(self) -> Dict[str, str]:
        if self._csrf_token:
            return {"X-CSRFToken": self._csrf_token}
        return {}

    def _raise_for_status(self, resp: requests.Response) -> None:
        if not resp.ok:
            if resp.status_code == 401:
                raise APIError(
                    401,
                    "Unauthorized. Run 'seizu login' to authenticate, "
                    "or pass --token / set SEIZU_TOKEN.",
                )
            try:
                body = resp.json()
                message = body.get("error") or body.get("message") or resp.text
            except Exception:
                message = resp.text
            raise APIError(resp.status_code, str(message))

    def get(self, path: str, **kwargs: Any) -> Any:
        resp = self._session.get(f"{self.base_url}{path}", timeout=30, **kwargs)
        self._raise_for_status(resp)
        return resp.json()

    def post(self, path: str, **kwargs: Any) -> Any:
        extra_headers: Dict[str, str] = kwargs.pop("headers", {})
        headers = {**self._csrf_header(), **extra_headers}
        resp = self._session.post(
            f"{self.base_url}{path}", headers=headers, timeout=30, **kwargs
        )
        self._raise_for_status(resp)
        return resp.json()

    def put(self, path: str, **kwargs: Any) -> Any:
        extra_headers: Dict[str, str] = kwargs.pop("headers", {})
        headers = {**self._csrf_header(), **extra_headers}
        resp = self._session.put(
            f"{self.base_url}{path}", headers=headers, timeout=30, **kwargs
        )
        self._raise_for_status(resp)
        return resp.json()

    def delete(self, path: str, **kwargs: Any) -> Any:
        extra_headers: Dict[str, str] = kwargs.pop("headers", {})
        headers = {**self._csrf_header(), **extra_headers}
        resp = self._session.delete(
            f"{self.base_url}{path}", headers=headers, timeout=30, **kwargs
        )
        self._raise_for_status(resp)
        if resp.content:
            return resp.json()
        return None
