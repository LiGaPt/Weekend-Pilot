from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.agents import AgentResult
from backend.app.planning import LocalLifeIntent
from backend.app.workflow.state import WeekendPilotWorkflowState, WorkflowStatus
from backend.app.workflow.timing import WorkflowTimingSummary


class WeekendPilotWorkflowRequest(BaseModel):
    user_input: str
    external_user_id: str | None = None
    display_name: str | None = None
    existing_user_id: UUID | None = None
    session_id: UUID | None = None
    case_id: str | None = None
    agent_version: str = "agent-v1"
    prompt_version: str = "prompt-v1"
    tool_profile: Literal["mock_world"] = "mock_world"
    world_profile: Literal["family_afternoon", "solo_afternoon"] = "family_afternoon"
    failure_profile: str | None = None
    auto_confirm: bool = False
    selected_plan_index: int = Field(default=0, ge=0)
    intent_override: LocalLifeIntent | None = None


class WeekendPilotWorkflowResult(BaseModel):
    run_id: UUID | None
    trace_id: str | None
    status: WorkflowStatus
    selected_plan_id: UUID | None = None
    workflow_timing_summary: WorkflowTimingSummary | None = None
    node_history: list[str] = Field(default_factory=list)
    tool_event_count: int = 0
    action_count: int = 0
    execution_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    error_json: dict[str, Any] | None = None
