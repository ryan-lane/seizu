import json

from reporting import scheduled_queries
from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction


def test_schedule_query(mocker):
    sq_id = "test_query"
    sq = ScheduledQuery(
        name="test name",
        cypher="test-query",
        enabled=False,
        frequency=5,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={
                    "sqs_queue": "test",
                },
            ),
        ],
    )
    queries = {
        "test-query": "TEST",
    }
    lock_scheduled_query_mock = mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query"
    )
    scheduled_queries.schedule_query(sq_id, sq, queries)
    assert lock_scheduled_query_mock.call_count == 0

    sq.enabled = True

    mocker.patch("reporting.scheduled_queries.lock_scheduled_query", return_value=False)
    result_mock = mocker.patch("reporting.scheduled_queries.run_query_with_retry")

    scheduled_queries.schedule_query(sq_id, sq, queries)
    assert result_mock.call_count == 0

    handle_results_mock = mocker.patch("reporting.scheduled_queries._handle_results")
    mocker.patch("reporting.scheduled_queries.lock_scheduled_query", return_value=True)
    result_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        return_value=[
            {"details": {"test": "test"}},
            {"details": {"test2": "test2"}},
        ],
    )
    reset_mock = mocker.patch(
        "reporting.scheduled_queries.reset_scheduled_query_fail_count"
    )

    scheduled_queries.schedule_query(sq_id, sq, queries)
    assert handle_results_mock.call_count == 1
    assert reset_mock.call_count == 1

    result_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        side_effect=Exception(),
    )
    incr_mock = mocker.patch(
        "reporting.scheduled_queries.incr_scheduled_query_fail_count"
    )
    scheduled_queries.schedule_query(sq_id, sq, queries)
    assert incr_mock.call_count == 1


def test___handle_results(mocker):
    mod_mock = mocker.patch("reporting.scheduled_query_modules.get_module")
    mod_mock.handle_results = mocker.MagicMock()

    sq_id = "test_query"
    action = ScheduledQueryAction(
        action_type="sqs",
        action_config={
            "sqs_queue": "test",
        },
    )
    results = [{"details": {"hello": "world"}}, {"details": {"foo": "bar"}}]
    scheduled_queries._handle_results(sq_id, mocker.MagicMock(), results)
    assert mod_mock.call_count == 0

    mocker.patch(
        "reporting.scheduled_query_modules.get_module_names", return_value=["slack"]
    )
    scheduled_queries._handle_results(sq_id, action, results)
    assert mod_mock.call_count == 0

    mocker.patch(
        "reporting.scheduled_query_modules.get_module_names", return_value=["sqs"]
    )
    scheduled_queries._handle_results(sq_id, action, results)
    assert mod_mock.call_count == 1


def test__schedule_queries(mocker):
    config = {
        "scheduled_queries": {
            "test_query": {
                "name": "test name",
                "cypher": "test-query",
                "enabled": False,
                "frequency": 5,
                "actions": [
                    {"action_type": "sqs", "action_config": {"sqs_queue": "test"}},
                ],
            },
            "test_query2": {
                "name": "test name",
                "cypher": "test-query",
                "enabled": False,
                "frequency": 5,
                "actions": [
                    {"action_type": "sqs", "action_config": {"sqs_queue": "test"}},
                ],
            },
        },
        "queries": {
            "test-query": "TEST",
        },
    }
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(config)))
    load_modules_mock = mocker.patch("reporting.scheduled_query_modules.load_modules")
    bootstrap_mock = mocker.patch("reporting.scheduled_queries._bootstrap")
    shutdown_mock = mocker.patch(
        "reporting.scheduled_queries._is_shutdown", side_effect=[False, False, True]
    )
    sq_mock = mocker.patch("reporting.scheduled_queries.schedule_query")
    sleep_mock = mocker.patch("reporting.scheduled_queries.time.sleep")

    scheduled_queries._schedule_queries()
    assert load_modules_mock.call_count == 1
    assert bootstrap_mock.call_count == 1
    assert shutdown_mock.call_count == 3
    assert sq_mock.call_count == 2
    assert sleep_mock.call_count == 1
