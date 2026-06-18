from __future__ import annotations

from backend.app.benchmark import load_benchmark_suite, load_registered_benchmark_cases
from backend.app.providers.mock_world.loader import load_mock_world


SUPPORTED_PROFILES = (
    "family_afternoon",
    "solo_afternoon",
    "couple_afternoon",
    "friends_gathering",
    "rainy_day_fallback",
    "budget_lite",
    "elder_afternoon",
)
EXPECTED_SUITE_COUNTS = {
    "default": 11,
    "expanded": 5,
    "recovery_focused": 8,
    "v2_integrity": 20,
    "all_registered": 30,
}


def test_mock_world_supported_profiles_match_current_taxonomy_breadth() -> None:
    loaded_profiles = tuple(load_mock_world(profile)["profile"] for profile in SUPPORTED_PROFILES)

    assert loaded_profiles == SUPPORTED_PROFILES


def test_benchmark_suites_match_current_mock_world_taxonomy_counts() -> None:
    assert {suite_id: len(load_benchmark_suite(suite_id)) for suite_id in EXPECTED_SUITE_COUNTS} == (
        EXPECTED_SUITE_COUNTS
    )


def test_registered_mock_world_benchmark_inventory_remains_at_thirty_cases() -> None:
    assert len(load_registered_benchmark_cases()) == 30
