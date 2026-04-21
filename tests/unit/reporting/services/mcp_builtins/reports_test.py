"""Tests for the ``reports__*`` MCP built-in group."""
import json
from unittest.mock import AsyncMock
from unittest.mock import patch

from mcp import types as mcp_types

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import ReportListItem
from reporting.schema.report_config import User
from reporting.services.mcp_server import _build_mcp_server
from reporting.services.mcp_server import _mcp_current_user
from reporting.services.mcp_server import _mcp_permissions

_NOW = "2024-01-01T00:00:00+00:00"


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
    created = ReportListItem(
        report_id="r1",
        name="my report",
        current_version=1,
        created_at=_NOW,
        updated_at=_NOW,
    )
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
        return_value=[
            ReportListItem(
                report_id="r1",
                name="n",
                current_version=1,
                created_at=_NOW,
                updated_at=_NOW,
            )
        ],
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
        result = await _call(
            server, "reports__pin", {"report_id": "r1", "pinned": True}
        )
        data = json.loads(result[0].text)

    assert data == {"report_id": "r1", "pinned": True}
    mock_pin.assert_awaited_once_with("r1", True)


async def test_reports_create_requires_write_permission():
    # Strip write perms — the auth layer should refuse before the handler runs.
    from reporting.authnz.permissions import Permission

    readonly = frozenset({Permission.REPORTS_READ.value})
    handler = _build_mcp_server().request_handlers[mcp_types.CallToolRequest]
    req = mcp_types.CallToolRequest(
        method="tools/call",
        params=mcp_types.CallToolRequestParams(
            name="reports__create", arguments={"name": "x"}
        ),
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
