import logging
from typing import Any

from datadog.dogstatsd.base import DogStatsd

from reporting.schema.report_config import ActionConfigFieldDef
from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.utils.settings import int_env, list_env, str_env

logger = logging.getLogger(__name__)

_STATSD_HOST = str_env("STATSD_HOST")
_STATSD_PORT = int_env("STATSD_PORT", 8125)
_STATSD_CONSTANT_TAGS = list_env("STATSD_CONSTANT_TAGS")

_CLIENT: DogStatsd | None = None


def _get_client() -> DogStatsd:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = DogStatsd(
            host=_STATSD_HOST or "localhost",
            port=_STATSD_PORT,
            constant_tags=_STATSD_CONSTANT_TAGS or [],
        )
    return _CLIENT


def action_name() -> str:
    return "statsd"


def action_config_schema() -> list[ActionConfigFieldDef]:
    return [
        ActionConfigFieldDef(
            name="metric",
            label="Metric name",
            type="string",
            required=True,
            description="StatsD metric name to emit (e.g. cves.critical).",
        ),
        ActionConfigFieldDef(
            name="value_field",
            label="Value field",
            type="string",
            required=True,
            description="Field in each result row that holds the numeric value to emit.",
        ),
        ActionConfigFieldDef(
            name="metric_type",
            label="Metric type",
            type="select",
            required=False,
            default="gauge",
            options=["gauge", "increment", "decrement"],
            description="StatsD metric type. Use 'gauge' for absolute values (counts, percentages).",
        ),
        ActionConfigFieldDef(
            name="tag_fields",
            label="Tag fields",
            type="string_list",
            required=False,
            description="Fields from each result row to attach as DogStatsD tags (emitted as field:value).",
        ),
        ActionConfigFieldDef(
            name="query_return_attribute",
            label="Query return attribute",
            type="string",
            required=False,
            default="details",
            description="Top-level attribute of each result row that contains the data map.",
        ),
    ]


async def setup() -> None:
    return


def handle_results(
    scheduled_query_id: str,
    action: ScheduledQueryAction,
    results: list[dict[str, Any]],
) -> None:
    if not results:
        return
    if not _STATSD_HOST:
        logger.warning(
            "STATSD_HOST is not configured; skipping statsd action",
            extra={"scheduled_query_id": scheduled_query_id},
        )
        return

    metric = action.action_config.get("metric")
    value_field = action.action_config.get("value_field")
    metric_type = action.action_config.get("metric_type", "gauge")
    tag_fields: list[str] = action.action_config.get("tag_fields") or []
    attr = action.action_config.get("query_return_attribute", "details")

    if not metric or not value_field:
        logger.error(
            "Skipping misconfigured statsd action: missing required fields",
            extra={
                "scheduled_query_id": scheduled_query_id,
                "missing": [k for k in ("metric", "value_field") if not action.action_config.get(k)],
            },
        )
        return

    client = _get_client()
    logger.info(
        "Sending statsd metrics for query",
        extra={
            "result_count": len(results),
            "scheduled_query_id": scheduled_query_id,
            "metric": metric,
        },
    )
    for result in results:
        row = result.get(attr, {})
        value = row.get(value_field)
        if value is None:
            continue
        tags = [f"{field}:{row[field]}" for field in tag_fields if field in row]
        if metric_type == "gauge":
            client.gauge(metric, float(value), tags=tags)
        elif metric_type == "increment":
            client.increment(metric, float(value), tags=tags)
        elif metric_type == "decrement":
            client.decrement(metric, float(value), tags=tags)
