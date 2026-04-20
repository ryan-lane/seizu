from unittest.mock import AsyncMock

from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.mcp_config import ToolItem
from reporting.schema.mcp_config import ToolsetListItem
from reporting.schema.mcp_config import ToolsetVersion
from reporting.schema.mcp_config import ToolVersion
from reporting.schema.report_config import User
from reporting.services.query_validator import ValidationResult

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="user@example.com",
    display_name="Test User",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)
_FAKE_CURRENT_USER = CurrentUser(
    user=_FAKE_USER, jwt_claims={}, permissions=ALL_PERMISSIONS
)

_TS_ID = "ts-abc123"
_TOOL_ID = "tool-xyz456"


def _make_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _FAKE_CURRENT_USER
    return app


def _toolset_item(
    ts_id: str = _TS_ID, name: str = "My Toolset", version: int = 1
) -> ToolsetListItem:
    return ToolsetListItem(
        toolset_id=ts_id,
        name=name,
        description="A test toolset",
        enabled=True,
        current_version=version,
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        created_by="test-user-id",
    )


def _toolset_version(ts_id: str = _TS_ID, version: int = 1) -> ToolsetVersion:
    return ToolsetVersion(
        toolset_id=ts_id,
        name="My Toolset",
        description="A test toolset",
        enabled=True,
        version=version,
        created_at="2024-01-01T00:00:00+00:00",
        created_by="test-user-id",
        comment="Initial version",
    )


def _tool_item(
    tool_id: str = _TOOL_ID, ts_id: str = _TS_ID, version: int = 1
) -> ToolItem:
    return ToolItem(
        tool_id=tool_id,
        toolset_id=ts_id,
        name="My Tool",
        description="A test tool",
        cypher="MATCH (n) RETURN n",
        parameters=[],
        enabled=True,
        current_version=version,
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        created_by="test-user-id",
    )


def _tool_version(
    tool_id: str = _TOOL_ID, ts_id: str = _TS_ID, version: int = 1
) -> ToolVersion:
    return ToolVersion(
        tool_id=tool_id,
        toolset_id=ts_id,
        name="My Tool",
        description="A test tool",
        cypher="MATCH (n) RETURN n",
        parameters=[],
        enabled=True,
        version=version,
        created_at="2024-01-01T00:00:00+00:00",
        created_by="test-user-id",
        comment="Initial version",
    )


_VALID_TOOLSET_BODY = {
    "name": "My Toolset",
    "description": "A test toolset",
    "enabled": True,
}
_VALID_TOOL_BODY = {
    "name": "My Tool",
    "description": "A test tool",
    "cypher": "MATCH (n) RETURN n",
    "parameters": [],
    "enabled": True,
}


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets
# ---------------------------------------------------------------------------


async def test_list_toolsets_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.list_toolsets",
        new=AsyncMock(return_value=[_toolset_item()]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/toolsets")
    assert ret.status_code == 200
    items = ret.json()["toolsets"]
    assert len(items) == 1
    assert items[0]["toolset_id"] == _TS_ID
    assert items[0]["name"] == "My Toolset"


async def test_list_toolsets_empty(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.list_toolsets",
        new=AsyncMock(return_value=[]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get("/api/v1/toolsets")
    assert ret.status_code == 200
    assert ret.json()["toolsets"] == []


# ---------------------------------------------------------------------------
# POST /api/v1/toolsets
# ---------------------------------------------------------------------------


async def test_create_toolset_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.create_toolset",
        new=AsyncMock(return_value=_toolset_item()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post("/api/v1/toolsets", json=_VALID_TOOLSET_BODY)
    assert ret.status_code == 201
    assert ret.json()["toolset_id"] == _TS_ID


async def test_create_toolset_invalid_body(mocker):
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post("/api/v1/toolsets", json={"invalid": "body"})
    assert ret.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}
# ---------------------------------------------------------------------------


async def test_get_toolset_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=_toolset_item()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}")
    assert ret.status_code == 200
    assert ret.json()["toolset_id"] == _TS_ID


async def test_get_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}")
    assert ret.status_code == 404
    assert "error" in ret.json()


# ---------------------------------------------------------------------------
# PUT /api/v1/toolsets/{toolset_id}
# ---------------------------------------------------------------------------


async def test_update_toolset_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.update_toolset",
        new=AsyncMock(return_value=_toolset_item(version=2)),
    )
    app = _make_app()
    body = {**_VALID_TOOLSET_BODY, "comment": "Updated"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.put(f"/api/v1/toolsets/{_TS_ID}", json=body)
    assert ret.status_code == 200
    assert ret.json()["current_version"] == 2


async def test_update_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.update_toolset",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.put(f"/api/v1/toolsets/{_TS_ID}", json=_VALID_TOOLSET_BODY)
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/toolsets/{toolset_id}
# ---------------------------------------------------------------------------


async def test_delete_toolset_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.delete_toolset",
        new=AsyncMock(return_value=True),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.delete(f"/api/v1/toolsets/{_TS_ID}")
    assert ret.status_code == 200
    assert ret.json()["toolset_id"] == _TS_ID


async def test_delete_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.delete_toolset",
        new=AsyncMock(return_value=False),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.delete(f"/api/v1/toolsets/{_TS_ID}")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/versions
# ---------------------------------------------------------------------------


async def test_list_toolset_versions_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=_toolset_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.list_toolset_versions",
        new=AsyncMock(return_value=[_toolset_version()]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/versions")
    assert ret.status_code == 200
    assert len(ret.json()["versions"]) == 1
    assert ret.json()["versions"][0]["version"] == 1


async def test_list_toolset_versions_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/versions")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/versions/{version}
# ---------------------------------------------------------------------------


async def test_get_toolset_version_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset_version",
        new=AsyncMock(return_value=_toolset_version()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/versions/1")
    assert ret.status_code == 200
    assert ret.json()["version"] == 1


async def test_get_toolset_version_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset_version",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/versions/99")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/tools
# ---------------------------------------------------------------------------


async def test_list_tools_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=_toolset_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.list_tools",
        new=AsyncMock(return_value=[_tool_item()]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools")
    assert ret.status_code == 200
    assert len(ret.json()["tools"]) == 1
    assert ret.json()["tools"][0]["tool_id"] == _TOOL_ID


async def test_list_tools_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_toolset",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/toolsets/{toolset_id}/tools
# ---------------------------------------------------------------------------


async def test_create_tool_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.validate_query",
        new=AsyncMock(return_value=ValidationResult()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.create_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools", json=_VALID_TOOL_BODY
        )
    assert ret.status_code == 201
    assert ret.json()["tool_id"] == _TOOL_ID


async def test_create_tool_cypher_validation_error(mocker):
    mocker.patch(
        "reporting.routes.toolsets.validate_query",
        new=AsyncMock(
            return_value=ValidationResult(errors=["Write queries are not allowed"])
        ),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools", json=_VALID_TOOL_BODY
        )
    assert ret.status_code == 400
    assert "errors" in ret.json()
    assert ret.json()["errors"] == ["Write queries are not allowed"]


async def test_create_tool_toolset_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.validate_query",
        new=AsyncMock(return_value=ValidationResult()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.create_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools", json=_VALID_TOOL_BODY
        )
    assert ret.status_code == 404


async def test_create_tool_invalid_body(mocker):
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools", json={"invalid": "body"}
        )
    assert ret.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/tools/{tool_id}
# ---------------------------------------------------------------------------


async def test_get_tool_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}")
    assert ret.status_code == 200
    assert ret.json()["tool_id"] == _TOOL_ID


async def test_get_tool_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}")
    assert ret.status_code == 404


async def test_get_tool_wrong_toolset(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item(ts_id="other-toolset")),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/v1/toolsets/{toolset_id}/tools/{tool_id}
# ---------------------------------------------------------------------------


async def test_update_tool_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.validate_query",
        new=AsyncMock(return_value=ValidationResult()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.update_tool",
        new=AsyncMock(return_value=_tool_item(version=2)),
    )
    app = _make_app()
    body = {**_VALID_TOOL_BODY, "comment": "Updated"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.put(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}", json=body)
    assert ret.status_code == 200
    assert ret.json()["current_version"] == 2


async def test_update_tool_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.put(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}", json=_VALID_TOOL_BODY
        )
    assert ret.status_code == 404


async def test_update_tool_cypher_validation_error(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.validate_query",
        new=AsyncMock(
            return_value=ValidationResult(errors=["Write queries are not allowed"])
        ),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.put(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}", json=_VALID_TOOL_BODY
        )
    assert ret.status_code == 400
    assert "errors" in ret.json()


# ---------------------------------------------------------------------------
# DELETE /api/v1/toolsets/{toolset_id}/tools/{tool_id}
# ---------------------------------------------------------------------------


async def test_delete_tool_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.delete_tool",
        new=AsyncMock(return_value=True),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.delete(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}")
    assert ret.status_code == 200
    assert ret.json()["tool_id"] == _TOOL_ID


async def test_delete_tool_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.delete(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions
# ---------------------------------------------------------------------------


async def test_list_tool_versions_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.report_store.list_tool_versions",
        new=AsyncMock(return_value=[_tool_version()]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/versions")
    assert ret.status_code == 200
    assert len(ret.json()["versions"]) == 1
    assert ret.json()["versions"][0]["version"] == 1


async def test_list_tool_versions_tool_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/versions")
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/toolsets/{toolset_id}/tools/{tool_id}/versions/{version}
# ---------------------------------------------------------------------------


async def test_get_tool_version_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool_version",
        new=AsyncMock(return_value=_tool_version()),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/versions/1")
    assert ret.status_code == 200
    assert ret.json()["version"] == 1


async def test_get_tool_version_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool_version",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/versions/99"
        )
    assert ret.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/toolsets/{toolset_id}/tools/{tool_id}/call
# ---------------------------------------------------------------------------


async def test_call_tool_success(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.reporting_neo4j.run_query",
        new=AsyncMock(return_value=[{"n": "value1"}, {"n": "value2"}]),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {}},
        )
    assert ret.status_code == 200
    assert ret.json()["results"] == [{"n": "value1"}, {"n": "value2"}]


async def test_call_tool_with_arguments(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    run_query_mock = AsyncMock(return_value=[])
    mocker.patch(
        "reporting.routes.toolsets.reporting_neo4j.run_query", new=run_query_mock
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {"limit": 10}},
        )
    assert ret.status_code == 200
    run_query_mock.assert_awaited_once_with(
        "MATCH (n) RETURN n", parameters={"limit": 10}
    )


async def test_call_tool_not_found(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=None),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {}},
        )
    assert ret.status_code == 404


async def test_call_tool_wrong_toolset(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item(ts_id="other-toolset")),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {}},
        )
    assert ret.status_code == 404


async def test_call_tool_disabled(mocker):
    disabled = _tool_item()
    disabled.enabled = False
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=disabled),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {}},
        )
    assert ret.status_code == 400
    assert "disabled" in ret.json()["error"].lower()


async def test_call_tool_execution_error(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool",
        new=AsyncMock(return_value=_tool_item()),
    )
    mocker.patch(
        "reporting.routes.toolsets.reporting_neo4j.run_query",
        new=AsyncMock(side_effect=Exception("Neo4j unavailable")),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/call",
            json={"arguments": {}},
        )
    assert ret.status_code == 500


async def test_get_tool_version_wrong_toolset(mocker):
    mocker.patch(
        "reporting.routes.toolsets.report_store.get_tool_version",
        new=AsyncMock(return_value=_tool_version(ts_id="other-toolset")),
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.get(f"/api/v1/toolsets/{_TS_ID}/tools/{_TOOL_ID}/versions/1")
    assert ret.status_code == 404
