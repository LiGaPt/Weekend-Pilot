from __future__ import annotations

from typing import Any, cast

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.matrix import (
    build_case_integrity_coverage_summary,
    build_case_matrix_summary,
    build_case_v2_matrix_summary,
)
from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkSuiteDescription, BenchmarkSuiteId


_BASELINE_CASE_IDS = [
    "family_afternoon_v1",
    "family_indoor_light_meal_v1",
    "family_outdoor_quick_dinner_v1",
    "family_memory_override_v1",
    "family_citywalk_addon_v1",
    "solo_afternoon_v1",
]
_EXPANDED_CASE_IDS = [
    "couple_afternoon_v1",
    "friends_gathering_v1",
    "rainy_day_fallback_v1",
    "budget_lite_v1",
    "elder_afternoon_v1",
]
_RECOVERY_FOCUSED_CASE_IDS = [
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "friends_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
    "family_ticket_sold_out_and_route_unavailable_v1",
    "elder_ticket_sold_out_and_route_unavailable_v1",
    "budget_queue_closed_constraint_v1",
    "family_table_unavailable_replan_required_v1",
]
_MEMORY_GOVERNANCE_CASE_IDS = [
    "family_memory_override_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    "family_memory_disabled_ignored_v1",
    "family_memory_candidate_not_auto_active_v1",
    "family_memory_sensitive_minimization_v1",
]
_CONVERSATION_CONTINUATION_CASE_IDS = [
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
]
_ROBUSTNESS_FOCUSED_CASE_IDS = [
    "family_distractor_selection_v1",
    "friends_distractor_selection_v1",
    "rainy_day_stable_sorting_v1",
    "budget_indoor_fallback_v1",
]
_DEFAULT_CASE_IDS = [*_BASELINE_CASE_IDS, *_EXPANDED_CASE_IDS]
_RELEASE_GATE_V1_CASE_IDS = [
    *_BASELINE_CASE_IDS,
    "couple_afternoon_v1",
    "friends_gathering_v1",
    "rainy_day_fallback_v1",
    "budget_lite_v1",
    "family_route_failure_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    *_CONVERSATION_CONTINUATION_CASE_IDS,
]
_ALL_REGISTERED_CASE_IDS = [
    *_DEFAULT_CASE_IDS,
    *_RECOVERY_FOCUSED_CASE_IDS,
    *_MEMORY_GOVERNANCE_CASE_IDS[1:],
    *_CONVERSATION_CONTINUATION_CASE_IDS,
    *_ROBUSTNESS_FOCUSED_CASE_IDS,
]
_V2_INTEGRITY_CASE_IDS = [
    "family_memory_override_v1",
    *_RECOVERY_FOCUSED_CASE_IDS,
    *_MEMORY_GOVERNANCE_CASE_IDS[1:],
    *_CONVERSATION_CONTINUATION_CASE_IDS,
    *_ROBUSTNESS_FOCUSED_CASE_IDS,
]
_ORDERED_SUITE_IDS: tuple[BenchmarkSuiteId, ...] = (
    "baseline",
    "expanded",
    "recovery_focused",
    "memory_governance",
    "conversation_continuations",
    "robustness_focused",
    "default",
    "release_gate_v1",
    "v2_integrity",
    "all_registered",
)
_SUITE_ALIASES: dict[str, BenchmarkSuiteId] = {
    "failures": "recovery_focused",
}
_SUITE_DEFINITIONS: dict[BenchmarkSuiteId, dict[str, Any]] = {
    "baseline": {
        "title": "Baseline benchmark suite",
        "description": "Historical family-plus-solo non-failure benchmark baseline.",
        "case_ids": _BASELINE_CASE_IDS,
    },
    "expanded": {
        "title": "Expanded scenario benchmark suite",
        "description": "Expanded non-failure scenario pack covering couple, friends, rainy-day, budget, and elder scenarios.",
        "case_ids": _EXPANDED_CASE_IDS,
    },
    "recovery_focused": {
        "title": "Recovery focused benchmark suite",
        "description": "Recovery-focused benchmark cases kept outside the non-failure suites.",
        "case_ids": _RECOVERY_FOCUSED_CASE_IDS,
    },
    "memory_governance": {
        "title": "Memory governance benchmark suite",
        "description": "Focused cases that prove memory helps when useful without overriding explicit user input.",
        "case_ids": _MEMORY_GOVERNANCE_CASE_IDS,
    },
    "conversation_continuations": {
        "title": "Conversation continuations benchmark suite",
        "description": "Mock World continuation cases that validate clarification and follow-up replan chains.",
        "case_ids": _CONVERSATION_CONTINUATION_CASE_IDS,
    },
    "robustness_focused": {
        "title": "Robustness focused benchmark suite",
        "description": "Focused Mock World cases that prove noisy candidate selection, fallback behavior, and stable search ordering.",
        "case_ids": _ROBUSTNESS_FOCUSED_CASE_IDS,
    },
    "default": {
        "title": "Default benchmark suite",
        "description": "Current eleven-case non-failure benchmark suite used by repository examples.",
        "case_ids": _DEFAULT_CASE_IDS,
    },
    "release_gate_v1": {
        "title": "Benchmark release gate v1",
        "description": "Blocking LocalLife-Bench L1-L3 release suite for formal V1 benchmark sign-off.",
        "case_ids": _RELEASE_GATE_V1_CASE_IDS,
    },
    "v2_integrity": {
        "title": "V2 integrity benchmark suite",
        "description": "Additive V2 integrity suite covering memory, recovery, continuation, robustness, and composite integrity stress using the current Mock World inventory.",
        "case_ids": _V2_INTEGRITY_CASE_IDS,
    },
    "all_registered": {
        "title": "All registered benchmark cases",
        "description": "Current default, recovery-focused, memory-governance, continuation, and robustness cases in canonical repository order.",
        "case_ids": _ALL_REGISTERED_CASE_IDS,
    },
}


def load_benchmark_suite(suite_id: BenchmarkSuiteId | str) -> list[BenchmarkCase]:
    definition = _validated_suite_definition(str(suite_id))
    from backend.app.benchmark.fixtures import load_benchmark_case

    return [load_benchmark_case(case_id) for case_id in definition["case_ids"]]


def list_benchmark_suites() -> list[BenchmarkSuiteDescription]:
    from backend.app.benchmark.fixtures import load_benchmark_case

    suites: list[BenchmarkSuiteDescription] = []
    for suite_id in _ORDERED_SUITE_IDS:
        definition = _validated_suite_definition(suite_id)
        cases = [load_benchmark_case(case_id) for case_id in definition["case_ids"]]
        suites.append(
            BenchmarkSuiteDescription(
                suite_id=suite_id,
                title=definition["title"],
                description=definition["description"],
                case_ids=list(definition["case_ids"]),
                case_count=len(cases),
                matrix_summary=build_case_matrix_summary(cases),
                v2_taxonomy_summary=build_case_v2_matrix_summary(cases),
                integrity_coverage_summary=build_case_integrity_coverage_summary(cases),
            )
        )
    return suites


def list_benchmark_suite_ids_for_case(case_id: str) -> list[BenchmarkSuiteId]:
    matching_suite_ids: list[BenchmarkSuiteId] = []
    for suite_id in _ORDERED_SUITE_IDS:
        definition = _validated_suite_definition(suite_id)
        if case_id in definition["case_ids"]:
            matching_suite_ids.append(suite_id)
    return matching_suite_ids


def load_default_benchmark_cases() -> list[BenchmarkCase]:
    return load_benchmark_suite("default")


def load_failure_benchmark_cases() -> list[BenchmarkCase]:
    return load_benchmark_suite("recovery_focused")


def _validated_suite_definition(suite_id: str) -> dict[str, Any]:
    canonical_suite_id = _canonical_suite_id(suite_id)
    if canonical_suite_id not in _SUITE_DEFINITIONS:
        raise BenchmarkHarnessError(f"Unknown benchmark suite ID: {suite_id}")

    definition = _SUITE_DEFINITIONS[canonical_suite_id]
    case_ids = definition.get("case_ids")
    if not isinstance(case_ids, list):
        raise BenchmarkHarnessError(f"Benchmark suite {canonical_suite_id} has invalid case_ids.")

    from backend.app.benchmark.fixtures import load_registered_benchmark_cases

    registered_case_ids = {case.case_id for case in load_registered_benchmark_cases()}
    seen: set[str] = set()
    for case_id in case_ids:
        if case_id in seen:
            raise BenchmarkHarnessError(
                f"Benchmark suite {canonical_suite_id} contains duplicate case ID: {case_id}"
            )
        if case_id not in registered_case_ids:
            raise BenchmarkHarnessError(
                f"Benchmark suite {canonical_suite_id} references unknown case ID: {case_id}"
            )
        seen.add(case_id)
    return definition


def canonical_benchmark_suite_id(suite_id: BenchmarkSuiteId | str) -> BenchmarkSuiteId:
    canonical_suite_id = _canonical_suite_id(str(suite_id))
    if canonical_suite_id not in _SUITE_DEFINITIONS:
        raise BenchmarkHarnessError(f"Unknown benchmark suite ID: {suite_id}")
    return cast(BenchmarkSuiteId, canonical_suite_id)


def _canonical_suite_id(suite_id: str) -> str:
    return _SUITE_ALIASES.get(suite_id, suite_id)
