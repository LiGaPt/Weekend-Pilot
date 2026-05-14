from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DraftStatus = Literal["draft"]
TimelineItemType = Literal["activity", "transfer", "dining", "buffer"]
ProposedActionType = Literal["book_ticket", "reserve_restaurant", "join_queue"]


class ItineraryCandidateRef(BaseModel):
    candidate_id: str
    name: str
    category: str
    provider: str
    address: str | None = None
    tags: list[str] = Field(default_factory=list)
    tool_event_ids: list[UUID] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ItineraryRouteRef(BaseModel):
    origin_candidate_id: str
    destination_candidate_id: str
    provider: str
    mode: str
    distance_meters: int | None = None
    duration_minutes: int | None = None
    tool_event_id: UUID | None = None
    summary: str | None = None


class TimelineItem(BaseModel):
    sequence: int
    item_type: TimelineItemType
    title: str
    candidate_id: str | None = None
    duration_minutes: int
    start_label: str
    end_label: str
    notes: list[str] = Field(default_factory=list)


class ProposedAction(BaseModel):
    action_ref: str
    action_type: ProposedActionType
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = True
    reason: str


class FeasibilitySummary(BaseModel):
    is_feasible: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_duration_minutes: int
    route_duration_minutes: int | None = None
    queue_wait_minutes: int | None = None


class ItineraryDraft(BaseModel):
    draft_id: str
    status: DraftStatus = "draft"
    title: str
    summary: str
    activity: ItineraryCandidateRef
    dining: ItineraryCandidateRef
    route: ItineraryRouteRef | None = None
    timeline: list[TimelineItem] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    feasibility: FeasibilitySummary
    evidence: dict[str, Any] = Field(default_factory=dict)


class ItineraryFailureReason(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ItineraryDraftResult(BaseModel):
    run_id: UUID
    provider_profile: str
    drafts: list[ItineraryDraft] = Field(default_factory=list)
    failed_reasons: list[ItineraryFailureReason] = Field(default_factory=list)
    generator_version: str
