from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ScenarioType = Literal["family", "friends", "solo", "unknown"]
ProviderProfile = Literal["mock_world", "amap"]


class TimeWindow(BaseModel):
    label: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    duration_hours_min: int | None = Field(default=None, ge=0)
    duration_hours_max: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_duration_bounds(self) -> "TimeWindow":
        if (
            self.duration_hours_min is not None
            and self.duration_hours_max is not None
            and self.duration_hours_min > self.duration_hours_max
        ):
            raise ValueError("duration_hours_min must be less than or equal to duration_hours_max.")
        return self


class ParticipantProfile(BaseModel):
    adults: int = Field(default=1, ge=0)
    children_ages: list[int] = Field(default_factory=list)


class IntentConstraints(BaseModel):
    child_friendly: bool = False
    max_distance_km: int | None = Field(default=None, gt=0)


class LocalLifeIntent(BaseModel):
    raw_text: str
    scenario_type: ScenarioType = "unknown"
    participants: ParticipantProfile = Field(default_factory=ParticipantProfile)
    time_window: TimeWindow = Field(default_factory=TimeWindow)
    constraints: IntentConstraints = Field(default_factory=IntentConstraints)
    activity_preferences: list[str] = Field(default_factory=list)
    dining_preferences: list[str] = Field(default_factory=list)
    origin_text: str | None = None
    parser_version: str


class IntentParseSignals(BaseModel):
    scenario_or_participants: bool = False
    time_window: bool = False
    max_distance_km: bool = False
    dining_preferences: bool = False
    activity_preferences: bool = False


class IntentParseResult(BaseModel):
    intent: LocalLifeIntent
    signals: IntentParseSignals = Field(default_factory=IntentParseSignals)


class PlannedToolCall(BaseModel):
    tool_name: str
    provider: ProviderProfile
    payload: dict[str, Any] = Field(default_factory=dict)


class ToolCallTemplate(BaseModel):
    tool_name: str
    provider: ProviderProfile
    required_inputs: list[str] = Field(default_factory=list)
    payload_template: dict[str, Any] = Field(default_factory=dict)


class QueryPlan(BaseModel):
    intent: LocalLifeIntent
    provider_profile: ProviderProfile
    initial_tool_calls: list[PlannedToolCall] = Field(default_factory=list)
    candidate_enrichment_templates: list[ToolCallTemplate] = Field(default_factory=list)
    route_templates: list[ToolCallTemplate] = Field(default_factory=list)
    forbidden_write_tools_before_confirmation: list[str] = Field(default_factory=list)
    planner_version: str
    notes: list[str] = Field(default_factory=list)
