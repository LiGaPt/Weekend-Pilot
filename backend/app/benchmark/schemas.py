from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.benchmark.timing import BenchmarkTimingSummary
from backend.app.workflow.timing import WorkflowTimingSummary


BenchmarkCaseStatus = Literal["passed", "failed", "error"]
BenchmarkReplayStatus = Literal["passed", "failed", "error"]


class BenchmarkMemoryItem(BaseModel):
    memory_type: str
    key: str
    value_json: dict[str, Any]
    text: str | None = None
    confidence: Decimal = Decimal("1.0")
    status: str = "active"


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
    expected: BenchmarkExpectedOutcome
    metadata: dict[str, Any] = Field(default_factory=dict)


class BenchmarkScore(BaseModel):
    name: str
    score: float
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCaseResult(BaseModel):
    schema_version: str = "weekendpilot_benchmark_case_result_v1"
    case_id: str
    status: BenchmarkCaseStatus
    run_id: UUID | None = None
    trace_id: str | None = None
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
    agent_roles: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    report_path: str | None = None


class BenchmarkRunReport(BaseModel):
    schema_version: str = "weekendpilot_benchmark_run_v1"
    run_status: Literal["passed", "failed", "error"]
    case_results: list[BenchmarkCaseResult]
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    benchmark_timing_summary: BenchmarkTimingSummary | None = None
    report_path: str | None = None


class BenchmarkReplaySummary(BaseModel):
    status: str | None = None
    workflow_status: str | None = None
    observed_tool_names: list[str] = Field(default_factory=list)
    action_count: int = 0
    injected_failure_count: int = 0
    recovery_actions: list[str] = Field(default_factory=list)


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
