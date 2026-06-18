from __future__ import annotations

import json
from importlib import resources
from json import JSONDecodeError

from pydantic import ValidationError

from backend.app.benchmark.case_matrix import get_registered_benchmark_case_ids
from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkCase


_REGISTERED_CASE_IDS = get_registered_benchmark_case_ids()


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
