import logging
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from boto3.dynamodb.conditions import Key
from snowflake import SnowflakeGenerator

from reporting import settings
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.services import get_boto_resource
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

# Module-level snowflake generator; lazily initialised so the machine ID
# setting is read after the module is imported.
_snowflake_gen: Optional[SnowflakeGenerator] = None

# DynamoDB key constants
_PK_REPORT_LIST = "REPORT_LIST"
# The latest-version pointer uses a '#' prefix so it sorts before all
# "VERSION#…" sort keys and is never returned by begins_with("VERSION#") queries.
_SK_LATEST = "#LATEST"
_SK_METADATA = "#METADATA"
_SK_VERSION_PREFIX = "VERSION#"
# Dashboard pointer — a single item that records which report is the default dashboard.
_PK_DASHBOARD = "#DASHBOARD"
_SK_DASHBOARD_POINTER = "#POINTER"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _get_snowflake_gen() -> SnowflakeGenerator:
    global _snowflake_gen
    if _snowflake_gen is None:
        _snowflake_gen = SnowflakeGenerator(settings.SNOWFLAKE_MACHINE_ID)
    return _snowflake_gen


def _get_table() -> Any:
    endpoint_url = settings.DYNAMODB_ENDPOINT_URL or None
    resource = get_boto_resource(
        "dynamodb",
        region=settings.DYNAMODB_REGION,
        endpoint_url=endpoint_url,
    )
    return resource.Table(settings.DYNAMODB_TABLE_NAME)


def _floats_to_decimal(value: Any) -> Any:
    """Recursively convert float to Decimal for DynamoDB compatibility.

    DynamoDB's boto3 resource rejects Python float values; all numbers must
    be stored as Decimal.  We convert via str() to avoid floating-point
    precision artefacts (e.g. Decimal(str(2.0)) == Decimal('2.0')).
    """
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(v) for v in value]
    return value


def _report_pk(report_id: str) -> str:
    return f"REPORT#{report_id}"


def _version_sk(version: int) -> str:
    """Zero-pad version numbers so lexicographic sort matches numeric sort."""
    return f"{_SK_VERSION_PREFIX}{version:010d}"  # noqa: E231


def generate_report_id() -> str:
    """Return a new unique snowflake ID string."""
    return str(next(_get_snowflake_gen()))


def _strip_none(value: Any) -> Any:
    """Recursively remove None values from dicts and lists.

    DynamoDB Local rejects the NULL type in TransactWriteItems, even when
    nested inside a Map or List attribute.  Omitting None entirely is
    equivalent — a missing attribute reads back as None on deserialisation.
    """
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value if v is not None]
    return value


def _transact_put(table: Any, *items: Dict[str, Any]) -> None:
    """Write one or more items atomically via TransactWriteItems.

    table.meta.client applies its own type serialization (Python → AttributeValue
    wire format), so items must be passed as plain Python dicts — not pre-serialized
    with TypeSerializer.  We only need to strip None values first, because
    boto3/botocore would convert them to {"NULL": True} which DynamoDB Local
    rejects inside TransactWriteItems.
    """
    table.meta.client.transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": settings.DYNAMODB_TABLE_NAME,
                    "Item": _strip_none(item),
                }
            }
            for item in items
        ]
    )


# ---------------------------------------------------------------------------
# DynamoDB backend implementation
# ---------------------------------------------------------------------------


class DynamoDBReportStore(ReportStore):
    """ReportStore implementation backed by Amazon DynamoDB."""

    def initialize(self) -> None:
        """Create the DynamoDB table if it does not already exist.

        Intended for development / local DynamoDB setups; enabled via
        DYNAMODB_CREATE_TABLE=true.
        """
        endpoint_url = settings.DYNAMODB_ENDPOINT_URL or None
        resource = get_boto_resource(
            "dynamodb",
            region=settings.DYNAMODB_REGION,
            endpoint_url=endpoint_url,
        )
        existing_names = [t.name for t in resource.tables.all()]
        if settings.DYNAMODB_TABLE_NAME in existing_names:
            return
        try:
            resource.create_table(
                TableName=settings.DYNAMODB_TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            logger.info(
                "Created DynamoDB table", extra={"table": settings.DYNAMODB_TABLE_NAME}
            )
        except resource.meta.client.exceptions.ResourceInUseException:
            logger.info(
                "DynamoDB table already exists (created by another worker)",
                extra={"table": settings.DYNAMODB_TABLE_NAME},
            )

    def list_reports(self) -> List[ReportListItem]:
        """Return lightweight metadata for all reports."""
        table = _get_table()
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(_PK_REPORT_LIST),
        )
        return [ReportListItem(**item) for item in resp.get("Items", [])]

    def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        """Return the latest version of a report config, or None if not found."""
        table = _get_table()
        resp = table.get_item(
            Key={"PK": _report_pk(report_id), "SK": _SK_LATEST},
        )
        item = resp.get("Item")
        if not item:
            return None
        return ReportVersion(**item)

    def get_report_version(
        self, report_id: str, version: int
    ) -> Optional[ReportVersion]:
        """Return a specific version of a report config, or None if not found."""
        table = _get_table()
        resp = table.get_item(
            Key={"PK": _report_pk(report_id), "SK": _version_sk(version)},
        )
        item = resp.get("Item")
        if not item:
            return None
        return ReportVersion(**item)

    def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        """Return all stored versions for a report, newest first.

        The #LATEST pointer is excluded because its SK starts with '#', not
        'VERSION#', so it is never returned by the begins_with filter.
        """
        table = _get_table()
        resp = table.query(
            KeyConditionExpression=Key("PK").eq(_report_pk(report_id))
            & Key("SK").begins_with(_SK_VERSION_PREFIX),
            ScanIndexForward=False,
        )
        return [ReportVersion(**item) for item in resp.get("Items", [])]

    def create_report(
        self,
        name: str,
        created_by: str,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""
        report_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()

        metadata_item = {
            "PK": _report_pk(report_id),
            "SK": _SK_METADATA,
            "report_id": report_id,
            "name": name,
            "current_version": 0,
            "created_at": now,
            "updated_at": now,
        }
        list_item = {
            "PK": _PK_REPORT_LIST,
            "SK": f"REPORT#{report_id}",
            "report_id": report_id,
            "name": name,
            "current_version": 0,
            "created_at": now,
            "updated_at": now,
        }

        table = _get_table()
        _transact_put(table, metadata_item, list_item)
        return ReportListItem(
            report_id=report_id,
            name=name,
            current_version=0,
            created_at=now,
            updated_at=now,
        )

    def save_report_version(
        self,
        report_id: str,
        config: Dict[str, Any],
        created_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ReportVersion]:
        """Append a new version to an existing report and return it.

        Returns None if the report does not exist.
        """
        table = _get_table()
        resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
        meta = resp.get("Item")
        if not meta:
            return None

        version = int(meta["current_version"]) + 1
        name = meta["name"]
        now = datetime.now(tz=timezone.utc).isoformat()

        version_item = {
            "PK": _report_pk(report_id),
            "SK": _version_sk(version),
            "report_id": report_id,
            "name": name,
            "version": version,
            "config": _floats_to_decimal(config),
            "created_at": now,
            "created_by": created_by,
            "comment": comment,
        }
        latest_item = {**version_item, "SK": _SK_LATEST}
        metadata_item = {
            "PK": _report_pk(report_id),
            "SK": _SK_METADATA,
            "report_id": report_id,
            "name": name,
            "current_version": version,
            "created_at": meta["created_at"],
            "updated_at": now,
        }
        list_item = {
            "PK": _PK_REPORT_LIST,
            "SK": f"REPORT#{report_id}",
            "report_id": report_id,
            "name": name,
            "current_version": version,
            "created_at": meta["created_at"],
            "updated_at": now,
        }

        _transact_put(table, version_item, latest_item, metadata_item, list_item)
        return ReportVersion(**version_item)

    def get_dashboard_report_id(self) -> Optional[str]:
        """Return the report_id of the current dashboard report, or None if not set."""
        table = _get_table()
        resp = table.get_item(Key={"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER})
        item = resp.get("Item")
        if not item:
            return None
        return item.get("report_id")

    def set_dashboard_report(self, report_id: str) -> bool:
        """Point the dashboard pointer at the given report.

        Returns False if the report does not exist.
        """
        table = _get_table()
        resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
        if not resp.get("Item"):
            return False
        table.put_item(
            Item={
                "PK": _PK_DASHBOARD,
                "SK": _SK_DASHBOARD_POINTER,
                "report_id": report_id,
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            }
        )
        return True

    def get_dashboard_report(self) -> Optional[ReportVersion]:
        """Return the latest version of the dashboard report, or None if not set."""
        report_id = self.get_dashboard_report_id()
        if not report_id:
            return None
        return self.get_report_latest(report_id)
