from __future__ import annotations

import pytest

from backend.app.benchmark import (
    BenchmarkHarnessError,
    BenchmarkSuiteDescription,
    list_benchmark_suites,
    load_benchmark_suite,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
    load_registered_benchmark_cases,
)
import backend.app.benchmark.suites as benchmark_suites


REGISTERED_CASE_IDS = [
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
]

DEFAULT_CASE_IDS = REGISTERED_CASE_IDS[:-1]
FAILURE_CASE_IDS = ["family_route_failure_v1"]
DEFAULT_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 5,
    "friends": 1,
    "mixed": 1,
    "solo": 1,
    "unknown": 1,
}
DEFAULT_LEVEL_COUNTS = {"L1": 3, "L2": 7}
DEFAULT_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 1,
}
DEFAULT_FAILURE_MODE_COUNTS = {"none": 10}
DEFAULT_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 5,
    "citywalk": 2,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 5,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
}
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 6,
    "friends": 1,
    "mixed": 1,
    "solo": 1,
    "unknown": 1,
}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 8}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 6,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 1,
}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {"none": 10, "route_unavailable": 1}
ALL_REGISTERED_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 6,
    "citywalk": 2,
    "date_friendly": 1,
    "failure_injected": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 3,
    "light_activity": 1,
    "light_meal": 6,
    "memory_override": 1,
    "outdoor_activity": 2,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
    "route_failure": 1,
}


def test_load_registered_benchmark_cases_returns_canonical_case_order() -> None:
    cases = load_registered_benchmark_cases()

    assert [case.case_id for case in cases] == REGISTERED_CASE_IDS


def test_load_benchmark_suite_returns_expected_named_membership() -> None:
    assert [case.case_id for case in load_benchmark_suite("default")] == DEFAULT_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("failures")] == FAILURE_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("all_registered")] == REGISTERED_CASE_IDS


def test_list_benchmark_suite_ids_for_case_returns_expected_membership() -> None:
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_afternoon_v1") == [
        "default",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("couple_afternoon_v1") == [
        "default",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_route_failure_v1") == [
        "failures",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("missing_case_v1") == []


def test_legacy_suite_wrappers_delegate_to_named_suites() -> None:
    assert [case.case_id for case in load_default_benchmark_cases()] == [
        case.case_id for case in load_benchmark_suite("default")
    ]
    assert [case.case_id for case in load_failure_benchmark_cases()] == [
        case.case_id for case in load_benchmark_suite("failures")
    ]


def test_list_benchmark_suites_returns_descriptions_in_deterministic_order() -> None:
    suites = list_benchmark_suites()

    assert [suite.suite_id for suite in suites] == ["default", "failures", "all_registered"]
    assert all(isinstance(suite, BenchmarkSuiteDescription) for suite in suites)

    default = suites[0]
    assert default.case_ids == DEFAULT_CASE_IDS
    assert default.case_count == 10
    assert default.matrix_summary.scenario_bucket_counts == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert default.matrix_summary.level_counts == DEFAULT_LEVEL_COUNTS
    assert default.matrix_summary.world_profile_counts == DEFAULT_WORLD_PROFILE_COUNTS
    assert default.matrix_summary.failure_mode_counts == DEFAULT_FAILURE_MODE_COUNTS
    assert default.matrix_summary.tag_counts == DEFAULT_TAG_COUNTS

    all_registered = suites[2]
    assert all_registered.case_ids == REGISTERED_CASE_IDS
    assert all_registered.case_count == 11
    assert all_registered.matrix_summary.scenario_bucket_counts == ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    assert all_registered.matrix_summary.level_counts == ALL_REGISTERED_LEVEL_COUNTS
    assert all_registered.matrix_summary.world_profile_counts == ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert all_registered.matrix_summary.failure_mode_counts == ALL_REGISTERED_FAILURE_MODE_COUNTS
    assert all_registered.matrix_summary.tag_counts == ALL_REGISTERED_TAG_COUNTS


def test_load_benchmark_suite_rejects_unknown_suite_id() -> None:
    with pytest.raises(BenchmarkHarnessError, match="Unknown benchmark suite ID: missing"):
        load_benchmark_suite("missing")


def test_list_benchmark_suites_rejects_duplicate_case_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark_suites,
        "_SUITE_DEFINITIONS",
        {
            "default": {
                "title": "Duplicate suite",
                "description": "Invalid",
                "case_ids": ["family_afternoon_v1", "family_afternoon_v1"],
            },
            "failures": {
                "title": "Failure benchmark suite",
                "description": "Failure cases",
                "case_ids": ["family_route_failure_v1"],
            },
            "all_registered": {
                "title": "All registered benchmark cases",
                "description": "All cases",
                "case_ids": REGISTERED_CASE_IDS,
            },
        },
    )

    with pytest.raises(BenchmarkHarnessError, match="contains duplicate case ID: family_afternoon_v1"):
        list_benchmark_suites()


def test_list_benchmark_suites_rejects_unknown_registered_case_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        benchmark_suites,
        "_SUITE_DEFINITIONS",
        {
            "default": {
                "title": "Default benchmark suite",
                "description": "Default cases",
                "case_ids": ["family_afternoon_v1"],
            },
            "failures": {
                "title": "Failure benchmark suite",
                "description": "Failure cases",
                "case_ids": ["family_route_failure_v1"],
            },
            "all_registered": {
                "title": "All registered benchmark cases",
                "description": "All cases",
                "case_ids": ["family_afternoon_v1", "missing_case_v1"],
            },
        },
    )

    with pytest.raises(BenchmarkHarnessError, match="references unknown case ID: missing_case_v1"):
        list_benchmark_suites()
