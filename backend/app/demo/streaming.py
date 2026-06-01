from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from backend.app.demo.progress import build_live_demo_progress_milestones
from backend.app.demo.schemas import DemoProgressSummary
from backend.app.models.runtime import ToolEvent


def encode_sse_event(event_name: str, payload: BaseModel | Mapping[str, Any]) -> str:
    encoded = json.dumps(
        jsonable_encoder(payload),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event_name}\ndata: {encoded}\n\n"


def serialize_progress_summary(progress: DemoProgressSummary) -> str:
    return json.dumps(
        progress.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def is_duplicate_progress_snapshot(
    previous_snapshot: str | None,
    progress: DemoProgressSummary,
) -> bool:
    return previous_snapshot == serialize_progress_summary(progress)


def derive_stream_progress_summaries(
    state: Mapping[str, Any],
    tool_events: Sequence[ToolEvent] | None,
    *,
    persisted_plan_count: int | None = None,
) -> list[DemoProgressSummary]:
    return build_live_demo_progress_milestones(
        state,
        tool_events,
        persisted_plan_count=persisted_plan_count,
    )
