from __future__ import annotations

from backend.app.benchmark import load_benchmark_case, load_registered_benchmark_cases
from backend.app.benchmark.matrix import build_case_v2_matrix_summary
from backend.app.benchmark.schemas import (
    BenchmarkCaseV2MatrixSummary,
    BenchmarkCaseV2Taxonomy,
    resolve_benchmark_case_v2_taxonomy,
)


def test_benchmark_case_v2_taxonomy_accepts_expected_values() -> None:
    taxonomy = BenchmarkCaseV2Taxonomy(
        scenario_bucket="family",
        level="L4",
        failure_mode="none",
        memory_mode="advisory_fill",
        conversation_mode="replan_versioned",
        stability_required=True,
    )

    assert taxonomy.scenario_bucket == "family"
    assert taxonomy.level == "L4"
    assert taxonomy.failure_mode == "none"
    assert taxonomy.memory_mode == "advisory_fill"
    assert taxonomy.conversation_mode == "replan_versioned"
    assert taxonomy.stability_required is True


def test_benchmark_case_v2_taxonomy_rejects_invalid_failure_mode() -> None:
    try:
        BenchmarkCaseV2Taxonomy(
            scenario_bucket="family",
            level="L2",
            failure_mode="RouteUnavailable",
            memory_mode="none",
            conversation_mode="single_turn",
            stability_required=False,
        )
    except ValueError as exc:
        assert "v2 taxonomy failure_mode" in str(exc)
    else:  # pragma: no cover - defensive guard for red stage
        raise AssertionError("Expected invalid V2 failure mode to be rejected")


def test_all_registered_cases_resolve_non_null_v2_taxonomy() -> None:
    cases = load_registered_benchmark_cases()

    resolved = [resolve_benchmark_case_v2_taxonomy(case) for case in cases]

    assert len(resolved) == 22
    assert all(isinstance(taxonomy, BenchmarkCaseV2Taxonomy) for taxonomy in resolved)


def test_v2_taxonomy_fallback_derives_expected_modes_for_representative_cases() -> None:
    assert resolve_benchmark_case_v2_taxonomy(load_benchmark_case("family_memory_override_v1")).memory_mode == (
        "override_guarded"
    )
    assert resolve_benchmark_case_v2_taxonomy(load_benchmark_case("family_memory_advisory_fill_v1")).memory_mode == (
        "advisory_fill"
    )
    assert resolve_benchmark_case_v2_taxonomy(
        load_benchmark_case("family_memory_expired_advisory_v1")
    ).memory_mode == "expired_advisory"
    assert resolve_benchmark_case_v2_taxonomy(
        load_benchmark_case("solo_clarification_continuation_v1")
    ).conversation_mode == "clarification"
    assert resolve_benchmark_case_v2_taxonomy(
        load_benchmark_case("family_replan_version_continuation_v1")
    ).conversation_mode == "replan_versioned"
    assert resolve_benchmark_case_v2_taxonomy(load_benchmark_case("family_route_failure_v1")).failure_mode == (
        "route_unavailable"
    )
    assert resolve_benchmark_case_v2_taxonomy(
        load_benchmark_case("family_route_and_dining_unavailable_v1")
    ).failure_mode == "route_and_dining_unavailable"
    assert resolve_benchmark_case_v2_taxonomy(
        load_benchmark_case("family_distractor_selection_v1")
    ).stability_required is True
    assert resolve_benchmark_case_v2_taxonomy(load_benchmark_case("rainy_day_stable_sorting_v1")).stability_required


def test_v2_taxonomy_fallback_resolves_existing_l4_style_case() -> None:
    taxonomy = resolve_benchmark_case_v2_taxonomy(load_benchmark_case("family_replan_version_continuation_v1"))

    assert taxonomy.level == "L4"


def test_build_case_v2_matrix_summary_returns_expected_counts_for_v2_integrity_member_pool() -> None:
    case_ids = [
        "family_memory_override_v1",
        "family_route_failure_v1",
        "family_route_and_dining_unavailable_v1",
        "rainy_day_ticket_sold_out_v1",
        "family_memory_advisory_fill_v1",
        "family_memory_expired_advisory_v1",
        "solo_clarification_continuation_v1",
        "family_replan_version_continuation_v1",
        "family_distractor_selection_v1",
        "friends_distractor_selection_v1",
        "rainy_day_stable_sorting_v1",
        "budget_indoor_fallback_v1",
    ]
    cases = [load_benchmark_case(case_id) for case_id in case_ids]

    summary = build_case_v2_matrix_summary(cases)

    assert isinstance(summary, BenchmarkCaseV2MatrixSummary)
    assert summary.case_count == 12
    assert summary.scenario_bucket_counts == {
        "family": 7,
        "friends": 1,
        "mixed": 2,
        "solo": 1,
        "unknown": 1,
    }
    assert summary.level_counts == {"L2": 5, "L3": 3, "L4": 1, "L5": 3}
    assert summary.failure_mode_counts == {
        "none": 9,
        "route_and_dining_unavailable": 1,
        "route_unavailable": 1,
        "ticket_sold_out_and_bad_weather": 1,
    }
    assert summary.memory_mode_counts == {
        "advisory_fill": 1,
        "expired_advisory": 1,
        "none": 9,
        "override_guarded": 1,
    }
    assert summary.conversation_mode_counts == {
        "clarification": 1,
        "replan_versioned": 1,
        "single_turn": 10,
    }
    assert summary.stability_required_counts == {"false": 3, "true": 9}
