from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import re
from typing import Any
from uuid import UUID

from backend.app.feedback.errors import FeedbackWriterError
from backend.app.feedback.memory_candidates import extract_feedback_memory_candidates
from backend.app.feedback.schemas import (
    ExecutionFeedbackResult,
    FeedbackActionStatus,
    FeedbackActionSummary,
    FeedbackMemoryCandidateSummary,
)
from backend.app.models.runtime import AgentRun, Plan
from backend.app.repositories import AgentRunRepository, MemoryItemRepository, PlanRepository


class DeterministicFeedbackWriter:
    writer_version = "deterministic_feedback_writer_v1"
    _MESSAGE_RECIPIENT_LABELS = {
        "wife": "妻子",
        "self": "自己",
    }

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
        "completed": "安排已完成",
        "partially_completed": "部分安排已完成",
        "failed": "安排未完成",
        "skipped": "未执行安排",
    }
    _NEXT_STEPS = {
        "completed": [
            "按确认后的时间出发，出门前再看一眼天气和路况。",
        ],
        "partially_completed": [
            "先查看未完成操作，再决定重试或调整方案。",
        ],
        "failed": [
            "本次确认操作没有完成，重试前请先查看失败原因。",
        ],
        "skipped": [
            "当前没有可执行的确认操作，请选择并确认包含订座、取号或订票的方案。",
        ],
    }

    def __init__(
        self,
        plans: PlanRepository,
        runs: AgentRunRepository,
    ) -> None:
        self.plans = plans
        self.runs = runs
        self.memory = MemoryItemRepository(plans.session)

    def write_execution_feedback(
        self,
        run_id: UUID,
        plan_id: UUID,
    ) -> ExecutionFeedbackResult:
        plan = self._load_plan(plan_id)
        run = self._load_run(run_id)
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
        memory_candidate_summary = self._persist_memory_candidates(run, plan_json)
        result = ExecutionFeedbackResult(
            run_id=run_id,
            plan_id=plan_id,
            status=feedback_status,
            run_status=feedback_status,
            headline=headline,
            message=message,
            final_arrangement_message=self._build_final_arrangement_message(
                plan_json,
                feedback_status,
                completed_actions,
                failed_actions,
            ),
            completed_actions=completed_actions,
            failed_actions=failed_actions,
            next_steps=list(self._NEXT_STEPS[feedback_status]),
            writer_version=self.writer_version,
            memory_candidate_summary=memory_candidate_summary,
        )
        self._persist_feedback(plan, plan_json, execution, result)
        self._update_run_status(run_id, result.run_status)
        return result

    def _load_plan(self, plan_id: UUID) -> Plan:
        plan = self.plans.get_by_id(plan_id)
        if plan is None:
            raise FeedbackWriterError("Plan does not exist.")
        return plan

    def _load_run(self, run_id: UUID) -> AgentRun:
        run = self.runs.get_by_id(run_id)
        if run is None:
            raise FeedbackWriterError("Run does not exist.")
        return run

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
        evidence = draft.get("evidence")
        if isinstance(evidence, dict):
            selected_addon = evidence.get("selected_addon")
            if isinstance(selected_addon, dict):
                candidate_id = selected_addon.get("candidate_id")
                name = selected_addon.get("name")
                if isinstance(candidate_id, str) and candidate_id and isinstance(name, str) and name:
                    labels[candidate_id] = name
            post_confirmation_message = evidence.get("post_confirmation_message")
            if isinstance(post_confirmation_message, dict):
                recipient = self._text(post_confirmation_message.get("recipient"))
                recipient_label = self._text(post_confirmation_message.get("recipient_label"))
                if recipient and recipient_label:
                    labels[recipient] = recipient_label
        for recipient, label in self._MESSAGE_RECIPIENT_LABELS.items():
            labels.setdefault(recipient, label)
        return labels

    def _action_message(
        self,
        status: FeedbackActionStatus,
        tool_name: str,
        target_label: str,
    ) -> str:
        if status == "completed":
            return f"已为{target_label}完成{self._tool_label(tool_name)}。"
        if status == "already_completed":
            return f"{target_label}的{self._tool_label(tool_name)}此前已完成，本次没有创建重复操作。"
        if status == "blocked":
            return f"{target_label}的{self._tool_label(tool_name)}已被阻止。"
        if status == "rate_limited":
            return f"{target_label}的{self._tool_label(tool_name)}触发限流，暂未完成。"
        return f"未能为{target_label}完成{self._tool_label(tool_name)}。"

    def _tool_label(self, tool_name: str) -> str:
        labels = {
            "book_ticket": "订票",
            "reserve_restaurant": "订座",
            "join_queue": "排队取号",
            "order_addon": "加购点单",
            "send_message": "发送消息",
        }
        return labels.get(tool_name, tool_name)

    def _error_code(self, raw_action: dict[str, Any]) -> str | None:
        error_json = raw_action.get("error_json")
        if not isinstance(error_json, dict):
            return None
        code = error_json.get("code")
        return code if isinstance(code, str) and code else None

    def _build_final_arrangement_message(
        self,
        plan_json: dict[str, Any],
        feedback_status: str,
        completed_actions: list[FeedbackActionSummary],
        failed_actions: list[FeedbackActionSummary],
    ) -> str | None:
        if feedback_status == "skipped":
            return None

        draft = plan_json.get("draft")
        if not isinstance(draft, dict):
            return None

        activity = draft.get("activity") if isinstance(draft.get("activity"), dict) else {}
        dining = draft.get("dining") if isinstance(draft.get("dining"), dict) else {}
        activity_name = self._text(activity.get("name"))
        dining_name = self._text(dining.get("name"))
        if activity_name is None and dining_name is None:
            return None

        opening = {
            "completed": "搞定了，",
            "partially_completed": "先帮你安排了可完成的部分，",
            "failed": "这次还没安排成功，",
        }.get(feedback_status)
        if opening is None:
            return None

        parts: list[str] = [opening]
        departure = self._departure_clause(plan_json)
        if departure:
            parts.append(f"{departure}，")

        plan_parts: list[str] = []
        if activity_name:
            plan_parts.append(f"先去{activity_name}")
        if dining_name:
            plan_parts.append(f"{'，再到' if plan_parts else '到'}{dining_name}")
        if plan_parts:
            parts.append("".join(plan_parts))

        suffix = self._arrangement_suffix(feedback_status, completed_actions, failed_actions)
        if suffix:
            parts.append(f"；{suffix}")
        return "".join(parts)

    def _departure_clause(self, plan_json: dict[str, Any]) -> str | None:
        draft = plan_json.get("draft")
        if not isinstance(draft, dict):
            return None
        timeline = draft.get("timeline")
        if not isinstance(timeline, list):
            return None
        for item in timeline:
            if not isinstance(item, dict):
                continue
            start_label = self._text(item.get("start_label"))
            if not start_label:
                continue
            normalized = self._normalize_time_label(start_label)
            if normalized:
                return f"{normalized}出发"
        return None

    def _normalize_time_label(self, start_label: str) -> str | None:
        match = re.search(r"(?<!\d)(\d{1,2}):(\d{2})", start_label)
        if not match:
            return None
        hour = int(match.group(1))
        minute = int(match.group(2))
        if minute not in {0, 30}:
            return None
        period = "下午" if hour >= 12 else "上午"
        display_hour = hour if 1 <= hour <= 12 else hour - 12 if hour > 12 else 12
        if minute == 0:
            return f"{period} {display_hour} 点"
        return f"{period} {display_hour} 点半"

    def _arrangement_suffix(
        self,
        feedback_status: str,
        completed_actions: list[FeedbackActionSummary],
        failed_actions: list[FeedbackActionSummary],
    ) -> str | None:
        completed_tools = {action.tool_name for action in completed_actions}
        if feedback_status == "completed":
            if {"reserve_restaurant", "send_message"}.issubset(completed_tools):
                return "订座和后续消息都已安排好"
            if completed_actions:
                return f"{'、'.join(self._tool_label(action.tool_name) for action in completed_actions)}已处理完成"
            return "可以按这个安排直接出发"
        if feedback_status == "partially_completed":
            completed_labels = "、".join(self._tool_label(action.tool_name) for action in completed_actions)
            failed_labels = "、".join(self._tool_label(action.tool_name) for action in failed_actions)
            if completed_labels and failed_labels:
                return f"{completed_labels}已完成，{failed_labels}还需要你再确认或处理"
            if failed_labels:
                return f"{failed_labels}还需要你再确认或处理"
            return "剩余步骤还需要再跟进"
        if feedback_status == "failed":
            failed_labels = "、".join(self._tool_label(action.tool_name) for action in failed_actions)
            if failed_labels:
                return f"{failed_labels}还没有执行成功，建议先处理这些问题再重试"
            return "建议先检查失败原因后再重试"
        return None

    def _text(self, value: Any) -> str | None:
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        return None

    def _message(self, headline: str, completed_count: int, failed_count: int) -> str:
        return (
            f"{headline}：{completed_count}项操作已完成，"
            f"{failed_count}项需要处理。"
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
            "final_arrangement_message": result.final_arrangement_message,
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
            "memory_candidate_summary": (
                result.memory_candidate_summary.model_dump(mode="json")
                if result.memory_candidate_summary is not None
                else None
            ),
        }
        updated = self.plans.update_plan_json(plan.plan_id, updated_json)
        if updated is None:
            raise FeedbackWriterError("Plan disappeared during feedback persistence.")

    def _persist_memory_candidates(
        self,
        run: AgentRun,
        plan_json: dict[str, Any],
    ) -> FeedbackMemoryCandidateSummary:
        candidates = extract_feedback_memory_candidates(plan_json)
        if not candidates:
            return FeedbackMemoryCandidateSummary(generation_status="not_applicable")
        if run.user_id is None:
            return FeedbackMemoryCandidateSummary(generation_status="degraded")

        created_keys: list[str] = []
        updated_keys: list[str] = []
        skipped_keys: list[str] = []
        degraded = False

        for candidate in candidates:
            try:
                existing = self.memory.get_by_user_memory_key(
                    run.user_id,
                    candidate.memory_type,
                    candidate.key,
                )
                if existing is None:
                    self.memory.create(
                        user_id=run.user_id,
                        memory_type=candidate.memory_type,
                        key=candidate.key,
                        value_json=candidate.value_json,
                        text=candidate.text,
                        confidence=candidate.confidence,
                        source_run_id=run.run_id,
                        source_langsmith_trace_id=None,
                        expires_at=None,
                        status=candidate.status,
                    )
                    created_keys.append(candidate.key)
                    continue

                if existing.status != "candidate":
                    skipped_keys.append(candidate.key)
                    continue

                updated = self.memory.update(
                    existing.memory_id,
                    value_json=candidate.value_json,
                    text=candidate.text,
                    confidence=candidate.confidence,
                    source_run_id=run.run_id,
                    source_langsmith_trace_id=None,
                    expires_at=None,
                    status=candidate.status,
                )
                if updated is None:
                    degraded = True
                    continue
                updated_keys.append(candidate.key)
            except Exception:
                degraded = True

        return FeedbackMemoryCandidateSummary(
            generation_status="degraded" if degraded else "completed",
            created_keys=created_keys,
            updated_keys=updated_keys,
            skipped_keys=skipped_keys,
        )

    def _generated_at(self, execution: dict[str, Any]) -> str:
        finished_at = execution.get("finished_at")
        if isinstance(finished_at, str) and finished_at:
            return finished_at
        return datetime.now(UTC).isoformat()

    def _update_run_status(self, run_id: UUID, status: str) -> None:
        if self.runs.update_status(run_id, status) is None:
            raise FeedbackWriterError("Run disappeared during feedback persistence.")
