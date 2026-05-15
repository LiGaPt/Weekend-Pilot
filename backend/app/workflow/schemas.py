from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from backend.app.agents import AgentResult


WorkflowStatus = Literal[
    "awaiting_confirmation",
    "completed",
    "failed",
    "error",
]


class WeekendPilotWorkflowRequest(BaseModel):
    user_input: str
    external_user_id: str | None = None
    display_name: str | None = None
    case_id: str | None = None
    agent_version: str = "agent-v1"
    prompt_version: str = "prompt-v1"
    tool_profile: Literal["mock_world"] = "mock_world"
    world_profile: Literal["family_afternoon"] = "family_afternoon"
    failure_profile: str | None = None
    auto_confirm: bool = False
    selected_plan_index: int = Field(default=0, ge=0)


class WeekendPilotWorkflowResult(BaseModel):
    run_id: UUID | None
    trace_id: str | None
    status: WorkflowStatus
    selected_plan_id: UUID | None = None
    node_history: list[str] = Field(default_factory=list)
    tool_event_count: int = 0
    action_count: int = 0
    execution_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    error_json: dict[str, Any] | None = None


class WeekendPilotWorkflowState(TypedDict, total=False):
    user_input: str
    external_user_id: str | None
    display_name: str | None
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
    trace_context: Any
    active_memories: list[dict[str, Any]]
    parsed_intent: Any
    query_plan: Any
    candidate_collection: Any
    enrichment_result: Any
    itinerary_drafts: Any
    final_review_result: Any
    agent_results: list[Any]
    supervisor_assignment_plan: Any
    recovery_decision: Any
    persisted_plans: list[Any]
    selected_plan_id: UUID | None
    confirmation_result: Any
    execution_result: Any
    feedback_result: Any
    observability_result: Any
    status: WorkflowStatus
    node_history: list[str]
    tool_event_count: int
    action_count: int
    execution_status: str | None
    feedback_status: str | None
    observability_status: str | None
    error_json: dict[str, Any] | None
