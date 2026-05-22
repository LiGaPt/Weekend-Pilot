from __future__ import annotations

from pydantic import BaseModel, Field

from backend.app.planning.schemas import LocalLifeIntent


class ClarificationPolicySummary(BaseModel):
    policy_version: str = "clarification_policy_v0"
    missing_fields: list[str] = Field(default_factory=list)
    question_text: str


def apply_clarification_policy(intent: LocalLifeIntent) -> ClarificationPolicySummary | None:
    missing_fields: list[str] = []

    if _is_missing_scenario_or_participants(intent):
        missing_fields.append("scenario_or_participants")
    if _is_missing_time_window(intent):
        missing_fields.append("time_window")

    if not missing_fields:
        return None

    return ClarificationPolicySummary(
        missing_fields=missing_fields,
        question_text=_question_text(missing_fields),
    )


def _is_missing_scenario_or_participants(intent: LocalLifeIntent) -> bool:
    return (
        intent.scenario_type == "unknown"
        and intent.participants.adults == 1
        and intent.participants.children_ages == []
        and not intent.constraints.child_friendly
    )


def _is_missing_time_window(intent: LocalLifeIntent) -> bool:
    return all(
        value is None
        for value in (
            intent.time_window.label,
            intent.time_window.start_at,
            intent.time_window.end_at,
            intent.time_window.duration_hours_min,
            intent.time_window.duration_hours_max,
        )
    )


def _question_text(missing_fields: list[str]) -> str:
    if missing_fields == ["scenario_or_participants", "time_window"]:
        return "为了继续规划，请补充这次是谁一起去，以及大概什么时间出发、准备玩多久。"
    if missing_fields == ["scenario_or_participants"]:
        return "为了继续规划，请补充这次是谁一起去。"
    return "为了继续规划，请补充大概什么时间出发、准备玩多久。"
