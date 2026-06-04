from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.planning import (
    Candidate,
    CandidateCollectionResult,
    CandidateEnricher,
    CandidateEnrichmentError,
    LocalLifeIntent,
    ParticipantProfile,
    PlannedToolCall,
    QueryPlan,
    ToolCallTemplate,
)
from backend.app.tool_gateway import ToolGatewayRequest, ToolGatewayResult


class FakeGateway:
    def __init__(self, results: list[ToolGatewayResult]) -> None:
        self.results = list(results)
        self.requests: list[ToolGatewayRequest] = []

    def invoke(self, request: ToolGatewayRequest) -> ToolGatewayResult:
        self.requests.append(request)
        return self.results.pop(0)


def _gateway_result(
    tool_name: str,
    *,
    provider: str = "mock_world",
    status: str = "succeeded",
    response_json: dict | None = None,
    error_json: dict | None = None,
    tool_event_id: UUID | None = None,
) -> ToolGatewayResult:
    return ToolGatewayResult(
        tool_name=tool_name,
        tool_type="read",
        provider=provider,
        status=status,
        response_json=response_json,
        error_json=error_json,
        tool_event_id=tool_event_id or uuid4(),
    )


def _intent() -> LocalLifeIntent:
    return LocalLifeIntent(
        raw_text="family afternoon",
        participants=ParticipantProfile(adults=2, children_ages=[5]),
        parser_version="test-parser",
    )


def _plan(
    *,
    provider_profile: str = "mock_world",
    initial_tool_calls: list[PlannedToolCall] | None = None,
    enrichment_templates: list[ToolCallTemplate] | None = None,
    route_templates: list[ToolCallTemplate] | None = None,
) -> QueryPlan:
    return QueryPlan(
        intent=_intent(),
        provider_profile=provider_profile,
        initial_tool_calls=initial_tool_calls or [],
        candidate_enrichment_templates=enrichment_templates or [],
        route_templates=route_templates or [],
        planner_version="test-planner",
    )


def _template(
    tool_name: str,
    *,
    provider: str = "mock_world",
    required_inputs: list[str] | None = None,
    payload_template: dict | None = None,
) -> ToolCallTemplate:
    return ToolCallTemplate(
        tool_name=tool_name,
        provider=provider,
        required_inputs=required_inputs or [],
        payload_template=payload_template or {},
    )


def _candidate(
    candidate_id: str,
    *,
    category: str = "activity",
    provider: str = "mock_world",
    location: dict | str | None = None,
    raw_payload: dict | None = None,
    source_call_index: int = 0,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        name=candidate_id,
        category=category,
        provider=provider,
        location=location,
        raw_payload=raw_payload or {},
        source_call_index=source_call_index,
    )


def _collection(
    *,
    activity_candidates: list[Candidate] | None = None,
    dining_candidates: list[Candidate] | None = None,
    other_candidates: list[Candidate] | None = None,
    provider_profile: str = "mock_world",
) -> CandidateCollectionResult:
    return CandidateCollectionResult(
        run_id=uuid4(),
        provider_profile=provider_profile,
        activity_candidates=activity_candidates or [],
        dining_candidates=dining_candidates or [],
        other_candidates=other_candidates or [],
        executor_version="test-executor",
    )


def _candidate_templates() -> list[ToolCallTemplate]:
    return [
        _template("get_poi_detail", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"}),
        _template("check_opening_hours", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"}),
        _template("check_queue", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"}),
        _template(
            "check_table_availability",
            required_inputs=["restaurant_id"],
            payload_template={"restaurant_id": "{restaurant_id}", "party_size": "{party_size}"},
        ),
        _template(
            "check_ticket_availability",
            required_inputs=["poi_id"],
            payload_template={"poi_id": "{poi_id}", "quantity": "{quantity}"},
        ),
    ]


def _mock_route_template() -> ToolCallTemplate:
    return _template(
        "check_route",
        required_inputs=["origin_id", "destination_id"],
        payload_template={"origin_id": "{origin_id}", "destination_id": "{destination_id}", "mode": "walking"},
    )


def _amap_route_template() -> ToolCallTemplate:
    return _template(
        "check_route",
        provider="amap",
        required_inputs=["origin", "destination"],
        payload_template={"origin": "{origin}", "destination": "{destination}", "mode": "walking"},
    )


def test_write_tool_in_enrichment_template_raises_before_gateway_invocation() -> None:
    gateway = FakeGateway([])
    plan = _plan(
        enrichment_templates=[
            _template("reserve_restaurant", required_inputs=["restaurant_id"]),
        ]
    )

    with pytest.raises(CandidateEnrichmentError, match="write tool"):
        CandidateEnricher(gateway).enrich(
            plan,
            _collection(activity_candidates=[_candidate("a1")]),
        )

    assert gateway.requests == []


def test_enricher_does_not_execute_initial_tool_calls() -> None:
    gateway = FakeGateway(
        [_gateway_result("get_poi_detail", response_json={"poi": {"poi_id": "a1"}})]
    )
    plan = _plan(
        initial_tool_calls=[
            PlannedToolCall(tool_name="search_poi", provider="mock_world", payload={"category": "activity"})
        ],
        enrichment_templates=[
            _template("get_poi_detail", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"})
        ],
    )

    CandidateEnricher(gateway).enrich(plan, _collection(activity_candidates=[_candidate("a1")]))

    assert [request.tool_name for request in gateway.requests] == ["get_poi_detail"]


def test_activity_candidate_gets_detail_opening_hours_and_ticket_availability() -> None:
    gateway = FakeGateway(
        [
            _gateway_result("get_poi_detail", response_json={"poi": {"poi_id": "a1", "name": "Museum"}}),
            _gateway_result("check_opening_hours", response_json={"opening_hours": {"is_open": True}}),
            _gateway_result("check_ticket_availability", response_json={"ticket_availability": {"available": True}}),
        ]
    )

    result = CandidateEnricher(gateway).enrich(
        _plan(enrichment_templates=_candidate_templates()),
        _collection(activity_candidates=[_candidate("a1")]),
    )

    enriched = result.enriched_activity_candidates[0]
    assert enriched.poi_detail == {"poi_id": "a1", "name": "Museum"}
    assert enriched.opening_hours == {"is_open": True}
    assert enriched.ticket_availability == {"available": True}
    assert [request.tool_name for request in gateway.requests] == [
        "get_poi_detail",
        "check_opening_hours",
        "check_ticket_availability",
    ]
    assert gateway.requests[-1].payload == {"poi_id": "a1", "quantity": 3}


def test_dining_candidate_gets_detail_opening_hours_queue_and_table_availability() -> None:
    gateway = FakeGateway(
        [
            _gateway_result("get_poi_detail", response_json={"poi": {"poi_id": "d1", "name": "Green Bowl"}}),
            _gateway_result("check_opening_hours", response_json={"opening_hours": {"is_open": True}}),
            _gateway_result("check_queue", response_json={"queue": {"wait_minutes": 12}}),
            _gateway_result("check_table_availability", response_json={"table_availability": {"available": True}}),
        ]
    )

    result = CandidateEnricher(gateway).enrich(
        _plan(enrichment_templates=_candidate_templates()),
        _collection(dining_candidates=[_candidate("d1", category="dining")]),
    )

    enriched = result.enriched_dining_candidates[0]
    assert enriched.poi_detail == {"poi_id": "d1", "name": "Green Bowl"}
    assert enriched.opening_hours == {"is_open": True}
    assert enriched.queue == {"wait_minutes": 12}
    assert enriched.table_availability == {"available": True}
    assert [request.tool_name for request in gateway.requests] == [
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
    ]
    assert gateway.requests[-1].payload == {"restaurant_id": "d1", "party_size": 3}


def test_other_candidates_are_skipped_by_default() -> None:
    gateway = FakeGateway([])

    result = CandidateEnricher(gateway).enrich(
        _plan(enrichment_templates=_candidate_templates()),
        _collection(other_candidates=[_candidate("o1", category="addon")]),
    )

    assert result.enriched_other_candidates == []
    assert gateway.requests == []


def test_other_candidates_can_be_enriched_when_limit_is_enabled() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "get_poi_detail",
                response_json={
                    "poi": {
                        "poi_id": "addon_drinks_001",
                        "vendor_id": "addon_drinks_001",
                        "menu": [{"sku": "water", "price_cents": 600}],
                    }
                },
            ),
            _gateway_result("check_opening_hours", response_json={"opening_hours": {"is_open": True}}),
        ]
    )

    result = CandidateEnricher(gateway, max_other_candidates=1).enrich(
        _plan(enrichment_templates=_candidate_templates()),
        _collection(other_candidates=[_candidate("addon_drinks_001", category="addon")]),
    )

    assert [item.candidate.candidate_id for item in result.enriched_other_candidates] == ["addon_drinks_001"]
    assert result.enriched_other_candidates[0].poi_detail == {
        "poi_id": "addon_drinks_001",
        "vendor_id": "addon_drinks_001",
        "menu": [{"sku": "water", "price_cents": 600}],
    }
    assert result.enriched_other_candidates[0].opening_hours == {"is_open": True}


def test_mock_world_route_matrix_uses_candidate_ids_for_activity_to_dining_pairs() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "check_route",
                response_json={"route": {"distance_meters": 500, "duration_minutes": 8}},
            ),
            _gateway_result(
                "check_route",
                response_json={"route": {"distance_meters": 900, "duration_minutes": 14}},
            ),
        ]
    )

    result = CandidateEnricher(gateway).enrich(
        _plan(route_templates=[_mock_route_template()]),
        _collection(
            activity_candidates=[_candidate("a1")],
            dining_candidates=[_candidate("d1", category="dining"), _candidate("d2", category="dining")],
        ),
    )

    assert [(entry.origin_candidate_id, entry.destination_candidate_id) for entry in result.route_matrix] == [
        ("a1", "d1"),
        ("a1", "d2"),
    ]
    assert [request.payload for request in gateway.requests] == [
        {"origin_id": "a1", "destination_id": "d1", "mode": "walking"},
        {"origin_id": "a1", "destination_id": "d2", "mode": "walking"},
    ]


def test_route_matrix_includes_dining_to_other_candidates_when_present() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "check_route",
                response_json={"route": {"distance_meters": 900, "duration_minutes": 13}},
            )
        ]
    )

    result = CandidateEnricher(gateway, max_other_candidates=1).enrich(
        _plan(route_templates=[_mock_route_template()]),
        _collection(
            dining_candidates=[_candidate("restaurant_light_001", category="dining")],
            other_candidates=[_candidate("addon_drinks_001", category="addon")],
        ),
    )

    assert [(entry.origin_candidate_id, entry.destination_candidate_id) for entry in result.route_matrix] == [
        ("restaurant_light_001", "addon_drinks_001"),
    ]
    assert gateway.requests[0].payload == {
        "origin_id": "restaurant_light_001",
        "destination_id": "addon_drinks_001",
        "mode": "walking",
    }


def test_amap_route_matrix_uses_string_locations_and_normalizes_duration_seconds() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "check_route",
                provider="amap",
                response_json={"route": {"distance_meters": 750, "duration_seconds": 125}},
            )
        ]
    )

    result = CandidateEnricher(gateway).enrich(
        _plan(provider_profile="amap", route_templates=[_amap_route_template()]),
        _collection(
            provider_profile="amap",
            activity_candidates=[_candidate("a1", provider="amap", location="121.1,31.1")],
            dining_candidates=[_candidate("d1", category="dining", provider="amap", location="121.2,31.2")],
        ),
    )

    assert gateway.requests[0].payload == {
        "origin": "121.1,31.1",
        "destination": "121.2,31.2",
        "mode": "walking",
    }
    assert result.route_matrix[0].distance_meters == 750
    assert result.route_matrix[0].duration_minutes == 3


def test_missing_amap_location_records_local_failure_when_fail_fast_is_false() -> None:
    gateway = FakeGateway([])

    result = CandidateEnricher(gateway).enrich(
        _plan(provider_profile="amap", route_templates=[_amap_route_template()]),
        _collection(
            provider_profile="amap",
            activity_candidates=[_candidate("a1", provider="amap", location=None)],
            dining_candidates=[_candidate("d1", category="dining", provider="amap", location="121.2,31.2")],
        ),
        fail_fast=False,
    )

    assert gateway.requests == []
    assert len(result.failed_tool_results) == 1
    assert result.failed_tool_results[0].error_json["code"] == "missing_template_input"
    assert result.route_matrix[0].status == "failed"
    assert result.route_matrix[0].error_json["missing_input"] == "origin"


def test_missing_amap_location_raises_when_fail_fast_is_true() -> None:
    gateway = FakeGateway([])

    with pytest.raises(CandidateEnrichmentError, match="missing template input"):
        CandidateEnricher(gateway).enrich(
            _plan(provider_profile="amap", route_templates=[_amap_route_template()]),
            _collection(
                provider_profile="amap",
                activity_candidates=[_candidate("a1", provider="amap", location=None)],
                dining_candidates=[_candidate("d1", category="dining", provider="amap", location="121.2,31.2")],
            ),
            fail_fast=True,
        )

    assert gateway.requests == []


def test_failed_gateway_result_is_collected_when_fail_fast_is_false() -> None:
    error = {"code": "provider_error", "message": "boom"}
    gateway = FakeGateway([_gateway_result("get_poi_detail", status="failed", error_json=error)])

    result = CandidateEnricher(gateway).enrich(
        _plan(
            enrichment_templates=[
                _template("get_poi_detail", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"})
            ]
        ),
        _collection(activity_candidates=[_candidate("a1")]),
        fail_fast=False,
    )

    assert len(result.failed_tool_results) == 1
    assert result.failed_tool_results[0].error_json == error
    assert result.enriched_activity_candidates[0].failed_tool_results[0].status == "failed"


def test_failed_gateway_result_raises_when_fail_fast_is_true() -> None:
    gateway = FakeGateway(
        [_gateway_result("get_poi_detail", status="rate_limited", error_json={"code": "rate_limited"})]
    )

    with pytest.raises(CandidateEnrichmentError, match="get_poi_detail"):
        CandidateEnricher(gateway).enrich(
            _plan(
                enrichment_templates=[
                    _template("get_poi_detail", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"})
                ]
            ),
            _collection(activity_candidates=[_candidate("a1")]),
            fail_fast=True,
        )


def test_malformed_success_response_is_collected_as_local_failure() -> None:
    gateway = FakeGateway([_gateway_result("get_poi_detail", response_json={"unexpected": {}})])

    result = CandidateEnricher(gateway).enrich(
        _plan(
            enrichment_templates=[
                _template("get_poi_detail", required_inputs=["poi_id"], payload_template={"poi_id": "{poi_id}"})
            ]
        ),
        _collection(activity_candidates=[_candidate("a1")]),
    )

    assert result.failed_tool_results[0].tool_event_id is None
    assert result.failed_tool_results[0].error_json["code"] == "malformed_tool_response"


def test_duplicate_candidates_are_deduped_and_candidate_limits_are_respected() -> None:
    gateway = FakeGateway([])

    result = CandidateEnricher(gateway, max_activity_candidates=2).enrich(
        _plan(),
        _collection(
            activity_candidates=[
                _candidate("a1", source_call_index=0),
                _candidate("a1", source_call_index=1),
                _candidate("a2", source_call_index=2),
                _candidate("a3", source_call_index=3),
            ]
        ),
    )

    assert [item.candidate.candidate_id for item in result.enriched_activity_candidates] == ["a1", "a2"]
    assert gateway.requests == []
