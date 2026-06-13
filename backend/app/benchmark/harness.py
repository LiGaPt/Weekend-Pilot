from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any, Sequence
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_chain import build_failure_chain_summary
from backend.app.benchmark.graders import (
    combine_scores,
    grade_agent_coverage,
    grade_conversation_path,
    grade_execution_safety,
    grade_failure_injection,
    grade_feedback,
    grade_memory_governance,
    grade_plan_quality,
    grade_robustness_expectation,
    grade_recovery_expectation,
    grade_trajectory,
    grade_workflow_path,
)
from backend.app.benchmark.failure_profiles import (
    build_benchmark_failure_injector,
    failure_profile_metadata,
)
from backend.app.benchmark.matrix import (
    build_case_integrity_coverage_summary,
    build_case_matrix_summary,
    build_case_v2_matrix_summary,
)
from backend.app.benchmark.rollups import build_benchmark_outcome_rollup
from backend.app.benchmark.reporting import write_case_report, write_run_report
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkConversationTraceStep,
    BenchmarkRunReport,
    BenchmarkSummary,
    BenchmarkSuiteId,
    resolve_benchmark_case_v2_taxonomy,
)
from backend.app.demo.schemas import (
    DemoClarifyRunRequest,
    DemoConfirmRunRequest,
    DemoReplanRunRequest,
    DemoStartRunRequest,
)
from backend.app.core.config import Settings
from backend.app.demo.service import DemoServiceError, DemoStartRunOverride, DemoWorkflowService
from backend.app.benchmark.suites import (
    canonical_benchmark_suite_id,
    list_benchmark_suites,
    load_benchmark_suite,
)
from backend.app.benchmark.timing import summarize_benchmark_timing
from backend.app.models.runtime import ActionLedger
from backend.app.observability.summary import RunSummary, build_run_summary, load_run_summary
from backend.app.providers.mock_world.loader import SUPPORTED_PROFILES
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    ConversationTurnRepository,
    MemoryItemRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache
from backend.app.workflow import (
    WeekendPilotWorkflowDependencies,
    WeekendPilotWorkflowRequest,
    WeekendPilotWorkflowResult,
    WeekendPilotWorkflowRunner,
)


class BenchmarkHarness:
    harness_version = "locallife_bench_harness_v0"

    def __init__(
        self,
        session: Session,
        cache: JsonRedisCache,
        rate_limiter: FixedWindowRateLimiter,
        report_dir: Path | str = "var/benchmarks",
        trace_buffer_path: Path | str | None = None,
        workflow_settings: Settings | None = None,
        workflow_llm_client: Any | None = None,
    ) -> None:
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.report_dir = Path(report_dir)
        self.trace_buffer_path = Path(trace_buffer_path) if trace_buffer_path is not None else None
        self.workflow_settings = workflow_settings
        self.workflow_llm_client = workflow_llm_client

    def run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        try:
            if case.tool_profile != "mock_world":
                return self._finalize_case_result(
                    BenchmarkCaseResult(
                        case_id=case.case_id,
                        status="error",
                        taxonomy=case.taxonomy,
                        v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                        scores=[],
                        overall_score=0.0,
                        tool_event_count=0,
                        action_count=0,
                        failure_reasons=[f"Unsupported benchmark tool_profile: {case.tool_profile}"],
                    )
                )
            if case.continuations:
                return self._run_continuation_case(case)
            return self._run_legacy_case(case)
        except BenchmarkHarnessError:
            raise
        except Exception as exc:
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                taxonomy=case.taxonomy,
                v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                scores=[],
                overall_score=0.0,
                tool_event_count=0,
                action_count=0,
                failure_reasons=[f"{type(exc).__name__}: {exc}"],
            )
            return self._finalize_case_result(result)

    def run_cases(self, cases: Sequence[BenchmarkCase]) -> BenchmarkRunReport:
        return self._run_cases_with_summary(cases, suite_id=None, suite_title=None, report_filename="run-report.json")

    def run_suite(self, suite_id: BenchmarkSuiteId | str) -> BenchmarkRunReport:
        canonical_suite_id = canonical_benchmark_suite_id(suite_id)
        suite_cases = load_benchmark_suite(canonical_suite_id)
        suite_description = next(
            (suite for suite in list_benchmark_suites() if suite.suite_id == canonical_suite_id),
            None,
        )
        if suite_description is None:
            raise BenchmarkHarnessError(f"Unknown benchmark suite ID: {suite_id}")
        return self._run_cases_with_summary(
            suite_cases,
            suite_id=canonical_suite_id,
            suite_title=suite_description.title,
            report_filename=f"suite-{canonical_suite_id}-run-report.json",
        )

    def _run_cases_with_summary(
        self,
        cases: Sequence[BenchmarkCase],
        *,
        suite_id: BenchmarkSuiteId | None,
        suite_title: str | None,
        report_filename: str,
    ) -> BenchmarkRunReport:
        results = [self.run_case(case) for case in cases]
        passed_count = sum(1 for result in results if result.status == "passed")
        failed_count = sum(1 for result in results if result.status == "failed")
        error_count = sum(1 for result in results if result.status == "error")
        timing_summary = summarize_benchmark_timing(results)
        overall_score = round(mean([result.overall_score for result in results]) if results else 0.0, 4)
        if error_count:
            run_status = "error"
        elif failed_count:
            run_status = "failed"
        else:
            run_status = "passed"
        report = BenchmarkRunReport(
            run_status=run_status,
            case_results=results,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            overall_score=overall_score,
            benchmark_timing_summary=timing_summary,
            benchmark_summary=BenchmarkSummary(
                suite_id=suite_id,
                suite_title=suite_title,
                run_status=run_status,
                case_count=len(results),
                passed_count=passed_count,
                failed_count=failed_count,
                error_count=error_count,
                overall_score=overall_score,
                benchmark_timing_summary=timing_summary,
                matrix_summary=build_case_matrix_summary(cases),
                v2_taxonomy_summary=build_case_v2_matrix_summary(cases),
                integrity_coverage_summary=build_case_integrity_coverage_summary(cases),
                outcome_rollup=build_benchmark_outcome_rollup(results),
            ),
        )
        report_path = write_run_report(report, self.report_dir, filename=report_filename)
        return report.model_copy(update={"report_path": str(report_path)})

    def _run_legacy_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        if case.world_profile not in SUPPORTED_PROFILES:
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                taxonomy=case.taxonomy,
                v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                scores=[],
                overall_score=0.0,
                tool_event_count=0,
                action_count=0,
                failure_reasons=[f"Unsupported benchmark profile: {case.tool_profile}/{case.world_profile}"],
            )
            return self._finalize_case_result(result)

        failure_injector = build_benchmark_failure_injector(case.failure_profile)
        repositories = _Repositories(self.session)
        external_user_id, _ = self._prepare_case_user(case, repositories)

        workflow_result = WeekendPilotWorkflowRunner(
            WeekendPilotWorkflowDependencies(
                session=self.session,
                cache=self.cache,
                rate_limiter=_BenchmarkCaseRateLimiter(self.rate_limiter, external_user_id),
                failure_injector=failure_injector,
                trace_buffer_path=self._trace_path(case.case_id),
                settings=self.workflow_settings,
                llm_client=self.workflow_llm_client,
            )
        ).run(
            WeekendPilotWorkflowRequest(
                user_input=case.user_input,
                external_user_id=external_user_id,
                display_name=f"Benchmark {case.case_id}",
                case_id=case.case_id,
                agent_version=case.agent_version,
                prompt_version=case.prompt_version,
                tool_profile=case.tool_profile,
                world_profile=case.world_profile,
                failure_profile=case.failure_profile,
                auto_confirm=True,
                selected_plan_index=0,
            )
        )

        if workflow_result.run_id is None:
            result = self._workflow_error_result(case, workflow_result)
            return self._finalize_case_result(result, repositories)

        run = repositories.runs.get_by_id(workflow_result.run_id)
        if run is None:
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                run_id=workflow_result.run_id,
                trace_id=workflow_result.trace_id,
                run_summary=None,
                taxonomy=case.taxonomy,
                v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                scores=[],
                overall_score=0.0,
                tool_event_count=workflow_result.tool_event_count,
                action_count=workflow_result.action_count,
                feedback_status=workflow_result.feedback_status,
                observability_status=workflow_result.observability_status,
                workflow_status=workflow_result.status,
                workflow_timing_summary=workflow_result.workflow_timing_summary,
                workflow_node_history=list(workflow_result.node_history),
                agent_roles=self._agent_roles(workflow_result),
                failure_reasons=["Workflow run was not persisted."],
            )
            return self._finalize_case_result(result, repositories)

        self._record_benchmark_metadata(repositories, run.run_id, case)
        updated_run = repositories.runs.get_by_id(run.run_id)
        persisted_run = updated_run if updated_run is not None else run
        run_metadata = persisted_run.metadata_json if isinstance(persisted_run.metadata_json, dict) else {}
        selected_plan = repositories.plans.get_selected_for_run(run.run_id)
        tool_events = repositories.tool_events.list_for_run(run.run_id)
        action_count = self._action_count(run.run_id)
        failure_chain_summary = (
            build_failure_chain_summary(
                failure_profile=case.failure_profile,
                tool_events=tool_events,
                run_metadata=run_metadata,
                workflow_status=workflow_result.status,
            )
            if case.failure_profile is not None
            else None
        )
        run_summary = self._run_summary(
            run=persisted_run,
            selected_plan=selected_plan,
            metadata=run_metadata,
            trace_id=workflow_result.trace_id,
            tool_events=tool_events,
            tool_event_count=len(tool_events),
            action_count=action_count,
        )

        if workflow_result.status == "error":
            result = self._workflow_error_result(
                case,
                workflow_result,
                run_summary=run_summary,
                failure_chain_summary=failure_chain_summary,
            )
            return self._finalize_case_result(result, repositories)

        plan_json = selected_plan.plan_json if selected_plan is not None and isinstance(selected_plan.plan_json, dict) else {}
        execution = plan_json.get("execution") if isinstance(plan_json, dict) else None
        feedback = plan_json.get("feedback") if isinstance(plan_json, dict) else None
        scores = [
            grade_workflow_path(workflow_result, case),
            grade_agent_coverage(workflow_result),
            grade_trajectory(case, tool_events),
            grade_failure_injection(case, tool_events),
            grade_execution_safety(case, execution),
            grade_feedback(case, feedback),
        ]
        if case.expected.expected_workflow_status == "completed":
            scores.insert(3, grade_plan_quality(selected_plan))
            if case.expected.robustness is not None:
                scores.insert(4, grade_robustness_expectation(case, selected_plan, tool_events))
        elif case.expected.robustness is not None:
            scores.append(grade_robustness_expectation(case, selected_plan, tool_events))
        if case.expected.expected_recovery_action is not None:
            scores.append(grade_recovery_expectation(case, run_metadata))
        if case.expected.memory_governance is not None:
            scores.append(grade_memory_governance(case, run_metadata))
        status, overall, failure_reasons = combine_scores(scores)
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            status=status,
            run_id=run.run_id,
            trace_id=workflow_result.trace_id,
            run_summary=run_summary,
            taxonomy=case.taxonomy,
            v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
            failure_chain_summary=failure_chain_summary,
            scores=scores,
            overall_score=overall,
            tool_event_count=len(tool_events),
            action_count=action_count,
            plan_status=getattr(selected_plan, "status", None),
            feedback_status=workflow_result.feedback_status or self._metadata_status(feedback),
            observability_status=workflow_result.observability_status,
            workflow_status=workflow_result.status,
            workflow_timing_summary=workflow_result.workflow_timing_summary,
            workflow_node_history=list(workflow_result.node_history),
            agent_roles=self._agent_roles(workflow_result),
            failure_reasons=failure_reasons,
        )
        return self._finalize_case_result(result, repositories)

    def _run_continuation_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        if case.tool_profile != "mock_world":
            return self._finalize_case_result(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    status="error",
                    taxonomy=case.taxonomy,
                    v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                    scores=[],
                    overall_score=0.0,
                    tool_event_count=0,
                    action_count=0,
                    failure_reasons=["Continuation benchmark cases currently support only tool_profile='mock_world'."],
                )
            )
        if case.failure_profile is not None:
            return self._finalize_case_result(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    status="error",
                    taxonomy=case.taxonomy,
                    v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                    scores=[],
                    overall_score=0.0,
                    tool_event_count=0,
                    action_count=0,
                    failure_reasons=["Continuation benchmark cases do not support failure profiles in v0."],
                )
            )
        if case.world_profile not in SUPPORTED_PROFILES:
            return self._finalize_case_result(
                BenchmarkCaseResult(
                    case_id=case.case_id,
                    status="error",
                    taxonomy=case.taxonomy,
                    v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
                    scores=[],
                    overall_score=0.0,
                    tool_event_count=0,
                    action_count=0,
                    failure_reasons=[f"Unsupported benchmark profile: {case.tool_profile}/{case.world_profile}"],
                )
            )

        repositories = _Repositories(self.session)
        external_user_id, user = self._prepare_case_user(case, repositories)
        service = DemoWorkflowService(
            session=self.session,
            cache=self.cache,
            rate_limiter=_BenchmarkCaseRateLimiter(self.rate_limiter, external_user_id),
            trace_buffer_path=self._trace_path(case.case_id),
            workflow_settings=self.workflow_settings,
            workflow_llm_client=self.workflow_llm_client,
        )
        conversation_trace: list[BenchmarkConversationTraceStep] = []
        conversation_run_ids: list[UUID] = []
        current_run_id: UUID | None = None

        try:
            start_summary = service.start_run(
                DemoStartRunRequest(
                    user_input=case.user_input,
                    external_user_id=external_user_id,
                    display_name=user.display_name,
                    case_id=case.case_id,
                    selected_plan_index=0,
                    read_profile="mock_world",
                ),
                override=DemoStartRunOverride(
                    tool_profile=case.tool_profile,
                    world_profile=case.world_profile,
                    agent_version=case.agent_version,
                    prompt_version=case.prompt_version,
                ),
            )
            current_run_id = start_summary.run_id
            if repositories.runs.get_by_id(current_run_id) is None:
                return self._finalize_case_result(
                    self._continuation_error_result(
                        case,
                        "Continuation start step did not persist a run.",
                        conversation_trace=conversation_trace,
                    ),
                    repositories,
                )
            conversation_run_ids.append(current_run_id)
            conversation_trace.append(
                self._conversation_trace_step(
                    mode="start",
                    source_run_id=None,
                    summary=start_summary,
                )
            )

            current_summary = start_summary
            for continuation in case.continuations:
                source_run_id = current_run_id
                if continuation.mode == "clarify":
                    current_summary = service.clarify_run(
                        source_run_id,
                        DemoClarifyRunRequest(
                            user_input=continuation.user_input,
                            selected_plan_index=continuation.selected_plan_index,
                        ),
                    )
                else:
                    current_summary = service.replan_run(
                        source_run_id,
                        DemoReplanRunRequest(
                            user_input=continuation.user_input,
                            selected_plan_index=continuation.selected_plan_index,
                        ),
                    )
                current_run_id = current_summary.run_id
                if repositories.runs.get_by_id(current_run_id) is None:
                    return self._finalize_case_result(
                        self._continuation_error_result(
                            case,
                            f"Continuation step {continuation.mode!r} did not persist a run.",
                            run_id=source_run_id,
                            conversation_trace=conversation_trace,
                        ),
                        repositories,
                    )
                conversation_run_ids.append(current_run_id)
                conversation_trace.append(
                    self._conversation_trace_step(
                        mode=continuation.mode,
                        source_run_id=source_run_id,
                        summary=current_summary,
                    )
                )

            if current_summary.status == "awaiting_confirmation":
                source_run_id = current_run_id
                current_summary = service.confirm_run(
                    source_run_id,
                    DemoConfirmRunRequest(),
                )
                current_run_id = current_summary.run_id
                conversation_trace.append(
                    self._conversation_trace_step(
                        mode="confirm",
                        source_run_id=source_run_id,
                        summary=current_summary,
                    )
                )
        except DemoServiceError as exc:
            return self._finalize_case_result(
                self._continuation_error_result(
                    case,
                    exc.message,
                    run_id=current_run_id,
                    conversation_trace=conversation_trace,
                ),
                repositories,
            )

        final_run = repositories.runs.get_by_id(current_run_id) if current_run_id is not None else None
        if final_run is None:
            return self._finalize_case_result(
                self._continuation_error_result(
                    case,
                    "Continuation chain did not leave a persisted final run.",
                    conversation_trace=conversation_trace,
                ),
                repositories,
            )

        ordered_run_ids = self._dedupe_run_ids(conversation_run_ids)
        for run_id in ordered_run_ids:
            self._record_benchmark_metadata(repositories, run_id, case)

        updated_final_run = repositories.runs.get_by_id(final_run.run_id)
        persisted_final_run = updated_final_run if updated_final_run is not None else final_run
        run_metadata = persisted_final_run.metadata_json if isinstance(persisted_final_run.metadata_json, dict) else {}
        selected_plan = repositories.plans.get_selected_for_run(persisted_final_run.run_id)
        aggregated_tool_events = self._tool_events_for_run_ids(repositories, ordered_run_ids)
        aggregated_action_count = self._action_count_for_run_ids(repositories, ordered_run_ids)
        final_run_tool_events = repositories.tool_events.list_for_run(persisted_final_run.run_id)
        final_run_action_count = len(repositories.action_ledger.list_for_run(persisted_final_run.run_id))
        conversation_turn_types = self._conversation_turn_types(repositories, persisted_final_run.session_id)
        run_summary = self._run_summary(
            run=persisted_final_run,
            selected_plan=selected_plan,
            metadata=run_metadata,
            trace_id=self._trace_id_from_metadata(run_metadata),
            tool_events=final_run_tool_events,
            tool_event_count=len(final_run_tool_events),
            action_count=final_run_action_count,
        )

        plan_json = selected_plan.plan_json if selected_plan is not None and isinstance(selected_plan.plan_json, dict) else {}
        execution = plan_json.get("execution") if isinstance(plan_json, dict) else None
        feedback = plan_json.get("feedback") if isinstance(plan_json, dict) else None
        workflow_result = {
            "status": persisted_final_run.status,
            "node_history": self._workflow_node_history_from_metadata(run_metadata),
            "agent_results": self._agent_results_from_metadata(run_metadata),
            "error_json": self._workflow_error_from_metadata(run_metadata),
        }
        scores = [
            grade_workflow_path(workflow_result, case),
            grade_agent_coverage(workflow_result),
            grade_trajectory(case, aggregated_tool_events),
            grade_failure_injection(case, aggregated_tool_events),
            grade_execution_safety(case, execution),
            grade_feedback(case, feedback),
        ]
        if case.expected.expected_workflow_status == "completed":
            scores.insert(3, grade_plan_quality(selected_plan))
            if case.expected.robustness is not None:
                scores.insert(4, grade_robustness_expectation(case, selected_plan, aggregated_tool_events))
        elif case.expected.robustness is not None:
            scores.append(grade_robustness_expectation(case, selected_plan, aggregated_tool_events))
        if case.expected.expected_recovery_action is not None:
            scores.append(grade_recovery_expectation(case, run_metadata))
        if case.expected.memory_governance is not None:
            scores.append(grade_memory_governance(case, run_metadata))
        if case.expected.conversation is not None:
            scores.append(
                grade_conversation_path(
                    case,
                    conversation_trace,
                    conversation_turn_types,
                )
            )

        status, overall, failure_reasons = combine_scores(scores)
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            status=status,
            run_id=persisted_final_run.run_id,
            trace_id=self._trace_id_from_metadata(run_metadata),
            run_summary=run_summary,
            taxonomy=case.taxonomy,
            v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
            scores=scores,
            overall_score=overall,
            tool_event_count=len(aggregated_tool_events),
            action_count=aggregated_action_count,
            plan_status=getattr(selected_plan, "status", None),
            feedback_status=current_summary.feedback_status or self._metadata_status(feedback),
            observability_status=self._observability_status_from_metadata(run_metadata),
            workflow_status=persisted_final_run.status,
            workflow_timing_summary=run_summary.workflow_timing_summary if run_summary is not None else None,
            workflow_node_history=self._workflow_node_history_from_metadata(run_metadata),
            conversation_trace=conversation_trace,
            conversation_turn_types=conversation_turn_types,
            agent_roles=self._agent_roles(workflow_result),
            failure_reasons=failure_reasons,
        )
        return self._finalize_case_result(result, repositories)

    def _workflow_error_result(
        self,
        case: BenchmarkCase,
        workflow_result: WeekendPilotWorkflowResult,
        *,
        run_summary: RunSummary | None = None,
        failure_chain_summary=None,
    ) -> BenchmarkCaseResult:
        return BenchmarkCaseResult(
            case_id=case.case_id,
            status="error",
            run_id=workflow_result.run_id,
            trace_id=workflow_result.trace_id,
            run_summary=run_summary,
            taxonomy=case.taxonomy,
            v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
            failure_chain_summary=failure_chain_summary,
            scores=[],
            overall_score=0.0,
            tool_event_count=workflow_result.tool_event_count,
            action_count=workflow_result.action_count,
            feedback_status=workflow_result.feedback_status,
            observability_status=workflow_result.observability_status,
            workflow_status=workflow_result.status,
            workflow_timing_summary=workflow_result.workflow_timing_summary,
            workflow_node_history=list(workflow_result.node_history),
            agent_roles=self._agent_roles(workflow_result),
            failure_reasons=[self._workflow_failure_reason(workflow_result)],
        )

    def _prepare_case_user(
        self,
        case: BenchmarkCase,
        repositories: "_Repositories",
    ):
        external_user_id = f"benchmark-{case.case_id}-{uuid4()}"
        user = repositories.users.get_by_external_id(external_user_id)
        if user is None:
            user = repositories.users.create(
                external_id=external_user_id,
                display_name=f"Benchmark {case.case_id}",
            )
        for item in case.memory_items:
            repositories.memory.create(
                user_id=user.user_id,
                memory_type=item.memory_type,
                key=item.key,
                value_json=item.value_json,
                text=item.text,
                confidence=item.confidence,
                source_run_id=None,
                source_langsmith_trace_id=None,
                expires_at=item.expires_at,
                status=item.status,
            )
        return external_user_id, user

    def _continuation_error_result(
        self,
        case: BenchmarkCase,
        message: str,
        *,
        run_id: UUID | None = None,
        conversation_trace: Sequence[BenchmarkConversationTraceStep] | None = None,
    ) -> BenchmarkCaseResult:
        return BenchmarkCaseResult(
            case_id=case.case_id,
            status="error",
            run_id=run_id,
            taxonomy=case.taxonomy,
            v2_taxonomy=resolve_benchmark_case_v2_taxonomy(case),
            scores=[],
            overall_score=0.0,
            tool_event_count=0,
            action_count=0,
            conversation_trace=list(conversation_trace or []),
            failure_reasons=[str(message)],
        )

    def _conversation_trace_step(
        self,
        *,
        mode: str,
        source_run_id: UUID | None,
        summary: Any,
    ) -> BenchmarkConversationTraceStep:
        plan_version = getattr(summary, "plan_version", None)
        version_label = getattr(plan_version, "version_label", None)
        return BenchmarkConversationTraceStep(
            mode=mode,
            source_run_id=source_run_id,
            run_id=getattr(summary, "run_id", None),
            status=str(getattr(summary, "status", "")),
            version_label=version_label,
        )

    def _dedupe_run_ids(self, run_ids: Sequence[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        ordered: list[UUID] = []
        for run_id in run_ids:
            if run_id in seen:
                continue
            seen.add(run_id)
            ordered.append(run_id)
        return ordered

    def _tool_events_for_run_ids(
        self,
        repositories: "_Repositories",
        run_ids: Sequence[UUID],
    ) -> list[Any]:
        events: list[Any] = []
        for run_id in run_ids:
            events.extend(repositories.tool_events.list_for_run(run_id))
        return events

    def _action_count_for_run_ids(
        self,
        repositories: "_Repositories",
        run_ids: Sequence[UUID],
    ) -> int:
        return sum(len(repositories.action_ledger.list_for_run(run_id)) for run_id in run_ids)

    def _conversation_turn_types(
        self,
        repositories: "_Repositories",
        session_id: UUID | None,
    ) -> list[str]:
        if session_id is None:
            return []
        return [
            str(turn.turn_type)
            for turn in repositories.conversation_turns.list_for_session(session_id)
            if getattr(turn, "turn_type", None)
        ]

    def _workflow_node_history_from_metadata(self, metadata: dict[str, Any]) -> list[str]:
        demo = metadata.get("demo")
        if isinstance(demo, dict):
            initial = demo.get("initial_node_history")
            continuation = demo.get("continuation_history")
            if isinstance(initial, list) or isinstance(continuation, list):
                return [
                    str(node)
                    for node in [*(initial or []), *(continuation or [])]
                    if node is not None
                ]
        workflow = metadata.get("workflow")
        if isinstance(workflow, dict) and isinstance(workflow.get("node_history"), list):
            return [str(node) for node in workflow.get("node_history", []) if node is not None]
        return []

    def _agent_results_from_metadata(self, metadata: dict[str, Any]) -> list[Any]:
        agents = metadata.get("agents")
        if not isinstance(agents, dict):
            return []
        results = agents.get("results")
        if not isinstance(results, list):
            return []
        return results

    def _workflow_error_from_metadata(self, metadata: dict[str, Any]) -> dict[str, Any] | None:
        workflow = metadata.get("workflow")
        if isinstance(workflow, dict) and isinstance(workflow.get("error"), dict):
            return workflow.get("error")
        demo = metadata.get("demo")
        if isinstance(demo, dict) and isinstance(demo.get("initial_error"), dict):
            return demo.get("initial_error")
        return None

    def _trace_id_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        demo = metadata.get("demo")
        if isinstance(demo, dict):
            trace_id = demo.get("trace_id")
            if isinstance(trace_id, str) and trace_id:
                return trace_id
        observability = metadata.get("observability")
        if isinstance(observability, dict):
            trace_id = observability.get("trace_id")
            if isinstance(trace_id, str) and trace_id:
                return trace_id
        stored = load_run_summary(metadata)
        if stored is not None and stored.trace_id:
            return stored.trace_id
        return None

    def _observability_status_from_metadata(self, metadata: dict[str, Any]) -> str | None:
        observability = metadata.get("observability")
        if isinstance(observability, dict):
            status = observability.get("status")
            if isinstance(status, str):
                return status
            if isinstance(observability.get("trace_id"), str):
                return "completed"
        return None

    def _record_benchmark_metadata(
        self,
        repositories: "_Repositories",
        run_id,
        case: BenchmarkCase,
    ) -> None:
        run = repositories.runs.get_by_id(run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        metadata["benchmark"] = {
            "case_id": case.case_id,
            "title": case.title,
            "failure_profile": case.failure_profile,
            "failure_profile_metadata": failure_profile_metadata(case.failure_profile),
            "benchmark_harness_version": self.harness_version,
            "harness_version": self.harness_version,
            "taxonomy": case.taxonomy.model_dump(mode="json"),
            "v2_taxonomy": resolve_benchmark_case_v2_taxonomy(case).model_dump(mode="json"),
            "metadata": case.metadata,
            "workflow_backed": True,
        }
        repositories.runs.update_metadata_json(run_id, metadata)

    def _finalize_case_result(
        self,
        result: BenchmarkCaseResult,
        repositories: "_Repositories" | None = None,
    ) -> BenchmarkCaseResult:
        report_path = write_case_report(result, self.report_dir)
        result_with_path = result.model_copy(update={"report_path": str(report_path)})
        if repositories is not None and result_with_path.run_id is not None:
            try:
                self._record_benchmark_artifact_summary(repositories, result_with_path)
            except Exception:
                return result_with_path
        return result_with_path

    def _record_benchmark_artifact_summary(
        self,
        repositories: "_Repositories",
        result: BenchmarkCaseResult,
    ) -> None:
        run = repositories.runs.get_by_id(result.run_id)
        if run is None:
            return
        metadata = deepcopy(run.metadata_json) if isinstance(run.metadata_json, dict) else {}
        benchmark_metadata = deepcopy(metadata.get("benchmark")) if isinstance(metadata.get("benchmark"), dict) else {}
        benchmark_metadata["artifact_summary"] = {
            "schema_version": "weekendpilot_benchmark_artifact_summary_v1",
            "benchmark_status": result.status,
            "overall_score": result.overall_score,
            "workflow_status": result.workflow_status,
            "tool_event_count": result.tool_event_count,
            "action_count": result.action_count,
            "failure_reasons": list(result.failure_reasons),
            "score_summaries": [
                {
                    "name": score.name,
                    "status": "passed" if score.passed else "failed",
                    "score": score.score,
                    "reason": score.reason,
                }
                for score in result.scores
            ],
            "report_path": result.report_path,
        }
        metadata["benchmark"] = benchmark_metadata
        repositories.runs.update_metadata_json(result.run_id, metadata)

    def _workflow_failure_reason(self, workflow_result: Any) -> str:
        error_json = _value(workflow_result, "error_json")
        status = _value(workflow_result, "status")
        if not isinstance(error_json, dict):
            return f"Workflow returned status {status!r}."
        error_type = error_json.get("error_type")
        message = error_json.get("message")
        if error_type and message:
            return f"{error_type}: {message}"
        if message:
            return str(message)
        if error_type:
            return str(error_type)
        return f"Workflow returned status {status!r}."

    def _agent_roles(self, workflow_result: Any) -> list[str]:
        return sorted(
            {
                str(_value(agent, "role"))
                for agent in (_value(workflow_result, "agent_results", []) or [])
                if _value(agent, "role")
            }
        )

    def _metadata_status(self, metadata: Any) -> str | None:
        if isinstance(metadata, dict):
            status = metadata.get("status")
            return status if isinstance(status, str) else None
        return None

    def _trace_path(self, case_id: str) -> Path:
        if self.trace_buffer_path is not None:
            return self.trace_buffer_path
        return self.report_dir / f"{case_id}-trace.jsonl"

    def _action_count(self, run_id) -> int:
        statement = select(ActionLedger).where(ActionLedger.run_id == run_id)
        return len(list(self.session.scalars(statement).all()))

    def _run_summary(
        self,
        *,
        run,
        selected_plan,
        metadata: dict[str, Any],
        trace_id: str | None,
        tool_events,
        tool_event_count: int,
        action_count: int,
    ) -> RunSummary | None:
        stored = load_run_summary(metadata)
        if stored is not None:
            return stored
        try:
            return build_run_summary(
                run,
                selected_plan,
                metadata,
                trace_id_override=trace_id,
                tool_events=tool_events,
                tool_event_count=tool_event_count,
                action_count=action_count,
            )
        except ValidationError:
            return None


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


class _Repositories:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)
        self.runs = AgentRunRepository(session)
        self.memory = MemoryItemRepository(session)
        self.tool_events = ToolEventRepository(session)
        self.action_ledger = ActionLedgerRepository(session)
        self.conversation_turns = ConversationTurnRepository(session)
        self.plans = PlanRepository(session)


class _BenchmarkCaseRateLimiter(FixedWindowRateLimiter):
    def __init__(self, base: FixedWindowRateLimiter, namespace: str) -> None:
        self._base = base
        self._namespace = namespace

    def allow(self, name: str, limit: int, window_seconds: int):
        return self._base.allow(
            f"benchmark:{self._namespace}:{name}",
            limit=limit,
            window_seconds=window_seconds,
        )
