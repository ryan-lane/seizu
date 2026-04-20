from unittest.mock import AsyncMock

from httpx import ASGITransport
from httpx import AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.report_config import User
from reporting.services.query_validator import ValidationResult

_FAKE_USER = User(
    user_id="test-user-id",
    sub="sub123",
    iss="https://idp.example.com",
    email="test@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)

_FAKE_CURRENT_USER = CurrentUser(
    user=_FAKE_USER, jwt_claims={}, permissions=ALL_PERMISSIONS
)


def _mock_validate(mocker, errors=None, warnings=None):
    result = ValidationResult(
        errors=errors if errors is not None else [],
        warnings=warnings if warnings is not None else [],
    )
    mocker.patch(
        "reporting.routes.validate.validate_query",
        new=AsyncMock(return_value=result),
    )
    return result


def _make_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: _FAKE_CURRENT_USER
    return app


async def test_validate_success(mocker):
    _mock_validate(mocker)
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            json={"query": "MATCH (n) RETURN n"},
        )
    assert ret.status_code == 200
    assert ret.json()["errors"] == []
    assert ret.json()["warnings"] == []


async def test_validate_with_errors_still_returns_200(mocker):
    """Validation errors are returned in the body with 200; 400 is for bad requests."""
    _mock_validate(mocker, errors=["Write queries are not allowed"])
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            json={"query": "CREATE (n) RETURN n"},
        )
    assert ret.status_code == 200
    assert ret.json()["errors"] == ["Write queries are not allowed"]
    assert ret.json()["warnings"] == []


async def test_validate_with_warnings(mocker):
    _mock_validate(mocker, warnings=["Unknown label: Foo", "Unknown property: bar"])
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            json={"query": "MATCH (n:Foo) WHERE n.bar = 1 RETURN n"},
        )
    assert ret.status_code == 200
    assert ret.json()["errors"] == []
    assert len(ret.json()["warnings"]) == 2


async def test_validate_with_errors_and_warnings(mocker):
    _mock_validate(
        mocker,
        errors=["Write queries are not allowed"],
        warnings=["Unknown label: Foo"],
    )
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            json={"query": "CREATE (n:Foo) RETURN n"},
        )
    assert ret.status_code == 200
    assert len(ret.json()["errors"]) == 1
    assert len(ret.json()["warnings"]) == 1


async def test_validate_no_json_body(mocker):
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            content=b"not json",
            headers={"Content-Type": "text/plain"},
        )
    assert ret.status_code == 422


async def test_validate_missing_query_field(mocker):
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        ret = await client.post(
            "/api/v1/validate",
            json={"params": {"name": "Alice"}},
        )
    assert ret.status_code == 422
