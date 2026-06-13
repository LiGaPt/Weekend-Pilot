from __future__ import annotations

from collections import Counter
from typing import Sequence

from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkIntegrityCoverageSummary,
    BenchmarkCaseMatrixSummary,
    BenchmarkCaseV2MatrixSummary,
    resolve_benchmark_case_v2_taxonomy,
)


def build_case_matrix_summary(cases: Sequence[BenchmarkCase]) -> BenchmarkCaseMatrixSummary:
    scenario_bucket_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    tool_profile_counts: Counter[str] = Counter()
    world_profile_counts: Counter[str] = Counter()
    failure_mode_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()

    for case in cases:
        taxonomy = case.taxonomy
        scenario_bucket_counts[taxonomy.scenario_bucket] += 1
        level_counts[taxonomy.level] += 1
        tool_profile_counts[case.tool_profile] += 1
        world_profile_counts[case.world_profile] += 1
        failure_mode_counts[taxonomy.failure_mode or "none"] += 1
        for tag in sorted(set(taxonomy.tags)):
            tag_counts[tag] += 1

    return BenchmarkCaseMatrixSummary(
        case_count=len(cases),
        scenario_bucket_counts=_sorted_counts(scenario_bucket_counts),
        level_counts=_sorted_counts(level_counts),
        tool_profile_counts=_sorted_counts(tool_profile_counts),
        world_profile_counts=_sorted_counts(world_profile_counts),
        failure_mode_counts=_sorted_counts(failure_mode_counts),
        tag_counts=_sorted_counts(tag_counts),
    )


def build_case_v2_matrix_summary(cases: Sequence[BenchmarkCase]) -> BenchmarkCaseV2MatrixSummary:
    scenario_bucket_counts: Counter[str] = Counter()
    level_counts: Counter[str] = Counter()
    failure_mode_counts: Counter[str] = Counter()
    memory_mode_counts: Counter[str] = Counter()
    conversation_mode_counts: Counter[str] = Counter()
    stability_required_counts: Counter[str] = Counter()

    for case in cases:
        taxonomy = resolve_benchmark_case_v2_taxonomy(case)
        scenario_bucket_counts[taxonomy.scenario_bucket] += 1
        level_counts[taxonomy.level] += 1
        failure_mode_counts[taxonomy.failure_mode] += 1
        memory_mode_counts[taxonomy.memory_mode] += 1
        conversation_mode_counts[taxonomy.conversation_mode] += 1
        stability_required_counts[str(taxonomy.stability_required).lower()] += 1

    return BenchmarkCaseV2MatrixSummary(
        case_count=len(cases),
        scenario_bucket_counts=_sorted_counts(scenario_bucket_counts),
        level_counts=_sorted_counts(level_counts),
        failure_mode_counts=_sorted_counts(failure_mode_counts),
        memory_mode_counts=_sorted_counts(memory_mode_counts),
        conversation_mode_counts=_sorted_counts(conversation_mode_counts),
        stability_required_counts=_sorted_counts(stability_required_counts),
    )


def build_case_integrity_coverage_summary(
    cases: Sequence[BenchmarkCase],
) -> BenchmarkIntegrityCoverageSummary:
    memory_case_count = 0
    recovery_case_count = 0
    continuation_case_count = 0
    robustness_case_count = 0
    l4_case_count = 0

    for case in cases:
        taxonomy = resolve_benchmark_case_v2_taxonomy(case)
        if taxonomy.memory_mode != "none":
            memory_case_count += 1
        if taxonomy.failure_mode != "none":
            recovery_case_count += 1
        if taxonomy.conversation_mode != "single_turn":
            continuation_case_count += 1
        if "robustness_case" in set(case.taxonomy.tags) or case.expected.robustness is not None:
            robustness_case_count += 1
        if taxonomy.level == "L4":
            l4_case_count += 1

    return BenchmarkIntegrityCoverageSummary(
        case_count=len(cases),
        memory_case_count=memory_case_count,
        recovery_case_count=recovery_case_count,
        continuation_case_count=continuation_case_count,
        robustness_case_count=robustness_case_count,
        l4_case_count=l4_case_count,
    )


def _sorted_counts(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}
