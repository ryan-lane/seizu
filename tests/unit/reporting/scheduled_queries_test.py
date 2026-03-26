from unittest.mock import AsyncMock

from reporting import scheduled_queries
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction


async def test_schedule_query_disabled(mocker):
    """Disabled queries are skipped without acquiring the lock."""
    sq_id = "test_query"
    sq = ScheduledQuery(
        name="test name",
        cypher="test-query",
        enabled=False,
        frequency=5,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            ),
        ],
    )
    lock_mock = mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(sq_id, sq)
    assert lock_mock.call_count == 0


async def test_schedule_query_lock_not_acquired(mocker):
    """If the lock is not acquired, the query is not run."""
    sq_id = "test_query"
    sq = ScheduledQuery(
        name="test name",
        cypher="test-query",
        enabled=True,
        frequency=5,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            ),
        ],
    )
    mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query",
        new=AsyncMock(return_value=False),
    )
    run_mock = mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(sq_id, sq)
    assert run_mock.call_count == 0


async def test_schedule_query_runs_and_handles_results(mocker):
    """When the lock is acquired, the query is run and actions are handled."""
    sq_id = "test_query"
    sq = ScheduledQuery(
        name="test name",
        cypher="test-query",
        enabled=True,
        frequency=5,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            ),
        ],
    )
    mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query",
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
    reset_mock = mocker.patch(
        "reporting.scheduled_queries.reset_scheduled_query_fail_count",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(sq_id, sq)
    assert handle_results_mock.call_count == 1
    assert reset_mock.call_count == 1


async def test_schedule_query_failure_increments_count(mocker):
    """When query execution raises, the fail count is incremented."""
    sq_id = "test_query"
    sq = ScheduledQuery(
        name="test name",
        cypher="test-query",
        enabled=True,
        frequency=5,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            ),
        ],
    )
    mocker.patch(
        "reporting.scheduled_queries.lock_scheduled_query",
        new=AsyncMock(return_value=True),
    )
    mocker.patch(
        "reporting.scheduled_queries.run_query_with_retry",
        new=AsyncMock(side_effect=Exception()),
    )
    incr_mock = mocker.patch(
        "reporting.scheduled_queries.incr_scheduled_query_fail_count",
        new=AsyncMock(),
    )
    await scheduled_queries.schedule_query(sq_id, sq)
    assert incr_mock.call_count == 1


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
