from __future__ import annotations

from copy import deepcopy
from typing import Any
from typing import Sequence

from pydantic import BaseModel, Field, ValidationError

from backend.app.models.runtime import AgentRun, Plan
from backend.app.observability.redaction import sanitize_trace_payload


AMAP_PREVIEW_CONFIRMATION_BLOCK_REASON = "AMAP read-only demo runs cannot be confirmed."
CANONICAL_BENCHMARK_BLOCK_REASON = "Canonical benchmark suites support Mock World only."


class RunErrorSummary(BaseModel):
    error_type: str
    message: str
    source: str
    details: dict[str, Any] | None = None


class PreviewDiagnostics(BaseModel):
    schema_version: str = "weekendpilot_preview_diagnostics_v1"
    read_profile: str
    mode: str
    confirmation_allowed: bool
    confirmation_block_reason: str
    benchmark_eligible: bool
    benchmark_block_reason: str
    observed_provider_names: list[str] = Field(default_factory=list)
    provider_event_count: int = 0
    write_tool_event_count: int = 0
    provider_error_types: list[str] = Field(default_factory=list)
    cross_provider_fallback_detected: bool = False


class RunSummary(BaseModel):
    schema_version: str = "weekendpilot_run_summary_v1"
    run_id: str
    trace_id: str | None = None
    case_id: str | None = None
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    failure_profile: str | None = None
    workflow_status: str
    selected_plan_id: str | None = None
    plan_status: str | None = None
    execution_status: str | None = None
    feedback_status: str | None = None
    tool_event_count: int = 0
    action_count: int = 0
    agent_roles: list[str] = Field(default_factory=list)
    workflow_timing_summary: dict[str, Any] | None = None
    preview_diagnostics: PreviewDiagnostics | None = None
    error: RunErrorSummary | None = None


def load_run_summary(metadata: dict[str, Any]) -> RunSummary | None:
    if not isinstance(metadata, dict):
        return None
    summary = metadata.get("summary")
    if not isinstance(summary, dict):
        return None

    summary_payload = deepcopy(summary)
    preview_diagnostics = _validated_preview_diagnostics(summary_payload.get("preview_diagnostics"))
    summary_payload["preview_diagnostics"] = (
        preview_diagnostics.model_dump(mode="json") if preview_diagnostics is not None else None
    )

    try:
        parsed = RunSummary.model_validate(summary_payload)
        return parsed.model_copy(
            update={
                "workflow_timing_summary": _validated_workflow_timing_summary(parsed.workflow_timing_summary),
                "preview_diagnostics": preview_diagnostics,
            }
        )
    except ValidationError:
        return None


def build_run_summary(
    run: AgentRun,
    selected_plan: Plan | None,
    metadata: dict[str, Any],
    *,
    trace_id_override: str | None,
    tool_events: Sequence[Any],
    tool_event_count: int,
    action_count: int,
) -> RunSummary:
    plan_json = selected_plan.plan_json if selected_plan is not None and isinstance(selected_plan.plan_json, dict) else {}
    execution = plan_json.get("execution") if isinstance(plan_json.get("execution"), dict) else {}
    feedback = plan_json.get("feedback") if isinstance(plan_json.get("feedback"), dict) else {}

    return RunSummary(
        run_id=str(run.run_id),
        trace_id=_trace_id(metadata, trace_id_override),
        case_id=run.case_id,
        agent_version=run.agent_version,
        prompt_version=run.prompt_version,
        tool_profile=run.tool_profile,
        world_profile=run.world_profile,
        failure_profile=run.failure_profile,
        workflow_status=run.status,
        selected_plan_id=str(selected_plan.plan_id) if selected_plan is not None else None,
        plan_status=selected_plan.status if selected_plan is not None else None,
        execution_status=_text_or_none(execution.get("status")),
        feedback_status=_text_or_none(feedback.get("status")),
        tool_event_count=max(0, int(tool_event_count)),
        action_count=max(0, int(action_count)),
        agent_roles=_agent_roles(metadata),
        workflow_timing_summary=_workflow_timing_summary_from_metadata(metadata),
        preview_diagnostics=build_preview_diagnostics(run, tool_events),
        error=_run_error_summary(metadata),
    )


def build_preview_diagnostics(
    run: AgentRun,
    tool_events: Sequence[Any],
) -> PreviewDiagnostics | None:
    if run.tool_profile != "amap":
        return None

    observed_provider_names = sorted(
        {
            provider
            for provider in (_tool_event_text(event, "provider") for event in tool_events)
            if provider is not None
        }
    )
    provider_event_count = sum(1 for event in tool_events if _tool_event_text(event, "provider") == "amap")
    write_tool_event_count = sum(1 for event in tool_events if _tool_event_text(event, "tool_type") == "write")

    return PreviewDiagnostics(
        read_profile="amap",
        mode="read_only_preview",
        confirmation_allowed=False,
        confirmation_block_reason=AMAP_PREVIEW_CONFIRMATION_BLOCK_REASON,
        benchmark_eligible=False,
        benchmark_block_reason=CANONICAL_BENCHMARK_BLOCK_REASON,
        observed_provider_names=observed_provider_names,
        provider_event_count=provider_event_count,
        write_tool_event_count=write_tool_event_count,
        provider_error_types=_provider_error_types(tool_events),
        cross_provider_fallback_detected=any(provider != "amap" for provider in observed_provider_names),
    )


def _trace_id(metadata: dict[str, Any], trace_id_override: str | None) -> str | None:
    if isinstance(trace_id_override, str) and trace_id_override:
        return trace_id_override
    demo = metadata.get("demo")
    if isinstance(demo, dict) and isinstance(demo.get("trace_id"), str):
        return demo["trace_id"]
    observability = metadata.get("observability")
    if isinstance(observability, dict) and isinstance(observability.get("trace_id"), str):
        return observability["trace_id"]
    return None


def _agent_roles(metadata: dict[str, Any]) -> list[str]:
    agents = metadata.get("agents")
    if not isinstance(agents, dict):
        return []
    results = agents.get("results")
    if not isinstance(results, list):
        return []

    roles: list[str] = []
    seen: set[str] = set()
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("role"), str):
            continue
        role = result["role"]
        if role in seen:
            continue
        roles.append(role)
        seen.add(role)
    return roles


def _workflow_timing_summary_from_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    workflow = metadata.get("workflow") if isinstance(metadata, dict) else None
    if not isinstance(workflow, dict):
        return None
    timing = workflow.get("timing")
    return _validated_workflow_timing_summary(timing)


def _run_error_summary(metadata: dict[str, Any]) -> RunErrorSummary | None:
    demo = metadata.get("demo")
    if isinstance(demo, dict) and isinstance(demo.get("initial_error"), dict):
        summary = _compact_error_summary(demo["initial_error"], source="demo.initial_error")
        if summary is not None:
            return summary

    observability = metadata.get("observability")
    if isinstance(observability, dict) and isinstance(observability.get("error"), dict):
        return _compact_error_summary(observability["error"], source="observability.error")
    return None


def _compact_error_summary(raw_error: dict[str, Any], *, source: str) -> RunErrorSummary | None:
    if not isinstance(raw_error, dict):
        return None

    error_type = _text_or_none(
        raw_error.get("error_type")
        or raw_error.get("code")
        or raw_error.get("exception_type")
        or raw_error.get("type")
    )
    message = _text_or_none(raw_error.get("message") or raw_error.get("reason"))

    details: dict[str, Any] = {}
    raw_details = raw_error.get("details")
    if isinstance(raw_details, dict):
        details.update(sanitize_trace_payload(deepcopy(raw_details)))
    elif raw_details is not None:
        details["details"] = sanitize_trace_payload(deepcopy(raw_details))

    for key, value in raw_error.items():
        if key in {"error_type", "code", "exception_type", "type", "message", "reason", "details"}:
            continue
        details[key] = sanitize_trace_payload(deepcopy(value))

    if error_type is None and message is None and not details:
        return None

    return RunErrorSummary(
        error_type=error_type or "unknown_error",
        message=message or "Unknown error.",
        source=source,
        details=details or None,
    )


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _validated_workflow_timing_summary(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    from backend.app.workflow.timing import WorkflowTimingSummary

    if isinstance(value, WorkflowTimingSummary):
        return value.model_dump(mode="json")
    return WorkflowTimingSummary.model_validate(value).model_dump(mode="json")


def _validated_preview_diagnostics(value: Any) -> PreviewDiagnostics | None:
    if value is None:
        return None
    try:
        return PreviewDiagnostics.model_validate(value)
    except ValidationError:
        return None


def _provider_error_types(tool_events: Sequence[Any]) -> list[str]:
    error_types: set[str] = set()
    for event in tool_events:
        if _tool_event_text(event, "provider") != "amap":
            continue
        raw_error = _tool_event_mapping(event, "error_json")
        if raw_error is None:
            continue
        sanitized_error = sanitize_trace_payload(deepcopy(raw_error))
        for key in ("error_type", "code", "exception_type", "type"):
            value = sanitized_error.get(key)
            if isinstance(value, str) and value:
                error_types.add(value)
                break
    return sorted(error_types)


def _tool_event_text(event: Any, key: str) -> str | None:
    value = _tool_event_value(event, key)
    return value if isinstance(value, str) and value else None


def _tool_event_mapping(event: Any, key: str) -> dict[str, Any] | None:
    value = _tool_event_value(event, key)
    return value if isinstance(value, dict) else None


def _tool_event_value(event: Any, key: str) -> Any:
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key, None)
