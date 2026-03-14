from datetime import datetime

import neo4j.exceptions
import pytest

from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.schema.reporting_config import ScheduledQueryWatchScan
from reporting.services import reporting_neo4j


def test__get_neo4j_client(mocker):
    db_mock = mocker.MagicMock
    mocker.patch(
        "reporting.services.reporting_neo4j.GraphDatabase.driver",
        return_value=db_mock,
    )
    assert reporting_neo4j._get_neo4j_client() == db_mock


def test__get_neo4j_client_with_cache(mocker):
    db_mock = mocker.MagicMock
    mocker.patch.object(reporting_neo4j, "_CLIENT_CACHE", db_mock)
    assert reporting_neo4j._get_neo4j_client() == db_mock


def test_run_query(mocker):
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.run.return_value = ["test"]
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    assert reporting_neo4j.run_query("test") == ["test"]


def test_run_query_with_single_retry_failure(mocker):
    run_query_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_query",
        side_effect=[neo4j.exceptions.ServiceUnavailable, "test-result"],
    )
    assert reporting_neo4j.run_query_with_retry("test", "test-result")
    assert run_query_mock.call_count == 2


def test_run_query_with_raise(mocker):
    run_query_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_query",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    with pytest.raises(neo4j.exceptions.ServiceUnavailable):
        reporting_neo4j.run_query_with_retry("test", "test-result")
        assert run_query_mock.call_count == 2


def test_run_tx(mocker):
    tx_mock = mocker.MagicMock()
    run_mock = mocker.MagicMock(return_value=["test"])
    tx_mock.run = run_mock
    assert reporting_neo4j.run_tx(tx_mock, "test-query") == ["test"]


def test_run_tx_with_single_retry_failure(mocker):
    run_tx_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_tx",
        side_effect=[neo4j.exceptions.ServiceUnavailable, "test-result"],
    )
    assert reporting_neo4j.run_tx_with_retry("test", "test-result")
    assert run_tx_mock.call_count == 2


def test_run_tx_with_raise(mocker):
    run_tx_mock = mocker.patch(
        "reporting.services.reporting_neo4j.run_tx",
        side_effect=neo4j.exceptions.ServiceUnavailable(),
    )
    with pytest.raises(neo4j.exceptions.ServiceUnavailable):
        reporting_neo4j.run_tx_with_retry("test", "test-result")
        assert run_tx_mock.call_count == 2


def test__lock(mocker):
    mocker.patch("reporting.services.reporting_neo4j.run_tx_with_retry")
    tx_mock = mocker.MagicMock()
    assert reporting_neo4j._lock(tx_mock, "test") is None


def test__scheduled_time(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_tx_with_retry",
        return_value=[{"sq.scheduled": 1}],
    )
    tx_mock = mocker.MagicMock()
    assert reporting_neo4j._scheduled_time(tx_mock, "test") == 1


def test__scan_time(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.run_tx_with_retry",
        return_value=[{"maxlastupdated": 1}],
    )
    tx_mock = mocker.MagicMock()
    assert (
        reporting_neo4j._scan_time(tx_mock, ScheduledQueryWatchScan(grouptype="test"))
        == 1
    )


def test__watch_triggered(mocker):
    mocker.patch("reporting.services.reporting_neo4j._scan_time", return_value=10)
    tx_mock = mocker.MagicMock()
    assert reporting_neo4j._watch_triggered(tx_mock, 1, [{"grouptype": "test"}]) is True
    assert (
        reporting_neo4j._watch_triggered(tx_mock, 11, [{"grouptype": "test"}]) is False
    )


def test_frequency_triggered():
    now = int(datetime.now().timestamp())
    assert reporting_neo4j._frequency_triggered(now, 60) is False
    assert reporting_neo4j._frequency_triggered(now - (120 * 60), 60) is True


def test_lock_scheduled_query(mocker):
    driver_mock = mocker.MagicMock()
    tx_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.begin_transaction.__enter__return_value = None
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    mocker.patch("reporting.services.reporting_neo4j._lock")
    mocker.patch(
        "reporting.services.reporting_neo4j._scheduled_time", return_value=True
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._frequency_triggered", return_value=True
    )
    mocker.patch(
        "reporting.services.reporting_neo4j._watch_triggered", return_value=True
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
    assert reporting_neo4j.lock_scheduled_query("test", sq) is True
    sq = ScheduledQuery(
        name="test",
        cypher="test",
        watch_scans=[
            ScheduledQueryWatchScan(
                grouptype="test",
            )
        ],
        actions=[
            ScheduledQueryAction(
                action_type="sqs",
                action_config={"sqs_queue": "test"},
            )
        ],
    )
    assert reporting_neo4j.lock_scheduled_query("test", sq) is True
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
    assert reporting_neo4j.lock_scheduled_query("test", sq) is False

    mocker.patch(
        "reporting.services.reporting_neo4j._lock",
        side_effect=neo4j.exceptions.TransactionError(tx_mock),
    )
    assert reporting_neo4j.lock_scheduled_query("test", sq) is False


def test_incr_scheduled_query_fail_count(mocker):
    mocker.patch("reporting.services.reporting_neo4j.run_query_with_retry")
    assert reporting_neo4j.incr_scheduled_query_fail_count("test") is None


def test_reset_scheduled_query_fail_count(mocker):
    mocker.patch("reporting.services.reporting_neo4j.run_query_with_retry")
    assert reporting_neo4j.reset_scheduled_query_fail_count("test") is None
