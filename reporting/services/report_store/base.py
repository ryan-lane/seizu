from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion


class ReportStore(ABC):
    """Abstract base class for report configuration storage backends."""

    @abstractmethod
    def initialize(self) -> None:
        """Perform any one-time setup required by the backend (e.g. create table)."""

    @abstractmethod
    def list_reports(self) -> List[ReportListItem]:
        """Return lightweight metadata for all reports."""

    @abstractmethod
    def get_report_latest(self, report_id: str) -> Optional[ReportVersion]:
        """Return the latest version of a report config, or None if not found."""

    @abstractmethod
    def get_report_version(
        self, report_id: str, version: int
    ) -> Optional[ReportVersion]:
        """Return a specific version of a report config, or None if not found."""

    @abstractmethod
    def list_report_versions(self, report_id: str) -> List[ReportVersion]:
        """Return all stored versions for a report, newest first."""

    @abstractmethod
    def create_report(
        self,
        config: Dict[str, Any],
        created_by: str,
        comment: Optional[str] = None,
    ) -> ReportVersion:
        """Create a new report with version 1 and return the initial ReportVersion."""

    @abstractmethod
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

    @abstractmethod
    def get_dashboard_report_id(self) -> Optional[str]:
        """Return the report_id of the current dashboard report, or None if not set."""

    @abstractmethod
    def set_dashboard_report(self, report_id: str) -> bool:
        """Point the dashboard pointer at the given report.

        Returns False if the report does not exist.
        """

    @abstractmethod
    def get_dashboard_report(self) -> Optional[ReportVersion]:
        """Return the latest version of the dashboard report, or None if not set."""
