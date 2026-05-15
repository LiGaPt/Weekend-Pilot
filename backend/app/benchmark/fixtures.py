from __future__ import annotations

import json
from importlib import resources
from json import JSONDecodeError

from pydantic import ValidationError

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkCase


_DEFAULT_CASE_IDS = ("family_afternoon_v1",)


def load_benchmark_case(case_id: str) -> BenchmarkCase:
    if case_id not in _DEFAULT_CASE_IDS:
        raise BenchmarkHarnessError(f"Unknown benchmark case ID: {case_id}")

    path = resources.files("backend.app.benchmark").joinpath("cases", f"{case_id}.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return BenchmarkCase.model_validate(payload)
    except FileNotFoundError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture not found: {case_id}") from exc
    except JSONDecodeError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture JSON is malformed: {case_id}") from exc
    except ValidationError as exc:
        raise BenchmarkHarnessError(f"Benchmark fixture schema is invalid: {case_id}") from exc


def load_default_benchmark_cases() -> list[BenchmarkCase]:
    return [load_benchmark_case(case_id) for case_id in _DEFAULT_CASE_IDS]
