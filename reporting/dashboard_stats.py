import asyncio
import logging

import neo4j.exceptions
from datadog.dogstatsd import statsd

from reporting import settings
from reporting import setup_logging  # noqa:F401
from reporting.schema.report_config import PanelStat
from reporting.services import report_store
from reporting.services import reporting_statsd  # noqa:F401
from reporting.services.reporting_neo4j import run_query_with_retry

logger = logging.getLogger(__name__)


async def send_stats_for_panel_stat(stat: PanelStat) -> None:
    """Emit statsd metrics for a pre-computed PanelStat record."""
    metric = stat.metric
    tags = [f"{k}:{v}" for k, v in stat.static_params.items()]  # noqa: E231

    if stat.input_param_name is not None and stat.input_cypher is not None:
        try:
            input_results = await run_query_with_retry(stat.input_cypher, {})
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
            _params = {stat.input_param_name: value, **stat.static_params}
            _tags = [f"{stat.input_param_name}:{value}"]  # noqa: E231
            _tags.extend(tags)
            try:
                metric_results = await run_query_with_retry(
                    stat.cypher, parameters=_params
                )
            except neo4j.exceptions.ServiceUnavailable:
                logger.exception(
                    "Failed to record metric",
                    extra={"metric": metric},
                )
                continue
            for metric_result in metric_results:
                if stat.panel_type == "progress":
                    statsd.gauge(
                        f"{metric}.numerator", metric_result["numerator"], tags=_tags
                    )
                    statsd.gauge(
                        f"{metric}.denominator",
                        metric_result["denominator"],
                        tags=_tags,
                    )
                elif stat.panel_type == "count":
                    statsd.gauge(f"{metric}.total", metric_result["total"], tags=_tags)
    else:
        try:
            metric_results = await run_query_with_retry(
                stat.cypher, parameters=stat.static_params
            )
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
            if stat.panel_type == "progress":
                statsd.gauge(
                    f"{metric}.numerator", metric_result["numerator"], tags=tags
                )
                statsd.gauge(
                    f"{metric}.denominator", metric_result["denominator"], tags=tags
                )
            elif stat.panel_type == "count":
                statsd.gauge(f"{metric}.total", metric_result["total"], tags=tags)


async def dashboard_stats() -> None:
    logger.debug("Sending in stats...")
    panel_stats = await report_store.list_panel_stats()
    for stat in panel_stats:
        await send_stats_for_panel_stat(stat)


def main() -> None:
    asyncio.run(dashboard_stats())


if __name__ == "__main__":
    main()
