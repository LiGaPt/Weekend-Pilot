from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from backend.app.feedback.errors import FeedbackWriterError
from backend.app.feedback.schemas import (
    ExecutionFeedbackResult,
    FeedbackActionStatus,
    FeedbackActionSummary,
)
from backend.app.models.runtime import Plan
from backend.app.repositories import AgentRunRepository, PlanRepository


class DeterministicFeedbackWriter:
    writer_version = "deterministic_feedback_writer_v1"

    _STATUS_MAP = {
        "succeeded": "completed",
        "partially_succeeded": "partially_completed",
        "failed": "failed",
        "skipped": "skipped",
    }
    _ACTION_STATUS_MAP: dict[str, FeedbackActionStatus] = {
        "succeeded": "completed",
        "idempotent_replay": "already_completed",
        "failed": "failed",
        "blocked": "blocked",
        "rate_limited": "rate_limited",
    }
    _COMPLETED_ACTION_STATUSES = {"completed", "already_completed"}
    _HEADLINES = {
        "completed": "Plan completed.",
        "partially_completed": "Plan partially completed.",
        "failed": "Plan failed.",
        "skipped": "Plan skipped.",
    }
    _NEXT_STEPS = {
        "completed": [],
        "partially_completed": [
            "Review the actions that need attention before retrying or changing the plan.",
        ],
        "failed": [
            "No confirmed actions completed. Review the failed actions before retrying.",
        ],
        "skipped": [
            "No confirmed actions were available to execute. Select or confirm a plan with executable actions.",
        ],
    }

    def __init__(
        self,
        plans: PlanRepository,
        runs: AgentRunRepository,
    ) -> None:
        self.plans = plans
        self.runs = runs

    def write_execution_feedback(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> ExecutionFeedbackResult:
        plan = self._load_plan(plan_id)
        self._load_run(run_id)
        if plan.run_id != run_id:
            raise FeedbackWriterError("Plan does not belong to the requested run.")
        if not plan.selected:
            raise FeedbackWriterError("Plan must be selected before writing feedback.")

        plan_json = self._reviewed_plan_json(plan)
        execution = self._execution_metadata(plan_json)
        feedback_status = self._feedback_status(execution)
        summaries = self._action_summaries(plan_json, execution)
        completed_actions = [
            summary for summary in summaries if summary.status in self._COMPLETED_ACTION_STATUSES
        ]
        failed_actions = [
            summary for summary in summaries if summary.status not in self._COMPLETED_ACTION_STATUSES
        ]
        headline = self._HEADLINES[feedback_status]
        message = self._message(headline, len(completed_actions), len(failed_actions))
        result = ExecutionFeedbackResult(
            run_id=run_id,
            plan_id=plan_id,
            status=feedback_status,
            run_status=feedback_status,
            headline=headline,
            message=message,
            completed_actions=completed_actions,
            failed_actions=failed_actions,
            next_steps=list(self._NEXT_STEPS[feedback_status]),
            writer_version=self.writer_version,
        )
        self._persist_feedback(plan, plan_json, execution, result)
        self._update_run_status(run_id, result.run_status)
        return result

    def _load_plan(self, plan_id: UUID) -> Plan:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise FeedbackWriterError("Plan does not exist.")
        return plan

    def _load_run(self, run_id: UUID) -> None:
        if self.runs.get_by_id(run_id) is None:
            raise FeedbackWriterError("Run does not exist.")

    def _reviewed_plan_json(self, plan: Plan) -> dict[str, Any]:
        plan_json = plan.plan_json
        if not isinstance(plan_json, dict):
            raise FeedbackWriterError("Plan JSON is malformed.")
        if plan_json.get("schema_version") != "reviewed_plan_v1":
            raise FeedbackWriterError("Plan JSON is not a reviewed plan.")
        return plan_json

    def _execution_metadata(self, plan_json: dict[str, Any]) -> dict[str, Any]:
        execution = plan_json.get("execution")
        if not isinstance(execution, dict):
            raise FeedbackWriterError("Plan is missing execution metadata.")
        if execution.get("schema_version") != "execution_workflow_v1":
            raise FeedbackWriterError("Execution metadata schema is unsupported.")
        if execution.get("status") not in self._STATUS_MAP:
            raise FeedbackWriterError("Execution status is unsupported.")
        action_results = execution.get("action_results")
        if not isinstance(action_results, list):
            raise FeedbackWriterError("Execution action results are malformed.")
        return execution

    def _feedback_status(self, execution: dict[str, Any]) -> str:
        status = execution.get("status")
        mapped = self._STATUS_MAP.get(status)
        if mapped is None:
            raise FeedbackWriterError("Execution status is unsupported.")
        return mapped

    def _action_summaries(
        self,
        plan_json: dict[str, Any],
        execution: dict[str, Any],
    ) -> list[FeedbackActionSummary]:
        labels = self._target_labels(plan_json)
        summaries = []
        for raw_action in sorted(
            execution["action_results"],
            key=lambda item: item.get("execution_order") if isinstance(item, dict) else 0,
        ):
            if not isinstance(raw_action, dict):
                raise FeedbackWriterError("Execution action result is malformed.")
            summaries.append(self._action_summary(raw_action, labels))
        return summaries

    def _action_summary(
        self,
        raw_action: dict[str, Any],
        labels: dict[str, str],
    ) -> FeedbackActionSummary:
        action_ref = self._required_string(raw_action, "action_ref")
        execution_order = raw_action.get("execution_order")
        if not isinstance(execution_order, int) or execution_order <= 0:
            raise FeedbackWriterError("Execution action has invalid execution_order.")
        tool_name = self._required_string(raw_action, "tool_name")
        target_id = self._required_string(raw_action, "target_id")
        raw_status = self._required_string(raw_action, "status")
        status = self._ACTION_STATUS_MAP.get(raw_status)
        if status is None:
            raise FeedbackWriterError("Execution action status is unsupported.")

        target_label = labels.get(target_id, target_id)
        return FeedbackActionSummary(
            action_ref=action_ref,
            execution_order=execution_order,
            tool_name=tool_name,
            target_id=target_id,
            target_label=target_label,
            status=status,
            message=self._action_message(status, tool_name, target_label),
            error_code=self._error_code(raw_action),
        )

    def _required_string(self, value: dict[str, Any], key: str) -> str:
        item = value.get(key)
        if not isinstance(item, str) or not item:
            raise FeedbackWriterError(f"Execution action is missing {key}.")
        return item

    def _target_labels(self, plan_json: dict[str, Any]) -> dict[str, str]:
        draft = plan_json.get("draft")
        if not isinstance(draft, dict):
            return {}

        labels = {}
        for key in ("activity", "dining"):
            candidate = draft.get(key)
            if not isinstance(candidate, dict):
                continue
            candidate_id = candidate.get("candidate_id")
            name = candidate.get("name")
            if isinstance(candidate_id, str) and candidate_id and isinstance(name, str) and name:
                labels[candidate_id] = name
        return labels

    def _action_message(
        self,
        status: FeedbackActionStatus,
        tool_name: str,
        target_label: str,
    ) -> str:
        if status == "completed":
            return f"Completed {tool_name} for {target_label}."
        if status == "already_completed":
            return f"Already completed {tool_name} for {target_label}; no duplicate action was created."
        if status == "blocked":
            return f"Blocked {tool_name} for {target_label}."
        if status == "rate_limited":
            return f"Rate limited while completing {tool_name} for {target_label}."
        return f"Could not complete {tool_name} for {target_label}."

    def _error_code(self, raw_action: dict[str, Any]) -> str | None:
        error_json = raw_action.get("error_json")
        if not isinstance(error_json, dict):
            return None
        code = error_json.get("code")
        return code if isinstance(code, str) and code else None

    def _message(self, headline: str, completed_count: int, failed_count: int) -> str:
        return (
            f"{headline} {completed_count} actions completed and "
            f"{failed_count} actions need attention."
        )

    def _persist_feedback(
        self,
        plan: Plan,
        plan_json: dict[str, Any],
        execution: dict[str, Any],
        result: ExecutionFeedbackResult,
    ) -> None:
        updated_json = deepcopy(plan_json)
        updated_json["feedback"] = {
            "schema_version": "execution_feedback_v1",
            "writer_version": self.writer_version,
            "status": result.status,
            "run_status": result.run_status,
            "headline": result.headline,
            "message": result.message,
            "completed_actions": [
                action.model_dump(mode="json")
                for action in result.completed_actions
            ],
            "failed_actions": [
                action.model_dump(mode="json")
                for action in result.failed_actions
            ],
            "next_steps": list(result.next_steps),
            "generated_at": self._generated_at(execution),
        }
        updated = self.plans.update_plan_json(plan.plan_id, updated_json)
        if updated is None:
            raise FeedbackWriterError("Plan disappeared during feedback persistence.")

    def _generated_at(self, execution: dict[str, Any]) -> str:
        finished_at = execution.get("finished_at")
        if isinstance(finished_at, str) and finished_at:
            return finished_at
        return datetime.now(UTC).isoformat()

    def _update_run_status(self, run_id: UUID, status: str) -> None:
        if self.runs.update_status(run_id, status) is None:
            raise FeedbackWriterError("Run disappeared during feedback persistence.")
