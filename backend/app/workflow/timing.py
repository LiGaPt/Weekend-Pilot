from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from pydantic import BaseModel, Field


class WorkflowNodeTimingRecord(BaseModel):
    node_name: str
    attempt_index: int
    duration_ms: int


class WorkflowStageTimingEntry(BaseModel):
    node_name: str
    attempt_count: int
    total_duration_ms: int


class WorkflowTimingSummary(BaseModel):
    schema_version: str = "workflow_timing_summary_v1"
    total_duration_ms: int
    stage_count: int
    stages: list[WorkflowStageTimingEntry] = Field(default_factory=list)


def append_workflow_timing_record(
    records: Iterable[WorkflowNodeTimingRecord | dict],
    node_name: str,
    duration_ms: int,
) -> list[WorkflowNodeTimingRecord]:
    parsed = [
        record if isinstance(record, WorkflowNodeTimingRecord) else WorkflowNodeTimingRecord.model_validate(record)
        for record in records
    ]
    attempt_index = 1 + sum(1 for record in parsed if record.node_name == node_name)
    return [
        *parsed,
        WorkflowNodeTimingRecord(
            node_name=node_name,
            attempt_index=attempt_index,
            duration_ms=max(1, int(duration_ms)),
        ),
    ]


def summarize_workflow_timing(
    records: Iterable[WorkflowNodeTimingRecord | dict],
    node_order: Iterable[str],
) -> WorkflowTimingSummary:
    parsed = [
        record if isinstance(record, WorkflowNodeTimingRecord) else WorkflowNodeTimingRecord.model_validate(record)
        for record in records
    ]
    grouped: dict[str, list[WorkflowNodeTimingRecord]] = defaultdict(list)
    for record in parsed:
        grouped[record.node_name].append(record)

    stages: list[WorkflowStageTimingEntry] = []
    for node_name in node_order:
        node_records = grouped.get(node_name, [])
        if not node_records:
            continue
        stages.append(
            WorkflowStageTimingEntry(
                node_name=node_name,
                attempt_count=len(node_records),
                total_duration_ms=sum(record.duration_ms for record in node_records),
            )
        )

    return WorkflowTimingSummary(
        total_duration_ms=sum(record.duration_ms for record in parsed),
        stage_count=len(stages),
        stages=stages,
    )
