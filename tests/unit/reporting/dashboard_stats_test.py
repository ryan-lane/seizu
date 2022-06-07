import neo4j.exceptions

from reporting import dashboard_stats
from reporting.schema.reporting_config import Input
from reporting.schema.reporting_config import Panel
from reporting.schema.reporting_config import PanelParam
from reporting.schema.reporting_config import ReportingConfig


def test_send_stats_for_panel_no_metric(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    run_query_mock = mocker.patch("reporting.dashboard_stats.run_query_with_retry")
    panel = Panel(
        cypher="test", params=[{"name": "severity", "value": "HIGH"}], _type="count"
    )
    config = mocker.MagicMock()
    dashboard_stats.send_stats_for_panel(panel, [], config)
    assert run_query_mock.call_count == 0
    assert stats_mock.call_count == 0


def test_send_stats_for_panel_with_input_exception(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    run_query_mock = mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
            PanelParam(name="service_name", input_id="service-name-autocomplete-input"),
        ],
        _type="count",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    panel_inputs = [
        Input(
            input_id="service-name-autocomplete-input",
            cypher="test",
            label="Service Name",
            _type="autocomplete",
            size=3,
        ),
    ]
    dashboard_stats.send_stats_for_panel(panel, panel_inputs, config)
    # once, but with an exception
    assert run_query_mock.call_count == 1
    assert stats_mock.call_count == 0


def test_send_stats_for_panel_with_metric_exception(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    run_query_mock = mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=[
            [{"value": "test-service"}, {"value": "test-service2"}],
            neo4j.exceptions.ServiceUnavailable(),
            [{"total": 1}],
        ],
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
            PanelParam(name="service_name", input_id="service-name-autocomplete-input"),
        ],
        _type="count",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    panel_inputs = [
        Input(
            input_id="service-name-autocomplete-input",
            cypher="test",
            label="Service Name",
            _type="autocomplete",
            size=3,
        ),
    ]
    dashboard_stats.send_stats_for_panel(panel, panel_inputs, config)
    # inputs call, exception to first input metric, return on 2nd input metric
    assert run_query_mock.call_count == 3
    # only one successful return for input metric query
    assert stats_mock.call_count == 1


def test_send_stats_for_panel_with_input(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    run_query_mock = mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=[
            [{"value": "test-service"}, {"value": "test-service2"}],
            [{"total": 1}],
            [{"total": 1}],
        ],
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
            PanelParam(name="service_name", input_id="service-name-autocomplete-input"),
        ],
        _type="count",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    panel_inputs = [
        Input(
            input_id="service-name-autocomplete-input",
            cypher="test",
            label="Service Name",
            _type="autocomplete",
            size=3,
        ),
    ]
    dashboard_stats.send_stats_for_panel(panel, panel_inputs, config)
    # once for inputs, twice for metrics
    assert run_query_mock.call_count == 3
    # two metrics to report. same panel with two input returns
    assert stats_mock.call_count == 2


def test_send_stats_for_panel_with_input_progress(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    run_query_mock = mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=[
            [{"value": "test-service"}, {"value": "test-service2"}],
            [{"numerator": 1, "denominator": 1}],
            [{"numerator": 1, "denominator": 1}],
        ],
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
            PanelParam(name="service_name", input_id="service-name-autocomplete-input"),
        ],
        _type="progress",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    panel_inputs = [
        Input(
            input_id="service-name-autocomplete-input",
            cypher="test",
            label="Service Name",
            _type="autocomplete",
            size=3,
        ),
    ]
    dashboard_stats.send_stats_for_panel(panel, panel_inputs, config)
    # once for inputs, twice for metrics
    assert run_query_mock.call_count == 3
    # 4 metrics to report. same panel with two input returns, but numerator and denominator metrics for each
    assert stats_mock.call_count == 4


def test_send_stats_for_panel_no_input(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry", return_value=[{"total": 1}]
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
        ],
        _type="count",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    dashboard_stats.send_stats_for_panel(panel, [], config)
    assert stats_mock.call_count == 1


def test_send_stats_for_panel_no_input_progress(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        return_value=[{"numerator": 1, "denominator": 1}],
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
        ],
        _type="progress",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    dashboard_stats.send_stats_for_panel(panel, [], config)
    assert stats_mock.call_count == 2


def test_send_stats_for_panel_no_stats(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    panel = Panel(
        cypher="test",
        params=[
            PanelParam(name="severity", value="HIGH"),
        ],
        _type="count",
        metric="crowdstrike.vulnerabilities",
    )
    config = ReportingConfig(
        queries={
            "test": "MATCH (g:GitHubRepository) RETURN g.id",
        },
    )
    dashboard_stats.send_stats_for_panel(panel, [], config)
    assert not stats_mock.called


def test_dashboard_stats(mocker):
    mocker.patch(
        "reporting.settings.REPORTING_CONFIG_FILE",
        "tests/data/reporting-dashboard.conf",
    )
    send_stats_mock = mocker.patch("reporting.dashboard_stats.send_stats_for_panel")
    runner = dashboard_stats.app.test_cli_runner()
    runner.invoke(dashboard_stats.dashboard_stats)
    assert send_stats_mock.call_count == 6
