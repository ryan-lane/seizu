"""CLI configuration loaded from ~/.config/seizu/seizu.conf."""

from pathlib import Path

import yaml
from pydantic import BaseModel

_DEFAULT_CONFIG_DIR = Path.home() / ".config" / "seizu"
_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "seizu.conf"
_DEFAULT_SEED_FILE = _DEFAULT_CONFIG_DIR / "reporting-dashboard.yaml"


class SeizuConfig(BaseModel):
    """Parsed contents of ~/.config/seizu/seizu.conf."""

    api_url: str | None = None
    seed_file: str | None = None


def load_config(config_file: Path | None = None) -> SeizuConfig:
    """Load the CLI config file.

    Reads *config_file* if provided, otherwise falls back to
    ``~/.config/seizu/seizu.conf``.  Returns an empty :class:`SeizuConfig`
    when the file does not exist rather than raising an error.
    """
    path = config_file or _DEFAULT_CONFIG_FILE
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return SeizuConfig.model_validate(data)
    except FileNotFoundError:
        return SeizuConfig()


def default_seed_file() -> str:
    """Return the default seed-file path as a string."""
    return str(_DEFAULT_SEED_FILE)
