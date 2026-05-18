from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from backend.app.agents import (
    DeterministicDiningAgent,
    DeterministicDiscoveryAgent,
    DeterministicItineraryPlannerAgent,
    DeterministicSupervisorAgent,
    DeterministicValidatorRecoveryAgent,
)
from backend.app.agents.factory import build_agent_adapters
from backend.app.agents.llm_adapters import (
    LLMDiningAgent,
    LLMDiscoveryAgent,
    LLMItineraryPlannerAgent,
)
from backend.app.core.config import Settings
from backend.app.llm import LLMCallMetadata, LLMChatCompletion, LLMProviderError, LLMUsage
from backend.app.planning import (
    Candidate,
    CandidateCollectionResult,
    CandidateEnrichmentResult,
    EnrichedCandidate,
    EnrichmentToolResult,
    IntentConstraints,
    LocalLifeIntent,
    ParticipantProfile,
    QueryPlan,
    RouteMatrixEntry,
    TimeWindow,
    ToolCallTemplate,
)


class FakeLLMClient:
    def __init__(self, *payloads: dict[str, Any], error: Exception | None = None) -> None:
        self.payloads = list(payloads)
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def chat_json(self, *, messages, temperature=0.2, max_tokens=400):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        payload = self.payloads.pop(0)
        return LLMChatCompletion(
            content_json=payload,
            metadata=LLMCallMetadata(
                provider_kind="openai_compatible",
                model_id="qwen3.6-plus",
                base_url_host="dashscope.aliyuncs.com",
                latency_ms=12,
                usage=LLMUsage(input_count=3, output_count=2, total_count=5),
                status="completed",
            ),
        )


def _intent() -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        scenario_type="family",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        time_window=TimeWindow(duration_hours_min=4, duration_hours_max=6),
        constraints=IntentConstraints(child_friendly=True, max_distance_km=8),
        activity_preferences=["child_friendly"],
        dining_preferences=["lighter_options"],
        parser_version="test-parser",
    )


def _plan() -> QueryPlan:
    return QueryPlan(
        intent=_intent(),
        provider_profile="mock_world",
        candidate_enrichment_templates=[
            ToolCallTemplate(tool_name="get_poi_detail", provider="mock_world"),
            ToolCallTemplate(tool_name="check_opening_hours", provider="mock_world"),
            ToolCallTemplate(tool_name="check_queue", provider="mock_world"),
            ToolCallTemplate(tool_name="check_table_availability", provider="mock_world"),
            ToolCallTemplate(tool_name="check_ticket_availability", provider="mock_world"),
        ],
        route_templates=[ToolCallTemplate(tool_name="check_route", provider="mock_world")],
        planner_version="test-planner",
    )


def _candidate(candidate_id: str, *, name: str, category: str, tags: list[str] | None = None) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        name=name,
        category=category,
        provider="mock_world",
        address=f"{name} address",
        tags=tags or [],
        raw_payload={"poi_id": candidate_id},
        source_call_index=0,
        tool_event_id=uuid4(),
    )


def _tool_result(tool_name: str, candidate_id: str) -> EnrichmentToolResult:
    return EnrichmentToolResult(
        stage="candidate_enrichment",
        candidate_id=candidate_id,
        tool_name=tool_name,
        provider="mock_world",
        status="succeeded",
        response_json={},
        tool_event_id=uuid4(),
    )


def _activity() -> EnrichedCandidate:
    candidate_id = "activity_museum_001"
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name="Xuhui Family Science Museum",
            category="activity",
            tags=["child_friendly"],
        ),
        poi_detail={"poi_id": candidate_id},
        opening_hours={"is_open": True},
        ticket_availability={"poi_id": candidate_id, "available": True, "time_slots": ["13:30"]},
        tool_results=[
            _tool_result("get_poi_detail", candidate_id),
            _tool_result("check_opening_hours", candidate_id),
            _tool_result("check_ticket_availability", candidate_id),
        ],
    )


def _dining() -> EnrichedCandidate:
    candidate_id = "restaurant_light_001"
    return EnrichedCandidate(
        candidate=_candidate(
            candidate_id,
            name="Green Bowl Family Bistro",
            category="dining",
            tags=["lighter_options", "child_friendly"],
        ),
        poi_detail={"poi_id": candidate_id},
        opening_hours={"is_open": True},
        queue={"queue_id": f"queue_{candidate_id}", "status": "open", "wait_minutes": 10},
        table_availability={
            "restaurant_id": candidate_id,
            "available": True,
            "time_slots": ["17:30"],
        },
        tool_results=[
            _tool_result("get_poi_detail", candidate_id),
            _tool_result("check_opening_hours", candidate_id),
            _tool_result("check_queue", candidate_id),
            _tool_result("check_table_availability", candidate_id),
        ],
    )


def _collection() -> CandidateCollectionResult:
    return CandidateCollectionResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        activity_candidates=[_activity().candidate],
        dining_candidates=[_dining().candidate],
        executor_version="test-executor",
    )


def _enrichment() -> CandidateEnrichmentResult:
    activity = _activity()
    dining = _dining()
    return CandidateEnrichmentResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        enriched_activity_candidates=[activity],
        enriched_dining_candidates=[dining],
        route_matrix=[
            RouteMatrixEntry(
                origin_candidate_id=activity.candidate.candidate_id,
                destination_candidate_id=dining.candidate.candidate_id,
                provider="mock_world",
                mode="walking",
                status="succeeded",
                route_json={"summary": "Short walk"},
                distance_meters=850,
                duration_minutes=12,
                tool_event_id=uuid4(),
            )
        ],
        tool_results=[*activity.tool_results, *dining.tool_results],
        enricher_version="test-enricher",
    )


def _settings(*, enabled: bool) -> Settings:
    return Settings(
        _env_file=None,
        llm_enabled=enabled,
        llm_api_key="local-test-key" if enabled else None,
        llm_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1" if enabled else None,
        llm_model_id="qwen3.6-plus" if enabled else None,
    )


def _metadata_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def test_factory_defaults_to_deterministic_adapters_when_llm_disabled() -> None:
    adapters = build_agent_adapters(_settings(enabled=False))

    assert isinstance(adapters.supervisor, DeterministicSupervisorAgent)
    assert isinstance(adapters.discovery, DeterministicDiscoveryAgent)
    assert isinstance(adapters.dining, DeterministicDiningAgent)
    assert isinstance(adapters.itinerary_planner, DeterministicItineraryPlannerAgent)
    assert isinstance(adapters.validator_recovery, DeterministicValidatorRecoveryAgent)


def test_factory_enables_llm_for_only_three_bounded_agents() -> None:
    adapters = build_agent_adapters(_settings(enabled=True), llm_client=FakeLLMClient({}))

    assert isinstance(adapters.supervisor, DeterministicSupervisorAgent)
    assert isinstance(adapters.discovery, LLMDiscoveryAgent)
    assert isinstance(adapters.dining, LLMDiningAgent)
    assert isinstance(adapters.itinerary_planner, LLMItineraryPlannerAgent)
    assert isinstance(adapters.validator_recovery, DeterministicValidatorRecoveryAgent)


def test_factory_with_incomplete_llm_config_uses_safe_fallbacks() -> None:
    settings = Settings(
        _env_file=None,
        llm_enabled=True,
        llm_api_key=None,
        llm_base_url=None,
        llm_model_id=None,
    )
    adapters = build_agent_adapters(settings)

    result = adapters.discovery.summarize(_plan(), _collection(), _enrichment())

    assert isinstance(adapters.discovery, LLMDiscoveryAgent)
    assert result.adapter_version == "deterministic_discovery_v1"
    assert result.output_json["llm"]["fallback_reason"] == "llm_config_incomplete"


def test_llm_discovery_success_records_safe_normalized_metadata() -> None:
    client = FakeLLMClient(
        {
            "summary": "活动候选适合亲子下午安排。",
            "candidate_ids": ["activity_museum_001"],
            "tool_names_used": ["get_poi_detail", "check_opening_hours"],
            "risk_codes": [],
        }
    )
    result = LLMDiscoveryAgent(client=client).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "llm_discovery_v0"
    assert result.role == "discovery"
    assert result.output_json["candidate_ids"] == ["activity_museum_001"]
    assert result.output_json["llm"]["usage"] == {
        "input_count": 3,
        "output_count": 2,
        "total_count": 5,
    }
    text = _metadata_text(result.model_dump(mode="json"))
    assert "prompt_tokens" not in text
    assert "completion_tokens" not in text
    assert "total_tokens" not in text
    assert "local-test-key" not in text
    assert "tool_event_id" not in text
    assert "action_id" not in text
    assert client.calls


def test_llm_dining_success_records_safe_normalized_metadata() -> None:
    result = LLMDiningAgent(
        client=FakeLLMClient(
            {
                "summary": "餐厅候选符合清淡和亲子需求。",
                "candidate_ids": ["restaurant_light_001"],
                "tool_names_used": ["get_poi_detail", "check_table_availability"],
                "risk_codes": [],
            }
        )
    ).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "llm_dining_v0"
    assert result.role == "dining"
    assert result.output_json["candidate_ids"] == ["restaurant_light_001"]
    assert result.output_json["llm"]["model_id"] == "qwen3.6-plus"


def test_llm_adapter_falls_back_for_invalid_candidate_ids() -> None:
    result = LLMDiscoveryAgent(
        client=FakeLLMClient(
            {
                "summary": "bad",
                "candidate_ids": ["missing"],
                "tool_names_used": ["get_poi_detail"],
            }
        )
    ).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "deterministic_discovery_v1"
    assert result.output_json["llm"]["status"] == "fallback"
    assert result.output_json["llm"]["fallback_reason"] == "invalid_candidate_ids"


def test_llm_adapter_falls_back_for_policy_mismatch() -> None:
    result = LLMDiningAgent(
        client=FakeLLMClient(
            {
                "summary": "bad",
                "candidate_ids": ["restaurant_light_001"],
                "tool_names_used": ["reserve_restaurant"],
            }
        )
    ).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "deterministic_dining_v1"
    assert result.output_json["llm"]["fallback_reason"] == "agent_policy_mismatch"


def test_llm_adapter_falls_back_for_schema_mismatch() -> None:
    result = LLMDiningAgent(
        client=FakeLLMClient(
            {
                "candidate_ids": ["restaurant_light_001"],
                "tool_names_used": ["get_poi_detail"],
            }
        )
    ).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "deterministic_dining_v1"
    assert result.output_json["llm"]["fallback_reason"] == "llm_schema_mismatch"


def test_llm_adapter_falls_back_for_provider_timeout() -> None:
    result = LLMDiscoveryAgent(
        client=FakeLLMClient(
            error=LLMProviderError("LLM request timed out.", fallback_reason="llm_timeout")
        )
    ).summarize(_plan(), _collection(), _enrichment())

    assert result.adapter_version == "deterministic_discovery_v1"
    assert result.output_json["llm"]["fallback_reason"] == "llm_timeout"


def test_llm_itinerary_planner_can_select_existing_draft_ids_only() -> None:
    result, drafts = LLMItineraryPlannerAgent(
        client=FakeLLMClient(
            {
                "summary": "保留当前最稳妥的草案。",
                "draft_ids": ["draft_1"],
            }
        )
    ).generate(_plan(), _enrichment())

    assert result.adapter_version == "llm_itinerary_planner_v0"
    assert [draft.draft_id for draft in drafts.drafts] == ["draft_1"]
    assert result.output_json["llm"]["usage"]["total_count"] == 5


def test_llm_itinerary_planner_falls_back_for_invalid_draft_ids() -> None:
    result, drafts = LLMItineraryPlannerAgent(
        client=FakeLLMClient(
            {
                "summary": "bad",
                "draft_ids": ["missing"],
            }
        )
    ).generate(_plan(), _enrichment())

    assert result.adapter_version == "deterministic_itinerary_planner_v1"
    assert [draft.draft_id for draft in drafts.drafts] == ["draft_1"]
    assert result.output_json["llm"]["fallback_reason"] == "invalid_draft_ids"


def test_llm_itinerary_planner_falls_back_for_duplicate_draft_ids() -> None:
    result, drafts = LLMItineraryPlannerAgent(
        client=FakeLLMClient(
            {
                "summary": "bad",
                "draft_ids": ["draft_1", "draft_1"],
            }
        )
    ).generate(_plan(), _enrichment())

    assert result.adapter_version == "deterministic_itinerary_planner_v1"
    assert [draft.draft_id for draft in drafts.drafts] == ["draft_1"]
    assert result.output_json["llm"]["fallback_reason"] == "invalid_draft_ids"


def test_llm_itinerary_planner_falls_back_when_no_deterministic_drafts_exist() -> None:
    empty = CandidateEnrichmentResult(
        run_id=uuid4(),
        provider_profile="mock_world",
        enricher_version="test-enricher",
    )

    result, drafts = LLMItineraryPlannerAgent(client=FakeLLMClient({})).generate(_plan(), empty)

    assert result.adapter_version == "deterministic_itinerary_planner_v1"
    assert drafts.drafts == []
    assert result.output_json["llm"]["fallback_reason"] == "no_deterministic_drafts"
