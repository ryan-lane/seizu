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
from sqlmodel import col
from sqlmodel import create_engine
from sqlmodel import Field
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel

from reporting import settings
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportMetadata
from reporting.schema.report_config import ReportVersion
from reporting.services.report_store.base import ReportStore

logger = logging.getLogger(__name__)

_engine = None
_snowflake_gen: Optional[SnowflakeGenerator] = None


# ---------------------------------------------------------------------------
# SQLModel table definitions
# ---------------------------------------------------------------------------


class ReportRecord(SQLModel, table=True):  # type: ignore
    __tablename__ = "reports"
    report_id: str = Field(primary_key=True)
    name: str
    description: str = ""
    current_version: int = 1
    created_at: str
    updated_at: str


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
        SQLModel.metadata.create_all(_get_engine())
        logger.info("SQL report store tables initialised")

    def list_reports(self) -> List[ReportListItem]:
        with Session(_get_engine()) as session:
            rows = session.exec(select(ReportRecord)).all()
            return [
                ReportListItem(
                    report_id=r.report_id,
                    name=r.name,
                    description=r.description,
                    current_version=r.current_version,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    def get_report_metadata(self, report_id: str) -> Optional[ReportMetadata]:
        with Session(_get_engine()) as session:
            row = session.get(ReportRecord, report_id)
            if not row:
                return None
            return ReportMetadata(
                report_id=row.report_id,
                name=row.name,
                description=row.description,
                current_version=row.current_version,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        with Session(_get_engine()) as session:
            report = session.get(ReportRecord, report_id)
            if not report:
                return None
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .where(ReportVersionRecord.version == report.current_version)
            )
            row = session.exec(stmt).first()
            if not row:
                return None
            return ReportVersion(
                report_id=row.report_id,
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
                version=row.version,
                config=row.config,
                created_at=row.created_at,
                created_by=row.created_by,
                comment=row.comment,
            )

    def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        with Session(_get_engine()) as session:
            stmt = (
                select(ReportVersionRecord)
                .where(ReportVersionRecord.report_id == report_id)
                .order_by(col(ReportVersionRecord.version).desc())
            )
            rows = session.exec(stmt).all()
            return [
                ReportVersion(
                    report_id=r.report_id,
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
        description: str,
        config: Dict[str, Any],
        created_by: str,
        comment: Optional[str] = None,
    ) -> ReportVersion:
        report_id = generate_report_id()
        now = datetime.now(tz=timezone.utc).isoformat()
        version = 1

        with Session(_get_engine()) as session:
            session.add(
                ReportRecord(
                    report_id=report_id,
                    name=name,
                    description=description,
                    current_version=version,
                    created_at=now,
                    updated_at=now,
                )
            )
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
            session.commit()

        return ReportVersion(
            report_id=report_id,
            version=version,
            config=config,
            created_at=now,
            created_by=created_by,
            comment=comment,
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
            session.commit()

        return ReportVersion(
            report_id=report_id,
            version=version,
            config=config,
            created_at=now,
            created_by=created_by,
            comment=comment,
        )

    def get_dashboard_report_id(self) -> Optional[str]:
        with Session(_get_engine()) as session:
            row = session.get(DashboardPointerRecord, 1)
            if not row:
                return None
            return row.report_id

    def set_dashboard_report(self, report_id: str) -> bool:
        with Session(_get_engine()) as session:
            if not session.get(ReportRecord, report_id):
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
