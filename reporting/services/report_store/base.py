from abc import ABC
from abc import abstractmethod
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import ReportVersion
from reporting.schema.report_config import User


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
        name: str,
        created_by: str,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""

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
    def delete_report(self, report_id: str) -> bool:
        """Delete a report and all its versions.

        Also clears the dashboard pointer if it points to this report.
        Returns False if the report does not exist.
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

    @abstractmethod
    def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: Optional[str] = None,
    ) -> User:
        """Get an existing user by (iss, sub), or create one on first login.

        Existing users are returned as-is; no fields are updated.
        Profile updates (email drift, last_login) are done separately via
        ``update_user_profile``, called only from the ``/api/v1/me`` route.
        Returns the User model.
        """

    @abstractmethod
    def update_user_profile(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        token_iat: Optional[datetime] = None,
    ) -> User:
        """Sync mutable profile fields, writing only what has changed.

        - ``email`` is written only when it differs from the stored value.
        - ``display_name`` is written only when provided and differs from stored.
        - ``last_login`` is written only when ``token_iat`` is provided and
          newer than the stored value (i.e. a new credential was issued).

        Returns the updated User.
        """

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[User]:
        """Return a user by their internal user_id, or None if not found."""

    @abstractmethod
    def archive_user(self, user_id: str) -> bool:
        """Soft-delete a user by setting archived_at.

        Returns False if the user does not exist.
        """
