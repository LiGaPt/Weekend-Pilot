from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


AgentRole = Literal[
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
]
AgentStatus = Literal["completed", "failed", "blocked", "skipped"]


class AgentInvocationContext(BaseModel):
    run_id: UUID
    trace_id: str | None = None
    role: AgentRole
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentToolPolicy(BaseModel):
    role: AgentRole
    allowed_read_tools: list[str] = Field(default_factory=list)
    allowed_write_tools: list[str] = Field(default_factory=list)
    may_execute_write_tools: bool = False


class AgentResult(BaseModel):
    role: AgentRole
    status: AgentStatus
    summary: str
    adapter_version: str
    tool_names_used: list[str] = Field(default_factory=list)
    output_json: dict[str, Any] = Field(default_factory=dict)
    error_json: dict[str, Any] | None = None


class SupervisorAssignment(BaseModel):
    assignment_id: str
    target_role: AgentRole
    objective: str
    required_inputs: list[str] = Field(default_factory=list)
    allowed_tool_names: list[str] = Field(default_factory=list)


class SupervisorAssignmentPlan(BaseModel):
    role: Literal["supervisor"] = "supervisor"
    assignments: list[SupervisorAssignment] = Field(default_factory=list)
    summary: str


class RecoveryDecision(BaseModel):
    verdict: Literal["passed", "failed"]
    error_type: str | None = None
    recovery_action: Literal[
        "none",
        "retry",
        "replace_candidate",
        "expand_search_radius",
        "ask_user",
        "stop_safely",
    ] = "none"
    route_to: str | None = None
    retry_budget: int = 0
    reason: str


class RecoveryExcludedCandidatePair(BaseModel):
    activity_candidate_id: str
    dining_candidate_id: str


class RecoveryEvaluationContext(BaseModel):
    attempted_actions: list[str] = Field(default_factory=list)
    search_expansion_level: int = 0
    excluded_candidate_pairs: list[RecoveryExcludedCandidatePair] = Field(default_factory=list)
    screened_candidate_ids: list[str] = Field(default_factory=list)
    route_failure_codes: list[str] = Field(default_factory=list)
