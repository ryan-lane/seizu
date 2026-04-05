from unittest.mock import AsyncMock

from reporting import scheduled_queries
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.reporting_config import ScheduledQueryAction


def _make_sq_item(
    sq_id: str,
    name: str,
    enabled: bool = True,
    frequency: int = 5,
    last_scheduled_at: str | None = None,
) -> ScheduledQueryItem:
    return ScheduledQueryItem(
        scheduled_query_id=sq_id,
        name=name,
        cypher="TEST",
        enabled=enabled,
        frequency=frequency,
        params=[],
        watch_scans=[],
        actions=[{"action_type": "sqs", "action_config": {"sqs_queue": "test"}}],
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
        created_by="seed-script",
        last_scheduled_at=last_scheduled_at,
    )


async def test_schedule_query_disabled(mocker):
    """Disabled queries are skipped without checking triggers."""
    item = _make_sq_item("test_query", "test name", enabled=False)
    trigger_mock = mocker.patch(
        "reporting.scheduled_queries._is_triggered",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(item)
    assert trigger_mock.call_count == 0


async def test_schedule_query_not_triggered(mocker):
    """If no trigger fires, the query is not run."""
    item = _make_sq_item("test_query", "test name")
    mocker.patch(
        "reporting.scheduled_queries._is_triggered",
        new=AsyncMock(return_value=False),
    )
    run_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(item)
    assert run_mock.call_count == 0


async def test_schedule_query_lock_not_acquired(mocker):
    """If the trigger fires but the lock CAS fails, the query is not run."""
    item = _make_sq_item("test_query", "test name")
    mocker.patch(
        "reporting.scheduled_queries._is_triggered",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "reporting.scheduled_queries.report_store.acquire_scheduled_query_lock",
        new=AsyncMock(return_value=False),
    )
    run_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(item)
    assert run_mock.call_count == 0


async def test_schedule_query_runs_and_handles_results(mocker):
    """When the lock is acquired, the query is run and actions are handled."""
    item = _make_sq_item("test_query", "test name")
    mocker.patch(
        "reporting.scheduled_queries._is_triggered",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "reporting.scheduled_queries.report_store.acquire_scheduled_query_lock",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(
            return_value=[
                {"details": {"test": "test"}},
                {"details": {"test2": "test2"}},
            ]
        ),
    )
    handle_results_mock = mocker.patch(
        "reporting.scheduled_queries._handle_results",
        new=AsyncMock(),
    )
    record_result_mock = mocker.patch(
        "reporting.scheduled_queries.report_store.record_scheduled_query_result",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(item)
    assert handle_results_mock.call_count == 1
    record_result_mock.assert_called_once_with(item.scheduled_query_id, "success")


async def test_schedule_query_failure_records_error(mocker):
    """When query execution raises, the failure is recorded."""
    item = _make_sq_item("test_query", "test name")
    mocker.patch(
        "reporting.scheduled_queries._is_triggered",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "reporting.scheduled_queries.report_store.acquire_scheduled_query_lock",
        new=AsyncMock(return_value=True),
    )
    exc = Exception("test error")
    mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(side_effect=exc),
    )
    record_result_mock = mocker.patch(
        "reporting.scheduled_queries.report_store.record_scheduled_query_result",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(item)
    record_result_mock.assert_called_once_with(
        item.scheduled_query_id, "failure", error="test error"
    )


async def test___handle_results_no_action_type(mocker):
    """Missing action_type is handled gracefully."""
    mod_mock = mocker.patch("reporting.scheduled_query_modules.get_module")
    sq_id = "test_query"
    await scheduled_queries._handle_results(sq_id, mocker.MagicMock(), [])
    assert mod_mock.call_count == 0


async def test___handle_results_unknown_action(mocker):
    """Action with unknown action_type (not in module names) is skipped."""
    mod_mock = mocker.patch("reporting.scheduled_query_modules.get_module")
    sq_id = "test_query"
    action = ScheduledQueryAction(
        action_type="sqs",
        action_config={"sqs_queue": "test"},
    )
    results = [{"details": {"hello": "world"}}]
    mocker.patch(
        "reporting.scheduled_query_modules.get_module_names", return_value=["slack"]
    )
    await scheduled_queries._handle_results(sq_id, action, results)
    assert mod_mock.call_count == 0


async def test___handle_results_known_action(mocker):
    """Action with known action_type calls the module."""
    mod_mock = mocker.patch("reporting.scheduled_query_modules.get_module")
    sq_id = "test_query"
    action = ScheduledQueryAction(
        action_type="sqs",
        action_config={"sqs_queue": "test"},
    )
    results = [{"details": {"hello": "world"}}, {"details": {"foo": "bar"}}]
    mocker.patch(
        "reporting.scheduled_query_modules.get_module_names", return_value=["sqs"]
    )
    await scheduled_queries._handle_results(sq_id, action, results)
    assert mod_mock.call_count == 1


async def test__schedule_queries(mocker):
    item1 = _make_sq_item("sq1", "test name")
    item2 = _make_sq_item("sq2", "test name 2")
    mocker.patch(
        "reporting.scheduled_queries.report_store.list_scheduled_queries",
        new=AsyncMock(return_value=[item1, item2]),
    )
    load_modules_mock = mocker.patch("reporting.scheduled_query_modules.load_modules")
    bootstrap_mock = mocker.patch("reporting.scheduled_queries._bootstrap")
    sq_mock = mocker.patch(
        "reporting.scheduled_queries.schedule_query",
        new=AsyncMock(),
    )

    # Control the shutdown event: set it after the sleep call so only one
    # loop iteration runs.
    sleep_call_count = 0

    async def fake_sleep(_delay: float) -> None:
        nonlocal sleep_call_count
        sleep_call_count += 1
        scheduled_queries._shutdown_event.set()

    mocker.patch("asyncio.sleep", new=fake_sleep)

    scheduled_queries._shutdown_event.clear()
    await scheduled_queries._schedule_queries()

    assert load_modules_mock.call_count == 1
    assert bootstrap_mock.call_count == 1
    assert sq_mock.call_count == 2
    assert sleep_call_count == 1


async def test__schedule_queries_calls_with_item(mocker):
    """_schedule_queries passes the full ScheduledQueryItem to schedule_query."""
    item = _make_sq_item("sq1", "test name")
    mocker.patch(
        "reporting.scheduled_queries.report_store.list_scheduled_queries",
        new=AsyncMock(return_value=[item]),
    )
    mocker.patch("reporting.scheduled_query_modules.load_modules")
    mocker.patch("reporting.scheduled_queries._bootstrap")
    sq_mock = mocker.patch(
        "reporting.scheduled_queries.schedule_query",
        new=AsyncMock(),
    )

    async def fake_sleep(_delay: float) -> None:
        scheduled_queries._shutdown_event.set()

    mocker.patch("asyncio.sleep", new=fake_sleep)

    scheduled_queries._shutdown_event.clear()
    await scheduled_queries._schedule_queries()

    sq_mock.assert_called_once_with(item)


async def test__frequency_triggered_no_previous_run():
    """A query with no last_scheduled_at is always triggered."""
    assert scheduled_queries._frequency_triggered(None, 60) is True


async def test__frequency_triggered_not_yet_due():
    """A query scheduled very recently is not triggered."""
    # Use a timestamp far in the future to ensure it's not due
    future = "2099-01-01T00:00:00+00:00"
    assert scheduled_queries._frequency_triggered(future, 60) is False


async def test__frequency_triggered_overdue():
    """A query whose window has elapsed is triggered."""
    past = "2000-01-01T00:00:00+00:00"
    assert scheduled_queries._frequency_triggered(past, 60) is True
