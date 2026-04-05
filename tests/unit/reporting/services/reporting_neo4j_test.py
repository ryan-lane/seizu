from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import neo4j.exceptions
import pytest

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


async def test__scan_time(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_query_with_retry",
        new=AsyncMock(return_value=[{"maxlastupdated": 1}]),
    )
    assert (
        await reporting_neo4j._scan_time(ScheduledQueryWatchScan(grouptype="test")) == 1
    )


async def test__scan_time_no_results(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_query_with_retry",
        new=AsyncMock(return_value=[{"maxlastupdated": None}]),
    )
    assert (
        await reporting_neo4j._scan_time(ScheduledQueryWatchScan(grouptype="test")) == 0
    )


async def test_check_watch_scan_triggered_true(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j._scan_time",
        new=AsyncMock(return_value=10),
    )
    # last_scheduled_at = epoch → unix seconds = 0 → 10 > 0
    result = await reporting_neo4j.check_watch_scan_triggered(
        "1970-01-01T00:00:00+00:00", [ScheduledQueryWatchScan(grouptype="test")]
    )
    assert result is True


async def test_check_watch_scan_triggered_false(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j._scan_time",
        new=AsyncMock(return_value=10),
    )
    # last_scheduled_at far in the future → unix seconds >> 10
    result = await reporting_neo4j.check_watch_scan_triggered(
        "2099-01-01T00:00:00+00:00", [ScheduledQueryWatchScan(grouptype="test")]
    )
    assert result is False


async def test_check_watch_scan_triggered_none_last_scheduled(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j._scan_time",
        new=AsyncMock(return_value=1),
    )
    # None → scheduled_unix = 0, any non-zero scan_time triggers
    result = await reporting_neo4j.check_watch_scan_triggered(
        None, [ScheduledQueryWatchScan(grouptype="test")]
    )
    assert result is True
