import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from reporting import settings
from reporting.schema.confirmations import (
    ActionConfirmation,
    ActionConfirmationTarget,
    ConfirmationDecision,
    ConfirmationSource,
)
from reporting.services import report_store

SENSITIVE_KEY_PARTS = ("password", "secret", "token", "key", "credential", "webhook")


def bearer_session_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def arguments_hash(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def public_confirmation_url(confirmation_id: str) -> str:
    return _public_url(f"/app/confirmations/{confirmation_id}")


def public_batch_confirmation_url(batch_id: str) -> str:
    return _public_url(f"/app/confirmations/batch/{batch_id}")


async def ensure_confirmation(
    *,
    user_id: str,
    source: ConfirmationSource,
    session_key: str,
    tool_name: str,
    target: ActionConfirmationTarget,
    arguments: dict[str, Any],
    batch_id: str | None = None,
) -> ActionConfirmation | None:
    """Return None when execution is allowed, else a pending/denied confirmation."""
    fingerprint = arguments_hash(arguments)
    grant = await report_store.find_action_confirmation_grant(
        user_id=user_id,
        source=source,
        session_key=session_key,
        tool_name=tool_name,
        action=target.action,
        resource_type=target.resource_type,
        resource_id=target.resource_id,
        arguments_hash=fingerprint,
    )
    if grant is not None:
        if grant.status == "approved":
            claimed = await report_store.claim_action_confirmation_for_execution(
                grant.confirmation_id,
                user_id,
            )
            return None if claimed is not None else grant.model_copy(update={"status": "executed"})
        return grant

    pending = await _find_pending_confirmation(
        user_id=user_id,
        source=source,
        session_key=session_key,
        tool_name=tool_name,
        target=target,
        arguments_hash=fingerprint,
    )
    if pending is not None:
        return pending

    now = datetime.now(tz=UTC)
    confirmation = ActionConfirmation(
        confirmation_id=uuid.uuid4().hex,
        user_id=user_id,
        source=source,
        session_key=session_key,
        tool_name=tool_name,
        action=target.action,
        resource_type=target.resource_type,
        resource_id=target.resource_id,
        arguments=arguments,
        arguments_hash=fingerprint,
        ui_arguments=redact_arguments(arguments),
        status="pending",
        batch_id=batch_id,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=settings.ACTION_CONFIRMATION_TTL_SECONDS)).isoformat(),
    )
    return await report_store.create_action_confirmation(confirmation)


async def decide_confirmation(
    *,
    confirmation_id: str,
    user_id: str,
    decision: ConfirmationDecision,
) -> ActionConfirmation | None:
    confirmation = await report_store.get_action_confirmation(confirmation_id, user_id=user_id)
    if confirmation is None:
        return None
    if is_expired(confirmation):
        return confirmation.model_copy(update={"status": "expired"})
    if confirmation.status != "pending":
        return confirmation
    decided = await report_store.decide_action_confirmation(
        confirmation_id=confirmation_id,
        user_id=user_id,
        decision=decision,
    )
    if decided is not None:
        return decided
    return await report_store.get_action_confirmation(confirmation_id, user_id=user_id)


def confirmation_required_payload(confirmation: ActionConfirmation) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "confirmation_required": True,
        "confirmation_id": confirmation.confirmation_id,
        "confirmation_url": public_confirmation_url(confirmation.confirmation_id),
        "tool_name": confirmation.tool_name,
        "action": confirmation.action,
        "resource_type": confirmation.resource_type,
        "resource_id": confirmation.resource_id,
        "arguments": confirmation.ui_arguments,
        "status": confirmation.status,
        "expires_at": confirmation.expires_at,
        "instructions": "Approve or deny this action in Seizu, then retry or continue the request.",
    }
    if confirmation.batch_id:
        payload["batch_id"] = confirmation.batch_id
        payload["batch_url"] = public_batch_confirmation_url(confirmation.batch_id)
    return payload


def redact_arguments(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if _is_sensitive_key(key) else redact_arguments(nested) for key, nested in value.items()
        }
    if isinstance(value, list):
        return [redact_arguments(item) for item in value]
    return value


def is_expired(confirmation: ActionConfirmation) -> bool:
    return datetime.fromisoformat(confirmation.expires_at) <= datetime.now(tz=UTC)


async def _find_pending_confirmation(
    *,
    user_id: str,
    source: ConfirmationSource,
    session_key: str,
    tool_name: str,
    target: ActionConfirmationTarget,
    arguments_hash: str,
) -> ActionConfirmation | None:
    confirmations = await report_store.list_action_confirmations(
        user_id=user_id,
        source=source,
        session_key=session_key,
        status="pending",
    )
    for item in confirmations:
        if (
            item.tool_name == tool_name
            and item.action == target.action
            and item.resource_type == target.resource_type
            and item.resource_id == target.resource_id
            and item.arguments_hash == arguments_hash
            and not is_expired(item)
        ):
            return item
    return None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _public_url(path: str) -> str:
    base_url = _public_ui_origin()
    return f"{base_url.rstrip('/')}{path}" if base_url else path


def _public_ui_origin() -> str:
    if settings.SEIZU_PUBLIC_URL:
        return settings.SEIZU_PUBLIC_URL
    if not settings.MCP_RESOURCE_URL:
        return ""
    parsed = urlparse(settings.MCP_RESOURCE_URL)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"
