from httpx import ASGITransport, AsyncClient

from reporting.app import create_app
from reporting.authnz import CurrentUser, get_current_user
from reporting.authnz.permissions import ALL_PERMISSIONS
from reporting.schema.confirmations import ActionConfirmation
from reporting.schema.report_config import User

_USER = User(
    user_id="user-1",
    sub="sub",
    iss="iss",
    email="user@example.com",
    created_at="2024-01-01T00:00:00+00:00",
    last_login="2024-01-01T00:00:00+00:00",
)


def _confirmation() -> ActionConfirmation:
    return ActionConfirmation.model_validate(
        {
            "confirmation_id": "confirm-1",
            "user_id": "user-1",
            "source": "chat",
            "session_key": "123",
            "tool_name": "toolsets__update_tool",
            "action": "update",
            "resource_type": "tool",
            "resource_id": "tool-1",
            "arguments": {"token": "secret-token", "name": "Lookup"},
            "arguments_hash": "hash-1",
            "ui_arguments": {"token": "[redacted]", "name": "Lookup"},
            "status": "pending",
            "batch_id": "batch-1",
            "created_at": "2024-01-01T00:00:00+00:00",
            "expires_at": "2099-01-01T00:30:00+00:00",
        }
    )


def _make_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user=_USER,
        jwt_claims={},
        permissions=ALL_PERMISSIONS,
    )
    return app


async def test_get_confirmation_returns_public_redacted_shape(mocker):
    mocker.patch("reporting.routes.confirmations.report_store.get_action_confirmation", return_value=_confirmation())
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/confirmations/confirm-1")

    assert response.status_code == 200
    body = response.json()["confirmation"]
    assert body["ui_arguments"] == {"token": "[redacted]", "name": "Lookup"}
    assert "arguments" not in body
    assert "arguments_hash" not in body
    assert "session_key" not in body
    assert "user_id" not in body


async def test_batch_confirmation_lookup_uses_batch_store_method(mocker):
    list_batch = mocker.patch(
        "reporting.routes.confirmations.report_store.list_batch_action_confirmations",
        return_value=[_confirmation()],
    )
    list_all = mocker.patch("reporting.routes.confirmations.report_store.list_action_confirmations")
    app = _make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/confirmations/batch/batch-1")

    assert response.status_code == 200
    assert len(response.json()["confirmations"]) == 1
    list_batch.assert_awaited_once_with(user_id="user-1", batch_id="batch-1")
    list_all.assert_not_called()
