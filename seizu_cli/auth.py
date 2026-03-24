"""Token storage and Device Authorization Grant flow (RFC 8628).

Token storage uses the OS-native secret store (macOS Keychain, Windows
Credential Manager, Linux SecretService/KWallet) via the ``keyring`` library.
If no usable system keyring is detected, commands that require credential
storage raise a ``RuntimeError`` with an OS-specific message explaining how
to fix the problem.  Passing ``--credentials-file PATH`` on any command
forces file-based storage and bypasses the keyring requirement entirely.
"""
import json
import sys
import time
from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import Union

import requests
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

#: Default file path used when no system keyring is available and
#: ``--credentials-file`` has not been supplied.
DEFAULT_CREDENTIALS_FILE = Path.home() / ".config" / "seizu" / "credentials.json"

#: Keyring service name — one entry per API URL lives under this service.
_KEYRING_SERVICE = "seizu"

#: OAuth2 grant type identifier for the Device Authorization Grant.
DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


# ---------------------------------------------------------------------------
# Token-store abstraction
# ---------------------------------------------------------------------------


class TokenStore(ABC):
    """Abstract base for credential backends."""

    @abstractmethod
    def load_token(self, api_url: str) -> Optional[str]:
        """Return the stored access token for *api_url*, or ``None``."""

    @abstractmethod
    def save_token(self, api_url: str, token: str) -> None:
        """Persist *token* for *api_url*."""

    @abstractmethod
    def clear_token(self, api_url: str) -> bool:
        """Remove credentials for *api_url*.  Returns ``True`` if anything was removed."""

    @abstractmethod
    def description(self) -> str:
        """Human-readable description shown in success messages."""


class KeyringStore(TokenStore):
    """Stores tokens in the OS-native secret store via the ``keyring`` library.

    On macOS this is the Keychain; on Windows, the Credential Manager; on
    Linux, the SecretService/D-Bus backend (GNOME Keyring or KWallet).
    """

    def load_token(self, api_url: str) -> Optional[str]:
        import keyring

        return keyring.get_password(_KEYRING_SERVICE, api_url)

    def save_token(self, api_url: str, token: str) -> None:
        import keyring

        keyring.set_password(_KEYRING_SERVICE, api_url, token)

    def clear_token(self, api_url: str) -> bool:
        import keyring
        import keyring.errors

        try:
            keyring.delete_password(_KEYRING_SERVICE, api_url)
            return True
        except keyring.errors.PasswordDeleteError:
            return False

    def description(self) -> str:
        import keyring

        return f"OS keyring ({type(keyring.get_keyring()).__name__})"


class FileStore(TokenStore):
    """Stores tokens in a local JSON file, keyed by API URL."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load_all(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_all(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def load_token(self, api_url: str) -> Optional[str]:
        return self._load_all().get(api_url, {}).get("access_token")

    def save_token(self, api_url: str, token: str) -> None:
        data = self._load_all()
        data[api_url] = {"access_token": token}
        self._save_all(data)

    def clear_token(self, api_url: str) -> bool:
        data = self._load_all()
        if api_url in data:
            del data[api_url]
            self._save_all(data)
            return True
        return False

    def description(self) -> str:
        return f"credentials file ({self.path})"


_NO_KEYRING_HINT = (
    "Pass [bold]--credentials-file PATH[/bold] to store credentials in a "
    "plain JSON file instead."
)

_OS_KEYRING_NAMES = {
    "darwin": "macOS Keychain",
    "win32": "Windows Credential Manager",
}

_OS_UNLOCK_HINTS = {
    "darwin": (
        "The macOS Keychain should be available automatically. "
        "If it is locked, run [bold]security unlock-keychain[/bold] "
        "or unlock it via Keychain Access.app."
    ),
    "win32": (
        "The Windows Credential Manager should be available automatically. "
        "Check that it is accessible and that your account has permission to use it."
    ),
    "linux": (
        "Install and start a keyring daemon — for GNOME desktops run "
        "[bold]gnome-keyring-daemon --start[/bold]; "
        "for KDE run [bold]kwallet-query[/bold] or unlock KWallet via the "
        "system tray. On headless systems, consider using "
        "[bold]--credentials-file PATH[/bold] instead."
    ),
}


def _os_keyring_name() -> str:
    return _OS_KEYRING_NAMES.get(sys.platform, "OS keyring")


def _os_unlock_hint() -> str:
    platform = sys.platform if sys.platform in _OS_UNLOCK_HINTS else "linux"
    return _OS_UNLOCK_HINTS[platform]


def get_store(
    credentials_file: Optional[Path] = None,
) -> Union[KeyringStore, FileStore]:
    """Return the appropriate token store.

    If *credentials_file* is given, returns ``FileStore(credentials_file)``.
    Otherwise requires a usable OS keyring and returns ``KeyringStore``.

    Raises ``RuntimeError`` with a human-readable, OS-specific message if no
    keyring is available and *credentials_file* was not supplied.
    """
    if credentials_file is not None:
        return FileStore(credentials_file)

    try:
        import keyring
        import keyring.backends.fail

        backend = keyring.get_keyring()
        if isinstance(backend, keyring.backends.fail.Keyring):
            raise RuntimeError(
                f"No usable {_os_keyring_name()} found "
                f"(detected backend: {type(backend).__name__}). "
                f"{_os_unlock_hint()}\n{_NO_KEYRING_HINT}"
            )

        return KeyringStore()
    except ImportError:
        raise RuntimeError(
            "The [bold]keyring[/bold] package is not installed. "
            "Install it with [bold]pip install keyring[/bold] to enable "
            f"secure {_os_keyring_name()} storage.\n{_NO_KEYRING_HINT}"
        ) from None
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"Could not initialise {_os_keyring_name()}: {exc}\n"
            f"{_os_unlock_hint()}\n{_NO_KEYRING_HINT}"
        ) from exc


# Convenience wrapper used by main.py to auto-load a stored token.
# Returns None (rather than raising) if no keyring is configured, so that
# commands which don't need authentication still work without a --credentials-file.


def load_token(api_url: str, credentials_file: Optional[Path] = None) -> Optional[str]:
    """Load the stored token for *api_url* using the auto-selected store.

    Returns ``None`` if the store is unavailable (no keyring and no
    *credentials_file*); callers that need a token will surface a 401 error
    naturally.
    """
    try:
        return get_store(credentials_file).load_token(api_url)
    except RuntimeError:
        return None


# ---------------------------------------------------------------------------
# OIDC discovery helpers
# ---------------------------------------------------------------------------


def _oidc_discovery(authority: str) -> Dict[str, Any]:
    resp = requests.get(
        f"{authority}/.well-known/openid-configuration",
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _api_oidc_config(api_url: str) -> Dict[str, Any]:
    """Return the ``oidc`` block from ``GET /api/v1/config``."""
    resp = requests.get(f"{api_url}/api/v1/config", timeout=10)
    resp.raise_for_status()
    body = resp.json()
    if not body.get("auth_required"):
        raise ValueError(
            "Authentication is not required on this server. "
            "Use the API without a token or set DEVELOPMENT_ONLY_REQUIRE_AUTH=true."
        )
    oidc = body.get("oidc")
    if not oidc:
        raise ValueError(
            "This server has auth_required=true but has not published OIDC configuration "
            "(OIDC_AUTHORITY is not set). Contact your administrator."
        )
    return oidc


# ---------------------------------------------------------------------------
# Device Authorization Grant flow
# ---------------------------------------------------------------------------


def device_authorize(api_url: str) -> str:
    """Perform the Device Authorization Grant flow and return the access token.

    1. Fetches OIDC config from ``GET {api_url}/api/v1/config``.
    2. Discovers the device authorization and token endpoints.
    3. Requests a device code and displays the user code + verification URL.
    4. Polls the token endpoint until the user authorises or the code expires.

    Raises ``ValueError`` with a human-readable message on any failure.
    """
    oidc = _api_oidc_config(api_url)
    authority = oidc["authority"]
    client_id = oidc["client_id"]
    scope = oidc.get("scope", "openid email profile")

    discovery = _oidc_discovery(authority)
    device_endpoint: Optional[str] = discovery.get("device_authorization_endpoint")
    token_endpoint: str = discovery["token_endpoint"]

    if not device_endpoint:
        raise ValueError(
            f"The OIDC provider at {authority!r} does not advertise a "
            "device_authorization_endpoint. Make sure the Device Authorization Grant "
            "is enabled on the provider (set device_code_flow in the Authentik blueprint)."
        )

    # ------------------------------------------------------------------
    # Step 1: request a device code
    # ------------------------------------------------------------------
    resp = requests.post(
        device_endpoint,
        data={"client_id": client_id, "scope": scope},
        timeout=10,
    )
    resp.raise_for_status()
    device: Dict[str, Any] = resp.json()

    user_code: str = device["user_code"]
    verification_uri: str = device["verification_uri"]
    verification_uri_complete: Optional[str] = device.get("verification_uri_complete")
    device_code: str = device["device_code"]
    expires_in: int = int(device.get("expires_in", 300))
    interval: int = int(device.get("interval", 5))

    # ------------------------------------------------------------------
    # Step 2: instruct the user
    # ------------------------------------------------------------------
    console.print()
    console.print("[bold]Device authorization required[/bold]")
    console.print()
    if verification_uri_complete:
        console.print(
            "  Open this URL in your browser to authorize —\n\n"
            f"    [bold cyan]{verification_uri_complete}[/bold cyan]\n"
        )
    else:
        console.print(
            f"  1. Open: [cyan]{verification_uri}[/cyan]\n"
            f"  2. Enter code: [bold cyan]{user_code}[/bold cyan]\n"
        )
    console.print("Waiting for authorization", end="")

    # ------------------------------------------------------------------
    # Step 3: poll the token endpoint
    # ------------------------------------------------------------------
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        time.sleep(interval)
        console.print(".", end="", highlight=False)

        token_resp = requests.post(
            token_endpoint,
            data={
                "grant_type": DEVICE_GRANT_TYPE,
                "client_id": client_id,
                "device_code": device_code,
            },
            timeout=10,
        )

        if token_resp.status_code == 200:
            console.print()  # newline after the dots
            return token_resp.json()["access_token"]

        error_body = token_resp.json()
        error = error_body.get("error", "")

        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        if error == "expired_token":
            raise ValueError("Device code expired. Please run 'seizu login' again.")
        if error == "access_denied":
            raise ValueError("Authorization was denied by the user.")

        description = error_body.get("error_description", "")
        raise ValueError(f"Token error ({error}): {description}")

    raise ValueError("Device code expired (timed out). Please run 'seizu login' again.")
