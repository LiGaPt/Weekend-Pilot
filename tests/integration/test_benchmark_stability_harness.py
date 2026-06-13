from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from backend.app.benchmark.stability_harness import run_benchmark_stability_passk


def test_benchmark_stability_harness_runs_v2_integrity_without_touching_gate_alias() -> None:
    output_root = _make_test_dir()

    try:
        report = run_benchmark_stability_passk(
            "v2_integrity",
            4,
            output_root=output_root,
            start_services=False,
        )

        latest_stability_alias = output_root / "latest-v2_integrity-passk-v0-report.json"
        assert report.suite_id == "v2_integrity"
        assert report.gate_id == "v2_integrity_gate"
        assert report.executed_run_count == 4
        assert report.window_count == 1
        assert len(report.attempts) == 4
        assert [attempt.attempt_index for attempt in report.attempts] == [1, 2, 3, 4]
        assert latest_stability_alias.exists()

        payload = json.loads(latest_stability_alias.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "weekendpilot_benchmark_stability_passk_v1"
        assert payload["metric_version"] == "passk_v0"
        assert payload["suite_id"] == "v2_integrity"
        assert payload["window_size"] == 4
        assert payload["window_count"] == 1
        assert payload["discarded_tail_run_count"] == 0
        assert len(payload["attempts"]) == 4
        assert payload["attempts"][0]["suite_report_path"] == "attempt-001/suite-v2_integrity-run-report.json"
        assert payload["attempts"][3]["suite_report_path"] == "attempt-004/suite-v2_integrity-run-report.json"

        run_directory = output_root / Path(report.report_path).parent.name
        assert not (run_directory / "latest-v2_integrity_gate-run-report.json").exists()
    finally:
        _cleanup_test_dir(output_root)


def _make_test_dir() -> Path:
    path = Path("var/test-benchmark-stability-harness-integration") / str(uuid4())
    path.mkdir(parents=True, exist_ok=False)
    return path


def _cleanup_test_dir(path: Path) -> None:
    if path.exists():
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            else:
                child.rmdir()
        path.rmdir()
    parent = path.parent
    if parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
    grandparent = parent.parent
    if grandparent.exists() and not any(grandparent.iterdir()):
        grandparent.rmdir()
