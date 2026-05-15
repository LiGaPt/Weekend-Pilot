from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


FeedbackStatus = Literal[
    "completed",
    "partially_completed",
    "failed",
    "skipped",
]

FeedbackActionStatus = Literal[
    "completed",
    "already_completed",
    "failed",
    "blocked",
    "rate_limited",
]


class FeedbackActionSummary(BaseModel):
    action_ref: str
    execution_order: int
    tool_name: str
    target_id: str
    target_label: str
    status: FeedbackActionStatus
    message: str
    error_code: str | None = None


class ExecutionFeedbackResult(BaseModel):
    run_id: UUID
    plan_id: UUID
    status: FeedbackStatus
    run_status: str
    headline: str
    message: str
    completed_actions: list[FeedbackActionSummary] = Field(default_factory=list)
    failed_actions: list[FeedbackActionSummary] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    writer_version: str
