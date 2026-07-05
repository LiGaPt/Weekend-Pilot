from __future__ import annotations

from collections import Counter
from pathlib import Path

from backend.app.benchmark import (
    list_benchmark_suites,
    load_benchmark_suite,
    load_registered_benchmark_cases,
)
from backend.app.benchmark.case_matrix import build_benchmark_case_matrix_manifest
from backend.app.providers.mock_world.loader import load_mock_world


SUPPORTED_MOCK_WORLD_PROFILES = (
    "family_afternoon",
    "friends_gathering",
    "solo_afternoon",
    "couple_afternoon",
    "rainy_day_fallback",
    "budget_lite",
    "elder_afternoon",
)
EXPECTED_ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 3,
    "couple_afternoon": 1,
    "elder_afternoon": 2,
    "family_afternoon": 16,
    "friends_gathering": 3,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
EXPECTED_V2_INTEGRITY_WORLD_PROFILE_COUNTS = {
    "budget_lite": 2,
    "elder_afternoon": 1,
    "family_afternoon": 12,
    "friends_gathering": 2,
    "rainy_day_fallback": 2,
    "solo_afternoon": 1,
}
EXPECTED_CORE_SUITE_COUNTS = {
    "default": 11,
    "expanded": 5,
    "recovery_focused": 8,
    "v2_integrity": 20,
    "all_registered": 30,
}
PUBLIC_MOCK_WORLD_PROFILES = (
    "family_afternoon",
    "friends_gathering",
    "solo_afternoon",
    "couple_afternoon",
    "rainy_day_fallback",
    "budget_lite",
)
STALE_CURRENT_STATE_DOC_PHRASES = (
    "五个默认 Mock World 家庭场景用例",
    "默认 Mock World 家庭场景用例",
)


def test_all_supported_mock_world_profiles_load() -> None:
    loaded_profiles = tuple(load_mock_world(profile)["profile"] for profile in SUPPORTED_MOCK_WORLD_PROFILES)

    assert loaded_profiles == SUPPORTED_MOCK_WORLD_PROFILES


def test_all_supported_profiles_have_registered_benchmark_representation() -> None:
    cases = load_registered_benchmark_cases()
    world_profile_counts = Counter(case.world_profile for case in cases)

    assert len(cases) == 30
    assert dict(sorted(world_profile_counts.items())) == EXPECTED_ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert set(SUPPORTED_MOCK_WORLD_PROFILES).issubset(world_profile_counts)


def test_case_matrix_suite_and_loaded_suite_counts_stay_aligned() -> None:
    manifest = build_benchmark_case_matrix_manifest()
    loaded_suite_counts = {
        suite_id: len(load_benchmark_suite(suite_id))
        for suite_id in EXPECTED_CORE_SUITE_COUNTS
    }

    assert manifest.registered_case_count == 30
    assert {suite_id: manifest.suite_counts[suite_id] for suite_id in EXPECTED_CORE_SUITE_COUNTS} == (
        EXPECTED_CORE_SUITE_COUNTS
    )
    assert loaded_suite_counts == EXPECTED_CORE_SUITE_COUNTS


def test_suite_descriptions_expose_multi_scenario_world_profile_summary() -> None:
    suites = {suite.suite_id: suite for suite in list_benchmark_suites()}

    assert suites["all_registered"].matrix_summary.world_profile_counts == (
        EXPECTED_ALL_REGISTERED_WORLD_PROFILE_COUNTS
    )
    assert suites["v2_integrity"].matrix_summary.world_profile_counts == (
        EXPECTED_V2_INTEGRITY_WORLD_PROFILE_COUNTS
    )
    assert suites["v2_integrity"].v2_taxonomy_summary is not None
    assert suites["v2_integrity"].v2_taxonomy_summary.case_count == 20


def test_public_mock_world_profiles_have_reviewable_non_failure_benchmark_cases() -> None:
    reviewable_cases = [
        case
        for case in load_benchmark_suite("default")
        if case.failure_profile is None and case.world_profile in PUBLIC_MOCK_WORLD_PROFILES
    ]

    assert {case.world_profile for case in reviewable_cases} == set(PUBLIC_MOCK_WORLD_PROFILES)
    assert all(case.tool_profile == "mock_world" for case in reviewable_cases)
    assert all(case.expected.expected_workflow_status == "completed" for case in reviewable_cases)
    assert all(case.expected.expected_execution_status == "succeeded" for case in reviewable_cases)
    assert all(case.expected.min_action_count >= 1 for case in reviewable_cases)


def test_current_docs_do_not_describe_mock_world_as_family_only() -> None:
    docs_to_check = (
        Path("README.md"),
        Path("docs/WEB_DEMO_README.md"),
        Path("docs/COMPETITION_DESIGN_DOCUMENT.md"),
        Path("docs/submission/EVIDENCE_MAP.md"),
        Path("docs/submission/DEMO_SCRIPT.md"),
    )
    stale_hits = [
        f"{path}:{phrase}"
        for path in docs_to_check
        for phrase in STALE_CURRENT_STATE_DOC_PHRASES
        if phrase in path.read_text(encoding="utf-8")
    ]

    assert stale_hits == []
