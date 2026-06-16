from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.benchmark import (
    BenchmarkHarness,
    load_benchmark_case,
    load_benchmark_suite,
    load_default_benchmark_cases,
    load_failure_benchmark_cases,
)
from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_chain import build_failure_chain_summary
import backend.app.benchmark.graders as benchmark_graders
import backend.app.benchmark.harness as benchmark_harness
from backend.app.benchmark.graders import (
    combine_scores,
    grade_conversation_path,
    grade_execution_safety,
    grade_failure_injection,
    grade_feedback,
    grade_memory_governance,
    grade_robustness_expectation,
    grade_recovery_expectation,
    grade_trajectory,
    grade_workflow_path,
)
from backend.app.benchmark.reporting import write_case_report, write_run_report
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkConversationExpectation,
    BenchmarkConversationExpectedStep,
    BenchmarkConversationTraceStep,
    BenchmarkContinuationRequest,
    BenchmarkMemoryDecisionExpectation,
    BenchmarkMemoryGovernanceExpectation,
    BenchmarkExpectedOutcome,
    BenchmarkRobustnessExpectation,
    BenchmarkRunReport,
    BenchmarkScore,
    BenchmarkSuiteDescription,
    BenchmarkSummary,
    resolve_benchmark_case_v2_taxonomy,
)
from backend.app.benchmark.matrix import build_case_integrity_coverage_summary, build_case_matrix_summary
from backend.app.benchmark.timing import summarize_benchmark_timing
from backend.app.core.config import Settings
from backend.app.workflow.timing import WorkflowStageTimingEntry, WorkflowTimingSummary
from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES


def _taxonomy_payload(
    *,
    scenario_bucket: str = "unknown",
    level: str = "L1",
    tags: list[str] | None = None,
    failure_mode: str | None = None,
) -> dict[str, object]:
    return {
        "suite": "locallife_bench_v1",
        "scenario_bucket": scenario_bucket,
        "level": level,
        "tags": tags or ["baseline"],
        "failure_mode": failure_mode,
    }


REQUIRED_WORKFLOW_NODES = V1_WORKFLOW_NODE_NAMES
REQUIRED_AGENT_ROLES = (
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
)
DEFAULT_CASE_IDS = (
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
    "elder_afternoon_v1",
)
FAILURE_CASE_IDS = (
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "friends_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1",
    "family_ticket_sold_out_and_route_unavailable_v1",
    "elder_ticket_sold_out_and_route_unavailable_v1",
    "budget_queue_closed_constraint_v1",
    "family_table_unavailable_replan_required_v1",
)
MEMORY_GOVERNANCE_CASE_IDS = (
    "family_memory_override_v1",
    "family_memory_advisory_fill_v1",
    "family_memory_expired_advisory_v1",
    "family_memory_disabled_ignored_v1",
    "family_memory_candidate_not_auto_active_v1",
    "family_memory_sensitive_minimization_v1",
)
CONTINUATION_CASE_IDS = (
    "solo_clarification_continuation_v1",
    "family_replan_version_continuation_v1",
)
ROBUSTNESS_CASE_IDS = (
    "family_distractor_selection_v1",
    "friends_distractor_selection_v1",
    "rainy_day_stable_sorting_v1",
    "budget_indoor_fallback_v1",
)
ROBUSTNESS_EXPECTATIONS_BY_CASE = {
    "family_distractor_selection_v1": {
        "world_profile": "family_afternoon",
        "selected_activity_id": "activity_museum_001",
        "selected_dining_id": "restaurant_light_001",
        "minimum_activity_search_results": 5,
        "minimum_dining_search_results": 5,
        "expected_activity_search_prefix": [
            "activity_museum_001",
            "activity_story_atelier_001",
            "activity_riverside_reading_001",
        ],
        "expected_dining_search_prefix": [
            "restaurant_light_001",
            "restaurant_picnic_001",
            "restaurant_garden_001",
        ],
        "required_unavailable_candidate_ids": [
            "activity_story_atelier_001",
            "restaurant_picnic_001",
        ],
        "minimum_failed_route_pairs": 1,
    },
    "friends_distractor_selection_v1": {
        "world_profile": "friends_gathering",
        "selected_activity_id": "activity_lawn_301",
        "selected_dining_id": "restaurant_yard_301",
        "minimum_activity_search_results": 4,
        "minimum_dining_search_results": 4,
        "expected_activity_search_prefix": [
            "activity_lawn_301",
            "activity_arcade_301",
            "activity_promenade_301",
        ],
        "expected_dining_search_prefix": [
            "restaurant_yard_301",
            "restaurant_patio_301",
            "restaurant_bistro_301",
        ],
        "required_unavailable_candidate_ids": [
            "activity_arcade_301",
            "restaurant_patio_301",
        ],
        "minimum_failed_route_pairs": 1,
    },
    "rainy_day_stable_sorting_v1": {
        "world_profile": "rainy_day_fallback",
        "selected_activity_id": "activity_market_401",
        "selected_dining_id": "restaurant_soup_401",
        "minimum_activity_search_results": 4,
        "minimum_dining_search_results": 4,
        "expected_activity_search_prefix": [
            "activity_market_401",
            "activity_arcade_401",
            "activity_gardenhall_401",
        ],
        "expected_dining_search_prefix": [
            "restaurant_soup_401",
            "restaurant_hotpot_401",
            "restaurant_cafe_401",
        ],
        "required_unavailable_candidate_ids": [
            "activity_arcade_401",
            "restaurant_hotpot_401",
        ],
        "minimum_failed_route_pairs": 1,
    },
    "budget_indoor_fallback_v1": {
        "world_profile": "budget_lite",
        "selected_activity_id": "activity_gallery_501",
        "selected_dining_id": "restaurant_bento_501",
        "minimum_activity_search_results": 3,
        "minimum_dining_search_results": 4,
        "expected_activity_search_prefix": [
            "activity_workshop_501",
            "activity_designmall_501",
            "activity_gallery_501",
        ],
        "expected_dining_search_prefix": [
            "restaurant_bento_501",
            "restaurant_cafe_501",
            "restaurant_bistro_501",
        ],
        "required_unavailable_candidate_ids": [
            "activity_workshop_501",
            "restaurant_cafe_501",
        ],
        "minimum_failed_route_pairs": 1,
    },
}
REQUIRED_CASE_TOOL_NAMES = {
    "search_poi",
    "check_weather",
    "get_poi_detail",
    "check_opening_hours",
    "check_queue",
    "check_table_availability",
    "check_ticket_availability",
    "check_route",
}
DEFAULT_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "elder": 1,
    "family": 5,
    "friends": 1,
    "mixed": 1,
    "solo": 1,
    "unknown": 1,
}
DEFAULT_LEVEL_COUNTS = {"L1": 3, "L2": 8}
DEFAULT_TOOL_PROFILE_COUNTS = {"mock_world": 11}
DEFAULT_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "couple_afternoon": 1,
    "elder_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
    "solo_afternoon": 1,
}
DEFAULT_FAILURE_MODE_COUNTS = {"none": 11}
DEFAULT_TAG_COUNTS = {
    "addon_optional": 1,
    "baseline": 2,
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 5,
    "citywalk": 2,
    "date_friendly": 1,
    "elder_friendly": 1,
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
    "short_walk": 1,
}
MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS = {"family": 6}
MEMORY_GOVERNANCE_LEVEL_COUNTS = {"L2": 1, "L3": 5}
MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS = {"mock_world": 6}
MEMORY_GOVERNANCE_WORLD_PROFILE_COUNTS = {"family_afternoon": 6}
MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS = {"none": 6}
MEMORY_GOVERNANCE_TAG_COUNTS = {
    "child_friendly": 6,
    "indoor_activity": 3,
    "light_meal": 3,
    "memory_advisory": 1,
    "memory_candidate": 2,
    "memory_disabled": 1,
    "memory_expired": 1,
    "memory_governance": 5,
    "memory_ignored": 1,
    "memory_override": 1,
    "sensitive_minimization": 1,
}
ROBUSTNESS_SCENARIO_BUCKET_COUNTS = {"family": 1, "friends": 1, "mixed": 1, "unknown": 1}
ROBUSTNESS_LEVEL_COUNTS = {"L2": 4}
ROBUSTNESS_TOOL_PROFILE_COUNTS = {"mock_world": 4}
ROBUSTNESS_WORLD_PROFILE_COUNTS = {
    "budget_lite": 1,
    "family_afternoon": 1,
    "friends_gathering": 1,
    "rainy_day_fallback": 1,
}
ROBUSTNESS_FAILURE_MODE_COUNTS = {"none": 4}
ROBUSTNESS_TAG_COUNTS = {
    "budget_limited": 1,
    "casual_dining": 1,
    "child_friendly": 1,
    "distractor_selection": 2,
    "fallback_selection": 1,
    "friends_group": 1,
    "indoor_activity": 2,
    "light_meal": 1,
    "outdoor_activity": 1,
    "rainy_day": 1,
    "robustness_case": 4,
    "stable_sorting": 1,
}
ALL_REGISTERED_SCENARIO_BUCKET_COUNTS = {
    "couple": 1,
    "elder": 2,
    "family": 16,
    "friends": 3,
    "mixed": 4,
    "solo": 2,
    "unknown": 2,
}
ALL_REGISTERED_LEVEL_COUNTS = {"L1": 3, "L2": 13, "L3": 7, "L5": 7}
ALL_REGISTERED_TOOL_PROFILE_COUNTS = {"mock_world": 30}
ALL_REGISTERED_WORLD_PROFILE_COUNTS = {
    "budget_lite": 3,
    "couple_afternoon": 1,
    "elder_afternoon": 2,
    "family_afternoon": 16,
    "friends_gathering": 3,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
ALL_REGISTERED_FAILURE_MODE_COUNTS = {
    "none": 22,
    "queue_closed_and_budget_constraint": 1,
    "route_and_dining_unavailable": 2,
    "route_unavailable": 1,
    "table_unavailable_and_replan_required": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 2,
}
ALL_REGISTERED_TAG_COUNTS = {
    "addon_optional": 1,
    "bad_weather": 1,
    "baseline": 2,
    "budget_limited": 3,
    "casual_dining": 2,
    "child_friendly": 16,
    "citywalk": 2,
    "clarification_turn": 1,
    "composite_failure": 7,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "distractor_selection": 2,
    "dining_unavailable": 2,
    "elder_friendly": 2,
    "failure_injected": 8,
    "fallback": 1,
    "fallback_selection": 1,
    "free_activity": 1,
    "friends_group": 3,
    "indoor_activity": 7,
    "light_activity": 2,
    "light_meal": 12,
    "memory_advisory": 1,
    "memory_candidate": 2,
    "memory_disabled": 1,
    "memory_expired": 1,
    "memory_governance": 5,
    "memory_ignored": 1,
    "memory_override": 1,
    "outdoor_activity": 3,
    "plan_versioning": 1,
    "quick_dinner": 1,
    "quick_meal": 1,
    "rainy_day": 3,
    "replan_turn": 2,
    "robustness_case": 4,
    "route_failure": 5,
    "sensitive_minimization": 1,
    "short_walk": 1,
    "stable_sorting": 1,
    "ticket_sold_out": 3,
}
EXPECTED_TAXONOMY_BY_CASE = {
    "family_afternoon_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L1",
        tags=["baseline", "child_friendly", "light_meal"],
    ),
    "family_indoor_light_meal_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal"],
    ),
    "family_outdoor_quick_dinner_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "outdoor_activity", "quick_dinner"],
    ),
    "family_memory_override_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "indoor_activity", "light_meal", "memory_override"],
    ),
    "family_memory_advisory_fill_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "light_meal", "memory_advisory", "memory_governance"],
    ),
    "family_memory_expired_advisory_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "indoor_activity", "memory_expired", "memory_governance"],
    ),
    "family_memory_disabled_ignored_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "memory_disabled", "memory_governance", "memory_ignored"],
    ),
    "family_memory_candidate_not_auto_active_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "memory_candidate", "memory_governance"],
    ),
    "family_memory_sensitive_minimization_v1": _taxonomy_payload(
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
    "family_citywalk_addon_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L1",
        tags=["addon_optional", "child_friendly", "citywalk"],
    ),
    "solo_afternoon_v1": _taxonomy_payload(
        scenario_bucket="solo",
        level="L1",
        tags=["baseline", "light_activity", "light_meal"],
    ),
    "couple_afternoon_v1": _taxonomy_payload(
        scenario_bucket="couple",
        level="L2",
        tags=["citywalk", "date_friendly", "light_meal"],
    ),
    "friends_gathering_v1": _taxonomy_payload(
        scenario_bucket="friends",
        level="L2",
        tags=["casual_dining", "friends_group", "outdoor_activity"],
    ),
    "rainy_day_fallback_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L2",
        tags=["fallback", "indoor_activity", "rainy_day"],
    ),
    "budget_lite_v1": _taxonomy_payload(
        scenario_bucket="unknown",
        level="L2",
        tags=["budget_limited", "free_activity", "quick_meal"],
    ),
    "elder_afternoon_v1": _taxonomy_payload(
        scenario_bucket="elder",
        level="L2",
        tags=["elder_friendly", "short_walk", "light_meal"],
    ),
    "family_route_failure_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "failure_injected", "light_meal", "route_failure"],
        failure_mode="route_unavailable",
    ),
    "family_route_and_dining_unavailable_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L5",
        tags=[
            "child_friendly",
            "composite_failure",
            "dining_unavailable",
            "failure_injected",
            "route_failure",
        ],
        failure_mode="route_and_dining_unavailable",
    ),
    "friends_route_and_dining_unavailable_v1": _taxonomy_payload(
        scenario_bucket="friends",
        level="L5",
        tags=[
            "composite_failure",
            "dining_unavailable",
            "failure_injected",
            "friends_group",
            "route_failure",
        ],
        failure_mode="route_and_dining_unavailable",
    ),
    "rainy_day_ticket_sold_out_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L5",
        tags=[
            "bad_weather",
            "composite_failure",
            "failure_injected",
            "rainy_day",
            "ticket_sold_out",
        ],
        failure_mode="ticket_sold_out_and_bad_weather",
    ),
    "family_ticket_sold_out_and_route_unavailable_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L5",
        tags=[
            "child_friendly",
            "composite_failure",
            "failure_injected",
            "route_failure",
            "ticket_sold_out",
        ],
        failure_mode="ticket_sold_out_and_route_unavailable",
    ),
    "elder_ticket_sold_out_and_route_unavailable_v1": _taxonomy_payload(
        scenario_bucket="elder",
        level="L5",
        tags=[
            "composite_failure",
            "elder_friendly",
            "failure_injected",
            "route_failure",
            "ticket_sold_out",
        ],
        failure_mode="ticket_sold_out_and_route_unavailable",
    ),
    "budget_queue_closed_constraint_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L5",
        tags=["budget_limited", "composite_failure", "failure_injected"],
        failure_mode="queue_closed_and_budget_constraint",
    ),
    "family_table_unavailable_replan_required_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L5",
        tags=["child_friendly", "composite_failure", "failure_injected", "replan_turn"],
        failure_mode="table_unavailable_and_replan_required",
    ),
    "solo_clarification_continuation_v1": _taxonomy_payload(
        scenario_bucket="solo",
        level="L3",
        tags=["clarification_turn", "conversation_continuation", "light_activity", "light_meal"],
    ),
    "family_replan_version_continuation_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L3",
        tags=["child_friendly", "conversation_continuation", "light_meal", "plan_versioning", "replan_turn"],
    ),
    "family_distractor_selection_v1": _taxonomy_payload(
        scenario_bucket="family",
        level="L2",
        tags=["child_friendly", "light_meal", "robustness_case", "distractor_selection"],
    ),
    "friends_distractor_selection_v1": _taxonomy_payload(
        scenario_bucket="friends",
        level="L2",
        tags=["casual_dining", "friends_group", "outdoor_activity", "robustness_case", "distractor_selection"],
    ),
    "rainy_day_stable_sorting_v1": _taxonomy_payload(
        scenario_bucket="mixed",
        level="L2",
        tags=["rainy_day", "indoor_activity", "robustness_case", "stable_sorting"],
    ),
    "budget_indoor_fallback_v1": _taxonomy_payload(
        scenario_bucket="unknown",
        level="L2",
        tags=["budget_limited", "indoor_activity", "robustness_case", "fallback_selection"],
    ),
}


def test_default_fixtures_load_as_ordered_benchmark_cases() -> None:
    cases = load_default_benchmark_cases()

    assert [case.case_id for case in cases] == list(DEFAULT_CASE_IDS)
    assert len(cases) == 11
    assert all(isinstance(case, BenchmarkCase) for case in cases)


def test_failure_fixtures_are_loadable_but_not_default() -> None:
    default_cases = load_default_benchmark_cases()
    failure_cases = load_failure_benchmark_cases()

    assert [case.case_id for case in failure_cases] == list(FAILURE_CASE_IDS)
    assert {case.case_id for case in default_cases}.isdisjoint(FAILURE_CASE_IDS)

    case = load_benchmark_case("family_route_failure_v1")
    assert case.case_id == "family_route_failure_v1"
    assert case.failure_profile == "route_unavailable_v0"
    assert case.expected.expected_workflow_status == "failed"
    assert case.expected.expected_error_type == "recovery_stopped"
    assert case.expected.expected_recovery_action == "stop_safely"
    assert case.expected.min_injected_failure_count == 1

    composite_case = load_benchmark_case("family_route_and_dining_unavailable_v1")
    assert composite_case.failure_profile == "route_and_dining_unavailable_v0"
    assert composite_case.expected.min_injected_failure_count == 3
    assert composite_case.expected.expected_workflow_status == "failed"
    assert composite_case.expected.expected_execution_status is None
    assert composite_case.expected.expected_feedback_status is None

    rainy_case = load_benchmark_case("rainy_day_ticket_sold_out_v1")
    assert rainy_case.failure_profile == "ticket_sold_out_and_bad_weather_v0"
    assert rainy_case.expected.min_injected_failure_count == 3
    assert rainy_case.expected.expected_recovery_action == "stop_safely"

    family_ticket_case = load_benchmark_case("family_ticket_sold_out_and_route_unavailable_v1")
    assert family_ticket_case.failure_profile == "ticket_sold_out_and_route_unavailable_v0"
    assert family_ticket_case.expected.min_injected_failure_count == 2

    friends_composite_case = load_benchmark_case("friends_route_and_dining_unavailable_v1")
    assert friends_composite_case.failure_profile == "route_and_dining_unavailable_v0"
    assert friends_composite_case.expected.min_injected_failure_count == 3

    elder_ticket_case = load_benchmark_case("elder_ticket_sold_out_and_route_unavailable_v1")
    assert elder_ticket_case.failure_profile == "ticket_sold_out_and_route_unavailable_v0"
    assert elder_ticket_case.expected.min_injected_failure_count == 2

    budget_queue_case = load_benchmark_case("budget_queue_closed_constraint_v1")
    assert budget_queue_case.failure_profile == "queue_closed_and_budget_constraint_v0"
    assert budget_queue_case.expected.min_injected_failure_count == 1

    table_replan_case = load_benchmark_case("family_table_unavailable_replan_required_v1")
    assert table_replan_case.failure_profile == "table_unavailable_and_replan_required_v0"
    assert table_replan_case.expected.min_injected_failure_count == 1


def test_memory_governance_fixtures_are_loadable_but_not_default() -> None:
    default_cases = load_default_benchmark_cases()
    default_case_ids = {case.case_id for case in default_cases}

    advisory_case = load_benchmark_case("family_memory_advisory_fill_v1")
    expired_case = load_benchmark_case("family_memory_expired_advisory_v1")

    assert advisory_case.case_id == "family_memory_advisory_fill_v1"
    assert advisory_case.case_id not in default_case_ids
    assert advisory_case.expected.memory_governance is not None
    assert advisory_case.expected.memory_governance.expected_policy_version == "memory_query_policy_v1"
    assert advisory_case.expected.memory_governance.expected_dimension_sources == {
        "dining_preferences": "memory",
    }
    assert advisory_case.expected.memory_governance.expected_dimension_tiers == {
        "dining_preferences": "advisory",
    }

    assert expired_case.case_id == "family_memory_expired_advisory_v1"
    assert expired_case.case_id not in default_case_ids
    assert expired_case.memory_items[0].status == "expired"
    assert expired_case.memory_items[0].expires_at is not None
    assert expired_case.expected.memory_governance is not None
    assert expired_case.expected.memory_governance.expected_dimension_sources == {
        "activity_preferences": "memory",
    }
    assert expired_case.expected.memory_governance.expected_dimension_tiers == {
        "activity_preferences": "advisory",
    }

    disabled_case = load_benchmark_case("family_memory_disabled_ignored_v1")
    candidate_case = load_benchmark_case("family_memory_candidate_not_auto_active_v1")
    sensitive_case = load_benchmark_case("family_memory_sensitive_minimization_v1")

    assert disabled_case.case_id not in default_case_ids
    assert [item.status for item in disabled_case.memory_items] == ["disabled", "ignored"]
    assert disabled_case.expected.memory_governance is not None
    assert disabled_case.expected.memory_governance.expected_absent_memory_keys == [
        "spouse_lighter_meals",
        "activity_style",
    ]

    assert candidate_case.case_id not in default_case_ids
    assert candidate_case.memory_items[0].status == "candidate"
    assert candidate_case.expected.memory_governance is not None
    assert candidate_case.expected.memory_governance.expected_absent_memory_keys == ["activity_style"]

    assert sensitive_case.case_id not in default_case_ids
    assert sensitive_case.expected.memory_governance is not None
    assert sensitive_case.expected.memory_governance.expected_feedback_memory_candidate_summary is not None


def test_continuation_fixtures_are_loadable_but_not_default() -> None:
    default_case_ids = {case.case_id for case in load_default_benchmark_cases()}
    clarification_case = load_benchmark_case("solo_clarification_continuation_v1")
    replan_case = load_benchmark_case("family_replan_version_continuation_v1")

    assert clarification_case.case_id not in default_case_ids
    assert clarification_case.continuations == [
        BenchmarkContinuationRequest(
            mode="clarify",
            user_input="This afternoon I want a nearby solo outing for a few hours.",
            selected_plan_index=0,
        )
    ]
    assert clarification_case.expected.conversation is not None
    assert [step.mode for step in clarification_case.expected.conversation.steps] == [
        "start",
        "clarify",
        "confirm",
    ]
    assert clarification_case.expected.conversation.required_turn_types == [
        "user_request",
        "assistant_clarification_request",
        "user_clarification_reply",
        "assistant_plan_options",
    ]

    assert replan_case.case_id not in default_case_ids
    assert replan_case.continuations == [
        BenchmarkContinuationRequest(
            mode="replan",
            user_input="Keep it nearby, but make it indoor this time.",
            selected_plan_index=0,
        )
    ]
    assert replan_case.expected.conversation is not None
    assert [step.mode for step in replan_case.expected.conversation.steps] == [
        "start",
        "replan",
        "confirm",
    ]
    assert replan_case.expected.conversation.required_turn_types == [
        "user_request",
        "assistant_plan_options",
        "user_follow_up",
        "assistant_replan_options",
    ]


def test_robustness_fixtures_are_loadable_but_not_default_or_release_gate() -> None:
    default_case_ids = {case.case_id for case in load_default_benchmark_cases()}
    release_gate_case_ids = {case.case_id for case in load_benchmark_suite("release_gate_v1")}

    for case_id, expected in ROBUSTNESS_EXPECTATIONS_BY_CASE.items():
        case = load_benchmark_case(case_id)

        assert case.case_id not in default_case_ids
        assert case.case_id not in release_gate_case_ids
        assert case.world_profile == expected["world_profile"]
        assert case.expected.robustness is not None
        assert case.expected.robustness.expected_selected_activity_id == expected["selected_activity_id"]
        assert case.expected.robustness.expected_selected_dining_id == expected["selected_dining_id"]
        assert case.expected.robustness.minimum_activity_search_results == expected["minimum_activity_search_results"]
        assert case.expected.robustness.minimum_dining_search_results == expected["minimum_dining_search_results"]
        assert case.expected.robustness.expected_activity_search_prefix == expected["expected_activity_search_prefix"]
        assert case.expected.robustness.expected_dining_search_prefix == expected["expected_dining_search_prefix"]
        assert case.expected.robustness.required_unavailable_candidate_ids == (
            expected["required_unavailable_candidate_ids"]
        )
        assert case.expected.robustness.minimum_failed_route_pairs == expected["minimum_failed_route_pairs"]


def test_default_fixtures_can_be_loaded_individually() -> None:
    for case_id in DEFAULT_CASE_IDS:
        case = load_benchmark_case(case_id)

        assert isinstance(case, BenchmarkCase)
        assert case.case_id == case_id


def test_default_and_failure_fixtures_expose_expected_taxonomy() -> None:
    case_ids = [
        *DEFAULT_CASE_IDS,
        *FAILURE_CASE_IDS,
        *MEMORY_GOVERNANCE_CASE_IDS[1:],
        *CONTINUATION_CASE_IDS,
        *ROBUSTNESS_CASE_IDS,
    ]

    for case_id in case_ids:
        case = load_benchmark_case(case_id)

        assert case.taxonomy.model_dump(mode="json") == EXPECTED_TAXONOMY_BY_CASE[case_id]


def test_default_fixtures_use_supported_mock_world_profiles() -> None:
    cases = load_default_benchmark_cases()

    assert {case.tool_profile for case in cases} == {"mock_world"}
    assert {case.world_profile for case in cases} == {
        "budget_lite",
        "couple_afternoon",
        "elder_afternoon",
        "family_afternoon",
        "friends_gathering",
        "rainy_day_fallback",
        "solo_afternoon",
    }


def test_default_case_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_default_benchmark_cases())

    assert summary.case_count == 11
    assert summary.scenario_bucket_counts == DEFAULT_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == DEFAULT_LEVEL_COUNTS
    assert summary.tool_profile_counts == DEFAULT_TOOL_PROFILE_COUNTS
    assert summary.world_profile_counts == DEFAULT_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == DEFAULT_FAILURE_MODE_COUNTS
    assert summary.tag_counts == DEFAULT_TAG_COUNTS


def test_memory_governance_suite_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("memory_governance"))

    assert summary.case_count == 6
    assert summary.scenario_bucket_counts == MEMORY_GOVERNANCE_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == MEMORY_GOVERNANCE_LEVEL_COUNTS
    assert summary.tool_profile_counts == MEMORY_GOVERNANCE_TOOL_PROFILE_COUNTS
    assert summary.world_profile_counts == MEMORY_GOVERNANCE_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == MEMORY_GOVERNANCE_FAILURE_MODE_COUNTS
    assert summary.tag_counts == MEMORY_GOVERNANCE_TAG_COUNTS


def test_robustness_focused_suite_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("robustness_focused"))

    assert summary.case_count == 4
    assert summary.scenario_bucket_counts == ROBUSTNESS_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == ROBUSTNESS_LEVEL_COUNTS
    assert summary.tool_profile_counts == ROBUSTNESS_TOOL_PROFILE_COUNTS
    assert summary.world_profile_counts == ROBUSTNESS_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == ROBUSTNESS_FAILURE_MODE_COUNTS
    assert summary.tag_counts == ROBUSTNESS_TAG_COUNTS


def test_all_registered_case_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("all_registered"))

    assert summary.case_count == 30
    assert summary.scenario_bucket_counts == ALL_REGISTERED_SCENARIO_BUCKET_COUNTS
    assert summary.level_counts == ALL_REGISTERED_LEVEL_COUNTS
    assert summary.tool_profile_counts == ALL_REGISTERED_TOOL_PROFILE_COUNTS
    assert summary.world_profile_counts == ALL_REGISTERED_WORLD_PROFILE_COUNTS
    assert summary.failure_mode_counts == ALL_REGISTERED_FAILURE_MODE_COUNTS
    assert summary.tag_counts == ALL_REGISTERED_TAG_COUNTS


def test_release_gate_v1_case_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("release_gate_v1"))

    assert summary.case_count == 15
    assert summary.scenario_bucket_counts == {
        "couple": 1,
        "family": 9,
        "friends": 1,
        "mixed": 1,
        "solo": 2,
        "unknown": 1,
    }
    assert summary.level_counts == {"L1": 3, "L2": 8, "L3": 4}
    assert summary.tool_profile_counts == {"mock_world": 15}
    assert summary.world_profile_counts == {
        "budget_lite": 1,
        "couple_afternoon": 1,
        "family_afternoon": 9,
        "friends_gathering": 1,
        "rainy_day_fallback": 1,
        "solo_afternoon": 2,
    }
    assert summary.failure_mode_counts == {"none": 14, "route_unavailable": 1}
    assert summary.tag_counts == {
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


def test_conversation_continuation_suite_matrix_summary_counts_are_expected() -> None:
    summary = build_case_matrix_summary(load_benchmark_suite("conversation_continuations"))

    assert summary.case_count == 2
    assert summary.scenario_bucket_counts == {"family": 1, "solo": 1}
    assert summary.level_counts == {"L3": 2}
    assert summary.tool_profile_counts == {"mock_world": 2}
    assert summary.world_profile_counts == {"family_afternoon": 1, "solo_afternoon": 1}
    assert summary.failure_mode_counts == {"none": 2}
    assert summary.tag_counts == {
        "child_friendly": 1,
        "clarification_turn": 1,
        "conversation_continuation": 2,
        "light_activity": 1,
        "light_meal": 2,
        "plan_versioning": 1,
        "replan_turn": 1,
    }


def test_default_fixtures_include_v1_metadata_and_expected_tools() -> None:
    cases = load_default_benchmark_cases()

    for case in cases:
        assert case.taxonomy.suite == "locallife_bench_v1"
        assert case.taxonomy.level in {"L1", "L2"}
        assert "suite" not in case.metadata
        assert "level" not in case.metadata
        assert isinstance(case.metadata["focus"], str)
        assert case.metadata["focus"]
        assert set(case.expected.required_tool_names) == REQUIRED_CASE_TOOL_NAMES
        assert case.expected.expected_execution_status == "succeeded"
        assert case.expected.expected_feedback_status == "completed"


def test_build_failure_chain_summary_deduplicates_effects_and_marks_bounded() -> None:
    summary = build_failure_chain_summary(
        failure_profile="route_and_dining_unavailable_v0",
        tool_events=[
            SimpleNamespace(
                tool_name="check_queue",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_queue",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_table_availability",
                status="succeeded",
                error_json={
                    "error_type": "failure_injected_response",
                    "details": {"effect_type": "dining_unavailable"},
                },
            ),
            SimpleNamespace(
                tool_name="check_route",
                status="failed",
                error_json={
                    "error_type": "failure_injected",
                    "details": {"effect_type": "route_infeasible"},
                },
            ),
        ],
        run_metadata={
            "workflow": {
                "recovery": {
                    "attempt_count": 1,
                    "max_attempts": 2,
                    "attempts": [
                        {"recovery_action": "stop_safely", "status": "stopped"},
                    ],
                }
            }
        },
        workflow_status="failed",
    )

    assert summary.profile_id == "route_and_dining_unavailable_v0"
    assert summary.injected_effects == [
        "check_queue:dining_unavailable:succeeded",
        "check_table_availability:dining_unavailable:succeeded",
        "check_route:route_infeasible:failed",
    ]
    assert summary.recovery_actions == ["stop_safely"]
    assert summary.attempt_count == 1
    assert summary.max_attempts == 2
    assert summary.bounded is True
    assert summary.terminal_workflow_status == "failed"


@pytest.mark.parametrize(
    ("case_id", "world_profile", "scenario_bucket", "tags", "focus"),
    [
        (
            "solo_afternoon_v1",
            "solo_afternoon",
            "solo",
            ["baseline", "light_activity", "light_meal"],
            "baseline_solo_afternoon",
        ),
        (
            "couple_afternoon_v1",
            "couple_afternoon",
            "couple",
            ["citywalk", "date_friendly", "light_meal"],
            "baseline_couple_citywalk",
        ),
        (
            "friends_gathering_v1",
            "friends_gathering",
            "friends",
            ["casual_dining", "friends_group", "outdoor_activity"],
            "friends_group_hangout",
        ),
        (
            "rainy_day_fallback_v1",
            "rainy_day_fallback",
            "mixed",
            ["fallback", "indoor_activity", "rainy_day"],
            "rainy_day_indoor_fallback",
        ),
        (
            "budget_lite_v1",
            "budget_lite",
            "unknown",
            ["budget_limited", "free_activity", "quick_meal"],
            "budget_lite_low_cost_route",
        ),
        (
            "elder_afternoon_v1",
            "elder_afternoon",
            "elder",
            ["elder_friendly", "short_walk", "light_meal"],
            "elder_gentle_afternoon",
        ),
        (
            "family_memory_advisory_fill_v1",
            "family_afternoon",
            "family",
            ["child_friendly", "light_meal", "memory_advisory", "memory_governance"],
            "memory_advisory_fill",
        ),
        (
            "family_memory_expired_advisory_v1",
            "family_afternoon",
            "family",
            ["child_friendly", "indoor_activity", "memory_expired", "memory_governance"],
            "memory_expired_advisory",
        ),
        (
            "solo_clarification_continuation_v1",
            "solo_afternoon",
            "solo",
            ["clarification_turn", "conversation_continuation", "light_activity", "light_meal"],
            "clarification_continuation_solo",
        ),
        (
            "family_replan_version_continuation_v1",
            "family_afternoon",
            "family",
            ["child_friendly", "conversation_continuation", "light_meal", "plan_versioning", "replan_turn"],
            "replan_version_continuation_family",
        ),
    ],
)
def test_fixture_uses_expected_profile_taxonomy_and_focus(
    case_id: str,
    world_profile: str,
    scenario_bucket: str,
    tags: list[str],
    focus: str,
) -> None:
    case = load_benchmark_case(case_id)

    assert case.tool_profile == "mock_world"
    assert case.world_profile == world_profile
    assert case.taxonomy.scenario_bucket == scenario_bucket
    assert case.taxonomy.tags == tags
    assert case.metadata["focus"] == focus


def test_unknown_case_raises_benchmark_harness_error() -> None:
    with pytest.raises(BenchmarkHarnessError):
        load_benchmark_case("missing_case")


def test_benchmark_case_rejects_duplicate_and_malformed_taxonomy_tags() -> None:
    payload = {
        "case_id": "case",
        "title": "Case",
        "user_input": "Plan an afternoon.",
        "expected": {
            "required_tool_names": ["search_poi"],
            "min_tool_event_count": 1,
            "min_action_count": 1,
        },
        "taxonomy": _taxonomy_payload(
            scenario_bucket="unknown",
            level="L1",
            tags=["baseline", "baseline"],
        ),
    }
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(payload)

    payload["taxonomy"] = _taxonomy_payload(
        scenario_bucket="unknown",
        level="L1",
        tags=["bad-tag"],
    )
    with pytest.raises(ValidationError):
        BenchmarkCase.model_validate(payload)


def test_benchmark_case_supports_additive_continuation_contracts() -> None:
    payload = {
        "case_id": "continuation_case",
        "title": "Continuation case",
        "user_input": "Plan something nearby.",
        "continuations": [
            {
                "mode": "clarify",
                "user_input": "This afternoon I want a nearby solo outing for a few hours.",
                "selected_plan_index": 0,
            }
        ],
        "expected": {
            "required_tool_names": ["search_poi"],
            "min_tool_event_count": 1,
            "min_action_count": 1,
            "conversation": {
                "steps": [
                    {"mode": "start", "expected_status": "awaiting_clarification", "expected_version_label": "v1"},
                    {"mode": "clarify", "expected_status": "awaiting_confirmation", "expected_version_label": "v1"},
                    {"mode": "confirm", "expected_status": "completed", "expected_version_label": "v1"},
                ],
                "required_turn_types": [
                    "user_request",
                    "assistant_clarification_request",
                    "user_clarification_reply",
                    "assistant_plan_options",
                ],
            },
        },
        "taxonomy": _taxonomy_payload(
            scenario_bucket="solo",
            level="L3",
            tags=["clarification_turn", "conversation_continuation"],
        ),
    }

    case = BenchmarkCase.model_validate(payload)

    assert case.continuations == [
        BenchmarkContinuationRequest(
            mode="clarify",
            user_input="This afternoon I want a nearby solo outing for a few hours.",
            selected_plan_index=0,
        )
    ]
    assert case.expected.conversation == BenchmarkConversationExpectation(
        steps=[
            BenchmarkConversationExpectedStep(
                mode="start",
                expected_status="awaiting_clarification",
                expected_version_label="v1",
            ),
            BenchmarkConversationExpectedStep(
                mode="clarify",
                expected_status="awaiting_confirmation",
                expected_version_label="v1",
            ),
            BenchmarkConversationExpectedStep(
                mode="confirm",
                expected_status="completed",
                expected_version_label="v1",
            ),
        ],
        required_turn_types=[
            "user_request",
            "assistant_clarification_request",
            "user_clarification_reply",
            "assistant_plan_options",
        ],
    )


def test_benchmark_case_result_exposes_conversation_trace_and_turn_types() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "solo_clarification_continuation_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "conversation_trace": [
                {
                    "mode": "start",
                    "source_run_id": None,
                    "run_id": str(uuid4()),
                    "status": "awaiting_clarification",
                    "version_label": "v1",
                }
            ],
            "conversation_turn_types": [
                "user_request",
                "assistant_clarification_request",
            ],
        }
    )

    assert result.conversation_trace == [
        BenchmarkConversationTraceStep(
            mode="start",
            source_run_id=None,
            run_id=result.conversation_trace[0].run_id,
            status="awaiting_clarification",
            version_label="v1",
        )
    ]
    assert result.conversation_turn_types == [
        "user_request",
        "assistant_clarification_request",
    ]


def test_benchmark_case_result_exposes_additive_memory_policy_summary() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "family_memory_advisory_fill_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "memory_policy_summary": {
                "policy_version": "memory_query_policy_v1",
                "considered_count": 1,
                "used_count": 0,
                "ignored_count": 0,
                "downgraded_count": 1,
                "overridden_count": 0,
                "primary_influence_count": 0,
                "advisory_influence_count": 1,
                "no_influence_count": 0,
            },
        }
    )

    assert result.memory_policy_summary is not None
    assert result.memory_policy_summary.policy_version == "memory_query_policy_v1"
    assert result.memory_policy_summary.downgraded_count == 1
    assert result.memory_policy_summary.advisory_influence_count == 1


def test_trajectory_grader_passes_when_required_tools_are_present() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi", "check_route"],
            min_tool_event_count=2,
            min_action_count=1,
        ),
    )
    tool_events = [
        type("ToolEventStub", (), {"tool_name": "search_poi"})(),
        type("ToolEventStub", (), {"tool_name": "check_route"})(),
    ]

    score = grade_trajectory(case, tool_events)

    assert score.passed is True
    assert score.score == 1.0


def test_trajectory_grader_fails_when_required_tool_is_missing() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi", "check_route"],
            min_tool_event_count=2,
            min_action_count=1,
        ),
    )
    tool_events = [type("ToolEventStub", (), {"tool_name": "search_poi"})()]

    score = grade_trajectory(case, tool_events)

    assert score.passed is False
    assert score.score == 0.0
    assert "check_route" in score.reason


def test_robustness_grader_passes_when_selected_pair_and_evidence_match() -> None:
    case = BenchmarkCase(
        case_id="budget_indoor_fallback_v1",
        title="Budget fallback",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(
            scenario_bucket="unknown",
            level="L2",
            tags=["budget_limited", "indoor_activity", "robustness_case", "fallback_selection"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            robustness=BenchmarkRobustnessExpectation(
                expected_selected_activity_id="activity_gallery_501",
                expected_selected_dining_id="restaurant_bento_501",
                minimum_activity_search_results=3,
                minimum_dining_search_results=4,
                expected_activity_search_prefix=[
                    "activity_workshop_501",
                    "activity_designmall_501",
                    "activity_gallery_501",
                ],
                expected_dining_search_prefix=[
                    "restaurant_bento_501",
                    "restaurant_cafe_501",
                    "restaurant_bistro_501",
                ],
                required_unavailable_candidate_ids=[
                    "activity_workshop_501",
                    "restaurant_cafe_501",
                ],
                minimum_failed_route_pairs=1,
            ),
        ),
    )
    selected_plan = SimpleNamespace(
        plan_json={
            "draft": {
                "activity": {"candidate_id": "activity_gallery_501"},
                "dining": {"candidate_id": "restaurant_bento_501"},
            }
        }
    )
    tool_events = [
        SimpleNamespace(
            tool_name="search_poi",
            request_json={"payload": {"category": "activity"}},
            response_json={
                "results": [
                    {"poi_id": "activity_workshop_501"},
                    {"poi_id": "activity_designmall_501"},
                    {"poi_id": "activity_gallery_501"},
                ]
            },
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="search_poi",
            request_json={"payload": {"category": "dining"}},
            response_json={
                "results": [
                    {"poi_id": "restaurant_bento_501"},
                    {"poi_id": "restaurant_cafe_501"},
                    {"poi_id": "restaurant_bistro_501"},
                    {"poi_id": "restaurant_noodle_501"},
                ]
            },
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_ticket_availability",
            request_json={"payload": {"poi_id": "activity_workshop_501"}},
            response_json={"ticket_availability": {"available": False}},
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_table_availability",
            request_json={"payload": {"restaurant_id": "restaurant_cafe_501"}},
            response_json={"table_availability": {"available": False}},
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_route",
            request_json={"payload": {"origin_id": "activity_workshop_501", "destination_id": "restaurant_bento_501"}},
            response_json=None,
            status="failed",
        ),
        SimpleNamespace(
            tool_name="check_route",
            request_json={"payload": {"origin_id": "activity_gallery_501", "destination_id": "restaurant_bento_501"}},
            response_json={"route": {"duration_minutes": 12}},
            status="succeeded",
        ),
    ]

    score = grade_robustness_expectation(case, selected_plan, tool_events)

    assert score.name == "robustness"
    assert score.passed is True
    assert score.details["selected_activity_id"] == "activity_gallery_501"
    assert score.details["selected_dining_id"] == "restaurant_bento_501"
    assert score.details["observed_activity_search_results"] == [
        "activity_workshop_501",
        "activity_designmall_501",
        "activity_gallery_501",
    ]
    assert score.details["observed_dining_search_results"] == [
        "restaurant_bento_501",
        "restaurant_cafe_501",
        "restaurant_bistro_501",
        "restaurant_noodle_501",
    ]
    assert score.details["observed_unavailable_candidate_ids"] == [
        "activity_workshop_501",
        "restaurant_cafe_501",
    ]
    assert score.details["failed_route_pair_count"] == 1


def test_robustness_grader_fails_when_selected_pair_does_not_match() -> None:
    case = BenchmarkCase(
        case_id="budget_indoor_fallback_v1",
        title="Budget fallback",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(
            scenario_bucket="unknown",
            level="L2",
            tags=["budget_limited", "indoor_activity", "robustness_case", "fallback_selection"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            robustness=BenchmarkRobustnessExpectation(
                expected_selected_activity_id="activity_gallery_501",
                expected_selected_dining_id="restaurant_bento_501",
                minimum_activity_search_results=3,
                minimum_dining_search_results=4,
                expected_activity_search_prefix=[
                    "activity_workshop_501",
                    "activity_designmall_501",
                    "activity_gallery_501",
                ],
                expected_dining_search_prefix=[
                    "restaurant_bento_501",
                    "restaurant_cafe_501",
                    "restaurant_bistro_501",
                ],
                required_unavailable_candidate_ids=[
                    "activity_workshop_501",
                    "restaurant_cafe_501",
                ],
                minimum_failed_route_pairs=1,
            ),
        ),
    )
    selected_plan = SimpleNamespace(
        plan_json={
            "draft": {
                "activity": {"candidate_id": "activity_gallery_501"},
                "dining": {"candidate_id": "restaurant_cafe_501"},
            }
        }
    )
    tool_events = [
        SimpleNamespace(
            tool_name="search_poi",
            request_json={"payload": {"category": "activity"}},
            response_json={"results": [{"poi_id": "activity_workshop_501"}, {"poi_id": "activity_gallery_501"}]},
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="search_poi",
            request_json={"payload": {"category": "dining"}},
            response_json={
                "results": [
                    {"poi_id": "restaurant_bento_501"},
                    {"poi_id": "restaurant_cafe_501"},
                    {"poi_id": "restaurant_bistro_501"},
                    {"poi_id": "restaurant_noodle_501"},
                ]
            },
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_ticket_availability",
            request_json={"payload": {"poi_id": "activity_workshop_501"}},
            response_json={"ticket_availability": {"available": False}},
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_table_availability",
            request_json={"payload": {"restaurant_id": "restaurant_cafe_501"}},
            response_json={"table_availability": {"available": False}},
            status="succeeded",
        ),
        SimpleNamespace(
            tool_name="check_route",
            request_json={"payload": {"origin_id": "activity_workshop_501", "destination_id": "restaurant_bento_501"}},
            response_json=None,
            status="failed",
        ),
    ]

    score = grade_robustness_expectation(case, selected_plan, tool_events)

    assert score.name == "robustness"
    assert score.passed is False
    assert score.score == 0.0
    assert score.details["selected_dining_id"] == "restaurant_cafe_501"
    assert "selected dining" in score.reason


def test_combine_scores_returns_failed_status_when_one_score_fails() -> None:
    status, overall, reasons = combine_scores(
        [
            BenchmarkScore(name="one", score=1.0, passed=True, reason="ok"),
            BenchmarkScore(name="two", score=0.0, passed=False, reason="missing"),
        ]
    )

    assert status == "failed"
    assert overall == 0.5
    assert reasons == ["missing"]


def test_workflow_path_grader_passes_for_completed_required_nodes() -> None:
    grader = getattr(benchmark_graders, "grade_workflow_path", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(status="completed", node_history=list(REQUIRED_WORKFLOW_NODES))

    score = grader(workflow_result)

    assert score.name == "workflow_path"
    assert score.passed is True
    assert score.score == 1.0


def test_workflow_path_grader_passes_for_expected_safe_stop_failure() -> None:
    case = BenchmarkCase(
        case_id="family_route_failure_v1",
        title="Route failure",
        user_input="Plan an afternoon.",
        failure_profile="route_unavailable_v0",
        taxonomy=_taxonomy_payload(failure_mode="route_unavailable"),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_workflow_status="failed",
            expected_execution_status=None,
            expected_feedback_status=None,
            expected_error_type="recovery_stopped",
        ),
    )
    workflow_result = SimpleNamespace(
        status="failed",
        error_json={"error_type": "recovery_stopped"},
        node_history=["initialize", "apply_recovery"],
    )

    score = grade_workflow_path(workflow_result, case)

    assert score.name == "workflow_path"
    assert score.passed is True
    assert score.score == 1.0
    assert score.details["expected_workflow_status"] == "failed"


def test_workflow_path_grader_fails_when_required_node_missing() -> None:
    grader = getattr(benchmark_graders, "grade_workflow_path", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(status="completed", node_history=["initialize"])

    score = grader(workflow_result)

    assert score.name == "workflow_path"
    assert score.passed is False
    assert "generate_summary_message" in score.reason


def test_agent_coverage_grader_passes_for_all_required_roles() -> None:
    grader = getattr(benchmark_graders, "grade_agent_coverage", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(
        agent_results=[SimpleNamespace(role=role) for role in REQUIRED_AGENT_ROLES]
    )

    score = grader(workflow_result)

    assert score.name == "agent_coverage"
    assert score.passed is True
    assert score.score == 1.0


def test_agent_coverage_grader_fails_when_role_missing() -> None:
    grader = getattr(benchmark_graders, "grade_agent_coverage", None)
    assert callable(grader)
    workflow_result = SimpleNamespace(agent_results=[SimpleNamespace(role="supervisor")])

    score = grader(workflow_result)

    assert score.name == "agent_coverage"
    assert score.passed is False
    assert "validator_recovery" in score.reason


def test_execution_safety_grader_accepts_persisted_execution_metadata_dict() -> None:
    case = _benchmark_case()
    execution = {
        "status": "succeeded",
        "action_results": [
            {"tool_name": "reserve_restaurant"},
            {"tool_name": "book_ticket"},
        ],
    }

    score = grade_execution_safety(case, execution)

    assert score.passed is True
    assert score.details["execution_status"] == "succeeded"
    assert score.details["write_tools"] == ["reserve_restaurant", "book_ticket"]


def test_execution_safety_grader_accepts_absent_execution_when_expected_is_none() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_execution_status=None,
        ),
    )

    score = grade_execution_safety(case, None)

    assert score.passed is True
    assert score.details["execution_status"] is None


def test_feedback_grader_accepts_persisted_feedback_metadata_dict() -> None:
    case = _benchmark_case()
    feedback = {
        "status": "completed",
        "headline": "安排已完成",
        "message": "安排已完成：2项操作已完成，0项需要处理。",
        "next_steps": ["按确认后的时间出发，出门前再看一眼天气和路况。"],
    }

    score = grade_feedback(case, feedback)

    assert score.passed is True
    assert score.details["feedback_status"] == "completed"


def test_feedback_grader_accepts_absent_feedback_when_expected_is_none() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_feedback_status=None,
        ),
    )

    score = grade_feedback(case, None)

    assert score.passed is True
    assert score.details["feedback_status"] is None


def test_failure_injection_grader_requires_injected_failures() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            min_injected_failure_count=1,
        ),
    )
    tool_events = [
        SimpleNamespace(
            tool_name="check_route",
            status="failed",
            error_json={
                "error_type": "failure_injected",
                "details": {"profile_id": "route_unavailable_v0"},
            },
        )
    ]

    score = grade_failure_injection(case, tool_events)

    assert score.passed is True
    assert score.details["injected_failure_count"] == 1


def test_recovery_expectation_grader_accepts_expected_recovery_action() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_recovery_action="stop_safely",
        ),
    )
    run_metadata = {
        "workflow": {
            "recovery": {
                "attempts": [
                    {
                        "recovery_action": "stop_safely",
                        "status": "stopped",
                    }
                ]
            }
        }
    }

    score = grade_recovery_expectation(case, run_metadata)

    assert score.passed is True
    assert score.details["observed_recovery_actions"] == ["stop_safely"]


def test_memory_governance_grader_passes_for_expected_policy_summary() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(
            scenario_bucket="family",
            level="L3",
            tags=["child_friendly", "memory_governance"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            memory_governance=BenchmarkMemoryGovernanceExpectation(
                expected_policy_version="memory_query_policy_v1",
                expected_dimension_sources={"dining_preferences": "memory"},
                expected_dimension_tiers={"dining_preferences": "advisory"},
                expected_memory_outcomes=[
                    BenchmarkMemoryDecisionExpectation(
                        memory_key="spouse_lighter_meals",
                        expected_outcome="applied_advisory",
                    )
                ],
                expected_decision_log=[
                    {
                        "memory_key": "spouse_lighter_meals",
                        "expected_decision": "applied_advisory",
                        "expected_status": "downgraded",
                        "expected_reason": "low_confidence_downgraded_to_advisory",
                        "expected_influence_level": "advisory",
                    }
                ],
                expected_policy_summary={
                    "considered_count": 1,
                    "used_count": 0,
                    "ignored_count": 0,
                    "downgraded_count": 1,
                    "overridden_count": 0,
                    "primary_influence_count": 0,
                    "advisory_influence_count": 1,
                    "no_influence_count": 0,
                },
            ),
        ),
    )
    run_metadata = {
        "workflow": {
            "memory_policy": {
                "policy_version": "memory_query_policy_v1",
                "dimension_outcomes": [
                    {
                        "dimension": "dining_preferences",
                        "winner_source": "memory",
                        "winner_memory_key": "spouse_lighter_meals",
                        "winner_tier": "advisory",
                        "effective_values": ["lighter_options"],
                        "suppressed_memory_keys": [],
                    }
                ],
                "memory_decisions": [
                    {
                        "memory_key": "spouse_lighter_meals",
                        "dimension": "dining_preferences",
                        "normalized_value": "lighter_options",
                        "confidence": "0.7000",
                        "tier": "advisory",
                        "expired": False,
                        "outcome": "applied_advisory",
                    }
                ],
                "decision_log": [
                    {
                        "memory_id": "00000000-0000-0000-0000-000000000001",
                        "key": "spouse_lighter_meals",
                        "status": "downgraded",
                        "decision": "applied_advisory",
                        "reason": "low_confidence_downgraded_to_advisory",
                        "influence_level": "advisory",
                        "dimension": "dining_preferences",
                        "normalized_value": "lighter_options",
                        "tier": "advisory",
                        "expired": False,
                    }
                ],
                "policy_summary": {
                    "policy_version": "memory_query_policy_v1",
                    "considered_count": 1,
                    "used_count": 0,
                    "ignored_count": 0,
                    "downgraded_count": 1,
                    "overridden_count": 0,
                    "primary_influence_count": 0,
                    "advisory_influence_count": 1,
                    "no_influence_count": 0,
                },
            }
        }
    }

    score = grade_memory_governance(case, run_metadata)

    assert score.name == "memory_governance"
    assert score.passed is True
    assert score.score == 1.0
    assert score.details["expected_policy_version"] == "memory_query_policy_v1"
    assert score.details["observed_dimension_sources"] == {"dining_preferences": "memory"}
    assert score.details["observed_dimension_tiers"] == {"dining_preferences": "advisory"}
    assert score.details["observed_memory_outcomes"] == {"spouse_lighter_meals": "applied_advisory"}
    assert score.details["observed_decision_log"]["spouse_lighter_meals"]["status"] == "downgraded"
    assert score.details["observed_policy_summary"]["downgraded_count"] == 1


def test_conversation_path_grader_passes_for_exact_status_version_and_turn_types() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan something nearby.",
        continuations=[
            BenchmarkContinuationRequest(
                mode="clarify",
                user_input="This afternoon I want a nearby solo outing for a few hours.",
            )
        ],
        taxonomy=_taxonomy_payload(
            scenario_bucket="solo",
            level="L3",
            tags=["clarification_turn", "conversation_continuation"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            conversation=BenchmarkConversationExpectation(
                steps=[
                    BenchmarkConversationExpectedStep(
                        mode="start",
                        expected_status="awaiting_clarification",
                        expected_version_label="v1",
                    ),
                    BenchmarkConversationExpectedStep(
                        mode="clarify",
                        expected_status="awaiting_confirmation",
                        expected_version_label="v1",
                    ),
                    BenchmarkConversationExpectedStep(
                        mode="confirm",
                        expected_status="completed",
                        expected_version_label="v1",
                    ),
                ],
                required_turn_types=[
                    "user_request",
                    "assistant_clarification_request",
                    "user_clarification_reply",
                    "assistant_plan_options",
                ],
            ),
        ),
    )

    score = grade_conversation_path(
        case,
        [
            BenchmarkConversationTraceStep(
                mode="start",
                source_run_id=None,
                run_id=uuid4(),
                status="awaiting_clarification",
                version_label="v1",
            ),
            BenchmarkConversationTraceStep(
                mode="clarify",
                source_run_id=uuid4(),
                run_id=uuid4(),
                status="awaiting_confirmation",
                version_label="v1",
            ),
            BenchmarkConversationTraceStep(
                mode="confirm",
                source_run_id=uuid4(),
                run_id=uuid4(),
                status="completed",
                version_label="v1",
            ),
        ],
        [
            "user_request",
            "assistant_clarification_request",
            "user_clarification_reply",
            "assistant_plan_options",
        ],
    )

    assert score.name == "conversation_path"
    assert score.passed is True
    assert score.score == 1.0


def test_conversation_path_grader_fails_for_step_count_mismatch() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan something nearby.",
        taxonomy=_taxonomy_payload(
            scenario_bucket="solo",
            level="L3",
            tags=["clarification_turn", "conversation_continuation"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            conversation=BenchmarkConversationExpectation(
                steps=[
                    BenchmarkConversationExpectedStep(mode="start", expected_status="awaiting_clarification"),
                    BenchmarkConversationExpectedStep(mode="clarify", expected_status="awaiting_confirmation"),
                ],
                required_turn_types=[],
            ),
        ),
    )

    score = grade_conversation_path(
        case,
        [
            BenchmarkConversationTraceStep(
                mode="start",
                source_run_id=None,
                run_id=uuid4(),
                status="awaiting_clarification",
            )
        ],
        [],
    )

    assert score.passed is False
    assert "step count" in score.reason


def test_conversation_path_grader_fails_when_required_turn_type_is_missing() -> None:
    case = BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan something nearby.",
        taxonomy=_taxonomy_payload(
            scenario_bucket="family",
            level="L3",
            tags=["conversation_continuation", "replan_turn"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
            conversation=BenchmarkConversationExpectation(
                steps=[
                    BenchmarkConversationExpectedStep(mode="start", expected_status="awaiting_confirmation"),
                    BenchmarkConversationExpectedStep(
                        mode="replan",
                        expected_status="awaiting_confirmation",
                        expected_version_label="v2",
                    ),
                ],
                required_turn_types=["user_follow_up", "assistant_replan_options"],
            ),
        ),
    )

    score = grade_conversation_path(
        case,
        [
            BenchmarkConversationTraceStep(
                mode="start",
                source_run_id=None,
                run_id=uuid4(),
                status="awaiting_confirmation",
                version_label="v1",
            ),
            BenchmarkConversationTraceStep(
                mode="replan",
                source_run_id=uuid4(),
                run_id=uuid4(),
                status="awaiting_confirmation",
                version_label="v2",
            ),
        ],
        ["user_follow_up"],
    )

    assert score.passed is False
    assert "assistant_replan_options" in score.reason


def test_report_writer_creates_parent_directory_and_json_file() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir / "nested"))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_path.name == "family_afternoon_v1.json"
        assert payload["case_id"] == "family_afternoon_v1"
        assert payload["report_path"] == str(report_path)
    finally:
        _cleanup_report_dir(report_dir)


def test_report_writer_output_excludes_raw_ids_and_sensitive_keys() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="failed",
        scores=[
            BenchmarkScore(
                name="safety",
                score=0.0,
                passed=False,
                reason="bad",
                details={
                    "action_id": "do-not-write",
                    "tool_event_id": "do-not-write",
                    "api_key": "do-not-write",
                    "token": "do-not-write",
                    "secret": "do-not-write",
                    "debug_trace": "do-not-write",
                },
            )
        ],
        overall_score=0.0,
        tool_event_count=1,
        action_count=1,
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        serialized = report_path.read_text(encoding="utf-8")
        assert "do-not-write" not in serialized
        assert "action_id" not in serialized
        assert "tool_event_id" not in serialized
        assert "api_key" not in serialized
        assert "token" not in serialized
        assert "secret" not in serialized
        assert "debug_trace" not in serialized
    finally:
        _cleanup_report_dir(report_dir)


def test_report_writer_includes_workflow_fields_and_agent_roles() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
        workflow_status="completed",
        workflow_node_history=list(REQUIRED_WORKFLOW_NODES),
        agent_roles=list(REQUIRED_AGENT_ROLES),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["workflow_status"] == "completed"
        assert payload["workflow_node_history"] == list(REQUIRED_WORKFLOW_NODES)
        assert payload["agent_roles"] == list(REQUIRED_AGENT_ROLES)
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_workflow_timing_summary() -> None:
    result = BenchmarkCaseResult(
        case_id="family_afternoon_v1",
        status="passed",
        scores=[],
        overall_score=1.0,
        tool_event_count=8,
        action_count=1,
        workflow_timing_summary=_workflow_timing_summary(
            total_duration_ms=120,
            stages=[
                WorkflowStageTimingEntry(
                    node_name="initialize",
                    attempt_count=1,
                    total_duration_ms=5,
                ),
                WorkflowStageTimingEntry(
                    node_name="execute_searches",
                    attempt_count=2,
                    total_duration_ms=40,
                ),
            ],
        ),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["workflow_timing_summary"]["schema_version"] == "workflow_timing_summary_v1"
        assert payload["workflow_timing_summary"]["stages"][1]["attempt_count"] == 2
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_run_summary_envelope() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "family_afternoon_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "run_summary": {
                "schema_version": "weekendpilot_run_summary_v1",
                "run_id": str(uuid4()),
                "trace_id": "trace-1",
                "case_id": "family_afternoon_v1",
                "agent_version": "agent-v1",
                "prompt_version": "prompt-v1",
                "tool_profile": "mock_world",
                "world_profile": "family_afternoon",
                "failure_profile": None,
                "workflow_status": "completed",
                "selected_plan_id": str(uuid4()),
                "plan_status": "selected",
                "execution_status": "succeeded",
                "feedback_status": "completed",
                "tool_event_count": 8,
                "action_count": 1,
                "agent_roles": ["supervisor", "discovery"],
                "workflow_timing_summary": {
                    "schema_version": "workflow_timing_summary_v1",
                    "total_duration_ms": 120,
                    "stage_count": 1,
                    "stages": [
                        {
                            "node_name": "initialize",
                            "attempt_count": 1,
                            "total_duration_ms": 120,
                        }
                    ],
                },
                "error": None,
            },
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["run_summary"]["schema_version"] == "weekendpilot_run_summary_v1"
        assert payload["run_summary"]["workflow_status"] == "completed"
        assert payload["run_summary"]["workflow_timing_summary"]["total_duration_ms"] == 120
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_taxonomy() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "solo_afternoon_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "taxonomy": _taxonomy_payload(
                scenario_bucket="solo",
                level="L1",
                tags=["baseline", "light_activity", "light_meal"],
            ),
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["taxonomy"]["suite"] == "locallife_bench_v1"
        assert payload["taxonomy"]["scenario_bucket"] == "solo"
        assert payload["taxonomy"]["tags"] == ["baseline", "light_activity", "light_meal"]
    finally:
        _cleanup_report_dir(report_dir)


def test_case_report_writer_includes_memory_policy_summary() -> None:
    result = BenchmarkCaseResult.model_validate(
        {
            "case_id": "family_memory_advisory_fill_v1",
            "status": "passed",
            "scores": [],
            "overall_score": 1.0,
            "tool_event_count": 8,
            "action_count": 1,
            "memory_policy_summary": {
                "policy_version": "memory_query_policy_v1",
                "considered_count": 1,
                "used_count": 0,
                "ignored_count": 0,
                "downgraded_count": 1,
                "overridden_count": 0,
                "primary_influence_count": 0,
                "advisory_influence_count": 1,
                "no_influence_count": 0,
            },
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_case_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["memory_policy_summary"]["policy_version"] == "memory_query_policy_v1"
        assert payload["memory_policy_summary"]["downgraded_count"] == 1
        assert payload["memory_policy_summary"]["advisory_influence_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def test_benchmark_timing_summary_uses_nearest_rank_percentiles_and_stage_order() -> None:
    results = [
        BenchmarkCaseResult(
            case_id=f"case-{index}",
            status="passed",
            scores=[],
            overall_score=1.0,
            tool_event_count=8,
            action_count=1,
            workflow_timing_summary=summary,
        )
        for index, summary in enumerate(
            [
                _workflow_timing_summary(
                    total_duration_ms=100,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=20,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=30,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=120,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=35,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=140,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=2,
                            total_duration_ms=40,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=22,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=160,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="logical_planner_agent",
                            attempt_count=1,
                            total_duration_ms=24,
                        ),
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=45,
                        ),
                    ],
                ),
                _workflow_timing_summary(
                    total_duration_ms=300,
                    stages=[
                        WorkflowStageTimingEntry(
                            node_name="execute_searches",
                            attempt_count=1,
                            total_duration_ms=60,
                        ),
                    ],
                ),
            ]
        )
    ]

    summary = summarize_benchmark_timing(results)

    assert summary.schema_version == "benchmark_timing_summary_v1"
    assert summary.case_count == 5
    assert summary.overall_total_duration_ms is not None
    assert summary.overall_total_duration_ms.sample_count == 5
    assert summary.overall_total_duration_ms.min_ms == 100
    assert summary.overall_total_duration_ms.p50_ms == 140
    assert summary.overall_total_duration_ms.p95_ms == 300
    assert summary.overall_total_duration_ms.p99_ms == 300
    assert summary.overall_total_duration_ms.max_ms == 300
    assert summary.overall_total_duration_ms.mean_ms == 164.0
    assert [entry.node_name for entry in summary.stages[:2]] == [
        "execute_searches",
        "logical_planner_agent",
    ]
    execute_searches = summary.stages[0]
    assert execute_searches.sample_count == 5
    assert execute_searches.retry_case_count == 1
    assert execute_searches.min_ms == 30
    assert execute_searches.p50_ms == 40
    assert execute_searches.p95_ms == 60
    assert execute_searches.p99_ms == 60
    assert execute_searches.max_ms == 60
    assert execute_searches.mean_ms == 42.0


def test_run_report_writer_creates_suite_report_with_timing_summary() -> None:
    result = BenchmarkRunReport(
        run_status="passed",
        case_results=[],
        passed_count=1,
        failed_count=0,
        error_count=0,
        overall_score=1.0,
        benchmark_timing_summary=summarize_benchmark_timing(
            [
                BenchmarkCaseResult(
                    case_id="family_afternoon_v1",
                    status="passed",
                    scores=[],
                    overall_score=1.0,
                    tool_event_count=8,
                    action_count=1,
                    workflow_timing_summary=_workflow_timing_summary(
                        total_duration_ms=120,
                        stages=[
                            WorkflowStageTimingEntry(
                                node_name="execute_searches",
                                attempt_count=1,
                                total_duration_ms=40,
                            )
                        ],
                    ),
                )
            ]
        ),
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_run_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_path.name == "run-report.json"
        assert payload["report_path"] == str(report_path)
        assert payload["benchmark_timing_summary"]["schema_version"] == "benchmark_timing_summary_v1"
        assert payload["benchmark_timing_summary"]["overall_total_duration_ms"]["sample_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def test_run_report_writer_includes_benchmark_summary_envelope() -> None:
    result = BenchmarkRunReport.model_validate(
        {
            "run_status": "passed",
            "case_results": [],
            "passed_count": 1,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "benchmark_timing_summary": {
                "schema_version": "benchmark_timing_summary_v1",
                "case_count": 1,
                "overall_total_duration_ms": {
                    "sample_count": 1,
                    "min_ms": 120,
                    "p50_ms": 120,
                    "p95_ms": 120,
                    "p99_ms": 120,
                    "max_ms": 120,
                    "mean_ms": 120.0,
                },
                "stages": [],
            },
            "benchmark_summary": {
                "schema_version": "weekendpilot_benchmark_summary_v1",
                "run_status": "passed",
                "case_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "error_count": 0,
                "overall_score": 1.0,
                "matrix_summary": {
                    "schema_version": "weekendpilot_benchmark_case_matrix_v1",
                    "case_count": 1,
                    "scenario_bucket_counts": {"family": 1},
                    "level_counts": {"L1": 1},
                    "tool_profile_counts": {"mock_world": 1},
                    "world_profile_counts": {"family_afternoon": 1},
                    "failure_mode_counts": {"none": 1},
                    "tag_counts": {"baseline": 1},
                },
                "benchmark_timing_summary": {
                    "schema_version": "benchmark_timing_summary_v1",
                    "case_count": 1,
                    "overall_total_duration_ms": {
                        "sample_count": 1,
                        "min_ms": 120,
                        "p50_ms": 120,
                        "p95_ms": 120,
                        "p99_ms": 120,
                        "max_ms": 120,
                        "mean_ms": 120.0,
                    },
                    "stages": [],
                },
            },
        }
    )
    report_dir = _unit_report_dir()

    try:
        report_path = Path(write_run_report(result, report_dir))

        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["benchmark_summary"]["schema_version"] == "weekendpilot_benchmark_summary_v1"
        assert payload["benchmark_summary"]["case_count"] == 1
        assert payload["benchmark_summary"]["matrix_summary"]["scenario_bucket_counts"] == {"family": 1}
        assert payload["benchmark_summary"]["matrix_summary"]["tool_profile_counts"] == {"mock_world": 1}
        assert payload["benchmark_summary"]["benchmark_timing_summary"]["case_count"] == 1
    finally:
        _cleanup_report_dir(report_dir)


def test_benchmark_summary_schema_includes_suite_and_outcome_rollup_fields() -> None:
    assert "suite_id" in BenchmarkSummary.model_fields
    assert "suite_title" in BenchmarkSummary.model_fields
    assert "outcome_rollup" in BenchmarkSummary.model_fields
    assert "integrity_coverage_summary" in BenchmarkSummary.model_fields


def test_build_case_integrity_coverage_summary_returns_expected_counts_for_v2_integrity_suite() -> None:
    summary = build_case_integrity_coverage_summary(load_benchmark_suite("v2_integrity"))

    assert summary.case_count == 20
    assert summary.memory_case_count == 6
    assert summary.recovery_case_count == 8
    assert summary.continuation_case_count == 3
    assert summary.robustness_case_count == 4
    assert summary.l4_case_count == 1


def test_run_cases_includes_additive_outcome_rollup_for_ad_hoc_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = [
        BenchmarkCase(
            case_id="family-pass",
            title="Family pass",
            user_input="Plan a family outing.",
            taxonomy=_taxonomy_payload(
                scenario_bucket="family",
                level="L1",
                tags=["baseline", "child_friendly", "light_meal"],
            ),
            expected=BenchmarkExpectedOutcome(
                required_tool_names=["search_poi"],
                min_tool_event_count=1,
                min_action_count=1,
            ),
        ),
        BenchmarkCase(
            case_id="solo-fail",
            title="Solo fail",
            user_input="Plan a solo outing.",
            taxonomy=_taxonomy_payload(
                scenario_bucket="solo",
                level="L1",
                tags=["baseline", "light_activity"],
            ),
            expected=BenchmarkExpectedOutcome(
                required_tool_names=["search_poi"],
                min_tool_event_count=1,
                min_action_count=1,
            ),
        ),
    ]
    result_map = {
        "family-pass": _benchmark_case_result(cases[0], status="passed"),
        "solo-fail": _benchmark_case_result(cases[1], status="failed"),
    }
    report_dir = _unit_report_dir()
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None, report_dir=report_dir)

    monkeypatch.setattr(harness, "run_case", lambda case: result_map[case.case_id])

    try:
        report = harness.run_cases(cases)

        assert report.report_path is not None
        assert report.report_path.endswith("run-report.json")
        assert report.benchmark_summary is not None
        assert report.benchmark_summary.suite_id is None
        assert report.benchmark_summary.suite_title is None
        assert report.benchmark_summary.v2_taxonomy_summary is not None
        assert report.benchmark_summary.v2_taxonomy_summary.case_count == 2
        assert report.benchmark_summary.v2_taxonomy_summary.level_counts == {"L1": 2}
        assert report.benchmark_summary.v2_taxonomy_summary.memory_mode_counts == {"none": 2}
        assert report.benchmark_summary.v2_taxonomy_summary.conversation_mode_counts == {
            "single_turn": 2
        }
        assert report.benchmark_summary.v2_taxonomy_summary.stability_required_counts == {"false": 2}
        assert report.benchmark_summary.integrity_coverage_summary is not None
        assert report.benchmark_summary.integrity_coverage_summary.case_count == 2
        assert report.benchmark_summary.integrity_coverage_summary.memory_case_count == 0
        assert report.benchmark_summary.integrity_coverage_summary.recovery_case_count == 0
        assert report.benchmark_summary.integrity_coverage_summary.continuation_case_count == 0
        assert report.benchmark_summary.integrity_coverage_summary.robustness_case_count == 0
        assert report.benchmark_summary.integrity_coverage_summary.l4_case_count == 0
        assert report.benchmark_summary.outcome_rollup is not None
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].case_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["family"].pass_rate == 1.0
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["solo"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.scenario_bucket_outcomes["solo"].pass_rate == 0.0
        assert "baseline" not in report.benchmark_summary.outcome_rollup.constraint_tag_outcomes
        assert report.benchmark_summary.outcome_rollup.constraint_tag_outcomes["child_friendly"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.constraint_tag_outcomes["light_activity"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].case_count == 2
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].passed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].failed_count == 1
        assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["none"].pass_rate == 0.5
    finally:
        _cleanup_report_dir(report_dir)


def test_run_suite_uses_canonical_suite_report_filename_and_normalizes_failures_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = BenchmarkCase(
        case_id="family_route_failure_v1",
        title="Recovery case",
        user_input="Plan around the route failure.",
        failure_profile="route_unavailable_v0",
        taxonomy=_taxonomy_payload(
            scenario_bucket="family",
            level="L2",
            tags=["child_friendly", "failure_injected", "light_meal", "route_failure"],
            failure_mode="route_unavailable",
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["check_route"],
            min_tool_event_count=1,
            min_action_count=0,
            expected_workflow_status="failed",
            expected_execution_status=None,
            expected_feedback_status=None,
            expected_error_type="recovery_stopped",
        ),
    )
    suite_description = BenchmarkSuiteDescription(
        suite_id="recovery_focused",
        title="Recovery focused benchmark suite",
        description="Recovery-only suite",
        case_ids=[case.case_id],
        case_count=1,
        matrix_summary=build_case_matrix_summary([case]),
    )
    report_dir = _unit_report_dir()
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None, report_dir=report_dir)
    captured: dict[str, str] = {}
    run_suite = getattr(harness, "run_suite", None)

    assert callable(run_suite)

    monkeypatch.setattr(benchmark_harness, "load_benchmark_suite", lambda suite_id: [case])
    monkeypatch.setattr(benchmark_harness, "list_benchmark_suites", lambda: [suite_description])
    monkeypatch.setattr(
        benchmark_harness,
        "write_run_report",
        lambda result, directory, filename="run-report.json": captured.setdefault(
            "report_path",
            str(Path(directory) / filename),
        ),
    )
    monkeypatch.setattr(
        harness,
        "run_case",
        lambda benchmark_case: _benchmark_case_result(
            benchmark_case,
            status="passed",
            workflow_status="failed",
        ),
    )

    report = run_suite("failures")

    assert report.report_path is not None
    assert report.report_path.endswith("suite-recovery_focused-run-report.json")
    assert captured["report_path"].endswith("suite-recovery_focused-run-report.json")
    assert report.benchmark_summary is not None
    assert report.benchmark_summary.suite_id == "recovery_focused"
    assert report.benchmark_summary.suite_title == "Recovery focused benchmark suite"
    assert report.benchmark_summary.v2_taxonomy_summary is not None
    assert report.benchmark_summary.v2_taxonomy_summary.case_count == 1
    assert report.benchmark_summary.v2_taxonomy_summary.failure_mode_counts == {"route_unavailable": 1}
    assert report.benchmark_summary.v2_taxonomy_summary.level_counts == {"L5": 1}
    assert report.benchmark_summary.integrity_coverage_summary is not None
    assert report.benchmark_summary.integrity_coverage_summary.case_count == 1
    assert report.benchmark_summary.integrity_coverage_summary.memory_case_count == 0
    assert report.benchmark_summary.integrity_coverage_summary.recovery_case_count == 1
    assert report.benchmark_summary.integrity_coverage_summary.continuation_case_count == 0
    assert report.benchmark_summary.integrity_coverage_summary.robustness_case_count == 0
    assert report.benchmark_summary.integrity_coverage_summary.l4_case_count == 0
    assert report.benchmark_summary.outcome_rollup is not None
    assert set(report.benchmark_summary.outcome_rollup.constraint_tag_outcomes) == {
        "child_friendly",
        "light_meal",
    }
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].case_count == 1
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].passed_count == 1
    assert report.benchmark_summary.outcome_rollup.failure_mode_outcomes["route_unavailable"].pass_rate == 1.0


def test_harness_uses_continuation_path_when_case_has_continuations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None)
    case = BenchmarkCase(
        case_id="continuation_case",
        title="Continuation case",
        user_input="Plan something nearby.",
        continuations=[
            BenchmarkContinuationRequest(
                mode="clarify",
                user_input="This afternoon I want a nearby solo outing for a few hours.",
            )
        ],
        taxonomy=_taxonomy_payload(
            scenario_bucket="solo",
            level="L3",
            tags=["clarification_turn", "conversation_continuation"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
        ),
    )
    calls: list[str] = []

    monkeypatch.setattr(
        harness,
        "_run_legacy_case",
        lambda benchmark_case: calls.append(f"legacy:{benchmark_case.case_id}"),
    )
    monkeypatch.setattr(
        harness,
        "_run_continuation_case",
        lambda benchmark_case: _benchmark_case_result(benchmark_case, status="passed"),
    )

    result = harness.run_case(case)

    assert result.status == "passed"
    assert calls == []


def test_legacy_case_passes_explicit_workflow_settings_into_workflow_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_dir = _unit_report_dir()
    workflow_settings = Settings(_env_file=None, app_name="benchmark-explicit-settings", llm_enabled=True)
    workflow_llm_client = object()
    harness = BenchmarkHarness(
        session=None,
        cache=None,
        rate_limiter=None,
        report_dir=report_dir,
        workflow_settings=workflow_settings,
        workflow_llm_client=workflow_llm_client,
    )
    captured: dict[str, object] = {}

    class FakeWorkflowDependencies:
        def __init__(self, **kwargs) -> None:
            captured["settings"] = kwargs.get("settings")
            captured["llm_client"] = kwargs.get("llm_client")

    class FakeWorkflowRunner:
        def __init__(self, dependencies) -> None:
            captured["dependencies"] = dependencies

        def run(self, request):
            captured["request"] = request
            return SimpleNamespace(
                run_id=None,
                trace_id=None,
                status="error",
                error_json={"message": "expected"},
                tool_event_count=0,
                action_count=0,
                feedback_status=None,
                observability_status=None,
                workflow_timing_summary=None,
                node_history=[],
                agent_results=[],
            )

    monkeypatch.setattr(benchmark_harness, "_Repositories", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        harness,
        "_prepare_case_user",
        lambda benchmark_case, repositories: ("benchmark-user", SimpleNamespace(display_name="Benchmark User")),
    )
    monkeypatch.setattr(harness, "_finalize_case_result", lambda result, repositories=None: result)
    monkeypatch.setattr(benchmark_harness, "WeekendPilotWorkflowDependencies", FakeWorkflowDependencies)
    monkeypatch.setattr(benchmark_harness, "WeekendPilotWorkflowRunner", FakeWorkflowRunner)

    try:
        result = harness._run_legacy_case(_benchmark_case())

        assert captured["settings"] is workflow_settings
        assert captured["llm_client"] is workflow_llm_client
        assert result.status == "error"
    finally:
        _cleanup_report_dir(report_dir)


def test_continuation_case_passes_explicit_workflow_settings_into_demo_workflow_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_dir = _unit_report_dir()
    workflow_settings = Settings(_env_file=None, app_name="benchmark-explicit-settings", llm_enabled=True)
    workflow_llm_client = object()
    harness = BenchmarkHarness(
        session=None,
        cache=None,
        rate_limiter=None,
        report_dir=report_dir,
        workflow_settings=workflow_settings,
        workflow_llm_client=workflow_llm_client,
    )
    case = BenchmarkCase(
        case_id="continuation_case",
        title="Continuation case",
        user_input="Plan something nearby.",
        continuations=[
            BenchmarkContinuationRequest(
                mode="clarify",
                user_input="This afternoon I want a nearby solo outing for a few hours.",
            )
        ],
        taxonomy=_taxonomy_payload(
            scenario_bucket="solo",
            level="L3",
            tags=["clarification_turn", "conversation_continuation"],
        ),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=1,
        ),
    )
    captured: dict[str, object] = {}

    class FakeDemoWorkflowService:
        def __init__(
            self,
            session,
            cache,
            rate_limiter,
            trace_buffer_path,
            workflow_settings=None,
            workflow_llm_client=None,
        ) -> None:
            captured["workflow_settings"] = workflow_settings
            captured["workflow_llm_client"] = workflow_llm_client
            captured["trace_buffer_path"] = trace_buffer_path

        def start_run(self, request, *, override=None):
            captured["request"] = request
            captured["override"] = override
            raise benchmark_harness.DemoServiceError(409, "stop after capture")

    monkeypatch.setattr(benchmark_harness, "_Repositories", lambda session: SimpleNamespace())
    monkeypatch.setattr(
        harness,
        "_prepare_case_user",
        lambda benchmark_case, repositories: ("benchmark-user", SimpleNamespace(display_name="Benchmark User")),
    )
    monkeypatch.setattr(harness, "_finalize_case_result", lambda result, repositories=None: result)
    monkeypatch.setattr(benchmark_harness, "DemoWorkflowService", FakeDemoWorkflowService)

    try:
        result = harness._run_continuation_case(case)

        assert captured["workflow_settings"] is workflow_settings
        assert captured["workflow_llm_client"] is workflow_llm_client
        assert result.status == "error"
        assert result.failure_reasons == ["stop after capture"]
    finally:
        _cleanup_report_dir(report_dir)


def test_harness_uses_legacy_path_when_case_has_no_continuations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None)
    case = _benchmark_case()
    calls: list[str] = []

    monkeypatch.setattr(
        harness,
        "_run_legacy_case",
        lambda benchmark_case: calls.append(f"legacy:{benchmark_case.case_id}") or _benchmark_case_result(
            benchmark_case,
            status="passed",
        ),
    )
    monkeypatch.setattr(
        harness,
        "_run_continuation_case",
        lambda benchmark_case: _benchmark_case_result(benchmark_case, status="failed"),
    )

    result = harness.run_case(case)

    assert result.status == "passed"
    assert calls == ["legacy:case"]


def test_harness_rejects_non_mock_world_case_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = BenchmarkHarness(session=None, cache=None, rate_limiter=None)
    case = BenchmarkCase(
        case_id="ad_hoc_preview_case",
        title="Ad hoc preview case",
        user_input="Plan an AMAP preview outing.",
        tool_profile="amap",
        world_profile="amap_shanghai_live",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=0,
        ),
    )
    calls: list[str] = []

    monkeypatch.setattr(
        harness,
        "_run_legacy_case",
        lambda benchmark_case: calls.append(f"legacy:{benchmark_case.case_id}") or _benchmark_case_result(
            benchmark_case,
            status="passed",
        ),
    )
    monkeypatch.setattr(
        harness,
        "_run_continuation_case",
        lambda benchmark_case: calls.append(f"continuation:{benchmark_case.case_id}") or _benchmark_case_result(
            benchmark_case,
            status="passed",
        ),
    )

    result = harness.run_case(case)

    assert result.status == "error"
    assert result.run_id is None
    assert result.trace_id is None
    assert result.tool_event_count == 0
    assert result.action_count == 0
    assert result.v2_taxonomy == resolve_benchmark_case_v2_taxonomy(case)
    assert result.failure_reasons == ["Unsupported benchmark tool_profile: amap"]
    assert calls == []


def _benchmark_case() -> BenchmarkCase:
    return BenchmarkCase(
        case_id="case",
        title="Case",
        user_input="Plan an afternoon.",
        taxonomy=_taxonomy_payload(),
        expected=BenchmarkExpectedOutcome(
            required_tool_names=["search_poi"],
            min_tool_event_count=1,
            min_action_count=2,
        ),
    )


def _benchmark_case_result(
    case: BenchmarkCase,
    *,
    status: str,
    workflow_status: str = "completed",
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        case_id=case.case_id,
        status=status,
        taxonomy=case.taxonomy,
        scores=[],
        overall_score=1.0 if status == "passed" else 0.0,
        tool_event_count=max(case.expected.min_tool_event_count, 1),
        action_count=max(case.expected.min_action_count, 0),
        workflow_status=workflow_status,
    )


def _workflow_timing_summary(
    *,
    total_duration_ms: int,
    stages: list[WorkflowStageTimingEntry],
) -> WorkflowTimingSummary:
    return WorkflowTimingSummary(
        total_duration_ms=total_duration_ms,
        stage_count=len(stages),
        stages=stages,
    )


def _unit_report_dir() -> Path:
    return Path("var/test-benchmarks") / f"unit-{uuid4()}"


def _cleanup_report_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        path.rmdir()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    var_dir = parent.parent
    if var_dir.exists() and not any(var_dir.iterdir()):
        var_dir.rmdir()
