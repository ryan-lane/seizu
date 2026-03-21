import neo4j.exceptions

from reporting import dashboard_stats
from reporting.schema.report_config import PanelStat


def test_dashboard_stats(mocker):
    panel_stats = [
        PanelStat(
            report_id="r1",
            metric="crowdstrike.vulnerabilities",
            panel_type="count",
            cypher="MATCH (n) RETURN count(n) AS total",
            static_params={"severity": "CRITICAL"},
        ),
        PanelStat(
            report_id="r1",
            metric="github.repo.private",
            panel_type="progress",
            cypher="MATCH (g) RETURN count(g) AS numerator, 10 AS denominator",
            static_params={},
        ),
    ]
    mocker.patch(
        "reporting.dashboard_stats.report_store.list_panel_stats",
        return_value=panel_stats,
    )
    send_stats_mock = mocker.patch(
        "reporting.dashboard_stats.send_stats_for_panel_stat"
    )
    runner = dashboard_stats.app.test_cli_runner()
    runner.invoke(dashboard_stats.dashboard_stats)
    assert send_stats_mock.call_count == 2
    send_stats_mock.assert_any_call(panel_stats[0])
    send_stats_mock.assert_any_call(panel_stats[1])


def test_send_stats_for_panel_stat_count_no_input(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        return_value=[{"total": 5}],
    )
    stat = PanelStat(
        report_id="r1",
        metric="crowdstrike.vulnerabilities",
        panel_type="count",
        cypher="MATCH (n) RETURN count(n) AS total",
        static_params={"severity": "HIGH"},
    )
    dashboard_stats.send_stats_for_panel_stat(stat)
    assert stats_mock.call_count == 1
    stats_mock.assert_called_once_with(
        "crowdstrike.vulnerabilities.total",
        5,
        tags=["severity:HIGH"],
    )


def test_send_stats_for_panel_stat_progress_no_input(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        return_value=[{"numerator": 3, "denominator": 10}],
    )
    stat = PanelStat(
        report_id="r1",
        metric="github.repo.private",
        panel_type="progress",
        cypher="MATCH (g) RETURN count(g) AS numerator, 10 AS denominator",
        static_params={},
    )
    dashboard_stats.send_stats_for_panel_stat(stat)
    assert stats_mock.call_count == 2


def test_send_stats_for_panel_stat_with_input(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=[
            [{"value": "svc-a"}, {"value": "svc-b"}],
            [{"total": 1}],
            [{"total": 2}],
        ],
    )
    stat = PanelStat(
        report_id="r1",
        metric="vuln.count",
        panel_type="count",
        cypher="MATCH (n) WHERE n.service = $service_name RETURN count(n) AS total",
        static_params={"severity": "HIGH"},
        input_param_name="service_name",
        input_cypher="MATCH (t:Tag) RETURN t.value AS value",
    )
    dashboard_stats.send_stats_for_panel_stat(stat)
    # once for inputs, twice for per-input metrics
    assert stats_mock.call_count == 2


def test_send_stats_for_panel_stat_with_input_service_unavailable(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd.gauge")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    stat = PanelStat(
        report_id="r1",
        metric="vuln.count",
        panel_type="count",
        cypher="MATCH (n) RETURN count(n) AS total",
        static_params={},
        input_param_name="service_name",
        input_cypher="MATCH (t:Tag) RETURN t.value AS value",
    )
    dashboard_stats.send_stats_for_panel_stat(stat)
    assert stats_mock.call_count == 0


def test_send_stats_for_panel_stat_no_input_service_unavailable(mocker):
    stats_mock = mocker.patch("reporting.dashboard_stats.statsd")
    mocker.patch(
        "reporting.dashboard_stats.run_query_with_retry",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    stat = PanelStat(
        report_id="r1",
        metric="vuln.count",
        panel_type="count",
        cypher="MATCH (n) RETURN count(n) AS total",
        static_params={},
    )
    dashboard_stats.send_stats_for_panel_stat(stat)
    assert not stats_mock.called
