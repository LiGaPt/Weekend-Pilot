from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from backend.app.benchmark.schemas import BenchmarkRunReport, RecoveryReplayReviewResult


REPO_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_STALE_ARTIFACT = "docs/artifacts/benchmark-all-registered-formal-report.json"
REQUIRED_GITIGNORE_RULES = (
    ".env",
    ".env.*",
    "!.env.example",
    "var/",
    "docs/artifacts/",
    "docs/TASK_WORKFLOW_PROMPTS.md",
    "docs/V1_DEVELOPMENT_REPORT.md",
    "qc",
)
OFFICIAL_TRACKED_DOCS = (
    "README.md",
    "docs/V1_5_REVIEW_EVIDENCE.md",
    "docs/COMPETITION_SUBMISSION_DESIGN.md",
    ".gitignore",
)
README_REQUIRED_SNIPPETS = (
    "docs/V1_5_REVIEW_EVIDENCE.md",
    "python scripts/verify_review_evidence.py",
)
V1_5_REQUIRED_SNIPPETS = (
    "python scripts/run_benchmark_release_gate.py",
    "python scripts/run_benchmark_coverage_gate.py",
    "python scripts/run_formal_verification.py",
    "python scripts/run_recovery_replay_review.py",
    "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
    "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
    "var/formal-benchmarks/latest-all_registered-run-report.json",
    "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    "`docs/artifacts/` is not the source of truth for benchmark or recovery evidence.",
    "Canonical generated evidence stays under `var/`.",
    "python scripts/verify_review_evidence.py",
)
SUBMISSION_REQUIRED_SNIPPETS = (
    "docs/V1_5_REVIEW_EVIDENCE.md",
    "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
    "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
    "var/formal-benchmarks/latest-all_registered-run-report.json",
    "var/recovery-reviews/latest-family_route_failure_v1-review.json",
)


class ReviewEvidenceVerificationError(RuntimeError):
    """Raised when a review-evidence file cannot be read or parsed."""


@dataclass(frozen=True)
class ReviewEvidenceArtifactContract:
    artifact_id: str
    command: str
    relative_path: Path
    artifact_type: Literal["benchmark", "recovery_review"]
    expected_suite_id: str | None = None
    expected_case_id: str | None = None
    expected_status: str = "passed"
    required_nested_values: dict[tuple[str, ...], Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReviewEvidenceVerificationResult:
    status: Literal["passed", "failed"]
    checked_docs: list[str]
    checked_aliases: dict[str, str]
    failures: list[str]


ARTIFACT_CONTRACTS = (
    ReviewEvidenceArtifactContract(
        artifact_id="release_gate_v1",
        command="python scripts/run_benchmark_release_gate.py",
        relative_path=Path("var/formal-benchmarks/latest-release_gate_v1-run-report.json"),
        artifact_type="benchmark",
        expected_suite_id="release_gate_v1",
        required_nested_values={
            ("release_gate_evaluation", "gate_id"): "release_gate_v1",
        },
    ),
    ReviewEvidenceArtifactContract(
        artifact_id="coverage_gate_v1_5",
        command="python scripts/run_benchmark_coverage_gate.py",
        relative_path=Path("var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"),
        artifact_type="benchmark",
        expected_suite_id="all_registered",
        required_nested_values={
            ("coverage_gate_evaluation", "gate_id"): "coverage_gate_v1_5",
            ("coverage_gate_evaluation", "release_blocked"): False,
        },
    ),
    ReviewEvidenceArtifactContract(
        artifact_id="formal_verification",
        command="python scripts/run_formal_verification.py",
        relative_path=Path("var/formal-benchmarks/latest-all_registered-run-report.json"),
        artifact_type="benchmark",
        expected_suite_id="all_registered",
    ),
    ReviewEvidenceArtifactContract(
        artifact_id="recovery_replay_review",
        command="python scripts/run_recovery_replay_review.py",
        relative_path=Path("var/recovery-reviews/latest-family_route_failure_v1-review.json"),
        artifact_type="recovery_review",
        expected_case_id="family_route_failure_v1",
    ),
)


def verify_review_evidence(repo_root: Path | str | None = None) -> ReviewEvidenceVerificationResult:
    root = Path(repo_root) if repo_root is not None else REPO_ROOT
    checked_docs = list(OFFICIAL_TRACKED_DOCS)
    checked_aliases = {contract.artifact_id: contract.relative_path.as_posix() for contract in ARTIFACT_CONTRACTS}
    failures: list[str] = []

    readme_path = root / "README.md"
    v15_path = root / "docs" / "V1_5_REVIEW_EVIDENCE.md"
    submission_path = root / "docs" / "COMPETITION_SUBMISSION_DESIGN.md"
    gitignore_path = root / ".gitignore"

    readme_text = _try_read_text(readme_path, root, failures)
    v15_text = _try_read_text(v15_path, root, failures)
    submission_text = _try_read_text(submission_path, root, failures)
    gitignore_text = _try_read_text(gitignore_path, root, failures)

    if readme_text is not None:
        failures.extend(_missing_snippet_failures(readme_text, readme_path, root, README_REQUIRED_SNIPPETS))
        failures.extend(_forbidden_snippet_failures(readme_text, readme_path, root, (FORBIDDEN_STALE_ARTIFACT,)))
    if v15_text is not None:
        failures.extend(_missing_snippet_failures(v15_text, v15_path, root, V1_5_REQUIRED_SNIPPETS))
        failures.extend(_forbidden_snippet_failures(v15_text, v15_path, root, (FORBIDDEN_STALE_ARTIFACT,)))
    if submission_text is not None:
        failures.extend(_missing_snippet_failures(submission_text, submission_path, root, SUBMISSION_REQUIRED_SNIPPETS))
        failures.extend(_forbidden_snippet_failures(submission_text, submission_path, root, (FORBIDDEN_STALE_ARTIFACT,)))
    if gitignore_text is not None:
        failures.extend(_missing_gitignore_rule_failures(gitignore_text, gitignore_path, root))

    for contract in ARTIFACT_CONTRACTS:
        failures.extend(_validate_artifact_contract(root, contract))

    status: Literal["passed", "failed"] = "passed" if not failures else "failed"
    return ReviewEvidenceVerificationResult(
        status=status,
        checked_docs=checked_docs,
        checked_aliases=checked_aliases,
        failures=failures,
    )


def main(repo_root: Path | str | None = None) -> int:
    try:
        result = verify_review_evidence(repo_root=repo_root)
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Review evidence verification failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if result.status != "passed":
        print(_format_failure_summary(result), file=sys.stderr)
        return 1

    print(_format_success_summary(result))
    return 0


def _format_success_summary(result: ReviewEvidenceVerificationResult) -> str:
    checked_docs = ", ".join(result.checked_docs)
    checked_aliases = ", ".join(result.checked_aliases.values())
    return "\n".join(
        [
            "Review evidence verification passed.",
            f"Checked docs: {checked_docs}",
            f"Checked aliases: {checked_aliases}",
        ]
    )


def _format_failure_summary(result: ReviewEvidenceVerificationResult) -> str:
    lines = ["Review evidence verification failed."]
    lines.extend(f"- {failure}" for failure in result.failures)
    return "\n".join(lines)


def _try_read_text(path: Path, root: Path, failures: list[str]) -> str | None:
    try:
        return _read_text(path)
    except ReviewEvidenceVerificationError as exc:
        failures.append(f"{_relative_label(path, root)}: {exc}")
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReviewEvidenceVerificationError("required file was not found.") from exc
    except OSError as exc:
        raise ReviewEvidenceVerificationError("required file could not be read.") from exc


def _missing_snippet_failures(
    text: str,
    path: Path,
    root: Path,
    snippets: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    label = _relative_label(path, root)
    for snippet in snippets:
        if snippet not in text:
            failures.append(f"{label}: missing required text `{snippet}`.")
    return failures


def _forbidden_snippet_failures(
    text: str,
    path: Path,
    root: Path,
    snippets: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    label = _relative_label(path, root)
    for snippet in snippets:
        if snippet in text:
            failures.append(f"{label}: forbidden stale text `{snippet}` is still present.")
    return failures


def _missing_gitignore_rule_failures(text: str, path: Path, root: Path) -> list[str]:
    lines = {line.strip() for line in text.splitlines()}
    label = _relative_label(path, root)
    failures: list[str] = []
    for rule in REQUIRED_GITIGNORE_RULES:
        if rule not in lines:
            failures.append(f"{label}: missing required ignore rule `{rule}`.")
    return failures


def _validate_artifact_contract(root: Path, contract: ReviewEvidenceArtifactContract) -> list[str]:
    try:
        payload = _read_json(root / contract.relative_path, command=contract.command, root=root)
    except ReviewEvidenceVerificationError as exc:
        return [str(exc)]

    if contract.artifact_type == "benchmark":
        return _validate_benchmark_artifact(root, contract, payload)
    return _validate_recovery_review_artifact(root, contract, payload)


def _validate_benchmark_artifact(
    root: Path,
    contract: ReviewEvidenceArtifactContract,
    payload: dict[str, Any],
) -> list[str]:
    label = contract.relative_path.as_posix()
    failures: list[str] = []

    try:
        report = BenchmarkRunReport.model_validate(payload)
    except ValidationError as exc:
        return [_artifact_failure(label, f"invalid benchmark report schema ({exc.errors()[0]['type']}).", contract.command)]

    if report.run_status != contract.expected_status:
        failures.append(
            _artifact_failure(
                label,
                f"expected run_status={contract.expected_status!r}, got {report.run_status!r}.",
                contract.command,
            )
        )

    summary = report.benchmark_summary
    if summary is None:
        failures.append(_artifact_failure(label, "missing benchmark_summary.", contract.command))
    elif summary.suite_id != contract.expected_suite_id:
        failures.append(
            _artifact_failure(
                label,
                f"expected benchmark_summary.suite_id={contract.expected_suite_id!r}, got {summary.suite_id!r}.",
                contract.command,
            )
        )

    for nested_path, expected_value in contract.required_nested_values.items():
        actual_value = _lookup_nested_value(payload, nested_path)
        if actual_value is _MISSING:
            dotted = ".".join(nested_path)
            failures.append(_artifact_failure(label, f"missing `{dotted}`.", contract.command))
            continue
        if actual_value != expected_value:
            dotted = ".".join(nested_path)
            failures.append(
                _artifact_failure(
                    label,
                    f"expected `{dotted}`={expected_value!r}, got {actual_value!r}.",
                    contract.command,
                )
            )

    return failures


def _validate_recovery_review_artifact(
    root: Path,
    contract: ReviewEvidenceArtifactContract,
    payload: dict[str, Any],
) -> list[str]:
    label = contract.relative_path.as_posix()

    try:
        review = RecoveryReplayReviewResult.model_validate(payload)
    except ValidationError as exc:
        return [_artifact_failure(label, f"invalid recovery review schema ({exc.errors()[0]['type']}).", contract.command)]

    failures: list[str] = []
    if review.status != contract.expected_status:
        failures.append(
            _artifact_failure(
                label,
                f"expected status={contract.expected_status!r}, got {review.status!r}.",
                contract.command,
            )
        )
    if review.case_id != contract.expected_case_id:
        failures.append(
            _artifact_failure(
                label,
                f"expected case_id={contract.expected_case_id!r}, got {review.case_id!r}.",
                contract.command,
            )
        )
    return failures


def _read_json(path: Path, *, command: str, root: Path) -> dict[str, Any]:
    label = _relative_label(path, root)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReviewEvidenceVerificationError(_artifact_failure(label, "artifact file was not found.", command)) from exc
    except OSError as exc:
        raise ReviewEvidenceVerificationError(_artifact_failure(label, "artifact file could not be read.", command)) from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ReviewEvidenceVerificationError(_artifact_failure(label, "artifact file is malformed JSON.", command)) from exc

    if not isinstance(payload, dict):
        raise ReviewEvidenceVerificationError(_artifact_failure(label, "artifact payload must be a JSON object.", command))
    return payload


def _artifact_failure(label: str, detail: str, command: str) -> str:
    return f"{label}: {detail} Re-run `{command}`."


def _relative_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


class _Missing:
    pass


_MISSING = _Missing()


def _lookup_nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current
