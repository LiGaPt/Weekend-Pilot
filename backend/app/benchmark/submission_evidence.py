from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from backend.app.benchmark.schemas import BenchmarkRunReport, BenchmarkStabilityPassKReport, RecoveryReplayReviewResult


SubmissionEvidenceKind = Literal["benchmark_run", "benchmark_stability", "recovery_review"]


@dataclass(frozen=True)
class SubmissionEvidenceContract:
    evidence_id: str
    command: str
    relative_path: Path
    artifact_kind: SubmissionEvidenceKind
    proves: str
    expected_status: str = "passed"
    expected_suite_id: str | None = None
    expected_gate_id: str | None = None
    expected_case_id: str | None = None
    expected_metric_version: str | None = None
    required_nested_values: dict[tuple[str, ...], Any] = field(default_factory=dict)


SUBMISSION_EVIDENCE_CONTRACTS: tuple[SubmissionEvidenceContract, ...] = (
    SubmissionEvidenceContract(
        evidence_id="release_gate_v1",
        command="python scripts/run_benchmark_release_gate.py",
        relative_path=Path("var/formal-benchmarks/latest-release_gate_v1-run-report.json"),
        artifact_kind="benchmark_run",
        proves="Current formal release gate baseline",
        expected_suite_id="release_gate_v1",
        expected_gate_id="release_gate_v1",
        required_nested_values={
            ("release_gate_evaluation", "gate_id"): "release_gate_v1",
        },
    ),
    SubmissionEvidenceContract(
        evidence_id="coverage_gate_v1_5",
        command="python scripts/run_benchmark_coverage_gate.py",
        relative_path=Path("var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"),
        artifact_kind="benchmark_run",
        proves="Breadth and diversity coverage gate",
        expected_suite_id="all_registered",
        expected_gate_id="coverage_gate_v1_5",
        required_nested_values={
            ("coverage_gate_evaluation", "gate_id"): "coverage_gate_v1_5",
            ("coverage_gate_evaluation", "release_blocked"): False,
        },
    ),
    SubmissionEvidenceContract(
        evidence_id="v2_integrity_gate",
        command="python scripts/run_benchmark_v2_integrity_gate.py",
        relative_path=Path("var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"),
        artifact_kind="benchmark_run",
        proves="V2 integrity benchmark gate",
        expected_suite_id="v2_integrity",
        expected_gate_id="v2_integrity_gate",
        required_nested_values={
            ("v2_integrity_gate_evaluation", "gate_id"): "v2_integrity_gate",
            ("v2_integrity_gate_evaluation", "suite_id"): "v2_integrity",
            ("v2_integrity_gate_evaluation", "release_blocked"): False,
        },
    ),
    SubmissionEvidenceContract(
        evidence_id="v2_integrity_passk",
        command="python scripts/run_benchmark_stability_passk.py --suite v2_integrity --runs 4",
        relative_path=Path("var/formal-benchmarks/stability/latest-v2_integrity-passk-v0-report.json"),
        artifact_kind="benchmark_stability",
        proves="V2 integrity repeated-run stability metrics",
        expected_suite_id="v2_integrity",
        expected_gate_id="v2_integrity_gate",
        expected_metric_version="passk_v0",
    ),
    SubmissionEvidenceContract(
        evidence_id="formal_verification_all_registered",
        command="python scripts/run_formal_verification.py",
        relative_path=Path("var/formal-benchmarks/latest-all_registered-run-report.json"),
        artifact_kind="benchmark_run",
        proves="Full registered-case formal verification",
        expected_suite_id="all_registered",
    ),
    SubmissionEvidenceContract(
        evidence_id="recovery_review_family_route_failure_v1",
        command="python scripts/run_recovery_replay_review.py",
        relative_path=Path("var/recovery-reviews/latest-family_route_failure_v1-review.json"),
        artifact_kind="recovery_review",
        proves="Failure-recovery replay review",
        expected_case_id="family_route_failure_v1",
    ),
)


def read_submission_evidence_payload(repo_root: Path, contract: SubmissionEvidenceContract) -> dict[str, Any]:
    payload = json.loads((repo_root / contract.relative_path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def summarize_submission_evidence(payload: dict[str, Any], contract: SubmissionEvidenceContract) -> str:
    if contract.artifact_kind == "benchmark_run":
        try:
            report = BenchmarkRunReport.model_validate(payload)
        except ValidationError:
            return "status=invalid"

        suite_id = report.benchmark_summary.suite_id if report.benchmark_summary is not None else "unknown"
        summary = f"run_status={report.run_status}, suite_id={suite_id}"
        gate_id = _lookup_nested_value(payload, ("v2_integrity_gate_evaluation", "gate_id"))
        if contract.evidence_id == "v2_integrity_gate" and isinstance(gate_id, str):
            summary = f"{summary}, gate_id={gate_id}"
        return summary

    if contract.artifact_kind == "benchmark_stability":
        try:
            report = BenchmarkStabilityPassKReport.model_validate(payload)
        except ValidationError:
            return "status=invalid"
        return (
            f"suite_id={report.suite_id}, gate_id={report.gate_id}, "
            f"metric_version={report.metric_version}"
        )

    try:
        review = RecoveryReplayReviewResult.model_validate(payload)
    except ValidationError:
        return "status=invalid"
    return f"status={review.status}, case_id={review.case_id}"


def _lookup_nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
