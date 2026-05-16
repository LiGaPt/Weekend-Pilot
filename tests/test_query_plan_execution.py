from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from backend.app.planning import (
    LocalLifeIntent,
    PlannedToolCall,
    QueryExecutionError,
    QueryPlan,
    QueryPlanExecutor,
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


def _intent() -> LocalLifeIntent:
    return LocalLifeIntent(raw_text="test request", parser_version="test-parser")


def _plan(
    initial_tool_calls: list[PlannedToolCall],
    *,
    provider_profile: str = "mock_world",
    enrichment_templates: list[ToolCallTemplate] | None = None,
    route_templates: list[ToolCallTemplate] | None = None,
) -> QueryPlan:
    return QueryPlan(
        intent=_intent(),
        provider_profile=provider_profile,
        initial_tool_calls=initial_tool_calls,
        candidate_enrichment_templates=enrichment_templates or [],
        route_templates=route_templates or [],
        planner_version="test-planner",
    )


def _gateway_result(
    tool_name: str,
    provider: str,
    *,
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


def test_executor_invokes_gateway_once_per_initial_call() -> None:
    run_id = uuid4()
    gateway = FakeGateway(
        [
            _gateway_result("search_poi", "mock_world", response_json={"results": []}),
            _gateway_result("check_weather", "mock_world", response_json={"weather": {"condition": "cloudy"}}),
        ]
    )
    plan = _plan(
        [
            PlannedToolCall(
                tool_name="search_poi",
                provider="mock_world",
                payload={"category": "activity"},
            ),
            PlannedToolCall(
                tool_name="check_weather",
                provider="mock_world",
                payload={"location": "徐汇"},
            ),
        ]
    )

    QueryPlanExecutor(gateway).execute_initial_calls(plan, run_id)

    assert [request.tool_name for request in gateway.requests] == ["search_poi", "check_weather"]
    assert all(request.run_id == run_id for request in gateway.requests)
    assert all(request.provider == "mock_world" for request in gateway.requests)
    assert all(request.user_confirmed is False for request in gateway.requests)
    assert gateway.requests[0].payload == {"category": "activity"}


def test_search_results_become_activity_dining_and_other_candidates() -> None:
    event_id = uuid4()
    gateway = FakeGateway(
        [
            _gateway_result(
                "search_poi",
                "mock_world",
                response_json={
                    "results": [
                        {
                            "poi_id": "activity-1",
                            "name": "Science Museum",
                            "category": "activity",
                            "address": "100 Museum Road",
                            "location": {"lat": 31.1, "lng": 121.4},
                            "tags": ["child_friendly", "indoor"],
                            "source": "fixture",
                        },
                        {
                            "id": "restaurant-1",
                            "name": "Green Bowl",
                            "category": "dining",
                            "address": "66 Healthy Lane",
                            "tags": "not-a-list",
                        },
                        {
                            "poi_id": "addon-1",
                            "name": "Water Stand",
                            "category": "addon",
                        },
                    ]
                },
                tool_event_id=event_id,
            )
        ]
    )
    plan = _plan(
        [
            PlannedToolCall(
                tool_name="search_poi",
                provider="mock_world",
                payload={"category": "activity"},
            )
        ]
    )

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4())

    assert [candidate.candidate_id for candidate in result.activity_candidates] == ["activity-1"]
    assert [candidate.candidate_id for candidate in result.dining_candidates] == ["restaurant-1"]
    assert [candidate.candidate_id for candidate in result.other_candidates] == ["addon-1"]
    activity = result.activity_candidates[0]
    assert activity.provider == "mock_world"
    assert activity.source == "fixture"
    assert activity.address == "100 Museum Road"
    assert activity.location == {"lat": 31.1, "lng": 121.4}
    assert activity.tags == ["child_friendly", "indoor"]
    assert activity.raw_payload["name"] == "Science Museum"
    assert activity.source_call_index == 0
    assert activity.tool_event_id == event_id
    assert result.dining_candidates[0].tags == []


def test_amap_shaped_search_result_without_tags_normalizes_safely() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "search_poi",
                "amap",
                response_json={
                    "results": [
                        {
                            "id": "B002",
                            "name": "Family Park",
                            "category": "Park",
                            "address": "",
                            "location": "121.480,31.230",
                            "source": "amap",
                        }
                    ]
                },
            )
        ]
    )
    plan = _plan(
        [PlannedToolCall(tool_name="search_poi", provider="amap", payload={"keywords": "park"})],
        provider_profile="amap",
    )

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4())

    assert result.activity_candidates == []
    assert result.dining_candidates == []
    assert len(result.other_candidates) == 1
    candidate = result.other_candidates[0]
    assert candidate.candidate_id == "B002"
    assert candidate.name == "Family Park"
    assert candidate.provider == "amap"
    assert candidate.source == "amap"
    assert candidate.tags == []


def test_weather_response_is_captured_separately() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "check_weather",
                "mock_world",
                response_json={"weather": {"location": "徐汇", "condition": "cloudy"}},
            )
        ]
    )
    plan = _plan(
        [PlannedToolCall(tool_name="check_weather", provider="mock_world", payload={"location": "徐汇"})]
    )

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4())

    assert result.weather == {"location": "徐汇", "condition": "cloudy"}
    assert result.activity_candidates == []
    assert result.dining_candidates == []


def test_failed_gateway_result_is_collected_when_fail_fast_is_false() -> None:
    error = {"code": "provider_error", "message": "provider failed"}
    gateway = FakeGateway(
        [
            _gateway_result("search_poi", "mock_world", status="failed", error_json=error),
            _gateway_result("check_weather", "mock_world", response_json={"weather": {"condition": "cloudy"}}),
        ]
    )
    plan = _plan(
        [
            PlannedToolCall(tool_name="search_poi", provider="mock_world", payload={"category": "activity"}),
            PlannedToolCall(tool_name="check_weather", provider="mock_world", payload={"location": "徐汇"}),
        ]
    )

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4(), fail_fast=False)

    assert len(result.tool_results) == 2
    assert len(result.failed_tool_results) == 1
    assert result.failed_tool_results[0].status == "failed"
    assert result.failed_tool_results[0].error_json == error
    assert result.weather == {"condition": "cloudy"}


def test_failed_gateway_result_raises_when_fail_fast_is_true() -> None:
    gateway = FakeGateway(
        [
            _gateway_result(
                "search_poi",
                "mock_world",
                status="rate_limited",
                error_json={"code": "rate_limited"},
            )
        ]
    )
    plan = _plan(
        [PlannedToolCall(tool_name="search_poi", provider="mock_world", payload={"category": "activity"})]
    )

    with pytest.raises(QueryExecutionError, match="search_poi"):
        QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4(), fail_fast=True)


def test_malformed_search_response_is_collected_when_fail_fast_is_false() -> None:
    gateway = FakeGateway(
        [_gateway_result("search_poi", "mock_world", response_json={"results": {"not": "a list"}})]
    )
    plan = _plan(
        [PlannedToolCall(tool_name="search_poi", provider="mock_world", payload={"category": "activity"})]
    )

    result = QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4(), fail_fast=False)

    assert result.activity_candidates == []
    assert len(result.failed_tool_results) == 1
    assert result.failed_tool_results[0].error_json["code"] == "malformed_search_response"


def test_initial_write_tool_raises_before_invoking_gateway() -> None:
    gateway = FakeGateway([])
    plan = _plan(
        [PlannedToolCall(tool_name="reserve_restaurant", provider="mock_world", payload={"restaurant_id": "r1"})]
    )

    with pytest.raises(QueryExecutionError, match="write tool"):
        QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4())

    assert gateway.requests == []


def test_executor_does_not_execute_enrichment_or_route_templates() -> None:
    gateway = FakeGateway([_gateway_result("search_poi", "mock_world", response_json={"results": []})])
    plan = _plan(
        [PlannedToolCall(tool_name="search_poi", provider="mock_world", payload={"category": "activity"})],
        enrichment_templates=[
            ToolCallTemplate(
                tool_name="reserve_restaurant",
                provider="mock_world",
                required_inputs=["restaurant_id"],
            )
        ],
        route_templates=[
            ToolCallTemplate(
                tool_name="check_route",
                provider="mock_world",
                required_inputs=["origin_id", "destination_id"],
            )
        ],
    )

    QueryPlanExecutor(gateway).execute_initial_calls(plan, uuid4())

    assert [request.tool_name for request in gateway.requests] == ["search_poi"]
