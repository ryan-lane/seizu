import logging
from typing import List

import neo4j.exceptions
from datadog.dogstatsd import statsd
from flask import Flask
from flask.cli import AppGroup

from reporting import settings
from reporting import setup_logging  # noqa:F401
from reporting.schema import reporting_config
from reporting.schema.reporting_config import Input
from reporting.schema.reporting_config import Panel
from reporting.schema.reporting_config import ReportingConfig
from reporting.services import reporting_statsd  # noqa:F401
from reporting.services.reporting_neo4j import run_query_with_retry

logger = logging.getLogger(__name__)

app = Flask(__name__)
user_cli = AppGroup("worker")
app.cli.add_command(user_cli)


def send_stats_for_panel(
    panel: Panel, panel_inputs: List[Input], config: ReportingConfig
) -> None:
    if panel._type not in ["progress", "count"]:
        return
    metric = panel.metric
    if not metric:
        return
    cypher_id = panel.cypher
    if not cypher_id:
        return
    cypher = config.queries[cypher_id]
    tags = []
    params = {}
    inputs = []
    for p in panel.params:
        if p.value:
            params.update({p.name: p.value})
            tags.append(f"{p.name}:{p.value}")
        elif p.input_id:
            inputs.append(p)
    if len(inputs) == 1:
        # For metrics, we only consider panels with at most one input, otherwise the cardinality will be too high.
        input_ref = inputs[0]
        _input = None
        for pi in panel_inputs:
            if pi.input_id == input_ref.input_id:
                _input = pi
        if _input is None:
            return
        if _input.cypher is None:
            return
        try:
            input_results = run_query_with_retry(_input.cypher, {})
        except neo4j.exceptions.ServiceUnavailable:
            logger.exception(
                "Failed to record metric",
                extra={"metric": metric},
            )
            return
        if len(input_results) > settings.DASHBOARD_STATS_MAX_INPUT_RESULTS:
            logger.warning(
                "Skipped metric with too many input values.",
                extra={"metric": metric},
            )
            return
        for input_result in input_results:
            value = input_result["value"]
            _params = {input_ref.name: value}
            _params.update(params)
            _tags = [f"{input_ref.name}:{value}"]
            _tags.extend(tags)
            try:
                metric_results = run_query_with_retry(cypher, parameters=_params)
            except neo4j.exceptions.ServiceUnavailable:
                logger.exception(
                    "Failed to record metric",
                    extra={"metric": metric},
                )
                continue
            for metric_result in metric_results:
                if panel._type == "progress":
                    numerator = metric_result["numerator"]
                    denominator = metric_result["denominator"]
                    statsd.gauge(f"{metric}.numerator", numerator, tags=_tags)
                    statsd.gauge(f"{metric}.denominator", denominator, tags=_tags)
                elif panel._type == "count":
                    total = metric_result["total"]
                    statsd.gauge(f"{metric}.total", total, tags=_tags)
    else:
        # if there's no inputs, we need to run a single query
        try:
            metric_results = run_query_with_retry(cypher, parameters=params)
        except neo4j.exceptions.ServiceUnavailable:
            logger.exception(
                "Failed to record metric", extra={"metric": metric, "tags": tags}
            )
            return
        except neo4j.exceptions.CypherSyntaxError:
            logger.exception(
                "Failed to record metric", extra={"metric": metric, "tags": tags}
            )
            return
        for metric_result in metric_results:
            if panel._type == "progress":
                numerator = metric_result["numerator"]
                denominator = metric_result["denominator"]
                statsd.gauge(f"{metric}.numerator", numerator, tags=tags)
                statsd.gauge(f"{metric}.denominator", denominator, tags=tags)
            elif panel._type == "count":
                total = metric_result["total"]
                statsd.gauge(f"{metric}.total", total, tags=tags)


@user_cli.command("dashboard-stats")
def dashboard_stats() -> None:
    logger.debug("Sending in stats...")
    config = reporting_config.load_file(settings.REPORTING_CONFIG_FILE)
    dashboard_rows = config.dashboard.rows
    for row in dashboard_rows:
        for panel in row.panels:
            send_stats_for_panel(panel, [], config)
    reports = config.reports
    for _, report in reports.items():
        for row in report.rows:
            for panel in row.panels:
                send_stats_for_panel(panel, report.inputs, config)
