from reporting.scheduled_query_modules import sqs
from reporting.schema.reporting_config import ReportingConfig
from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction


def test_action_name():
    assert sqs.action_name() == "sqs"


def test_setup(mocker):
    mocker.patch(
        "reporting.scheduled_query_modules.sqs._SQS_CREATE_SCHEDULED_QUERY_QUEUES", True
    )
    client_mock = mocker.MagicMock()
    client_mock.create_queue = mocker.MagicMock()
    mocker.patch(
        "reporting.scheduled_query_modules.sqs._get_client", return_value=client_mock
    )
    sq = {
        "test_query": ScheduledQuery(
            name="test_query",
            cypher="test",
            actions=[
                ScheduledQueryAction(
                    action_type="sqs", action_config={"sqs_queue": "test"}
                )
            ],
        ),
        "test_query2": ScheduledQuery(
            name="test_query",
            cypher="test",
            actions=[
                ScheduledQueryAction(
                    action_type="sqs", action_config={"sqs_queue": "test2"}
                )
            ],
        ),
    }
    config = ReportingConfig(scheduled_queries=sq)
    sqs.setup(config)
    assert client_mock.create_queue.call_count == 2


def test_handle_results(mocker):
    action = ScheduledQueryAction(
        action_type="sqs", action_config={"sqs_queue": "test"}
    )
    results = [{"details": {"param1": "value1"}}, {"details": {"param2": "value2"}}]
    client_mock = mocker.MagicMock()
    client_mock.send_message = mocker.MagicMock()
    mocker.patch(
        "reporting.scheduled_query_modules.sqs._get_client", return_value=client_mock
    )

    sqs.handle_results("test_query", action, results)
    assert client_mock.send_message.call_count == 2
