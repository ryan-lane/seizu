from decimal import Decimal
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.services.report_store import dynamodb as dynamodb_module
from reporting.services.report_store.dynamodb import DynamoDBReportStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_snowflake_gen():
    """Reset the module-level snowflake generator between tests."""
    original = dynamodb_module._snowflake_gen
    dynamodb_module._snowflake_gen = None
    yield
    dynamodb_module._snowflake_gen = original


@pytest.fixture()
def mock_table():
    return MagicMock()


@pytest.fixture()
def patch_table(mock_table):
    with patch(
        "reporting.services.report_store.dynamodb._get_table",
        return_value=mock_table,
    ):
        yield mock_table


@pytest.fixture()
def store():
    return DynamoDBReportStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _version_item(report_id="123", version=1):
    return {
        "PK": f"REPORT#{report_id}",
        "SK": f"VERSION#{version:010d}",  # noqa: E231
        "report_id": report_id,
        "name": "My Report",
        "version": version,
        "config": {"rows": []},
        "created_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "comment": None,
    }


def _latest_item(report_id="123", version=1):
    return {
        "PK": f"REPORT#{report_id}",
        "SK": "#LATEST",
        "report_id": report_id,
        "name": "My Report",
        "version": version,
        "config": {"rows": []},
        "created_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "comment": None,
    }


def _metadata_item(report_id="123", current_version=1):
    return {
        "PK": f"REPORT#{report_id}",
        "SK": "#METADATA",
        "report_id": report_id,
        "name": "My Report",
        "current_version": current_version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


async def test_list_reports_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [
            {
                "PK": "REPORT_LIST",
                "SK": "REPORT#123",
                "report_id": "123",
                "name": "My Report",
                "current_version": 1,
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    result = await store.list_reports()
    assert len(result) == 1
    assert isinstance(result[0], ReportListItem)
    assert result[0].report_id == "123"
    assert result[0].name == "My Report"
    assert result[0].current_version == 1


async def test_list_reports_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_reports()
    assert result == []


async def test_list_reports_coerces_decimal(patch_table, store):
    patch_table.query.return_value = {
        "Items": [
            {
                "PK": "REPORT_LIST",
                "SK": "REPORT#123",
                "report_id": "123",
                "name": "My Report",
                "current_version": Decimal("3"),
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    result = await store.list_reports()
    assert result[0].current_version == 3
    assert isinstance(result[0].current_version, int)


# ---------------------------------------------------------------------------
# get_report_latest
# ---------------------------------------------------------------------------


async def test_get_report_latest_found(patch_table, store):
    patch_table.get_item.return_value = {"Item": _version_item()}
    result = await store.get_report_latest("123")
    assert isinstance(result, ReportVersion)
    assert result.version == 1


async def test_get_report_latest_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_report_latest("missing")
    assert result is None


async def test_get_report_latest_queries_correct_sk(patch_table, store):
    patch_table.get_item.return_value = {}
    await store.get_report_latest("abc")
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "REPORT#abc", "SK": "#LATEST"}
    )


# ---------------------------------------------------------------------------
# get_report_version
# ---------------------------------------------------------------------------


async def test_get_report_version_found(patch_table, store):
    patch_table.get_item.return_value = {"Item": _version_item(version=2)}
    result = await store.get_report_version("123", 2)
    assert isinstance(result, ReportVersion)
    assert result.version == 2


async def test_get_report_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_report_version("123", 99)
    assert result is None


async def test_get_report_version_uses_zero_padded_sk(patch_table, store):
    patch_table.get_item.return_value = {}
    await store.get_report_version("abc", 5)
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "REPORT#abc", "SK": "VERSION#0000000005"}
    )


# ---------------------------------------------------------------------------
# list_report_versions
# ---------------------------------------------------------------------------


async def test_list_report_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [_version_item(version=2), _version_item(version=1)]
    }
    result = await store.list_report_versions("123")
    assert len(result) == 2
    assert result[0].version == 2
    assert result[1].version == 1


async def test_list_report_versions_scan_index_forward_false(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    await store.list_report_versions("abc")
    call_kwargs = patch_table.query.call_args[1]
    assert call_kwargs.get("ScanIndexForward") is False


# ---------------------------------------------------------------------------
# create_report
# ---------------------------------------------------------------------------


async def test_create_report_returns_list_item(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="snowflake123",
    )
    result = await store.create_report(
        name="My Report",
        created_by="user@example.com",
    )

    assert isinstance(result, ReportListItem)
    assert result.report_id == "snowflake123"
    assert result.name == "My Report"
    assert result.current_version == 0


async def test_create_report_writes_two_items_transactionally(
    patch_table, store, mocker
):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    await store.create_report(name="My Report", created_by="u@x.com")

    patch_table.meta.client.transact_write_items.assert_called_once()
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    assert len(items) == 2


async def test_create_report_correct_sks(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    await store.create_report(name="My Report", created_by="u@x.com")

    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    sks = [i["Put"]["Item"]["SK"] for i in items]
    assert "#METADATA" in sks
    # list item SK is the report_id prefixed with REPORT#
    pks = [i["Put"]["Item"]["PK"] for i in items]
    assert "REPORT_LIST" in pks


# ---------------------------------------------------------------------------
# save_report_version
# ---------------------------------------------------------------------------


async def test_save_report_version_returns_none_when_report_missing(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.save_report_version(
        report_id="missing",
        config={},
        created_by="u@x.com",
    )
    assert result is None


async def test_save_report_version_increments_version(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=3)}

    result = await store.save_report_version(
        report_id="123",
        config={"rows": [{"name": "new"}]},
        created_by="editor@example.com",
        comment="v4",
    )

    assert result.version == 4
    assert result.name == "My Report"
    assert result.config == {"rows": [{"name": "new"}]}
    assert result.comment == "v4"


async def test_save_report_version_writes_five_items_transactionally(
    patch_table, store
):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=1)}

    await store.save_report_version(report_id="123", config={}, created_by="u@x.com")

    patch_table.meta.client.transact_write_items.assert_called_once()
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    # version, latest, metadata, list, panel_stats = 5 items
    assert len(items) == 5
    patch_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# _floats_to_decimal helper
# ---------------------------------------------------------------------------


def test_floats_to_decimal_converts_float():
    result = dynamodb_module._floats_to_decimal({"size": 2.0, "threshold": 0.5})
    assert result == {"size": Decimal("2.0"), "threshold": Decimal("0.5")}
    assert isinstance(result["size"], Decimal)


def test_floats_to_decimal_handles_nested():
    result = dynamodb_module._floats_to_decimal(
        {"rows": [{"size": 12.0, "nested": {"value": 1.5}}]}
    )
    assert result["rows"][0]["size"] == Decimal("12.0")
    assert result["rows"][0]["nested"]["value"] == Decimal("1.5")


def test_floats_to_decimal_leaves_non_floats_unchanged():
    result = dynamodb_module._floats_to_decimal(
        {"name": "CVEs", "version": 1, "enabled": True, "comment": None}
    )
    assert result == {"name": "CVEs", "version": 1, "enabled": True, "comment": None}


async def test_save_report_version_converts_floats_in_config(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=0)}
    await store.save_report_version(
        report_id="123", config={"rows": [{"size": 2.0}]}, created_by="u@x.com"
    )

    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    version_item = next(
        i for i in items if i["Put"]["Item"]["SK"] == "VERSION#0000000001"
    )
    # _floats_to_decimal converts 2.0 → Decimal("2.0") so that the resource
    # layer's TypeSerializer produces a valid N attribute (float is rejected).
    size = version_item["Put"]["Item"]["config"]["rows"][0]["size"]
    assert size == Decimal("2.0")


# ---------------------------------------------------------------------------
# _version_sk helper
# ---------------------------------------------------------------------------


def test_version_sk_zero_pads():
    assert dynamodb_module._version_sk(1) == "VERSION#0000000001"
    assert dynamodb_module._version_sk(999) == "VERSION#0000000999"
    assert dynamodb_module._version_sk(1_000_000_000) == "VERSION#1000000000"


# ---------------------------------------------------------------------------
# initialize (create_table_if_not_exists)
# ---------------------------------------------------------------------------


async def test_initialize_skips_when_table_present(store, mocker):
    mock_resource = MagicMock()
    mock_table = MagicMock()
    mock_table.name = "seizu-reports"
    mock_resource.tables.all.return_value = [mock_table]
    mocker.patch(
        "reporting.services.report_store.dynamodb.get_boto_resource",
        return_value=mock_resource,
    )
    mocker.patch("reporting.settings.DYNAMODB_TABLE_NAME", "seizu-reports")

    await store.initialize()

    mock_resource.create_table.assert_not_called()


async def test_initialize_creates_when_missing(store, mocker):
    mock_resource = MagicMock()
    mock_resource.tables.all.return_value = []
    mocker.patch(
        "reporting.services.report_store.dynamodb.get_boto_resource",
        return_value=mock_resource,
    )
    mocker.patch("reporting.settings.DYNAMODB_TABLE_NAME", "seizu-reports")

    await store.initialize()

    mock_resource.create_table.assert_called_once()
    kwargs = mock_resource.create_table.call_args[1]
    assert kwargs["TableName"] == "seizu-reports"
    assert kwargs["BillingMode"] == "PAY_PER_REQUEST"


async def test_initialize_handles_race_condition(store, mocker):
    mock_resource = MagicMock()
    mock_resource.tables.all.return_value = []
    mock_resource.create_table.side_effect = (
        mock_resource.meta.client.exceptions.ResourceInUseException(
            {"Error": {"Code": "ResourceInUseException", "Message": ""}},
            "CreateTable",
        )
    )
    mocker.patch(
        "reporting.services.report_store.dynamodb.get_boto_resource",
        return_value=mock_resource,
    )
    mocker.patch("reporting.settings.DYNAMODB_TABLE_NAME", "seizu-reports")

    # Should not raise
    await store.initialize()


# ---------------------------------------------------------------------------
# _strip_none helper
# ---------------------------------------------------------------------------


def test_strip_none_removes_top_level_none():
    result = dynamodb_module._strip_none({"a": 1, "b": None, "c": "x"})
    assert result == {"a": 1, "c": "x"}


def test_strip_none_removes_nested_none_in_dict():
    result = dynamodb_module._strip_none({"a": {"b": None, "c": "x"}})
    assert result == {"a": {"c": "x"}}


def test_strip_none_removes_none_in_list():
    result = dynamodb_module._strip_none({"a": [None, "x", None]})
    assert result == {"a": ["x"]}


def test_strip_none_removes_deeply_nested_none():
    result = dynamodb_module._strip_none(
        {
            "rows": [
                {
                    "panels": [
                        {
                            "size": Decimal("2.0"),
                            "threshold": None,
                            "caption": None,
                        }
                    ]
                }
            ]
        }
    )
    assert result == {"rows": [{"panels": [{"size": Decimal("2.0")}]}]}


def test_strip_none_leaves_falsy_non_none_values():
    result = dynamodb_module._strip_none({"a": 0, "b": "", "c": False, "d": []})
    assert result == {"a": 0, "b": "", "c": False, "d": []}


# ---------------------------------------------------------------------------
# _strip_none — no None values after stripping (regression: model_dump() Nones)
# ---------------------------------------------------------------------------


def _contains_none(obj) -> bool:
    """Recursively check if any value in a plain Python dict/list is None."""
    if isinstance(obj, dict):
        return any(v is None or _contains_none(v) for v in obj.values())
    if isinstance(obj, list):
        return any(item is None or _contains_none(item) for item in obj)
    return False


def test_strip_none_removes_nested_nones_from_config():
    item = {
        "PK": "REPORT#123",
        "config": {
            "name": "My Report",
            "rows": [
                {
                    "name": "row1",
                    "panels": [
                        {
                            "type": "count",
                            "size": Decimal("2.4"),
                            "threshold": None,
                            "caption": None,
                            "bar_settings": None,
                        }
                    ],
                }
            ],
        },
    }
    result = dynamodb_module._strip_none(item)
    panel = result["config"]["rows"][0]["panels"][0]
    assert "threshold" not in panel
    assert "caption" not in panel
    assert "bar_settings" not in panel
    assert panel["size"] == Decimal("2.4")


# ---------------------------------------------------------------------------
# get_dashboard_report_id
# ---------------------------------------------------------------------------


async def test_get_dashboard_report_id_returns_none_when_not_set(patch_table, store):
    patch_table.get_item.return_value = {}
    assert await store.get_dashboard_report_id() is None


async def test_get_dashboard_report_id_returns_report_id(patch_table, store):
    patch_table.get_item.return_value = {
        "Item": {"PK": "#DASHBOARD", "SK": "#POINTER", "report_id": "abc123"}
    }
    assert await store.get_dashboard_report_id() == "abc123"


async def test_get_dashboard_report_id_queries_correct_key(patch_table, store):
    patch_table.get_item.return_value = {}
    await store.get_dashboard_report_id()
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "#DASHBOARD", "SK": "#POINTER"}
    )


# ---------------------------------------------------------------------------
# set_dashboard_report
# ---------------------------------------------------------------------------


async def test_set_dashboard_report_returns_false_when_report_missing(
    patch_table, store
):
    patch_table.get_item.return_value = {}
    assert await store.set_dashboard_report("nonexistent") is False


async def test_set_dashboard_report_returns_true_when_report_exists(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item()}
    assert await store.set_dashboard_report("123") is True


async def test_set_dashboard_report_writes_pointer_item(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(report_id="rid1")}
    await store.set_dashboard_report("rid1")
    patch_table.put_item.assert_called_once()
    item = patch_table.put_item.call_args[1]["Item"]
    assert item["report_id"] == "rid1"
    assert item["PK"] == "#DASHBOARD"
    assert item["SK"] == "#POINTER"


# ---------------------------------------------------------------------------
# get_dashboard_report
# ---------------------------------------------------------------------------


async def test_get_dashboard_report_returns_none_when_not_set(patch_table, store):
    patch_table.get_item.return_value = {}
    assert await store.get_dashboard_report() is None


async def test_get_dashboard_report_returns_report_version(patch_table, store):
    patch_table.get_item.side_effect = [
        {"Item": {"PK": "#DASHBOARD", "SK": "#POINTER", "report_id": "123"}},
        {"Item": _version_item(report_id="123")},
    ]
    result = await store.get_dashboard_report()
    assert isinstance(result, ReportVersion)
    assert result.report_id == "123"


# ---------------------------------------------------------------------------
# save_report_version — correct sort keys
# ---------------------------------------------------------------------------


async def test_save_report_version_correct_sks(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=2)}
    await store.save_report_version(report_id="123", config={}, created_by="u@x.com")
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    sks = [i["Put"]["Item"]["SK"] for i in items]
    assert "#LATEST" in sks
    assert "VERSION#0000000003" in sks
    assert "REPORT#123" in sks
    assert "#METADATA" in sks


# ---------------------------------------------------------------------------
# create_report — config with nested Nones (model_dump()-style)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# delete_report
# ---------------------------------------------------------------------------


async def test_delete_report_returns_false_when_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    assert await store.delete_report("missing") is False


async def test_delete_report_returns_true_on_success(patch_table, store):
    patch_table.get_item.side_effect = [
        {"Item": _metadata_item()},  # metadata check
        {},  # dashboard pointer check — not set
    ]
    patch_table.query.return_value = {
        "Items": [
            {"PK": "REPORT#123", "SK": "#METADATA"},
            {"PK": "REPORT#123", "SK": "#LATEST"},
            {"PK": "REPORT#123", "SK": "VERSION#0000000001"},
        ]
    }
    assert await store.delete_report("123") is True


async def test_delete_report_clears_dashboard_pointer(patch_table, store):
    patch_table.get_item.side_effect = [
        {"Item": _metadata_item()},  # metadata check
        {"Item": {"PK": "#DASHBOARD", "SK": "#POINTER", "report_id": "123"}},
    ]
    patch_table.query.return_value = {
        "Items": [{"PK": "REPORT#123", "SK": "#METADATA"}]
    }
    await store.delete_report("123")
    # batch_writer context manager calls delete_item; verify it was called
    batch = patch_table.batch_writer.return_value.__enter__.return_value
    deleted_keys = [call[1]["Key"] for call in batch.delete_item.call_args_list]
    assert {"PK": "#DASHBOARD", "SK": "#POINTER"} in deleted_keys


async def test_save_report_version_nested_none_config_produces_no_nones(
    patch_table, store
):
    """Config from Pydantic model_dump() may contain nested None values for
    optional fields; verify _strip_none removes them before they reach DynamoDB
    (which would convert None to {"NULL": True}, rejected by DynamoDB Local)."""
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=0)}
    config = {
        "inputs": [],
        "rows": [
            {
                "name": "row1",
                "panels": [
                    {
                        "type": "count",
                        "cypher": "cves-total",
                        "details_cypher": None,
                        "params": [
                            {
                                "name": "base_severity",
                                "input_id": None,
                                "value": "CRITICAL",
                            }
                        ],
                        "caption": "Total CVEs",
                        "table_id": None,
                        "markdown": None,
                        "size": 2.4,
                        "threshold": None,
                        "bar_settings": None,
                        "pie_settings": None,
                        "metric": "cve.count",
                    }
                ],
            }
        ],
    }
    await store.save_report_version(
        report_id="123", config=config, created_by="u@x.com"
    )
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    for item_op in items:
        assert not _contains_none(item_op["Put"]["Item"])


# ---------------------------------------------------------------------------
# get_or_create_user
# ---------------------------------------------------------------------------


def _user_profile_item(user_id="uid1"):
    return {
        "PK": f"USER#{user_id}",
        "SK": "#METADATA",
        "user_id": user_id,
        "sub": "sub123",
        "iss": "https://idp.example.com",
        "email": "alice@example.com",
        "display_name": "Alice",
        "created_at": "2024-01-01T00:00:00+00:00",
        "last_login": "2024-01-01T00:00:00+00:00",
    }


async def test_get_or_create_user_creates_new_user(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="uid1",
    )
    # Lookup returns nothing (new user)
    patch_table.get_item.return_value = {}

    from reporting.schema.report_config import User

    user = await store.get_or_create_user(
        sub="sub123",
        iss="https://idp.example.com",
        email="alice@example.com",
        display_name="Alice",
    )
    assert isinstance(user, User)
    assert user.user_id == "uid1"
    assert user.sub == "sub123"
    assert user.email == "alice@example.com"


async def test_get_or_create_user_creates_lookup_and_profile_items(
    patch_table, store, mocker
):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="uid1",
    )
    patch_table.get_item.return_value = {}

    await store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )

    # put_item called twice: once for lookup (conditional), once for profile
    assert patch_table.put_item.call_count == 2
    call_items = [c[1]["Item"] for c in patch_table.put_item.call_args_list]
    pks = {item["PK"] for item in call_items}
    assert "USER_LOOKUP" in pks
    assert "USER#uid1" in pks


async def test_get_or_create_user_returns_existing_user_on_lookup_hit(
    patch_table, store
):
    lookup_item = {
        "PK": "USER_LOOKUP",
        "SK": "https://idp.example.com#sub123",
        "user_id": "uid1",
    }
    profile_item = {
        "PK": "USER#uid1",
        "SK": "#METADATA",
        "user_id": "uid1",
        "sub": "sub123",
        "iss": "https://idp.example.com",
        "email": "alice@example.com",
        "created_at": "2024-01-01T00:00:00+00:00",
        "last_login": "2024-01-01T00:00:00+00:00",
    }
    # First call: lookup hit; second call: profile fetch
    patch_table.get_item.side_effect = [
        {"Item": lookup_item},
        {"Item": profile_item},
    ]

    from reporting.schema.report_config import User

    user = await store.get_or_create_user(
        sub="sub123", iss="https://idp.example.com", email="alice@example.com"
    )
    assert isinstance(user, User)
    assert user.user_id == "uid1"
    patch_table.put_item.assert_not_called()
    patch_table.update_item.assert_not_called()


# ---------------------------------------------------------------------------
# get_user
# ---------------------------------------------------------------------------


async def test_get_user_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    assert await store.get_user("nonexistent") is None


async def test_get_user_returns_user(patch_table, store):
    patch_table.get_item.return_value = {"Item": _user_profile_item()}
    from reporting.schema.report_config import User

    user = await store.get_user("uid1")
    assert isinstance(user, User)
    assert user.user_id == "uid1"
    assert user.email == "alice@example.com"


# ---------------------------------------------------------------------------
# archive_user
# ---------------------------------------------------------------------------


async def test_archive_user_returns_false_when_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    assert await store.archive_user("nonexistent") is False


async def test_archive_user_updates_archived_at(patch_table, store):
    patch_table.get_item.return_value = {"Item": _user_profile_item()}
    result = await store.archive_user("uid1")
    assert result is True
    patch_table.update_item.assert_called_once()
    kwargs = patch_table.update_item.call_args[1]
    assert kwargs["Key"] == {"PK": "USER#uid1", "SK": "#METADATA"}
    assert "archived_at" in kwargs["UpdateExpression"]


# ---------------------------------------------------------------------------
# list_panel_stats
# ---------------------------------------------------------------------------


async def test_list_panel_stats_returns_empty_when_none(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_panel_stats()
    assert result == []


async def test_list_panel_stats_returns_stat_records(patch_table, store):
    patch_table.query.return_value = {
        "Items": [
            {
                "PK": "PANEL_STATS",
                "SK": "REPORT#rid1",
                "report_id": "rid1",
                "stats": [
                    {
                        "metric": "cve.count",
                        "panel_type": "count",
                        "cypher": "MATCH (c:CVE) RETURN count(c.id) AS total",
                        "static_params": {"severity": "CRITICAL"},
                    }
                ],
            }
        ]
    }
    result = await store.list_panel_stats()
    assert len(result) == 1
    assert isinstance(result[0], PanelStat)
    assert result[0].report_id == "rid1"
    assert result[0].metric == "cve.count"
    assert result[0].panel_type == "count"
    assert result[0].static_params == {"severity": "CRITICAL"}
    assert result[0].input_param_name is None


async def test_list_panel_stats_queries_correct_pk(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    await store.list_panel_stats()
    call_kwargs = patch_table.query.call_args[1]
    assert call_kwargs["ExpressionAttributeValues"][":pk"] == "PANEL_STATS"


async def test_save_report_version_writes_panel_stats(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=0)}
    config = {
        "name": "Test",
        "queries": {"cves-total": "MATCH (c:CVE) RETURN count(c.id) AS total"},
        "inputs": [],
        "rows": [
            {
                "name": "row",
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
    await store.save_report_version(
        report_id="123", config=config, created_by="u@x.com"
    )
    # Stats are written as part of the transact_write, not via batch_writer
    patch_table.batch_writer.assert_not_called()
    transact_call = patch_table.meta.client.transact_write_items.call_args
    items = transact_call[1]["TransactItems"]
    # version, latest, metadata, list, stats = 5 items
    assert len(items) == 5
    stats_put = next(
        i["Put"] for i in items if i["Put"]["Item"].get("PK") == "PANEL_STATS"
    )
    assert stats_put["Item"]["SK"] == "REPORT#123"
    stats_list = stats_put["Item"]["stats"]
    assert len(stats_list) == 1
    assert stats_list[0]["metric"] == "cve.count"
    assert stats_list[0]["panel_type"] == "count"


# ---------------------------------------------------------------------------
# Scheduled queries
# ---------------------------------------------------------------------------


def _sq_metadata_item(sq_id="sq1", current_version=1):
    return {
        "PK": f"SQ#{sq_id}",
        "SK": "#METADATA",
        "scheduled_query_id": sq_id,
        "name": "My Query",
        "cypher": "MATCH (n) RETURN n",
        "params": [],
        "frequency": 60,
        "watch_scans": [],
        "enabled": True,
        "actions": [{"action_type": "log", "action_config": {}}],
        "current_version": current_version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "updated_by": "user@example.com",
    }


def _sq_version_dynamo_item(sq_id="sq1", version=1):
    return {
        "PK": f"SQ#{sq_id}",
        "SK": f"VERSION#{version:010d}",  # noqa: E231
        "scheduled_query_id": sq_id,
        "name": "My Query",
        "version": version,
        "cypher": "MATCH (n) RETURN n",
        "params": [],
        "frequency": 60,
        "watch_scans": [],
        "enabled": True,
        "actions": [{"action_type": "log", "action_config": {}}],
        "created_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "comment": None,
    }


_SQ_KWARGS = dict(
    name="My Query",
    cypher="MATCH (n) RETURN n",
    params=[],
    frequency=60,
    watch_scans=[],
    enabled=True,
    actions=[{"action_type": "log", "action_config": {}}],
    created_by="user@example.com",
)


async def test_list_scheduled_queries_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_scheduled_queries()
    assert result == []


async def test_list_scheduled_queries_returns_items(patch_table, store):
    patch_table.query.return_value = {"Items": [_sq_metadata_item()]}
    result = await store.list_scheduled_queries()
    assert len(result) == 1
    assert result[0].scheduled_query_id == "sq1"
    assert result[0].name == "My Query"
    assert result[0].current_version == 1


async def test_get_scheduled_query_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _sq_metadata_item()}
    result = await store.get_scheduled_query("sq1")
    assert result is not None
    assert result.scheduled_query_id == "sq1"
    assert result.name == "My Query"


async def test_get_scheduled_query_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_scheduled_query("nonexistent")
    assert result is None


async def test_create_scheduled_query(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="sq1",
    )
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.create_scheduled_query(**_SQ_KWARGS)
    assert result.scheduled_query_id == "sq1"
    assert result.current_version == 1
    assert result.created_by == "user@example.com"
    assert result.updated_by == "user@example.com"
    assert patch_table.meta.client.transact_write_items.call_count == 1


async def test_update_scheduled_query_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _sq_metadata_item(current_version=1)}
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.update_scheduled_query(
        sq_id="sq1",
        name="Updated",
        cypher="MATCH (n) RETURN n LIMIT 1",
        params=[],
        frequency=120,
        watch_scans=[],
        enabled=False,
        actions=[],
        updated_by="editor@example.com",
        comment="v2",
    )
    assert result is not None
    assert result.current_version == 2
    assert result.updated_by == "editor@example.com"


async def test_update_scheduled_query_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.update_scheduled_query(
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


async def test_list_scheduled_query_versions_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_scheduled_query_versions("sq1")
    assert result == []


async def test_list_scheduled_query_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [
            _sq_version_dynamo_item(version=2),
            _sq_version_dynamo_item(version=1),
        ]
    }
    result = await store.list_scheduled_query_versions("sq1")
    assert len(result) == 2
    assert result[0].version == 2
    assert result[1].version == 1


async def test_get_scheduled_query_version_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _sq_version_dynamo_item(version=1)}
    result = await store.get_scheduled_query_version("sq1", 1)
    assert result is not None
    assert result.version == 1
    assert result.scheduled_query_id == "sq1"


async def test_get_scheduled_query_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_scheduled_query_version("sq1", 99)
    assert result is None


async def test_delete_scheduled_query_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _sq_metadata_item()}
    patch_table.query.return_value = {
        "Items": [
            {"PK": "SQ#sq1", "SK": "#METADATA"},
            {"PK": "SQ#sq1", "SK": "VERSION#0000000001"},
        ]
    }
    batch_mock = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
    result = await store.delete_scheduled_query("sq1")
    assert result is True
    assert batch_mock.delete_item.call_count == 3  # 2 items + 1 list item


async def test_delete_scheduled_query_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.delete_scheduled_query("nonexistent")
    assert result is False


async def test_acquire_scheduled_query_lock_no_previous(patch_table, store):
    """Lock acquired when no previous last_scheduled_at exists."""
    patch_table.update_item.return_value = {}
    result = await store.acquire_scheduled_query_lock("sq1", None)
    assert result is True
    assert patch_table.update_item.call_count == 2


async def test_acquire_scheduled_query_lock_with_expected(patch_table, store):
    """Lock acquired when last_scheduled_at matches expected."""
    patch_table.update_item.return_value = {}
    result = await store.acquire_scheduled_query_lock(
        "sq1", "2024-01-01T00:00:00+00:00"
    )
    assert result is True
    assert patch_table.update_item.call_count == 2


async def test_acquire_scheduled_query_lock_race(patch_table, store):
    """Lock not acquired when condition check fails (another worker won)."""
    import botocore.exceptions

    err = botocore.exceptions.ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}},
        "UpdateItem",
    )
    patch_table.update_item.side_effect = err
    result = await store.acquire_scheduled_query_lock("sq1", None)
    assert result is False


async def test_record_scheduled_query_result_success(patch_table, store):
    """Success result clears last_errors."""
    patch_table.get_item.return_value = {
        "Item": {
            **_sq_metadata_item(),
            "last_errors": [{"timestamp": "t", "error": "e"}],
        }
    }
    await store.record_scheduled_query_result("sq1", "success")
    assert patch_table.update_item.call_count == 2
    call_kwargs = patch_table.update_item.call_args_list[0][1]
    assert call_kwargs["ExpressionAttributeValues"][":errors"] == []


async def test_record_scheduled_query_result_failure(patch_table, store):
    """Failure result prepends error to last_errors, capped at 5."""
    existing = [{"timestamp": f"t{i}", "error": f"e{i}"} for i in range(5)]
    patch_table.get_item.return_value = {
        "Item": {**_sq_metadata_item(), "last_errors": existing}
    }
    await store.record_scheduled_query_result("sq1", "failure", error="new error")
    call_kwargs = patch_table.update_item.call_args_list[0][1]
    errors = call_kwargs["ExpressionAttributeValues"][":errors"]
    assert len(errors) == 5
    assert errors[0]["error"] == "new error"


async def test_record_scheduled_query_result_not_found(patch_table, store):
    """Missing item is handled gracefully without update calls."""
    patch_table.get_item.return_value = {}
    await store.record_scheduled_query_result("nonexistent", "success")
    assert patch_table.update_item.call_count == 0


# ---------------------------------------------------------------------------
# Toolsets
# ---------------------------------------------------------------------------


def _ts_metadata_item(ts_id="ts1", current_version=1):
    return {
        "PK": f"TOOLSET#{ts_id}",
        "SK": "#METADATA",
        "toolset_id": ts_id,
        "name": "My Toolset",
        "description": "A toolset",
        "enabled": True,
        "current_version": current_version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "updated_by": "user@example.com",
    }


def _ts_version_item(ts_id="ts1", version=1):
    return {
        "PK": f"TOOLSET#{ts_id}",
        "SK": f"VERSION#{version:010d}",  # noqa: E231
        "toolset_id": ts_id,
        "name": "My Toolset",
        "description": "A toolset",
        "enabled": True,
        "version": version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "comment": None,
    }


async def test_list_toolsets_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_toolsets()
    assert result == []


async def test_list_toolsets_returns_items(patch_table, store):
    patch_table.query.return_value = {"Items": [_ts_metadata_item()]}
    result = await store.list_toolsets()
    assert len(result) == 1
    assert result[0].toolset_id == "ts1"
    assert result[0].name == "My Toolset"


async def test_get_toolset_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _ts_metadata_item()}
    result = await store.get_toolset("ts1")
    assert result is not None
    assert result.toolset_id == "ts1"


async def test_get_toolset_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_toolset("nonexistent")
    assert result is None


async def test_create_toolset(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="ts1",
    )
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.create_toolset(
        name="My Toolset",
        description="desc",
        enabled=True,
        created_by="user@example.com",
    )
    assert result.toolset_id == "ts1"
    assert result.current_version == 1
    assert result.created_by == "user@example.com"
    assert patch_table.meta.client.transact_write_items.call_count == 1


async def test_update_toolset_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _ts_metadata_item(current_version=1)}
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.update_toolset(
        toolset_id="ts1",
        name="Updated",
        description="new desc",
        enabled=False,
        updated_by="editor@example.com",
        comment="v2",
    )
    assert result is not None
    assert result.current_version == 2
    assert result.updated_by == "editor@example.com"


async def test_update_toolset_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.update_toolset(
        toolset_id="nonexistent",
        name="X",
        description="",
        enabled=True,
        updated_by="u@x.com",
    )
    assert result is None


async def test_delete_toolset_success(patch_table, store):
    def _query_side_effect(**kwargs):
        pk = kwargs["ExpressionAttributeValues"][":pk"]
        if pk == "TOOLSET#ts1":
            return {
                "Items": [
                    {"PK": "TOOLSET#ts1", "SK": "#METADATA"},
                    {"PK": "TOOLSET#ts1", "SK": "VERSION#0000000001"},
                ]
            }
        if pk == "TOOL_LIST#ts1":
            return {"Items": []}
        return {"Items": []}

    patch_table.get_item.return_value = {"Item": _ts_metadata_item()}
    patch_table.query.side_effect = _query_side_effect
    batch_mock = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
    result = await store.delete_toolset("ts1")
    assert result is True


async def test_delete_toolset_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.delete_toolset("nonexistent")
    assert result is False


async def test_list_toolset_versions_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_toolset_versions("ts1")
    assert result == []


async def test_list_toolset_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [_ts_version_item(version=2), _ts_version_item(version=1)]
    }
    result = await store.list_toolset_versions("ts1")
    assert len(result) == 2
    assert result[0].version == 2


async def test_get_toolset_version_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _ts_version_item(version=1)}
    result = await store.get_toolset_version("ts1", 1)
    assert result is not None
    assert result.version == 1


async def test_get_toolset_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_toolset_version("ts1", 99)
    assert result is None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _tool_metadata_item(tool_id="t1", toolset_id="ts1", current_version=1):
    return {
        "PK": f"TOOL#{tool_id}",
        "SK": "#METADATA",
        "tool_id": tool_id,
        "toolset_id": toolset_id,
        "name": "My Tool",
        "description": "A tool",
        "cypher": "MATCH (n) RETURN n LIMIT 1",
        "parameters": [],
        "enabled": True,
        "current_version": current_version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "updated_by": "user@example.com",
    }


def _tool_version_dynamo_item(tool_id="t1", toolset_id="ts1", version=1):
    return {
        "PK": f"TOOL#{tool_id}",
        "SK": f"VERSION#{version:010d}",  # noqa: E231
        "tool_id": tool_id,
        "toolset_id": toolset_id,
        "name": "My Tool",
        "description": "A tool",
        "cypher": "MATCH (n) RETURN n LIMIT 1",
        "parameters": [],
        "enabled": True,
        "version": version,
        "created_at": "2024-01-01T00:00:00+00:00",
        "created_by": "user@example.com",
        "comment": None,
    }


async def test_list_tools_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_tools("ts1")
    assert result == []


async def test_list_tools_returns_items(patch_table, store):
    def _query_side_effect(**kwargs):
        pk = kwargs["ExpressionAttributeValues"][":pk"]
        if pk == "TOOL_LIST#ts1":
            return {"Items": [{"SK": "TOOL#t1"}]}
        return {"Items": []}

    patch_table.query.side_effect = _query_side_effect
    patch_table.get_item.return_value = {"Item": _tool_metadata_item()}
    result = await store.list_tools("ts1")
    assert len(result) == 1
    assert result[0].tool_id == "t1"


async def test_get_tool_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _tool_metadata_item()}
    result = await store.get_tool("t1")
    assert result is not None
    assert result.tool_id == "t1"


async def test_get_tool_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_tool("nonexistent")
    assert result is None


async def test_create_tool_success(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="t1",
    )
    patch_table.get_item.return_value = {"Item": _ts_metadata_item()}
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.create_tool(
        toolset_id="ts1",
        name="My Tool",
        description="desc",
        cypher="MATCH (n) RETURN n",
        parameters=[],
        enabled=True,
        created_by="user@example.com",
    )
    assert result is not None
    assert result.tool_id == "t1"
    assert result.current_version == 1
    assert patch_table.meta.client.transact_write_items.call_count == 1


async def test_create_tool_toolset_not_found(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="t1",
    )
    patch_table.get_item.return_value = {}
    result = await store.create_tool(
        toolset_id="nonexistent",
        name="My Tool",
        description="",
        cypher="MATCH (n) RETURN n",
        parameters=[],
        enabled=True,
        created_by="user@example.com",
    )
    assert result is None


async def test_update_tool_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _tool_metadata_item(current_version=1)}
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.update_tool(
        tool_id="t1",
        name="Updated",
        description="new desc",
        cypher="MATCH (n) RETURN n LIMIT 5",
        parameters=[],
        enabled=False,
        updated_by="editor@example.com",
        comment="v2",
    )
    assert result is not None
    assert result.current_version == 2
    assert result.updated_by == "editor@example.com"


async def test_update_tool_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.update_tool(
        tool_id="nonexistent",
        name="X",
        description="",
        cypher="MATCH (n) RETURN n",
        parameters=[],
        enabled=True,
        updated_by="u@x.com",
    )
    assert result is None


async def test_delete_tool_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _tool_metadata_item()}
    patch_table.query.return_value = {
        "Items": [
            {"PK": "TOOL#t1", "SK": "#METADATA"},
            {"PK": "TOOL#t1", "SK": "VERSION#0000000001"},
        ]
    }
    batch_mock = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
    result = await store.delete_tool("t1")
    assert result is True
    # 2 tool items + 1 list item
    assert batch_mock.delete_item.call_count == 3


async def test_delete_tool_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.delete_tool("nonexistent")
    assert result is False


async def test_list_tool_versions_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_tool_versions("t1")
    assert result == []


async def test_list_tool_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [
            _tool_version_dynamo_item(version=2),
            _tool_version_dynamo_item(version=1),
        ]
    }
    result = await store.list_tool_versions("t1")
    assert len(result) == 2
    assert result[0].version == 2


async def test_get_tool_version_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _tool_version_dynamo_item(version=1)}
    result = await store.get_tool_version("t1", 1)
    assert result is not None
    assert result.version == 1
    assert result.tool_id == "t1"


async def test_get_tool_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_tool_version("t1", 99)
    assert result is None


async def test_list_enabled_tools_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_enabled_tools()
    assert result == []


async def test_list_enabled_tools_skips_disabled_toolset(patch_table, store):
    def _query_side_effect(**kwargs):
        pk = kwargs["ExpressionAttributeValues"][":pk"]
        if pk == "TOOLSET_LIST":
            return {
                "Items": [
                    {**_ts_metadata_item(), "enabled": False},
                ]
            }
        return {"Items": []}

    patch_table.query.side_effect = _query_side_effect
    result = await store.list_enabled_tools()
    assert result == []


async def test_list_enabled_tools_returns_enabled_tools(patch_table, store):
    tool_list_item = {
        **_tool_metadata_item(),
        "PK": "TOOL_LIST#ts1",
        "SK": "TOOL#t1",
        "enabled": True,
    }
    call_count = 0

    def _query_side_effect(**kwargs):
        nonlocal call_count
        pk = kwargs["ExpressionAttributeValues"][":pk"]
        call_count += 1
        if pk == "TOOLSET_LIST":
            return {"Items": [_ts_metadata_item()]}
        if pk == "TOOL_LIST#ts1":
            return {"Items": [tool_list_item]}
        return {"Items": []}

    patch_table.query.side_effect = _query_side_effect
    patch_table.get_item.return_value = {"Item": _tool_metadata_item()}
    result = await store.list_enabled_tools()
    assert len(result) == 1
    assert result[0].tool_id == "t1"


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------

_NOW = "2024-01-01T00:00:00+00:00"


def _role_metadata_item(role_id="r1", current_version=1):
    return {
        "PK": f"ROLE#{role_id}",
        "SK": "#METADATA",
        "role_id": role_id,
        "name": "Custom Role",
        "description": "A test role",
        "permissions": ["reports:read", "query:execute"],
        "current_version": current_version,
        "created_at": _NOW,
        "updated_at": _NOW,
        "created_by": "uid1",
        "updated_by": "uid1",
    }


def _role_version_item(role_id="r1", version=1):
    return {
        "PK": f"ROLE#{role_id}",
        "SK": f"VERSION#{version:010d}",  # noqa: E231
        "role_id": role_id,
        "name": "Custom Role",
        "description": "A test role",
        "permissions": ["reports:read"],
        "version": version,
        "created_at": _NOW,
        "created_by": "uid1",
    }


async def test_list_roles_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_roles()
    assert result == []


async def test_list_roles_returns_items(patch_table, store):
    patch_table.query.return_value = {"Items": [_role_metadata_item()]}
    result = await store.list_roles()
    assert len(result) == 1
    assert result[0].role_id == "r1"
    assert result[0].name == "Custom Role"


async def test_get_role_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _role_metadata_item()}
    result = await store.get_role("r1")
    assert result is not None
    assert result.role_id == "r1"


async def test_get_role_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_role("nonexistent")
    assert result is None


async def test_get_role_by_name_found(patch_table, store):
    patch_table.query.return_value = {"Items": [_role_metadata_item()]}
    result = await store.get_role_by_name("Custom Role")
    assert result is not None
    assert result.name == "Custom Role"


async def test_get_role_by_name_not_found(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.get_role_by_name("nonexistent")
    assert result is None


async def test_create_role(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="r1",
    )
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.create_role(
        name="Custom Role",
        description="A test role",
        permissions=["reports:read"],
        created_by="uid1",
    )
    assert result.role_id == "r1"
    assert result.name == "Custom Role"
    assert result.current_version == 1
    assert result.created_by == "uid1"
    assert patch_table.meta.client.transact_write_items.call_count == 1


async def test_update_role_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _role_metadata_item(current_version=1)}
    patch_table.meta.client.transact_write_items = MagicMock()
    result = await store.update_role(
        role_id="r1",
        name="Updated Role",
        description="new desc",
        permissions=["reports:read", "reports:write"],
        updated_by="uid2",
        comment="v2",
    )
    assert result is not None
    assert result.name == "Updated Role"
    assert result.current_version == 2
    assert result.updated_by == "uid2"


async def test_update_role_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.update_role(
        role_id="nonexistent",
        name="X",
        description="",
        permissions=[],
        updated_by="u",
    )
    assert result is None


async def test_delete_role_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _role_metadata_item()}
    patch_table.query.return_value = {
        "Items": [
            {"PK": "ROLE#r1", "SK": "#METADATA"},
            {"PK": "ROLE#r1", "SK": "VERSION#0000000001"},
        ]
    }
    batch_mock = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=batch_mock)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)
    result = await store.delete_role("r1")
    assert result is True


async def test_delete_role_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.delete_role("nonexistent")
    assert result is False


async def test_list_role_versions_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = await store.list_role_versions("r1")
    assert result == []


async def test_list_role_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [_role_version_item(version=2), _role_version_item(version=1)]
    }
    result = await store.list_role_versions("r1")
    assert len(result) == 2
    assert result[0].version == 2


async def test_get_role_version_success(patch_table, store):
    patch_table.get_item.return_value = {"Item": _role_version_item(version=1)}
    result = await store.get_role_version("r1", 1)
    assert result is not None
    assert result.version == 1


async def test_get_role_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = await store.get_role_version("r1", 99)
    assert result is None
