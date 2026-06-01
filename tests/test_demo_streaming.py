from __future__ import annotations

import json
from uuid import uuid4

from backend.app.demo.streaming import (
    derive_stream_progress_summary,
    encode_sse_event,
    is_duplicate_progress_snapshot,
    serialize_progress_summary,
)
from backend.app.demo.schemas import DemoProgressSummary
from backend.app.models.runtime import ToolEvent


def _tool_event(
    run_id,
    *,
    sequence: int,
    category: str | None = None,
    canonical_category: str | None = None,
    response_json: dict[str, object] | None = None,
) -> ToolEvent:
    payload: dict[str, object] = {}
    if category is not None:
        payload["category"] = category
    if canonical_category is not None:
        payload["canonical_category"] = canonical_category
    return ToolEvent(
        event_id=uuid4(),
        run_id=run_id,
        tool_name="search_poi",
        tool_type="read",
        provider="mock_world",
        request_json={"payload": payload, "event_sequence": sequence},
        response_json=response_json if response_json is not None else {"results": []},
        error_json=None,
        status="succeeded",
        cache_hit=False,
        latency_ms=3,
        langsmith_trace_id=None,
    )


def test_encode_sse_event_formats_single_json_data_line() -> None:
    frame = encode_sse_event(
        "progress",
        {
            "event_index": 1,
            "run_id": str(uuid4()),
            "progress": {
                "schema_version": "public_demo_progress_v1",
                "current_stage": "understanding_request",
                "current_label": "正在理解需求",
                "stage_history": ["understanding_request"],
                "steps": [
                    {
                        "stage": "understanding_request",
                        "label": "正在理解需求",
                        "status": "current",
                        "summary": "已理解出行目标与核心约束",
                    }
                ],
            },
        },
    )

    assert frame.startswith("event: progress\n")
    assert frame.endswith("\n\n")
    lines = frame.strip().splitlines()
    assert lines[0] == "event: progress"
    assert len([line for line in lines if line.startswith("data: ")]) == 1
    payload = json.loads(lines[1][len("data: ") :])
    assert payload["event_index"] == 1
    assert payload["progress"]["current_stage"] == "understanding_request"


def test_duplicate_progress_snapshots_are_detected() -> None:
    progress = DemoProgressSummary.model_validate(
        {
            "current_stage": "planning_queries",
            "current_label": "正在规划查询",
            "stage_history": ["understanding_request", "planning_queries"],
            "steps": [
                {
                    "stage": "understanding_request",
                    "label": "正在理解需求",
                    "status": "completed",
                    "summary": "已理解出行目标与核心约束",
                },
                {
                    "stage": "planning_queries",
                    "label": "正在规划查询",
                    "status": "current",
                    "summary": "已整理活动与餐饮查询方向",
                },
            ],
        }
    )

    snapshot = serialize_progress_summary(progress)

    assert is_duplicate_progress_snapshot(snapshot, progress) is True


def test_live_progress_uses_in_memory_draft_count_before_plan_rows_exist() -> None:
    run_id = uuid4()
    progress = derive_stream_progress_summary(
        {
            "run_id": run_id,
            "status": "running",
            "node_history": [
                "initialize",
                "parse_intent",
                "load_memory",
                "generate_queries",
                "logical_planner_agent",
            ],
            "itinerary_drafts": {"drafts": [{"draft_id": "draft-1"}, {"draft_id": "draft-2"}]},
        },
        [],
        persisted_plan_count=0,
    )

    assert progress.current_stage == "building_itinerary"
    assert progress.steps[-1].summary == "已生成 2 个候选方案"


def test_execute_searches_can_surface_both_search_stages_in_one_snapshot() -> None:
    run_id = uuid4()
    progress = derive_stream_progress_summary(
        {
            "run_id": run_id,
            "status": "running",
            "node_history": [
                "initialize",
                "parse_intent",
                "load_memory",
                "generate_queries",
                "execute_searches",
            ],
        },
        [
            _tool_event(run_id, sequence=1, category="activity", response_json={"results": [{}, {}]}),
            _tool_event(run_id, sequence=2, category="dining", response_json={"candidate_count": 3}),
        ],
    )

    assert progress.current_stage == "searching_dining"
    assert progress.stage_history == [
        "understanding_request",
        "planning_queries",
        "searching_activities",
        "searching_dining",
    ]
    assert progress.steps[-2].summary == "已找到 2 个活动"
    assert progress.steps[-1].summary == "已找到 3 个餐厅"
