from decimal import Decimal
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportMetadata
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
        "description": "A test report",
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
                "description": "desc",
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
                "description": "",
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
# get_report_metadata
# ---------------------------------------------------------------------------


def test_get_report_metadata_found(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item()}
    result = store.get_report_metadata("123")
    assert isinstance(result, ReportMetadata)
    assert result.report_id == "123"
    assert result.current_version == 1


def test_get_report_metadata_not_found(patch_table, store):
    patch_table.get_item.return_value = {}
    result = store.get_report_metadata("missing")
    assert result is None


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


def test_create_report_returns_version(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="snowflake123",
    )
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    result = store.create_report(
        name="Test",
        description="desc",
        config={"rows": []},
        created_by="user@example.com",
        comment="initial version",
    )

    assert isinstance(result, ReportVersion)
    assert result.report_id == "snowflake123"
    assert result.version == 1
    assert result.config == {"rows": []}
    assert result.created_by == "user@example.com"
    assert result.comment == "initial version"


def test_create_report_writes_four_items(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    store.create_report(name="T", description="", config={}, created_by="u@x.com")

    assert mock_batch.put_item.call_count == 4


def test_create_report_latest_item_has_correct_sk(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    store.create_report(name="T", description="", config={}, created_by="u@x.com")

    put_calls = mock_batch.put_item.call_args_list
    sks = [c[1]["Item"]["SK"] for c in put_calls]
    assert "#LATEST" in sks
    assert "VERSION#0000000001" in sks
    assert "#METADATA" in sks
    assert "REPORT#rid" in sks


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
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    result = store.save_report_version(
        report_id="123",
        config={"rows": [{"name": "new"}]},
        created_by="editor@example.com",
        comment="v4",
    )

    assert result.version == 4
    assert result.config == {"rows": [{"name": "new"}]}
    assert result.comment == "v4"


def test_save_report_version_updates_metadata_and_list(patch_table, store):
    patch_table.get_item.return_value = {"Item": _metadata_item(current_version=1)}
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    store.save_report_version(report_id="123", config={}, created_by="u@x.com")

    assert patch_table.update_item.call_count == 2
    update_keys = [c[1]["Key"]["SK"] for c in patch_table.update_item.call_args_list]
    assert "#METADATA" in update_keys
    assert any("REPORT#123" in k for k in update_keys)


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


def test_create_report_converts_floats_in_config(patch_table, store, mocker):
    mocker.patch(
        "reporting.services.report_store.dynamodb.generate_report_id",
        return_value="rid",
    )
    mock_batch = MagicMock()
    patch_table.batch_writer.return_value.__enter__ = MagicMock(return_value=mock_batch)
    patch_table.batch_writer.return_value.__exit__ = MagicMock(return_value=False)

    store.create_report(
        name="T",
        description="",
        config={"rows": [{"size": 2.0}]},
        created_by="u@x.com",
    )

    put_calls = mock_batch.put_item.call_args_list
    version_call = next(
        c for c in put_calls if c[1]["Item"]["SK"] == "VERSION#0000000001"
    )
    stored_config = version_call[1]["Item"]["config"]
    assert stored_config["rows"][0]["size"] == Decimal("2.0")


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
