from __future__ import annotations

from math import ceil
from typing import Any, Iterable

from pydantic import BaseModel, Field

from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES
from backend.app.workflow.timing import WorkflowTimingSummary


class BenchmarkTimingPercentileStats(BaseModel):
    sample_count: int
    min_ms: int
    p50_ms: int
    p95_ms: int
    p99_ms: int
    max_ms: int
    mean_ms: float


class BenchmarkStageTimingPercentileEntry(BenchmarkTimingPercentileStats):
    node_name: str
    retry_case_count: int


class BenchmarkTimingSummary(BaseModel):
    schema_version: str = "benchmark_timing_summary_v1"
    case_count: int
    overall_total_duration_ms: BenchmarkTimingPercentileStats | None = None
    stages: list[BenchmarkStageTimingPercentileEntry] = Field(default_factory=list)


def summarize_benchmark_timing(
    case_results: Iterable[Any],
    node_order: Iterable[str] = V1_WORKFLOW_NODE_NAMES,
) -> BenchmarkTimingSummary:
    results = list(case_results)
    timing_summaries = [_workflow_timing_summary(_result_value(result, "workflow_timing_summary")) for result in results]
    available = [summary for summary in timing_summaries if summary is not None]

    overall_values = [summary.total_duration_ms for summary in available]
    stage_samples: dict[str, list[int]] = {}
    stage_retry_counts: dict[str, int] = {}
    for node_name in node_order:
        stage_samples[node_name] = []
        stage_retry_counts[node_name] = 0

    for summary in available:
        for stage in summary.stages:
            if stage.node_name not in stage_samples:
                continue
            stage_samples[stage.node_name].append(stage.total_duration_ms)
            if stage.attempt_count > 1:
                stage_retry_counts[stage.node_name] += 1

    stages = []
    for node_name in node_order:
        values = stage_samples[node_name]
        stats = _build_stats(values)
        if stats is None:
            continue
        stages.append(
            BenchmarkStageTimingPercentileEntry(
                node_name=node_name,
                retry_case_count=stage_retry_counts[node_name],
                **stats.model_dump(),
            )
        )

    return BenchmarkTimingSummary(
        case_count=len(results),
        overall_total_duration_ms=_build_stats(overall_values),
        stages=stages,
    )


def nearest_rank_percentile(values: Iterable[int], percentile: float) -> int:
    ordered = sorted(int(value) for value in values)
    if not ordered:
        raise ValueError("nearest_rank_percentile requires at least one value.")
    sample_count = len(ordered)
    rank = ceil(percentile * sample_count)
    rank = max(1, min(rank, sample_count))
    return ordered[rank - 1]


def _build_stats(values: list[int]) -> BenchmarkTimingPercentileStats | None:
    if not values:
        return None
    ordered = sorted(int(value) for value in values)
    sample_count = len(ordered)
    return BenchmarkTimingPercentileStats(
        sample_count=sample_count,
        min_ms=ordered[0],
        p50_ms=nearest_rank_percentile(ordered, 0.50),
        p95_ms=nearest_rank_percentile(ordered, 0.95),
        p99_ms=nearest_rank_percentile(ordered, 0.99),
        max_ms=ordered[-1],
        mean_ms=round(sum(ordered) / sample_count, 2),
    )


def _workflow_timing_summary(value: Any) -> WorkflowTimingSummary | None:
    if isinstance(value, WorkflowTimingSummary):
        return value
    if isinstance(value, dict):
        return WorkflowTimingSummary.model_validate(value)
    return None


def _result_value(result: Any, name: str) -> Any:
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name, None)
