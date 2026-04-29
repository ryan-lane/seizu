"""Tests for the statsd scheduled query action module."""

from unittest.mock import MagicMock, patch

import pytest

from reporting.scheduled_query_modules import statsd as statsd_module
from reporting.schema.reporting_config import ScheduledQueryAction


def _action(config: dict) -> ScheduledQueryAction:
    return ScheduledQueryAction(action_type="statsd", action_config=config)


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the module-level client singleton between tests."""
    original = statsd_module._CLIENT
    statsd_module._CLIENT = None
    yield
    statsd_module._CLIENT = original


def test_action_name():
    assert statsd_module.action_name() == "statsd"


def test_action_config_schema_fields():
    fields = {f.name: f for f in statsd_module.action_config_schema()}
    assert "metric" in fields
    assert "value_field" in fields
    assert "metric_type" in fields
    assert "tag_fields" in fields
    assert "query_return_attribute" in fields
    assert fields["metric"].required is True
    assert fields["value_field"].required is True
    assert fields["metric_type"].default == "gauge"
    assert fields["query_return_attribute"].default == "details"


async def test_setup_is_noop():
    await statsd_module.setup()  # should not raise


def test_handle_results_skips_empty():
    """No client call when results is empty."""
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        statsd_module.handle_results("sq1", _action({"metric": "m", "value_field": "total"}), [])
        mock_client.gauge.assert_not_called()


def test_handle_results_warns_when_no_host(caplog):
    with patch.object(statsd_module, "_STATSD_HOST", ""):
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "m", "value_field": "total"}),
            [{"details": {"total": 5}}],
        )
    assert "STATSD_HOST" in caplog.text


def test_handle_results_errors_on_missing_config(caplog):
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        statsd_module.handle_results("sq1", _action({}), [{"details": {"total": 5}}])
    assert "missing required fields" in caplog.text
    mock_client.gauge.assert_not_called()


def test_handle_results_gauge():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"details": {"total": 42}}]
        statsd_module.handle_results("sq1", _action({"metric": "cves.total", "value_field": "total"}), results)
        mock_client.gauge.assert_called_once_with("cves.total", 42.0, tags=[])


def test_handle_results_gauge_with_tags():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"details": {"total": 10, "severity": "CRITICAL"}}]
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "cves", "value_field": "total", "tag_fields": ["severity"]}),
            results,
        )
        mock_client.gauge.assert_called_once_with("cves", 10.0, tags=["severity:CRITICAL"])


def test_handle_results_multiple_rows():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [
            {"details": {"count": 5, "env": "prod"}},
            {"details": {"count": 3, "env": "staging"}},
        ]
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "apps.count", "value_field": "count", "tag_fields": ["env"]}),
            results,
        )
        assert mock_client.gauge.call_count == 2
        calls = [c.args for c in mock_client.gauge.call_args_list]
        assert ("apps.count", 5.0) in calls
        assert ("apps.count", 3.0) in calls


def test_handle_results_increment():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"details": {"count": 7}}]
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "errors", "value_field": "count", "metric_type": "increment"}),
            results,
        )
        mock_client.increment.assert_called_once_with("errors", 7.0, tags=[])


def test_handle_results_decrement():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"details": {"count": 2}}]
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "queue", "value_field": "count", "metric_type": "decrement"}),
            results,
        )
        mock_client.decrement.assert_called_once_with("queue", 2.0, tags=[])


def test_handle_results_skips_none_value():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"details": {"other_field": 5}}]  # value_field missing
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "m", "value_field": "total"}),
            results,
        )
        mock_client.gauge.assert_not_called()


def test_handle_results_custom_return_attribute():
    with patch.object(statsd_module, "_STATSD_HOST", "localhost"):
        mock_client = MagicMock()
        statsd_module._CLIENT = mock_client
        results = [{"row": {"total": 99}}]
        statsd_module.handle_results(
            "sq1",
            _action({"metric": "m", "value_field": "total", "query_return_attribute": "row"}),
            results,
        )
        mock_client.gauge.assert_called_once_with("m", 99.0, tags=[])
