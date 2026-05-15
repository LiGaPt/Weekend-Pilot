from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.graders import (
    combine_scores,
    grade_execution_safety,
    grade_feedback,
    grade_plan_quality,
    grade_trajectory,
)
from backend.app.benchmark.reporting import write_case_report
from backend.app.benchmark.schemas import BenchmarkCase, BenchmarkCaseResult, BenchmarkRunReport
from backend.app.confirmation import HumanConfirmationService
from backend.app.execution import DeterministicExecutionWorkflow
from backend.app.feedback import DeterministicFeedbackWriter
from backend.app.models.runtime import ActionLedger
from backend.app.observability import LocalTraceBuffer, ObservabilityRecorder
from backend.app.planning import (
    CandidateEnricher,
    DeterministicIntentParser,
    DeterministicItineraryGenerator,
    DeterministicQueryPlanner,
    QueryPlanExecutor,
)
from backend.app.plans import ReviewedPlanPersistenceService
from backend.app.providers.mock_world import build_mock_world_registry
from backend.app.repositories import (
    ActionLedgerRepository,
    AgentRunRepository,
    MemoryItemRepository,
    PlanRepository,
    ToolEventRepository,
    UserRepository,
)
from backend.app.review import FinalReviewGate
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache
from backend.app.tool_gateway import ToolGateway


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
                scores=[],
                overall_score=0.0,
                tool_event_count=0,
                action_count=0,
                failure_reasons=[f"{type(exc).__name__}: {exc}"],
            )
            report_path = write_case_report(result, self.report_dir)
            return result.model_copy(update={"report_path": str(report_path)})

    def run_cases(self, cases: Sequence[BenchmarkCase]) -> BenchmarkRunReport:
        results = [self.run_case(case) for case in cases]
        passed_count = sum(1 for result in results if result.status == "passed")
        failed_count = sum(1 for result in results if result.status == "failed")
        error_count = sum(1 for result in results if result.status == "error")
        if error_count:
            run_status = "error"
        elif failed_count:
            run_status = "failed"
        else:
            run_status = "passed"
        return BenchmarkRunReport(
            run_status=run_status,
            case_results=results,
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            overall_score=round(mean([result.overall_score for result in results]) if results else 0.0, 4),
        )

    def _run_case(self, case: BenchmarkCase) -> BenchmarkCaseResult:
        if case.tool_profile != "mock_world" or case.world_profile != "family_afternoon":
            result = BenchmarkCaseResult(
                case_id=case.case_id,
                status="error",
                scores=[],
                overall_score=0.0,
                tool_event_count=0,
                action_count=0,
                failure_reasons=[f"Unsupported benchmark profile: {case.tool_profile}/{case.world_profile}"],
            )
            report_path = write_case_report(result, self.report_dir)
            return result.model_copy(update={"report_path": str(report_path)})

        repositories = _Repositories(self.session)
        user = repositories.users.create(
            external_id=f"benchmark-{case.case_id}-{uuid4()}",
            display_name=f"Benchmark {case.case_id}",
        )
        run = repositories.runs.create(
            user_id=user.user_id,
            case_id=case.case_id,
            agent_version=case.agent_version,
            prompt_version=case.prompt_version,
            tool_profile=case.tool_profile,
            world_profile=case.world_profile,
            failure_profile=case.failure_profile,
            status="running",
            metadata_json={
                "benchmark": {
                    "case_id": case.case_id,
                    "title": case.title,
                    "benchmark_harness_version": self.harness_version,
                    "harness_version": self.harness_version,
                    "metadata": case.metadata,
                }
            },
        )
        for item in case.memory_items:
            repositories.memory.create(
                user_id=user.user_id,
                memory_type=item.memory_type,
                key=item.key,
                value_json=item.value_json,
                text=item.text,
                confidence=item.confidence,
                source_run_id=run.run_id,
                source_langsmith_trace_id=None,
                expires_at=None,
                status=item.status,
            )

        gateway = ToolGateway(
            registry=build_mock_world_registry(case.world_profile),
            tool_events=repositories.tool_events,
            action_ledger=repositories.action_ledger,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
        )
        recorder = ObservabilityRecorder(
            runs=repositories.runs,
            tool_events=repositories.tool_events,
            action_ledger=repositories.action_ledger,
            plans=repositories.plans,
            local_buffer=LocalTraceBuffer(self._trace_path(case.case_id)),
        )
        trace_context = recorder.build_context(run.run_id)

        intent = DeterministicIntentParser().parse(case.user_input)
        query_plan = DeterministicQueryPlanner().build(intent, provider_profile=case.tool_profile)
        collection = QueryPlanExecutor(gateway).execute_initial_calls(
            query_plan,
            run.run_id,
            langsmith_trace_id=trace_context.trace_id,
        )
        enrichment = CandidateEnricher(gateway).enrich(
            query_plan,
            collection,
            langsmith_trace_id=trace_context.trace_id,
        )
        drafts = DeterministicItineraryGenerator().generate(query_plan, enrichment)
        review = FinalReviewGate().review(
            query_plan,
            enrichment,
            drafts,
            pre_confirmation_action_count=self._action_count(run.run_id),
        )
        persistence = ReviewedPlanPersistenceService(repositories.plans)
        persisted = persistence.persist_reviewed_drafts(review, drafts)
        if not persisted.persisted_plans:
            raise RuntimeError("No reviewed plans were persisted for benchmark case.")

        selected = persistence.select_plan(run.run_id, persisted.persisted_plans[0].plan_id)
        HumanConfirmationService(repositories.plans).confirm_plan(
            run.run_id,
            selected.plan_id,
            confirmed_by="benchmark",
            source="locallife-bench",
        )
        execution = DeterministicExecutionWorkflow(repositories.plans, gateway).execute_confirmed_plan(
            run.run_id,
            selected.plan_id,
            langsmith_trace_id=trace_context.trace_id,
        )
        feedback = DeterministicFeedbackWriter(
            plans=repositories.plans,
            runs=repositories.runs,
        ).write_execution_feedback(run.run_id, selected.plan_id)
        observability = recorder.record_run_summary(trace_context)

        tool_events = repositories.tool_events.list_for_run(run.run_id)
        selected_plan = repositories.plans.get_selected_for_run(run.run_id)
        scores = [
            grade_trajectory(case, tool_events),
            grade_plan_quality(selected_plan),
            grade_execution_safety(case, execution),
            grade_feedback(case, feedback),
        ]
        status, overall, failure_reasons = combine_scores(scores)
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            status=status,
            run_id=run.run_id,
            trace_id=trace_context.trace_id,
            scores=scores,
            overall_score=overall,
            tool_event_count=len(tool_events),
            action_count=self._action_count(run.run_id),
            plan_status=getattr(selected_plan, "status", None),
            feedback_status=feedback.status,
            observability_status="recorded" if observability.local_buffer_written else observability.status,
            failure_reasons=failure_reasons,
        )
        report_path = write_case_report(result, self.report_dir)
        return result.model_copy(update={"report_path": str(report_path)})

    def _trace_path(self, case_id: str) -> Path:
        if self.trace_buffer_path is not None:
            return self.trace_buffer_path
        return self.report_dir / f"{case_id}-trace.jsonl"

    def _action_count(self, run_id) -> int:
        statement = select(ActionLedger).where(ActionLedger.run_id == run_id)
        return len(list(self.session.scalars(statement).all()))


class _Repositories:
    def __init__(self, session: Session) -> None:
        self.users = UserRepository(session)
        self.runs = AgentRunRepository(session)
        self.memory = MemoryItemRepository(session)
        self.tool_events = ToolEventRepository(session)
        self.action_ledger = ActionLedgerRepository(session)
        self.plans = PlanRepository(session)
