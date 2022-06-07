from datetime import datetime

import neo4j.exceptions
import pytest
from pynamodb.exceptions import DoesNotExist
from pynamodb.exceptions import PutError

from reporting.exceptions import UserCreationError
from reporting.exceptions import UserDeletionError
from reporting.models.user import User
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


def test_get_users(mocker):
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.run.return_value = [{"username": "testuser"}]
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    assert reporting_neo4j.get_users() == ["testuser"]


def test_create_user(mocker):
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.write_transaction.return_value = None
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    mocker.patch("reporting.models.user.User.save")
    mocker.patch(
        "reporting.services.reporting_neo4j.secrets.token_hex",
        return_value="test_secret",
    )
    assert reporting_neo4j.create_user("test") == "test_secret"


def test_create_user_dynamo_failure(mocker):
    mocker.patch("reporting.models.user.User.save", side_effect=PutError())
    with pytest.raises(UserCreationError):
        reporting_neo4j.create_user("test")


def test_create_user_neo4j_failure(mocker):
    mocker.patch("reporting.models.user.User.save")
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.write_transaction.side_effect = (
        neo4j.exceptions.ClientError
    )
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    with pytest.raises(UserCreationError):
        reporting_neo4j.create_user("test")


def test_delete_user(mocker):
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.write_transaction.return_value = None
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    assert reporting_neo4j.delete_user("test") is None


def test_delete_user_neo4j_failure(mocker):
    driver_mock = mocker.MagicMock()
    session_mock = mocker.MagicMock()
    session_mock.__enter__.return_value.write_transaction.side_effect = (
        neo4j.exceptions.ClientError
    )
    driver_mock.session.return_value = session_mock
    mocker.patch(
        "reporting.services.reporting_neo4j._get_neo4j_client",
        return_value=driver_mock,
    )
    with pytest.raises(UserDeletionError):
        reporting_neo4j.delete_user("test")


def test_delete_expired_users(mocker):
    mocker.patch(
        "reporting.services.reporting_neo4j.get_users",
        return_value=[
            "expired_user",
            "valid_user",
            "nonexistent_user",
            "failedtodelete_user",
            "neo4j",
        ],
    )
    expired_user_mock = mocker.MagicMock()
    expired_user_mock.is_expired.return_value = True
    valid_user_mock = mocker.MagicMock()
    valid_user_mock.is_expired.return_value = False
    failedtodelete_user_mock = mocker.MagicMock()
    failedtodelete_user_mock.is_expired.return_value = True
    user_mock = mocker.patch.object(
        User,
        "get",
        side_effect=[
            expired_user_mock,
            valid_user_mock,
            DoesNotExist,
            failedtodelete_user_mock,
        ],
    )
    delete_mock = mocker.patch(
        "reporting.services.reporting_neo4j.delete_user",
        side_effect=[None, None, UserDeletionError],
    )
    reporting_neo4j.delete_expired_users()
    delete_mock.assert_has_calls(
        [
            mocker.call("expired_user"),
            mocker.call("nonexistent_user"),
            mocker.call("failedtodelete_user"),
        ],
    )
    user_mock.assert_has_calls(
        [
            mocker.call("expired_user"),
            mocker.call("valid_user"),
            mocker.call("nonexistent_user"),
            mocker.call("failedtodelete_user"),
        ],
    )


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
        watch_scans=ScheduledQueryWatchScan(
            grouptype="test",
        ),
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
