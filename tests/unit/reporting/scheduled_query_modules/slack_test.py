from reporting.scheduled_query_modules import slack
from reporting.schema.reporting_config import ScheduledQueryAction


def test_action_name():
    assert slack.action_name() == "slack"


def test_setup(mocker):
    assert slack.setup({}) is None


def test_handle_results(mocker):
    action = ScheduledQueryAction(
        action_type="slack",
        action_config={
            "title": "test",
            "initial_comment": "test comment",
            "channels": ["ABCDE", "TEST123"],
        },
    )
    results = [{"details": {"param1": "value1"}}, {"details": {"param1": "value2"}}]
    client_mock = mocker.MagicMock()
    client_mock.conversations_join = mocker.MagicMock()
    client_mock.files_upload = mocker.MagicMock()
    mocker.patch(
        "reporting.scheduled_query_modules.slack._get_client", return_value=client_mock
    )

    slack.handle_results("test_query", action, results)
    assert client_mock.conversations_join.call_count == 2
    assert client_mock.files_upload.call_count == 1
