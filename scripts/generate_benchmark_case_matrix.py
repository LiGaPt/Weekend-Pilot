from __future__ import annotations

import argparse
import json

from backend.app.benchmark.case_matrix import build_benchmark_case_matrix_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic benchmark case matrix manifests.")
    parser.add_argument("--suite-id", default=None, help="Optional benchmark suite ID to filter rows.")
    parser.add_argument("--format", choices=("json",), default="json", help="Output format.")
    args = parser.parse_args()

    manifest = build_benchmark_case_matrix_manifest(args.suite_id)
    print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
