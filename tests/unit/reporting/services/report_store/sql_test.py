"""Tests for the SQLModel report store backend.

Uses an in-memory SQLite database via StaticPool so all sessions within a test
share the same underlying connection and therefore the same database state.
"""
from unittest.mock import patch

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine
from sqlmodel import SQLModel

from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import User
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
    assert "users" in table_names
    assert "panel_stats" in table_names


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
    store.create_report(name="My Report", created_by="user@example.com")
    result = store.list_reports()
    assert len(result) == 1
    assert isinstance(result[0], ReportListItem)
    assert result[0].report_id == "rid1"
    assert result[0].name == "My Report"
    assert result[0].current_version == 0


# ---------------------------------------------------------------------------
# get_report_latest
# ---------------------------------------------------------------------------


def test_get_report_latest_not_found(store):
    assert store.get_report_latest("missing") is None


def test_get_report_latest_not_found_for_empty_report(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r1", created_by="user@example.com")
    assert store.get_report_latest("rid1") is None


def test_get_report_latest_returns_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r1", created_by="user@example.com")
    store.save_report_version(
        report_id="rid1",
        config={"rows": [{"name": "r1"}]},
        created_by="user@example.com",
        comment="v1",
    )
    result = store.get_report_latest("rid1")
    assert isinstance(result, ReportVersion)
    assert result.report_id == "rid1"
    assert result.name == "r1"
    assert result.version == 1
    assert result.config == {"rows": [{"name": "r1"}]}
    assert result.created_by == "user@example.com"
    assert result.comment == "v1"


def test_get_report_latest_returns_newest_after_update(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 1}, created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 2}, created_by="u@x.com")
    result = store.get_report_latest("rid1")
    assert result.version == 2
    assert result.config == {"v": 2}


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
    store.create_report(name="r", created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 1}, created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 2}, created_by="u@x.com")

    v1 = store.get_report_version("rid1", 1)
    v2 = store.get_report_version("rid1", 2)
    assert v1.version == 1
    assert v1.name == "r"
    assert v1.config == {"v": 1}
    assert v2.version == 2
    assert v2.config == {"v": 2}


# ---------------------------------------------------------------------------
# list_report_versions
# ---------------------------------------------------------------------------


def test_list_report_versions_empty(store):
    assert store.list_report_versions("missing") == []


def test_list_report_versions_empty_for_report_with_no_versions(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    assert store.list_report_versions("rid1") == []


def test_list_report_versions_newest_first(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 1}, created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 2}, created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 3}, created_by="u@x.com")

    versions = store.list_report_versions("rid1")
    assert len(versions) == 3
    assert versions[0].version == 3
    assert versions[1].version == 2
    assert versions[2].version == 1


# ---------------------------------------------------------------------------
# create_report
# ---------------------------------------------------------------------------


def test_create_report_returns_list_item(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="snowflake42",
    )
    result = store.create_report(
        name="My Report",
        created_by="creator@example.com",
    )
    assert isinstance(result, ReportListItem)
    assert result.report_id == "snowflake42"
    assert result.name == "My Report"
    assert result.current_version == 0


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
    store.create_report(name="r", created_by="u@x.com")
    result = store.save_report_version(
        report_id="rid1",
        config={"v": 2},
        created_by="editor@example.com",
        comment="update",
    )
    assert result.version == 1
    assert result.name == "r"
    assert result.config == {"v": 2}
    assert result.comment == "update"


def test_save_report_version_does_not_change_name(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="Original Name", created_by="u@x.com")
    store.save_report_version(
        report_id="rid1",
        config={"rows": []},
        created_by="u@x.com",
    )
    result = store.list_reports()
    assert result[0].name == "Original Name"
    assert result[0].current_version == 1


def test_save_report_version_latest_reflects_new_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 1}, created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 2}, created_by="u@x.com")

    latest = store.get_report_latest("rid1")
    assert latest.version == 2


# ---------------------------------------------------------------------------
# get/set dashboard
# ---------------------------------------------------------------------------


def test_get_dashboard_report_id_none_when_not_set(store):
    assert store.get_dashboard_report_id() is None


def test_get_dashboard_report_none_when_not_set(store):
    assert store.get_dashboard_report() is None


def test_set_dashboard_report_false_for_missing_report(store):
    assert store.set_dashboard_report("nonexistent") is False


def test_set_dashboard_report_succeeds_for_empty_report(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="My Report", created_by="u@x.com")
    ok = store.set_dashboard_report("rid1")
    assert ok is True
    assert store.get_dashboard_report_id() == "rid1"


def test_set_and_get_dashboard_report(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="My Report", created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config={"rows": []}, created_by="u@x.com"
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
    store.create_report(name="r1", created_by="u@x.com")
    store.create_report(name="r2", created_by="u@x.com")
    store.set_dashboard_report("rid1")
    store.set_dashboard_report("rid2")
    assert store.get_dashboard_report_id() == "rid2"


# ---------------------------------------------------------------------------
# delete_report
# ---------------------------------------------------------------------------


def test_delete_report_returns_false_for_missing_report(store):
    assert store.delete_report("nonexistent") is False


def test_delete_report_removes_report(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    store.save_report_version(report_id="rid1", config={"v": 1}, created_by="u@x.com")
    assert store.delete_report("rid1") is True
    assert store.list_reports() == []
    assert store.list_report_versions("rid1") == []


def test_delete_report_clears_dashboard_pointer(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="r", created_by="u@x.com")
    store.set_dashboard_report("rid1")
    assert store.get_dashboard_report_id() == "rid1"
    store.delete_report("rid1")
    assert store.get_dashboard_report_id() is None


def test_delete_report_does_not_clear_other_dashboard_pointer(store, mocker):
    ids = iter(["rid1", "rid2"])
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        side_effect=lambda: next(ids),
    )
    store.create_report(name="r1", created_by="u@x.com")
    store.create_report(name="r2", created_by="u@x.com")
    store.set_dashboard_report("rid2")
    store.delete_report("rid1")
    assert store.get_dashboard_report_id() == "rid2"


# ---------------------------------------------------------------------------
# get_or_create_user
# ---------------------------------------------------------------------------


def test_get_or_create_user_creates_new_user(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    user = store.get_or_create_user(
        sub="sub123",
        iss="https://idp.example.com",
        email="alice@example.com",
        display_name="Alice",
    )
    assert isinstance(user, User)
    assert user.user_id == "uid1"
    assert user.sub == "sub123"
    assert user.iss == "https://idp.example.com"
    assert user.email == "alice@example.com"
    assert user.display_name == "Alice"
    assert user.archived_at is None


def test_get_or_create_user_returns_existing_user(store, mocker):
    ids = iter(["uid1", "uid2"])
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        side_effect=lambda: next(ids),
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    # Second call with same (iss, sub) must not create a new user
    user = store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    assert user.user_id == "uid1"


def test_get_or_create_user_returns_existing_without_update(store, mocker):
    """Subsequent calls with a changed email must not update the stored record."""
    ids = iter(["uid1", "uid2"])
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        side_effect=lambda: next(ids),
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="old@example.com"
    )
    user = store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="new@example.com"
    )
    assert user.email == "old@example.com"


# ---------------------------------------------------------------------------
# update_user_profile
# ---------------------------------------------------------------------------


def test_update_user_profile_updates_email_when_changed(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="old@example.com"
    )
    user = store.update_user_profile(user_id="uid1", email="new@example.com")
    assert user.email == "new@example.com"


def test_update_user_profile_no_write_when_nothing_changed(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    user = store.update_user_profile(user_id="uid1", email="alice@example.com")
    assert user.email == "alice@example.com"


def test_update_user_profile_updates_last_login_when_iat_is_newer(store, mocker):
    from datetime import datetime, timezone

    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    # Use future dates so both are guaranteed newer than the creation-time `now`
    first_iat = datetime(2030, 1, 1, tzinfo=timezone.utc)
    second_iat = datetime(2030, 6, 1, tzinfo=timezone.utc)
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    store.update_user_profile(
        user_id="uid1", email="alice@example.com", token_iat=first_iat
    )
    user = store.update_user_profile(
        user_id="uid1", email="alice@example.com", token_iat=second_iat
    )
    assert user.last_login == second_iat.isoformat()


def test_update_user_profile_does_not_update_last_login_when_iat_is_older(
    store, mocker
):
    from datetime import datetime, timezone

    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    # Use future dates so both are newer than creation-time `now`
    newer_iat = datetime(2030, 6, 1, tzinfo=timezone.utc)
    older_iat = datetime(2030, 1, 1, tzinfo=timezone.utc)
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    store.update_user_profile(
        user_id="uid1", email="alice@example.com", token_iat=newer_iat
    )
    user = store.update_user_profile(
        user_id="uid1", email="alice@example.com", token_iat=older_iat
    )
    assert user.last_login == newer_iat.isoformat()


def test_get_or_create_user_different_sub_creates_separate_users(store, mocker):
    ids = iter(["uid1", "uid2"])
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        side_effect=lambda: next(ids),
    )
    u1 = store.get_or_create_user(
        sub="sub-alice", iss="https://idp.example.com", email="shared@example.com"
    )
    u2 = store.get_or_create_user(
        sub="sub-bob", iss="https://idp.example.com", email="shared@example.com"
    )
    assert u1.user_id != u2.user_id


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------


def test_get_user_not_found(store):
    assert store.get_user("nonexistent") is None


def test_get_user_returns_created_user(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    user = store.get_user("uid1")
    assert isinstance(user, User)
    assert user.user_id == "uid1"
    assert user.email == "alice@example.com"


# ---------------------------------------------------------------------------
# archive_user
# ---------------------------------------------------------------------------


def test_archive_user_returns_false_for_missing(store):
    assert store.archive_user("nonexistent") is False


def test_archive_user_sets_archived_at(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="uid1",
    )
    store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    assert store.archive_user("uid1") is True
    user = store.get_user("uid1")
    assert user.archived_at is not None


# ---------------------------------------------------------------------------
# list_panel_stats
# ---------------------------------------------------------------------------

_STAT_CONFIG = {
    "name": "Test Report",
    "queries": {
        "cves-total": "MATCH (c:CVE) RETURN count(c.id) AS total",
    },
    "inputs": [],
    "rows": [
        {
            "name": "CVEs",
            "panels": [
                {
                    "type": "count",
                    "cypher": "cves-total",
                    "params": [{"name": "severity", "value": "CRITICAL"}],
                    "metric": "cve.count",
                    "size": 3,
                }
            ],
        }
    ],
}


def test_list_panel_stats_empty(store):
    assert store.list_panel_stats() == []


def test_list_panel_stats_populated_on_save_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="Test", created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config=_STAT_CONFIG, created_by="u@x.com"
    )
    stats = store.list_panel_stats()
    assert len(stats) == 1
    assert isinstance(stats[0], PanelStat)
    assert stats[0].report_id == "rid1"
    assert stats[0].metric == "cve.count"
    assert stats[0].panel_type == "count"
    assert stats[0].static_params == {"severity": "CRITICAL"}
    assert stats[0].input_param_name is None


def test_list_panel_stats_replaced_on_new_version(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="Test", created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config=_STAT_CONFIG, created_by="u@x.com"
    )
    # Save a version with no stat panels — stats should be cleared
    store.save_report_version(
        report_id="rid1", config={"name": "Test", "rows": []}, created_by="u@x.com"
    )
    assert store.list_panel_stats() == []


def test_list_panel_stats_cleared_on_delete(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="rid1",
    )
    store.create_report(name="Test", created_by="u@x.com")
    store.save_report_version(
        report_id="rid1", config=_STAT_CONFIG, created_by="u@x.com"
    )
    assert len(store.list_panel_stats()) == 1
    store.delete_report("rid1")
    assert store.list_panel_stats() == []


# ---------------------------------------------------------------------------
# Scheduled queries
# ---------------------------------------------------------------------------

_SQ_KWARGS = dict(
    name="Test Query",
    cypher="MATCH (n) RETURN n",
    params=[],
    frequency=60,
    watch_scans=[],
    enabled=True,
    actions=[{"action_type": "log", "action_config": {}}],
    created_by="user@example.com",
)


def test_list_scheduled_queries_empty(store):
    assert store.list_scheduled_queries() == []


def test_create_scheduled_query(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    result = store.create_scheduled_query(**_SQ_KWARGS)
    assert result.scheduled_query_id == "sq1"
    assert result.name == "Test Query"
    assert result.current_version == 1
    assert result.created_by == "user@example.com"
    assert result.updated_by == "user@example.com"


def test_list_scheduled_queries_returns_created(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    items = store.list_scheduled_queries()
    assert len(items) == 1
    assert items[0].scheduled_query_id == "sq1"


def test_get_scheduled_query_success(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    item = store.get_scheduled_query("sq1")
    assert item is not None
    assert item.name == "Test Query"
    assert item.current_version == 1


def test_get_scheduled_query_not_found(store):
    assert store.get_scheduled_query("nonexistent") is None


def test_update_scheduled_query_success(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    result = store.update_scheduled_query(
        sq_id="sq1",
        name="Updated Query",
        cypher="MATCH (n) RETURN n LIMIT 1",
        params=[],
        frequency=120,
        watch_scans=[],
        enabled=False,
        actions=[],
        updated_by="editor@example.com",
        comment="Updated for testing",
    )
    assert result is not None
    assert result.name == "Updated Query"
    assert result.current_version == 2
    assert result.updated_by == "editor@example.com"
    assert result.created_by == "user@example.com"


def test_update_scheduled_query_not_found(store):
    result = store.update_scheduled_query(
        sq_id="nonexistent",
        name="X",
        cypher="MATCH (n) RETURN n",
        params=[],
        frequency=60,
        watch_scans=[],
        enabled=True,
        actions=[],
        updated_by="u@x.com",
    )
    assert result is None


def test_list_scheduled_query_versions(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    store.update_scheduled_query(
        sq_id="sq1",
        name="Updated",
        cypher="MATCH (n) RETURN n LIMIT 1",
        params=[],
        frequency=60,
        watch_scans=[],
        enabled=True,
        actions=[],
        updated_by="u@x.com",
        comment="v2",
    )
    versions = store.list_scheduled_query_versions("sq1")
    assert len(versions) == 2
    assert versions[0].version == 2  # descending order
    assert versions[1].version == 1


def test_list_scheduled_query_versions_not_found(store):
    assert store.list_scheduled_query_versions("nonexistent") == []


def test_get_scheduled_query_version_success(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    v = store.get_scheduled_query_version("sq1", 1)
    assert v is not None
    assert v.version == 1
    assert v.name == "Test Query"


def test_get_scheduled_query_version_not_found(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    assert store.get_scheduled_query_version("sq1", 99) is None


def test_get_scheduled_query_version_sq_not_found(store):
    assert store.get_scheduled_query_version("nonexistent", 1) is None


def test_delete_scheduled_query_success(store, mocker):
    mocker.patch(
        "reporting.services.report_store.sql.generate_report_id",
        return_value="sq1",
    )
    store.create_scheduled_query(**_SQ_KWARGS)
    assert store.delete_scheduled_query("sq1") is True
    assert store.get_scheduled_query("sq1") is None
    assert store.list_scheduled_query_versions("sq1") == []


def test_delete_scheduled_query_not_found(store):
    assert store.delete_scheduled_query("nonexistent") is False
