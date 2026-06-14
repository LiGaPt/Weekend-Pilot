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


def grade_robustness_expectation(
    case: BenchmarkCase,
    selected_plan: Any,
    tool_events: Sequence[Any],
) -> BenchmarkScore:
    expectation = case.expected.robustness
    if expectation is None:
        raise ValueError("Robustness grading requires case.expected.robustness.")

    plan_json = getattr(selected_plan, "plan_json", None)
    selected_activity_id = _selected_candidate_id(plan_json, "activity")
    selected_dining_id = _selected_candidate_id(plan_json, "dining")
    activity_results = _search_results_for_category(tool_events, "activity")
    dining_results = _search_results_for_category(tool_events, "dining")
    unavailable_candidate_ids = _unavailable_candidate_ids(tool_events)
    failed_route_pair_count = sum(
        1
        for event in tool_events
        if _value(event, "tool_name") == "check_route"
        and _value(event, "status") not in {"succeeded", "cached"}
    )

    failures: list[str] = []
    if selected_activity_id != expectation.expected_selected_activity_id:
        failures.append(
            "Observed selected activity "
            f"{selected_activity_id!r} did not match expected {expectation.expected_selected_activity_id!r}."
        )
    if selected_dining_id != expectation.expected_selected_dining_id:
        failures.append(
            "Observed selected dining "
            f"{selected_dining_id!r} did not match expected {expectation.expected_selected_dining_id!r}."
        )
    if len(activity_results) < expectation.minimum_activity_search_results:
        failures.append(
            "Observed activity search results "
            f"{len(activity_results)} below required minimum {expectation.minimum_activity_search_results}."
        )
    if len(dining_results) < expectation.minimum_dining_search_results:
        failures.append(
            "Observed dining search results "
            f"{len(dining_results)} below required minimum {expectation.minimum_dining_search_results}."
        )
    if activity_results[: len(expectation.expected_activity_search_prefix)] != expectation.expected_activity_search_prefix:
        failures.append("Observed activity search prefix did not match expected deterministic prefix.")
    if dining_results[: len(expectation.expected_dining_search_prefix)] != expectation.expected_dining_search_prefix:
        failures.append("Observed dining search prefix did not match expected deterministic prefix.")
    missing_unavailable_ids = [
        candidate_id
        for candidate_id in expectation.required_unavailable_candidate_ids
        if candidate_id not in unavailable_candidate_ids
    ]
    if missing_unavailable_ids:
        failures.append(
            f"Missing required unavailable candidate IDs: {', '.join(missing_unavailable_ids)}"
        )
    if failed_route_pair_count < expectation.minimum_failed_route_pairs:
        failures.append(
            "Observed failed route pair count "
            f"{failed_route_pair_count} below required minimum {expectation.minimum_failed_route_pairs}."
        )

    passed = not failures
    reason = (
        "Selected pair, noisy search ordering, unavailable candidates, and route fallback evidence matched expectation."
    )
    if failures:
        reason = failures[0]
    return BenchmarkScore(
        name="robustness",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "selected_activity_id": selected_activity_id,
            "selected_dining_id": selected_dining_id,
            "observed_activity_search_results": activity_results,
            "observed_dining_search_results": dining_results,
            "observed_unavailable_candidate_ids": unavailable_candidate_ids,
            "failed_route_pair_count": failed_route_pair_count,
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


def grade_conversation_path(
    case: BenchmarkCase,
    conversation_trace: Sequence[Any],
    conversation_turn_types: Sequence[str],
) -> BenchmarkScore:
    expectation = case.expected.conversation
    if expectation is None:
        raise ValueError("Conversation-path grading requires case.expected.conversation.")

    expected_steps = list(expectation.steps)
    observed_steps = list(conversation_trace)
    expected_step_signatures = [
        {
            "mode": step.mode,
            "status": step.expected_status,
            "version_label": step.expected_version_label,
        }
        for step in expected_steps
    ]
    observed_step_signatures = [
        {
            "mode": str(_value(step, "mode")),
            "status": str(_value(step, "status")),
            "version_label": _value(step, "version_label"),
        }
        for step in observed_steps
    ]

    failures: list[str] = []
    if len(observed_steps) != len(expected_steps):
        failures.append(
            f"Observed conversation step count {len(observed_steps)} did not match expected {len(expected_steps)}."
        )
    else:
        for index, (expected_step, observed_step) in enumerate(zip(expected_steps, observed_steps), start=1):
            observed_mode = str(_value(observed_step, "mode"))
            observed_status = str(_value(observed_step, "status"))
            observed_version_label = _value(observed_step, "version_label")
            if observed_mode != expected_step.mode:
                failures.append(
                    f"Conversation step {index} mode {observed_mode!r} did not match expected {expected_step.mode!r}."
                )
                break
            if observed_status != expected_step.expected_status:
                failures.append(
                    "Conversation step "
                    f"{index} status {observed_status!r} did not match expected {expected_step.expected_status!r}."
                )
                break
            if (
                expected_step.expected_version_label is not None
                and observed_version_label != expected_step.expected_version_label
            ):
                failures.append(
                    "Conversation step "
                    f"{index} version label {observed_version_label!r} did not match expected "
                    f"{expected_step.expected_version_label!r}."
                )
                break

    observed_turn_types = [str(turn_type) for turn_type in conversation_turn_types]
    missing_turn_types = [
        turn_type for turn_type in expectation.required_turn_types if turn_type not in observed_turn_types
    ]
    if missing_turn_types:
        failures.append(f"Missing required conversation turn types: {', '.join(missing_turn_types)}")

    passed = not failures
    reason = "Conversation path matched expected statuses, versions, and turn types."
    if failures:
        reason = failures[0]
    return BenchmarkScore(
        name="conversation_path",
        score=1.0 if passed else 0.0,
        passed=passed,
        reason=reason,
        details={
            "expected_step_signatures": expected_step_signatures,
            "observed_step_signatures": observed_step_signatures,
            "required_turn_types": list(expectation.required_turn_types),
            "observed_turn_types": observed_turn_types,
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


def grade_memory_governance(
    case: BenchmarkCase,
    run_metadata: Any,
    feedback_memory_candidate_summary: Any | None = None,
) -> BenchmarkScore:
    expectation = case.expected.memory_governance
    if expectation is None:
        raise ValueError("Memory-governance grading requires case.expected.memory_governance.")

    workflow_metadata = _value(run_metadata, "workflow", {}) or {}
    memory_policy = _value(workflow_metadata, "memory_policy", {}) or {}
    observed_policy_version = _value(memory_policy, "policy_version")

    raw_dimension_outcomes = _value(memory_policy, "dimension_outcomes", []) or []
    raw_memory_decisions = _value(memory_policy, "memory_decisions", []) or []
    raw_decision_log = _value(memory_policy, "decision_log", []) or []
    raw_policy_summary = _value(memory_policy, "policy_summary", {}) or {}
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
    observed_decision_log = {
        str(_value(entry, "key")): {
            "decision": _value(entry, "decision"),
            "status": _value(entry, "status"),
            "reason": _value(entry, "reason"),
            "influence_level": _value(entry, "influence_level"),
        }
        for entry in raw_decision_log
        if _value(entry, "key")
    }
    observed_policy_summary = {
        str(key): int(value)
        for key, value in raw_policy_summary.items()
        if key != "policy_version" and isinstance(value, int)
    }
    observed_feedback_memory_candidate_summary = _safe_feedback_memory_candidate_summary(
        feedback_memory_candidate_summary
    )

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
    for decision in expectation.expected_decision_log:
        observed_entry = observed_decision_log.get(decision.memory_key)
        if observed_entry is None:
            failures.append(f"Decision log for {decision.memory_key!r} was missing.")
            continue
        for field_name, expected_value in (
            ("decision", decision.expected_decision),
            ("status", decision.expected_status),
            ("reason", decision.expected_reason),
            ("influence_level", decision.expected_influence_level),
        ):
            observed_value = observed_entry.get(field_name)
            if observed_value != expected_value:
                failures.append(
                    f"Decision log {field_name} for {decision.memory_key!r} was {observed_value!r}, expected {expected_value!r}."
                )
    for memory_key in expectation.expected_absent_memory_keys:
        if memory_key in observed_memory_outcomes:
            failures.append(f"Expected {memory_key!r} to be absent from memory_decisions.")
        if memory_key in observed_decision_log:
            failures.append(f"Expected {memory_key!r} to be absent from decision_log.")
    if expectation.expected_policy_summary is not None:
        for key, expected_value in expectation.expected_policy_summary.items():
            observed_value = observed_policy_summary.get(key)
            if observed_value != expected_value:
                failures.append(
                    f"Policy summary {key!r} was {observed_value!r}, expected {expected_value!r}."
                )
    if expectation.expected_feedback_memory_candidate_summary is not None:
        expected_feedback_summary = expectation.expected_feedback_memory_candidate_summary.model_dump(mode="json")
        if observed_feedback_memory_candidate_summary != expected_feedback_summary:
            failures.append(
                "Observed feedback memory candidate summary did not match expected safe summary."
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
            "expected_decision_log": {
                decision.memory_key: {
                    "decision": decision.expected_decision,
                    "status": decision.expected_status,
                    "reason": decision.expected_reason,
                    "influence_level": decision.expected_influence_level,
                }
                for decision in expectation.expected_decision_log
            },
            "observed_decision_log": observed_decision_log,
            "expected_absent_memory_keys": list(expectation.expected_absent_memory_keys),
            "expected_policy_summary": dict(expectation.expected_policy_summary or {}),
            "observed_policy_summary": observed_policy_summary,
            "expected_feedback_memory_candidate_summary": (
                expectation.expected_feedback_memory_candidate_summary.model_dump(mode="json")
                if expectation.expected_feedback_memory_candidate_summary is not None
                else None
            ),
            "observed_feedback_memory_candidate_summary": observed_feedback_memory_candidate_summary,
        },
    )


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _selected_candidate_id(plan_json: Any, section: str) -> str | None:
    draft = _value(plan_json, "draft")
    candidate = _value(draft, section)
    candidate_id = _value(candidate, "candidate_id")
    return candidate_id if isinstance(candidate_id, str) and candidate_id else None


def _search_results_for_category(tool_events: Sequence[Any], category: str) -> list[str]:
    for event in tool_events:
        if _value(event, "tool_name") != "search_poi":
            continue
        payload = _value(_value(event, "request_json", {}), "payload", {})
        if _value(payload, "category") != category:
            continue
        results = _value(_value(event, "response_json", {}), "results", [])
        if not isinstance(results, list):
            return []
        return [
            poi_id
            for poi_id in (_value(item, "poi_id") for item in results)
            if isinstance(poi_id, str) and poi_id
        ]
    return []


def _unavailable_candidate_ids(tool_events: Sequence[Any]) -> list[str]:
    observed: list[str] = []
    for event in tool_events:
        tool_name = _value(event, "tool_name")
        request_payload = _value(_value(event, "request_json", {}), "payload", {})
        response_json = _value(event, "response_json", {})
        candidate_id: str | None = None
        unavailable = False

        if tool_name == "check_ticket_availability":
            candidate_id = _first_text(
                _value(request_payload, "poi_id"),
                _value(request_payload, "candidate_id"),
            )
            ticket = _value(response_json, "ticket_availability", {})
            unavailable = _value(ticket, "available") is False
        elif tool_name == "check_table_availability":
            candidate_id = _first_text(
                _value(request_payload, "restaurant_id"),
                _value(request_payload, "candidate_id"),
            )
            table = _value(response_json, "table_availability", {})
            unavailable = _value(table, "available") is False
        elif tool_name == "check_queue":
            queue = _value(response_json, "queue", {})
            candidate_id = _first_text(
                _value(request_payload, "poi_id"),
                _value(queue, "poi_id"),
                _value(request_payload, "candidate_id"),
            )
            queue_status = _value(queue, "status")
            unavailable = isinstance(queue_status, str) and queue_status != "open"

        if unavailable and candidate_id and candidate_id not in observed:
            observed.append(candidate_id)
    return observed


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _safe_feedback_memory_candidate_summary(summary: Any | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    allowed_keys = {
        "schema_version",
        "generation_status",
        "created_keys",
        "updated_keys",
        "skipped_keys",
    }
    if isinstance(summary, dict):
        payload = summary
    elif hasattr(summary, "model_dump"):
        payload = summary.model_dump(mode="json")
    else:
        return None
    return {key: payload.get(key) for key in allowed_keys}


def combine_scores(scores: Sequence[BenchmarkScore]) -> tuple[str, float, list[str]]:
    if not scores:
        return "failed", 0.0, ["No benchmark scores were produced."]
    failed_reasons = [score.reason for score in scores if not score.passed]
    status = "passed" if not failed_reasons else "failed"
    overall = round(sum(score.score for score in scores) / len(scores), 4)
    return status, overall, failed_reasons
