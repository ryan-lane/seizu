"""Tests for seizu_cli.config."""
from pathlib import Path

import pytest

from seizu_cli.config import load_config
from seizu_cli.config import SeizuConfig


def test_load_config_returns_empty_when_file_missing(tmp_path: Path) -> None:
    cfg = load_config(tmp_path / "nonexistent.conf")
    assert cfg.api_url is None
    assert cfg.seed_file is None


def test_load_config_reads_api_url(tmp_path: Path) -> None:
    conf = tmp_path / "seizu.conf"
    conf.write_text("api_url: https://seizu.example.com\n")
    cfg = load_config(conf)
    assert cfg.api_url == "https://seizu.example.com"


def test_load_config_reads_seed_file(tmp_path: Path) -> None:
    conf = tmp_path / "seizu.conf"
    conf.write_text("seed_file: /data/dashboard.yaml\n")
    cfg = load_config(conf)
    assert cfg.seed_file == "/data/dashboard.yaml"


def test_load_config_reads_all_fields(tmp_path: Path) -> None:
    conf = tmp_path / "seizu.conf"
    conf.write_text(
        "api_url: https://seizu.example.com\n" "seed_file: /data/dashboard.yaml\n"
    )
    cfg = load_config(conf)
    assert cfg.api_url == "https://seizu.example.com"
    assert cfg.seed_file == "/data/dashboard.yaml"


def test_load_config_empty_file_returns_empty_config(tmp_path: Path) -> None:
    conf = tmp_path / "seizu.conf"
    conf.write_text("")
    cfg = load_config(conf)
    assert cfg.api_url is None
    assert cfg.seed_file is None


def test_load_config_uses_default_path_when_none_given(
    mocker: pytest.MonkeyPatch,
) -> None:
    mocker.patch(
        "seizu_cli.config._DEFAULT_CONFIG_FILE", Path("/nonexistent/seizu.conf")
    )
    cfg = load_config()
    assert isinstance(cfg, SeizuConfig)
    assert cfg.api_url is None


def test_seizu_config_defaults() -> None:
    cfg = SeizuConfig()
    assert cfg.api_url is None
    assert cfg.seed_file is None


def test_seizu_config_validation() -> None:
    cfg = SeizuConfig.model_validate({"api_url": "http://localhost:8080"})
    assert cfg.api_url == "http://localhost:8080"
    assert cfg.seed_file is None
