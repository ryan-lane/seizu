"""Global CLI state shared between the callback and command handlers."""
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seizu_cli.client import SeizuClient

api_url: str = "http://localhost:8080"
token: Optional[str] = None
credentials_file: Optional[Path] = None
_client: Optional["SeizuClient"] = None


def get_client() -> "SeizuClient":
    """Return the shared API client, creating it lazily on first call."""
    from seizu_cli.client import SeizuClient

    global _client
    if _client is None:
        _client = SeizuClient(api_url, token)
    return _client


def reset_client() -> None:
    """Drop the cached client so the next call to get_client() creates a fresh one."""
    global _client
    _client = None
