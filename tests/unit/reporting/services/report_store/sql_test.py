"""Tests for the SQLModel report store backend.

Uses an in-memory SQLite database via StaticPool so all sessions within a test
share the same underlying connection and therefore the same database state.
"""
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine
from sqlmodel import SQLModel

from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.services.report_store import sql as sql_module
from reporting.services.report_store.sql import SQLModelReportStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_snowflake_gen():
    """Reset the module-level snowflake generator between tests."""
    original = sql_module._snowflake_gen
    sql_module._snowflake_gen = None
    yield
    sql_module._snowflake_gen = original


@pytest.fixture()
def test_engine():
    """In-memory SQLite engine shared across all sessions in a test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture()
def store(test_engine):
    with patch(
        "reporting.services.report_store.sql._get_engine", return_value=test_engine
    ):
        yield SQLModelReportStore()


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


def test_initialize_creates_tables(mocker):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    mocker.patch("reporting.services.report_store.sql._get_engine", return_value=engine)
    s = SQLModelReportStore()
    s.initialize()
    table_names = engine.dialect.get_table_names(engine.connect())
    assert "report_versions" in table_names
    assert "dashboard_pointer" in table_names
    assert "reports" in table_names


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


def test_list_reports_empty(store):
    assert store.list_reports() == []


def test_list_reports_returns_created_reports(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(
        config={"name": "My Report", "rows": []},
        created_by="user@example.com",
    )
    result = store.list_reports()
    assert len(result) == 1
    assert isinstance(result[0], ReportListItem)
    assert result[0].report_id == "rid1"
    assert result[0].name == "My Report"
    assert result[0].current_version == 1


# ---------------------------------------------------------------------------
# get_report_latest
# ---------------------------------------------------------------------------


def test_get_report_latest_not_found(store):
    assert store.get_report_latest("missing") is None


def test_get_report_latest_returns_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(
        config={"name": "r1", "rows": [{"name": "r1"}]},
        created_by="user@example.com",
        comment="v1",
    )
    result = store.get_report_latest("rid1")
    assert isinstance(result, ReportVersion)
    assert result.report_id == "rid1"
    assert result.version == 1
    assert result.config == {"name": "r1", "rows": [{"name": "r1"}]}
    assert result.created_by == "user@example.com"
    assert result.comment == "v1"


def test_get_report_latest_returns_newest_after_update(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "r", "v": 1}, created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 2}, created_by="u@x.com"
    )
    result = store.get_report_latest("rid1")
    assert result.version == 2
    assert result.config == {"name": "r", "v": 2}


# ---------------------------------------------------------------------------
# get_report_version
# ---------------------------------------------------------------------------


def test_get_report_version_not_found(store):
    assert store.get_report_version("missing", 1) is None


def test_get_report_version_found(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "r", "v": 1}, created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 2}, created_by="u@x.com"
    )

    v1 = store.get_report_version("rid1", 1)
    v2 = store.get_report_version("rid1", 2)
    assert v1.version == 1
    assert v1.config == {"name": "r", "v": 1}
    assert v2.version == 2
    assert v2.config == {"name": "r", "v": 2}


# ---------------------------------------------------------------------------
# list_report_versions
# ---------------------------------------------------------------------------


def test_list_report_versions_empty(store):
    assert store.list_report_versions("missing") == []


def test_list_report_versions_newest_first(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "r", "v": 1}, created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 2}, created_by="u@x.com"
    )
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 3}, created_by="u@x.com"
    )

    versions = store.list_report_versions("rid1")
    assert len(versions) == 3
    assert versions[0].version == 3
    assert versions[1].version == 2
    assert versions[2].version == 1


# ---------------------------------------------------------------------------
# create_report
# ---------------------------------------------------------------------------


def test_create_report_returns_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="snowflake42",
    )
    result = store.create_report(
        config={"name": "My Report", "rows": []},
        created_by="creator@example.com",
        comment="first",
    )
    assert isinstance(result, ReportVersion)
    assert result.report_id == "snowflake42"
    assert result.version == 1
    assert result.config == {"name": "My Report", "rows": []}
    assert result.created_by == "creator@example.com"
    assert result.comment == "first"


# ---------------------------------------------------------------------------
# save_report_version
# ---------------------------------------------------------------------------


def test_save_report_version_returns_none_for_missing_report(store):
    result = store.save_report_version(
        report_id="nonexistent", config={}, created_by="u@x.com"
    )
    assert result is None


def test_save_report_version_increments_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "r", "v": 1}, created_by="u@x.com")
    result = store.save_report_version(
        report_id="rid1",
        config={"name": "r updated", "v": 2},
        created_by="editor@example.com",
        comment="update",
    )
    assert result.version == 2
    assert result.config == {"name": "r updated", "v": 2}
    assert result.comment == "update"


def test_save_report_version_updates_name_in_record(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "Original Name"}, created_by="u@x.com")
    store.save_report_version(
        report_id="rid1",
        config={"name": "Updated Name"},
        created_by="u@x.com",
    )
    result = store.list_reports()
    assert result[0].name == "Updated Name"
    assert result[0].current_version == 2


def test_save_report_version_latest_reflects_new_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(config={"name": "r"}, created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 2}, created_by="u@x.com"
    )
    store.save_report_version(
        report_id="rid1", config={"name": "r", "v": 3}, created_by="u@x.com"
    )

    latest = store.get_report_latest("rid1")
    assert latest.version == 3


# ---------------------------------------------------------------------------
# get/set dashboard
# ---------------------------------------------------------------------------


def test_get_dashboard_report_id_none_when_not_set(store):
    assert store.get_dashboard_report_id() is None


def test_get_dashboard_report_none_when_not_set(store):
    assert store.get_dashboard_report() is None


def test_set_dashboard_report_false_for_missing_report(store):
    assert store.set_dashboard_report("nonexistent") is False


def test_set_and_get_dashboard_report(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(
        config={"name": "My Report", "rows": []},
        created_by="u@x.com",
    )
    ok = store.set_dashboard_report("rid1")
    assert ok is True
    assert store.get_dashboard_report_id() == "rid1"

    report = store.get_dashboard_report()
    assert isinstance(report, ReportVersion)
    assert report.report_id == "rid1"
    assert report.version == 1


def test_set_dashboard_report_can_be_changed(store, mocker):
    ids = iter(["rid1", "rid2"])
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        side_effect=lambda: next(ids),
    )
    store.create_report(config={"name": "r1"}, created_by="u@x.com")
    store.create_report(config={"name": "r2"}, created_by="u@x.com")
    store.set_dashboard_report("rid1")
    store.set_dashboard_report("rid2")
    assert store.get_dashboard_report_id() == "rid2"
