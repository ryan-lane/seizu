from reporting import scheduled_queries
from reporting.schema.report_config import ScheduledQueryItem
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
    lock_scheduled_query_mock = mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query"
    )
    scheduled_queries.schedule_query(sq_id, sq)
    assert lock_scheduled_query_mock.call_count == 0

    sq.enabled = True

    mocker.patch("reporting.scheduled_queries.lock_scheduled_query", return_value=False)
    result_mock = mocker.patch("reporting.scheduled_queries.run_query_with_retry")

    scheduled_queries.schedule_query(sq_id, sq)
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

    scheduled_queries.schedule_query(sq_id, sq)
    assert handle_results_mock.call_count == 1
    assert reset_mock.call_count == 1

    result_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        side_effect=Exception(),
    )
    incr_mock = mocker.patch(
        "reporting.scheduled_queries.incr_scheduled_query_fail_count"
    )
    scheduled_queries.schedule_query(sq_id, sq)
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


def _make_sq_item(sq_id: str, name: str) -> ScheduledQueryItem:
    return ScheduledQueryItem(
        scheduled_query_id=sq_id,
        name=name,
        cypher="TEST",
        enabled=False,
        frequency=5,
        params=[],
        watch_scans=[],
        actions=[{"action_type": "sqs", "action_config": {"sqs_queue": "test"}}],
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        created_by="seed-script",
    )


def test__schedule_queries(mocker):
    item1 = _make_sq_item("sq1", "test name")
    item2 = _make_sq_item("sq2", "test name 2")
    mocker.patch(
        "reporting.scheduled_queries.report_store.list_scheduled_queries",
        return_value=[item1, item2],
    )
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
