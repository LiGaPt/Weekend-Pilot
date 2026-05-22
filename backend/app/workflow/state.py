from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from backend.app.agents import AgentResult, RecoveryDecision, SupervisorAssignmentPlan
from backend.app.confirmation import ConfirmationResult
from backend.app.execution import ExecutionWorkflowResult
from backend.app.feedback.schemas import ExecutionFeedbackResult
from backend.app.observability.schemas import RunTraceContext, TraceRecordResult
from backend.app.planning import (
    Candidate,
    CandidateCollectionResult,
    CandidateEnrichmentResult,
    IntentParseSignals,
    ItineraryDraftResult,
    LocalLifeIntent,
    QueryPlan,
    RouteMatrixEntry,
)
from backend.app.plans.schemas import PersistedPlan
from backend.app.review.schemas import FinalReviewResult
from backend.app.workflow.recovery import RecoveryAttempt
from backend.app.workflow.timing import WorkflowNodeTimingRecord, WorkflowTimingSummary


WorkflowStatus = Literal[
    "awaiting_clarification",
    "awaiting_confirmation",
    "completed",
    "failed",
    "error",
]

V1_WORKFLOW_NODE_NAMES = (
    "initialize",
    "parse_intent",
    "load_memory",
    "generate_queries",
    "execute_searches",
    "populate_candidate_blackboard",
    "pre_flight_check_availability",
    "logical_planner_agent",
    "route_and_time_engine",
    "semantic_validator",
    "final_review",
    "present_to_user",
    "wait_confirmation",
    "saga_execution_engine",
    "generate_summary_message",
)

CandidateSuitabilityStatus = Literal["unscreened", "screened_in", "screened_out"]


class WorkflowMemoryRecord(BaseModel):
    memory_id: UUID
    memory_type: str
    key: str
    value_json: dict[str, Any]
    text: str | None = None
    confidence: str
    source_run_id: UUID | None = None
    source_langsmith_trace_id: str | None = None
    expires_at: str | None = None
    status: str


class CandidateBlackboardEntry(BaseModel):
    candidate: Candidate
    suitability_status: CandidateSuitabilityStatus = "unscreened"
    evidence_tool_names: list[str] = Field(default_factory=list)
    risk_codes: list[str] = Field(default_factory=list)


class CandidateBlackboard(BaseModel):
    activity_candidates: list[CandidateBlackboardEntry] = Field(default_factory=list)
    dining_candidates: list[CandidateBlackboardEntry] = Field(default_factory=list)
    other_candidates: list[CandidateBlackboardEntry] = Field(default_factory=list)
    screened_candidate_ids: list[str] = Field(default_factory=list)


class RouteTimeSummary(BaseModel):
    route_count: int = 0
    feasible_draft_count: int = 0
    infeasible_draft_count: int = 0
    route_matrix: list[RouteMatrixEntry] = Field(default_factory=list)
    summary_version: str = "route_time_summary_v1"


class WeekendPilotWorkflowState(TypedDict, total=False):
    user_input: str
    external_user_id: str | None
    display_name: str | None
    existing_user_id: UUID | None
    session_id: UUID | None
    case_id: str | None
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    failure_profile: str | None
    auto_confirm: bool
    selected_plan_index: int
    run_id: UUID | None
    user_id: UUID | None
    trace_id: str | None
    trace_context: RunTraceContext
    active_memories: list[WorkflowMemoryRecord]
    intent_override: LocalLifeIntent
    parsed_intent: LocalLifeIntent
    intent_parse_signals: IntentParseSignals
    query_plan: QueryPlan
    candidate_collection: CandidateCollectionResult
    candidate_blackboard: CandidateBlackboard
    enrichment_result: CandidateEnrichmentResult
    itinerary_drafts: ItineraryDraftResult
    route_time_summary: RouteTimeSummary
    final_review_result: FinalReviewResult
    agent_results: list[AgentResult]
    supervisor_assignment_plan: SupervisorAssignmentPlan
    recovery_decision: RecoveryDecision
    recovery_attempts: list[RecoveryAttempt]
    max_recovery_attempts: int
    active_recovery_route: str | None
    persisted_plans: list[PersistedPlan]
    selected_plan_id: UUID | None
    generate_queries_status: str | None
    confirmation_result: ConfirmationResult
    execution_result: ExecutionWorkflowResult
    feedback_result: ExecutionFeedbackResult
    observability_result: TraceRecordResult
    workflow_stage_timings: list[WorkflowNodeTimingRecord]
    workflow_timing_summary: WorkflowTimingSummary | dict[str, Any] | None
    status: WorkflowStatus
    node_history: list[str]
    tool_event_count: int
    action_count: int
    execution_status: str | None
    feedback_status: str | None
    observability_status: str | None
    error_json: dict[str, Any] | None
