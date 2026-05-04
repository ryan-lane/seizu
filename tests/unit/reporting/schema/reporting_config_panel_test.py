"""Round-trip tests for the new layout fields on ``Panel``."""

from seizu_schema.reporting_config import Panel


def test_legacy_panel_without_layout_fields_validates() -> None:
    """A panel authored before per-panel height support must still validate."""
    panel = Panel.model_validate({"type": "count", "size": 3, "cypher": "RETURN 1"})

    assert panel.size == 3
    assert panel.w is None
    assert panel.h is None
    assert panel.x is None
    assert panel.y is None
    assert panel.min_h is None
    assert panel.auto_height is None


def test_panel_with_full_layout_round_trips() -> None:
    """All new fields persist through ``model_dump`` round-trip."""
    payload = {
        "type": "markdown",
        "markdown": "# Hello",
        "w": 6,
        "h": 8,
        "x": 0,
        "y": 0,
        "min_h": 4,
        "auto_height": True,
    }

    panel = Panel.model_validate(payload)
    dumped = panel.model_dump(exclude_none=True)

    assert dumped["w"] == 6
    assert dumped["h"] == 8
    assert dumped["x"] == 0
    assert dumped["y"] == 0
    assert dumped["min_h"] == 4
    assert dumped["auto_height"] is True


def test_layout_fields_default_to_none() -> None:
    """Omitted layout fields are excluded from a ``exclude_none`` dump."""
    panel = Panel.model_validate({"type": "table", "cypher": "RETURN 1"})
    dumped = panel.model_dump(exclude_none=True)

    for field in ("w", "h", "x", "y", "min_h", "auto_height"):
        assert field not in dumped
