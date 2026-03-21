import logging
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from snowflake import SnowflakeGenerator
from sqlalchemy import Column
from sqlalchemy import Engine
from sqlalchemy import JSON
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlmodel import col
from sqlmodel import create_engine
from sqlmodel import Field
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel

from reporting import settings
from reporting.schema.report_config import PanelStat
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import User
from reporting.services.report_store.base import extract_panel_stats
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

_engine = None
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


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = settings.SQL_DATABASE_URL
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args)
    return _engine


# ---------------------------------------------------------------------------
# SQL backend implementation
# ---------------------------------------------------------------------------


class SQLModelReportStore(ReportStore):
    """ReportStore implementation backed by any SQLAlchemy-compatible database.

    Configured via the ``SQL_DATABASE_URL`` setting.  Any URL supported by
    SQLAlchemy works (PostgreSQL, SQLite, MySQL, etc.).
    """

    def initialize(self) -> None:
        """Create all tables if they do not already exist."""
        try:
            SQLModel.metadata.create_all(_get_engine())
            logger.info("SQL report store tables initialised")
        except IntegrityError:
            # Race condition: multiple gunicorn workers call initialize()
            # simultaneously. PostgreSQL's CREATE TABLE IF NOT EXISTS is not
            # atomic under concurrent load; the second worker hits a unique
            # violation on pg_type. The tables were created by the first
            # worker, so this is safe to ignore.
            logger.info("SQL report store tables already exist")

    def list_reports(self) -> List[ReportListItem]:
        with Session(_get_engine()) as session:
            rows = session.exec(select(ReportRecord)).all()
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

    def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
            if not report:
                return None
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .order_by(col(ReportVersionRecord.version).desc())
                .limit(1)
            )
            row = session.exec(stmt).first()
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

    def get_report_version(
        self, report_id: str, version: int
    ) -> Optional[ReportVersion]:
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
            if not report:
                return None
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .where(ReportVersionRecord.version == version)
            )
            row = session.exec(stmt).first()
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

    def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
            if not report:
                return []
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .order_by(col(ReportVersionRecord.version).desc())
            )
            rows = session.exec(stmt).all()
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

    def create_report(
        self,
        name: str,
        created_by: str,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""
        report_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()

        with Session(_get_engine()) as session:
            session.add(
                ReportRecord(
                    report_id=report_id,
                    name=name,
                    current_version=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()

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
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
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
            for old_stat in session.exec(old_stats_stmt).all():
                session.delete(old_stat)
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

            session.commit()

        return ReportVersion(
            report_id=report_id,
            name=name,
            version=version,
            config=config,
            created_at=now,
            created_by=created_by,
            comment=comment,
        )

    def delete_report(self, report_id: str) -> bool:
        """Delete a report and all its versions.

        Returns False if the report does not exist.
        """
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
            if not report:
                return False

            # Clear the dashboard pointer if it references this report
            pointer = session.get(DashboardPointerRecord, 1)
            if pointer and pointer.report_id == report_id:
                session.delete(pointer)

            # Delete all versions for this report
            stmt = select(ReportVersionRecord).where(
                ReportVersionRecord.report_id == report_id
            )
            for version_record in session.exec(stmt).all():
                session.delete(version_record)

            # Delete all panel stats for this report
            stats_stmt = select(PanelStatRecord).where(
                PanelStatRecord.report_id == report_id
            )
            for stat_record in session.exec(stats_stmt).all():
                session.delete(stat_record)

            session.delete(report)
            session.commit()
        return True

    def get_dashboard_report_id(self) -> Optional[str]:
        with Session(_get_engine()) as session:
            row = session.get(DashboardPointerRecord, 1)
            if not row:
                return None
            return row.report_id

    def set_dashboard_report(self, report_id: str) -> bool:
        with Session(_get_engine()) as session:
            exists = session.get(ReportRecord, report_id)
            if not exists:
                return False
            now = datetime.now(tz=timezone.utc).isoformat()
            existing = session.get(DashboardPointerRecord, 1)
            if existing:
                existing.report_id = report_id
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    DashboardPointerRecord(id=1, report_id=report_id, updated_at=now)
                )
            session.commit()
        return True

    def get_dashboard_report(self) -> Optional[ReportVersion]:
        report_id = self.get_dashboard_report_id()
        if not report_id:
            return None
        return self.get_report_latest(report_id)

    def list_panel_stats(self) -> List[PanelStat]:
        """Return all PanelStat records across all reports."""
        with Session(_get_engine()) as session:
            rows = session.exec(select(PanelStatRecord)).all()
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

    def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: Optional[str] = None,
    ) -> User:
        now = datetime.now(tz=timezone.utc).isoformat()
        with Session(_get_engine()) as session:
            stmt = (
                select(UserRecord)
                .where(UserRecord.iss == iss)
                .where(UserRecord.sub == sub)
            )
            record = session.exec(stmt).first()
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
                session.commit()
                session.refresh(record)
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

    def update_user_profile(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        token_iat: Optional[datetime] = None,
    ) -> User:
        with Session(_get_engine()) as session:
            record = session.get(UserRecord, user_id)
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
                session.commit()
                session.refresh(record)
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

    def get_user(self, user_id: str) -> Optional[User]:
        with Session(_get_engine()) as session:
            record = session.get(UserRecord, user_id)
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

    def archive_user(self, user_id: str) -> bool:
        now = datetime.now(tz=timezone.utc).isoformat()
        with Session(_get_engine()) as session:
            record = session.get(UserRecord, user_id)
            if not record:
                return False
            record.archived_at = now
            session.add(record)
            session.commit()
        return True
