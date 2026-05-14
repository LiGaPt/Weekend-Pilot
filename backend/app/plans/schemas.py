from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


PlanPersistenceStatus = Literal["created", "already_exists"]
SkippedPlanReason = Literal["review_blocked", "draft_not_found", "not_safe_to_present"]


class PersistedPlan(BaseModel):
    plan_id: UUID
    run_id: UUID
    draft_id: str
    status: str
    selected: bool
    safe_to_present: bool
    review_decision: str
    persistence_status: PlanPersistenceStatus | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkippedDraft(BaseModel):
    draft_id: str
    reason: SkippedPlanReason
    review_decision: str | None = None
    message: str


class PersistedPlanResult(BaseModel):
    run_id: UUID
    persisted_plans: list[PersistedPlan] = Field(default_factory=list)
    skipped_drafts: list[SkippedDraft] = Field(default_factory=list)
    service_version: str
