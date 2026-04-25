from unittest.mock import AsyncMock

from reporting.scheduled_query_modules import sqs
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.reporting_config import ScheduledQueryAction


def test_action_name():
    assert sqs.action_name() == "sqs"


async def test_setup(mocker):
    mocker.patch("reporting.scheduled_query_modules.sqs._SQS_CREATE_SCHEDULED_QUERY_QUEUES", True)
    client_mock = mocker.MagicMock()
    client_mock.create_queue = mocker.MagicMock()
    mocker.patch("reporting.scheduled_query_modules.sqs._get_client", return_value=client_mock)
    items = [
        ScheduledQueryItem(
            scheduled_query_id="sq1",
            name="test_query",
            cypher="test",
            enabled=True,
            params=[],
            watch_scans=[],
            actions=[{"action_type": "sqs", "action_config": {"sqs_queue": "test"}}],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_by="seed-script",
        ),
        ScheduledQueryItem(
            scheduled_query_id="sq2",
            name="test_query2",
            cypher="test",
            enabled=True,
            params=[],
            watch_scans=[],
            actions=[{"action_type": "sqs", "action_config": {"sqs_queue": "test2"}}],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            created_by="seed-script",
        ),
    ]
    mocker.patch(
        "reporting.scheduled_query_modules.sqs.report_store.list_scheduled_queries",
        new=AsyncMock(return_value=items),
    )
    await sqs.setup()
    assert client_mock.create_queue.call_count == 2


def test_handle_results(mocker):
    action = ScheduledQueryAction(action_type="sqs", action_config={"sqs_queue": "test"})
    results = [{"details": {"param1": "value1"}}, {"details": {"param2": "value2"}}]
    client_mock = mocker.MagicMock()
    client_mock.send_message = mocker.MagicMock()
    mocker.patch("reporting.scheduled_query_modules.sqs._get_client", return_value=client_mock)

    sqs.handle_results("test_query", action, results)
    assert client_mock.send_message.call_count == 2
