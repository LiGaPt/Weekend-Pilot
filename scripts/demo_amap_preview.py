from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.core.config import get_settings


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_USER_INPUT = "Plan a light family afternoon nearby."


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    body: dict[str, Any]


def start_amap_preview_run(base_url: str) -> dict[str, Any]:
    payload = {
        "user_input": DEFAULT_USER_INPUT,
        "external_user_id": "web-demo-user",
        "display_name": "Web Demo User",
        "case_id": "web-demo",
        "selected_plan_index": 0,
        "read_profile": "amap",
    }
    with httpx.Client(timeout=15.0) as client:
        response = client.post(f"{base_url}/demo/runs", json=payload)
    body = _safe_json(response)
    if response.status_code != 200:
        raise RuntimeError(f"start run failed with {response.status_code}: {_detail_from_body(body)}")
    return body


def confirm_amap_preview_run(base_url: str, run_id: str) -> HttpResult:
    with httpx.Client(timeout=15.0) as client:
        response = client.post(
            f"{base_url}/demo/runs/{run_id}/confirm",
            json={"confirmed_by": "web-demo-user"},
        )
    return HttpResult(status_code=response.status_code, body=_safe_json(response))


def main(base_url: str = DEFAULT_BASE_URL) -> int:
    key = get_settings().amap_maps_api_key
    if key is None or not key.get_secret_value().strip():
        print("AMap preview unavailable: AMAP_MAPS_API_KEY is not configured.")
        return 0

    try:
        start_body = start_amap_preview_run(base_url)
        run_id = str(start_body.get("run_id", ""))
        print("AMap Preview Demo")
        print(f"run_id: {run_id}")
        print(f"status: {start_body.get('status')}")
        print(f"read_profile: {start_body.get('read_profile')}")

        confirm_result = confirm_amap_preview_run(base_url, run_id)
        print(f"confirm: {confirm_result.status_code}")
        detail = _detail_from_body(confirm_result.body)
        if detail:
            print(detail)
        return 0
    except Exception as exc:  # pragma: no cover - network failure handling
        print(f"AMap preview failed: {_short_exception(exc)}")
        return 1


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _detail_from_body(body: dict[str, Any]) -> str:
    detail = body.get("detail")
    return detail if isinstance(detail, str) else ""


def _short_exception(exc: Exception) -> str:
    message = str(exc).strip()
    return message or type(exc).__name__


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AMap read-only preview demo flow.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()
    raise SystemExit(main(base_url=args.base_url))
