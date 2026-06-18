from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.benchmark import load_benchmark_case, load_registered_benchmark_cases
from backend.app.benchmark.case_matrix import (
    build_benchmark_case_matrix_manifest,
    get_benchmark_case_matrix_suite_case_ids,
    get_registered_benchmark_case_ids,
    list_benchmark_case_matrix_rows,
)


EXPECTED_SUITE_COUNTS = {
    "baseline": 6,
    "expanded": 5,
    "recovery_focused": 8,
    "memory_governance": 6,
    "conversation_continuations": 2,
    "robustness_focused": 4,
    "default": 11,
    "release_gate_v1": 15,
    "v2_integrity": 20,
    "all_registered": 30,
}


def test_case_matrix_rows_are_unique_and_keep_canonical_registered_order() -> None:
    rows = list_benchmark_case_matrix_rows()

    assert len(rows) == 30
    assert len({row.case_id for row in rows}) == 30
    assert tuple(row.case_id for row in rows) == get_registered_benchmark_case_ids()
    assert tuple(case.case_id for case in load_registered_benchmark_cases()) == get_registered_benchmark_case_ids()


def test_case_matrix_suite_membership_matches_current_baseline() -> None:
    manifest = build_benchmark_case_matrix_manifest()

    assert manifest.registered_case_count == 30
    assert manifest.suite_counts == EXPECTED_SUITE_COUNTS
    assert tuple(case.case_id for case in manifest.cases) == get_registered_benchmark_case_ids()
    assert tuple(case.case_id for case in build_benchmark_case_matrix_manifest("v2_integrity").cases) == (
        get_benchmark_case_matrix_suite_case_ids("v2_integrity")
    )


def test_case_matrix_taxonomy_matches_fixture_taxonomy_for_representative_cases() -> None:
    rows_by_case_id = {row.case_id: row for row in list_benchmark_case_matrix_rows()}

    for case_id in (
        "family_afternoon_v1",
        "family_memory_sensitive_minimization_v1",
        "family_route_and_dining_unavailable_v1",
        "solo_clarification_continuation_v1",
        "budget_indoor_fallback_v1",
    ):
        fixture = load_benchmark_case(case_id)
        row = rows_by_case_id[case_id]

        assert row.world_profile == fixture.world_profile
        assert row.failure_profile == fixture.failure_profile
        assert row.taxonomy.model_dump(mode="json") == fixture.taxonomy.model_dump(mode="json")


def test_case_matrix_export_script_prints_deterministic_json_for_selected_suite() -> None:
    script_path = Path("scripts/generate_benchmark_case_matrix.py")

    completed = subprocess.run(
        [sys.executable, str(script_path), "--suite-id", "v2_integrity", "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)

    assert payload["registered_case_count"] == 30
    assert payload["selected_suite_id"] == "v2_integrity"
    assert payload["suite_counts"]["v2_integrity"] == 20
    assert len(payload["cases"]) == 20
    assert payload["cases"][0]["case_id"] == "family_memory_override_v1"
