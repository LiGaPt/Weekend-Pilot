from __future__ import annotations

import backend.app.demo.versioning as demo_versioning
from uuid import uuid4

from backend.app.demo.versioning import build_next_plan_version_metadata, summarize_plan_version


def test_summarize_plan_version_defaults_to_v1_when_metadata_is_missing() -> None:
    summary = summarize_plan_version({})

    assert summary.version_number == 1
    assert summary.version_label == "v1"
    assert summary.source_run_id is None
    assert summary.source_selected_plan_id is None


def test_summarize_plan_version_sanitizes_invalid_metadata_to_v1() -> None:
    summary = summarize_plan_version(
        {
            "demo": {
                "plan_version": {
                    "version_number": 0,
                    "source_run_id": "not-a-uuid",
                    "source_selected_plan_id": 123,
                }
            }
        }
    )

    assert summary.version_number == 1
    assert summary.version_label == "v1"
    assert summary.source_run_id is None
    assert summary.source_selected_plan_id is None


def test_build_next_plan_version_metadata_increments_v1_source_to_v2() -> None:
    source_run_id = uuid4()
    source_selected_plan_id = uuid4()

    metadata = build_next_plan_version_metadata(
        {"demo": {"plan_version": {"version_number": 1}}},
        source_run_id=source_run_id,
        source_selected_plan_id=source_selected_plan_id,
    )

    assert metadata == {
        "version_number": 2,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": str(source_selected_plan_id),
    }


def test_build_next_plan_version_metadata_increments_v2_source_to_v3() -> None:
    source_run_id = uuid4()

    metadata = build_next_plan_version_metadata(
        {"demo": {"plan_version": {"version_number": 2}}},
        source_run_id=source_run_id,
        source_selected_plan_id=None,
    )

    assert metadata == {
        "version_number": 3,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": None,
    }


def test_build_next_plan_version_metadata_treats_missing_source_metadata_as_v1() -> None:
    source_run_id = uuid4()

    metadata = build_next_plan_version_metadata(
        {"demo": {}},
        source_run_id=source_run_id,
        source_selected_plan_id=None,
    )

    assert metadata == {
        "version_number": 2,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": None,
    }


def test_build_clarification_plan_version_metadata_keeps_source_version_without_increment() -> None:
    source_run_id = uuid4()

    assert hasattr(demo_versioning, "build_clarification_plan_version_metadata")
    metadata = demo_versioning.build_clarification_plan_version_metadata(
        {"demo": {"plan_version": {"version_number": 1}}},
        source_run_id=source_run_id,
    )

    assert metadata == {
        "version_number": 1,
        "source_run_id": str(source_run_id),
        "source_selected_plan_id": None,
    }
