from __future__ import annotations

from typing import Any, Sequence

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.schemas import BenchmarkFailureChainSummary


_INJECTED_ERROR_TYPES = {"failure_injected", "failure_injected_response"}


def build_failure_chain_summary(
    *,
    failure_profile: str,
    tool_events: Sequence[Any],
    run_metadata: Any,
    workflow_status: str | None,
) -> BenchmarkFailureChainSummary:
    recovery = _recovery_metadata(run_metadata)
    attempt_count = _int_field(recovery, "attempt_count")
    max_attempts = _int_field(recovery, "max_attempts")
    attempts = recovery.get("attempts")
    if not isinstance(attempts, list):
        raise BenchmarkHarnessError("Benchmark recovery metadata is missing attempts.")

    recovery_actions: list[str] = []
    seen_actions: set[str] = set()
    for attempt in attempts:
        action = _string_field(attempt, "recovery_action", required=False)
        if action and action not in seen_actions:
            recovery_actions.append(action)
            seen_actions.add(action)

    injected_effects: list[str] = []
    seen_effects: set[str] = set()
    for event in _ordered_tool_events(tool_events):
        error_json = _value(event, "error_json")
        if not isinstance(error_json, dict) or error_json.get("error_type") not in _INJECTED_ERROR_TYPES:
            continue
        details = error_json.get("details")
        if not isinstance(details, dict):
            raise BenchmarkHarnessError("Injected benchmark tool event is missing effect details.")
        tool_name = _string_field(event, "tool_name")
        status = _string_field(event, "status")
        effect_type = _string_field(details, "effect_type", required=False) or _string_field(
            details,
            "injected_error_type",
            required=False,
        )
        if not effect_type:
            raise BenchmarkHarnessError("Injected benchmark tool event is missing effect_type.")
        signature = f"{tool_name}:{effect_type}:{status}"
        if signature not in seen_effects:
            injected_effects.append(signature)
            seen_effects.add(signature)

    if not injected_effects:
        raise BenchmarkHarnessError("Benchmark failure chain summary requires injected benchmark tool events.")

    return BenchmarkFailureChainSummary(
        profile_id=failure_profile,
        injected_effects=injected_effects,
        recovery_actions=recovery_actions,
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        bounded=attempt_count <= max_attempts,
        terminal_workflow_status=workflow_status,
    )


def _recovery_metadata(run_metadata: Any) -> dict[str, Any]:
    workflow = _value(run_metadata, "workflow")
    if not isinstance(workflow, dict):
        raise BenchmarkHarnessError("Benchmark run metadata is missing workflow recovery metadata.")
    recovery = workflow.get("recovery")
    if not isinstance(recovery, dict):
        raise BenchmarkHarnessError("Benchmark run metadata is missing workflow recovery metadata.")
    return recovery


def _int_field(source: Any, key: str) -> int:
    value = _value(source, key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise BenchmarkHarnessError(f"Benchmark recovery metadata field {key!r} is invalid.") from exc


def _string_field(source: Any, key: str, *, required: bool = True) -> str | None:
    value = _value(source, key)
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value:
        raise BenchmarkHarnessError(f"Benchmark failure-chain field {key!r} is invalid.")
    return value


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _ordered_tool_events(tool_events: Sequence[Any]) -> list[Any]:
    indexed_events = list(enumerate(tool_events))
    indexed_events.sort(
        key=lambda item: (
            _event_sequence(item[1]),
            item[0],
        )
    )
    return [event for _, event in indexed_events]


def _event_sequence(event: Any) -> int:
    request_json = _value(event, "request_json")
    if not isinstance(request_json, dict):
        return 1_000_000_000
    value = request_json.get("event_sequence")
    try:
        return int(value)
    except (TypeError, ValueError):
        return 1_000_000_000
