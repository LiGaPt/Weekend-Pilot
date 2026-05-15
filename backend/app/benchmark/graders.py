from __future__ import annotations

import re
from typing import Any, Sequence

from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkScore
from backend.app.tool_gateway.registry import WRITE_TOOLS


_UNSAFE_FEEDBACK_PATTERN = re.compile(r"\b(action_id|tool_event_id|traceback|stack trace|debug)\b", re.IGNORECASE)


def grade_trajectory(case: BenchmarkCase, tool_events: Sequence[Any]) -> BenchmarkScore:
    observed = [str(getattr(event, "tool_name", "")) for event in tool_events]
    missing = sorted(set(case.expected.required_tool_names) - set(observed))
    enough_events = len(observed) >= case.expected.min_tool_event_count
    passed = not missing and enough_events
    reason = "Required tools were called."
    if missing:
        reason = f"Missing required tools: {', '.join(missing)}"
    elif not enough_events:
        reason = (
            f"Tool event count {len(observed)} is below required minimum "
            f"{case.expected.min_tool_event_count}."
        )
    return BenchmarkScore(
        name="trajectory",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "required_tool_names": list(case.expected.required_tool_names),
            "observed_tool_names": observed,
            "tool_event_count": len(observed),
        },
    )


def grade_plan_quality(selected_plan: Any) -> BenchmarkScore:
    plan_json = getattr(selected_plan, "plan_json", None)
    selected = bool(getattr(selected_plan, "selected", False))
    safe_to_present = isinstance(plan_json, dict) and plan_json.get("safe_to_present") is True
    passed = selected_plan is not None and selected and safe_to_present
    return BenchmarkScore(
        name="plan_quality",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason="A selected safe reviewed plan exists." if passed else "No selected safe reviewed plan exists.",
        details={
            "selected": selected,
            "safe_to_present": safe_to_present,
            "plan_status": getattr(selected_plan, "status", None),
        },
    )


def grade_execution_safety(case: BenchmarkCase, execution_result: Any) -> BenchmarkScore:
    status = getattr(execution_result, "status", None)
    action_results = list(getattr(execution_result, "action_results", []) or [])
    unsafe_tools = sorted(
        {
            str(getattr(action, "tool_name", ""))
            for action in action_results
            if getattr(action, "tool_name", None) not in WRITE_TOOLS
        }
    )
    enough_actions = len(action_results) >= case.expected.min_action_count
    passed = status == case.expected.expected_execution_status and not unsafe_tools and enough_actions
    reason = "Execution succeeded with registered write tools."
    if status != case.expected.expected_execution_status:
        reason = f"Execution status {status!r} did not match expected {case.expected.expected_execution_status!r}."
    elif unsafe_tools:
        reason = f"Execution used unregistered write tools: {', '.join(unsafe_tools)}"
    elif not enough_actions:
        reason = (
            f"Action count {len(action_results)} is below required minimum "
            f"{case.expected.min_action_count}."
        )
    return BenchmarkScore(
        name="execution_safety",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "execution_status": status,
            "action_count": len(action_results),
            "write_tools": [getattr(action, "tool_name", None) for action in action_results],
        },
    )


def grade_feedback(case: BenchmarkCase, feedback_result: Any) -> BenchmarkScore:
    status = getattr(feedback_result, "status", None)
    text = " ".join(
        str(value or "")
        for value in (
            getattr(feedback_result, "headline", None),
            getattr(feedback_result, "message", None),
            " ".join(getattr(feedback_result, "next_steps", []) or []),
        )
    )
    user_safe = _UNSAFE_FEEDBACK_PATTERN.search(text) is None
    passed = status == case.expected.expected_feedback_status and user_safe
    reason = "Feedback completed and is user-safe."
    if status != case.expected.expected_feedback_status:
        reason = f"Feedback status {status!r} did not match expected {case.expected.expected_feedback_status!r}."
    elif not user_safe:
        reason = "Feedback contains raw IDs or debug wording."
    return BenchmarkScore(
        name="feedback",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={"feedback_status": status, "user_safe": user_safe},
    )


def combine_scores(scores: Sequence[BenchmarkScore]) -> tuple[str, float, list[str]]:
    if not scores:
        return "failed", 0.0, ["No benchmark scores were produced."]
    failed_reasons = [score.reason for score in scores if not score.passed]
    status = "passed" if not failed_reasons else "failed"
    overall = round(sum(score.score for score in scores) / len(scores), 4)
    return status, overall, failed_reasons
