from __future__ import annotations

import json
from importlib import resources
from json import JSONDecodeError

from pydantic import ValidationError

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkCase


_REGISTERED_CASE_IDS = (
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
)


def load_benchmark_case(case_id: str) -> BenchmarkCase:
    if case_id not in _REGISTERED_CASE_IDS:
        raise BenchmarkHarnessError(f"Unknown benchmark case ID: {case_id}")

    path = resources.files("backend.app.benchmark").joinpath("cases", f"{case_id}.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        case = BenchmarkCase.model_validate(payload)
        _validate_canonical_case(case)
        return case
    except FileNotFoundError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture not found: {case_id}") from exc
    except JSONDecodeError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture JSON is malformed: {case_id}") from exc
    except ValidationError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture schema is invalid: {case_id}") from exc


def load_registered_benchmark_cases() -> list[BenchmarkCase]:
    return [load_benchmark_case(case_id) for case_id in _REGISTERED_CASE_IDS]


def _validate_canonical_case(case: BenchmarkCase) -> None:
    if case.tool_profile != "mock_world":
        raise BenchmarkHarnessError(
            f"Canonical benchmark case must use tool_profile='mock_world': {case.case_id} -> {case.tool_profile}"
        )
