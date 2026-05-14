from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReviewDecision = Literal["approved", "approved_with_warnings", "blocked"]
ReviewStatus = Literal["passed", "warning", "failed"]
ReviewSeverity = Literal["info", "warning", "error"]


class ReviewCheck(BaseModel):
    check_name: str
    status: ReviewStatus
    severity: ReviewSeverity
    message: str
    draft_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ReviewedDraft(BaseModel):
    draft_id: str
    decision: ReviewDecision
    safe_to_present: bool
    checks: list[ReviewCheck] = Field(default_factory=list)
    errors: list[ReviewCheck] = Field(default_factory=list)
    warnings: list[ReviewCheck] = Field(default_factory=list)


class FinalReviewResult(BaseModel):
    run_id: UUID
    provider_profile: str
    decision: ReviewDecision
    safe_to_present: bool
    reviewed_drafts: list[ReviewedDraft] = Field(default_factory=list)
    checks: list[ReviewCheck] = Field(default_factory=list)
    errors: list[ReviewCheck] = Field(default_factory=list)
    warnings: list[ReviewCheck] = Field(default_factory=list)
    gate_version: str
