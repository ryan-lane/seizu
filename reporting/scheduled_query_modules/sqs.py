import json
import logging
from typing import Any
from typing import Dict

from reporting.schema.reporting_config import ReportingConfig
from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.services import get_boto_client
from reporting.utils.settings import bool_env
from reporting.utils.settings import str_env

logger = logging.getLogger(__name__)

# Whether or not to create the queues referenced in the scheduled query sqs actions (meant for dev)
_SQS_CREATE_SCHEDULED_QUERY_QUEUES = bool_env(
    "SQS_CREATE_SCHEDULED_QUERY_QUEUES", False
)
# URL for the SQS server, for use in dev when pointing at a fake SQS
_SQS_URL = str_env("SQS_URL")


def _get_client() -> Any:
    if _SQS_URL:
        return get_boto_client("sqs", endpoint_url=_SQS_URL)
    else:
        return get_boto_client("sqs")


def action_name() -> str:
    return "sqs"


def setup(config: ReportingConfig) -> None:
    if not _SQS_CREATE_SCHEDULED_QUERY_QUEUES:
        return
    scheduled_queries = config.scheduled_queries
    for scheduled_query_id, scheduled_query in scheduled_queries.items():
        for action in scheduled_query.actions:
            if action.action_type == "sqs":
                sqs_client = _get_client()
                sqs_client.create_queue(QueueName=action.action_config["sqs_queue"])


def handle_results(
    scheduled_query_id: str, action: ScheduledQueryAction, results: Dict[str, Any]
) -> None:
    if not results:
        return

    sqs_client = _get_client()
    q_url = sqs_client.get_queue_url(QueueName=action.action_config["sqs_queue"])[
        "QueueUrl"
    ]
    attr = action.action_config.get("query_return_attribute", "details")
    logger.info(
        "Sending results for query",
        extra={
            "result_count": len(results),
            "scheduled_query_id": scheduled_query_id,
        },
    )
    for result in results:
        body = json.dumps(result[attr])
        sqs_client.send_message(
            QueueUrl=q_url,
            MessageBody=body,
            MessageAttributes={
                "type": {
                    "DataType": "String",
                    "StringValue": scheduled_query_id,
                },
                "source": {
                    "DataType": "String",
                    "StringValue": "seizu",
                },
            },
        )
