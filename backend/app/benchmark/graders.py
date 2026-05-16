from __future__ import annotations

import re
from typing import Any, Sequence

from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkScore
from backend.app.tool_gateway.registry import WRITE_TOOLS
from backend.app.workflow.state import V1_WORKFLOW_NODE_NAMES


_UNSAFE_FEEDBACK_PATTERN = re.compile(r"\b(action_id|tool_event_id|traceback|stack trace|debug)\b", re.IGNORECASE)
REQUIRED_WORKFLOW_NODES = V1_WORKFLOW_NODE_NAMES
REQUIRED_AGENT_ROLES = (
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
)


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


def grade_workflow_path(workflow_result: Any) -> BenchmarkScore:
    status = _value(workflow_result, "status")
    node_history = [str(node) for node in (_value(workflow_result, "node_history", []) or [])]
    missing = sorted(set(REQUIRED_WORKFLOW_NODES) - set(node_history))
    passed = status == "completed" and not missing
    reason = "Workflow completed through the required product path."
    if status != "completed":
        reason = f"Workflow status {status!r} did not match expected 'completed'."
    elif missing:
        reason = f"Missing required workflow nodes: {', '.join(missing)}"
    return BenchmarkScore(
        name="workflow_path",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "workflow_status": status,
            "required_node_names": list(REQUIRED_WORKFLOW_NODES),
            "node_history": node_history,
            "missing_node_names": missing,
        },
    )


def grade_agent_coverage(workflow_result: Any) -> BenchmarkScore:
    agent_results = _value(workflow_result, "agent_results", []) or []
    observed_roles = [
        str(role)
        for role in (_value(agent, "role") for agent in agent_results)
        if role
    ]
    missing = sorted(set(REQUIRED_AGENT_ROLES) - set(observed_roles))
    passed = not missing
    return BenchmarkScore(
        name="agent_coverage",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=(
            "All required bounded agent roles were present."
            if passed
            else f"Missing required agent roles: {', '.join(missing)}"
        ),
        details={
            "required_agent_roles": list(REQUIRED_AGENT_ROLES),
            "observed_agent_roles": observed_roles,
            "missing_agent_roles": missing,
        },
    )


def grade_execution_safety(case: BenchmarkCase, execution_result: Any) -> BenchmarkScore:
    status = _value(execution_result, "status")
    action_results = list(_value(execution_result, "action_results", []) or [])
    write_tools = [_value(action, "tool_name") for action in action_results]
    unsafe_tools = sorted(
        {
            str(tool_name or "")
            for tool_name in write_tools
            if tool_name not in WRITE_TOOLS
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
            "write_tools": write_tools,
        },
    )


def grade_feedback(case: BenchmarkCase, feedback_result: Any) -> BenchmarkScore:
    status = _value(feedback_result, "status")
    next_steps = _value(feedback_result, "next_steps", []) or []
    if not isinstance(next_steps, list):
        next_steps = [next_steps]
    text = " ".join(
        str(value or "")
        for value in (
            _value(feedback_result, "headline"),
            _value(feedback_result, "message"),
            " ".join(str(step or "") for step in next_steps),
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


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def combine_scores(scores: Sequence[BenchmarkScore]) -> tuple[str, float, list[str]]:
    if not scores:
        return "failed", 0.0, ["No benchmark scores were produced."]
    failed_reasons = [score.reason for score in scores if not score.passed]
    status = "passed" if not failed_reasons else "failed"
    overall = round(sum(score.score for score in scores) / len(scores), 4)
    return status, overall, failed_reasons
