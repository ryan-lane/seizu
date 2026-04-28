"""Tests for the ``reports__*`` MCP built-in group."""

import json
from unittest.mock import AsyncMock, patch

from mcp import types as mcp_types

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import ReportListItem, ReportVersion, User
from reporting.services.mcp_server import _build_mcp_server, _mcp_current_user, _mcp_permissions

_NOW = "2024-01-01T00:00:00+00:00"


def _report_list_item(report_id: str = "r1", name: str = "n") -> ReportListItem:
    return ReportListItem(
        report_id=report_id,
        name=name,
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
        created_by="u1",
        updated_by="u1",
        access={"scope": "public"},
    )


def _current_user() -> CurrentUser:
    return CurrentUser(
        user=User(
            user_id="u1",
            sub="u1",
            iss="dev",
            email="u1@example.com",
            display_name="u1",
            created_at=_NOW,
            last_login=_NOW,
        ),
        jwt_claims={},
        permissions=ALL_PERMISSIONS,
    )


async def _call(server, name, arguments):
    handler = server.request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name=name, arguments=arguments),
    )
    perm_tok = _mcp_permissions.set(ALL_PERMISSIONS)
    user_tok = _mcp_current_user.set(_current_user())
    try:
        result = await handler(req)
    finally:
        _mcp_permissions.reset(perm_tok)
        _mcp_current_user.reset(user_tok)
    return result.root.content


async def test_reports_create_uses_current_user():
    created = _report_list_item(name="my report")
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.create_report",
        new_callable=AsyncMock,
        return_value=created,
    ) as mock_create:
        server = _build_mcp_server()
        result = await _call(server, "reports__create", {"name": "my report"})
        data = json.loads(result[0].text)

    assert data["report_id"] == "r1"
    # Verify the resolved CurrentUser was forwarded as created_by — this is
    # the whole reason we thread CurrentUser through the MCP context.
    mock_create.assert_awaited_once_with(name="my report", created_by="u1")


async def test_reports_list_returns_reports():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.list_reports",
        new_callable=AsyncMock,
        return_value=[_report_list_item()],
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__list", {})
        data = json.loads(result[0].text)

    assert len(data["reports"]) == 1
    assert data["reports"][0]["report_id"] == "r1"


async def test_reports_pin_calls_store():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.pin_report",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_pin:
        server = _build_mcp_server()
        result = await _call(server, "reports__pin", {"report_id": "r1", "pinned": True})
        data = json.loads(result[0].text)

    assert data == {"report_id": "r1", "pinned": True}
    mock_pin.assert_awaited_once_with("r1", True, updated_by="u1", user_id="u1")


async def test_reports_create_requires_write_permission():
    # Strip write perms — the auth layer should refuse before the handler runs.
    from reporting.authnz.permissions import Permission

    readonly = frozenset({Permission.REPORTS_READ.value})
    handler = _build_mcp_server().request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(name="reports__create", arguments={"name": "x"}),
    )
    perm_tok = _mcp_permissions.set(readonly)
    user_tok = _mcp_current_user.set(_current_user())
    try:
        result = await handler(req)
    finally:
        _mcp_permissions.reset(perm_tok)
        _mcp_current_user.reset(user_tok)
    data = json.loads(result.root.content[0].text)
    assert "Permission denied" in data["error"]


def _report_version(version: int = 1) -> ReportVersion:
    return ReportVersion(
        report_id="r1",
        name="n",
        version=version,
        config={"rows": []},
        created_at=_NOW,
        created_by="u1",
        comment=None,
        report_created_by="u1",
        report_updated_by="u1",
        access={"scope": "public"},
    )


async def test_reports_get_returns_latest():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_report_latest",
        new_callable=AsyncMock,
        return_value=_report_version(),
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get", {"report_id": "r1"})
        data = json.loads(result[0].text)

    assert data["report_id"] == "r1"


async def test_reports_get_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_report_latest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get", {"report_id": "nope"})
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_get_dashboard_returns_report():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_dashboard_report",
        new_callable=AsyncMock,
        return_value=_report_version(),
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get_dashboard", {})
        data = json.loads(result[0].text)

    assert data["report_id"] == "r1"


async def test_reports_get_dashboard_returns_error_when_none():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_dashboard_report",
        new_callable=AsyncMock,
        return_value=None,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get_dashboard", {})
        data = json.loads(result[0].text)

    assert data == {"error": "No dashboard report configured"}


async def test_reports_create_version_success():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.save_report_version",
        new_callable=AsyncMock,
        return_value=_report_version(2),
    ) as mock_save:
        server = _build_mcp_server()
        result = await _call(
            server,
            "reports__create_version",
            {
                "report_id": "r1",
                "config": {"rows": []},
                "comment": "why",
            },
        )
        data = json.loads(result[0].text)

    assert data["version"] == 2
    mock_save.assert_awaited_once_with(
        report_id="r1",
        config={"rows": []},
        created_by="u1",
        comment="why",
        user_id="u1",
    )


async def test_reports_create_version_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.save_report_version",
        new_callable=AsyncMock,
        return_value=None,
    ):
        server = _build_mcp_server()
        result = await _call(
            server,
            "reports__create_version",
            {"report_id": "nope", "config": {}},
        )
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_update_rejects_unpublish_when_pinned():
    report = _report_list_item()
    report.pinned = True
    with (
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_report_metadata",
            new_callable=AsyncMock,
            return_value=report,
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_dashboard_report_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.update_report_metadata",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__update", {"report_id": "r1", "access": {"scope": "private"}})
        data = json.loads(result[0].text)

    assert data == {"error": "Report must be unpinned and removed from the dashboard before it can be made private"}
    mock_update.assert_not_called()


async def test_reports_update_rejects_unpublish_when_dashboard():
    with (
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_report_metadata",
            new_callable=AsyncMock,
            return_value=_report_list_item(),
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_dashboard_report_id",
            new_callable=AsyncMock,
            return_value="r1",
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.update_report_metadata",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__update", {"report_id": "r1", "access": {"scope": "private"}})
        data = json.loads(result[0].text)

    assert data == {"error": "Report must be unpinned and removed from the dashboard before it can be made private"}
    mock_update.assert_not_called()


async def test_reports_delete_success():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.delete_report",
        new_callable=AsyncMock,
        return_value=True,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__delete", {"report_id": "r1"})
        data = json.loads(result[0].text)

    assert data == {"report_id": "r1"}


async def test_reports_delete_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.delete_report",
        new_callable=AsyncMock,
        return_value=False,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__delete", {"report_id": "nope"})
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_pin_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.pin_report",
        new_callable=AsyncMock,
        return_value=False,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__pin", {"report_id": "nope", "pinned": True})
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_set_dashboard_success():
    with (
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_report_metadata",
            new_callable=AsyncMock,
            return_value=_report_list_item(),
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.set_dashboard_report",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__set_dashboard", {"report_id": "r1"})
        data = json.loads(result[0].text)

    assert data == {"report_id": "r1"}


async def test_reports_set_dashboard_returns_error_when_missing():
    with (
        patch(
            "reporting.services.mcp_builtins.reports.report_store.get_report_metadata",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "reporting.services.mcp_builtins.reports.report_store.set_dashboard_report",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__set_dashboard", {"report_id": "nope"})
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_list_versions_returns_versions():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.list_report_versions",
        new_callable=AsyncMock,
        return_value=[_report_version(1), _report_version(2)],
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__list_versions", {"report_id": "r1"})
        data = json.loads(result[0].text)

    assert len(data["versions"]) == 2


async def test_reports_list_versions_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.list_report_versions",
        new_callable=AsyncMock,
        return_value=[],
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__list_versions", {"report_id": "nope"})
        data = json.loads(result[0].text)

    assert data == {"error": "Report not found"}


async def test_reports_get_version_returns_version():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_report_version",
        new_callable=AsyncMock,
        return_value=_report_version(3),
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get_version", {"report_id": "r1", "version": 3})
        data = json.loads(result[0].text)

    assert data["version"] == 3


async def test_reports_get_version_returns_error_when_missing():
    with patch(
        "reporting.services.mcp_builtins.reports.report_store.get_report_version",
        new_callable=AsyncMock,
        return_value=None,
    ):
        server = _build_mcp_server()
        result = await _call(server, "reports__get_version", {"report_id": "r1", "version": 99})
        data = json.loads(result[0].text)

    assert data == {"error": "Version not found"}
