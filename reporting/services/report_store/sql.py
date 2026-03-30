import logging
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from snowflake import SnowflakeGenerator
from sqlalchemy import Column
from sqlalchemy import JSON
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col
from sqlmodel import Field
from sqlmodel import select
from sqlmodel import SQLModel

from reporting import settings
from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolParamDef
from reporting.schema.mcp_config import ToolsetListItem
from reporting.schema.mcp_config import ToolsetVersion
from reporting.schema.mcp_config import ToolVersion
from reporting.schema.rbac import RoleItem
from reporting.schema.rbac import RoleVersion
from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import QueryHistoryItem
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.report_config import ScheduledQueryVersion
from reporting.schema.report_config import User
from reporting.services.report_store.base import extract_panel_stats
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_snowflake_gen: Optional[SnowflakeGenerator] = None


# ---------------------------------------------------------------------------
# SQLModel table definitions
# ---------------------------------------------------------------------------


class ReportVersionRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "report_versions"
    __table_args__ = (UniqueConstraint("report_id", "version"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: str = Field(index=True)
    version: int
    config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON, nullable=False))
    created_at: str
    created_by: str
    comment: Optional[str] = None


class DashboardPointerRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "dashboard_pointer"
    id: int = Field(default=1, primary_key=True)
    report_id: str
    updated_at: str


class ReportRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "reports"
    report_id: str = Field(primary_key=True)
    name: str
    current_version: int = 0
    created_at: str
    updated_at: str


class UserRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("iss", "sub"),)
    user_id: str = Field(primary_key=True)
    sub: str
    iss: str
    email: str
    display_name: Optional[str] = None
    created_at: str
    last_login: str
    archived_at: Optional[str] = None


class PanelStatRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "panel_stats"
    id: Optional[int] = Field(default=None, primary_key=True)
    report_id: str = Field(index=True)
    metric: str
    panel_type: str
    cypher: str
    static_params: Dict[str, Any] = Field(
        default={}, sa_column=Column(JSON, nullable=False)
    )
    input_param_name: Optional[str] = None
    input_cypher: Optional[str] = None


class ScheduledQueryRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "scheduled_queries"
    scheduled_query_id: str = Field(primary_key=True)
    name: str
    cypher: str
    params: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    frequency: Optional[int] = None
    watch_scans: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    enabled: bool = True
    actions: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None


class ScheduledQueryVersionRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "scheduled_query_versions"
    __table_args__ = (UniqueConstraint("scheduled_query_id", "version"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    scheduled_query_id: str = Field(index=True)
    version: int
    cypher: str
    params: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    frequency: Optional[int] = None
    watch_scans: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    enabled: bool = True
    actions: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    created_at: str
    created_by: str
    comment: Optional[str] = None


class ToolsetRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "toolsets"
    toolset_id: str = Field(primary_key=True)
    name: str
    description: str = ""
    enabled: bool = True
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None


class ToolsetVersionRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "toolset_versions"
    __table_args__ = (UniqueConstraint("toolset_id", "version"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    toolset_id: str = Field(index=True)
    version: int
    name: str
    description: str = ""
    enabled: bool = True
    created_at: str
    created_by: str
    comment: Optional[str] = None


class ToolRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "tools"
    tool_id: str = Field(primary_key=True)
    toolset_id: str = Field(index=True)
    name: str
    description: str = ""
    cypher: str
    parameters: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    enabled: bool = True
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None


class ToolVersionRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "tool_versions"
    __table_args__ = (UniqueConstraint("tool_id", "version"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    tool_id: str = Field(index=True)
    toolset_id: str
    version: int
    name: str
    description: str = ""
    cypher: str
    parameters: List[Dict[str, Any]] = Field(
        default=[], sa_column=Column(JSON, nullable=False)
    )
    enabled: bool = True
    created_at: str
    created_by: str
    comment: Optional[str] = None


class QueryHistoryRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "query_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    history_id: str = Field(unique=True)
    user_id: str = Field(index=True)
    query: str
    executed_at: str


class RoleRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "roles"
    role_id: str = Field(primary_key=True)
    name: str = Field(unique=True)
    description: str = ""
    permissions: List[str] = Field(default=[], sa_column=Column(JSON, nullable=False))
    current_version: int = 0
    created_at: str
    updated_at: str
    created_by: str
    updated_by: Optional[str] = None


class RoleVersionRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "role_versions"
    __table_args__ = (UniqueConstraint("role_id", "version"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    role_id: str = Field(index=True)
    version: int
    name: str
    description: str = ""
    permissions: List[str] = Field(default=[], sa_column=Column(JSON, nullable=False))
    created_at: str
    created_by: str
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _get_snowflake_gen() -> SnowflakeGenerator:
    global _snowflake_gen
    if _snowflake_gen is None:
        _snowflake_gen = SnowflakeGenerator(settings.SNOWFLAKE_MACHINE_ID)
    return _snowflake_gen


def generate_report_id() -> str:
    return str(next(_get_snowflake_gen()))


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = settings.SQL_DATABASE_URL
        # Replace sync postgresql:// with async postgresql+asyncpg://
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite:"):
            # sqlite+aiosqlite for async sqlite (not commonly used in prod)
            url = url.replace("sqlite:", "sqlite+aiosqlite:", 1)
        _engine = create_async_engine(url)
    return _engine


# ---------------------------------------------------------------------------
# SQL backend implementation
# ---------------------------------------------------------------------------


class SQLModelReportStore(ReportStore):
    """ReportStore implementation backed by any SQLAlchemy-compatible database.

    Configured via the ``SQL_DATABASE_URL`` setting.
    """

    async def initialize(self) -> None:
        """Create all tables if they do not already exist."""
        try:
            async with _get_engine().begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("SQL report store tables initialised")
        except IntegrityError:
            logger.info("SQL report store tables already exist")

    async def list_reports(self) -> List[ReportListItem]:
        async with AsyncSession(_get_engine()) as session:
            result = await session.execute(select(ReportRecord))
            rows = result.scalars().all()
            return [
                ReportListItem(
                    report_id=r.report_id,
                    name=r.name,
                    current_version=r.current_version,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    async def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        async with AsyncSession(_get_engine()) as session:
            report = await session.get(ReportRecord, report_id)
            if not report:
                return None
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .order_by(col(ReportVersionRecord.version).desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row:
                return None
            return ReportVersion(
                report_id=row.report_id,
                name=report.name,
                version=row.version,
                config=row.config,
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    async def get_report_version(
        self, report_id: str, version: int
    ) -> Optional[ReportVersion]:
        async with AsyncSession(_get_engine()) as session:
            report = await session.get(ReportRecord, report_id)
            if not report:
                return None
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .where(ReportVersionRecord.version == version)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row:
                return None
            return ReportVersion(
                report_id=row.report_id,
                name=report.name,
                version=row.version,
                config=row.config,
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    async def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        async with AsyncSession(_get_engine()) as session:
            report = await session.get(ReportRecord, report_id)
            if not report:
                return []
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .order_by(col(ReportVersionRecord.version).desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                ReportVersion(
                    report_id=r.report_id,
                    name=report.name,
                    version=r.version,
                    config=r.config,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    comment=r.comment,
                )
                for r in rows
            ]

    async def create_report(
        self,
        name: str,
        created_by: str,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""
        report_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()

        async with AsyncSession(_get_engine()) as session:
            session.add(
                ReportRecord(
                    report_id=report_id,
                    name=name,
                    current_version=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

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
        async with AsyncSession(_get_engine()) as session:
            report = await session.get(ReportRecord, report_id)
            if not report:
                return None

            version = report.current_version + 1
            name = report.name
            now = datetime.now(tz=timezone.utc).isoformat()

            session.add(
                ReportVersionRecord(
                    report_id=report_id,
                    version=version,
                    config=config,
                    created_at=now,
                    created_by=created_by,
                    comment=comment,
                )
            )
            report.current_version = version
            report.updated_at = now
            session.add(report)

            # Replace panel stats for this report atomically with the version write.
            old_stats_stmt = select(PanelStatRecord).where(
                PanelStatRecord.report_id == report_id
            )
            old_stats_result = await session.execute(old_stats_stmt)
            for old_stat in old_stats_result.scalars().all():
                await session.delete(old_stat)
            for stat in extract_panel_stats(report_id, config):
                session.add(
                    PanelStatRecord(
                        report_id=report_id,
                        metric=stat.metric,
                        panel_type=stat.panel_type,
                        cypher=stat.cypher,
                        static_params=stat.static_params,
                        input_param_name=stat.input_param_name,
                        input_cypher=stat.input_cypher,
                    )
                )

            await session.commit()

        return ReportVersion(
            report_id=report_id,
            name=name,
            version=version,
            config=config,
            created_at=now,
            created_by=created_by,
            comment=comment,
        )

    async def delete_report(self, report_id: str) -> bool:
        """Delete a report and all its versions."""
        async with AsyncSession(_get_engine()) as session:
            report = await session.get(ReportRecord, report_id)
            if not report:
                return False

            pointer = await session.get(DashboardPointerRecord, 1)
            if pointer and pointer.report_id == report_id:
                await session.delete(pointer)

            stmt = select(ReportVersionRecord).where(
                ReportVersionRecord.report_id == report_id
            )
            result = await session.execute(stmt)
            for version_record in result.scalars().all():
                await session.delete(version_record)

            stats_stmt = select(PanelStatRecord).where(
                PanelStatRecord.report_id == report_id
            )
            stats_result = await session.execute(stats_stmt)
            for stat_record in stats_result.scalars().all():
                await session.delete(stat_record)

            await session.delete(report)
            await session.commit()
        return True

    async def get_dashboard_report_id(self) -> Optional[str]:
        async with AsyncSession(_get_engine()) as session:
            row = await session.get(DashboardPointerRecord, 1)
            if not row:
                return None
            return row.report_id

    async def set_dashboard_report(self, report_id: str) -> bool:
        async with AsyncSession(_get_engine()) as session:
            exists = await session.get(ReportRecord, report_id)
            if not exists:
                return False
            now = datetime.now(tz=timezone.utc).isoformat()
            existing = await session.get(DashboardPointerRecord, 1)
            if existing:
                existing.report_id = report_id
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    DashboardPointerRecord(id=1, report_id=report_id, updated_at=now)
                )
            await session.commit()
        return True

    async def get_dashboard_report(self) -> Optional[ReportVersion]:
        report_id = await self.get_dashboard_report_id()
        if not report_id:
            return None
        return await self.get_report_latest(report_id)

    async def list_panel_stats(self) -> List[PanelStat]:
        """Return all PanelStat records across all reports."""
        async with AsyncSession(_get_engine()) as session:
            result = await session.execute(select(PanelStatRecord))
            rows = result.scalars().all()
            return [
                PanelStat(
                    report_id=r.report_id,
                    metric=r.metric,
                    panel_type=r.panel_type,
                    cypher=r.cypher,
                    static_params=r.static_params or {},
                    input_param_name=r.input_param_name,
                    input_cypher=r.input_cypher,
                )
                for r in rows
            ]

    async def list_scheduled_queries(self) -> List[ScheduledQueryItem]:
        async with AsyncSession(_get_engine()) as session:
            result = await session.execute(select(ScheduledQueryRecord))
            rows = result.scalars().all()
            return [
                ScheduledQueryItem(
                    scheduled_query_id=r.scheduled_query_id,
                    name=r.name,
                    cypher=r.cypher,
                    params=r.params or [],
                    frequency=r.frequency,
                    watch_scans=r.watch_scans or [],
                    enabled=r.enabled,
                    actions=r.actions or [],
                    current_version=r.current_version,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    created_by=r.created_by,
                    updated_by=r.updated_by,
                )
                for r in rows
            ]

    async def get_scheduled_query(self, sq_id: str) -> Optional[ScheduledQueryItem]:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ScheduledQueryRecord, sq_id)
            if not record:
                return None
            return ScheduledQueryItem(
                scheduled_query_id=record.scheduled_query_id,
                name=record.name,
                cypher=record.cypher,
                params=record.params or [],
                frequency=record.frequency,
                watch_scans=record.watch_scans or [],
                enabled=record.enabled,
                actions=record.actions or [],
                current_version=record.current_version,
                created_at=record.created_at,
                updated_at=record.updated_at,
                created_by=record.created_by,
                updated_by=record.updated_by,
            )

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
        async with AsyncSession(_get_engine()) as session:
            record = ScheduledQueryRecord(
                scheduled_query_id=sq_id,
                name=name,
                cypher=cypher,
                params=params,
                frequency=frequency,
                watch_scans=watch_scans,
                enabled=enabled,
                actions=actions,
                current_version=version,
                created_at=now,
                updated_at=now,
                created_by=created_by,
                updated_by=created_by,
            )
            session.add(record)
            session.add(
                ScheduledQueryVersionRecord(
                    scheduled_query_id=sq_id,
                    version=version,
                    cypher=cypher,
                    params=params,
                    frequency=frequency,
                    watch_scans=watch_scans,
                    enabled=enabled,
                    actions=actions,
                    created_at=now,
                    created_by=created_by,
                    comment=None,
                )
            )
            await session.commit()
        return ScheduledQueryItem(
            scheduled_query_id=sq_id,
            name=name,
            cypher=cypher,
            params=params,
            frequency=frequency,
            watch_scans=watch_scans,
            enabled=enabled,
            actions=actions,
            current_version=version,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

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
        now = datetime.now(tz=timezone.utc).isoformat()
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ScheduledQueryRecord, sq_id)
            if not record:
                return None
            original_created_at = record.created_at
            original_created_by = record.created_by
            version = record.current_version + 1
            record.name = name
            record.cypher = cypher
            record.params = params
            record.frequency = frequency
            record.watch_scans = watch_scans
            record.enabled = enabled
            record.actions = actions
            record.current_version = version
            record.updated_at = now
            record.updated_by = updated_by
            session.add(record)
            session.add(
                ScheduledQueryVersionRecord(
                    scheduled_query_id=sq_id,
                    version=version,
                    cypher=cypher,
                    params=params,
                    frequency=frequency,
                    watch_scans=watch_scans,
                    enabled=enabled,
                    actions=actions,
                    created_at=now,
                    created_by=updated_by,
                    comment=comment,
                )
            )
            await session.commit()
        return ScheduledQueryItem(
            scheduled_query_id=sq_id,
            name=name,
            cypher=cypher,
            params=params,
            frequency=frequency,
            watch_scans=watch_scans,
            enabled=enabled,
            actions=actions,
            current_version=version,
            created_at=original_created_at,
            updated_at=now,
            created_by=original_created_by,
            updated_by=updated_by,
        )

    async def list_scheduled_query_versions(
        self, sq_id: str
    ) -> List[ScheduledQueryVersion]:
        async with AsyncSession(_get_engine()) as session:
            sq = await session.get(ScheduledQueryRecord, sq_id)
            if not sq:
                return []
            stmt = (
                select(ScheduledQueryVersionRecord)
                .where(ScheduledQueryVersionRecord.scheduled_query_id == sq_id)
                .order_by(col(ScheduledQueryVersionRecord.version).desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                ScheduledQueryVersion(
                    scheduled_query_id=r.scheduled_query_id,
                    name=sq.name,
                    version=r.version,
                    cypher=r.cypher,
                    params=r.params or [],
                    frequency=r.frequency,
                    watch_scans=r.watch_scans or [],
                    enabled=r.enabled,
                    actions=r.actions or [],
                    created_at=r.created_at,
                    created_by=r.created_by,
                    comment=r.comment,
                )
                for r in rows
            ]

    async def get_scheduled_query_version(
        self, sq_id: str, version: int
    ) -> Optional[ScheduledQueryVersion]:
        async with AsyncSession(_get_engine()) as session:
            sq = await session.get(ScheduledQueryRecord, sq_id)
            if not sq:
                return None
            stmt = (
                select(ScheduledQueryVersionRecord)
                .where(ScheduledQueryVersionRecord.scheduled_query_id == sq_id)
                .where(ScheduledQueryVersionRecord.version == version)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row:
                return None
            return ScheduledQueryVersion(
                scheduled_query_id=row.scheduled_query_id,
                name=sq.name,
                version=row.version,
                cypher=row.cypher,
                params=row.params or [],
                frequency=row.frequency,
                watch_scans=row.watch_scans or [],
                enabled=row.enabled,
                actions=row.actions or [],
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    async def delete_scheduled_query(self, sq_id: str) -> bool:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ScheduledQueryRecord, sq_id)
            if not record:
                return False
            stmt = select(ScheduledQueryVersionRecord).where(
                ScheduledQueryVersionRecord.scheduled_query_id == sq_id
            )
            result = await session.execute(stmt)
            for ver in result.scalars().all():
                await session.delete(ver)
            await session.delete(record)
            await session.commit()
        return True

    async def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: Optional[str] = None,
    ) -> User:
        now = datetime.now(tz=timezone.utc).isoformat()
        async with AsyncSession(_get_engine()) as session:
            stmt = (
                select(UserRecord)
                .where(UserRecord.iss == iss)
                .where(UserRecord.sub == sub)
            )
            result = await session.execute(stmt)
            record = result.scalars().first()
            if not record:
                user_id = generate_report_id()
                record = UserRecord(
                    user_id=user_id,
                    sub=sub,
                    iss=iss,
                    email=email,
                    display_name=display_name,
                    created_at=now,
                    last_login=now,
                    archived_at=None,
                )
                session.add(record)
                await session.commit()
                await session.refresh(record)
        return User(
            user_id=record.user_id,
            sub=record.sub,
            iss=record.iss,
            email=record.email,
            display_name=record.display_name,
            created_at=record.created_at,
            last_login=record.last_login,
            archived_at=record.archived_at,
        )

    async def update_user_profile(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        token_iat: Optional[datetime] = None,
    ) -> User:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(UserRecord, user_id)
            if not record:
                raise ValueError(f"User {user_id!r} not found")
            changed = False
            if record.email != email:
                record.email = email
                changed = True
            if display_name is not None and record.display_name != display_name:
                record.display_name = display_name
                changed = True
            if token_iat is not None:
                stored = datetime.fromisoformat(record.last_login)
                if token_iat > stored:
                    record.last_login = token_iat.isoformat()
                    changed = True
            if changed:
                session.add(record)
                await session.commit()
                await session.refresh(record)
        return User(
            user_id=record.user_id,
            sub=record.sub,
            iss=record.iss,
            email=record.email,
            display_name=record.display_name,
            created_at=record.created_at,
            last_login=record.last_login,
            archived_at=record.archived_at,
        )

    async def get_user(self, user_id: str) -> Optional[User]:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(UserRecord, user_id)
            if not record:
                return None
            return User(
                user_id=record.user_id,
                sub=record.sub,
                iss=record.iss,
                email=record.email,
                display_name=record.display_name,
                created_at=record.created_at,
                last_login=record.last_login,
                archived_at=record.archived_at,
            )

    async def archive_user(self, user_id: str) -> bool:
        now = datetime.now(tz=timezone.utc).isoformat()
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(UserRecord, user_id)
            if not record:
                return False
            record.archived_at = now
            session.add(record)
            await session.commit()
        return True

    # ------------------------------------------------------------------
    # Toolsets
    # ------------------------------------------------------------------

    def _toolset_item_from_record(self, record: ToolsetRecord) -> ToolsetListItem:
        return ToolsetListItem(
            toolset_id=record.toolset_id,
            name=record.name,
            description=record.description or "",
            enabled=record.enabled,
            current_version=record.current_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by=record.created_by,
            updated_by=record.updated_by,
        )

    async def list_toolsets(self) -> List[ToolsetListItem]:
        async with AsyncSession(_get_engine()) as session:
            result = await session.execute(select(ToolsetRecord))
            rows = result.scalars().all()
            return [self._toolset_item_from_record(r) for r in rows]

    async def get_toolset(self, toolset_id: str) -> Optional[ToolsetListItem]:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolsetRecord, toolset_id)
            if not record:
                return None
            return self._toolset_item_from_record(record)

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
        async with AsyncSession(_get_engine()) as session:
            record = ToolsetRecord(
                toolset_id=toolset_id,
                name=name,
                description=description,
                enabled=enabled,
                current_version=version,
                created_at=now,
                updated_at=now,
                created_by=created_by,
                updated_by=created_by,
            )
            session.add(record)
            session.add(
                ToolsetVersionRecord(
                    toolset_id=toolset_id,
                    version=version,
                    name=name,
                    description=description,
                    enabled=enabled,
                    created_at=now,
                    created_by=created_by,
                    comment=None,
                )
            )
            await session.commit()
        return ToolsetListItem(
            toolset_id=toolset_id,
            name=name,
            description=description,
            enabled=enabled,
            current_version=version,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

    async def update_toolset(
        self,
        toolset_id: str,
        name: str,
        description: str,
        enabled: bool,
        updated_by: str,
        comment: Optional[str] = None,
    ) -> Optional[ToolsetListItem]:
        now = datetime.now(tz=timezone.utc).isoformat()
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolsetRecord, toolset_id)
            if not record:
                return None
            original_created_at = record.created_at
            original_created_by = record.created_by
            version = record.current_version + 1
            record.name = name
            record.description = description
            record.enabled = enabled
            record.current_version = version
            record.updated_at = now
            record.updated_by = updated_by
            session.add(record)
            session.add(
                ToolsetVersionRecord(
                    toolset_id=toolset_id,
                    version=version,
                    name=name,
                    description=description,
                    enabled=enabled,
                    created_at=now,
                    created_by=updated_by,
                    comment=comment,
                )
            )
            await session.commit()
        return ToolsetListItem(
            toolset_id=toolset_id,
            name=name,
            description=description,
            enabled=enabled,
            current_version=version,
            created_at=original_created_at,
            updated_at=now,
            created_by=original_created_by,
            updated_by=updated_by,
        )

    async def delete_toolset(self, toolset_id: str) -> bool:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolsetRecord, toolset_id)
            if not record:
                return False

            # Delete all tools and their versions
            tools_stmt = select(ToolRecord).where(ToolRecord.toolset_id == toolset_id)
            tools_result = await session.execute(tools_stmt)
            for tool_record in tools_result.scalars().all():
                versions_stmt = select(ToolVersionRecord).where(
                    ToolVersionRecord.tool_id == tool_record.tool_id
                )
                versions_result = await session.execute(versions_stmt)
                for ver in versions_result.scalars().all():
                    await session.delete(ver)
                await session.delete(tool_record)

            # Delete all toolset versions
            ts_versions_stmt = select(ToolsetVersionRecord).where(
                ToolsetVersionRecord.toolset_id == toolset_id
            )
            ts_versions_result = await session.execute(ts_versions_stmt)
            for ver in ts_versions_result.scalars().all():
                await session.delete(ver)

            await session.delete(record)
            await session.commit()
        return True

    async def list_toolset_versions(self, toolset_id: str) -> List[ToolsetVersion]:
        async with AsyncSession(_get_engine()) as session:
            ts = await session.get(ToolsetRecord, toolset_id)
            if not ts:
                return []
            stmt = (
                select(ToolsetVersionRecord)
                .where(ToolsetVersionRecord.toolset_id == toolset_id)
                .order_by(col(ToolsetVersionRecord.version).desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                ToolsetVersion(
                    toolset_id=r.toolset_id,
                    name=r.name,
                    description=r.description or "",
                    enabled=r.enabled,
                    version=r.version,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    comment=r.comment,
                )
                for r in rows
            ]

    async def get_toolset_version(
        self, toolset_id: str, version: int
    ) -> Optional[ToolsetVersion]:
        async with AsyncSession(_get_engine()) as session:
            stmt = (
                select(ToolsetVersionRecord)
                .where(ToolsetVersionRecord.toolset_id == toolset_id)
                .where(ToolsetVersionRecord.version == version)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row:
                return None
            return ToolsetVersion(
                toolset_id=row.toolset_id,
                name=row.name,
                description=row.description or "",
                enabled=row.enabled,
                version=row.version,
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def _tool_item_from_record(self, record: ToolRecord) -> ToolItem:
        return ToolItem(
            tool_id=record.tool_id,
            toolset_id=record.toolset_id,
            name=record.name,
            description=record.description or "",
            cypher=record.cypher,
            parameters=[
                ToolParamDef(**p) if isinstance(p, dict) else p
                for p in (record.parameters or [])
            ],
            enabled=record.enabled,
            current_version=record.current_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
            created_by=record.created_by,
            updated_by=record.updated_by,
        )

    async def list_tools(self, toolset_id: str) -> List[ToolItem]:
        async with AsyncSession(_get_engine()) as session:
            stmt = select(ToolRecord).where(ToolRecord.toolset_id == toolset_id)
            result = await session.execute(stmt)
            return [self._tool_item_from_record(r) for r in result.scalars().all()]

    async def get_tool(self, tool_id: str) -> Optional[ToolItem]:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolRecord, tool_id)
            if not record:
                return None
            return self._tool_item_from_record(record)

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
        async with AsyncSession(_get_engine()) as session:
            ts = await session.get(ToolsetRecord, toolset_id)
            if not ts:
                return None
            tool_id = generate_report_id()
            now = datetime.now(tz=timezone.utc).isoformat()
            version = 1
            record = ToolRecord(
                tool_id=tool_id,
                toolset_id=toolset_id,
                name=name,
                description=description,
                cypher=cypher,
                parameters=parameters,
                enabled=enabled,
                current_version=version,
                created_at=now,
                updated_at=now,
                created_by=created_by,
                updated_by=created_by,
            )
            session.add(record)
            session.add(
                ToolVersionRecord(
                    tool_id=tool_id,
                    toolset_id=toolset_id,
                    version=version,
                    name=name,
                    description=description,
                    cypher=cypher,
                    parameters=parameters,
                    enabled=enabled,
                    created_at=now,
                    created_by=created_by,
                    comment=None,
                )
            )
            await session.commit()
        return ToolItem(
            tool_id=tool_id,
            toolset_id=toolset_id,
            name=name,
            description=description,
            cypher=cypher,
            parameters=[
                ToolParamDef(**p) if isinstance(p, dict) else p for p in parameters
            ],
            enabled=enabled,
            current_version=version,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

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
        now = datetime.now(tz=timezone.utc).isoformat()
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolRecord, tool_id)
            if not record:
                return None
            toolset_id = record.toolset_id
            original_created_at = record.created_at
            original_created_by = record.created_by
            version = record.current_version + 1
            record.name = name
            record.description = description
            record.cypher = cypher
            record.parameters = parameters
            record.enabled = enabled
            record.current_version = version
            record.updated_at = now
            record.updated_by = updated_by
            session.add(record)
            session.add(
                ToolVersionRecord(
                    tool_id=tool_id,
                    toolset_id=toolset_id,
                    version=version,
                    name=name,
                    description=description,
                    cypher=cypher,
                    parameters=parameters,
                    enabled=enabled,
                    created_at=now,
                    created_by=updated_by,
                    comment=comment,
                )
            )
            await session.commit()
        return ToolItem(
            tool_id=tool_id,
            toolset_id=toolset_id,
            name=name,
            description=description,
            cypher=cypher,
            parameters=[
                ToolParamDef(**p) if isinstance(p, dict) else p for p in parameters
            ],
            enabled=enabled,
            current_version=version,
            created_at=original_created_at,
            updated_at=now,
            created_by=original_created_by,
            updated_by=updated_by,
        )

    async def delete_tool(self, tool_id: str) -> bool:
        async with AsyncSession(_get_engine()) as session:
            record = await session.get(ToolRecord, tool_id)
            if not record:
                return False
            stmt = select(ToolVersionRecord).where(ToolVersionRecord.tool_id == tool_id)
            result = await session.execute(stmt)
            for ver in result.scalars().all():
                await session.delete(ver)
            await session.delete(record)
            await session.commit()
        return True

    async def list_tool_versions(self, tool_id: str) -> List[ToolVersion]:
        async with AsyncSession(_get_engine()) as session:
            tool = await session.get(ToolRecord, tool_id)
            if not tool:
                return []
            stmt = (
                select(ToolVersionRecord)
                .where(ToolVersionRecord.tool_id == tool_id)
                .order_by(col(ToolVersionRecord.version).desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                ToolVersion(
                    tool_id=r.tool_id,
                    toolset_id=r.toolset_id,
                    name=r.name,
                    description=r.description or "",
                    cypher=r.cypher,
                    parameters=[
                        ToolParamDef(**p) if isinstance(p, dict) else p
                        for p in (r.parameters or [])
                    ],
                    enabled=r.enabled,
                    version=r.version,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    comment=r.comment,
                )
                for r in rows
            ]

    async def get_tool_version(
        self, tool_id: str, version: int
    ) -> Optional[ToolVersion]:
        async with AsyncSession(_get_engine()) as session:
            stmt = (
                select(ToolVersionRecord)
                .where(ToolVersionRecord.tool_id == tool_id)
                .where(ToolVersionRecord.version == version)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            if not row:
                return None
            return ToolVersion(
                tool_id=row.tool_id,
                toolset_id=row.toolset_id,
                name=row.name,
                description=row.description or "",
                cypher=row.cypher,
                parameters=[
                    ToolParamDef(**p) if isinstance(p, dict) else p
                    for p in (row.parameters or [])
                ],
                enabled=row.enabled,
                version=row.version,
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    async def list_enabled_tools(self) -> List[ToolItem]:
        from sqlmodel import col

        async with AsyncSession(_get_engine()) as session:
            ts_stmt = select(ToolsetRecord).where(
                col(ToolsetRecord.enabled) == True  # noqa: E712
            )
            ts_result = await session.execute(ts_stmt)
            enabled_toolset_ids = [r.toolset_id for r in ts_result.scalars().all()]
            if not enabled_toolset_ids:
                return []
            tool_stmt = (
                select(ToolRecord)
                .where(col(ToolRecord.toolset_id).in_(enabled_toolset_ids))
                .where(col(ToolRecord.enabled) == True)  # noqa: E712
            )
            tool_result = await session.execute(tool_stmt)
            return [self._tool_item_from_record(r) for r in tool_result.scalars().all()]

    # ------------------------------------------------------------------
    # Query history
    # ------------------------------------------------------------------

    async def save_query_history(self, user_id: str, query: str) -> QueryHistoryItem:
        """Append a query execution to the user's history."""
        history_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()
        record = QueryHistoryRecord(
            history_id=history_id,
            user_id=user_id,
            query=query,
            executed_at=now,
        )
        async with AsyncSession(_get_engine()) as session:
            session.add(record)
            await session.commit()
        return QueryHistoryItem(
            history_id=history_id,
            user_id=user_id,
            query=query,
            executed_at=now,
        )

    async def list_query_history(
        self, user_id: str, page: int, per_page: int
    ) -> tuple[List[QueryHistoryItem], int]:
        """Return a paginated page of query history (newest first) and the total count."""
        from sqlalchemy import func

        async with AsyncSession(_get_engine()) as session:
            count_stmt = (
                select(func.count())
                .select_from(QueryHistoryRecord)
                .where(col(QueryHistoryRecord.user_id) == user_id)
            )
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            offset = (page - 1) * per_page
            page_stmt = (
                select(QueryHistoryRecord)
                .where(col(QueryHistoryRecord.user_id) == user_id)
                .order_by(col(QueryHistoryRecord.id).desc())
                .offset(offset)
                .limit(per_page)
            )
            page_result = await session.execute(page_stmt)
            rows = page_result.scalars().all()
            return [
                QueryHistoryItem(
                    history_id=r.history_id,
                    user_id=r.user_id,
                    query=r.query,
                    executed_at=r.executed_at,
                )
                for r in rows
            ], total

    # ------------------------------------------------------------------
    # Roles (user-defined, versioned)
    # ------------------------------------------------------------------

    async def list_roles(self) -> List[RoleItem]:
        async with AsyncSession(_get_engine()) as session:
            result = await session.execute(select(RoleRecord))
            rows = result.scalars().all()
            return [
                RoleItem(
                    role_id=r.role_id,
                    name=r.name,
                    description=r.description,
                    permissions=r.permissions,
                    current_version=r.current_version,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    created_by=r.created_by,
                    updated_by=r.updated_by,
                )
                for r in rows
            ]

    async def get_role(self, role_id: str) -> Optional[RoleItem]:
        async with AsyncSession(_get_engine()) as session:
            r = await session.get(RoleRecord, role_id)
            if not r:
                return None
            return RoleItem(
                role_id=r.role_id,
                name=r.name,
                description=r.description,
                permissions=r.permissions,
                current_version=r.current_version,
                created_at=r.created_at,
                updated_at=r.updated_at,
                created_by=r.created_by,
                updated_by=r.updated_by,
            )

    async def get_role_by_name(self, name: str) -> Optional[RoleItem]:
        async with AsyncSession(_get_engine()) as session:
            stmt = select(RoleRecord).where(col(RoleRecord.name) == name)
            result = await session.execute(stmt)
            r = result.scalars().first()
            if not r:
                return None
            return RoleItem(
                role_id=r.role_id,
                name=r.name,
                description=r.description,
                permissions=r.permissions,
                current_version=r.current_version,
                created_at=r.created_at,
                updated_at=r.updated_at,
                created_by=r.created_by,
                updated_by=r.updated_by,
            )

    async def create_role(
        self,
        name: str,
        description: str,
        permissions: List[str],
        created_by: str,
    ) -> RoleItem:
        role_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()
        version = 1
        async with AsyncSession(_get_engine()) as session:
            session.add(
                RoleRecord(
                    role_id=role_id,
                    name=name,
                    description=description,
                    permissions=permissions,
                    current_version=version,
                    created_at=now,
                    updated_at=now,
                    created_by=created_by,
                    updated_by=created_by,
                )
            )
            session.add(
                RoleVersionRecord(
                    role_id=role_id,
                    version=version,
                    name=name,
                    description=description,
                    permissions=permissions,
                    created_at=now,
                    created_by=created_by,
                )
            )
            await session.commit()
        return RoleItem(
            role_id=role_id,
            name=name,
            description=description,
            permissions=permissions,
            current_version=version,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )

    async def update_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: List[str],
        updated_by: str,
        comment: Optional[str] = None,
    ) -> Optional[RoleItem]:
        async with AsyncSession(_get_engine()) as session:
            r = await session.get(RoleRecord, role_id)
            if not r:
                return None
            now = datetime.now(tz=timezone.utc).isoformat()
            version = r.current_version + 1
            r.name = name
            r.description = description
            r.permissions = permissions
            r.current_version = version
            r.updated_at = now
            r.updated_by = updated_by
            session.add(r)
            session.add(
                RoleVersionRecord(
                    role_id=role_id,
                    version=version,
                    name=name,
                    description=description,
                    permissions=permissions,
                    created_at=now,
                    created_by=updated_by,
                    comment=comment,
                )
            )
            await session.commit()
            await session.refresh(r)
            return RoleItem(
                role_id=r.role_id,
                name=r.name,
                description=r.description,
                permissions=r.permissions,
                current_version=r.current_version,
                created_at=r.created_at,
                updated_at=r.updated_at,
                created_by=r.created_by,
                updated_by=r.updated_by,
            )

    async def delete_role(self, role_id: str) -> bool:
        async with AsyncSession(_get_engine()) as session:
            r = await session.get(RoleRecord, role_id)
            if not r:
                return False
            stmt = select(RoleVersionRecord).where(
                col(RoleVersionRecord.role_id) == role_id
            )
            result = await session.execute(stmt)
            for row in result.scalars().all():
                await session.delete(row)
            await session.delete(r)
            await session.commit()
            return True

    async def list_role_versions(self, role_id: str) -> List[RoleVersion]:
        async with AsyncSession(_get_engine()) as session:
            stmt = (
                select(RoleVersionRecord)
                .where(col(RoleVersionRecord.role_id) == role_id)
                .order_by(col(RoleVersionRecord.version).desc())
            )
            result = await session.execute(stmt)
            return [
                RoleVersion(
                    role_id=r.role_id,
                    name=r.name,
                    description=r.description,
                    permissions=r.permissions,
                    version=r.version,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    comment=r.comment,
                )
                for r in result.scalars().all()
            ]

    async def get_role_version(
        self, role_id: str, version: int
    ) -> Optional[RoleVersion]:
        async with AsyncSession(_get_engine()) as session:
            stmt = (
                select(RoleVersionRecord)
                .where(col(RoleVersionRecord.role_id) == role_id)
                .where(col(RoleVersionRecord.version) == version)
            )
            result = await session.execute(stmt)
            r = result.scalars().first()
            if not r:
                return None
            return RoleVersion(
                role_id=r.role_id,
                name=r.name,
                description=r.description,
                permissions=r.permissions,
                version=r.version,
                created_at=r.created_at,
                created_by=r.created_by,
                comment=r.comment,
            )

    # ------------------------------------------------------------------
