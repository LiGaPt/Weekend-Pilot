from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ExecutionWorkflowStatus = Literal[
    "succeeded",
    "partially_succeeded",
    "failed",
    "skipped",
]

ExecutionActionStatus = Literal[
    "succeeded",
    "failed",
    "blocked",
    "rate_limited",
    "idempotent_replay",
]


class ExecutionActionResult(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: str
    target_id: str
    idempotency_key: str
    status: ExecutionActionStatus
    action_id: UUID | None = None
    tool_event_id: UUID | None = None
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None


class ExecutionWorkflowResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: ExecutionWorkflowStatus
    plan_status: str
    action_results: list[ExecutionActionResult] = Field(default_factory=list)
    succeeded_count: int
    failed_count: int
    workflow_version: str
