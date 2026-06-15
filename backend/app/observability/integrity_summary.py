from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.app.benchmark.schemas import BenchmarkRunReport, BenchmarkStabilityPassKReport, RecoveryReplayReviewResult
from backend.app.observability.schemas import (
    SystemIntegrityBenchmarkSummary,
    SystemIntegrityEvidencePathSummary,
    SystemIntegrityMemoryGovernanceSummary,
    SystemIntegrityRecoveryReplaySummary,
    SystemIntegrityRedactionSummary,
    SystemIntegrityStabilitySummary,
    SystemIntegritySummary,
    SystemIntegrityTimingSummary,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_PATHS: dict[str, Path] = {
    "release_gate_v1": Path("var/formal-benchmarks/latest-release_gate_v1-run-report.json"),
    "coverage_gate_v1_5": Path("var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"),
    "v2_integrity_gate": Path("var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"),
    "formal_verification_all_registered": Path("var/formal-benchmarks/latest-all_registered-run-report.json"),
    "v2_integrity_passk": Path("var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json"),
    "recovery_review_family_route_failure_v1": Path("var/recovery-reviews/latest-family_route_failure_v1-review.json"),
}
REQUIRED_EVIDENCE_IDS = {
    "v2_integrity_gate",
    "formal_verification_all_registered",
    "recovery_review_family_route_failure_v1",
}
OPTIONAL_EVIDENCE_IDS = {
    "release_gate_v1",
    "coverage_gate_v1_5",
    "v2_integrity_passk",
}
FORBIDDEN_KEY_MARKERS = [
    "api_key",
    "token",
    "secret",
    "authorization",
    "prompt",
    "debug_trace",
    "action_id",
    "tool_event_id",
    "idempotency_key",
]


def load_system_integrity_summary() -> SystemIntegritySummary:
    benchmark_summary = _load_benchmark_summary()
    stability_summary = _load_stability_summary()
    memory_summary = _load_memory_governance_summary()
    recovery_summary = _load_recovery_replay_summary()
    timing_summary = _build_timing_summary(benchmark_summary, stability_summary)
    evidence_paths = _build_evidence_paths(
        benchmark_summary=benchmark_summary,
        stability_summary=stability_summary,
        memory_summary=memory_summary,
        recovery_summary=recovery_summary,
    )

    return SystemIntegritySummary(
        status=_derive_top_level_status(
            benchmark_summary=benchmark_summary,
            stability_summary=stability_summary,
            memory_summary=memory_summary,
            recovery_summary=recovery_summary,
        ),
        benchmark_summary=benchmark_summary,
        stability_summary=stability_summary,
        memory_governance_summary=memory_summary,
        recovery_replay_summary=recovery_summary,
        timing_summary=timing_summary,
        redaction_summary=SystemIntegrityRedactionSummary(
            forbidden_key_markers=list(FORBIDDEN_KEY_MARKERS),
        ),
        evidence_paths=evidence_paths,
    )


def _load_benchmark_summary() -> SystemIntegrityBenchmarkSummary:
    evidence_id = "v2_integrity_gate"
    payload = _read_json(evidence_id)
    if payload["status"] != "ready":
        return SystemIntegrityBenchmarkSummary(
            status=payload["status"],
            reason=payload["reason"],
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    try:
        report = BenchmarkRunReport.model_validate(payload["payload"])
    except ValidationError:
        return SystemIntegrityBenchmarkSummary(
            status="invalid",
            reason="Latest v2_integrity gate report is invalid.",
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    evaluation = payload["payload"].get("v2_integrity_gate_evaluation")
    if not isinstance(evaluation, dict):
        return SystemIntegrityBenchmarkSummary(
            status="invalid",
            reason="Latest v2_integrity gate report is missing v2_integrity_gate_evaluation.",
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    summary = report.benchmark_summary
    observed = evaluation.get("observed_coverage") if isinstance(evaluation.get("observed_coverage"), dict) else {}
    return SystemIntegrityBenchmarkSummary(
        status="ready",
        suite_id=summary.suite_id if summary is not None else None,
        gate_id=evaluation.get("gate_id") if isinstance(evaluation.get("gate_id"), str) else None,
        run_status=report.run_status,
        release_blocked=evaluation.get("release_blocked") if isinstance(evaluation.get("release_blocked"), bool) else None,
        case_count=summary.case_count if summary is not None else None,
        passed_count=summary.passed_count if summary is not None else None,
        failed_count=summary.failed_count if summary is not None else None,
        error_count=summary.error_count if summary is not None else None,
        overall_score=summary.overall_score if summary is not None else None,
        blocking_failures=[item for item in evaluation.get("blocking_failures", []) if isinstance(item, str)],
        integrity_coverage_summary=_coerce_count_map(observed.get("integrity_coverage_summary")),
        memory_mode_counts=_coerce_count_map(observed.get("memory_mode_counts")),
        conversation_mode_counts=_coerce_count_map(observed.get("conversation_mode_counts")),
        failure_mode_counts=_coerce_count_map(observed.get("failure_mode_counts")),
        latest_report_path=_display_path(_path_for(evidence_id)),
    )


def _load_stability_summary() -> SystemIntegrityStabilitySummary:
    evidence_id = "v2_integrity_passk"
    payload = _read_json(evidence_id)
    if payload["status"] != "ready":
        return SystemIntegrityStabilitySummary(
            status=payload["status"],
            reason=payload["reason"],
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    try:
        report = BenchmarkStabilityPassKReport.model_validate(payload["payload"])
    except ValidationError:
        return SystemIntegrityStabilitySummary(
            status="invalid",
            reason="Latest v2_integrity pass-k report is invalid.",
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    return SystemIntegrityStabilitySummary(
        status="ready",
        suite_id=report.suite_id,
        gate_id=report.gate_id,
        metric_version=report.metric_version,
        requested_run_count=report.requested_run_count,
        executed_run_count=report.executed_run_count,
        window_size=report.window_size,
        window_count=report.window_count,
        discarded_tail_run_count=report.discarded_tail_run_count,
        success_count=report.success_count,
        failure_count=report.failure_count,
        error_count=report.error_count,
        success_at_1=report.success_at_1,
        pass_at_4=report.pass_at_4,
        pass_pow_4=report.pass_pow_4,
        stable_enough=report.pass_pow_4 >= 1.0 if report.window_count > 0 else False,
        has_required_window=report.window_count >= 1,
        latest_report_path=_display_path(_path_for(evidence_id)),
    )


def _load_memory_governance_summary() -> SystemIntegrityMemoryGovernanceSummary:
    evidence_id = "formal_verification_all_registered"
    payload = _read_json(evidence_id)
    if payload["status"] != "ready":
        return SystemIntegrityMemoryGovernanceSummary(
            status=payload["status"],
            reason=payload["reason"],
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    try:
        report = BenchmarkRunReport.model_validate(payload["payload"])
    except ValidationError:
        return SystemIntegrityMemoryGovernanceSummary(
            status="invalid",
            reason="Latest all_registered report is invalid.",
            latest_report_path=_display_path(_path_for(evidence_id)),
        )

    case_ids: list[str] = []
    failing_case_ids: list[str] = []
    passed = 0
    failed = 0
    errored = 0
    for case_result in report.case_results:
        memory_score = next((score for score in case_result.scores if score.name == "memory_governance"), None)
        if memory_score is None:
            continue
        case_ids.append(case_result.case_id)
        if case_result.status == "passed":
            passed += 1
        elif case_result.status == "failed":
            failed += 1
            failing_case_ids.append(case_result.case_id)
        else:
            errored += 1
            failing_case_ids.append(case_result.case_id)

    return SystemIntegrityMemoryGovernanceSummary(
        status="ready",
        source_suite_id=report.benchmark_summary.suite_id if report.benchmark_summary is not None else None,
        memory_case_count=len(case_ids),
        passed_case_count=passed,
        failed_case_count=failed,
        error_case_count=errored,
        all_memory_cases_passed=len(case_ids) > 0 and failed == 0 and errored == 0,
        case_ids=case_ids,
        failing_case_ids=failing_case_ids,
        latest_report_path=_display_path(_path_for(evidence_id)),
    )


def _load_recovery_replay_summary() -> SystemIntegrityRecoveryReplaySummary:
    evidence_id = "recovery_review_family_route_failure_v1"
    payload = _read_json(evidence_id)
    if payload["status"] != "ready":
        return SystemIntegrityRecoveryReplaySummary(
            status=payload["status"],
            reason=payload["reason"],
            latest_review_path=_display_path(_path_for(evidence_id)),
        )

    try:
        review = RecoveryReplayReviewResult.model_validate(payload["payload"])
    except ValidationError:
        return SystemIntegrityRecoveryReplaySummary(
            status="invalid",
            reason="Latest canonical recovery replay review is invalid.",
            latest_review_path=_display_path(_path_for(evidence_id)),
        )

    passed_check_count = sum(1 for check in review.checks if check.passed)
    recovery_review = review.recovery_review
    return SystemIntegrityRecoveryReplaySummary(
        status="ready",
        case_id=review.case_id,
        review_status=review.status,
        check_count=len(review.checks),
        passed_check_count=passed_check_count,
        failed_check_count=len(review.checks) - passed_check_count,
        latest_review_path=_display_path(_path_for(evidence_id)),
        source_report_path=review.source_report_path,
        replay_report_path=review.replay_report_path,
        recovery_actions=list(recovery_review.recovery_actions) if recovery_review is not None else [],
        attempt_count=recovery_review.attempt_count if recovery_review is not None else None,
        max_attempts=recovery_review.max_attempts if recovery_review is not None else None,
    )


def _build_timing_summary(
    benchmark_summary: SystemIntegrityBenchmarkSummary,
    stability_summary: SystemIntegrityStabilitySummary,
) -> SystemIntegrityTimingSummary:
    payload = _read_json("v2_integrity_gate")
    benchmark_timing_summary = None
    if payload["status"] == "ready":
        raw_summary = payload["payload"].get("benchmark_summary")
        if isinstance(raw_summary, dict) and raw_summary.get("benchmark_timing_summary") is not None:
            benchmark_timing_summary = raw_summary.get("benchmark_timing_summary")

    if benchmark_timing_summary is not None:
        return SystemIntegrityTimingSummary(
            status="ready",
            benchmark_timing_summary_present=True,
            benchmark_timing_summary=benchmark_timing_summary,
            stability_window_size=stability_summary.window_size,
            stability_executed_run_count=stability_summary.executed_run_count,
        )
    if stability_summary.status == "ready":
        return SystemIntegrityTimingSummary(
            status="partial",
            reason="Benchmark timing summary is missing, but stability timing metadata is available.",
            benchmark_timing_summary_present=False,
            stability_window_size=stability_summary.window_size,
            stability_executed_run_count=stability_summary.executed_run_count,
        )
    return SystemIntegrityTimingSummary(
        status="missing",
        reason="No timing evidence is available.",
        benchmark_timing_summary_present=False,
    )


def _build_evidence_paths(
    *,
    benchmark_summary: SystemIntegrityBenchmarkSummary,
    stability_summary: SystemIntegrityStabilitySummary,
    memory_summary: SystemIntegrityMemoryGovernanceSummary,
    recovery_summary: SystemIntegrityRecoveryReplaySummary,
) -> list[SystemIntegrityEvidencePathSummary]:
    section_status_by_id = {
        "v2_integrity_gate": benchmark_summary.status,
        "formal_verification_all_registered": memory_summary.status,
        "v2_integrity_passk": stability_summary.status,
        "recovery_review_family_route_failure_v1": recovery_summary.status,
        "release_gate_v1": "ready" if _path_for("release_gate_v1").exists() else "missing",
        "coverage_gate_v1_5": "ready" if _path_for("coverage_gate_v1_5").exists() else "missing",
    }
    return [
        SystemIntegrityEvidencePathSummary(
            evidence_id=evidence_id,
            path=_display_path(path),
            exists=_path_for(evidence_id).exists(),
            required_for_summary=evidence_id in REQUIRED_EVIDENCE_IDS,
            status=section_status_by_id.get(evidence_id, "missing"),
        )
        for evidence_id, path in EVIDENCE_PATHS.items()
    ]


def _derive_top_level_status(
    *,
    benchmark_summary: SystemIntegrityBenchmarkSummary,
    stability_summary: SystemIntegrityStabilitySummary,
    memory_summary: SystemIntegrityMemoryGovernanceSummary,
    recovery_summary: SystemIntegrityRecoveryReplaySummary,
) -> str:
    required_sections = [
        benchmark_summary.status,
        memory_summary.status,
        recovery_summary.status,
    ]
    optional_sections = [stability_summary.status]
    if any(status == "invalid" for status in required_sections + optional_sections):
        return "invalid_evidence"
    if any(status == "missing" for status in required_sections):
        return "missing_evidence"
    if all(status == "ready" for status in required_sections + optional_sections):
        return "ready"
    return "degraded"


def _read_json(evidence_id: str) -> dict[str, Any]:
    path = _path_for(evidence_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"status": "missing", "reason": f"{evidence_id} evidence is missing.", "payload": None}
    except (OSError, json.JSONDecodeError):
        return {"status": "invalid", "reason": f"{evidence_id} evidence is invalid.", "payload": None}
    if not isinstance(payload, dict):
        return {"status": "invalid", "reason": f"{evidence_id} evidence is invalid.", "payload": None}
    return {"status": "ready", "reason": None, "payload": payload}


def _path_for(evidence_id: str) -> Path:
    raw_path = EVIDENCE_PATHS[evidence_id]
    return raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path


def _display_path(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    if "var" in path.parts:
        return Path(*path.parts[path.parts.index("var") :]).as_posix()
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def _coerce_count_map(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(key): int(count) for key, count in value.items() if isinstance(count, int)}
    return {}
