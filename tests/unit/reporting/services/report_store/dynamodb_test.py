from decimal import Decimal
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

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


def test_list_reports_returns_items(patch_table, store):
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
    result = store.list_reports()
    assert len(result) == 1
    assert isinstance(result[0], ReportListItem)
    assert result[0].report_id == "123"
    assert result[0].name == "My Report"
    assert result[0].current_version == 1


def test_list_reports_empty(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    result = store.list_reports()
    assert result == []


def test_list_reports_coerces_decimal(patch_table, store):
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
    result = store.list_reports()
    assert result[0].current_version == 3
    assert isinstance(result[0].current_version, int)


# ---------------------------------------------------------------------------
# get_report_latest
# ---------------------------------------------------------------------------


def test_get_report_latest_found(patch_table, store):
    patch_table.get_item.return_value = {"Item": _version_item()}
    result = store.get_report_latest("123")
    assert isinstance(result, ReportVersion)
    assert result.version == 1


def test_get_report_latest_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = store.get_report_latest("missing")
    assert result is None


def test_get_report_latest_queries_correct_sk(patch_table, store):
    patch_table.get_item.return_value = {}
    store.get_report_latest("abc")
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "REPORT#abc", "SK": "#LATEST"}
    )


# ---------------------------------------------------------------------------
# get_report_version
# ---------------------------------------------------------------------------


def test_get_report_version_found(patch_table, store):
    patch_table.get_item.return_value = {"Item": _version_item(version=2)}
    result = store.get_report_version("123", 2)
    assert isinstance(result, ReportVersion)
    assert result.version == 2


def test_get_report_version_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = store.get_report_version("123", 99)
    assert result is None


def test_get_report_version_uses_zero_padded_sk(patch_table, store):
    patch_table.get_item.return_value = {}
    store.get_report_version("abc", 5)
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "REPORT#abc", "SK": "VERSION#0000000005"}
    )


# ---------------------------------------------------------------------------
# list_report_versions
# ---------------------------------------------------------------------------


def test_list_report_versions_returns_items(patch_table, store):
    patch_table.query.return_value = {
        "Items": [_version_item(version=2), _version_item(version=1)]
    }
    result = store.list_report_versions("123")
    assert len(result) == 2
    assert result[0].version == 2
    assert result[1].version == 1


def test_list_report_versions_scan_index_forward_false(patch_table, store):
    patch_table.query.return_value = {"Items": []}
    store.list_report_versions("abc")
    call_kwargs = patch_table.query.call_args[1]
    assert call_kwargs.get("ScanIndexForward") is False


# ---------------------------------------------------------------------------
# create_report
# ---------------------------------------------------------------------------


def test_create_report_returns_list_item(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="snowflake123",
    )
    result = store.create_report(
        name="My Report",
        created_by="user@example.com",
    )

    assert isinstance(result, ReportListItem)
    assert result.report_id == "snowflake123"
    assert result.name == "My Report"
    assert result.current_version == 0


def test_create_report_writes_two_items_transactionally(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    store.create_report(name="My Report", created_by="u@x.com")

    patch_table.meta.client.transact_write_items.assert_called_once()
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    assert len(items) == 2


def test_create_report_correct_sks(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    store.create_report(name="My Report", created_by="u@x.com")

    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    sks = [i["Put"]["Item"]["SK"] for i in items]
    assert "#METADATA" in sks
    # list item SK is the report_id prefixed with REPORT#
    pks = [i["Put"]["Item"]["PK"] for i in items]
    assert "REPORT_LIST" in pks


# ---------------------------------------------------------------------------
# save_report_version
# ---------------------------------------------------------------------------


def test_save_report_version_returns_none_when_report_missing(patch_table, store):
    patch_table.get_item.return_value = {}
    result = store.save_report_version(
        report_id="missing",
        config={},
        created_by="u@x.com",
    )
    assert result is None


def test_save_report_version_increments_version(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=3)}

    result = store.save_report_version(
        report_id="123",
        config={"rows": [{"name": "new"}]},
        created_by="editor@example.com",
        comment="v4",
    )

    assert result.version == 4
    assert result.name == "My Report"
    assert result.config == {"rows": [{"name": "new"}]}
    assert result.comment == "v4"


def test_save_report_version_writes_four_items_transactionally(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=1)}

    store.save_report_version(report_id="123", config={}, created_by="u@x.com")

    patch_table.meta.client.transact_write_items.assert_called_once()
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    assert len(items) == 4
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


def test_save_report_version_converts_floats_in_config(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=0)}
    store.save_report_version(
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


def test_initialize_skips_when_table_present(store, mocker):
    mock_resource = MagicMock()
    mock_table = MagicMock()
    mock_table.name = "seizu-reports"
    mock_resource.tables.all.return_value = [mock_table]
    mocker.patch(
        "reporting.services.report_store.dynamodb.get_boto_resource",
        return_value=mock_resource,
    )
    mocker.patch("reporting.settings.DYNAMODB_TABLE_NAME", "seizu-reports")

    store.initialize()

    mock_resource.create_table.assert_not_called()


def test_initialize_creates_when_missing(store, mocker):
    mock_resource = MagicMock()
    mock_resource.tables.all.return_value = []
    mocker.patch(
        "reporting.services.report_store.dynamodb.get_boto_resource",
        return_value=mock_resource,
    )
    mocker.patch("reporting.settings.DYNAMODB_TABLE_NAME", "seizu-reports")

    store.initialize()

    mock_resource.create_table.assert_called_once()
    kwargs = mock_resource.create_table.call_args[1]
    assert kwargs["TableName"] == "seizu-reports"
    assert kwargs["BillingMode"] == "PAY_PER_REQUEST"


def test_initialize_handles_race_condition(store, mocker):
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
    store.initialize()


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


def test_get_dashboard_report_id_returns_none_when_not_set(patch_table, store):
    patch_table.get_item.return_value = {}
    assert store.get_dashboard_report_id() is None


def test_get_dashboard_report_id_returns_report_id(patch_table, store):
    patch_table.get_item.return_value = {
        "Item": {"PK": "#DASHBOARD", "SK": "#POINTER", "report_id": "abc123"}
    }
    assert store.get_dashboard_report_id() == "abc123"


def test_get_dashboard_report_id_queries_correct_key(patch_table, store):
    patch_table.get_item.return_value = {}
    store.get_dashboard_report_id()
    patch_table.get_item.assert_called_once_with(
        Key={"PK": "#DASHBOARD", "SK": "#POINTER"}
    )


# ---------------------------------------------------------------------------
# set_dashboard_report
# ---------------------------------------------------------------------------


def test_set_dashboard_report_returns_false_when_report_missing(patch_table, store):
    patch_table.get_item.return_value = {}
    assert store.set_dashboard_report("nonexistent") is False


def test_set_dashboard_report_returns_true_when_report_exists(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item()}
    assert store.set_dashboard_report("123") is True


def test_set_dashboard_report_writes_pointer_item(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(report_id="rid1")}
    store.set_dashboard_report("rid1")
    patch_table.put_item.assert_called_once()
    item = patch_table.put_item.call_args[1]["Item"]
    assert item["report_id"] == "rid1"
    assert item["PK"] == "#DASHBOARD"
    assert item["SK"] == "#POINTER"


# ---------------------------------------------------------------------------
# get_dashboard_report
# ---------------------------------------------------------------------------


def test_get_dashboard_report_returns_none_when_not_set(patch_table, store):
    patch_table.get_item.return_value = {}
    assert store.get_dashboard_report() is None


def test_get_dashboard_report_returns_report_version(patch_table, store):
    patch_table.get_item.side_effect = [
        {"Item": {"PK": "#DASHBOARD", "SK": "#POINTER", "report_id": "123"}},
        {"Item": _version_item(report_id="123")},
    ]
    result = store.get_dashboard_report()
    assert isinstance(result, ReportVersion)
    assert result.report_id == "123"


# ---------------------------------------------------------------------------
# save_report_version — correct sort keys
# ---------------------------------------------------------------------------


def test_save_report_version_correct_sks(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=2)}
    store.save_report_version(report_id="123", config={}, created_by="u@x.com")
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    sks = [i["Put"]["Item"]["SK"] for i in items]
    assert "#LATEST" in sks
    assert "VERSION#0000000003" in sks
    assert "REPORT#123" in sks
    assert "#METADATA" in sks


# ---------------------------------------------------------------------------
# create_report — config with nested Nones (model_dump()-style)
# ---------------------------------------------------------------------------


def test_save_report_version_nested_none_config_produces_no_nones(patch_table, store):
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
    store.save_report_version(report_id="123", config=config, created_by="u@x.com")
    items = patch_table.meta.client.transact_write_items.call_args[1]["TransactItems"]
    for item_op in items:
        assert not _contains_none(item_op["Put"]["Item"])
