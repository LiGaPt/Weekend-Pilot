from __future__ import annotations

from typing import cast

from pydantic import BaseModel

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkCaseTaxonomy, BenchmarkSuiteId


ORDERED_BENCHMARK_SUITE_IDS: tuple[BenchmarkSuiteId, ...] = (
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


class BenchmarkCaseMatrixRow(BaseModel):
    case_id: str
    world_profile: str
    failure_profile: str | None
    suite_ids: tuple[BenchmarkSuiteId, ...]
    taxonomy: BenchmarkCaseTaxonomy


class BenchmarkCaseMatrixManifest(BaseModel):
    registered_case_count: int
    selected_suite_id: BenchmarkSuiteId | None = None
    suite_counts: dict[str, int]
    cases: list[BenchmarkCaseMatrixRow]


def _row(
    case_id: str,
    world_profile: str,
    failure_profile: str | None,
    suite_ids: tuple[BenchmarkSuiteId, ...],
    *,
    scenario_bucket: str,
    level: str,
    tags: list[str],
    failure_mode: str | None = None,
) -> BenchmarkCaseMatrixRow:
    return BenchmarkCaseMatrixRow(
        case_id=case_id,
        world_profile=world_profile,
        failure_profile=failure_profile,
        suite_ids=suite_ids,
        taxonomy=BenchmarkCaseTaxonomy(
            suite="locallife_bench_v1",
            scenario_bucket=cast(
                "literal['family','solo','friends','couple','elder','mixed','unknown']",
                scenario_bucket,
            ),
            level=cast("literal['L1','L2','L3','L4','L5']", level),
            tags=tags,
            failure_mode=failure_mode,
        ),
    )


_CASE_MATRIX_ROWS: tuple[BenchmarkCaseMatrixRow, ...] = (
    _row(
        "family_afternoon_v1",
        "family_afternoon",
        None,
        ("baseline", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="family",
        level="L1",
        tags=["baseline", "child_friendly", "light_meal"],
    ),
    _row(
        "family_indoor_light_meal_v1",
        "family_afternoon",
        None,
        ("baseline", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal"],
    ),
    _row(
        "family_outdoor_quick_dinner_v1",
        "family_afternoon",
        None,
        ("baseline", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "outdoor_activity", "quick_dinner"],
    ),
    _row(
        "family_memory_override_v1",
        "family_afternoon",
        None,
        ("baseline", "memory_governance", "default", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal", "memory_override"],
    ),
    _row(
        "family_citywalk_addon_v1",
        "family_afternoon",
        None,
        ("baseline", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="family",
        level="L1",
        tags=["addon_optional", "child_friendly", "citywalk"],
    ),
    _row(
        "solo_afternoon_v1",
        "solo_afternoon",
        None,
        ("baseline", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="solo",
        level="L1",
        tags=["baseline", "light_activity", "light_meal"],
    ),
    _row(
        "couple_afternoon_v1",
        "couple_afternoon",
        None,
        ("expanded", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="couple",
        level="L2",
        tags=["citywalk", "date_friendly", "light_meal"],
    ),
    _row(
        "friends_gathering_v1",
        "friends_gathering",
        None,
        ("expanded", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="friends",
        level="L2",
        tags=["casual_dining", "friends_group", "outdoor_activity"],
    ),
    _row(
        "rainy_day_fallback_v1",
        "rainy_day_fallback",
        None,
        ("expanded", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="mixed",
        level="L2",
        tags=["fallback", "indoor_activity", "rainy_day"],
    ),
    _row(
        "budget_lite_v1",
        "budget_lite",
        None,
        ("expanded", "default", "release_gate_v1", "all_registered"),
        scenario_bucket="unknown",
        level="L2",
        tags=["budget_limited", "free_activity", "quick_meal"],
    ),
    _row(
        "elder_afternoon_v1",
        "elder_afternoon",
        None,
        ("expanded", "default", "all_registered"),
        scenario_bucket="elder",
        level="L2",
        tags=["elder_friendly", "short_walk", "light_meal"],
    ),
    _row(
        "family_route_failure_v1",
        "family_afternoon",
        "route_unavailable_v0",
        ("recovery_focused", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "failure_injected", "light_meal", "route_failure"],
        failure_mode="route_unavailable",
    ),
    _row(
        "family_route_and_dining_unavailable_v1",
        "family_afternoon",
        "route_and_dining_unavailable_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L5",
        tags=["child_friendly", "composite_failure", "dining_unavailable", "failure_injected", "route_failure"],
        failure_mode="route_and_dining_unavailable",
    ),
    _row(
        "friends_route_and_dining_unavailable_v1",
        "friends_gathering",
        "route_and_dining_unavailable_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="friends",
        level="L5",
        tags=["composite_failure", "dining_unavailable", "failure_injected", "friends_group", "route_failure"],
        failure_mode="route_and_dining_unavailable",
    ),
    _row(
        "rainy_day_ticket_sold_out_v1",
        "rainy_day_fallback",
        "ticket_sold_out_and_bad_weather_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="mixed",
        level="L5",
        tags=["bad_weather", "composite_failure", "failure_injected", "rainy_day", "ticket_sold_out"],
        failure_mode="ticket_sold_out_and_bad_weather",
    ),
    _row(
        "family_ticket_sold_out_and_route_unavailable_v1",
        "family_afternoon",
        "ticket_sold_out_and_route_unavailable_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L5",
        tags=["child_friendly", "composite_failure", "failure_injected", "route_failure", "ticket_sold_out"],
        failure_mode="ticket_sold_out_and_route_unavailable",
    ),
    _row(
        "elder_ticket_sold_out_and_route_unavailable_v1",
        "elder_afternoon",
        "ticket_sold_out_and_route_unavailable_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="elder",
        level="L5",
        tags=["composite_failure", "elder_friendly", "failure_injected", "route_failure", "ticket_sold_out"],
        failure_mode="ticket_sold_out_and_route_unavailable",
    ),
    _row(
        "budget_queue_closed_constraint_v1",
        "budget_lite",
        "queue_closed_and_budget_constraint_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="mixed",
        level="L5",
        tags=["budget_limited", "composite_failure", "failure_injected"],
        failure_mode="queue_closed_and_budget_constraint",
    ),
    _row(
        "family_table_unavailable_replan_required_v1",
        "family_afternoon",
        "table_unavailable_and_replan_required_v0",
        ("recovery_focused", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L5",
        tags=["child_friendly", "composite_failure", "failure_injected", "replan_turn"],
        failure_mode="table_unavailable_and_replan_required",
    ),
    _row(
        "family_memory_advisory_fill_v1",
        "family_afternoon",
        None,
        ("memory_governance", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "light_meal", "memory_advisory", "memory_governance"],
    ),
    _row(
        "family_memory_expired_advisory_v1",
        "family_afternoon",
        None,
        ("memory_governance", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "indoor_activity", "memory_expired", "memory_governance"],
    ),
    _row(
        "family_memory_disabled_ignored_v1",
        "family_afternoon",
        None,
        ("memory_governance", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "memory_disabled", "memory_governance", "memory_ignored"],
    ),
    _row(
        "family_memory_candidate_not_auto_active_v1",
        "family_afternoon",
        None,
        ("memory_governance", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "memory_candidate", "memory_governance"],
    ),
    _row(
        "family_memory_sensitive_minimization_v1",
        "family_afternoon",
        None,
        ("memory_governance", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=[
            "child_friendly",
            "indoor_activity",
            "light_meal",
            "memory_candidate",
            "memory_governance",
            "sensitive_minimization",
        ],
    ),
    _row(
        "solo_clarification_continuation_v1",
        "solo_afternoon",
        None,
        ("conversation_continuations", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="solo",
        level="L3",
        tags=["clarification_turn", "conversation_continuation", "light_activity", "light_meal"],
    ),
    _row(
        "family_replan_version_continuation_v1",
        "family_afternoon",
        None,
        ("conversation_continuations", "release_gate_v1", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "conversation_continuation", "light_meal", "plan_versioning", "replan_turn"],
    ),
    _row(
        "family_distractor_selection_v1",
        "family_afternoon",
        None,
        ("robustness_focused", "v2_integrity", "all_registered"),
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "light_meal", "robustness_case", "distractor_selection"],
    ),
    _row(
        "friends_distractor_selection_v1",
        "friends_gathering",
        None,
        ("robustness_focused", "v2_integrity", "all_registered"),
        scenario_bucket="friends",
        level="L2",
        tags=["casual_dining", "friends_group", "outdoor_activity", "robustness_case", "distractor_selection"],
    ),
    _row(
        "rainy_day_stable_sorting_v1",
        "rainy_day_fallback",
        None,
        ("robustness_focused", "v2_integrity", "all_registered"),
        scenario_bucket="mixed",
        level="L2",
        tags=["rainy_day", "indoor_activity", "robustness_case", "stable_sorting"],
    ),
    _row(
        "budget_indoor_fallback_v1",
        "budget_lite",
        None,
        ("robustness_focused", "v2_integrity", "all_registered"),
        scenario_bucket="unknown",
        level="L2",
        tags=["budget_limited", "indoor_activity", "robustness_case", "fallback_selection"],
    ),
)


def list_benchmark_case_matrix_rows() -> tuple[BenchmarkCaseMatrixRow, ...]:
    return _CASE_MATRIX_ROWS


def get_registered_benchmark_case_ids() -> tuple[str, ...]:
    return tuple(row.case_id for row in _CASE_MATRIX_ROWS)


def get_benchmark_case_matrix_suite_case_ids(suite_id: BenchmarkSuiteId | str) -> tuple[str, ...]:
    canonical_suite_id = canonical_benchmark_case_matrix_suite_id(suite_id)
    return tuple(
        row.case_id
        for row in _CASE_MATRIX_ROWS
        if canonical_suite_id in row.suite_ids
    )


def get_benchmark_case_matrix_suite_ids_for_case(case_id: str) -> tuple[BenchmarkSuiteId, ...]:
    for row in _CASE_MATRIX_ROWS:
        if row.case_id == case_id:
            return row.suite_ids
    return ()


def build_benchmark_case_matrix_manifest(
    suite_id: BenchmarkSuiteId | str | None = None,
) -> BenchmarkCaseMatrixManifest:
    selected_suite_id = None if suite_id is None else canonical_benchmark_case_matrix_suite_id(suite_id)
    if selected_suite_id is None:
        cases = list(_CASE_MATRIX_ROWS)
    else:
        cases = [row for row in _CASE_MATRIX_ROWS if selected_suite_id in row.suite_ids]
    return BenchmarkCaseMatrixManifest(
        registered_case_count=len(_CASE_MATRIX_ROWS),
        selected_suite_id=selected_suite_id,
        suite_counts={
            suite_key: len(get_benchmark_case_matrix_suite_case_ids(suite_key))
            for suite_key in ORDERED_BENCHMARK_SUITE_IDS
        },
        cases=cases,
    )


def canonical_benchmark_case_matrix_suite_id(suite_id: BenchmarkSuiteId | str) -> BenchmarkSuiteId:
    canonical_suite_id = _SUITE_ALIASES.get(str(suite_id), str(suite_id))
    if canonical_suite_id not in ORDERED_BENCHMARK_SUITE_IDS:
        raise BenchmarkHarnessError(f"Unknown benchmark suite ID: {suite_id}")
    return cast(BenchmarkSuiteId, canonical_suite_id)


def _validate_case_matrix_rows() -> None:
    seen_case_ids: set[str] = set()
    for row in _CASE_MATRIX_ROWS:
        if row.case_id in seen_case_ids:
            raise BenchmarkHarnessError(f"Duplicate benchmark case matrix case ID: {row.case_id}")
        seen_case_ids.add(row.case_id)
        seen_suite_ids: set[BenchmarkSuiteId] = set()
        for suite_id in row.suite_ids:
            canonical_suite_id = canonical_benchmark_case_matrix_suite_id(suite_id)
            if canonical_suite_id in seen_suite_ids:
                raise BenchmarkHarnessError(
                    f"Benchmark case matrix row contains duplicate suite ID: {row.case_id} -> {suite_id}"
                )
            seen_suite_ids.add(canonical_suite_id)


_validate_case_matrix_rows()
