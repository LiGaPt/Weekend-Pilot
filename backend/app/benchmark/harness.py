from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any, Sequence
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_chain import build_failure_chain_summary
from backend.app.benchmark.graders import (
    combine_scores,
    grade_agent_coverage,
    grade_execution_safety,
    grade_failure_injection,
    grade_feedback,
    grade_plan_quality,
    grade_recovery_expectation,
    grade_trajectory,
    grade_workflow_path,
)
from backend.app.benchmark.failure_profiles import (
    build_benchmark_failure_injector,
    failure_profile_metadata,
)
from backend.app.benchmark.matrix import build_case_matrix_summary
from backend.app.benchmark.rollups import build_benchmark_outcome_rollup
from backend.app.benchmark.reporting import write_case_report, write_run_report
from backend.app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkRunReport,
    BenchmarkSummary,
    BenchmarkSuiteId,
)
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
    ) -> None:
        self.session = session
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.report_dir = Path(report_dir)
        self.trace_buffer_path = Path(trace_buffer_path) if trace_buffer_path is not None else None

    def run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        try:
            return self._run_case(case)
        except BenchmarkHarnessError:
            raise
        except Exception as exc:
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                taxonomy=case.taxonomy,
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
                outcome_rollup=build_benchmark_outcome_rollup(results),
            ),
        )
        report_path = write_run_report(report, self.report_dir, filename=report_filename)
        return report.model_copy(update={"report_path": str(report_path)})

    def _run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        if case.tool_profile != "mock_world" or case.world_profile not in SUPPORTED_PROFILES:
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                taxonomy=case.taxonomy,
                scores=[],
                overall_score=0.0,
                tool_event_count=0,
                action_count=0,
                failure_reasons=[f"Unsupported benchmark profile: {case.tool_profile}/{case.world_profile}"],
            )
            return self._finalize_case_result(result)

        failure_injector = build_benchmark_failure_injector(case.failure_profile)
        repositories = _Repositories(self.session)
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
                expires_at=None,
                status=item.status,
            )

        workflow_result = WeekendPilotWorkflowRunner(
            WeekendPilotWorkflowDependencies(
                session=self.session,
                cache=self.cache,
                rate_limiter=_BenchmarkCaseRateLimiter(self.rate_limiter, external_user_id),
                failure_injector=failure_injector,
                trace_buffer_path=self._trace_path(case.case_id),
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
        if case.expected.expected_recovery_action is not None:
            scores.append(grade_recovery_expectation(case, run_metadata))
        status, overall, failure_reasons = combine_scores(scores)
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            status=status,
            run_id=run.run_id,
            trace_id=workflow_result.trace_id,
            run_summary=run_summary,
            taxonomy=case.taxonomy,
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

    def _workflow_failure_reason(self, workflow_result: WeekendPilotWorkflowResult) -> str:
        error_json = workflow_result.error_json
        if not isinstance(error_json, dict):
            return f"Workflow returned status {workflow_result.status!r}."
        error_type = error_json.get("error_type")
        message = error_json.get("message")
        if error_type and message:
            return f"{error_type}: {message}"
        if message:
            return str(message)
        if error_type:
            return str(error_type)
        return f"Workflow returned status {workflow_result.status!r}."

    def _agent_roles(self, workflow_result: WeekendPilotWorkflowResult) -> list[str]:
        return sorted(
            {
                str(agent.role)
                for agent in workflow_result.agent_results
                if getattr(agent, "role", None)
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
                tool_event_count=tool_event_count,
                action_count=action_count,
            )
        except ValidationError:
            return None


class _Repositories:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)
        self.runs = AgentRunRepository(session)
        self.memory = MemoryItemRepository(session)
        self.tool_events = ToolEventRepository(session)
        self.action_ledger = ActionLedgerRepository(session)
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
