from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from reporting.schema.mcp_config import ToolItem, ToolsetListItem, ToolsetVersion, ToolVersion
from reporting.schema.rbac import RoleItem, RoleVersion
from reporting.schema.report_config import (
    PanelStat,
    QueryHistoryItem,
    ReportListItem,
    ReportVersion,
    ScheduledQueryItem,
    ScheduledQueryVersion,
    User,
)


def extract_panel_stats(report_id: str, config: dict[str, Any]) -> list[PanelStat]:
    """Parse a report config dict and return PanelStat records for every stat-worthy panel.

    A panel qualifies when all of the following hold:
    - ``type`` is ``"count"`` or ``"progress"``
    - ``metric`` is set
    - ``cypher`` is set
    - At most one param references an input (panels with >1 input params are skipped
      because the tag cardinality would be unmanageably high)

    The ``cypher`` field is resolved against ``report.queries`` at extraction time so
    that stat workers never need to load full report configs.
    """
    # Import here to avoid module-level circular dependencies.
    from reporting.schema import reporting_config

    try:
        report = reporting_config.Report.model_validate(config)
    except Exception:
        return []

    stats: list[PanelStat] = []
    for row in report.rows:
        for panel in row.panels:
            if panel.type not in ("count", "progress"):
                continue
            if not panel.metric or not panel.cypher:
                continue

            cypher = report.queries.get(panel.cypher, panel.cypher)
            static_params: dict[str, Any] = {}
            input_params = []
            for p in panel.params:
                if p.value:
                    static_params[p.name] = p.value
                elif p.input_id:
                    input_params.append(p)

            if len(input_params) > 1:
                # Too many inputs — cardinality would be too high.
                continue

            input_param_name = None
            input_cypher = None
            if len(input_params) == 1:
                input_ref = input_params[0]
                _input = next(
                    (i for i in report.inputs if i.input_id == input_ref.input_id),
                    None,
                )
                if _input is None or _input.cypher is None:
                    continue
                input_param_name = input_ref.name
                input_cypher = _input.cypher

            stats.append(
                PanelStat(
                    report_id=report_id,
                    metric=panel.metric,
                    panel_type=panel.type,
                    cypher=cypher,
                    static_params=static_params,
                    input_param_name=input_param_name,
                    input_cypher=input_cypher,
                )
            )
    return stats


class ReportStore(ABC):
    """Abstract base class for report configuration storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Perform any one-time setup required by the backend (e.g. create table)."""

    @abstractmethod
    async def list_reports(self) -> list[ReportListItem]:
        """Return lightweight metadata for all reports."""

    @abstractmethod
    async def get_report_latest(self, report_id: str) -> ReportVersion | None:
        """Return the latest version of a report config, or None if not found."""

    @abstractmethod
    async def get_report_version(self, report_id: str, version: int) -> ReportVersion | None:
        """Return a specific version of a report config, or None if not found."""

    @abstractmethod
    async def list_report_versions(self, report_id: str) -> list[ReportVersion]:
        """Return all stored versions for a report, newest first."""

    @abstractmethod
    async def create_report(
        self,
        name: str,
        created_by: str,
    ) -> ReportListItem:
        """Create a new empty report (no initial version) and return the ReportListItem."""

    @abstractmethod
    async def save_report_version(
        self,
        report_id: str,
        config: dict[str, Any],
        created_by: str,
        comment: str | None = None,
    ) -> ReportVersion | None:
        """Append a new version to an existing report and return it.

        Returns None if the report does not exist.
        """

    @abstractmethod
    async def delete_report(self, report_id: str) -> bool:
        """Delete a report and all its versions.

        Also clears the dashboard pointer if it points to this report.
        Returns False if the report does not exist.
        """

    @abstractmethod
    async def pin_report(self, report_id: str, pinned: bool) -> bool:
        """Set or clear the pinned flag on a report.

        Returns False if the report does not exist.
        """

    @abstractmethod
    async def get_dashboard_report_id(self) -> str | None:
        """Return the report_id of the current dashboard report, or None if not set."""

    @abstractmethod
    async def set_dashboard_report(self, report_id: str) -> bool:
        """Point the dashboard pointer at the given report.

        Returns False if the report does not exist.
        """

    @abstractmethod
    async def get_dashboard_report(self) -> ReportVersion | None:
        """Return the latest version of the dashboard report, or None if not set."""

    @abstractmethod
    async def get_or_create_user(
        self,
        sub: str,
        iss: str,
        email: str,
        display_name: str | None = None,
    ) -> User:
        """Get an existing user by (iss, sub), or create one on first login.

        Existing users are returned as-is; no fields are updated.
        Profile updates (email drift, last_login) are done separately via
        ``update_user_profile``, called only from the ``/api/v1/me`` route.
        Returns the User model.
        """

    @abstractmethod
    async def update_user_profile(
        self,
        user_id: str,
        email: str,
        display_name: str | None = None,
        token_iat: datetime | None = None,
    ) -> User:
        """Sync mutable profile fields, writing only what has changed.

        - ``email`` is written only when it differs from the stored value.
        - ``display_name`` is written only when provided and differs from stored.
        - ``last_login`` is written only when ``token_iat`` is provided and
          newer than the stored value (i.e. a new credential was issued).

        Returns the updated User.
        """

    @abstractmethod
    async def get_user(self, user_id: str) -> User | None:
        """Return a user by their internal user_id, or None if not found."""

    @abstractmethod
    async def archive_user(self, user_id: str) -> bool:
        """Soft-delete a user by setting archived_at.

        Returns False if the user does not exist.
        """

    @abstractmethod
    async def list_panel_stats(self) -> list[PanelStat]:
        """Return all PanelStat records across all reports.

        These are pre-computed descriptors written atomically with each
        ``save_report_version`` call.  The stats worker uses this to avoid
        loading every full report config on each run.
        """

    @abstractmethod
    async def list_scheduled_queries(self) -> list[ScheduledQueryItem]:
        """Return all scheduled queries."""

    @abstractmethod
    async def get_scheduled_query(self, sq_id: str) -> ScheduledQueryItem | None:
        """Return a scheduled query by ID, or None if not found."""

    @abstractmethod
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
        """Create a new scheduled query (at version 1) and return it."""

    @abstractmethod
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
        """Save a new version of an existing scheduled query. Returns None if not found."""

    @abstractmethod
    async def list_scheduled_query_versions(self, sq_id: str) -> list[ScheduledQueryVersion]:
        """Return all stored versions for a scheduled query, newest first."""

    @abstractmethod
    async def get_scheduled_query_version(self, sq_id: str, version: int) -> ScheduledQueryVersion | None:
        """Return a specific version of a scheduled query, or None if not found."""

    @abstractmethod
    async def acquire_scheduled_query_lock(self, sq_id: str, expected_last_scheduled_at: str | None) -> bool:
        """Atomically set last_scheduled_at = now if it still equals expected.

        Returns True if the lock was acquired (CAS succeeded), False if another
        worker already updated the value (CAS failed).
        """

    @abstractmethod
    async def record_scheduled_query_result(self, sq_id: str, status: str, error: str | None = None) -> None:
        """Record the result of a scheduled query execution.

        Updates ``last_run_status`` and ``last_run_at`` on the item.  When
        *status* is ``"failure"`` and *error* is provided, the error is
        prepended to ``last_errors`` (capped at 5 entries).
        """

    @abstractmethod
    async def delete_scheduled_query(self, sq_id: str) -> bool:
        """Delete a scheduled query and all its versions. Returns False if not found."""

    # ------------------------------------------------------------------
    # Toolsets
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_toolsets(self) -> list[ToolsetListItem]:
        """Return all toolsets."""

    @abstractmethod
    async def get_toolset(self, toolset_id: str) -> ToolsetListItem | None:
        """Return a toolset by ID, or None if not found."""

    @abstractmethod
    async def create_toolset(
        self,
        name: str,
        description: str,
        enabled: bool,
        created_by: str,
    ) -> ToolsetListItem:
        """Create a new toolset (at version 1) and return it."""

    @abstractmethod
    async def update_toolset(
        self,
        toolset_id: str,
        name: str,
        description: str,
        enabled: bool,
        updated_by: str,
        comment: str | None = None,
    ) -> ToolsetListItem | None:
        """Save a new version of an existing toolset. Returns None if not found."""

    @abstractmethod
    async def delete_toolset(self, toolset_id: str) -> bool:
        """Delete a toolset, all its versions, and all its tools. Returns False if not found."""

    @abstractmethod
    async def list_toolset_versions(self, toolset_id: str) -> list[ToolsetVersion]:
        """Return all stored versions for a toolset, newest first."""

    @abstractmethod
    async def get_toolset_version(self, toolset_id: str, version: int) -> ToolsetVersion | None:
        """Return a specific version of a toolset, or None if not found."""

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_tools(self, toolset_id: str) -> list[ToolItem]:
        """Return all tools within a toolset."""

    @abstractmethod
    async def get_tool(self, tool_id: str) -> ToolItem | None:
        """Return a tool by ID, or None if not found."""

    @abstractmethod
    async def create_tool(
        self,
        toolset_id: str,
        name: str,
        description: str,
        cypher: str,
        parameters: list[dict[str, Any]],
        enabled: bool,
        created_by: str,
    ) -> ToolItem | None:
        """Create a new tool (at version 1). Returns None if the toolset does not exist."""

    @abstractmethod
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
        """Save a new version of an existing tool. Returns None if not found."""

    @abstractmethod
    async def delete_tool(self, tool_id: str) -> bool:
        """Delete a tool and all its versions. Returns False if not found."""

    @abstractmethod
    async def list_tool_versions(self, tool_id: str) -> list[ToolVersion]:
        """Return all stored versions for a tool, newest first."""

    @abstractmethod
    async def get_tool_version(self, tool_id: str, version: int) -> ToolVersion | None:
        """Return a specific version of a tool, or None if not found."""

    @abstractmethod
    async def list_enabled_tools(self) -> list[ToolItem]:
        """Return all enabled tools in all enabled toolsets."""

    # ------------------------------------------------------------------
    # Query history
    # ------------------------------------------------------------------

    @abstractmethod
    async def save_query_history(self, user_id: str, query: str) -> QueryHistoryItem:
        """Append a query execution to the user's history and return the new item."""

    @abstractmethod
    async def list_query_history(self, user_id: str, page: int, per_page: int) -> tuple[list[QueryHistoryItem], int]:
        """Return a paginated page of query history (newest first) and the total count.

        Only items belonging to ``user_id`` are returned — callers must never
        pass a user_id they do not own.
        """

    # ------------------------------------------------------------------
    # Roles (user-defined, versioned)
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_roles(self) -> list[RoleItem]:
        """Return all user-defined roles."""

    @abstractmethod
    async def get_role(self, role_id: str) -> RoleItem | None:
        """Return a user-defined role by ID, or None if not found."""

    @abstractmethod
    async def get_role_by_name(self, name: str) -> RoleItem | None:
        """Return a user-defined role by name, or None if not found."""

    @abstractmethod
    async def create_role(
        self,
        name: str,
        description: str,
        permissions: list[str],
        created_by: str,
    ) -> RoleItem:
        """Create a new user-defined role (at version 1) and return it."""

    @abstractmethod
    async def update_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: list[str],
        updated_by: str,
        comment: str | None = None,
    ) -> RoleItem | None:
        """Save a new version of an existing role. Returns None if not found."""

    @abstractmethod
    async def delete_role(self, role_id: str) -> bool:
        """Delete a role and all its versions. Returns False if not found."""

    @abstractmethod
    async def list_role_versions(self, role_id: str) -> list[RoleVersion]:
        """Return all stored versions for a role, newest first."""

    @abstractmethod
    async def get_role_version(self, role_id: str, version: int) -> RoleVersion | None:
        """Return a specific version of a role, or None if not found."""
