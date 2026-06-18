from __future__ import annotations

from typing import Any, cast

from backend.app.benchmark.case_matrix import (
    ORDERED_BENCHMARK_SUITE_IDS,
    canonical_benchmark_case_matrix_suite_id,
    get_benchmark_case_matrix_suite_case_ids,
    get_benchmark_case_matrix_suite_ids_for_case,
)
from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.matrix import (
    build_case_integrity_coverage_summary,
    build_case_matrix_summary,
    build_case_v2_matrix_summary,
)
from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkSuiteDescription, BenchmarkSuiteId


_ORDERED_SUITE_IDS: tuple[BenchmarkSuiteId, ...] = ORDERED_BENCHMARK_SUITE_IDS
_SUITE_ALIASES: dict[str, BenchmarkSuiteId] = {
    "failures": "recovery_focused",
}
_SUITE_DEFINITIONS: dict[BenchmarkSuiteId, dict[str, Any]] = {
    "baseline": {
        "title": "Baseline benchmark suite",
        "description": "Historical family-plus-solo non-failure benchmark baseline.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("baseline")),
    },
    "expanded": {
        "title": "Expanded scenario benchmark suite",
        "description": "Expanded non-failure scenario pack covering couple, friends, rainy-day, budget, and elder scenarios.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("expanded")),
    },
    "recovery_focused": {
        "title": "Recovery focused benchmark suite",
        "description": "Recovery-focused benchmark cases kept outside the non-failure suites.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("recovery_focused")),
    },
    "memory_governance": {
        "title": "Memory governance benchmark suite",
        "description": "Focused cases that prove memory helps when useful without overriding explicit user input.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("memory_governance")),
    },
    "conversation_continuations": {
        "title": "Conversation continuations benchmark suite",
        "description": "Mock World continuation cases that validate clarification and follow-up replan chains.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("conversation_continuations")),
    },
    "robustness_focused": {
        "title": "Robustness focused benchmark suite",
        "description": "Focused Mock World cases that prove noisy candidate selection, fallback behavior, and stable search ordering.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("robustness_focused")),
    },
    "default": {
        "title": "Default benchmark suite",
        "description": "Current eleven-case non-failure benchmark suite used by repository examples.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("default")),
    },
    "release_gate_v1": {
        "title": "Benchmark release gate v1",
        "description": "Blocking LocalLife-Bench L1-L3 release suite for formal V1 benchmark sign-off.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("release_gate_v1")),
    },
    "v2_integrity": {
        "title": "V2 integrity benchmark suite",
        "description": "Additive V2 integrity suite covering memory, recovery, continuation, robustness, and composite integrity stress using the current Mock World inventory.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("v2_integrity")),
    },
    "all_registered": {
        "title": "All registered benchmark cases",
        "description": "Current default, recovery-focused, memory-governance, continuation, and robustness cases in canonical repository order.",
        "case_ids": list(get_benchmark_case_matrix_suite_case_ids("all_registered")),
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
    return list(get_benchmark_case_matrix_suite_ids_for_case(case_id))


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
    return canonical_benchmark_case_matrix_suite_id(_SUITE_ALIASES.get(suite_id, suite_id))
