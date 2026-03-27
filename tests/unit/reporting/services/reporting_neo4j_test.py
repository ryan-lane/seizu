from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import neo4j.exceptions
import pytest

from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.schema.reporting_config import ScheduledQueryWatchScan
from reporting.services import reporting_neo4j


def test__get_neo4j_client(mocker):
    db_mock = mocker.MagicMock
    mocker.patch(
        "reporting.services.reporting_neo4j.AsyncGraphDatabase.driver",
        return_value=db_mock,
    )
    assert reporting_neo4j._get_async_neo4j_client() == db_mock


def test__get_neo4j_client_with_cache(mocker):
    db_mock = mocker.MagicMock
    mocker.patch.object(reporting_neo4j, "_ASYNC_CLIENT_CACHE", db_mock)
    assert reporting_neo4j._get_async_neo4j_client() == db_mock


async def test_run_query(mocker):
    mock_record = MagicMock()
    driver_mock = MagicMock()

    async def _records():
        yield mock_record

    session_mock = AsyncMock()
    session_mock.run = AsyncMock(return_value=_records())
    driver_mock.session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    driver_mock.session.return_value.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "reporting.services.reporting_neo4j._get_async_neo4j_client",
        return_value=driver_mock,
    )
    result = await reporting_neo4j.run_query("MATCH (n) RETURN n")
    assert result == [mock_record]


async def test_run_query_with_single_retry_failure(mocker):
    run_query_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_query",
        new=AsyncMock(
            side_effect=[neo4j.exceptions.ServiceUnavailable(), ["test-result"]]
        ),
    )
    result = await reporting_neo4j.run_query_with_retry("test", {})
    assert result == ["test-result"]
    assert run_query_mock.call_count == 2


async def test_run_query_with_raise(mocker):
    run_query_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_query",
        new=AsyncMock(side_effect=neo4j.exceptions.ServiceUnavailable()),
    )
    with pytest.raises(neo4j.exceptions.ServiceUnavailable):
        await reporting_neo4j.run_query_with_retry("test", {})
    assert run_query_mock.call_count >= 2


async def test_run_tx(mocker):
    mock_record = MagicMock()
    tx_mock = AsyncMock()

    async def _records():
        yield mock_record

    tx_mock.run = AsyncMock(return_value=_records())
    result = await reporting_neo4j.run_tx(tx_mock, "MATCH (n) RETURN n")
    assert result == [mock_record]


async def test_run_tx_with_single_retry_failure(mocker):
    run_tx_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_tx",
        new=AsyncMock(
            side_effect=[neo4j.exceptions.ServiceUnavailable(), ["test-result"]]
        ),
    )
    tx_mock = AsyncMock()
    result = await reporting_neo4j.run_tx_with_retry(tx_mock, "test")
    assert result == ["test-result"]
    assert run_tx_mock.call_count == 2


async def test_run_tx_with_raise(mocker):
    run_tx_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_tx",
        new=AsyncMock(side_effect=neo4j.exceptions.ServiceUnavailable()),
    )
    tx_mock = AsyncMock()
    with pytest.raises(neo4j.exceptions.ServiceUnavailable):
        await reporting_neo4j.run_tx_with_retry(tx_mock, "test")
    assert run_tx_mock.call_count >= 2


async def test__lock(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_tx_with_retry",
        new=AsyncMock(),
    )
    tx_mock = AsyncMock()
    assert await reporting_neo4j._lock(tx_mock, "test") is None


async def test__scheduled_time(mocker):
    mock_record = MagicMock()
    mock_record.__getitem__ = MagicMock(return_value=1)
    mocker.patch(
        "reporting.services.reporting_neo4j.run_tx_with_retry",
        new=AsyncMock(return_value=[{"sq.scheduled": 1}]),
    )
    tx_mock = AsyncMock()
    assert await reporting_neo4j._scheduled_time(tx_mock, "test") == 1


async def test__scan_time(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_tx_with_retry",
        new=AsyncMock(return_value=[{"maxlastupdated": 1}]),
    )
    tx_mock = AsyncMock()
    assert (
        await reporting_neo4j._scan_time(
            tx_mock, ScheduledQueryWatchScan(grouptype="test")
        )
        == 1
    )


async def test__watch_triggered(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j._scan_time",
        new=AsyncMock(return_value=10),
    )
    tx_mock = AsyncMock()
    assert (
        await reporting_neo4j._watch_triggered(
            tx_mock, 1, [ScheduledQueryWatchScan(grouptype="test")]
        )
        is True
    )
    assert (
        await reporting_neo4j._watch_triggered(
            tx_mock, 11, [ScheduledQueryWatchScan(grouptype="test")]
        )
        is False
    )


def test_frequency_triggered():
    now = int(datetime.now().timestamp())
    assert reporting_neo4j._frequency_triggered(now, 60) is False
    assert reporting_neo4j._frequency_triggered(now - (120 * 60), 60) is True


async def test_lock_scheduled_query_frequency(mocker):
    """lock_scheduled_query returns True when frequency triggers."""
    mocker.patch(
        "reporting.services.reporting_neo4j._lock",
        new=AsyncMock(),
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._scheduled_time",
        new=AsyncMock(return_value=0),
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._frequency_triggered",
        return_value=True,
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._watch_triggered",
        new=AsyncMock(return_value=False),
    )

    # Build async context manager for driver.session() and session.begin_transaction()
    tx_mock = AsyncMock()
    tx_cm = AsyncMock()
    tx_cm.__aenter__ = AsyncMock(return_value=tx_mock)
    tx_cm.__aexit__ = AsyncMock(return_value=False)

    session_mock = AsyncMock()
    session_mock.begin_transaction = AsyncMock(return_value=tx_cm)
    driver_mock = MagicMock()
    driver_mock.session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    driver_mock.session.return_value.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "reporting.services.reporting_neo4j._get_async_neo4j_client",
        return_value=driver_mock,
    )

    sq = ScheduledQuery(
        name="test",
        cypher="test",
        frequency=1,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            )
        ],
    )
    assert await reporting_neo4j.lock_scheduled_query("test", sq) is True


async def test_lock_scheduled_query_no_trigger(mocker):
    """lock_scheduled_query returns False when neither frequency nor watch triggers."""
    mocker.patch(
        "reporting.services.reporting_neo4j._scheduled_time",
        new=AsyncMock(return_value=0),
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._frequency_triggered",
        return_value=False,
    )

    tx_mock = AsyncMock()
    tx_cm = AsyncMock()
    tx_cm.__aenter__ = AsyncMock(return_value=tx_mock)
    tx_cm.__aexit__ = AsyncMock(return_value=False)

    session_mock = AsyncMock()
    session_mock.begin_transaction = AsyncMock(return_value=tx_cm)
    driver_mock = MagicMock()
    driver_mock.session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    driver_mock.session.return_value.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "reporting.services.reporting_neo4j._get_async_neo4j_client",
        return_value=driver_mock,
    )

    sq = ScheduledQuery(
        name="test",
        cypher="test",
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            )
        ],
    )
    assert await reporting_neo4j.lock_scheduled_query("test", sq) is False


async def test_lock_scheduled_query_transaction_error(mocker):
    """lock_scheduled_query returns False on TransactionError."""
    tx_mock = AsyncMock()
    mocker.patch(
        "reporting.services.reporting_neo4j._scheduled_time",
        new=AsyncMock(side_effect=neo4j.exceptions.TransactionError(tx_mock)),
    )

    tx_cm = AsyncMock()
    tx_cm.__aenter__ = AsyncMock(return_value=tx_mock)
    tx_cm.__aexit__ = AsyncMock(return_value=False)

    session_mock = AsyncMock()
    session_mock.begin_transaction = AsyncMock(return_value=tx_cm)
    driver_mock = MagicMock()
    driver_mock.session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    driver_mock.session.return_value.__aexit__ = AsyncMock(return_value=False)

    mocker.patch(
        "reporting.services.reporting_neo4j._get_async_neo4j_client",
        return_value=driver_mock,
    )

    sq = ScheduledQuery(
        name="test",
        cypher="test",
        frequency=1,
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            )
        ],
    )
    assert await reporting_neo4j.lock_scheduled_query("test", sq) is False


async def test_incr_scheduled_query_fail_count(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_query_with_retry",
        new=AsyncMock(),
    )
    assert await reporting_neo4j.incr_scheduled_query_fail_count("test") is None


async def test_reset_scheduled_query_fail_count(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_query_with_retry",
        new=AsyncMock(),
    )
    assert await reporting_neo4j.reset_scheduled_query_fail_count("test") is None
