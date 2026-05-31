from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ConfirmationSource = Literal["mcp", "chat"]
ConfirmationStatus = Literal["pending", "approved", "denied", "expired", "executed"]
ConfirmationDecision = Literal["approved", "denied"]


class ActionConfirmationTarget(BaseModel):
    """Action/resource tuple used for confirmation grant scope."""

    action: str
    resource_type: str
    resource_id: str


class ActionConfirmation(BaseModel):
    """Server-side record for a pending or decided action confirmation."""

    confirmation_id: str
    user_id: str
    source: ConfirmationSource
    session_key: str
    tool_name: str
    action: str
    resource_type: str
    resource_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ui_arguments: dict[str, Any] = Field(default_factory=dict)
    status: ConfirmationStatus
    batch_id: str | None = None
    created_at: str
    expires_at: str
    decided_at: str | None = None
    decided_by: str | None = None


class ConfirmationListResponse(BaseModel):
    confirmations: list[ActionConfirmation]


class ConfirmationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ConfirmationDecision


class ConfirmationResponse(BaseModel):
    confirmation: ActionConfirmation
