from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.planning.candidates import Candidate


EnrichmentStage = Literal["candidate_enrichment", "route_matrix"]


class EnrichmentToolResult(BaseModel):
    stage: EnrichmentStage
    candidate_id: str | None = None
    origin_candidate_id: str | None = None
    destination_candidate_id: str | None = None
    tool_name: str
    provider: str
    status: str
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    tool_event_id: UUID | None = None


class EnrichedCandidate(BaseModel):
    candidate: Candidate
    poi_detail: dict[str, Any] | None = None
    opening_hours: dict[str, Any] | None = None
    queue: dict[str, Any] | None = None
    table_availability: dict[str, Any] | None = None
    ticket_availability: dict[str, Any] | None = None
    tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    failed_tool_results: list[EnrichmentToolResult] = Field(default_factory=list)


class RouteMatrixEntry(BaseModel):
    origin_candidate_id: str
    destination_candidate_id: str
    provider: str
    mode: str = "walking"
    status: str
    route_json: dict[str, Any] | None = None
    distance_meters: int | None = None
    duration_minutes: int | None = None
    tool_event_id: UUID | None = None
    error_json: dict[str, Any] | None = None


class CandidateEnrichmentResult(BaseModel):
    run_id: UUID
    provider_profile: str
    enriched_activity_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    enriched_dining_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    enriched_other_candidates: list[EnrichedCandidate] = Field(default_factory=list)
    route_matrix: list[RouteMatrixEntry] = Field(default_factory=list)
    tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    failed_tool_results: list[EnrichmentToolResult] = Field(default_factory=list)
    enricher_version: str
