from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    relative_path: Path
    proves: str


EVIDENCE_ITEMS = (
    EvidenceItem(
        evidence_id="release_gate_v1",
        relative_path=Path("var/formal-benchmarks/latest-release_gate_v1-run-report.json"),
        proves="Current formal release gate baseline",
    ),
    EvidenceItem(
        evidence_id="coverage_gate_v1_5",
        relative_path=Path("var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json"),
        proves="Breadth and diversity coverage gate",
    ),
    EvidenceItem(
        evidence_id="v2_integrity_gate",
        relative_path=Path("var/formal-benchmarks/latest-v2_integrity_gate-run-report.json"),
        proves="V2 integrity benchmark gate",
    ),
    EvidenceItem(
        evidence_id="formal_verification_all_registered",
        relative_path=Path("var/formal-benchmarks/latest-all_registered-run-report.json"),
        proves="Full registered-case formal verification",
    ),
    EvidenceItem(
        evidence_id="recovery_review_family_route_failure_v1",
        relative_path=Path("var/recovery-reviews/latest-family_route_failure_v1-review.json"),
        proves="Failure-recovery replay review",
    ),
)


def main(repo_root: Path | None = None) -> int:
    root = repo_root or REPO_ROOT
    print(format_submission_evidence(root))
    return 1 if any(not (root / item.relative_path).exists() for item in EVIDENCE_ITEMS) else 0


def format_submission_evidence(repo_root: Path) -> str:
    lines = ["Submission Evidence Summary"]
    for item in EVIDENCE_ITEMS:
        absolute_path = repo_root / item.relative_path
        if not absolute_path.exists():
            lines.append(f"[MISSING] {item.evidence_id}")
            lines.append(f"  path: {item.relative_path.as_posix()}")
            lines.append(f"  proves: {item.proves}")
            continue

        payload = _read_json(absolute_path)
        summary = _summarize_payload(payload)
        lines.append(f"[OK] {item.evidence_id}")
        lines.append(f"  path: {item.relative_path.as_posix()}")
        lines.append(f"  proves: {item.proves}")
        lines.append(f"  summary: {summary}")
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _summarize_payload(payload: dict[str, Any]) -> str:
    if "benchmark_summary" in payload and isinstance(payload["benchmark_summary"], dict):
        suite_id = payload["benchmark_summary"].get("suite_id", "unknown")
        run_status = payload.get("run_status", "unknown")
        return f"run_status={run_status}, suite_id={suite_id}"
    if "case_id" in payload:
        return f"status={payload.get('status', 'unknown')}, case_id={payload.get('case_id')}"
    return "status=unknown"


if __name__ == "__main__":
    raise SystemExit(main())
