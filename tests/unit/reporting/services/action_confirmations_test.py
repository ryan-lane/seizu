from reporting.schema.confirmations import ActionConfirmation, ActionConfirmationTarget
from reporting.services import action_confirmations

_NOW = "2024-01-01T00:00:00+00:00"
_LATER = "2099-01-01T00:30:00+00:00"


def _confirmation(status: str = "pending", arguments: dict[str, object] | None = None) -> ActionConfirmation:
    args = arguments or {"report_id": "r1"}
    return ActionConfirmation.model_validate(
        {
            "confirmation_id": "confirm-1",
            "user_id": "user-1",
            "source": "mcp",
            "session_key": "session-1",
            "tool_name": "reports__delete",
            "action": "delete",
            "resource_type": "report",
            "resource_id": "r1",
            "arguments": args,
            "arguments_hash": action_confirmations.arguments_hash(args),
            "ui_arguments": args,
            "status": status,
            "created_at": _NOW,
            "expires_at": _LATER,
        }
    )


async def test_pending_confirmation_is_bound_to_arguments_hash(mocker):
    create_confirmation = mocker.patch(
        "reporting.services.action_confirmations.report_store.create_action_confirmation",
        side_effect=lambda confirmation: confirmation,
    )
    mocker.patch(
        "reporting.services.action_confirmations.report_store.find_action_confirmation_grant",
        return_value=None,
    )
    mocker.patch(
        "reporting.services.action_confirmations.report_store.list_action_confirmations",
        return_value=[_confirmation(arguments={"report_id": "r1", "comment": "old"})],
    )

    result = await action_confirmations.ensure_confirmation(
        user_id="user-1",
        source="mcp",
        session_key="session-1",
        tool_name="reports__delete",
        target=ActionConfirmationTarget(action="delete", resource_type="report", resource_id="r1"),
        arguments={"report_id": "r1", "comment": "new"},
    )

    assert result is not None
    assert result.arguments == {"report_id": "r1", "comment": "new"}
    create_confirmation.assert_awaited_once()


async def test_approved_confirmation_is_claimed_before_execution(mocker):
    approved = _confirmation("approved")
    mocker.patch(
        "reporting.services.action_confirmations.report_store.find_action_confirmation_grant",
        return_value=approved,
    )
    claim = mocker.patch(
        "reporting.services.action_confirmations.report_store.claim_action_confirmation_for_execution",
        return_value=approved.model_copy(update={"status": "executed"}),
    )

    result = await action_confirmations.ensure_confirmation(
        user_id="user-1",
        source="mcp",
        session_key="session-1",
        tool_name="reports__delete",
        target=ActionConfirmationTarget(action="delete", resource_type="report", resource_id="r1"),
        arguments={"report_id": "r1"},
    )

    assert result is None
    claim.assert_awaited_once_with("confirm-1", "user-1")


async def test_already_consumed_approval_blocks_execution(mocker):
    approved = _confirmation("approved")
    mocker.patch(
        "reporting.services.action_confirmations.report_store.find_action_confirmation_grant",
        return_value=approved,
    )
    mocker.patch(
        "reporting.services.action_confirmations.report_store.claim_action_confirmation_for_execution",
        return_value=None,
    )

    result = await action_confirmations.ensure_confirmation(
        user_id="user-1",
        source="mcp",
        session_key="session-1",
        tool_name="reports__delete",
        target=ActionConfirmationTarget(action="delete", resource_type="report", resource_id="r1"),
        arguments={"report_id": "r1"},
    )

    assert result is not None
    assert result.status == "executed"
