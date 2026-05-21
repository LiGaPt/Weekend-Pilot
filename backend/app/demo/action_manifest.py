from __future__ import annotations

from typing import Any, Callable

from backend.app.demo.schemas import DemoActionManifestItemSummary, DemoActionManifestSummary


def summarize_action_manifest(
    plan_json: dict[str, Any] | None,
    sanitizer: Callable[[Any], Any],
) -> DemoActionManifestSummary:
    confirmed_manifest = _summarize_confirmed_actions(plan_json, sanitizer)
    if confirmed_manifest is not None:
        return confirmed_manifest

    proposed_manifest = _summarize_proposed_actions(plan_json, sanitizer)
    if proposed_manifest is not None:
        return proposed_manifest

    return DemoActionManifestSummary(source="none", action_count=0, actions=[])


def _summarize_confirmed_actions(
    plan_json: dict[str, Any] | None,
    sanitizer: Callable[[Any], Any],
) -> DemoActionManifestSummary | None:
    actions = _confirmed_actions(plan_json)
    if not actions:
        return None

    normalized = [_normalize_confirmed_action(action, sanitizer) for action in actions]
    if any(item is None for item in normalized):
        return None

    sorted_actions = sorted(
        [item for item in normalized if item is not None],
        key=lambda item: item.execution_order or 0,
    )
    if not sorted_actions:
        return None
    if len({item.execution_order for item in sorted_actions}) != len(sorted_actions):
        return None

    return DemoActionManifestSummary(
        source="confirmed_actions",
        action_count=len(sorted_actions),
        actions=sorted_actions,
    )


def _summarize_proposed_actions(
    plan_json: dict[str, Any] | None,
    sanitizer: Callable[[Any], Any],
) -> DemoActionManifestSummary | None:
    actions = _proposed_actions(plan_json)
    if not actions:
        return None

    normalized = [_normalize_proposed_action(action, index, sanitizer) for index, action in enumerate(actions, start=1)]
    if any(item is None for item in normalized):
        return None

    public_actions = [item for item in normalized if item is not None]
    if not public_actions:
        return None

    return DemoActionManifestSummary(
        source="proposed_actions",
        action_count=len(public_actions),
        actions=public_actions,
    )


def _confirmed_actions(plan_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(plan_json, dict):
        return []
    raw = plan_json.get("confirmed_actions")
    if not isinstance(raw, list) or not raw:
        return []
    if any(not isinstance(item, dict) for item in raw):
        return []
    return raw


def _proposed_actions(plan_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(plan_json, dict):
        return []
    draft = plan_json.get("draft")
    if not isinstance(draft, dict):
        return []
    raw = draft.get("proposed_actions")
    if not isinstance(raw, list) or not raw:
        return []
    if any(not isinstance(item, dict) for item in raw):
        return []
    return raw


def _normalize_confirmed_action(
    action: dict[str, Any],
    sanitizer: Callable[[Any], Any],
) -> DemoActionManifestItemSummary | None:
    execution_order = _positive_int(action.get("execution_order"))
    action_type = _string_or_none(action.get("tool_name"))
    action_ref = _string_or_none(action.get("action_ref"))
    target_id = _string_or_none(action.get("target_id"))
    reason = _string_or_none(action.get("reason"))
    payload = action.get("payload")
    if execution_order is None or action_type is None or action_ref is None or target_id is None:
        return None
    if not isinstance(payload, dict):
        return None

    payload_preview = sanitizer(payload)
    if not isinstance(payload_preview, dict):
        return None

    return DemoActionManifestItemSummary(
        action_ref=action_ref,
        execution_order=execution_order,
        action_type=action_type,
        target_id=target_id,
        payload_preview=payload_preview,
        reason=reason,
    )


def _normalize_proposed_action(
    action: dict[str, Any],
    execution_order: int,
    sanitizer: Callable[[Any], Any],
) -> DemoActionManifestItemSummary | None:
    action_type = _string_or_none(action.get("action_type"))
    action_ref = _string_or_none(action.get("action_ref"))
    target_id = _string_or_none(action.get("target_id"))
    reason = _string_or_none(action.get("reason"))
    payload = action.get("payload")
    if action_type is None or action_ref is None or target_id is None:
        return None
    if not isinstance(payload, dict):
        return None

    payload_preview = sanitizer(payload)
    if not isinstance(payload_preview, dict):
        return None

    return DemoActionManifestItemSummary(
        action_ref=action_ref,
        execution_order=execution_order,
        action_type=action_type,
        target_id=target_id,
        payload_preview=payload_preview,
        reason=reason,
    )


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 1:
        return value
    return None


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
