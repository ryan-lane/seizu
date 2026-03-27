import asyncio
import logging
from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import boto3
from snowflake import SnowflakeGenerator

from reporting import settings
from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolParamDef
from reporting.schema.mcp_config import ToolsetListItem
from reporting.schema.mcp_config import ToolsetVersion
from reporting.schema.mcp_config import ToolVersion
from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.report_config import ScheduledQueryVersion
from reporting.schema.report_config import User
from reporting.services.report_store.base import extract_panel_stats
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
# User lookup — PK is shared; SK encodes iss + sub for lookup by external identity.
_PK_USER_LOOKUP = "USER_LOOKUP"
# Panel stats — pre-computed stat descriptors; one item per report stored under a
# single shared PK for efficient full listing.  SK encodes report_id so the item
# can be targeted directly for updates and deletes without a query.
_PK_PANEL_STATS = "PANEL_STATS"
# Scheduled queries — list index PK for listing all scheduled queries.
_PK_SCHEDULED_QUERY_LIST = "SCHEDULED_QUERY_LIST"
# Toolsets — list index PK for listing all toolsets.
_PK_TOOLSET_LIST = "TOOLSET_LIST"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _get_snowflake_gen() -> SnowflakeGenerator:
    global _snowflake_gen
    if _snowflake_gen is None:
        _snowflake_gen = SnowflakeGenerator(settings.SNOWFLAKE_MACHINE_ID)
    return _snowflake_gen


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


def _sq_pk(sq_id: str) -> str:
    return f"SQ#{sq_id}"


def _toolset_pk(toolset_id: str) -> str:
    return f"TOOLSET#{toolset_id}"


def _toolset_list_sk(toolset_id: str) -> str:
    return f"TOOLSET#{toolset_id}"


def _tool_pk(tool_id: str) -> str:
    return f"TOOL#{tool_id}"


def _tool_list_pk(toolset_id: str) -> str:
    return f"TOOL_LIST#{toolset_id}"


def _tool_list_sk(tool_id: str) -> str:
    return f"TOOL#{tool_id}"


def _toolset_from_item(item: Dict) -> ToolsetListItem:
    return ToolsetListItem(
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        enabled=item.get("enabled", True),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _toolset_version_from_item(item: Dict) -> ToolsetVersion:
    return ToolsetVersion(
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        enabled=item.get("enabled", True),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _tool_from_item(item: Dict) -> ToolItem:
    return ToolItem(
        tool_id=item["tool_id"],
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        cypher=item["cypher"],
        parameters=[
            ToolParamDef(**p) if isinstance(p, dict) else p
            for p in item.get("parameters", [])
        ],
        enabled=item.get("enabled", True),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _tool_version_from_item(item: Dict) -> ToolVersion:
    return ToolVersion(
        tool_id=item["tool_id"],
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        cypher=item["cypher"],
        parameters=[
            ToolParamDef(**p) if isinstance(p, dict) else p
            for p in item.get("parameters", [])
        ],
        enabled=item.get("enabled", True),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _sq_version_sk(version: int) -> str:
    """Zero-pad version numbers so lexicographic sort matches numeric sort."""
    return f"{_SK_VERSION_PREFIX}{version:010d}"  # noqa: E231


def _sq_from_item(item: Dict) -> ScheduledQueryItem:
    return ScheduledQueryItem(
        scheduled_query_id=item["scheduled_query_id"],
        name=item["name"],
        cypher=item["cypher"],
        params=item.get("params", []),
        frequency=item.get("frequency"),
        watch_scans=item.get("watch_scans", []),
        enabled=item.get("enabled", True),
        actions=item.get("actions", []),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _sq_version_from_item(item: Dict) -> ScheduledQueryVersion:
    return ScheduledQueryVersion(
        scheduled_query_id=item["scheduled_query_id"],
        name=item["name"],
        version=item["version"],
        cypher=item["cypher"],
        params=item.get("params", []),
        frequency=item.get("frequency"),
        watch_scans=item.get("watch_scans", []),
        enabled=item.get("enabled", True),
        actions=item.get("actions", []),
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _user_pk(user_id: str) -> str:
    return f"USER#{user_id}"


def _user_lookup_sk(iss: str, sub: str) -> str:
    return f"{iss}#{sub}"


def _user_from_item(item: Dict) -> User:
    return User(
        user_id=item["user_id"],
        sub=item["sub"],
        iss=item["iss"],
        email=item["email"],
        display_name=item.get("display_name"),
        created_at=item["created_at"],
        last_login=item.get("last_login", item.get("last_seen_at", "")),
        archived_at=item.get("archived_at"),
    )


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


def get_boto_resource() -> Any:
    """Return a sync boto3 DynamoDB service resource."""
    return boto3.resource(
        "dynamodb",
        region_name=settings.DYNAMODB_REGION,
        endpoint_url=settings.DYNAMODB_ENDPOINT_URL or None,
    )


def _get_table() -> Any:
    """Return a sync boto3 DynamoDB Table object."""
    return get_boto_resource().Table(settings.DYNAMODB_TABLE_NAME)


def _transact_put_sync(table: Any, *items: Dict[str, Any]) -> None:
    """Write one or more items atomically via TransactWriteItems."""
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


def _update_user_profile_internal(
    table: Any,
    user_id: str,
    email: str,
    display_name: Optional[str],
    token_iat: Optional[datetime],
) -> User:
    """Apply an email/display_name update and conditionally advance last_login."""
    update_exp = "SET email = :e"
    exp_values: Dict = {":e": email}
    if display_name is not None:
        update_exp += ", display_name = :d"
        exp_values[":d"] = display_name
    if token_iat is not None:
        iat_str = token_iat.isoformat()
        try:
            resp = table.update_item(
                Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
                UpdateExpression=update_exp + ", last_login = :t",
                ConditionExpression="last_login < :t",
                ExpressionAttributeValues={**exp_values, ":t": iat_str},
                ReturnValues="ALL_NEW",
            )
            return _user_from_item(resp["Attributes"])
        except table.meta.client.exceptions.ConditionalCheckFailedException:
            pass  # Token not newer — update email only
    resp = table.update_item(
        Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
        UpdateExpression=update_exp,
        ExpressionAttributeValues=exp_values,
        ReturnValues="ALL_NEW",
    )
    return _user_from_item(resp["Attributes"])


# ---------------------------------------------------------------------------
# DynamoDB backend implementation
# ---------------------------------------------------------------------------


class DynamoDBReportStore(ReportStore):
    """ReportStore implementation backed by Amazon DynamoDB."""

    async def initialize(self) -> None:
        """Create the DynamoDB table if it does not already exist.

        Intended for development / local DynamoDB setups; enabled via
        DYNAMODB_CREATE_TABLE=true.
        """

        def _op() -> None:
            dynamodb = get_boto_resource()
            existing_names = [t.name for t in dynamodb.tables.all()]
            if settings.DYNAMODB_TABLE_NAME in existing_names:
                return
            try:
                dynamodb.create_table(
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
                    "Created DynamoDB table",
                    extra={"table": settings.DYNAMODB_TABLE_NAME},
                )
            except dynamodb.meta.client.exceptions.ResourceInUseException:
                logger.info(
                    "DynamoDB table already exists (created by another worker)",
                    extra={"table": settings.DYNAMODB_TABLE_NAME},
                )

        await asyncio.to_thread(_op)

    async def list_reports(self) -> List[ReportListItem]:
        """Return lightweight metadata for all reports."""

        def _op() -> List[ReportListItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_REPORT_LIST},
            )
            return [ReportListItem(**item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        """Return the latest version of a report config, or None if not found."""

        def _op() -> Optional[ReportVersion]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _report_pk(report_id), "SK": _SK_LATEST},
            )
            item = resp.get("Item")
            if not item:
                return None
            return ReportVersion(**item)

        return await asyncio.to_thread(_op)

    async def get_report_version(
        self, report_id: str, version: int
    ) -> Optional[ReportVersion]:
        """Return a specific version of a report config, or None if not found."""

        def _op() -> Optional[ReportVersion]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _report_pk(report_id), "SK": _version_sk(version)},
            )
            item = resp.get("Item")
            if not item:
                return None
            return ReportVersion(**item)

        return await asyncio.to_thread(_op)

    async def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        """Return all stored versions for a report, newest first."""

        def _op() -> List[ReportVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _report_pk(report_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [ReportVersion(**item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def create_report(
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

        def _op() -> None:
            table = _get_table()
            _transact_put_sync(table, metadata_item, list_item)

        await asyncio.to_thread(_op)
        return ReportListItem(
            report_id=report_id,
            name=name,
            current_version=0,
            created_at=now,
            updated_at=now,
        )

    async def save_report_version(
        self,
        report_id: str,
        config: Dict[str, Any],
        created_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ReportVersion]:
        """Append a new version to an existing report and return it."""

        def _op() -> Optional[ReportVersion]:
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

            stats = extract_panel_stats(report_id, config)
            stats_item = {
                "PK": _PK_PANEL_STATS,
                "SK": f"REPORT#{report_id}",
                "report_id": report_id,
                "stats": [
                    {
                        "metric": s.metric,
                        "panel_type": s.panel_type,
                        "cypher": s.cypher,
                        "static_params": _floats_to_decimal(s.static_params),
                        "input_param_name": s.input_param_name,
                        "input_cypher": s.input_cypher,
                    }
                    for s in stats
                ],
            }
            _transact_put_sync(
                table,
                version_item,
                latest_item,
                metadata_item,
                list_item,
                stats_item,
            )
            return ReportVersion(**version_item)

        return await asyncio.to_thread(_op)

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report and all its versions."""

        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False

            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _report_pk(report_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [
                {"PK": item["PK"], "SK": item["SK"]}
                for item in items_resp.get("Items", [])
            ]
            keys_to_delete.append({"PK": _PK_REPORT_LIST, "SK": f"REPORT#{report_id}"})
            keys_to_delete.append({"PK": _PK_PANEL_STATS, "SK": f"REPORT#{report_id}"})

            dashboard_resp = table.get_item(
                Key={"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER}
            )
            dashboard_item = dashboard_resp.get("Item")
            if dashboard_item and dashboard_item.get("report_id") == report_id:
                keys_to_delete.append(
                    {"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER}
                )

            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)

            return True

        return await asyncio.to_thread(_op)

    async def get_dashboard_report_id(self) -> Optional[str]:
        """Return the report_id of the current dashboard report, or None if not set."""

        def _op() -> Optional[str]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER}
            )
            item = resp.get("Item")
            if not item:
                return None
            return item.get("report_id")

        return await asyncio.to_thread(_op)

    async def set_dashboard_report(self, report_id: str) -> bool:
        """Point the dashboard pointer at the given report."""

        def _op() -> bool:
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

        return await asyncio.to_thread(_op)

    async def get_dashboard_report(self) -> Optional[ReportVersion]:
        """Return the latest version of the dashboard report, or None if not set."""
        report_id = await self.get_dashboard_report_id()
        if not report_id:
            return None
        return await self.get_report_latest(report_id)

    async def list_panel_stats(self) -> List[PanelStat]:
        """Return all PanelStat records across all reports."""

        def _op() -> List[PanelStat]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_PANEL_STATS},
            )
            result = []
            for item in resp.get("Items", []):
                report_id = item["report_id"]
                for stat_data in item.get("stats", []):
                    result.append(
                        PanelStat(
                            report_id=report_id,
                            metric=stat_data["metric"],
                            panel_type=stat_data["panel_type"],
                            cypher=stat_data["cypher"],
                            static_params=stat_data.get("static_params", {}),
                            input_param_name=stat_data.get("input_param_name"),
                            input_cypher=stat_data.get("input_cypher"),
                        )
                    )
            return result

        return await asyncio.to_thread(_op)

    async def list_scheduled_queries(self) -> List[ScheduledQueryItem]:
        def _op() -> List[ScheduledQueryItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_SCHEDULED_QUERY_LIST},
            )
            return [_sq_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_scheduled_query(self, sq_id: str) -> Optional[ScheduledQueryItem]:
        def _op() -> Optional[ScheduledQueryItem]:
            table = _get_table()
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _sq_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_scheduled_query(
        self,
        name: str,
        cypher: str,
        params: List[Dict[str, Any]],
        frequency: Optional[int],
        watch_scans: List[Dict[str, Any]],
        enabled: bool,
        actions: List[Dict[str, Any]],
        created_by: str,
    ) -> ScheduledQueryItem:
        sq_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()
        version = 1
        base = _strip_none(
            {
                "scheduled_query_id": sq_id,
                "name": name,
                "cypher": cypher,
                "params": _floats_to_decimal(params),
                "frequency": frequency,
                "watch_scans": _floats_to_decimal(watch_scans),
                "enabled": enabled,
                "actions": _floats_to_decimal(actions),
                "current_version": version,
                "created_at": now,
                "updated_at": now,
                "created_by": created_by,
                "updated_by": created_by,
            }
        )
        metadata_item = {"PK": _sq_pk(sq_id), "SK": _SK_METADATA, **base}
        list_item = {
            "PK": _PK_SCHEDULED_QUERY_LIST,
            "SK": _sq_pk(sq_id),
            **base,
        }
        version_item = _strip_none(
            {
                "PK": _sq_pk(sq_id),
                "SK": _sq_version_sk(version),
                "scheduled_query_id": sq_id,
                "name": name,
                "version": version,
                "cypher": cypher,
                "params": _floats_to_decimal(params),
                "frequency": frequency,
                "watch_scans": _floats_to_decimal(watch_scans),
                "enabled": enabled,
                "actions": _floats_to_decimal(actions),
                "created_at": now,
                "created_by": created_by,
                "comment": None,
            }
        )

        def _op() -> None:
            table = _get_table()
            _transact_put_sync(table, metadata_item, list_item, version_item)

        await asyncio.to_thread(_op)
        return _sq_from_item(base)

    async def update_scheduled_query(
        self,
        sq_id: str,
        name: str,
        cypher: str,
        params: List[Dict[str, Any]],
        frequency: Optional[int],
        watch_scans: List[Dict[str, Any]],
        enabled: bool,
        actions: List[Dict[str, Any]],
        updated_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ScheduledQueryItem]:
        def _op() -> Optional[ScheduledQueryItem]:
            table = _get_table()
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=timezone.utc).isoformat()
            base = _strip_none(
                {
                    "scheduled_query_id": sq_id,
                    "name": name,
                    "cypher": cypher,
                    "params": _floats_to_decimal(params),
                    "frequency": frequency,
                    "watch_scans": _floats_to_decimal(watch_scans),
                    "enabled": enabled,
                    "actions": _floats_to_decimal(actions),
                    "current_version": version,
                    "created_at": existing["created_at"],
                    "updated_at": now,
                    "created_by": existing["created_by"],
                    "updated_by": updated_by,
                }
            )
            metadata_item = {"PK": _sq_pk(sq_id), "SK": _SK_METADATA, **base}
            list_item = {
                "PK": _PK_SCHEDULED_QUERY_LIST,
                "SK": _sq_pk(sq_id),
                **base,
            }
            version_item = _strip_none(
                {
                    "PK": _sq_pk(sq_id),
                    "SK": _sq_version_sk(version),
                    "scheduled_query_id": sq_id,
                    "name": name,
                    "version": version,
                    "cypher": cypher,
                    "params": _floats_to_decimal(params),
                    "frequency": frequency,
                    "watch_scans": _floats_to_decimal(watch_scans),
                    "enabled": enabled,
                    "actions": _floats_to_decimal(actions),
                    "created_at": now,
                    "created_by": updated_by,
                    "comment": comment,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _sq_from_item(base)

        return await asyncio.to_thread(_op)

    async def list_scheduled_query_versions(
        self, sq_id: str
    ) -> List[ScheduledQueryVersion]:
        def _op() -> List[ScheduledQueryVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _sq_pk(sq_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_sq_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_scheduled_query_version(
        self, sq_id: str, version: int
    ) -> Optional[ScheduledQueryVersion]:
        def _op() -> Optional[ScheduledQueryVersion]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _sq_pk(sq_id), "SK": _sq_version_sk(version)}
            )
            item = resp.get("Item")
            if not item:
                return None
            return _sq_version_from_item(item)

        return await asyncio.to_thread(_op)

    async def delete_scheduled_query(self, sq_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _sq_pk(sq_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [
                {"PK": item["PK"], "SK": item["SK"]}
                for item in items_resp.get("Items", [])
            ]
            keys_to_delete.append({"PK": _PK_SCHEDULED_QUERY_LIST, "SK": _sq_pk(sq_id)})
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: Optional[str] = None,
    ) -> User:
        """Get an existing user by (iss, sub), or create one on first login."""

        def _op() -> User:
            table = _get_table()
            now = datetime.now(tz=timezone.utc).isoformat()
            lookup_sk = _user_lookup_sk(iss, sub)

            lookup_resp = table.get_item(
                Key={"PK": _PK_USER_LOOKUP, "SK": lookup_sk},
            )
            lookup_item = lookup_resp.get("Item")

            if lookup_item:
                user_id = lookup_item["user_id"]
                profile_resp = table.get_item(
                    Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
                )
                return _user_from_item(profile_resp["Item"])

            user_id = generate_report_id()
            profile_item = _strip_none(
                {
                    "PK": _user_pk(user_id),
                    "SK": _SK_METADATA,
                    "user_id": user_id,
                    "sub": sub,
                    "iss": iss,
                    "email": email,
                    "display_name": display_name,
                    "created_at": now,
                    "last_login": now,
                    "archived_at": None,
                }
            )
            new_lookup_item = {
                "PK": _PK_USER_LOOKUP,
                "SK": lookup_sk,
                "user_id": user_id,
            }

            try:
                table.put_item(
                    Item=new_lookup_item,
                    ConditionExpression="attribute_not_exists(PK)",
                )
                table.put_item(Item=profile_item)
            except table.meta.client.exceptions.ConditionalCheckFailedException:
                lookup_resp2 = table.get_item(
                    Key={"PK": _PK_USER_LOOKUP, "SK": lookup_sk},
                )
                user_id = lookup_resp2["Item"]["user_id"]
                profile_resp = table.get_item(
                    Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
                )
                return _user_from_item(profile_resp["Item"])

            return User(
                user_id=user_id,
                sub=sub,
                iss=iss,
                email=email,
                display_name=display_name,
                created_at=now,
                last_login=now,
                archived_at=None,
            )

        return await asyncio.to_thread(_op)

    async def update_user_profile(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        token_iat: Optional[datetime] = None,
    ) -> User:
        """Sync mutable profile fields, writing only what has changed."""

        def _op() -> User:
            table = _get_table()
            profile_resp = table.get_item(
                Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
            )
            item = profile_resp.get("Item")
            if not item:
                raise ValueError(f"User {user_id!r} not found")
            stored_user = _user_from_item(item)

            email_changed = stored_user.email != email
            name_changed = (
                display_name is not None and stored_user.display_name != display_name
            )
            iat_newer = token_iat is not None and token_iat > datetime.fromisoformat(
                stored_user.last_login
            )

            if not (email_changed or name_changed or iat_newer):
                return stored_user

            return _update_user_profile_internal(
                table,
                user_id,
                email,
                display_name if name_changed else None,
                token_iat if iat_newer else None,
            )

        return await asyncio.to_thread(_op)

    async def get_user(self, user_id: str) -> Optional[User]:
        """Return a user by their internal user_id, or None if not found."""

        def _op() -> Optional[User]:
            table = _get_table()
            resp = table.get_item(Key={"PK": _user_pk(user_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _user_from_item(item)

        return await asyncio.to_thread(_op)

    async def archive_user(self, user_id: str) -> bool:
        """Soft-delete a user by setting archived_at."""

        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _user_pk(user_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False
            now = datetime.now(tz=timezone.utc).isoformat()
            table.update_item(
                Key={"PK": _user_pk(user_id), "SK": _SK_METADATA},
                UpdateExpression="SET archived_at = :t",
                ExpressionAttributeValues={":t": now},
            )
            return True

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Toolsets
    # ------------------------------------------------------------------

    async def list_toolsets(self) -> List[ToolsetListItem]:
        def _op() -> List[ToolsetListItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_TOOLSET_LIST},
            )
            return [_toolset_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_toolset(self, toolset_id: str) -> Optional[ToolsetListItem]:
        def _op() -> Optional[ToolsetListItem]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA}
            )
            item = resp.get("Item")
            if not item:
                return None
            return _toolset_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_toolset(
        self,
        name: str,
        description: str,
        enabled: bool,
        created_by: str,
    ) -> ToolsetListItem:
        toolset_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()
        version = 1
        base = _strip_none(
            {
                "toolset_id": toolset_id,
                "name": name,
                "description": description,
                "enabled": enabled,
                "current_version": version,
                "created_at": now,
                "updated_at": now,
                "created_by": created_by,
                "updated_by": created_by,
            }
        )
        metadata_item = {"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA, **base}
        list_item = {
            "PK": _PK_TOOLSET_LIST,
            "SK": _toolset_list_sk(toolset_id),
            **base,
        }
        version_item = _strip_none(
            {
                "PK": _toolset_pk(toolset_id),
                "SK": _version_sk(version),
                "toolset_id": toolset_id,
                "name": name,
                "description": description,
                "enabled": enabled,
                "version": version,
                "created_at": now,
                "created_by": created_by,
                "comment": None,
            }
        )

        def _op() -> None:
            table = _get_table()
            _transact_put_sync(table, metadata_item, list_item, version_item)

        await asyncio.to_thread(_op)
        return _toolset_from_item(base)

    async def update_toolset(
        self,
        toolset_id: str,
        name: str,
        description: str,
        enabled: bool,
        updated_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ToolsetListItem]:
        def _op() -> Optional[ToolsetListItem]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA}
            )
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=timezone.utc).isoformat()
            base = _strip_none(
                {
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "enabled": enabled,
                    "current_version": version,
                    "created_at": existing["created_at"],
                    "updated_at": now,
                    "created_by": existing["created_by"],
                    "updated_by": updated_by,
                }
            )
            metadata_item = {
                "PK": _toolset_pk(toolset_id),
                "SK": _SK_METADATA,
                **base,
            }
            list_item = {
                "PK": _PK_TOOLSET_LIST,
                "SK": _toolset_list_sk(toolset_id),
                **base,
            }
            version_item = _strip_none(
                {
                    "PK": _toolset_pk(toolset_id),
                    "SK": _version_sk(version),
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "enabled": enabled,
                    "version": version,
                    "created_at": now,
                    "created_by": updated_by,
                    "comment": comment,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _toolset_from_item(base)

        return await asyncio.to_thread(_op)

    async def delete_toolset(self, toolset_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA}
            )
            if not resp.get("Item"):
                return False

            # Find and delete all tools in this toolset first
            tool_list_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _tool_list_pk(toolset_id)},
                ProjectionExpression="SK",
            )
            tool_ids = [
                item["SK"].replace("TOOL#", "")
                for item in tool_list_resp.get("Items", [])
            ]
            for tool_id in tool_ids:
                tool_items_resp = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": _tool_pk(tool_id)},
                    ProjectionExpression="PK, SK",
                )
                keys_to_delete = [
                    {"PK": i["PK"], "SK": i["SK"]}
                    for i in tool_items_resp.get("Items", [])
                ]
                with table.batch_writer() as batch:
                    for key in keys_to_delete:
                        batch.delete_item(Key=key)

            # Delete the tool list partition for this toolset
            tool_list_keys = [
                {"PK": _tool_list_pk(toolset_id), "SK": _tool_list_sk(tool_id)}
                for tool_id in tool_ids
            ]

            # Delete all toolset items
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _toolset_pk(toolset_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [
                {"PK": item["PK"], "SK": item["SK"]}
                for item in items_resp.get("Items", [])
            ]
            keys_to_delete.append(
                {"PK": _PK_TOOLSET_LIST, "SK": _toolset_list_sk(toolset_id)}
            )
            keys_to_delete.extend(tool_list_keys)

            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)

            return True

        return await asyncio.to_thread(_op)

    async def list_toolset_versions(self, toolset_id: str) -> List[ToolsetVersion]:
        def _op() -> List[ToolsetVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _toolset_pk(toolset_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_toolset_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_toolset_version(
        self, toolset_id: str, version: int
    ) -> Optional[ToolsetVersion]:
        def _op() -> Optional[ToolsetVersion]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _toolset_pk(toolset_id), "SK": _version_sk(version)}
            )
            item = resp.get("Item")
            if not item:
                return None
            return _toolset_version_from_item(item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def list_tools(self, toolset_id: str) -> List[ToolItem]:
        def _op() -> List[ToolItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _tool_list_pk(toolset_id)},
            )
            tool_ids = [
                item["SK"].replace("TOOL#", "") for item in resp.get("Items", [])
            ]
            tools = []
            for tool_id in tool_ids:
                tool_resp = table.get_item(
                    Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA}
                )
                item = tool_resp.get("Item")
                if item:
                    tools.append(_tool_from_item(item))
            return tools

        return await asyncio.to_thread(_op)

    async def get_tool(self, tool_id: str) -> Optional[ToolItem]:
        def _op() -> Optional[ToolItem]:
            table = _get_table()
            resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _tool_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_tool(
        self,
        toolset_id: str,
        name: str,
        description: str,
        cypher: str,
        parameters: List[Dict[str, Any]],
        enabled: bool,
        created_by: str,
    ) -> Optional[ToolItem]:
        def _op() -> Optional[ToolItem]:
            table = _get_table()
            # Verify toolset exists
            ts_resp = table.get_item(
                Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA}
            )
            if not ts_resp.get("Item"):
                return None

            tool_id = generate_report_id()
            now = datetime.now(tz=timezone.utc).isoformat()
            version = 1
            base = _strip_none(
                {
                    "tool_id": tool_id,
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "cypher": cypher,
                    "parameters": _floats_to_decimal(parameters),
                    "enabled": enabled,
                    "current_version": version,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": created_by,
                    "updated_by": created_by,
                }
            )
            metadata_item = {"PK": _tool_pk(tool_id), "SK": _SK_METADATA, **base}
            list_item = {
                "PK": _tool_list_pk(toolset_id),
                "SK": _tool_list_sk(tool_id),
                **base,
            }
            version_item = _strip_none(
                {
                    "PK": _tool_pk(tool_id),
                    "SK": _version_sk(version),
                    "tool_id": tool_id,
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "cypher": cypher,
                    "parameters": _floats_to_decimal(parameters),
                    "enabled": enabled,
                    "version": version,
                    "created_at": now,
                    "created_by": created_by,
                    "comment": None,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _tool_from_item(base)

        return await asyncio.to_thread(_op)

    async def update_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        cypher: str,
        parameters: List[Dict[str, Any]],
        enabled: bool,
        updated_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ToolItem]:
        def _op() -> Optional[ToolItem]:
            table = _get_table()
            resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            toolset_id = existing["toolset_id"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=timezone.utc).isoformat()
            base = _strip_none(
                {
                    "tool_id": tool_id,
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "cypher": cypher,
                    "parameters": _floats_to_decimal(parameters),
                    "enabled": enabled,
                    "current_version": version,
                    "created_at": existing["created_at"],
                    "updated_at": now,
                    "created_by": existing["created_by"],
                    "updated_by": updated_by,
                }
            )
            metadata_item = {"PK": _tool_pk(tool_id), "SK": _SK_METADATA, **base}
            list_item = {
                "PK": _tool_list_pk(toolset_id),
                "SK": _tool_list_sk(tool_id),
                **base,
            }
            version_item = _strip_none(
                {
                    "PK": _tool_pk(tool_id),
                    "SK": _version_sk(version),
                    "tool_id": tool_id,
                    "toolset_id": toolset_id,
                    "name": name,
                    "description": description,
                    "cypher": cypher,
                    "parameters": _floats_to_decimal(parameters),
                    "enabled": enabled,
                    "version": version,
                    "created_at": now,
                    "created_by": updated_by,
                    "comment": comment,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _tool_from_item(base)

        return await asyncio.to_thread(_op)

    async def delete_tool(self, tool_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return False
            toolset_id = item["toolset_id"]
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _tool_pk(tool_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [
                {"PK": i["PK"], "SK": i["SK"]} for i in items_resp.get("Items", [])
            ]
            keys_to_delete.append(
                {"PK": _tool_list_pk(toolset_id), "SK": _tool_list_sk(tool_id)}
            )
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def list_tool_versions(self, tool_id: str) -> List[ToolVersion]:
        def _op() -> List[ToolVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _tool_pk(tool_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_tool_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_tool_version(
        self, tool_id: str, version: int
    ) -> Optional[ToolVersion]:
        def _op() -> Optional[ToolVersion]:
            table = _get_table()
            resp = table.get_item(
                Key={"PK": _tool_pk(tool_id), "SK": _version_sk(version)}
            )
            item = resp.get("Item")
            if not item:
                return None
            return _tool_version_from_item(item)

        return await asyncio.to_thread(_op)

    async def list_enabled_tools(self) -> List[ToolItem]:
        def _op() -> List[ToolItem]:
            table = _get_table()
            ts_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_TOOLSET_LIST},
            )
            enabled_toolset_ids = [
                item["toolset_id"]
                for item in ts_resp.get("Items", [])
                if item.get("enabled", True)
            ]
            tools = []
            for toolset_id in enabled_toolset_ids:
                tool_list_resp = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": _tool_list_pk(toolset_id)},
                )
                for list_item in tool_list_resp.get("Items", []):
                    if list_item.get("enabled", True):
                        tool_resp = table.get_item(
                            Key={
                                "PK": _tool_pk(list_item["tool_id"]),
                                "SK": _SK_METADATA,
                            }
                        )
                        item = tool_resp.get("Item")
                        if item and item.get("enabled", True):
                            tools.append(_tool_from_item(item))
            return tools

        return await asyncio.to_thread(_op)
