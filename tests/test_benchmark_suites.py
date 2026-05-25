from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.benchmark import (
    BenchmarkHarnessError,
    BenchmarkSuiteDescription,
    list_benchmark_suites,
    load_benchmark_case,
    load_benchmark_suite,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
    load_registered_benchmark_cases,
)
import backend.app.benchmark.fixtures as benchmark_fixtures
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
    "family_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
]
BASELINE_CASE_IDS = REGISTERED_CASE_IDS[:6]
EXPANDED_CASE_IDS = REGISTERED_CASE_IDS[6:10]
RECOVERY_FOCUSED_CASE_IDS = [
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
]
MEMORY_GOVERNANCE_CASE_IDS = [
    "family_memory_override_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
]
CONVERSATION_CONTINUATION_CASE_IDS = [
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
]
DEFAULT_CASE_IDS = BASELINE_CASE_IDS + EXPANDED_CASE_IDS
RELEASE_GATE_V1_CASE_IDS = [
    *DEFAULT_CASE_IDS,
    "family_route_failure_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    *CONVERSATION_CONTINUATION_CASE_IDS,
]
CANONICAL_SUITE_IDS = [
    "baseline",
    "expanded",
    "recovery_focused",
    "memory_governance",
    "conversation_continuations",
    "default",
    "release_gate_v1",
    "all_registered",
]
BASELINE_SCENARIO_BUCKET_COUNTS = {"family": 5, "solo": 1}
BASELINE_LEVEL_COUNTS = {"L1": 3, "L2": 3}
BASELINE_TOOL_PROFILE_COUNTS = {"mock_world": 6}
BASELINE_WORLD_PROFILE_COUNTS = {"family_afternoon": 5, "solo_afternoon": 1}
BASELINE_FAILURE_MODE_COUNTS = {"none": 6}
BASELINE_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "child_friendly": 5,
    "citywalk": 1,
    "indoor_activity": 2,
    "light_activity": 1,
    "light_meal": 4,
    "memory_override": 1,
    "outdoor_activity": 1,
    "quick_dinner": 1,
}
EXPANDED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "friends": 1,
    "mixed": 1,
    "unknown": 1,
}
EXPANDED_LEVEL_COUNTS = {"L2": 4}
EXPANDED_TOOL_PROFILE_COUNTS = {"mock_world": 4}
EXPANDED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
}
EXPANDED_FAILURE_MODE_COUNTS = {"none": 4}
EXPANDED_TAG_COUNTS = {
    "budget_limited": 1,
    "casual_dining": 1,
    "citywalk": 1,
    "date_friendly": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 1,
    "light_meal": 1,
    "outdoor_activity": 1,
    "quick_meal": 1,
    "rainy_day": 1,
}
RECOVERY_SCENARIO_BUCKET_COUNTS = {"family": 2, "mixed": 1}
RECOVERY_LEVEL_COUNTS = {"L2": 1, "L5": 2}
RECOVERY_TOOL_PROFILE_COUNTS = {"mock_world": 3}
RECOVERY_WORLD_PROFILE_COUNTS = {"family_afternoon": 2, "rainy_day_fallback": 1}
RECOVERY_FAILURE_MODE_COUNTS = {
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
RECOVERY_TAG_COUNTS = {
    "bad_weather": 1,
    "child_friendly": 2,
    "composite_failure": 2,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "light_meal": 1,
    "rainy_day": 1,
    "route_failure": 2,
    "ticket_sold_out": 1,
}
DEFAULT_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 5,
    "friends": 1,
    "mixed": 1,
    "solo": 1,
    "unknown": 1,
}
DEFAULT_LEVEL_COUNTS = {"L1": 3, "L2": 7}
DEFAULT_TOOL_PROFILE_COUNTS = {"mock_world": 10}
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
MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS = {"family": 3}
MEMORY_GOVERNANCE_LEVEL_COUNTS = {"L2": 1, "L3": 2}
MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS = {"mock_world": 3}
MEMORY_GOVERNANCE_WORLD_PROFILE_COUNTS = {"family_afternoon": 3}
MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS = {"none": 3}
MEMORY_GOVERNANCE_TAG_COUNTS = {
    "child_friendly": 3,
    "indoor_activity": 2,
    "light_meal": 2,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
}
CONVERSATION_CONTINUATION_SCENARIO_BUCKET_COUNTS = {"family": 1, "solo": 1}
CONVERSATION_CONTINUATION_LEVEL_COUNTS = {"L3": 2}
CONVERSATION_CONTINUATION_TOOL_PROFILE_COUNTS = {"mock_world": 2}
CONVERSATION_CONTINUATION_WORLD_PROFILE_COUNTS = {
    "family_afternoon": 1,
    "solo_afternoon": 1,
}
CONVERSATION_CONTINUATION_FAILURE_MODE_COUNTS = {"none": 2}
CONVERSATION_CONTINUATION_TAG_COUNTS = {
    "child_friendly": 1,
    "clarification_turn": 1,
    "conversation_continuation": 2,
    "light_activity": 1,
    "light_meal": 2,
    "plan_versioning": 1,
    "replan_turn": 1,
}
RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 9,
    "friends": 1,
    "mixed": 1,
    "solo": 2,
    "unknown": 1,
}
RELEASE_GATE_V1_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L3": 4}
RELEASE_GATE_V1_TOOL_PROFILE_COUNTS = {"mock_world": 15}
RELEASE_GATE_V1_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 9,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 2,
}
RELEASE_GATE_V1_FAILURE_MODE_COUNTS = {
    "none": 14,
    "route_unavailable": 1,
}
RELEASE_GATE_V1_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 9,
    "citywalk": 2,
    "clarification_turn": 1,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "failure_injected": 1,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 1,
    "replan_turn": 1,
    "route_failure": 1,
}
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "family": 10,
    "friends": 1,
    "mixed": 2,
    "solo": 2,
    "unknown": 1,
}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 8, "L3": 4, "L5": 2}
ALL_REGISTERED_TOOL_PROFILE_COUNTS = {"mock_world": 17}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "family_afternoon": 10,
    "friends_gathering": 1,
    "rainy_day_fallback": 2,
    "solo_afternoon": 2,
}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {
    "none": 14,
    "route_and_dining_unavailable": 1,
    "route_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
}
ALL_REGISTERED_TAG_COUNTS = {
    "addon_optional": 1,
    "bad_weather": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 10,
    "citywalk": 2,
    "clarification_turn": 1,
    "composite_failure": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "dining_unavailable": 1,
    "failure_injected": 3,
    "fallback": 1,
    "free_activity": 1,
    "friends_group": 1,
    "indoor_activity": 4,
    "light_activity": 2,
    "light_meal": 9,
    "memory_advisory": 1,
    "memory_expired": 1,
    "memory_governance": 2,
    "memory_override": 1,
    "outdoor_activity": 2,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 2,
    "replan_turn": 1,
    "route_failure": 2,
    "ticket_sold_out": 1,
}


def test_load_registered_benchmark_cases_returns_canonical_case_order() -> None:
    cases = load_registered_benchmark_cases()

    assert [case.case_id for case in cases] == REGISTERED_CASE_IDS


def test_load_benchmark_suite_returns_expected_named_membership() -> None:
    assert [case.case_id for case in load_benchmark_suite("baseline")] == BASELINE_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("expanded")] == EXPANDED_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("recovery_focused")] == RECOVERY_FOCUSED_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("memory_governance")] == MEMORY_GOVERNANCE_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("conversation_continuations")] == (
        CONVERSATION_CONTINUATION_CASE_IDS
    )
    assert [case.case_id for case in load_benchmark_suite("default")] == DEFAULT_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("release_gate_v1")] == RELEASE_GATE_V1_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("failures")] == RECOVERY_FOCUSED_CASE_IDS
    assert [case.case_id for case in load_benchmark_suite("all_registered")] == REGISTERED_CASE_IDS


def test_list_benchmark_suite_ids_for_case_returns_expected_membership() -> None:
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_afternoon_v1") == [
        "baseline",
        "default",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_memory_override_v1") == [
        "baseline",
        "memory_governance",
        "default",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("couple_afternoon_v1") == [
        "expanded",
        "default",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_route_failure_v1") == [
        "recovery_focused",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_memory_advisory_fill_v1") == [
        "memory_governance",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("solo_clarification_continuation_v1") == [
        "conversation_continuations",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_replan_version_continuation_v1") == [
        "conversation_continuations",
        "release_gate_v1",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("family_route_and_dining_unavailable_v1") == [
        "recovery_focused",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("rainy_day_ticket_sold_out_v1") == [
        "recovery_focused",
        "all_registered",
    ]
    assert benchmark_suites.list_benchmark_suite_ids_for_case("missing_case_v1") == []


def test_legacy_suite_wrappers_delegate_to_named_suites() -> None:
    assert [case.case_id for case in load_default_benchmark_cases()] == [
        case.case_id for case in load_benchmark_suite("default")
    ]
    assert [case.case_id for case in load_failure_benchmark_cases()] == [
        case.case_id for case in load_benchmark_suite("recovery_focused")
    ]


def test_list_benchmark_suites_returns_descriptions_in_deterministic_order() -> None:
    suites = list_benchmark_suites()

    assert [suite.suite_id for suite in suites] == CANONICAL_SUITE_IDS
    assert all(isinstance(suite, BenchmarkSuiteDescription) for suite in suites)

    suite_map = {suite.suite_id: suite for suite in suites}

    _assert_suite_description(
        suite_map["baseline"],
        case_ids=BASELINE_CASE_IDS,
        case_count=6,
        scenario_bucket_counts=BASELINE_SCENARIO_BUCKET_COUNTS,
        level_counts=BASELINE_LEVEL_COUNTS,
        tool_profile_counts=BASELINE_TOOL_PROFILE_COUNTS,
        world_profile_counts=BASELINE_WORLD_PROFILE_COUNTS,
        failure_mode_counts=BASELINE_FAILURE_MODE_COUNTS,
        tag_counts=BASELINE_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["expanded"],
        case_ids=EXPANDED_CASE_IDS,
        case_count=4,
        scenario_bucket_counts=EXPANDED_SCENARIO_BUCKET_COUNTS,
        level_counts=EXPANDED_LEVEL_COUNTS,
        tool_profile_counts=EXPANDED_TOOL_PROFILE_COUNTS,
        world_profile_counts=EXPANDED_WORLD_PROFILE_COUNTS,
        failure_mode_counts=EXPANDED_FAILURE_MODE_COUNTS,
        tag_counts=EXPANDED_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["recovery_focused"],
        case_ids=RECOVERY_FOCUSED_CASE_IDS,
        case_count=3,
        scenario_bucket_counts=RECOVERY_SCENARIO_BUCKET_COUNTS,
        level_counts=RECOVERY_LEVEL_COUNTS,
        tool_profile_counts=RECOVERY_TOOL_PROFILE_COUNTS,
        world_profile_counts=RECOVERY_WORLD_PROFILE_COUNTS,
        failure_mode_counts=RECOVERY_FAILURE_MODE_COUNTS,
        tag_counts=RECOVERY_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["memory_governance"],
        case_ids=MEMORY_GOVERNANCE_CASE_IDS,
        case_count=3,
        scenario_bucket_counts=MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS,
        level_counts=MEMORY_GOVERNANCE_LEVEL_COUNTS,
        tool_profile_counts=MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS,
        world_profile_counts=MEMORY_GOVERNANCE_WORLD_PROFILE_COUNTS,
        failure_mode_counts=MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS,
        tag_counts=MEMORY_GOVERNANCE_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["conversation_continuations"],
        case_ids=CONVERSATION_CONTINUATION_CASE_IDS,
        case_count=2,
        scenario_bucket_counts=CONVERSATION_CONTINUATION_SCENARIO_BUCKET_COUNTS,
        level_counts=CONVERSATION_CONTINUATION_LEVEL_COUNTS,
        tool_profile_counts=CONVERSATION_CONTINUATION_TOOL_PROFILE_COUNTS,
        world_profile_counts=CONVERSATION_CONTINUATION_WORLD_PROFILE_COUNTS,
        failure_mode_counts=CONVERSATION_CONTINUATION_FAILURE_MODE_COUNTS,
        tag_counts=CONVERSATION_CONTINUATION_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["default"],
        case_ids=DEFAULT_CASE_IDS,
        case_count=10,
        scenario_bucket_counts=DEFAULT_SCENARIO_BUCKET_COUNTS,
        level_counts=DEFAULT_LEVEL_COUNTS,
        tool_profile_counts=DEFAULT_TOOL_PROFILE_COUNTS,
        world_profile_counts=DEFAULT_WORLD_PROFILE_COUNTS,
        failure_mode_counts=DEFAULT_FAILURE_MODE_COUNTS,
        tag_counts=DEFAULT_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["release_gate_v1"],
        case_ids=RELEASE_GATE_V1_CASE_IDS,
        case_count=15,
        scenario_bucket_counts=RELEASE_GATE_V1_SCENARIO_BUCKET_COUNTS,
        level_counts=RELEASE_GATE_V1_LEVEL_COUNTS,
        tool_profile_counts=RELEASE_GATE_V1_TOOL_PROFILE_COUNTS,
        world_profile_counts=RELEASE_GATE_V1_WORLD_PROFILE_COUNTS,
        failure_mode_counts=RELEASE_GATE_V1_FAILURE_MODE_COUNTS,
        tag_counts=RELEASE_GATE_V1_TAG_COUNTS,
    )
    _assert_suite_description(
        suite_map["all_registered"],
        case_ids=REGISTERED_CASE_IDS,
        case_count=17,
        scenario_bucket_counts=ALL_REGISTERED_SCENARIO_BUCKET_COUNTS,
        level_counts=ALL_REGISTERED_LEVEL_COUNTS,
        tool_profile_counts=ALL_REGISTERED_TOOL_PROFILE_COUNTS,
        world_profile_counts=ALL_REGISTERED_WORLD_PROFILE_COUNTS,
        failure_mode_counts=ALL_REGISTERED_FAILURE_MODE_COUNTS,
        tag_counts=ALL_REGISTERED_TAG_COUNTS,
    )


def test_canonical_fixture_and_suite_loading_reject_non_mock_world_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_id = "family_afternoon_v1"
    fixture_payload = load_benchmark_case(case_id).model_dump(mode="json")
    fixture_payload["tool_profile"] = "amap"
    fixture_root = Path("var/test-benchmark-fixtures") / str(uuid4())

    try:
        cases_dir = fixture_root / "cases"
        cases_dir.mkdir(parents=True)
        (cases_dir / f"{case_id}.json").write_text(json.dumps(fixture_payload), encoding="utf-8")

        monkeypatch.setattr(benchmark_fixtures, "_REGISTERED_CASE_IDS", (case_id,))
        monkeypatch.setattr(benchmark_fixtures.resources, "files", lambda _: fixture_root)
        monkeypatch.setattr(benchmark_suites, "_ORDERED_SUITE_IDS", ("default",))
        monkeypatch.setattr(
            benchmark_suites,
            "_SUITE_DEFINITIONS",
            {
                "default": {
                    "title": "Default suite",
                    "description": "Invalid canonical suite",
                    "case_ids": [case_id],
                }
            },
        )
        message = "Canonical benchmark case must use tool_profile='mock_world': family_afternoon_v1 -> amap"

        with pytest.raises(BenchmarkHarnessError) as exc_info:
            load_benchmark_case(case_id)
        assert str(exc_info.value) == message

        with pytest.raises(BenchmarkHarnessError) as exc_info:
            load_registered_benchmark_cases()
        assert str(exc_info.value) == message

        with pytest.raises(BenchmarkHarnessError) as exc_info:
            load_benchmark_suite("default")
        assert str(exc_info.value) == message

        with pytest.raises(BenchmarkHarnessError) as exc_info:
            list_benchmark_suites()
        assert str(exc_info.value) == message
    finally:
        fixture_file = fixture_root / "cases" / f"{case_id}.json"
        if fixture_file.exists():
            fixture_file.unlink()
        cases_dir = fixture_root / "cases"
        if cases_dir.exists():
            cases_dir.rmdir()
        if fixture_root.exists():
            fixture_root.rmdir()
        parent = fixture_root.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


def test_load_benchmark_suite_rejects_unknown_suite_id() -> None:
    with pytest.raises(BenchmarkHarnessError, match="Unknown benchmark suite ID: missing"):
        load_benchmark_suite("missing")


def test_list_benchmark_suites_rejects_duplicate_case_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        benchmark_suites,
        "_SUITE_DEFINITIONS",
        {
            "baseline": {
                "title": "Duplicate suite",
                "description": "Invalid",
                "case_ids": ["family_afternoon_v1", "family_afternoon_v1"],
            },
            "expanded": {
                "title": "Expanded suite",
                "description": "Expanded cases",
                "case_ids": EXPANDED_CASE_IDS,
            },
            "recovery_focused": {
                "title": "Recovery suite",
                "description": "Recovery cases",
                "case_ids": RECOVERY_FOCUSED_CASE_IDS,
            },
            "memory_governance": {
                "title": "Memory governance suite",
                "description": "Memory governance cases",
                "case_ids": MEMORY_GOVERNANCE_CASE_IDS,
            },
            "conversation_continuations": {
                "title": "Conversation continuations suite",
                "description": "Continuation cases",
                "case_ids": CONVERSATION_CONTINUATION_CASE_IDS,
            },
            "default": {
                "title": "Default suite",
                "description": "Default cases",
                "case_ids": DEFAULT_CASE_IDS,
            },
            "release_gate_v1": {
                "title": "Release gate v1 suite",
                "description": "Blocking V1 release gate cases",
                "case_ids": RELEASE_GATE_V1_CASE_IDS,
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
            "baseline": {
                "title": "Baseline suite",
                "description": "Baseline cases",
                "case_ids": BASELINE_CASE_IDS,
            },
            "expanded": {
                "title": "Expanded suite",
                "description": "Expanded cases",
                "case_ids": EXPANDED_CASE_IDS,
            },
            "recovery_focused": {
                "title": "Recovery suite",
                "description": "Recovery cases",
                "case_ids": RECOVERY_FOCUSED_CASE_IDS,
            },
            "memory_governance": {
                "title": "Memory governance suite",
                "description": "Memory governance cases",
                "case_ids": MEMORY_GOVERNANCE_CASE_IDS,
            },
            "conversation_continuations": {
                "title": "Conversation continuations suite",
                "description": "Continuation cases",
                "case_ids": CONVERSATION_CONTINUATION_CASE_IDS,
            },
            "default": {
                "title": "Default suite",
                "description": "Default cases",
                "case_ids": DEFAULT_CASE_IDS,
            },
            "release_gate_v1": {
                "title": "Release gate v1 suite",
                "description": "Blocking V1 release gate cases",
                "case_ids": RELEASE_GATE_V1_CASE_IDS,
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


def _assert_suite_description(
    suite: BenchmarkSuiteDescription,
    *,
    case_ids: list[str],
    case_count: int,
    scenario_bucket_counts: dict[str, int],
    level_counts: dict[str, int],
    tool_profile_counts: dict[str, int],
    world_profile_counts: dict[str, int],
    failure_mode_counts: dict[str, int],
    tag_counts: dict[str, int],
) -> None:
    assert suite.case_ids == case_ids
    assert suite.case_count == case_count
    assert suite.matrix_summary.scenario_bucket_counts == scenario_bucket_counts
    assert suite.matrix_summary.level_counts == level_counts
    assert suite.matrix_summary.tool_profile_counts == tool_profile_counts
    assert suite.matrix_summary.world_profile_counts == world_profile_counts
    assert suite.matrix_summary.failure_mode_counts == failure_mode_counts
    assert suite.matrix_summary.tag_counts == tag_counts
