import logging
from typing import Any
from typing import Dict
from typing import List

from reporting.schema.reporting_config import ScheduledQueryAction

logger = logging.getLogger(__name__)


def action_name() -> str:
    return "log"


def setup(config: Dict[str, Any]) -> None:
    return


def handle_results(
    scheduled_query_id: str, action: ScheduledQueryAction, results: List[Dict[str, Any]]
) -> None:
    if not results:
        return

    attr = action.action_config.get("query_return_attribute", "details")
    message = action.action_config.get("message", f"Result for {scheduled_query_id}")
    level = action.action_config.get("level", "info")
    log_attrs = action.action_config.get("log_attrs", [])
    if not log_attrs:
        logger.error(f"{scheduled_query_id} is missing log_attrs in action_config.")
        return

    logger.info(
        "Sending results for query",
        extra={
            "result_count": len(results),
            "scheduled_query_id": scheduled_query_id,
        },
    )
    for result in results:
        data = {}
        for key, val in result[attr].items():
            if key in log_attrs:
                data[key] = val
        level_ref = getattr(logging, level.upper())
        logger.log(level_ref, message, extra=data)
