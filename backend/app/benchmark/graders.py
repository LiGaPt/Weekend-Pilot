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


def grade_workflow_path(workflow_result: Any, case: BenchmarkCase | None = None) -> BenchmarkScore:
    expected_status = case.expected.expected_workflow_status if case is not None else "completed"
    expected_error_type = case.expected.expected_error_type if case is not None else None
    status = _value(workflow_result, "status")
    node_history = [str(node) for node in (_value(workflow_result, "node_history", []) or [])]
    error_json = _value(workflow_result, "error_json")
    observed_error_type = error_json.get("error_type") if isinstance(error_json, dict) else None
    missing = sorted(set(REQUIRED_WORKFLOW_NODES) - set(node_history)) if expected_status == "completed" else []
    error_matches = expected_error_type is None or observed_error_type == expected_error_type
    passed = status == expected_status and not missing and error_matches
    reason = "Workflow completed through the required product path."
    if expected_status != "completed":
        reason = "Workflow reached the expected failure path."
    if status != expected_status:
        reason = f"Workflow status {status!r} did not match expected {expected_status!r}."
    elif expected_error_type is not None and observed_error_type != expected_error_type:
        reason = f"Workflow error type {observed_error_type!r} did not match expected {expected_error_type!r}."
    elif missing:
        reason = f"Missing required workflow nodes: {', '.join(missing)}"
    return BenchmarkScore(
        name="workflow_path",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "workflow_status": status,
            "expected_workflow_status": expected_status,
            "workflow_error_type": observed_error_type,
            "expected_error_type": expected_error_type,
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
    if case.expected.expected_execution_status is None:
        execution_absent = status is None and not action_results
        passed = execution_absent and not unsafe_tools and enough_actions
        reason = "No execution was recorded, as expected."
        if not execution_absent:
            reason = "Execution metadata was present when no execution was expected."
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
                "expected_execution_status": case.expected.expected_execution_status,
                "action_count": len(action_results),
                "write_tools": write_tools,
            },
        )

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
            "expected_execution_status": case.expected.expected_execution_status,
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
    if case.expected.expected_feedback_status is None:
        feedback_absent = status is None and not text.strip()
        passed = feedback_absent and user_safe
        reason = "No feedback was recorded, as expected."
        if not feedback_absent:
            reason = "Feedback metadata was present when no feedback was expected."
        elif not user_safe:
            reason = "Feedback contains raw IDs or debug wording."
        return BenchmarkScore(
            name="feedback",
            score=1.0 if passed else 0.0,
            passed=passed,
            reason=reason,
            details={
                "feedback_status": status,
                "expected_feedback_status": case.expected.expected_feedback_status,
                "user_safe": user_safe,
            },
        )

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
        details={
            "feedback_status": status,
            "expected_feedback_status": case.expected.expected_feedback_status,
            "user_safe": user_safe,
        },
    )


def grade_failure_injection(case: BenchmarkCase, tool_events: Sequence[Any]) -> BenchmarkScore:
    injected_events = [
        event
        for event in tool_events
        if isinstance(_value(event, "error_json"), dict)
        and _value(event, "error_json").get("error_type")
        in {"failure_injected", "failure_injected_response"}
    ]
    expected_minimum = case.expected.min_injected_failure_count
    passed = len(injected_events) >= expected_minimum
    reason = "Injected failure count met expectation."
    if not passed:
        reason = (
            f"Injected failure count {len(injected_events)} is below required minimum "
            f"{expected_minimum}."
        )
    return BenchmarkScore(
        name="failure_injection",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "expected_min_injected_failure_count": expected_minimum,
            "injected_failure_count": len(injected_events),
            "injected_tool_names": [str(_value(event, "tool_name", "")) for event in injected_events],
        },
    )


def grade_recovery_expectation(case: BenchmarkCase, run_metadata: Any) -> BenchmarkScore:
    expected_action = case.expected.expected_recovery_action
    attempts = []
    workflow_metadata = _value(run_metadata, "workflow", {}) or {}
    recovery_metadata = _value(workflow_metadata, "recovery", {}) or {}
    raw_attempts = _value(recovery_metadata, "attempts", []) or []
    if isinstance(raw_attempts, list):
        attempts = raw_attempts

    observed_actions = [
        str(action)
        for action in (_value(attempt, "recovery_action") for attempt in attempts)
        if action
    ]
    observed_statuses = [
        str(status)
        for status in (_value(attempt, "status") for attempt in attempts)
        if status
    ]
    passed = expected_action is None or expected_action in observed_actions
    reason = "Recovery action matched expectation."
    if not passed:
        reason = f"Recovery action {expected_action!r} was not observed."
    return BenchmarkScore(
        name="recovery_expectation",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "expected_recovery_action": expected_action,
            "observed_recovery_actions": observed_actions,
            "observed_recovery_statuses": observed_statuses,
        },
    )


def grade_memory_governance(case: BenchmarkCase, run_metadata: Any) -> BenchmarkScore:
    expectation = case.expected.memory_governance
    if expectation is None:
        raise ValueError("Memory-governance grading requires case.expected.memory_governance.")

    workflow_metadata = _value(run_metadata, "workflow", {}) or {}
    memory_policy = _value(workflow_metadata, "memory_policy", {}) or {}
    observed_policy_version = _value(memory_policy, "policy_version")

    raw_dimension_outcomes = _value(memory_policy, "dimension_outcomes", []) or []
    raw_memory_decisions = _value(memory_policy, "memory_decisions", []) or []
    observed_dimension_sources = {
        str(_value(outcome, "dimension")): str(_value(outcome, "winner_source"))
        for outcome in raw_dimension_outcomes
        if _value(outcome, "dimension") and _value(outcome, "winner_source")
    }
    observed_dimension_tiers = {
        str(_value(outcome, "dimension")): str(_value(outcome, "winner_tier"))
        for outcome in raw_dimension_outcomes
        if _value(outcome, "dimension") and _value(outcome, "winner_tier") is not None
    }
    observed_memory_outcomes = {
        str(_value(decision, "memory_key")): str(_value(decision, "outcome"))
        for decision in raw_memory_decisions
        if _value(decision, "memory_key") and _value(decision, "outcome")
    }

    failures: list[str] = []
    if observed_policy_version != expectation.expected_policy_version:
        failures.append(
            f"Policy version {observed_policy_version!r} did not match expected {expectation.expected_policy_version!r}."
        )
    for dimension, expected_source in expectation.expected_dimension_sources.items():
        observed_source = observed_dimension_sources.get(dimension)
        if observed_source != expected_source:
            failures.append(
                f"Dimension source for {dimension!r} was {observed_source!r}, expected {expected_source!r}."
            )
    for dimension, expected_tier in expectation.expected_dimension_tiers.items():
        observed_tier = observed_dimension_tiers.get(dimension)
        if observed_tier != expected_tier:
            failures.append(
                f"Dimension tier for {dimension!r} was {observed_tier!r}, expected {expected_tier!r}."
            )
    for decision in expectation.expected_memory_outcomes:
        observed_outcome = observed_memory_outcomes.get(decision.memory_key)
        if observed_outcome != decision.expected_outcome:
            failures.append(
                f"Memory outcome for {decision.memory_key!r} was {observed_outcome!r}, expected {decision.expected_outcome!r}."
            )

    passed = not failures
    reason = "Memory governance summary matched expected policy decisions."
    if failures:
        reason = failures[0]
    return BenchmarkScore(
        name="memory_governance",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "expected_policy_version": expectation.expected_policy_version,
            "observed_policy_version": observed_policy_version,
            "expected_dimension_sources": dict(expectation.expected_dimension_sources),
            "observed_dimension_sources": observed_dimension_sources,
            "expected_dimension_tiers": dict(expectation.expected_dimension_tiers),
            "observed_dimension_tiers": observed_dimension_tiers,
            "expected_memory_outcomes": {
                decision.memory_key: decision.expected_outcome
                for decision in expectation.expected_memory_outcomes
            },
            "observed_memory_outcomes": observed_memory_outcomes,
        },
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
