from __future__ import annotations

from collections import Counter
from typing import Sequence

from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkCaseMatrixSummary


def build_case_matrix_summary(cases: Sequence[BenchmarkCase]) -> BenchmarkCaseMatrixSummary:
    scenario_bucket_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    world_profile_counts: Counter[str] = Counter()
    failure_mode_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()

    for case in cases:
        taxonomy = case.taxonomy
        scenario_bucket_counts[taxonomy.scenario_bucket] += 1
        level_counts[taxonomy.level] += 1
        world_profile_counts[case.world_profile] += 1
        failure_mode_counts[taxonomy.failure_mode or "none"] += 1
        for tag in sorted(set(taxonomy.tags)):
            tag_counts[tag] += 1

    return BenchmarkCaseMatrixSummary(
        case_count=len(cases),
        scenario_bucket_counts=_sorted_counts(scenario_bucket_counts),
        level_counts=_sorted_counts(level_counts),
        world_profile_counts=_sorted_counts(world_profile_counts),
        failure_mode_counts=_sorted_counts(failure_mode_counts),
        tag_counts=_sorted_counts(tag_counts),
    )


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}
