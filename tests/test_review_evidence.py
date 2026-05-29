from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.benchmark.review_evidence import main, verify_review_evidence


@pytest.fixture()
def repo_directory() -> Path:
    directory = Path("var/test-review-evidence") / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    try:
        yield directory
    finally:
        for path in sorted(directory.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if directory.exists():
            directory.rmdir()


def test_verify_review_evidence_passes_for_aligned_repo(repo_directory: Path) -> None:
    _write_repo_fixture(repo_directory)

    result = verify_review_evidence(repo_directory)

    assert result.status == "passed"
    assert result.failures == []
    assert result.checked_docs == [
        "README.md",
        "docs/V1_5_REVIEW_EVIDENCE.md",
        "docs/COMPETITION_SUBMISSION_DESIGN.md",
        ".gitignore",
    ]
    assert result.checked_aliases == {
        "release_gate_v1": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
        "coverage_gate_v1_5": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
        "formal_verification": "var/formal-benchmarks/latest-all_registered-run-report.json",
        "recovery_replay_review": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
    }


def test_verify_review_evidence_fails_when_v1_5_doc_is_missing_required_command(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        v15_doc_overrides={
            "omit_commands": ["python scripts/run_recovery_replay_review.py"],
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any("docs/V1_5_REVIEW_EVIDENCE.md" in failure for failure in result.failures)
    assert any("python scripts/run_recovery_replay_review.py" in failure for failure in result.failures)


def test_verify_review_evidence_fails_when_submission_doc_reintroduces_stale_artifact_path(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        submission_doc_overrides={
            "append_lines": ["Legacy artifact: docs/artifacts/benchmark-all-registered-formal-report.json"],
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any("docs/COMPETITION_SUBMISSION_DESIGN.md" in failure for failure in result.failures)
    assert any("docs/artifacts/benchmark-all-registered-formal-report.json" in failure for failure in result.failures)


def test_verify_review_evidence_fails_when_gitignore_is_missing_required_rule(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        gitignore_overrides={
            "omit_rules": ["qc"],
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any(".gitignore" in failure for failure in result.failures)
    assert any("qc" in failure for failure in result.failures)


def test_verify_review_evidence_fails_when_release_gate_alias_has_wrong_suite_id(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        alias_overrides={
            "release_gate_suite_id": "all_registered",
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any("latest-release_gate_v1-run-report.json" in failure for failure in result.failures)
    assert any("release_gate_v1" in failure for failure in result.failures)


def test_verify_review_evidence_fails_when_release_gate_alias_is_missing_gate_evaluation(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        alias_overrides={
            "include_release_gate_evaluation": False,
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any("latest-release_gate_v1-run-report.json" in failure for failure in result.failures)
    assert any("release_gate_evaluation" in failure for failure in result.failures)


def test_verify_review_evidence_fails_when_recovery_review_alias_has_wrong_case_id(repo_directory: Path) -> None:
    _write_repo_fixture(
        repo_directory,
        alias_overrides={
            "recovery_case_id": "wrong_case_v1",
        },
    )

    result = verify_review_evidence(repo_directory)

    assert result.status == "failed"
    assert any("latest-family_route_failure_v1-review.json" in failure for failure in result.failures)
    assert any("family_route_failure_v1" in failure for failure in result.failures)


def test_main_returns_non_zero_and_prints_failures_for_invalid_repo(
    repo_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_repo_fixture(
        repo_directory,
        v15_doc_overrides={
            "omit_commands": ["python scripts/run_formal_verification.py"],
        },
    )

    exit_code = main(repo_root=repo_directory)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Review evidence verification failed." in captured.err
    assert "python scripts/run_formal_verification.py" in captured.err


def _write_repo_fixture(
    repo_root: Path,
    *,
    v15_doc_overrides: dict[str, object] | None = None,
    submission_doc_overrides: dict[str, object] | None = None,
    gitignore_overrides: dict[str, object] | None = None,
    alias_overrides: dict[str, object] | None = None,
) -> None:
    v15_doc_overrides = v15_doc_overrides or {}
    submission_doc_overrides = submission_doc_overrides or {}
    gitignore_overrides = gitignore_overrides or {}
    alias_overrides = alias_overrides or {}

    (repo_root / "docs").mkdir(parents=True, exist_ok=True)
    (repo_root / "var" / "formal-benchmarks").mkdir(parents=True, exist_ok=True)
    (repo_root / "var" / "recovery-reviews").mkdir(parents=True, exist_ok=True)

    readme_lines = [
        "# WeekendPilot",
        "",
        "For the pinned V1.5 reviewer evidence package, including the exact review commands, canonical latest aliases, and tracked-versus-ignored ownership rules, see `docs/V1_5_REVIEW_EVIDENCE.md`.",
        "Run `python scripts/verify_review_evidence.py` before submission to validate the official docs and current latest aliases together.",
    ]
    (repo_root / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")

    commands = [
        "python scripts/run_benchmark_release_gate.py",
        "python scripts/run_benchmark_coverage_gate.py",
        "python scripts/run_formal_verification.py",
        "python scripts/run_recovery_replay_review.py",
    ]
    omitted_commands = set(v15_doc_overrides.get("omit_commands", []))
    filtered_commands = [command for command in commands if command not in omitted_commands]
    v15_lines = [
        "# V1.5 Review Evidence",
        "",
        "## Canonical Review Commands",
        "",
        *[f"- `{command}`" for command in filtered_commands],
        "",
        "## Canonical Latest Aliases",
        "",
        "- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`",
        "- `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`",
        "- `var/formal-benchmarks/latest-all_registered-run-report.json`",
        "- `var/recovery-reviews/latest-family_route_failure_v1-review.json`",
        "",
        "## Ownership",
        "",
        "- `docs/artifacts/` is not the source of truth for benchmark or recovery evidence.",
        "- Canonical generated evidence stays under `var/`.",
        "- Official tracked docs include `docs/COMPETITION_SUBMISSION_DESIGN.md` and `docs/V1_5_REVIEW_EVIDENCE.md`.",
        "",
        "## Verification",
        "",
        "- Run `python scripts/verify_review_evidence.py` before submission.",
    ]
    (repo_root / "docs" / "V1_5_REVIEW_EVIDENCE.md").write_text("\n".join(v15_lines) + "\n", encoding="utf-8")

    submission_lines = [
        "# WeekendPilot 参赛提交版设计说明",
        "",
        "正式评审请以 `docs/V1_5_REVIEW_EVIDENCE.md` 为 reviewer 入口。",
        "- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`",
        "- `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`",
        "- `var/formal-benchmarks/latest-all_registered-run-report.json`",
        "- `var/recovery-reviews/latest-family_route_failure_v1-review.json`",
        "- `docs/artifacts/` 不是 benchmark 或 recovery evidence 的 source of truth；正式引用应始终指向 `var/` 下的 canonical latest aliases。",
    ]
    submission_lines.extend(submission_doc_overrides.get("append_lines", []))
    (repo_root / "docs" / "COMPETITION_SUBMISSION_DESIGN.md").write_text(
        "\n".join(submission_lines) + "\n",
        encoding="utf-8",
    )

    gitignore_rules = [
        ".env",
        ".env.*",
        "!.env.example",
        "var/",
        "docs/artifacts/",
        "docs/TASK_WORKFLOW_PROMPTS.md",
        "docs/V1_DEVELOPMENT_REPORT.md",
        "qc",
    ]
    omitted_rules = set(gitignore_overrides.get("omit_rules", []))
    filtered_rules = [rule for rule in gitignore_rules if rule not in omitted_rules]
    (repo_root / ".gitignore").write_text("\n".join(filtered_rules) + "\n", encoding="utf-8")

    release_gate_payload = _build_benchmark_report(
        suite_id=str(alias_overrides.get("release_gate_suite_id", "release_gate_v1")),
        suite_title="Benchmark release gate v1",
        case_count=15,
        passed_count=15,
        report_path="var/formal-benchmarks/release-gate-v1-placeholder/suite-release_gate_v1-run-report.json",
    )
    if bool(alias_overrides.get("include_release_gate_evaluation", True)):
        release_gate_payload["release_gate_evaluation"] = {
            "gate_id": "release_gate_v1",
            "release_blocked": False,
        }
    _write_json(
        repo_root / "var" / "formal-benchmarks" / "latest-release_gate_v1-run-report.json",
        release_gate_payload,
    )

    coverage_gate_payload = _build_benchmark_report(
        suite_id="all_registered",
        suite_title="All registered benchmark suite",
        case_count=21,
        passed_count=21,
        report_path="var/formal-benchmarks/formal-placeholder/suite-all_registered-run-report.json",
    )
    coverage_gate_payload["coverage_gate_evaluation"] = {
        "gate_id": "coverage_gate_v1_5",
        "release_blocked": False,
    }
    _write_json(
        repo_root / "var" / "formal-benchmarks" / "latest-coverage_gate_v1_5-run-report.json",
        coverage_gate_payload,
    )

    formal_payload = _build_benchmark_report(
        suite_id="all_registered",
        suite_title="All registered benchmark suite",
        case_count=21,
        passed_count=21,
        report_path="var/formal-benchmarks/formal-placeholder/suite-all_registered-run-report.json",
    )
    _write_json(
        repo_root / "var" / "formal-benchmarks" / "latest-all_registered-run-report.json",
        formal_payload,
    )

    recovery_payload = {
        "schema_version": "weekendpilot_recovery_replay_review_v1",
        "status": str(alias_overrides.get("recovery_status", "passed")),
        "case_id": str(alias_overrides.get("recovery_case_id", "family_route_failure_v1")),
        "run_directory": "var/recovery-reviews/recovery-review-placeholder",
        "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json",
        "checks": [],
    }
    _write_json(
        repo_root / "var" / "recovery-reviews" / "latest-family_route_failure_v1-review.json",
        recovery_payload,
    )


def _build_benchmark_report(
    *,
    suite_id: str,
    suite_title: str,
    case_count: int,
    passed_count: int,
    report_path: str,
) -> dict[str, object]:
    return {
        "schema_version": "weekendpilot_benchmark_run_v1",
        "run_status": "passed",
        "case_results": [],
        "passed_count": passed_count,
        "failed_count": 0,
        "error_count": 0,
        "overall_score": 1.0,
        "benchmark_summary": {
            "schema_version": "weekendpilot_benchmark_summary_v1",
            "suite_id": suite_id,
            "suite_title": suite_title,
            "run_status": "passed",
            "case_count": case_count,
            "passed_count": passed_count,
            "failed_count": 0,
            "error_count": 0,
            "overall_score": 1.0,
            "matrix_summary": {
                "schema_version": "weekendpilot_benchmark_case_matrix_v1",
                "case_count": case_count,
                "level_counts": {"L1": 3, "L2": 8, "L3": 4},
                "tool_profile_counts": {"mock_world": case_count},
                "failure_mode_counts": {"none": case_count},
                "tag_counts": {"review_evidence": 1},
            },
        },
        "report_path": report_path,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
