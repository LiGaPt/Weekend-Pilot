from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    candidate_id: str
    name: str
    category: str
    provider: str
    source: str | None = None
    address: str | None = None
    location: dict[str, Any] | str | None = None
    tags: list[str] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    source_call_index: int
    tool_event_id: UUID | None = None


class InitialToolExecutionResult(BaseModel):
    source_call_index: int
    tool_name: str
    provider: str
    status: str
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    tool_event_id: UUID | None = None


class CandidateCollectionResult(BaseModel):
    run_id: UUID
    provider_profile: str
    activity_candidates: list[Candidate] = Field(default_factory=list)
    dining_candidates: list[Candidate] = Field(default_factory=list)
    other_candidates: list[Candidate] = Field(default_factory=list)
    weather: dict[str, Any] | None = None
    tool_results: list[InitialToolExecutionResult] = Field(default_factory=list)
    failed_tool_results: list[InitialToolExecutionResult] = Field(default_factory=list)
    executor_version: str
