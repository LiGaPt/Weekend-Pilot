from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


DemoReadProfile = Literal["mock_world", "amap"]


class DemoStartRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    external_user_id: str | None = None
    display_name: str | None = None
    case_id: str | None = "web-demo"
    selected_plan_index: int = Field(default=0, ge=0)
    read_profile: DemoReadProfile = "mock_world"


class DemoReplanRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    selected_plan_index: int = Field(default=0, ge=0)


class DemoClarifyRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    selected_plan_index: int = Field(default=0, ge=0)


class DemoConfirmRunRequest(BaseModel):
    plan_id: UUID | None = None
    confirmed_by: str = "web-demo-user"


class DemoDeclineRunRequest(BaseModel):
    plan_id: UUID | None = None
    declined_by: str = "web-demo-user"
    reason: str | None = None


class DemoCandidateSummary(BaseModel):
    candidate_id: str | None = None
    name: str | None = None
    category: str | None = None
    provider: str | None = None
    address: str | None = None
    tags: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class DemoTimelineItem(BaseModel):
    sequence: int | None = None
    item_type: str | None = None
    title: str | None = None
    candidate_id: str | None = None
    duration_minutes: int | None = None
    start_label: str | None = None
    end_label: str | None = None
    notes: list[str] = Field(default_factory=list)


class DemoRouteSummary(BaseModel):
    origin_candidate_id: str | None = None
    destination_candidate_id: str | None = None
    provider: str | None = None
    mode: str | None = None
    distance_meters: int | None = None
    duration_minutes: int | None = None
    summary: str | None = None


class DemoFeasibilitySummary(BaseModel):
    is_feasible: bool | None = None
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_duration_minutes: int | None = None
    route_duration_minutes: int | None = None
    queue_wait_minutes: int | None = None


class DemoProposedActionSummary(BaseModel):
    action_ref: str | None = None
    action_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool | None = None
    reason: str | None = None


class DemoConfirmationSummary(BaseModel):
    status: str | None = None
    confirmed_by: str | None = None
    declined_by: str | None = None
    source: str | None = None
    confirmed_at: str | None = None
    declined_at: str | None = None
    reason: str | None = None
    action_count: int | None = None


class DemoExecutionSummary(BaseModel):
    status: str | None = None
    plan_status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    succeeded_count: int | None = None
    failed_count: int | None = None
    action_results: list[dict[str, Any]] = Field(default_factory=list)


class DemoFeedbackSummary(BaseModel):
    status: str | None = None
    run_status: str | None = None
    headline: str | None = None
    message: str | None = None
    completed_actions: list[dict[str, Any]] = Field(default_factory=list)
    failed_actions: list[dict[str, Any]] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    generated_at: str | None = None


class DemoPlanVersionSummary(BaseModel):
    version_number: int = Field(ge=1)
    version_label: str
    source_run_id: UUID | None = None
    source_selected_plan_id: UUID | None = None


class DemoClarificationSummary(BaseModel):
    prompt: str
    missing_fields: list[str] = Field(default_factory=list)


DemoProgressStage = Literal[
    "understanding_request",
    "planning_queries",
    "searching_activities",
    "searching_dining",
    "checking_availability",
    "building_itinerary",
    "checking_route_time",
    "reviewing_plan",
    "ready_for_confirmation",
    "executing_confirmed_actions",
]


class DemoProgressSummary(BaseModel):
    schema_version: Literal["public_demo_progress_v1"] = "public_demo_progress_v1"
    current_stage: DemoProgressStage
    current_label: str
    stage_history: list[DemoProgressStage] = Field(default_factory=list)


class DemoActionManifestItemSummary(BaseModel):
    action_ref: str | None = None
    execution_order: int | None = Field(default=None, ge=1)
    action_type: str | None = None
    target_id: str | None = None
    payload_preview: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class DemoActionManifestSummary(BaseModel):
    source: str
    action_count: int = Field(ge=0)
    actions: list[DemoActionManifestItemSummary] = Field(default_factory=list)


class DemoPlanPreview(BaseModel):
    plan_id: UUID
    status: str
    selected: bool
    title: str | None = None
    summary: str | None = None
    activity: DemoCandidateSummary | dict[str, Any] | None = None
    dining: DemoCandidateSummary | dict[str, Any] | None = None
    timeline: list[DemoTimelineItem | dict[str, Any]] = Field(default_factory=list)
    route: DemoRouteSummary | dict[str, Any] | None = None
    feasibility: DemoFeasibilitySummary | dict[str, Any] | None = None
    proposed_actions: list[DemoProposedActionSummary | dict[str, Any]] = Field(default_factory=list)
    action_manifest: DemoActionManifestSummary
    confirmation: DemoConfirmationSummary | dict[str, Any] | None = None
    execution: DemoExecutionSummary | dict[str, Any] | None = None
    feedback: DemoFeedbackSummary | dict[str, Any] | None = None


class DemoRunSummary(BaseModel):
    run_id: UUID
    status: str
    read_profile: DemoReadProfile
    selected_plan_id: UUID | None = None
    progress: DemoProgressSummary
    plan_version: DemoPlanVersionSummary
    plans: list[DemoPlanPreview] = Field(default_factory=list)
    action_count: int = 0
    execution_status: str | None = None
    feedback_status: str | None = None
    error: dict[str, Any] | None = None
    clarification: DemoClarificationSummary | None = None
