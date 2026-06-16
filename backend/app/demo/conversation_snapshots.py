from __future__ import annotations

from typing import Any

from backend.app.demo.schemas import DemoRunSummary


SNAPSHOT_SCHEMA_VERSION = "conversation_turn_state_snapshot_v0"
_FORBIDDEN_KEY_FRAGMENTS = (
    "action_id",
    "tool_event_id",
    "event_id",
    "idempotency_key",
    "confirmation_id",
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "authorization",
    "prompt",
    "debug_trace",
)


def _sanitize_snapshot_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            if isinstance(key, str) and _is_forbidden_key(key):
                continue
            sanitized[key] = _sanitize_snapshot_payload(child)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_snapshot_payload(item) for item in value]
    return value


def _is_forbidden_key(key: str) -> bool:
    normalized = key.casefold()
    return any(fragment in normalized for fragment in _FORBIDDEN_KEY_FRAGMENTS)


def build_conversation_turn_state_snapshot(summary: DemoRunSummary) -> dict[str, Any]:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "run_status": summary.status,
        "selected_plan_id": str(summary.selected_plan_id) if summary.selected_plan_id is not None else None,
        "plan_count": len(summary.plans),
        "plan_version_label": summary.plan_version.version_label,
        "action_count": summary.action_count,
        "execution_status": summary.execution_status,
        "feedback_status": summary.feedback_status,
        "clarification_missing_fields": (
            list(summary.clarification.missing_fields) if summary.clarification is not None else []
        ),
        "progress": _sanitize_snapshot_payload(summary.progress.model_dump(mode="json")),
    }
