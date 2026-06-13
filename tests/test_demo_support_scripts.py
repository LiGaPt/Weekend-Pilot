from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _load_script_module(script_name: str, module_name: str):
    script_path = SCRIPTS_DIR / script_name
    assert script_path.exists(), f"Expected script to exist: {script_path}"

    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _make_local_temp_dir() -> Path:
    directory = REPO_ROOT / "var" / "test-demo-support-scripts" / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    return directory


def _cleanup_local_temp_dir(directory: Path) -> None:
    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    if directory.exists():
        directory.rmdir()


def test_demo_preflight_main_prints_recording_checklist(monkeypatch, capsys) -> None:
    module = _load_script_module("demo_preflight.py", "weekendpilot_demo_preflight")

    monkeypatch.setattr(
        module,
        "build_preflight_report",
        lambda repo_root=None: [
            module.CheckResult("PostgreSQL", "pass", "ok"),
            module.CheckResult("Redis", "pass", "ok"),
            module.CheckResult("Alembic", "pass", "at head"),
            module.CheckResult("API Health", "pass", "http://127.0.0.1:8000/health"),
            module.CheckResult("Public Demo", "pass", "http://127.0.0.1:5173/"),
            module.CheckResult("Internal Review", "pass", "http://127.0.0.1:5174/"),
            module.CheckResult(
                "Evidence Aliases",
                "pass",
                "latest-release_gate_v1-run-report.json, latest-coverage_gate_v1_5-run-report.json, latest-v2_integrity_gate-run-report.json, latest-all_registered-run-report.json, latest-family_route_failure_v1-review.json",
            ),
            module.CheckResult("AMap Preview", "warn", "missing key"),
        ],
    )

    exit_code = module.main(repo_root=REPO_ROOT)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Demo Preflight Checklist" in captured.out
    assert "[PASS] Internal Review: http://127.0.0.1:5174/" in captured.out
    assert "latest-release_gate_v1-run-report.json" in captured.out
    assert "latest-v2_integrity_gate-run-report.json" in captured.out
    assert "[WARN] AMap Preview: missing key" in captured.out
    assert "Traceback" not in captured.out


def test_demo_amap_preview_main_skips_cleanly_when_key_is_missing(monkeypatch, capsys) -> None:
    module = _load_script_module("demo_amap_preview.py", "weekendpilot_demo_amap_preview")
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(amap_maps_api_key=None))

    exit_code = module.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AMap preview unavailable" in captured.out
    assert "AMAP_MAPS_API_KEY is not configured" in captured.out
    assert "Traceback" not in captured.out


def test_demo_amap_preview_main_prints_run_fields_and_confirm_block(monkeypatch, capsys) -> None:
    module = _load_script_module("demo_amap_preview.py", "weekendpilot_demo_amap_preview_ready")
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(amap_maps_api_key=SimpleNamespace(get_secret_value=lambda: "local-key")),
    )

    start_calls: list[str] = []
    confirm_calls: list[tuple[str, str]] = []

    def fake_start(base_url: str):
        start_calls.append(base_url)
        return {
            "run_id": "run-amap-1",
            "status": "awaiting_confirmation",
            "read_profile": "amap",
        }

    def fake_confirm(base_url: str, run_id: str):
        confirm_calls.append((base_url, run_id))
        return module.HttpResult(
            status_code=409,
            body={"detail": "AMAP read-only demo runs cannot be confirmed."},
        )

    monkeypatch.setattr(module, "start_amap_preview_run", fake_start)
    monkeypatch.setattr(module, "confirm_amap_preview_run", fake_confirm)

    exit_code = module.main(base_url="http://127.0.0.1:8000")
    captured = capsys.readouterr()

    assert exit_code == 0
    assert start_calls == ["http://127.0.0.1:8000"]
    assert confirm_calls == [("http://127.0.0.1:8000", "run-amap-1")]
    assert "run_id: run-amap-1" in captured.out
    assert "status: awaiting_confirmation" in captured.out
    assert "read_profile: amap" in captured.out
    assert "confirm: 409" in captured.out
    assert "AMAP read-only demo runs cannot be confirmed." in captured.out


def test_show_submission_evidence_main_prints_aliases_and_meanings(capsys) -> None:
    module = _load_script_module("show_submission_evidence.py", "weekendpilot_submission_evidence")
    temp_root = _make_local_temp_dir()
    try:
        formal_dir = temp_root / "var" / "formal-benchmarks"
        recovery_dir = temp_root / "var" / "recovery-reviews"
        formal_dir.mkdir(parents=True)
        recovery_dir.mkdir(parents=True)

        (formal_dir / "latest-release_gate_v1-run-report.json").write_text(
            json.dumps({"run_status": "passed", "benchmark_summary": {"suite_id": "release_gate_v1"}}),
            encoding="utf-8",
        )
        (formal_dir / "latest-coverage_gate_v1_5-run-report.json").write_text(
            json.dumps({"run_status": "passed", "benchmark_summary": {"suite_id": "all_registered"}}),
            encoding="utf-8",
        )
        (formal_dir / "latest-v2_integrity_gate-run-report.json").write_text(
            json.dumps({"run_status": "passed", "benchmark_summary": {"suite_id": "v2_integrity"}}),
            encoding="utf-8",
        )
        (formal_dir / "latest-all_registered-run-report.json").write_text(
            json.dumps({"run_status": "passed", "benchmark_summary": {"suite_id": "all_registered"}}),
            encoding="utf-8",
        )
        (recovery_dir / "latest-family_route_failure_v1-review.json").write_text(
            json.dumps({"status": "passed", "case_id": "family_route_failure_v1"}),
            encoding="utf-8",
        )

        exit_code = module.main(repo_root=temp_root)
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Submission Evidence Summary" in captured.out
        assert "var/formal-benchmarks/latest-release_gate_v1-run-report.json" in captured.out
        assert "Current formal release gate baseline" in captured.out
        assert "coverage_gate_v1_5" in captured.out
        assert "Breadth and diversity coverage gate" in captured.out
        assert "v2_integrity_gate" in captured.out
        assert "V2 integrity benchmark gate" in captured.out
        assert "latest-family_route_failure_v1-review.json" in captured.out
        assert "Failure-recovery replay review" in captured.out
    finally:
        _cleanup_local_temp_dir(temp_root)


def test_submission_docs_exist_and_readme_links_to_supporting_docs() -> None:
    docs_dir = REPO_ROOT / "docs" / "submission"
    required = [
        "OVERVIEW.md",
        "DEMO_SCRIPT.md",
        "FUNCTION_COVERAGE_MAP.md",
        "EVIDENCE_MAP.md",
        "RECORDING_CHECKLIST.md",
    ]

    for filename in required:
        assert (docs_dir / filename).exists(), f"Expected submission doc to exist: {filename}"

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/WEB_DEMO_README.md" in readme_text
    assert "docs/V1_5_REVIEW_EVIDENCE.md" in readme_text


def test_phase0_version_scope_is_consistent_across_readme_and_submission_docs() -> None:
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "docs" / "WEB_DEMO_README.md",
        REPO_ROOT / "docs" / "submission" / "OVERVIEW.md",
        REPO_ROOT / "docs" / "submission" / "DEMO_SCRIPT.md",
        REPO_ROOT / "docs" / "submission" / "EVIDENCE_MAP.md",
        REPO_ROOT / "docs" / "submission" / "FUNCTION_COVERAGE_MAP.md",
        REPO_ROOT / "docs" / "submission" / "RECORDING_CHECKLIST.md",
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "V1.5 baseline / V2 Integrity candidate" in text, path
        assert "V2 Integrity Edition" in text, path
        assert "benchmark" in text, path
        assert "memory governance" in text, path
        assert "observability" in text, path
        assert "recovery" in text, path
        assert "AMap" in text, path


def test_web_demo_readme_covers_submission_recording_workflow() -> None:
    runbook_text = (REPO_ROOT / "docs" / "WEB_DEMO_README.md").read_text(encoding="utf-8")

    assert "python scripts/demo_preflight.py" in runbook_text
    assert "python scripts/show_submission_evidence.py" in runbook_text
    assert "python scripts/demo_amap_preview.py" in runbook_text
    assert "docs/submission/OVERVIEW.md" in runbook_text
    assert "`run_id`" in runbook_text
    assert "`5173 -> 5174`" in runbook_text
    assert "benchmark" in runbook_text


def test_readme_covers_project_status_startup_benchmark_and_tests() -> None:
    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    roadmap_asset = REPO_ROOT / "docs" / "assets" / "readme-current-version-roadmap.svg"

    assert roadmap_asset.exists()
    assert "docs/assets/readme-current-version-roadmap.svg" in readme_text
    assert "## Benchmark" in readme_text
    assert "## Mock World" in readme_text
    assert "docker compose up -d postgres redis" in readme_text
    assert "uvicorn backend.app.main:app --reload" in readme_text
    assert "npm --prefix frontend run dev" in readme_text
    assert "npm --prefix frontend run dev:internal" in readme_text
    assert "distractor" in readme_text
    assert "release_gate_v1" in readme_text
    assert "coverage_gate_v1_5" in readme_text
    assert "all_registered" in readme_text
    assert "latest-family_route_failure_v1-review.json" in readme_text
    assert "`15/15`" in readme_text
    assert "`22/22`" in readme_text
    assert "`3/3`" in readme_text
    assert "show_submission_evidence.py" in readme_text
    assert "python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q" in readme_text
    assert "npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx" in readme_text
    assert "`15 passed`" in readme_text
    assert "`24 passed`" in readme_text
