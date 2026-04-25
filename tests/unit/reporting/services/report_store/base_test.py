"""Tests for extract_panel_stats helper in report_store.base."""

from reporting.schema.report_config import PanelStat
from reporting.services.report_store.base import extract_panel_stats

_QUERIES = {
    "cves-total": "MATCH (c:CVE) RETURN count(c.id) AS total",
    "cves-progress": "MATCH (c:CVE) WITH count(c) AS d RETURN count(c) AS numerator, d AS denominator",
    "input-query": "MATCH (t:Tag) RETURN t.value AS value",
}


def _config(rows, queries=None, inputs=None):
    return {
        "name": "Test",
        "queries": queries or _QUERIES,
        "inputs": inputs or [],
        "rows": rows,
    }


def test_extract_panel_stats_empty_config():
    assert extract_panel_stats("rid1", {"name": "x", "rows": []}) == []


def test_extract_panel_stats_invalid_config_returns_empty():
    # Non-parseable config should not raise, just return empty list
    assert extract_panel_stats("rid1", {"not": "a report"}) == []


def test_extract_panel_stats_count_panel_static_params():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [{"name": "severity", "value": "CRITICAL"}],
                        "metric": "cve.count",
                        "size": 3,
                    }
                ],
            }
        ]
    )
    stats = extract_panel_stats("rid1", config)
    assert len(stats) == 1
    s = stats[0]
    assert isinstance(s, PanelStat)
    assert s.report_id == "rid1"
    assert s.metric == "cve.count"
    assert s.panel_type == "count"
    assert s.cypher == _QUERIES["cves-total"]
    assert s.static_params == {"severity": "CRITICAL"}
    assert s.input_param_name is None
    assert s.input_cypher is None


def test_extract_panel_stats_resolves_cypher_key():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [],
                        "metric": "cve.count",
                        "size": 3,
                    }
                ],
            }
        ]
    )
    stats = extract_panel_stats("rid1", config)
    assert stats[0].cypher == _QUERIES["cves-total"]


def test_extract_panel_stats_direct_cypher_string():
    direct = "MATCH (n) RETURN count(n) AS total"
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": direct,
                        "params": [],
                        "metric": "cve.count",
                        "size": 3,
                    }
                ],
            }
        ]
    )
    stats = extract_panel_stats("rid1", config)
    assert stats[0].cypher == direct


def test_extract_panel_stats_skips_non_stat_panel_types():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {"type": "table", "cypher": "cves-total", "params": [], "size": 12},
                    {"type": "bar", "cypher": "cves-total", "params": [], "size": 6},
                ],
            }
        ]
    )
    assert extract_panel_stats("rid1", config) == []


def test_extract_panel_stats_skips_panel_without_metric():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [],
                        "size": 3,
                        # no metric field
                    }
                ],
            }
        ]
    )
    assert extract_panel_stats("rid1", config) == []


def test_extract_panel_stats_skips_panel_without_cypher():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "params": [],
                        "metric": "cve.count",
                        "size": 3,
                        # no cypher field
                    }
                ],
            }
        ]
    )
    assert extract_panel_stats("rid1", config) == []


def test_extract_panel_stats_skips_panel_with_multiple_inputs():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [
                            {"name": "a", "input_id": "input-a"},
                            {"name": "b", "input_id": "input-b"},
                        ],
                        "metric": "cve.count",
                        "size": 3,
                    }
                ],
            }
        ],
        inputs=[
            {
                "input_id": "input-a",
                "cypher": "MATCH (n) RETURN n.v AS value",
                "label": "A",
                "type": "autocomplete",
            },
            {
                "input_id": "input-b",
                "cypher": "MATCH (n) RETURN n.v AS value",
                "label": "B",
                "type": "autocomplete",
            },
        ],
    )
    assert extract_panel_stats("rid1", config) == []


def test_extract_panel_stats_with_single_input():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [{"name": "service_name", "input_id": "svc-input"}],
                        "metric": "vuln.count",
                        "size": 3,
                    }
                ],
            }
        ],
        inputs=[
            {
                "input_id": "svc-input",
                "cypher": _QUERIES["input-query"],
                "label": "Service",
                "type": "autocomplete",
            }
        ],
    )
    stats = extract_panel_stats("rid1", config)
    assert len(stats) == 1
    s = stats[0]
    assert s.input_param_name == "service_name"
    assert s.input_cypher == _QUERIES["input-query"]


def test_extract_panel_stats_skips_input_ref_with_no_cypher():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [{"name": "svc", "input_id": "svc-input"}],
                        "metric": "vuln.count",
                        "size": 3,
                    }
                ],
            }
        ],
        inputs=[
            {
                "input_id": "svc-input",
                "label": "Service",
                "type": "text",
                # no cypher — text inputs don't have a query
            }
        ],
    )
    # Panel referencing an input with no cypher should be skipped
    assert extract_panel_stats("rid1", config) == []


def test_extract_panel_stats_progress_panel():
    config = _config(
        rows=[
            {
                "name": "row",
                "panels": [
                    {
                        "type": "progress",
                        "cypher": "cves-progress",
                        "params": [],
                        "metric": "cve.progress",
                        "size": 3,
                    }
                ],
            }
        ]
    )
    stats = extract_panel_stats("rid1", config)
    assert len(stats) == 1
    assert stats[0].panel_type == "progress"


def test_extract_panel_stats_multiple_panels():
    config = _config(
        rows=[
            {
                "name": "row1",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [{"name": "severity", "value": "CRITICAL"}],
                        "metric": "cve.count",
                        "size": 3,
                    },
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "params": [{"name": "severity", "value": "HIGH"}],
                        "metric": "cve.count",
                        "size": 3,
                    },
                    # table panel — should be skipped
                    {"type": "table", "cypher": "cves-total", "params": [], "size": 12},
                ],
            }
        ]
    )
    stats = extract_panel_stats("rid1", config)
    assert len(stats) == 2
    severities = {s.static_params.get("severity") for s in stats}
    assert severities == {"CRITICAL", "HIGH"}
