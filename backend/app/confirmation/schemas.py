from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ConfirmationDecision = Literal["confirmed", "declined"]
ConfirmationStatus = Literal["confirmed", "declined"]
ConfirmedActionType = Literal[
    "join_queue",
    "reserve_restaurant",
    "book_ticket",
    "order_addon",
    "send_message",
]


class ConfirmedActionSpec(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: ConfirmedActionType
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    user_confirmed: bool = True
    reason: str


class ConfirmationResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: ConfirmationStatus
    confirmation_id: str
    selected: bool
    confirmed_actions: list[ConfirmedActionSpec] = Field(default_factory=list)
    service_version: str
