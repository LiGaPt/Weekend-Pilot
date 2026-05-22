from __future__ import annotations

from typing import Sequence

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import (
    BenchmarkCaseResult,
    BenchmarkOutcomeBucketStats,
    BenchmarkOutcomeRollup,
)


_EXCLUDED_CONSTRAINT_TAGS = frozenset({"baseline", "failure_injected", "route_failure"})


def build_benchmark_outcome_rollup(results: Sequence[BenchmarkCaseResult]) -> BenchmarkOutcomeRollup:
    scenario_bucket_counts: dict[str, dict[str, int]] = {}
    constraint_tag_counts: dict[str, dict[str, int]] = {}
    failure_mode_counts: dict[str, dict[str, int]] = {}

    for result in results:
        taxonomy = result.taxonomy
        if taxonomy is None:
            raise BenchmarkHarnessError(f"Benchmark result missing taxonomy for rollup: {result.case_id}")

        _increment_bucket(scenario_bucket_counts, taxonomy.scenario_bucket, result.status)
        for tag in sorted({tag for tag in taxonomy.tags if tag not in _EXCLUDED_CONSTRAINT_TAGS}):
            _increment_bucket(constraint_tag_counts, tag, result.status)
        _increment_bucket(failure_mode_counts, taxonomy.failure_mode or "none", result.status)

    return BenchmarkOutcomeRollup(
        scenario_bucket_outcomes=_finalize_bucket_map(scenario_bucket_counts),
        constraint_tag_outcomes=_finalize_bucket_map(constraint_tag_counts),
        failure_mode_outcomes=_finalize_bucket_map(failure_mode_counts),
    )


def _increment_bucket(bucket_map: dict[str, dict[str, int]], bucket: str, status: str) -> None:
    counts = bucket_map.setdefault(
        bucket,
        {
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "error_count": 0,
        },
    )
    counts["case_count"] += 1
    counts[f"{status}_count"] += 1


def _finalize_bucket_map(bucket_map: dict[str, dict[str, int]]) -> dict[str, BenchmarkOutcomeBucketStats]:
    return {
        bucket: BenchmarkOutcomeBucketStats(
            case_count=counts["case_count"],
            passed_count=counts["passed_count"],
            failed_count=counts["failed_count"],
            error_count=counts["error_count"],
            pass_rate=_pass_rate(counts["passed_count"], counts["case_count"]),
        )
        for bucket, counts in sorted(bucket_map.items())
    }


def _pass_rate(passed_count: int, case_count: int) -> float:
    if case_count == 0:
        return 0.0
    return round(passed_count / case_count, 4)
