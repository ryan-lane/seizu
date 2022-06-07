import csv
import io
import logging
from typing import Any
from typing import Dict
from typing import List

from slack_sdk import WebClient

from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.utils.settings import str_env

logger = logging.getLogger(__name__)

# Bot token from a slack app's settings
_SLACK_OAUTH_BOT_TOKEN = str_env("SLACK_OAUTH_BOT_TOKEN")

_CLIENT = None


def _get_client() -> Any:
    global _CLIENT

    if _CLIENT is None:
        _CLIENT = WebClient(token=_SLACK_OAUTH_BOT_TOKEN)
    return _CLIENT


def action_name() -> str:
    return "slack"


def setup(config: Dict[str, Any]) -> None:
    return


def handle_results(
    scheduled_query_id: str, action: ScheduledQueryAction, results: List[Dict[str, Any]]
) -> None:
    if not results:
        return

    slack_client = _get_client()

    attr = action.action_config.get("query_return_attribute", "details")
    logger.info(
        "Sending results for query",
        extra={
            "result_count": len(results),
            "scheduled_query_id": scheduled_query_id,
        },
    )
    for key in ["channels", "initial_comment", "title"]:
        if not action.action_config.get(key):
            logger.error(
                "Skipping misconfigured scheduled query",
                extra={
                    "scheduled_query_id": scheduled_query_id,
                    "action_type": action.action_type,
                    "misconfiguration": f"missing {key}",
                },
            )

    content = io.StringIO()
    fieldnames = results[0][attr].keys()
    writer = csv.DictWriter(content, fieldnames=fieldnames)
    writer.writeheader()
    for result in results:
        writer.writerow(result[attr])

    for channel in action.action_config["channels"]:
        slack_client.conversations_join(channel=channel)
    slack_client.files_upload(
        content=content.getvalue(),
        filename=f"{attr}.csv",
        channels=action.action_config["channels"],
        title=action.action_config["title"],
        initial_comment=action.action_config["initial_comment"],
    )
