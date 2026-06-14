from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.app.benchmark.formal_verification import (
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    run_formal_verification,
)
from backend.app.benchmark.schemas import BenchmarkRunReport


COVERAGE_GATE_ID = "coverage_gate_v1_5"
COVERAGE_SUITE_ID = "all_registered"
LATEST_REPORT_FILENAME = f"latest-{COVERAGE_GATE_ID}-run-report.json"
DEFAULT_MAX_SCENARIO_SHARE = 0.6
DEFAULT_MAX_WORLD_PROFILE_SHARE = 0.6
DEFAULT_MAX_NON_FAILURE_SHARE = 0.9
MINIMUM_CASE_COUNT = 28
SCHEMA_VERSION = "weekendpilot_coverage_gate_evaluation_v1"
SCENARIO_BUCKET_MINIMUMS = {
    "couple": 1,
    "elder": 1,
    "family": 5,
    "friends": 2,
    "mixed": 3,
    "solo": 2,
    "unknown": 2,
}
WORLD_PROFILE_MINIMUMS = {
    "budget_lite": 2,
    "couple_afternoon": 1,
    "elder_afternoon": 1,
    "family_afternoon": 5,
    "friends_gathering": 2,
    "rainy_day_fallback": 3,
    "solo_afternoon": 2,
}
FAILURE_MODE_MINIMUMS = {
    "route_unavailable": 1,
    "route_and_dining_unavailable": 1,
    "ticket_sold_out_and_bad_weather": 1,
    "ticket_sold_out_and_route_unavailable": 1,
    "queue_closed_and_budget_constraint": 1,
    "table_unavailable_and_replan_required": 1,
}
CONSTRAINT_TAG_MINIMUMS = {
    "budget_limited": 2,
    "casual_dining": 2,
    "conversation_continuation": 2,
    "date_friendly": 1,
    "elder_friendly": 1,
    "friends_group": 2,
    "memory_governance": 2,
    "rainy_day": 3,
    "robustness_case": 4,
}


class BenchmarkCoverageGateError(RuntimeError):
    """Raised when the benchmark coverage gate cannot finish successfully."""


@dataclass(frozen=True)
class BenchmarkCoverageGateResult:
    gate_id: str
    suite_id: str | None
    release_blocked: bool
    blocking_failures: list[str]
    run_status: str
    case_count: int
    passed_count: int
    failed_count: int
    error_count: int
    overall_score: float
    run_directory: Path
    suite_report_path: Path
    latest_report_path: Path
    scenario_bucket_counts: dict[str, int]
    world_profile_counts: dict[str, int]
    failure_mode_counts: dict[str, int]
    constraint_tag_case_counts: dict[str, int]
    share_checks: dict[str, dict[str, Any]]


def run_benchmark_coverage_gate(
    output_root: Path | str | None = None,
    *,
    start_services: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> BenchmarkCoverageGateResult:
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT_ROOT
    latest_report_path = root / LATEST_REPORT_FILENAME

    try:
        formal_result = run_formal_verification(
            output_root=root,
            start_services=start_services,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
    except Exception as exc:
        raise BenchmarkCoverageGateError(f"Formal verification failed: {exc}") from exc

    suite_report_path = formal_result.suite_report_path
    raw_payload, report = _load_suite_report(suite_report_path)

    summary = report.benchmark_summary
    suite_id = summary.suite_id if summary is not None else formal_result.suite_id
    run_status = report.run_status
    case_count = summary.case_count if summary is not None else formal_result.case_count
    passed_count = summary.passed_count if summary is not None else formal_result.passed_count
    failed_count = summary.failed_count if summary is not None else formal_result.failed_count
    error_count = summary.error_count if summary is not None else formal_result.error_count
    overall_score = summary.overall_score if summary is not None else formal_result.overall_score

    blocking_failures: list[str] = []
    scenario_bucket_counts: dict[str, int] = {}
    world_profile_counts: dict[str, int] = {}
    failure_mode_counts: dict[str, int] = {}
    constraint_tag_case_counts: dict[str, int] = {}

    if suite_id != COVERAGE_SUITE_ID:
        blocking_failures.append(f"Expected suite_id={COVERAGE_SUITE_ID!r}, got {suite_id!r}.")
    if run_status != "passed":
        blocking_failures.append(f"Expected run_status='passed', got {run_status!r}.")
    if failed_count != 0:
        blocking_failures.append(f"Expected failed_count=0, got {failed_count}.")
    if error_count != 0:
        blocking_failures.append(f"Expected error_count=0, got {error_count}.")
    if case_count < MINIMUM_CASE_COUNT:
        blocking_failures.append(f"Expected case_count>={MINIMUM_CASE_COUNT}, got {case_count}.")

    if summary is None:
        blocking_failures.append("Missing benchmark_summary.")
    else:
        matrix_summary = summary.matrix_summary
        outcome_rollup = summary.outcome_rollup

        if matrix_summary is None:
            blocking_failures.append("Missing benchmark_summary.matrix_summary.")
        else:
            scenario_bucket_counts = _coerce_count_map(matrix_summary.scenario_bucket_counts)
            world_profile_counts = _coerce_count_map(matrix_summary.world_profile_counts)
            failure_mode_counts = _coerce_count_map(matrix_summary.failure_mode_counts)
            tool_profile_counts = _coerce_count_map(matrix_summary.tool_profile_counts)
            expected_tool_profile_counts = {"mock_world": case_count}
            if tool_profile_counts != expected_tool_profile_counts:
                blocking_failures.append(
                    "Expected matrix_summary.tool_profile_counts="
                    f"{expected_tool_profile_counts}, got {tool_profile_counts}."
                )

        raw_constraint_tag_outcomes = _raw_constraint_tag_outcomes(raw_payload)

        if outcome_rollup is None:
            blocking_failures.append("Missing benchmark_summary.outcome_rollup.")
        else:
            if raw_constraint_tag_outcomes is None:
                blocking_failures.append("Missing benchmark_summary.outcome_rollup.constraint_tag_outcomes.")
            else:
                constraint_tag_case_counts = _coerce_constraint_tag_counts(outcome_rollup.constraint_tag_outcomes)

    blocking_failures.extend(
        _evaluate_minimums(
            "scenario_bucket_counts",
            scenario_bucket_counts,
            SCENARIO_BUCKET_MINIMUMS,
        )
    )
    blocking_failures.extend(
        _evaluate_minimums(
            "world_profile_counts",
            world_profile_counts,
            WORLD_PROFILE_MINIMUMS,
        )
    )
    blocking_failures.extend(
        _evaluate_minimums(
            "failure_mode_counts",
            failure_mode_counts,
            FAILURE_MODE_MINIMUMS,
        )
    )
    blocking_failures.extend(
        _evaluate_minimums(
            "constraint_tag_case_counts",
            constraint_tag_case_counts,
            CONSTRAINT_TAG_MINIMUMS,
        )
    )

    share_checks = _build_share_checks(
        case_count=case_count,
        scenario_bucket_counts=scenario_bucket_counts,
        world_profile_counts=world_profile_counts,
        failure_mode_counts=failure_mode_counts,
    )
    blocking_failures.extend(_share_check_failures(share_checks))

    evaluation_payload = _build_coverage_gate_evaluation(
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        case_count=case_count,
        scenario_bucket_counts=scenario_bucket_counts,
        world_profile_counts=world_profile_counts,
        failure_mode_counts=failure_mode_counts,
        constraint_tag_case_counts=constraint_tag_case_counts,
        share_checks=share_checks,
    )

    report_enriched = False
    enrichment_error = _write_coverage_gate_evaluation(suite_report_path, evaluation_payload)
    if enrichment_error is not None:
        blocking_failures.append(enrichment_error)
    else:
        report_enriched = True

    if not blocking_failures:
        alias_error = _refresh_latest_alias(suite_report_path, latest_report_path)
        if alias_error is not None:
            blocking_failures.append(alias_error)

    if report_enriched and blocking_failures != evaluation_payload["blocking_failures"]:
        final_payload = _build_coverage_gate_evaluation(
            suite_id=suite_id,
            release_blocked=bool(blocking_failures),
            blocking_failures=blocking_failures,
            case_count=case_count,
            scenario_bucket_counts=scenario_bucket_counts,
            world_profile_counts=world_profile_counts,
            failure_mode_counts=failure_mode_counts,
            constraint_tag_case_counts=constraint_tag_case_counts,
            share_checks=share_checks,
        )
        follow_up_error = _write_coverage_gate_evaluation(suite_report_path, final_payload)
        if follow_up_error is not None:
            blocking_failures.append(follow_up_error)

    return BenchmarkCoverageGateResult(
        gate_id=COVERAGE_GATE_ID,
        suite_id=suite_id,
        release_blocked=bool(blocking_failures),
        blocking_failures=blocking_failures,
        run_status=run_status,
        case_count=case_count,
        passed_count=passed_count,
        failed_count=failed_count,
        error_count=error_count,
        overall_score=overall_score,
        run_directory=formal_result.run_directory,
        suite_report_path=suite_report_path,
        latest_report_path=latest_report_path,
        scenario_bucket_counts=scenario_bucket_counts,
        world_profile_counts=world_profile_counts,
        failure_mode_counts=failure_mode_counts,
        constraint_tag_case_counts=constraint_tag_case_counts,
        share_checks=share_checks,
    )


def main() -> int:
    try:
        result = run_benchmark_coverage_gate()
    except BenchmarkCoverageGateError as exc:
        print(f"Benchmark coverage gate failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Benchmark coverage gate failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if result.release_blocked:
        print(_format_failure_summary(result), file=sys.stderr)
        return 1

    print(_format_success_summary(result))
    return 0


def _load_suite_report(suite_report_path: Path) -> tuple[dict[str, Any], BenchmarkRunReport]:
    try:
        raw_payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkCoverageGateError(f"Could not read suite report: {suite_report_path}") from exc

    try:
        report = BenchmarkRunReport.model_validate(raw_payload)
    except ValidationError as exc:
        raise BenchmarkCoverageGateError(f"Could not validate suite report: {suite_report_path}") from exc

    return raw_payload, report


def _evaluate_minimums(
    label: str,
    observed_counts: dict[str, int],
    required_counts: dict[str, int],
) -> list[str]:
    failures: list[str] = []
    for key, minimum in required_counts.items():
        observed = int(observed_counts.get(key, 0))
        if observed < minimum:
            failures.append(f"Expected {label}['{key}']>={minimum}, got {observed}.")
    return failures


def _build_share_checks(
    *,
    case_count: int,
    scenario_bucket_counts: dict[str, int],
    world_profile_counts: dict[str, int],
    failure_mode_counts: dict[str, int],
) -> dict[str, dict[str, Any]]:
    return {
        "family_scenario_share": _share_check(
            observed_count=scenario_bucket_counts.get("family", 0),
            case_count=case_count,
            max_ratio=DEFAULT_MAX_SCENARIO_SHARE,
        ),
        "family_afternoon_world_profile_share": _share_check(
            observed_count=world_profile_counts.get("family_afternoon", 0),
            case_count=case_count,
            max_ratio=DEFAULT_MAX_WORLD_PROFILE_SHARE,
        ),
        "non_failure_share": _share_check(
            observed_count=failure_mode_counts.get("none", 0),
            case_count=case_count,
            max_ratio=DEFAULT_MAX_NON_FAILURE_SHARE,
        ),
    }


def _share_check(*, observed_count: int, case_count: int, max_ratio: float) -> dict[str, Any]:
    observed_ratio = _round_ratio(observed_count, case_count)
    status = "passed" if observed_ratio <= max_ratio else "failed"
    return {
        "observed_ratio": observed_ratio,
        "max_ratio": max_ratio,
        "status": status,
    }


def _share_check_failures(share_checks: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for label, payload in share_checks.items():
        if payload["status"] == "failed":
            failures.append(
                f"Expected {label}<={payload['max_ratio']}, got {payload['observed_ratio']}."
            )
    return failures


def _build_coverage_gate_evaluation(
    *,
    suite_id: str | None,
    release_blocked: bool,
    blocking_failures: list[str],
    case_count: int,
    scenario_bucket_counts: dict[str, int],
    world_profile_counts: dict[str, int],
    failure_mode_counts: dict[str, int],
    constraint_tag_case_counts: dict[str, int],
    share_checks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "gate_id": COVERAGE_GATE_ID,
        "suite_id": suite_id,
        "release_blocked": release_blocked,
        "blocking_failures": list(blocking_failures),
        "coverage_thresholds": {
            "minimum_case_count": MINIMUM_CASE_COUNT,
            "scenario_bucket_minimums": dict(SCENARIO_BUCKET_MINIMUMS),
            "scenario_bucket_max_share": {"family": DEFAULT_MAX_SCENARIO_SHARE},
            "world_profile_minimums": dict(WORLD_PROFILE_MINIMUMS),
            "world_profile_max_share": {"family_afternoon": DEFAULT_MAX_WORLD_PROFILE_SHARE},
            "failure_mode_minimums": dict(FAILURE_MODE_MINIMUMS),
            "failure_mode_max_share": {"none": DEFAULT_MAX_NON_FAILURE_SHARE},
            "constraint_tag_minimums": dict(CONSTRAINT_TAG_MINIMUMS),
        },
        "observed_coverage": {
            "case_count": case_count,
            "scenario_bucket_counts": dict(scenario_bucket_counts),
            "world_profile_counts": dict(world_profile_counts),
            "failure_mode_counts": dict(failure_mode_counts),
            "constraint_tag_case_counts": dict(constraint_tag_case_counts),
        },
        "share_checks": share_checks,
    }


def _write_coverage_gate_evaluation(suite_report_path: Path, evaluation: dict[str, Any]) -> str | None:
    temp_path = suite_report_path.with_name(f"{suite_report_path.name}.tmp")
    try:
        payload = json.loads(suite_report_path.read_text(encoding="utf-8"))
        payload["coverage_gate_evaluation"] = evaluation
        suite_report_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(suite_report_path)
        return None
    except (OSError, json.JSONDecodeError):
        return f"Could not enrich coverage gate report: {suite_report_path}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _refresh_latest_alias(suite_report_path: Path, latest_report_path: Path) -> str | None:
    temp_path = latest_report_path.with_name(f"{latest_report_path.name}.tmp")
    try:
        latest_report_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(suite_report_path, temp_path)
        temp_path.replace(latest_report_path)
        return None
    except OSError:
        return f"Could not refresh latest report alias: {latest_report_path}"
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _format_success_summary(result: BenchmarkCoverageGateResult) -> str:
    return "\n".join(_build_summary_lines(result, heading="Benchmark coverage gate passed."))


def _format_failure_summary(result: BenchmarkCoverageGateResult) -> str:
    lines = _build_summary_lines(result, heading="Benchmark coverage gate failed.")
    lines.append("Blocking failures:")
    lines.extend(f"- {failure}" for failure in result.blocking_failures)
    return "\n".join(lines)


def _build_summary_lines(result: BenchmarkCoverageGateResult, *, heading: str) -> list[str]:
    lines = [
        heading,
        f"Gate: {result.gate_id}",
        f"Suite: {result.suite_id}",
        (
            f"Cases: {result.case_count} "
            f"({result.passed_count} passed, {result.failed_count} failed, {result.error_count} error)"
        ),
        f"Overall score: {result.overall_score}",
    ]
    for label in (
        "family_scenario_share",
        "family_afternoon_world_profile_share",
        "non_failure_share",
    ):
        payload = result.share_checks.get(label, {})
        lines.append(
            f"{label}: {payload.get('observed_ratio')} <= {payload.get('max_ratio')} ({payload.get('status')})"
        )
    lines.extend(
        [
            f"Run directory: {result.run_directory}",
            f"Suite report: {result.suite_report_path}",
            f"Latest report: {result.latest_report_path}",
        ]
    )
    return lines


def _coerce_count_map(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        return {str(key): int(count) for key, count in value.items()}
    return {}


def _coerce_constraint_tag_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    counts: dict[str, int] = {}
    for key, stats in value.items():
        tag = str(key)
        if tag not in CONSTRAINT_TAG_MINIMUMS:
            continue
        if isinstance(stats, dict):
            counts[tag] = int(stats.get("case_count", 0) or 0)
        else:
            counts[tag] = int(getattr(stats, "case_count", 0) or 0)
    return counts


def _raw_constraint_tag_outcomes(raw_payload: dict[str, Any]) -> Any:
    summary = raw_payload.get("benchmark_summary")
    if not isinstance(summary, dict):
        return None
    outcome_rollup = summary.get("outcome_rollup")
    if not isinstance(outcome_rollup, dict):
        return None
    return outcome_rollup.get("constraint_tag_outcomes")


def _round_ratio(observed_count: int, case_count: int) -> float:
    if case_count <= 0:
        return 0.0
    return round(observed_count / case_count, 4)
