from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.demo.schemas import DemoPlanVersionSummary


def build_initial_plan_version_metadata() -> dict[str, Any]:
    return {
        "version_number": 1,
        "source_run_id": None,
        "source_selected_plan_id": None,
    }


def summarize_plan_version(metadata_json: dict[str, Any] | None) -> DemoPlanVersionSummary:
    metadata = _plan_version_metadata(metadata_json)
    version_number = _sanitize_version_number(metadata.get("version_number"))
    return DemoPlanVersionSummary(
        version_number=version_number,
        version_label=f"v{version_number}",
        source_run_id=_uuid_or_none(metadata.get("source_run_id")),
        source_selected_plan_id=_uuid_or_none(metadata.get("source_selected_plan_id")),
    )


def build_next_plan_version_metadata(
    source_metadata_json: dict[str, Any] | None,
    *,
    source_run_id: UUID,
    source_selected_plan_id: UUID | str | None,
) -> dict[str, Any]:
    source_summary = summarize_plan_version(source_metadata_json)
    return {
        "version_number": source_summary.version_number + 1,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": _string_or_none(source_selected_plan_id),
    }


def build_clarification_plan_version_metadata(
    source_metadata_json: dict[str, Any] | None,
    *,
    source_run_id: UUID,
) -> dict[str, Any]:
    source_summary = summarize_plan_version(source_metadata_json)
    return {
        "version_number": source_summary.version_number,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": None,
    }


def _plan_version_metadata(metadata_json: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata_json, dict):
        return {}
    demo = metadata_json.get("demo")
    if not isinstance(demo, dict):
        return {}
    plan_version = demo.get("plan_version")
    if not isinstance(plan_version, dict):
        return {}
    return plan_version


def _sanitize_version_number(value: Any) -> int:
    if isinstance(value, bool):
        return 1
    if isinstance(value, int):
        return value if value >= 1 else 1
    return 1


def _uuid_or_none(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _string_or_none(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)
