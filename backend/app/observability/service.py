from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.runtime import ActionLedger, AgentRun, Plan, ToolEvent
from backend.app.observability.redaction import sanitize_trace_payload
from backend.app.planning.memory_query_policy import MemoryPolicyAuditSummary
from backend.app.observability.schemas import (
    InternalActionLedgerSummary,
    InternalBenchmarkArtifactSummary,
    InternalBenchmarkScoreSummary,
    InternalStructuredRunSummary,
    InternalBenchmarkTaxonomySummary,
    InternalRecoveryAttemptSummary,
    InternalRecoveryPathSummary,
    InternalRecoveryReplaySourceSummary,
    InternalObservabilityRunSummary,
    InternalObservabilitySummary,
    InternalRunSummaryLatestToolEvent,
    InternalRunSummaryRecoveryDigest,
    InternalRunSummaryStageTimingDigest,
    InternalToolEventSummary,
    InternalRunSummaryToolEventDigest,
)
from backend.app.observability.summary import RunSummary, build_preview_diagnostics, load_run_summary
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    PlanRepository,
    ToolEventRepository,
)
from backend.app.workflow.timing import WorkflowTimingSummary


class InternalObservabilityRunNotFoundError(LookupError):
    """Raised when an internal observability run cannot be found."""


class InternalObservabilityService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_run_summary(self, run_id: UUID) -> InternalObservabilityRunSummary:
        run = AgentRunRepository(self.session).get_by_id(run_id)
        if run is None:
            raise InternalObservabilityRunNotFoundError(f"Run {run_id} was not found.")

        selected_plan = PlanRepository(self.session).get_selected_for_run(run_id)
        selected_plan_json = self._plan_json(selected_plan)
        metadata = self._metadata(run)
        canonical_summary = load_run_summary(metadata)
        tool_events = ToolEventRepository(self.session).list_for_run(run_id)
        workflow_timing_summary = self._workflow_timing_summary(metadata, canonical_summary)
        recovery_path_summary = self._recovery_path_summary(metadata)

        return InternalObservabilityRunSummary(
            run_id=run.run_id,
            status=run.status,
            trace_id=self._trace_id(metadata, canonical_summary),
            case_id=run.case_id,
            agent_version=run.agent_version,
            prompt_version=run.prompt_version,
            tool_profile=run.tool_profile,
            world_profile=run.world_profile,
            failure_profile=run.failure_profile,
            created_at=run.created_at,
            updated_at=run.updated_at,
            tool_event_count=self._tool_event_count(run.run_id, canonical_summary),
            action_count=self._action_count(run.run_id, canonical_summary),
            execution_status=self._execution_status(selected_plan_json, canonical_summary),
            feedback_status=self._feedback_status(selected_plan_json, canonical_summary),
            observability_status=self._observability_status(metadata),
            agent_roles=self._agent_roles(metadata, canonical_summary),
            node_history=self._node_history(metadata),
            preview_diagnostics=self._preview_diagnostics(run, canonical_summary, tool_events),
            tool_event_summaries=self._tool_event_summaries(tool_events),
            action_ledger_summaries=self._action_ledger_summaries(run.run_id),
            workflow_timing_summary=workflow_timing_summary,
            observability_summary=self._observability_summary(metadata),
            benchmark_artifact_summary=self._benchmark_artifact_summary(metadata),
            recovery_path_summary=recovery_path_summary,
            run_summary=self._structured_run_summary(
                run=run,
                selected_plan=selected_plan,
                metadata=metadata,
                canonical_summary=canonical_summary,
                workflow_timing_summary=workflow_timing_summary,
                tool_events=tool_events,
                recovery_path_summary=recovery_path_summary,
            ),
        )

    def _metadata(self, run: AgentRun) -> dict[str, Any]:
        return deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}

    def _plan_json(self, plan: Plan | None) -> dict[str, Any]:
        if plan is None or not isinstance(plan.plan_json, dict):
            return {}
        return deepcopy(plan.plan_json)

    def _trace_id(self, metadata: dict[str, Any], canonical_summary: RunSummary | None) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.trace_id
        demo = metadata.get("demo")
        if isinstance(demo, dict) and isinstance(demo.get("trace_id"), str):
            return demo["trace_id"]
        observability = metadata.get("observability")
        if isinstance(observability, dict) and isinstance(observability.get("trace_id"), str):
            return observability["trace_id"]
        return None

    def _node_history(self, metadata: dict[str, Any]) -> list[str]:
        demo = metadata.get("demo")
        if not isinstance(demo, dict):
            return []
        initial = demo.get("initial_node_history")
        continuation = demo.get("continuation_history")
        return [
            item
            for item in [
                *(initial if isinstance(initial, list) else []),
                *(continuation if isinstance(continuation, list) else []),
            ]
            if isinstance(item, str)
        ]

    def _tool_event_summaries(self, tool_events: list[ToolEvent]) -> list[InternalToolEventSummary]:
        return [
            InternalToolEventSummary(
                tool_name=event.tool_name,
                tool_type=event.tool_type,
                provider=event.provider,
                status=event.status,
                cache_hit=event.cache_hit,
                latency_ms=event.latency_ms,
                created_at=event.created_at,
                request_preview=_preview_payload(event.request_json),
                response_preview=_preview_payload(event.response_json),
                error_preview=_preview_payload(event.error_json),
            )
            for event in tool_events
        ]

    def _action_ledger_summaries(self, run_id: UUID) -> list[InternalActionLedgerSummary]:
        return [
            InternalActionLedgerSummary(
                action_type=action.action_type,
                target_id=action.target_id,
                status=action.status,
                created_at=action.created_at,
                updated_at=action.updated_at,
                request_preview=_preview_payload(action.request_json),
                response_preview=_preview_payload(action.response_json),
                error_preview=_preview_payload(action.error_json),
            )
            for action in ActionLedgerRepository(self.session).list_for_run(run_id)
        ]

    def _agent_roles(self, metadata: dict[str, Any], canonical_summary: RunSummary | None) -> list[str]:
        if canonical_summary is not None:
            return list(canonical_summary.agent_roles)
        agents = metadata.get("agents")
        if not isinstance(agents, dict):
            return []
        results = agents.get("results")
        if not isinstance(results, list):
            return []
        return [
            result["role"]
            for result in results
            if isinstance(result, dict) and isinstance(result.get("role"), str)
        ]

    def _workflow_timing_summary(
        self,
        metadata: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> WorkflowTimingSummary | None:
        if canonical_summary is not None:
            timing = canonical_summary.workflow_timing_summary
            if isinstance(timing, dict):
                try:
                    return WorkflowTimingSummary.model_validate(timing)
                except ValidationError:
                    return None
            return None
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict) or not isinstance(workflow.get("timing"), dict):
            return None
        try:
            return WorkflowTimingSummary.model_validate(workflow["timing"])
        except ValidationError:
            return None

    def _observability_summary(self, metadata: dict[str, Any]) -> InternalObservabilitySummary:
        observability = metadata.get("observability")
        if not isinstance(observability, dict):
            return InternalObservabilitySummary()

        local_buffer = observability.get("local_buffer")
        langsmith = observability.get("langsmith")
        local_buffer_error = (
            sanitize_trace_payload(local_buffer.get("error"))
            if isinstance(local_buffer, dict) and isinstance(local_buffer.get("error"), dict)
            else None
        )
        langsmith_error = (
            sanitize_trace_payload(langsmith.get("error"))
            if isinstance(langsmith, dict) and langsmith.get("error") is not None
            else None
        )

        return InternalObservabilitySummary(
            trace_id=observability.get("trace_id") if isinstance(observability.get("trace_id"), str) else None,
            status=observability.get("status") if isinstance(observability.get("status"), str) else None,
            local_buffer_written=(
                local_buffer.get("written")
                if isinstance(local_buffer, dict) and isinstance(local_buffer.get("written"), bool)
                else None
            ),
            langsmith_enabled=(
                langsmith.get("enabled")
                if isinstance(langsmith, dict) and isinstance(langsmith.get("enabled"), bool)
                else None
            ),
            langsmith_posted=(
                langsmith.get("posted")
                if isinstance(langsmith, dict) and isinstance(langsmith.get("posted"), bool)
                else None
            ),
            local_buffer_error=local_buffer_error,
            langsmith_error=langsmith_error,
        )

    def _benchmark_artifact_summary(
        self,
        metadata: dict[str, Any],
    ) -> InternalBenchmarkArtifactSummary | None:
        from backend.app.benchmark.suites import list_benchmark_suite_ids_for_case

        benchmark = metadata.get("benchmark")
        if not isinstance(benchmark, dict):
            return None

        case_id = benchmark.get("case_id")
        if not isinstance(case_id, str):
            return None

        raw_taxonomy = benchmark.get("taxonomy")
        taxonomy = None
        if isinstance(raw_taxonomy, dict):
            try:
                taxonomy = InternalBenchmarkTaxonomySummary.model_validate(raw_taxonomy)
            except ValidationError:
                taxonomy = None

        raw_artifact = benchmark.get("artifact_summary")
        return InternalBenchmarkArtifactSummary(
            case_id=case_id,
            title=benchmark.get("title") if isinstance(benchmark.get("title"), str) else None,
            workflow_backed=(
                benchmark.get("workflow_backed")
                if isinstance(benchmark.get("workflow_backed"), bool)
                else None
            ),
            registered_suite_ids=list_benchmark_suite_ids_for_case(case_id),
            taxonomy=taxonomy,
            benchmark_status=_string_or_none(raw_artifact, "benchmark_status"),
            overall_score=_float_or_none(raw_artifact, "overall_score"),
            workflow_status=_string_or_none(raw_artifact, "workflow_status"),
            tool_event_count=_int_or_none(raw_artifact, "tool_event_count"),
            action_count=_int_or_none(raw_artifact, "action_count"),
            failure_reasons=_string_list(_mapping_value(raw_artifact, "failure_reasons")),
            memory_policy_summary=self._memory_policy_summary(metadata, raw_artifact),
            score_summaries=_benchmark_score_summaries(_mapping_value(raw_artifact, "score_summaries")),
            report_path=_string_or_none(raw_artifact, "report_path"),
        )

    def _memory_policy_summary(
        self,
        metadata: dict[str, Any],
        raw_artifact: Any,
    ) -> MemoryPolicyAuditSummary | None:
        artifact_summary = _mapping_value(raw_artifact, "memory_policy_summary")
        if isinstance(artifact_summary, dict):
            try:
                return MemoryPolicyAuditSummary.model_validate(artifact_summary)
            except ValidationError:
                pass

        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict):
            return None
        memory_policy = workflow.get("memory_policy")
        if not isinstance(memory_policy, dict):
            return None
        policy_summary = memory_policy.get("policy_summary")
        if not isinstance(policy_summary, dict):
            return None
        try:
            return MemoryPolicyAuditSummary.model_validate(policy_summary)
        except ValidationError:
            return None

    def _recovery_path_summary(
        self,
        metadata: dict[str, Any],
    ) -> InternalRecoveryPathSummary | None:
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict):
            return None

        recovery = workflow.get("recovery")
        if not isinstance(recovery, dict):
            return None

        attempts = _recovery_attempt_summaries(_mapping_value(recovery, "attempts"))
        attempt_count = len(attempts)
        max_attempts = _non_negative_int_or_default(_mapping_value(recovery, "max_attempts"), attempt_count)

        return InternalRecoveryPathSummary(
            attempt_count=attempt_count,
            max_attempts=max_attempts,
            attempts=attempts,
            replay_source=_recovery_replay_source(metadata),
        )

    def _execution_status(
        self,
        selected_plan_json: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.execution_status
        execution = selected_plan_json.get("execution")
        return execution.get("status") if isinstance(execution, dict) and isinstance(execution.get("status"), str) else None

    def _feedback_status(
        self,
        selected_plan_json: dict[str, Any],
        canonical_summary: RunSummary | None,
    ) -> str | None:
        if canonical_summary is not None:
            return canonical_summary.feedback_status
        feedback = selected_plan_json.get("feedback")
        return feedback.get("status") if isinstance(feedback, dict) and isinstance(feedback.get("status"), str) else None

    def _observability_status(self, metadata: dict[str, Any]) -> str | None:
        observability = metadata.get("observability")
        return (
            observability.get("status")
            if isinstance(observability, dict) and isinstance(observability.get("status"), str)
            else None
        )

    def _tool_event_count(self, run_id: UUID, canonical_summary: RunSummary | None) -> int:
        if canonical_summary is not None:
            return canonical_summary.tool_event_count
        return int(
            self.session.scalar(select(func.count()).select_from(ToolEvent).where(ToolEvent.run_id == run_id))
            or 0
        )

    def _action_count(self, run_id: UUID, canonical_summary: RunSummary | None) -> int:
        if canonical_summary is not None:
            return canonical_summary.action_count
        return int(
            self.session.scalar(select(func.count()).select_from(ActionLedger).where(ActionLedger.run_id == run_id))
            or 0
        )

    def _preview_diagnostics(
        self,
        run: AgentRun,
        canonical_summary: RunSummary | None,
        tool_events: list[ToolEvent],
    ):
        if canonical_summary is not None and canonical_summary.preview_diagnostics is not None:
            return canonical_summary.preview_diagnostics
        return build_preview_diagnostics(run, tool_events)

    def _structured_run_summary(
        self,
        *,
        run: AgentRun,
        selected_plan: Plan | None,
        metadata: dict[str, Any],
        canonical_summary: RunSummary | None,
        workflow_timing_summary: WorkflowTimingSummary | None,
        tool_events: list[ToolEvent],
        recovery_path_summary: InternalRecoveryPathSummary | None,
    ) -> InternalStructuredRunSummary:
        selected_plan_id = (
            canonical_summary.selected_plan_id
            if canonical_summary is not None
            else (str(selected_plan.plan_id) if selected_plan is not None else None)
        )
        plan_status = canonical_summary.plan_status if canonical_summary is not None else (selected_plan.status if selected_plan else None)
        execution_status = self._execution_status(self._plan_json(selected_plan), canonical_summary)
        feedback_status = self._feedback_status(self._plan_json(selected_plan), canonical_summary)

        return InternalStructuredRunSummary(
            run_id=run.run_id,
            trace_id=self._trace_id(metadata, canonical_summary),
            workflow_status=run.status,
            selected_plan_id=selected_plan_id,
            plan_status=plan_status,
            execution_status=execution_status,
            feedback_status=feedback_status,
            stage_timing=self._stage_timing_digest(workflow_timing_summary),
            tool_events=self._tool_event_digest(tool_events),
            recovery=self._recovery_digest(recovery_path_summary),
        )

    def _stage_timing_digest(
        self,
        workflow_timing_summary: WorkflowTimingSummary | None,
    ) -> InternalRunSummaryStageTimingDigest:
        if workflow_timing_summary is None:
            return InternalRunSummaryStageTimingDigest(present=False)

        slowest_stage = max(
            workflow_timing_summary.stages,
            key=lambda stage: stage.total_duration_ms,
            default=None,
        )
        return InternalRunSummaryStageTimingDigest(
            present=True,
            total_duration_ms=workflow_timing_summary.total_duration_ms,
            stage_count=workflow_timing_summary.stage_count,
            slowest_stage_name=slowest_stage.node_name if slowest_stage is not None else None,
            slowest_stage_duration_ms=slowest_stage.total_duration_ms if slowest_stage is not None else None,
        )

    def _tool_event_digest(self, tool_events: list[ToolEvent]) -> InternalRunSummaryToolEventDigest:
        status_counts: dict[str, int] = {}
        provider_counts: dict[str, int] = {}
        read_count = 0
        write_count = 0

        for event in tool_events:
            status_counts[event.status] = status_counts.get(event.status, 0) + 1
            provider_counts[event.provider] = provider_counts.get(event.provider, 0) + 1
            if event.tool_type == "read":
                read_count += 1
            else:
                write_count += 1

        latest_event = tool_events[-1] if tool_events else None
        return InternalRunSummaryToolEventDigest(
            total_count=len(tool_events),
            read_count=read_count,
            write_count=write_count,
            status_counts=status_counts,
            provider_counts=provider_counts,
            latest_event=(
                InternalRunSummaryLatestToolEvent(
                    tool_name=latest_event.tool_name,
                    tool_type=latest_event.tool_type,
                    provider=latest_event.provider,
                    status=latest_event.status,
                    latency_ms=latest_event.latency_ms,
                    created_at=latest_event.created_at,
                )
                if latest_event is not None
                else None
            ),
        )

    def _recovery_digest(
        self,
        recovery_path_summary: InternalRecoveryPathSummary | None,
    ) -> InternalRunSummaryRecoveryDigest:
        if recovery_path_summary is None or recovery_path_summary.attempt_count == 0 or not recovery_path_summary.attempts:
            return InternalRunSummaryRecoveryDigest()

        latest_attempt = max(recovery_path_summary.attempts, key=lambda attempt: attempt.attempt_index)
        return InternalRunSummaryRecoveryDigest(
            entered_recovery=True,
            attempt_count=recovery_path_summary.attempt_count,
            max_attempts=recovery_path_summary.max_attempts,
            terminal_action=latest_attempt.recovery_action,
            terminal_status=latest_attempt.status,
            latest_error_type=latest_attempt.error_type,
            replay_case_id=(
                recovery_path_summary.replay_source.case_id
                if recovery_path_summary.replay_source is not None
                else None
            ),
        )


def _preview_payload(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    sanitized = sanitize_trace_payload(deepcopy(value))
    preview = _drop_forbidden_preview_keys(_redact_identifier_keys(sanitized))
    if isinstance(preview, dict):
        return preview
    return {"value": preview}


def _redact_identifier_keys(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_identifier_key(key):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = _redact_identifier_keys(item)
        return sanitized
    if isinstance(value, list):
        return [_redact_identifier_keys(item) for item in value]
    return value


def _drop_forbidden_preview_keys(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_forbidden_preview_key(key):
                continue
            sanitized[key] = _drop_forbidden_preview_keys(item)
        return sanitized
    if isinstance(value, list):
        return [_drop_forbidden_preview_keys(item) for item in value]
    return value


def _is_identifier_key(key: Any) -> bool:
    normalized = str(key).casefold()
    return normalized == "id" or normalized.endswith("_id")


def _is_forbidden_preview_key(key: Any) -> bool:
    return str(key).casefold() in {
        "action_id",
        "tool_event_id",
        "event_id",
        "idempotency_key",
        "confirmation_id",
    }


def _mapping_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return None


def _string_or_none(value: Any, key: str) -> str | None:
    candidate = _mapping_value(value, key)
    return candidate if isinstance(candidate, str) else None


def _int_or_none(value: Any, key: str) -> int | None:
    candidate = _mapping_value(value, key)
    return candidate if isinstance(candidate, int) else None


def _float_or_none(value: Any, key: str) -> float | None:
    candidate = _mapping_value(value, key)
    if isinstance(candidate, (int, float)):
        return float(candidate)
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _benchmark_score_summaries(value: Any) -> list[InternalBenchmarkScoreSummary]:
    if not isinstance(value, list):
        return []

    summaries: list[InternalBenchmarkScoreSummary] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        status = item.get("status")
        score = item.get("score")
        reason = item.get("reason")
        if (
            isinstance(name, str)
            and isinstance(status, str)
            and isinstance(score, (int, float))
            and isinstance(reason, str)
        ):
            summaries.append(
                InternalBenchmarkScoreSummary(
                    name=name,
                    status=status,
                    score=float(score),
                    reason=reason,
                )
                )
    return summaries


def _recovery_attempt_summaries(value: Any) -> list[InternalRecoveryAttemptSummary]:
    if not isinstance(value, list):
        return []

    attempts: list[InternalRecoveryAttemptSummary] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        try:
            attempts.append(InternalRecoveryAttemptSummary.model_validate(item))
        except ValidationError:
            continue
    return attempts


def _recovery_replay_source(metadata: dict[str, Any]) -> InternalRecoveryReplaySourceSummary | None:
    benchmark = metadata.get("benchmark")
    if not isinstance(benchmark, dict):
        return None

    case_id = benchmark.get("case_id")
    artifact_summary = benchmark.get("artifact_summary")
    report_path = _string_or_none(artifact_summary, "report_path")
    if not isinstance(case_id, str) or report_path is None:
        return None

    return InternalRecoveryReplaySourceSummary(
        case_id=case_id,
        benchmark_report_path=report_path,
    )


def _non_negative_int_or_default(value: Any, default: int) -> int:
    if isinstance(value, int):
        return max(value, 0)
    return max(default, 0)
