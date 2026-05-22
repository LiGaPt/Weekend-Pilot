from __future__ import annotations

from typing import Any

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.matrix import build_case_matrix_summary
from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkSuiteDescription, BenchmarkSuiteId


_ORDERED_SUITE_IDS: tuple[BenchmarkSuiteId, ...] = ("default", "failures", "all_registered")
_SUITE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "default": {
        "title": "Default benchmark suite",
        "description": "Current non-failure baseline suite used by repository benchmark examples.",
        "case_ids": [
            "family_afternoon_v1",
            "family_indoor_light_meal_v1",
            "family_outdoor_quick_dinner_v1",
            "family_memory_override_v1",
            "family_citywalk_addon_v1",
            "solo_afternoon_v1",
            "couple_afternoon_v1",
            "friends_gathering_v1",
            "rainy_day_fallback_v1",
            "budget_lite_v1",
        ],
    },
    "failures": {
        "title": "Failure benchmark suite",
        "description": "Current failure-injection benchmark cases kept outside the default suite.",
        "case_ids": [
            "family_route_failure_v1",
        ],
    },
    "all_registered": {
        "title": "All registered benchmark cases",
        "description": "Current default plus failure cases in canonical repository order.",
        "case_ids": [
            "family_afternoon_v1",
            "family_indoor_light_meal_v1",
            "family_outdoor_quick_dinner_v1",
            "family_memory_override_v1",
            "family_citywalk_addon_v1",
            "solo_afternoon_v1",
            "couple_afternoon_v1",
            "friends_gathering_v1",
            "rainy_day_fallback_v1",
            "budget_lite_v1",
            "family_route_failure_v1",
        ],
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
    return load_benchmark_suite("failures")


def _validated_suite_definition(suite_id: str) -> dict[str, Any]:
    if suite_id not in _SUITE_DEFINITIONS:
        raise BenchmarkHarnessError(f"Unknown benchmark suite ID: {suite_id}")

    definition = _SUITE_DEFINITIONS[suite_id]
    case_ids = definition.get("case_ids")
    if not isinstance(case_ids, list):
        raise BenchmarkHarnessError(f"Benchmark suite {suite_id} has invalid case_ids.")

    from backend.app.benchmark.fixtures import load_registered_benchmark_cases

    registered_case_ids = {case.case_id for case in load_registered_benchmark_cases()}
    seen: set[str] = set()
    for case_id in case_ids:
        if case_id in seen:
            raise BenchmarkHarnessError(f"Benchmark suite {suite_id} contains duplicate case ID: {case_id}")
        if case_id not in registered_case_ids:
            raise BenchmarkHarnessError(f"Benchmark suite {suite_id} references unknown case ID: {case_id}")
        seen.add(case_id)
    return definition
