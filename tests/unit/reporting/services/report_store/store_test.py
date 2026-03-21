"""Tests for the report_store __init__ module (factory and delegators)."""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from reporting.services import report_store
from reporting.services.report_store.dynamodb import DynamoDBReportStore
from reporting.services.report_store.sql import SQLModelReportStore


@pytest.fixture(autouse=True)
def reset_store():
    """Reset the module-level store singleton between tests."""
    original = report_store._store
    report_store._store = None
    yield
    report_store._store = original


# ---------------------------------------------------------------------------
# get_store factory
# ---------------------------------------------------------------------------


def test_get_store_dynamodb_default(mocker):
    mocker.patch("reporting.settings.REPORT_STORE_BACKEND", "dynamodb")
    store = report_store.get_store()
    assert isinstance(store, DynamoDBReportStore)


def test_get_store_sqlmodel(mocker):
    mocker.patch("reporting.settings.REPORT_STORE_BACKEND", "sqlmodel")
    store = report_store.get_store()
    assert isinstance(store, SQLModelReportStore)


def test_get_store_unknown_backend_raises(mocker):
    mocker.patch("reporting.settings.REPORT_STORE_BACKEND", "unknown")
    with pytest.raises(ValueError, match="Unknown report store backend"):
        report_store.get_store()


def test_get_store_returns_singleton(mocker):
    mocker.patch("reporting.settings.REPORT_STORE_BACKEND", "dynamodb")
    s1 = report_store.get_store()
    s2 = report_store.get_store()
    assert s1 is s2


# ---------------------------------------------------------------------------
# Module-level delegators
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_store():
    store = MagicMock()
    with patch("reporting.services.report_store.get_store", return_value=store):
        yield store


def test_initialize_delegates(mock_store):
    report_store.initialize()
    mock_store.initialize.assert_called_once()


def test_list_reports_delegates(mock_store):
    mock_store.list_reports.return_value = []
    result = report_store.list_reports()
    mock_store.list_reports.assert_called_once()
    assert result == []


def test_get_report_latest_delegates(mock_store):
    mock_store.get_report_latest.return_value = None
    report_store.get_report_latest("rid1")
    mock_store.get_report_latest.assert_called_once_with("rid1")


def test_get_report_version_delegates(mock_store):
    mock_store.get_report_version.return_value = None
    report_store.get_report_version("rid1", 2)
    mock_store.get_report_version.assert_called_once_with("rid1", 2)


def test_list_report_versions_delegates(mock_store):
    mock_store.list_report_versions.return_value = []
    report_store.list_report_versions("rid1")
    mock_store.list_report_versions.assert_called_once_with("rid1")


def test_create_report_delegates(mock_store):
    report_store.create_report(name="My Report", created_by="u@x.com")
    mock_store.create_report.assert_called_once_with(
        name="My Report", created_by="u@x.com"
    )


def test_save_report_version_delegates(mock_store):
    report_store.save_report_version(
        report_id="rid1", config={}, created_by="u@x.com", comment="v2"
    )
    mock_store.save_report_version.assert_called_once_with(
        report_id="rid1", config={}, created_by="u@x.com", comment="v2"
    )


def test_get_dashboard_report_id_delegates(mock_store):
    mock_store.get_dashboard_report_id.return_value = None
    report_store.get_dashboard_report_id()
    mock_store.get_dashboard_report_id.assert_called_once()


def test_set_dashboard_report_delegates(mock_store):
    mock_store.set_dashboard_report.return_value = True
    report_store.set_dashboard_report("rid1")
    mock_store.set_dashboard_report.assert_called_once_with("rid1")


def test_get_dashboard_report_delegates(mock_store):
    mock_store.get_dashboard_report.return_value = None
    report_store.get_dashboard_report()
    mock_store.get_dashboard_report.assert_called_once()


def test_list_panel_stats_delegates(mock_store):
    mock_store.list_panel_stats.return_value = []
    result = report_store.list_panel_stats()
    mock_store.list_panel_stats.assert_called_once()
    assert result == []
