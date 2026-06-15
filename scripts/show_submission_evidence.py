from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.benchmark.submission_evidence import (
    SUBMISSION_EVIDENCE_CONTRACTS,
    read_submission_evidence_payload,
    summarize_submission_evidence,
)


def main(repo_root: Path | None = None) -> int:
    root = repo_root or REPO_ROOT
    print(format_submission_evidence(root))
    return 1 if _has_invalid_required_evidence(root) else 0


def format_submission_evidence(repo_root: Path) -> str:
    lines = ["Submission Evidence Summary"]
    for item in SUBMISSION_EVIDENCE_CONTRACTS:
        absolute_path = repo_root / item.relative_path
        if not absolute_path.exists():
            lines.append(f"[MISSING] {item.evidence_id}")
            lines.append(f"  path: {item.relative_path.as_posix()}")
            lines.append(f"  proves: {item.proves}")
            continue

        try:
            payload = read_submission_evidence_payload(repo_root, item)
        except (OSError, json.JSONDecodeError):
            lines.append(f"[INVALID] {item.evidence_id}")
            lines.append(f"  path: {item.relative_path.as_posix()}")
            lines.append(f"  proves: {item.proves}")
            continue
        summary = summarize_submission_evidence(payload, item)
        lines.append(f"[OK] {item.evidence_id}")
        lines.append(f"  path: {item.relative_path.as_posix()}")
        lines.append(f"  proves: {item.proves}")
        lines.append(f"  summary: {summary}")
    return "\n".join(lines)


def _has_invalid_required_evidence(repo_root: Path) -> bool:
    for item in SUBMISSION_EVIDENCE_CONTRACTS:
        absolute_path = repo_root / item.relative_path
        if not absolute_path.exists():
            return True
        try:
            payload = read_submission_evidence_payload(repo_root, item)
        except (OSError, json.JSONDecodeError):
            return True
        if summarize_submission_evidence(payload, item) == "status=invalid":
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
