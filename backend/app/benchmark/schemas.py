from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from backend.app.observability.summary import RunSummary
from backend.app.benchmark.timing import BenchmarkTimingSummary
from backend.app.workflow.timing import WorkflowTimingSummary


BenchmarkCaseStatus = Literal["passed", "failed", "error"]
BenchmarkReplayStatus = Literal["passed", "failed", "error"]
BenchmarkSuiteId = Literal[
    "baseline",
    "expanded",
    "recovery_focused",
    "memory_governance",
    "conversation_continuations",
    "default",
    "release_gate_v1",
    "all_registered",
]
_LOWER_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class BenchmarkMemoryItem(BaseModel):
    memory_type: str
    key: str
    value_json: dict[str, Any]
    text: str | None = None
    confidence: Decimal = Decimal("1.0")
    expires_at: datetime | None = None
    status: str = "active"


class BenchmarkMemoryDecisionExpectation(BaseModel):
    memory_key: str
    expected_outcome: str


class BenchmarkMemoryGovernanceExpectation(BaseModel):
    expected_policy_version: str
    expected_dimension_sources: dict[str, str] = Field(default_factory=dict)
    expected_dimension_tiers: dict[str, str] = Field(default_factory=dict)
    expected_memory_outcomes: list[BenchmarkMemoryDecisionExpectation] = Field(default_factory=list)


class BenchmarkContinuationRequest(BaseModel):
    mode: Literal["clarify", "replan"]
    user_input: str
    selected_plan_index: int = Field(default=0, ge=0)


class BenchmarkConversationExpectedStep(BaseModel):
    mode: Literal["start", "clarify", "replan", "confirm"]
    expected_status: str
    expected_version_label: str | None = None


class BenchmarkConversationExpectation(BaseModel):
    steps: list[BenchmarkConversationExpectedStep]
    required_turn_types: list[str] = Field(default_factory=list)


class BenchmarkConversationTraceStep(BaseModel):
    mode: Literal["start", "clarify", "replan", "confirm"]
    source_run_id: UUID | None
    run_id: UUID | None
    status: str
    version_label: str | None = None


class BenchmarkExpectedOutcome(BaseModel):
    required_tool_names: list[str]
    min_tool_event_count: int
    min_action_count: int
    expected_workflow_status: str = "completed"
    expected_execution_status: str | None = "succeeded"
    expected_feedback_status: str | None = "completed"
    expected_error_type: str | None = None
    expected_recovery_action: str | None = None
    min_injected_failure_count: int = 0
    memory_governance: BenchmarkMemoryGovernanceExpectation | None = None
    conversation: BenchmarkConversationExpectation | None = None


class BenchmarkCaseTaxonomy(BaseModel):
    suite: Literal["locallife_bench_v1"]
    scenario_bucket: Literal["family", "solo", "friends", "couple", "elder", "mixed", "unknown"]
    level: Literal["L1", "L2", "L3", "L4", "L5"]
    tags: list[str]
    failure_mode: str | None = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for tag in value:
            if not isinstance(tag, str) or not tag:
                raise ValueError("taxonomy tags must be non-empty strings")
            if _LOWER_SNAKE_CASE_PATTERN.fullmatch(tag) is None:
                raise ValueError("taxonomy tags must use lower_snake_case")
            if tag in seen:
                raise ValueError("taxonomy tags must be unique")
            seen.add(tag)
        return value

    @field_validator("failure_mode")
    @classmethod
    def validate_failure_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _LOWER_SNAKE_CASE_PATTERN.fullmatch(value) is None:
            raise ValueError("taxonomy failure_mode must use lower_snake_case")
        return value


class BenchmarkCase(BaseModel):
    case_id: str
    title: str
    user_input: str
    agent_version: str = "agent-v1"
    prompt_version: str = "prompt-v1"
    tool_profile: str = "mock_world"
    world_profile: str = "family_afternoon"
    failure_profile: str | None = None
    memory_items: list[BenchmarkMemoryItem] = Field(default_factory=list)
    continuations: list[BenchmarkContinuationRequest] = Field(default_factory=list)
    expected: BenchmarkExpectedOutcome
    taxonomy: BenchmarkCaseTaxonomy
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkScore(BaseModel):
    name: str
    score: float
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkFailureChainSummary(BaseModel):
    profile_id: str
    injected_effects: list[str] = Field(default_factory=list)
    recovery_actions: list[str] = Field(default_factory=list)
    attempt_count: int
    max_attempts: int
    bounded: bool
    terminal_workflow_status: str | None = None


class BenchmarkCaseResult(BaseModel):
    schema_version: str = "weekendpilot_benchmark_case_result_v1"
    case_id: str
    status: BenchmarkCaseStatus
    run_id: UUID | None = None
    trace_id: str | None = None
    run_summary: RunSummary | None = None
    taxonomy: BenchmarkCaseTaxonomy | None = None
    failure_chain_summary: BenchmarkFailureChainSummary | None = None
    scores: list[BenchmarkScore]
    overall_score: float
    tool_event_count: int
    action_count: int
    plan_status: str | None = None
    feedback_status: str | None = None
    observability_status: str | None = None
    workflow_status: str | None = None
    workflow_timing_summary: WorkflowTimingSummary | None = None
    workflow_node_history: list[str] = Field(default_factory=list)
    conversation_trace: list[BenchmarkConversationTraceStep] = Field(default_factory=list)
    conversation_turn_types: list[str] = Field(default_factory=list)
    agent_roles: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    report_path: str | None = None


class BenchmarkCaseMatrixSummary(BaseModel):
    schema_version: str = "weekendpilot_benchmark_case_matrix_v1"
    case_count: int
    scenario_bucket_counts: dict[str, int] = Field(default_factory=dict)
    level_counts: dict[str, int] = Field(default_factory=dict)
    tool_profile_counts: dict[str, int] = Field(default_factory=dict)
    world_profile_counts: dict[str, int] = Field(default_factory=dict)
    failure_mode_counts: dict[str, int] = Field(default_factory=dict)
    tag_counts: dict[str, int] = Field(default_factory=dict)


class BenchmarkSuiteDescription(BaseModel):
    suite_id: BenchmarkSuiteId
    title: str
    description: str
    case_ids: list[str]
    case_count: int
    matrix_summary: BenchmarkCaseMatrixSummary


class BenchmarkOutcomeBucketStats(BaseModel):
    case_count: int
    passed_count: int
    failed_count: int
    error_count: int
    pass_rate: float


class BenchmarkOutcomeRollup(BaseModel):
    schema_version: str = "weekendpilot_benchmark_outcome_rollup_v1"
    scenario_bucket_outcomes: dict[str, BenchmarkOutcomeBucketStats] = Field(default_factory=dict)
    constraint_tag_outcomes: dict[str, BenchmarkOutcomeBucketStats] = Field(default_factory=dict)
    failure_mode_outcomes: dict[str, BenchmarkOutcomeBucketStats] = Field(default_factory=dict)


class BenchmarkSummary(BaseModel):
    schema_version: str = "weekendpilot_benchmark_summary_v1"
    suite_id: BenchmarkSuiteId | None = None
    suite_title: str | None = None
    run_status: Literal["passed", "failed", "error"]
    case_count: int
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    benchmark_timing_summary: BenchmarkTimingSummary | None = None
    matrix_summary: BenchmarkCaseMatrixSummary | None = None
    outcome_rollup: BenchmarkOutcomeRollup | None = None


class BenchmarkRunReport(BaseModel):
    schema_version: str = "weekendpilot_benchmark_run_v1"
    run_status: Literal["passed", "failed", "error"]
    case_results: list[BenchmarkCaseResult]
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    benchmark_timing_summary: BenchmarkTimingSummary | None = None
    benchmark_summary: BenchmarkSummary | None = None
    report_path: str | None = None


class BenchmarkReplaySummary(BaseModel):
    status: str | None = None
    workflow_status: str | None = None
    observed_tool_names: list[str] = Field(default_factory=list)
    action_count: int = 0
    injected_failure_count: int = 0
    recovery_actions: list[str] = Field(default_factory=list)
    failure_chain_signature: list[str] = Field(default_factory=list)


class BenchmarkReplayMismatch(BaseModel):
    field: str
    source: Any
    replay: Any


class BenchmarkReplayCaseResult(BaseModel):
    schema_version: str = "weekendpilot_benchmark_replay_case_v1"
    case_id: str
    status: BenchmarkReplayStatus
    source: BenchmarkReplaySummary
    replay: BenchmarkReplaySummary
    mismatches: list[BenchmarkReplayMismatch] = Field(default_factory=list)
    replay_benchmark_status: str | None = None
    benchmark_report_path: str | None = None
    replay_report_path: str | None = None
    failure_reasons: list[str] = Field(default_factory=list)


class BenchmarkReplayRunReport(BaseModel):
    schema_version: str = "weekendpilot_benchmark_replay_run_v1"
    run_status: BenchmarkReplayStatus
    case_results: list[BenchmarkReplayCaseResult]
    passed_count: int
    failed_count: int
    error_count: int
