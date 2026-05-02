import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
import botocore.exceptions
from snowflake import SnowflakeGenerator

from reporting import settings
from reporting.schema.mcp_config import (
    SkillItem,
    SkillsetListItem,
    SkillsetVersion,
    SkillVersion,
    ToolItem,
    ToolParamDef,
    ToolsetListItem,
    ToolsetVersion,
    ToolVersion,
)
from reporting.schema.rbac import RoleItem, RoleVersion
from reporting.schema.report_config import (
    QueryHistoryItem,
    ReportAccess,
    ReportListItem,
    ReportVersion,
    ScheduledQueryItem,
    ScheduledQueryVersion,
    User,
)
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

# Module-level snowflake generator; lazily initialised so the machine ID
# setting is read after the module is imported.
_snowflake_gen: SnowflakeGenerator | None = None

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
# Scheduled queries — list index PK for listing all scheduled queries.
_PK_SCHEDULED_QUERY_LIST = "SCHEDULED_QUERY_LIST"
# Toolsets — list index PK for listing all toolsets.
_PK_TOOLSET_LIST = "TOOLSET_LIST"
# Skillsets — list index PK for listing all skillsets.
_PK_SKILLSET_LIST = "SKILLSET_LIST"
# Roles — list index PK for listing all user-defined roles.
_PK_ROLE_LIST = "ROLE_LIST"
# Group mappings — list index PK for listing all group-to-role mappings.
# Query history — per-user SK prefix; items sorted newest-first by snowflake ID.
_SK_QUERY_HISTORY_PREFIX = "HISTORY#"
# Maximum history items fetched from DynamoDB per user (caps scan size).
_QUERY_HISTORY_MAX = 500


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


def _query_history_pk(user_id: str) -> str:
    return f"QUERY_HISTORY#{user_id}"


def _query_history_sk(history_id: str) -> str:
    """Pad the snowflake ID so lexicographic order matches time order."""
    return f"{_SK_QUERY_HISTORY_PREFIX}{history_id.zfill(20)}"


def _role_pk(role_id: str) -> str:
    return f"ROLE#{role_id}"


def _role_list_sk(role_id: str) -> str:
    return f"ROLE#{role_id}"


def _role_from_item(item: dict) -> RoleItem:
    return RoleItem(
        role_id=item["role_id"],
        name=item["name"],
        description=item.get("description", ""),
        permissions=item.get("permissions", []),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _report_visible_to_user(item: dict[str, Any], user_id: str | None) -> bool:
    if user_id is None:
        return True
    access = item["access"]
    return access["scope"] == "public" or item["created_by"] == user_id


def _report_list_item_from_item(item: dict[str, Any]) -> ReportListItem:
    return ReportListItem(
        report_id=item["report_id"],
        name=item["name"],
        current_version=item["current_version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item["updated_by"],
        access=item["access"],
        pinned=bool(item.get("pinned", False)),
    )


def _report_version_from_item(item: dict[str, Any], meta: dict[str, Any]) -> ReportVersion:
    return ReportVersion(
        report_id=item["report_id"],
        name=item["name"],
        version=item["version"],
        config=item["config"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
        report_created_by=meta["created_by"],
        report_updated_by=meta["updated_by"],
        access=meta["access"],
    )


def _role_version_from_item(item: dict) -> RoleVersion:
    return RoleVersion(
        role_id=item["role_id"],
        name=item["name"],
        description=item.get("description", ""),
        permissions=item.get("permissions", []),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


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


def _skillset_pk(skillset_id: str) -> str:
    return f"SKILLSET#{skillset_id}"


def _skillset_list_sk(skillset_id: str) -> str:
    return f"SKILLSET#{skillset_id}"


def _skill_pk(skill_id: str) -> str:
    return f"SKILL#{skill_id}"


def _skill_list_pk(skillset_id: str) -> str:
    return f"SKILL_LIST#{skillset_id}"


def _skill_list_sk(skill_id: str) -> str:
    return f"SKILL#{skill_id}"


def _toolset_from_item(item: dict) -> ToolsetListItem:
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


def _toolset_version_from_item(item: dict) -> ToolsetVersion:
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


def _tool_from_item(item: dict) -> ToolItem:
    return ToolItem(
        tool_id=item["tool_id"],
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        cypher=item["cypher"],
        parameters=[ToolParamDef(**p) if isinstance(p, dict) else p for p in item.get("parameters", [])],
        enabled=item.get("enabled", True),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _tool_version_from_item(item: dict) -> ToolVersion:
    return ToolVersion(
        tool_id=item["tool_id"],
        toolset_id=item["toolset_id"],
        name=item["name"],
        description=item.get("description", ""),
        cypher=item["cypher"],
        parameters=[ToolParamDef(**p) if isinstance(p, dict) else p for p in item.get("parameters", [])],
        enabled=item.get("enabled", True),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _skillset_from_item(item: dict) -> SkillsetListItem:
    return SkillsetListItem(
        skillset_id=item["skillset_id"],
        name=item["name"],
        description=item.get("description", ""),
        enabled=item.get("enabled", True),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _skillset_version_from_item(item: dict) -> SkillsetVersion:
    return SkillsetVersion(
        skillset_id=item["skillset_id"],
        name=item["name"],
        description=item.get("description", ""),
        enabled=item.get("enabled", True),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _skill_from_item(item: dict) -> SkillItem:
    return SkillItem(
        skill_id=item["skill_id"],
        skillset_id=item["skillset_id"],
        name=item["name"],
        description=item.get("description", ""),
        template=item["template"],
        parameters=[ToolParamDef(**p) if isinstance(p, dict) else p for p in item.get("parameters", [])],
        triggers=item.get("triggers", []),
        tools_required=item.get("tools_required", []),
        enabled=item.get("enabled", True),
        current_version=item.get("current_version", 0),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        created_by=item["created_by"],
        updated_by=item.get("updated_by"),
    )


def _skill_version_from_item(item: dict) -> SkillVersion:
    return SkillVersion(
        skill_id=item["skill_id"],
        skillset_id=item["skillset_id"],
        name=item["name"],
        description=item.get("description", ""),
        template=item["template"],
        parameters=[ToolParamDef(**p) if isinstance(p, dict) else p for p in item.get("parameters", [])],
        triggers=item.get("triggers", []),
        tools_required=item.get("tools_required", []),
        enabled=item.get("enabled", True),
        version=item["version"],
        created_at=item["created_at"],
        created_by=item["created_by"],
        comment=item.get("comment"),
    )


def _sq_version_sk(version: int) -> str:
    """Zero-pad version numbers so lexicographic sort matches numeric sort."""
    return f"{_SK_VERSION_PREFIX}{version:010d}"  # noqa: E231


def _sq_from_item(item: dict) -> ScheduledQueryItem:
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
        last_run_status=item.get("last_run_status"),
        last_run_at=item.get("last_run_at"),
        last_errors=item.get("last_errors", []),
        last_scheduled_at=item.get("last_scheduled_at"),
    )


def _sq_version_from_item(item: dict) -> ScheduledQueryVersion:
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


def _user_from_item(item: dict) -> User:
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


def _transact_put_sync(table: Any, *items: dict[str, Any]) -> None:
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
    display_name: str | None,
    token_iat: datetime | None,
) -> User:
    """Apply an email/display_name update and conditionally advance last_login."""
    update_exp = "SET email = :e"
    exp_values: dict = {":e": email}
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

    async def list_reports(self, user_id: str | None = None) -> list[ReportListItem]:
        """Return lightweight metadata for all reports."""

        def _op() -> list[ReportListItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_REPORT_LIST},
            )
            items = resp.get("Items", [])
            return [_report_list_item_from_item(item) for item in items if _report_visible_to_user(item, user_id)]

        return await asyncio.to_thread(_op)

    async def get_report_metadata(
        self,
        report_id: str,
        user_id: str | None = None,
    ) -> ReportListItem | None:
        def _op() -> ReportListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item or not _report_visible_to_user(item, user_id):
                return None
            return _report_list_item_from_item(item)

        return await asyncio.to_thread(_op)

    async def get_report_latest(
        self,
        report_id: str,
        user_id: str | None = None,
    ) -> ReportVersion | None:
        """Return the latest version of a report config, or None if not found."""

        def _op() -> ReportVersion | None:
            table = _get_table()
            meta_resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = meta_resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return None
            resp = table.get_item(
                Key={"PK": _report_pk(report_id), "SK": _SK_LATEST},
            )
            item = resp.get("Item")
            if not item:
                return None
            return _report_version_from_item(item, meta)

        return await asyncio.to_thread(_op)

    async def get_report_version(
        self,
        report_id: str,
        version: int,
        user_id: str | None = None,
    ) -> ReportVersion | None:
        """Return a specific version of a report config, or None if not found."""

        def _op() -> ReportVersion | None:
            table = _get_table()
            meta_resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = meta_resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return None
            resp = table.get_item(
                Key={"PK": _report_pk(report_id), "SK": _version_sk(version)},
            )
            item = resp.get("Item")
            if not item:
                return None
            return _report_version_from_item(item, meta)

        return await asyncio.to_thread(_op)

    async def list_report_versions(
        self,
        report_id: str,
        user_id: str | None = None,
    ) -> list[ReportVersion]:
        """Return all stored versions for a report, newest first."""

        def _op() -> list[ReportVersion]:
            table = _get_table()
            meta_resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = meta_resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return []
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _report_pk(report_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_report_version_from_item(item, meta) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def create_report(
        self,
        name: str,
        created_by: str,
        access: ReportAccess | None = None,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""
        report_id = generate_report_id()
        now = datetime.now(tz=UTC).isoformat()
        report_access = access or ReportAccess(scope="private")

        metadata_item = {
            "PK": _report_pk(report_id),
            "SK": _SK_METADATA,
            "report_id": report_id,
            "name": name,
            "current_version": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
            "updated_by": created_by,
            "access": report_access.model_dump(),
            "pinned": False,
        }
        list_item = {
            "PK": _PK_REPORT_LIST,
            "SK": f"REPORT#{report_id}",
            "report_id": report_id,
            "name": name,
            "current_version": 0,
            "created_at": now,
            "updated_at": now,
            "created_by": created_by,
            "updated_by": created_by,
            "access": report_access.model_dump(),
            "pinned": False,
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
            created_by=created_by,
            updated_by=created_by,
            access=report_access,
            pinned=False,
        )

    async def save_report_version(
        self,
        report_id: str,
        config: dict[str, Any],
        created_by: str,
        comment: str | None = None,
        user_id: str | None = None,
    ) -> ReportVersion | None:
        """Append a new version to an existing report and return it."""

        def _op() -> ReportVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return None

            version = int(meta["current_version"]) + 1
            config_name = config.get("name")
            if isinstance(config_name, str) and config_name.strip():
                report_name = config_name.strip()
            else:
                report_name = meta["name"]
            stored_config = {**config, "name": report_name}
            pinned = bool(meta.get("pinned", False))
            now = datetime.now(tz=UTC).isoformat()

            version_item = {
                "PK": _report_pk(report_id),
                "SK": _version_sk(version),
                "report_id": report_id,
                "name": report_name,
                "version": version,
                "config": _floats_to_decimal(stored_config),
                "created_at": now,
                "created_by": created_by,
                "comment": comment,
            }
            latest_item = {**version_item, "SK": _SK_LATEST}
            metadata_item = {
                "PK": _report_pk(report_id),
                "SK": _SK_METADATA,
                "report_id": report_id,
                "name": report_name,
                "current_version": version,
                "created_at": meta["created_at"],
                "updated_at": now,
                "created_by": meta["created_by"],
                "updated_by": created_by,
                "access": meta["access"],
                "pinned": pinned,
            }
            list_item = {
                "PK": _PK_REPORT_LIST,
                "SK": f"REPORT#{report_id}",
                "report_id": report_id,
                "name": report_name,
                "current_version": version,
                "created_at": meta["created_at"],
                "updated_at": now,
                "created_by": meta["created_by"],
                "updated_by": created_by,
                "access": meta["access"],
                "pinned": pinned,
            }

            _transact_put_sync(
                table,
                version_item,
                latest_item,
                metadata_item,
                list_item,
            )
            return _report_version_from_item(version_item, metadata_item)

        return await asyncio.to_thread(_op)

    async def update_report_visibility(
        self,
        report_id: str,
        updated_by: str,
        access: ReportAccess | None = None,
    ) -> ReportListItem | None:
        def _op() -> ReportListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = resp.get("Item")
            if not meta:
                return None

            now = datetime.now(tz=UTC).isoformat()
            new_access = access.model_dump() if access is not None else meta["access"]
            updated = {
                **meta,
                "updated_at": now,
                "updated_by": updated_by,
                "access": new_access,
            }
            list_item = {
                "PK": _PK_REPORT_LIST,
                "SK": f"REPORT#{report_id}",
                "report_id": report_id,
                "name": meta["name"],
                "current_version": meta["current_version"],
                "created_at": meta["created_at"],
                "updated_at": now,
                "created_by": meta["created_by"],
                "updated_by": updated_by,
                "access": new_access,
                "pinned": bool(meta.get("pinned", False)),
            }
            _transact_put_sync(table, updated, list_item)
            return _report_list_item_from_item(list_item)

        return await asyncio.to_thread(_op)

    async def delete_report(self, report_id: str, user_id: str | None = None) -> bool:
        """Delete a report and all its versions."""

        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return False

            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _report_pk(report_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [{"PK": item["PK"], "SK": item["SK"]} for item in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _PK_REPORT_LIST, "SK": f"REPORT#{report_id}"})

            dashboard_resp = table.get_item(Key={"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER})
            dashboard_item = dashboard_resp.get("Item")
            if dashboard_item and dashboard_item.get("report_id") == report_id:
                keys_to_delete.append({"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER})

            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)

            return True

        return await asyncio.to_thread(_op)

    async def pin_report(
        self,
        report_id: str,
        pinned: bool,
        updated_by: str,
        user_id: str | None = None,
    ) -> bool:
        """Set or clear the pinned flag on a report."""

        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _report_pk(report_id), "SK": _SK_METADATA})
            meta = resp.get("Item")
            if not meta or not _report_visible_to_user(meta, user_id):
                return False
            now = datetime.now(tz=UTC).isoformat()
            table.update_item(
                Key={"PK": _report_pk(report_id), "SK": _SK_METADATA},
                UpdateExpression="SET pinned = :pinned, updated_at = :updated_at, updated_by = :updated_by",
                ExpressionAttributeValues={":pinned": pinned, ":updated_at": now, ":updated_by": updated_by},
            )
            table.update_item(
                Key={"PK": _PK_REPORT_LIST, "SK": f"REPORT#{report_id}"},
                UpdateExpression="SET pinned = :pinned, updated_at = :updated_at, updated_by = :updated_by",
                ExpressionAttributeValues={":pinned": pinned, ":updated_at": now, ":updated_by": updated_by},
            )
            return True

        return await asyncio.to_thread(_op)

    async def get_dashboard_report_id(self) -> str | None:
        """Return the report_id of the current dashboard report, or None if not set."""

        def _op() -> str | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _PK_DASHBOARD, "SK": _SK_DASHBOARD_POINTER})
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
            meta = resp.get("Item")
            if not meta:
                return False
            if meta["access"]["scope"] != "public":
                return False
            table.put_item(
                Item={
                    "PK": _PK_DASHBOARD,
                    "SK": _SK_DASHBOARD_POINTER,
                    "report_id": report_id,
                    "updated_at": datetime.now(tz=UTC).isoformat(),
                }
            )
            return True

        return await asyncio.to_thread(_op)

    async def get_dashboard_report(self) -> ReportVersion | None:
        """Return the latest version of the dashboard report, or None if not set."""
        report_id = await self.get_dashboard_report_id()
        if not report_id:
            return None
        report = await self.get_report_latest(report_id)
        if report and report.access.scope == "public":
            return report
        return None

    async def list_scheduled_queries(self) -> list[ScheduledQueryItem]:
        def _op() -> list[ScheduledQueryItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_SCHEDULED_QUERY_LIST},
            )
            return [_sq_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_scheduled_query(self, sq_id: str) -> ScheduledQueryItem | None:
        def _op() -> ScheduledQueryItem | None:
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
        params: list[dict[str, Any]],
        frequency: int | None,
        watch_scans: list[dict[str, Any]],
        enabled: bool,
        actions: list[dict[str, Any]],
        created_by: str,
    ) -> ScheduledQueryItem:
        sq_id = generate_report_id()
        now = datetime.now(tz=UTC).isoformat()
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
        params: list[dict[str, Any]],
        frequency: int | None,
        watch_scans: list[dict[str, Any]],
        enabled: bool,
        actions: list[dict[str, Any]],
        updated_by: str,
        comment: str | None = None,
    ) -> ScheduledQueryItem | None:
        def _op() -> ScheduledQueryItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
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

    async def list_scheduled_query_versions(self, sq_id: str) -> list[ScheduledQueryVersion]:
        def _op() -> list[ScheduledQueryVersion]:
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

    async def get_scheduled_query_version(self, sq_id: str, version: int) -> ScheduledQueryVersion | None:
        def _op() -> ScheduledQueryVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _sq_version_sk(version)})
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
            keys_to_delete = [{"PK": item["PK"], "SK": item["SK"]} for item in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _PK_SCHEDULED_QUERY_LIST, "SK": _sq_pk(sq_id)})
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def acquire_scheduled_query_lock(self, sq_id: str, expected_last_scheduled_at: str | None) -> bool:
        def _op() -> bool:
            table = _get_table()
            now = datetime.now(tz=UTC).isoformat()
            update_expr = "SET last_scheduled_at = :new_val"
            expr_values: dict[str, Any] = {":new_val": now}

            if expected_last_scheduled_at is None:
                condition = "attribute_not_exists(last_scheduled_at)"
            else:
                condition = "last_scheduled_at = :expected"
                expr_values[":expected"] = expected_last_scheduled_at

            try:
                table.update_item(
                    Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA},
                    UpdateExpression=update_expr,
                    ExpressionAttributeValues=expr_values,
                    ConditionExpression=condition,
                )
            except botocore.exceptions.ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return False
                raise
            # Update the list item (best-effort, no condition needed)
            table.update_item(
                Key={"PK": _PK_SCHEDULED_QUERY_LIST, "SK": _sq_pk(sq_id)},
                UpdateExpression=update_expr,
                ExpressionAttributeValues={":new_val": now},
            )
            return True

        return await asyncio.to_thread(_op)

    async def record_scheduled_query_result(self, sq_id: str, status: str, error: str | None = None) -> None:
        def _op() -> None:
            table = _get_table()
            now = datetime.now(tz=UTC).isoformat()

            # Read current metadata to get existing last_errors
            resp = table.get_item(Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return

            if status == "failure" and error:
                errors = list(item.get("last_errors", []))
                errors.insert(0, {"timestamp": now, "error": error})
                errors = errors[:5]
            elif status == "success":
                errors = []
            else:
                errors = list(item.get("last_errors", []))

            update_expr = "SET last_run_status = :status, last_run_at = :now, last_errors = :errors"
            expr_values = {":status": status, ":now": now, ":errors": errors}

            # Update both metadata and list items
            table.update_item(
                Key={"PK": _sq_pk(sq_id), "SK": _SK_METADATA},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )
            table.update_item(
                Key={"PK": _PK_SCHEDULED_QUERY_LIST, "SK": _sq_pk(sq_id)},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )

        await asyncio.to_thread(_op)

    async def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: str | None = None,
    ) -> User:
        """Get an existing user by (iss, sub), or create one on first login."""

        def _op() -> User:
            table = _get_table()
            now = datetime.now(tz=UTC).isoformat()
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
        display_name: str | None = None,
        token_iat: datetime | None = None,
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
            name_changed = display_name is not None and stored_user.display_name != display_name
            iat_newer = token_iat is not None and token_iat > datetime.fromisoformat(stored_user.last_login)

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

    async def get_user(self, user_id: str) -> User | None:
        """Return a user by their internal user_id, or None if not found."""

        def _op() -> User | None:
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
            now = datetime.now(tz=UTC).isoformat()
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

    async def list_toolsets(self) -> list[ToolsetListItem]:
        def _op() -> list[ToolsetListItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_TOOLSET_LIST},
            )
            return [_toolset_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_toolset(self, toolset_id: str) -> ToolsetListItem | None:
        def _op() -> ToolsetListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _toolset_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_toolset(
        self,
        toolset_id: str,
        name: str,
        description: str,
        enabled: bool,
        created_by: str,
    ) -> ToolsetListItem:
        now = datetime.now(tz=UTC).isoformat()
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
        comment: str | None = None,
    ) -> ToolsetListItem | None:
        def _op() -> ToolsetListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
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
            resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False

            # Find and delete all tools in this toolset first
            tool_list_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _tool_list_pk(toolset_id)},
                ProjectionExpression="SK",
            )
            tool_ids = [item["SK"].replace("TOOL#", "") for item in tool_list_resp.get("Items", [])]
            for tool_id in tool_ids:
                tool_items_resp = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": _tool_pk(tool_id)},
                    ProjectionExpression="PK, SK",
                )
                keys_to_delete = [{"PK": i["PK"], "SK": i["SK"]} for i in tool_items_resp.get("Items", [])]
                with table.batch_writer() as batch:
                    for key in keys_to_delete:
                        batch.delete_item(Key=key)

            # Delete the tool list partition for this toolset
            tool_list_keys = [{"PK": _tool_list_pk(toolset_id), "SK": _tool_list_sk(tool_id)} for tool_id in tool_ids]

            # Delete all toolset items
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _toolset_pk(toolset_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [{"PK": item["PK"], "SK": item["SK"]} for item in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _PK_TOOLSET_LIST, "SK": _toolset_list_sk(toolset_id)})
            keys_to_delete.extend(tool_list_keys)

            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)

            return True

        return await asyncio.to_thread(_op)

    async def list_toolset_versions(self, toolset_id: str) -> list[ToolsetVersion]:
        def _op() -> list[ToolsetVersion]:
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

    async def get_toolset_version(self, toolset_id: str, version: int) -> ToolsetVersion | None:
        def _op() -> ToolsetVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _version_sk(version)})
            item = resp.get("Item")
            if not item:
                return None
            return _toolset_version_from_item(item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    async def list_tools(self, toolset_id: str) -> list[ToolItem]:
        def _op() -> list[ToolItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _tool_list_pk(toolset_id)},
            )
            tool_ids = [item["SK"].replace("TOOL#", "") for item in resp.get("Items", [])]
            tools = []
            for tool_id in tool_ids:
                tool_resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
                item = tool_resp.get("Item")
                if item:
                    tools.append(_tool_from_item(item))
            return tools

        return await asyncio.to_thread(_op)

    async def get_tool(self, tool_id: str) -> ToolItem | None:
        def _op() -> ToolItem | None:
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
        tool_id: str,
        name: str,
        description: str,
        cypher: str,
        parameters: list[dict[str, Any]],
        enabled: bool,
        created_by: str,
    ) -> ToolItem | None:
        def _op() -> ToolItem | None:
            table = _get_table()
            # Verify toolset exists
            ts_resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA})
            if not ts_resp.get("Item"):
                return None

            now = datetime.now(tz=UTC).isoformat()
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
        parameters: list[dict[str, Any]],
        enabled: bool,
        updated_by: str,
        comment: str | None = None,
    ) -> ToolItem | None:
        def _op() -> ToolItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            toolset_id = existing["toolset_id"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
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
            keys_to_delete = [{"PK": i["PK"], "SK": i["SK"]} for i in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _tool_list_pk(toolset_id), "SK": _tool_list_sk(tool_id)})
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def list_tool_versions(self, tool_id: str) -> list[ToolVersion]:
        def _op() -> list[ToolVersion]:
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

    async def get_tool_version(self, tool_id: str, version: int) -> ToolVersion | None:
        def _op() -> ToolVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _version_sk(version)})
            item = resp.get("Item")
            if not item:
                return None
            return _tool_version_from_item(item)

        return await asyncio.to_thread(_op)

    async def list_enabled_tools(self) -> list[ToolItem]:
        def _op() -> list[ToolItem]:
            table = _get_table()
            ts_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_TOOLSET_LIST},
            )
            enabled_toolset_ids = [item["toolset_id"] for item in ts_resp.get("Items", []) if item.get("enabled", True)]
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

    async def get_enabled_tool(self, toolset_id: str, tool_id: str) -> ToolItem | None:
        def _op() -> ToolItem | None:
            table = _get_table()
            tool_resp = table.get_item(Key={"PK": _tool_pk(tool_id), "SK": _SK_METADATA})
            tool_item = tool_resp.get("Item")
            if not tool_item or tool_item.get("toolset_id") != toolset_id or not tool_item.get("enabled", True):
                return None

            toolset_resp = table.get_item(Key={"PK": _toolset_pk(toolset_id), "SK": _SK_METADATA})
            toolset_item = toolset_resp.get("Item")
            if not toolset_item or not toolset_item.get("enabled", True):
                return None
            return _tool_from_item(tool_item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Skillsets
    # ------------------------------------------------------------------

    async def list_skillsets(self) -> list[SkillsetListItem]:
        def _op() -> list[SkillsetListItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_SKILLSET_LIST},
            )
            return [_skillset_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_skillset(self, skillset_id: str) -> SkillsetListItem | None:
        def _op() -> SkillsetListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _skillset_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_skillset(
        self,
        skillset_id: str,
        name: str,
        description: str,
        enabled: bool,
        created_by: str,
    ) -> SkillsetListItem:
        now = datetime.now(tz=UTC).isoformat()
        version = 1
        base = _strip_none(
            {
                "skillset_id": skillset_id,
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
        metadata_item = {"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA, **base}
        list_item = {
            "PK": _PK_SKILLSET_LIST,
            "SK": _skillset_list_sk(skillset_id),
            **base,
        }
        version_item = _strip_none(
            {
                "PK": _skillset_pk(skillset_id),
                "SK": _version_sk(version),
                "skillset_id": skillset_id,
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
        return _skillset_from_item(base)

    async def update_skillset(
        self,
        skillset_id: str,
        name: str,
        description: str,
        enabled: bool,
        updated_by: str,
        comment: str | None = None,
    ) -> SkillsetListItem | None:
        def _op() -> SkillsetListItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
            base = _strip_none(
                {
                    "skillset_id": skillset_id,
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
            metadata_item = {"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA, **base}
            list_item = {"PK": _PK_SKILLSET_LIST, "SK": _skillset_list_sk(skillset_id), **base}
            version_item = _strip_none(
                {
                    "PK": _skillset_pk(skillset_id),
                    "SK": _version_sk(version),
                    "skillset_id": skillset_id,
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
            return _skillset_from_item(base)

        return await asyncio.to_thread(_op)

    async def delete_skillset(self, skillset_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False

            skill_list_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _skill_list_pk(skillset_id)},
                ProjectionExpression="SK",
            )
            skill_ids = [item["SK"].replace("SKILL#", "") for item in skill_list_resp.get("Items", [])]
            for skill_id in skill_ids:
                skill_items_resp = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": _skill_pk(skill_id)},
                    ProjectionExpression="PK, SK",
                )
                keys_to_delete = [{"PK": i["PK"], "SK": i["SK"]} for i in skill_items_resp.get("Items", [])]
                with table.batch_writer() as batch:
                    for key in keys_to_delete:
                        batch.delete_item(Key=key)

            skill_list_keys = [
                {"PK": _skill_list_pk(skillset_id), "SK": _skill_list_sk(skill_id)} for skill_id in skill_ids
            ]
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _skillset_pk(skillset_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [{"PK": item["PK"], "SK": item["SK"]} for item in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _PK_SKILLSET_LIST, "SK": _skillset_list_sk(skillset_id)})
            keys_to_delete.extend(skill_list_keys)

            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)

            return True

        return await asyncio.to_thread(_op)

    async def list_skillset_versions(self, skillset_id: str) -> list[SkillsetVersion]:
        def _op() -> list[SkillsetVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _skillset_pk(skillset_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_skillset_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_skillset_version(self, skillset_id: str, version: int) -> SkillsetVersion | None:
        def _op() -> SkillsetVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _version_sk(version)})
            item = resp.get("Item")
            if not item:
                return None
            return _skillset_version_from_item(item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    async def list_skills(self, skillset_id: str) -> list[SkillItem]:
        def _op() -> list[SkillItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _skill_list_pk(skillset_id)},
            )
            skill_ids = [item["SK"].replace("SKILL#", "") for item in resp.get("Items", [])]
            skills = []
            for skill_id in skill_ids:
                skill_resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _SK_METADATA})
                item = skill_resp.get("Item")
                if item:
                    skills.append(_skill_from_item(item))
            return skills

        return await asyncio.to_thread(_op)

    async def get_skill(self, skill_id: str) -> SkillItem | None:
        def _op() -> SkillItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _skill_from_item(item)

        return await asyncio.to_thread(_op)

    async def create_skill(
        self,
        skillset_id: str,
        skill_id: str,
        name: str,
        description: str,
        template: str,
        parameters: list[dict[str, Any]],
        triggers: list[str],
        tools_required: list[str],
        enabled: bool,
        created_by: str,
    ) -> SkillItem | None:
        def _op() -> SkillItem | None:
            table = _get_table()
            ss_resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA})
            if not ss_resp.get("Item"):
                return None

            now = datetime.now(tz=UTC).isoformat()
            version = 1
            base = _strip_none(
                {
                    "skill_id": skill_id,
                    "skillset_id": skillset_id,
                    "name": name,
                    "description": description,
                    "template": template,
                    "parameters": _floats_to_decimal(parameters),
                    "triggers": triggers,
                    "tools_required": tools_required,
                    "enabled": enabled,
                    "current_version": version,
                    "created_at": now,
                    "updated_at": now,
                    "created_by": created_by,
                    "updated_by": created_by,
                }
            )
            metadata_item = {"PK": _skill_pk(skill_id), "SK": _SK_METADATA, **base}
            list_item = {"PK": _skill_list_pk(skillset_id), "SK": _skill_list_sk(skill_id), **base}
            version_item = _strip_none(
                {
                    "PK": _skill_pk(skill_id),
                    "SK": _version_sk(version),
                    "skill_id": skill_id,
                    "skillset_id": skillset_id,
                    "name": name,
                    "description": description,
                    "template": template,
                    "parameters": _floats_to_decimal(parameters),
                    "triggers": triggers,
                    "tools_required": tools_required,
                    "enabled": enabled,
                    "version": version,
                    "created_at": now,
                    "created_by": created_by,
                    "comment": None,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _skill_from_item(base)

        return await asyncio.to_thread(_op)

    async def update_skill(
        self,
        skill_id: str,
        name: str,
        description: str,
        template: str,
        parameters: list[dict[str, Any]],
        triggers: list[str],
        tools_required: list[str],
        enabled: bool,
        updated_by: str,
        comment: str | None = None,
    ) -> SkillItem | None:
        def _op() -> SkillItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            skillset_id = existing["skillset_id"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
            base = _strip_none(
                {
                    "skill_id": skill_id,
                    "skillset_id": skillset_id,
                    "name": name,
                    "description": description,
                    "template": template,
                    "parameters": _floats_to_decimal(parameters),
                    "triggers": triggers,
                    "tools_required": tools_required,
                    "enabled": enabled,
                    "current_version": version,
                    "created_at": existing["created_at"],
                    "updated_at": now,
                    "created_by": existing["created_by"],
                    "updated_by": updated_by,
                }
            )
            metadata_item = {"PK": _skill_pk(skill_id), "SK": _SK_METADATA, **base}
            list_item = {"PK": _skill_list_pk(skillset_id), "SK": _skill_list_sk(skill_id), **base}
            version_item = _strip_none(
                {
                    "PK": _skill_pk(skill_id),
                    "SK": _version_sk(version),
                    "skill_id": skill_id,
                    "skillset_id": skillset_id,
                    "name": name,
                    "description": description,
                    "template": template,
                    "parameters": _floats_to_decimal(parameters),
                    "triggers": triggers,
                    "tools_required": tools_required,
                    "enabled": enabled,
                    "version": version,
                    "created_at": now,
                    "created_by": updated_by,
                    "comment": comment,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _skill_from_item(base)

        return await asyncio.to_thread(_op)

    async def delete_skill(self, skill_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return False
            skillset_id = item["skillset_id"]
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _skill_pk(skill_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [{"PK": i["PK"], "SK": i["SK"]} for i in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _skill_list_pk(skillset_id), "SK": _skill_list_sk(skill_id)})
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def list_skill_versions(self, skill_id: str) -> list[SkillVersion]:
        def _op() -> list[SkillVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _skill_pk(skill_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_skill_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_skill_version(self, skill_id: str, version: int) -> SkillVersion | None:
        def _op() -> SkillVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _version_sk(version)})
            item = resp.get("Item")
            if not item:
                return None
            return _skill_version_from_item(item)

        return await asyncio.to_thread(_op)

    async def list_enabled_skills(self) -> list[SkillItem]:
        def _op() -> list[SkillItem]:
            table = _get_table()
            ss_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_SKILLSET_LIST},
            )
            enabled_skillset_ids = [
                item["skillset_id"] for item in ss_resp.get("Items", []) if item.get("enabled", True)
            ]
            skills = []
            for skillset_id in enabled_skillset_ids:
                skill_list_resp = table.query(
                    KeyConditionExpression="PK = :pk",
                    ExpressionAttributeValues={":pk": _skill_list_pk(skillset_id)},
                )
                for list_item in skill_list_resp.get("Items", []):
                    if list_item.get("enabled", True):
                        skill_resp = table.get_item(
                            Key={
                                "PK": _skill_pk(list_item["skill_id"]),
                                "SK": _SK_METADATA,
                            }
                        )
                        item = skill_resp.get("Item")
                        if item and item.get("enabled", True):
                            skills.append(_skill_from_item(item))
            return skills

        return await asyncio.to_thread(_op)

    async def get_enabled_skill(self, skillset_id: str, skill_id: str) -> SkillItem | None:
        def _op() -> SkillItem | None:
            table = _get_table()
            skill_resp = table.get_item(Key={"PK": _skill_pk(skill_id), "SK": _SK_METADATA})
            skill_item = skill_resp.get("Item")
            if not skill_item or skill_item.get("skillset_id") != skillset_id or not skill_item.get("enabled", True):
                return None

            skillset_resp = table.get_item(Key={"PK": _skillset_pk(skillset_id), "SK": _SK_METADATA})
            skillset_item = skillset_resp.get("Item")
            if not skillset_item or not skillset_item.get("enabled", True):
                return None
            return _skill_from_item(skill_item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Roles (user-defined, versioned)
    # ------------------------------------------------------------------

    async def list_roles(self) -> list[RoleItem]:
        def _op() -> list[RoleItem]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _PK_ROLE_LIST},
            )
            return [_role_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_role(self, role_id: str) -> RoleItem | None:
        def _op() -> RoleItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _role_pk(role_id), "SK": _SK_METADATA})
            item = resp.get("Item")
            if not item:
                return None
            return _role_from_item(item)

        return await asyncio.to_thread(_op)

    async def get_role_by_name(self, name: str) -> RoleItem | None:
        def _op() -> RoleItem | None:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk",
                FilterExpression="#n = :name",
                ExpressionAttributeNames={"#n": "name"},
                ExpressionAttributeValues={":pk": _PK_ROLE_LIST, ":name": name},
            )
            items = resp.get("Items", [])
            if not items:
                return None
            return _role_from_item(items[0])

        return await asyncio.to_thread(_op)

    async def create_role(
        self,
        name: str,
        description: str,
        permissions: list[str],
        created_by: str,
    ) -> RoleItem:
        role_id = generate_report_id()
        now = datetime.now(tz=UTC).isoformat()
        version = 1
        base = _strip_none(
            {
                "role_id": role_id,
                "name": name,
                "description": description,
                "permissions": permissions,
                "current_version": version,
                "created_at": now,
                "updated_at": now,
                "created_by": created_by,
                "updated_by": created_by,
            }
        )
        metadata_item = {"PK": _role_pk(role_id), "SK": _SK_METADATA, **base}
        list_item = {"PK": _PK_ROLE_LIST, "SK": _role_list_sk(role_id), **base}
        version_item = _strip_none(
            {
                "PK": _role_pk(role_id),
                "SK": _version_sk(version),
                "role_id": role_id,
                "name": name,
                "description": description,
                "permissions": permissions,
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
        return _role_from_item(base)

    async def update_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: list[str],
        updated_by: str,
        comment: str | None = None,
    ) -> RoleItem | None:
        def _op() -> RoleItem | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _role_pk(role_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return None
            existing = resp["Item"]
            current_version = int(existing.get("current_version", 0))
            version = current_version + 1
            now = datetime.now(tz=UTC).isoformat()
            base = _strip_none(
                {
                    "role_id": role_id,
                    "name": name,
                    "description": description,
                    "permissions": permissions,
                    "current_version": version,
                    "created_at": existing["created_at"],
                    "updated_at": now,
                    "created_by": existing["created_by"],
                    "updated_by": updated_by,
                }
            )
            metadata_item = {"PK": _role_pk(role_id), "SK": _SK_METADATA, **base}
            list_item = {"PK": _PK_ROLE_LIST, "SK": _role_list_sk(role_id), **base}
            version_item = _strip_none(
                {
                    "PK": _role_pk(role_id),
                    "SK": _version_sk(version),
                    "role_id": role_id,
                    "name": name,
                    "description": description,
                    "permissions": permissions,
                    "version": version,
                    "created_at": now,
                    "created_by": updated_by,
                    "comment": comment,
                }
            )
            _transact_put_sync(table, metadata_item, list_item, version_item)
            return _role_from_item(base)

        return await asyncio.to_thread(_op)

    async def delete_role(self, role_id: str) -> bool:
        def _op() -> bool:
            table = _get_table()
            resp = table.get_item(Key={"PK": _role_pk(role_id), "SK": _SK_METADATA})
            if not resp.get("Item"):
                return False
            items_resp = table.query(
                KeyConditionExpression="PK = :pk",
                ExpressionAttributeValues={":pk": _role_pk(role_id)},
                ProjectionExpression="PK, SK",
            )
            keys_to_delete = [{"PK": item["PK"], "SK": item["SK"]} for item in items_resp.get("Items", [])]
            keys_to_delete.append({"PK": _PK_ROLE_LIST, "SK": _role_list_sk(role_id)})
            with table.batch_writer() as batch:
                for key in keys_to_delete:
                    batch.delete_item(Key=key)
            return True

        return await asyncio.to_thread(_op)

    async def list_role_versions(self, role_id: str) -> list[RoleVersion]:
        def _op() -> list[RoleVersion]:
            table = _get_table()
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": _role_pk(role_id),
                    ":prefix": _SK_VERSION_PREFIX,
                },
                ScanIndexForward=False,
            )
            return [_role_version_from_item(item) for item in resp.get("Items", [])]

        return await asyncio.to_thread(_op)

    async def get_role_version(self, role_id: str, version: int) -> RoleVersion | None:
        def _op() -> RoleVersion | None:
            table = _get_table()
            resp = table.get_item(Key={"PK": _role_pk(role_id), "SK": _version_sk(version)})
            item = resp.get("Item")
            if not item:
                return None
            return _role_version_from_item(item)

        return await asyncio.to_thread(_op)

    # ------------------------------------------------------------------
    # Query history
    # ------------------------------------------------------------------

    async def save_query_history(self, user_id: str, query: str) -> QueryHistoryItem:
        """Append a query execution to the user's history."""
        history_id = str(next(_get_snowflake_gen()))
        now = datetime.now(tz=UTC).isoformat()
        item = {
            "PK": _query_history_pk(user_id),
            "SK": _query_history_sk(history_id),
            "history_id": history_id,
            "user_id": user_id,
            "query": query,
            "executed_at": now,
        }

        def _op() -> None:
            table = _get_table()
            table.put_item(Item=_strip_none(item))

        await asyncio.to_thread(_op)
        return QueryHistoryItem(
            history_id=history_id,
            user_id=user_id,
            query=query,
            executed_at=now,
        )

    async def list_query_history(self, user_id: str, page: int, per_page: int) -> tuple[list[QueryHistoryItem], int]:
        """Return a paginated page of query history (newest first) and the total count."""

        def _op() -> tuple[list[QueryHistoryItem], int]:
            table = _get_table()
            pk = _query_history_pk(user_id)

            # Count (capped at _QUERY_HISTORY_MAX to bound the scan).
            count_resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": pk,
                    ":prefix": _SK_QUERY_HISTORY_PREFIX,
                },
                Select="COUNT",
                Limit=_QUERY_HISTORY_MAX,
            )
            total = count_resp.get("Count", 0)
            if total == 0:
                return [], 0

            # Fetch only as many items as needed to reach the end of the requested
            # page (DynamoDB has no OFFSET, so we scan from the start and slice).
            fetch_limit = page * per_page
            resp = table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
                ExpressionAttributeValues={
                    ":pk": pk,
                    ":prefix": _SK_QUERY_HISTORY_PREFIX,
                },
                ScanIndexForward=False,
                Limit=fetch_limit,
            )
            items = resp.get("Items", [])
            offset = (page - 1) * per_page
            paged = items[offset : offset + per_page]  # noqa: E203
            return [
                QueryHistoryItem(
                    history_id=it["history_id"],
                    user_id=it["user_id"],
                    query=it["query"],
                    executed_at=it["executed_at"],
                )
                for it in paged
            ], total

        return await asyncio.to_thread(_op)
