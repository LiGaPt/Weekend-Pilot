from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_profiles import (
    QUEUE_CLOSED_AND_BUDGET_CONSTRAINT_PROFILE_ID,
    ROUTE_UNAVAILABLE_PROFILE_ID,
    ROUTE_AND_DINING_UNAVAILABLE_PROFILE_ID,
    TABLE_UNAVAILABLE_AND_REPLAN_REQUIRED_PROFILE_ID,
    TICKET_SOLD_OUT_AND_ROUTE_UNAVAILABLE_PROFILE_ID,
    TICKET_SOLD_OUT_AND_BAD_WEATHER_PROFILE_ID,
    build_benchmark_failure_injector,
    failure_profile_metadata,
)
from backend.app.tool_gateway import (
    StaticToolFailureInjector,
    ToolDefinition,
    ToolFailureInjectionRule,
    ToolGatewayRequest,
)


def test_no_failure_profile_returns_no_injector() -> None:
    assert build_benchmark_failure_injector(None) is None


def test_route_unavailable_profile_injects_check_route_failure() -> None:
    injector = build_benchmark_failure_injector(ROUTE_UNAVAILABLE_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_route",
            payload={"origin_id": "activity", "destination_id": "dining"},
        ),
        ToolDefinition(name="check_route", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "failed"
    assert decision.response_json is None
    assert decision.error_json["error_type"] == "failure_injected"
    assert decision.error_json["details"] == {
        "profile_id": "route_unavailable_v0",
        "rule_id": "route_unavailable_v0.check_route",
        "tool_name": "check_route",
        "effect_kind": "hard_failure",
        "effect_type": "route_infeasible",
    }


def test_route_unavailable_profile_does_not_inject_other_read_tools() -> None:
    injector = build_benchmark_failure_injector(ROUTE_UNAVAILABLE_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(run_id=uuid4(), tool_name="search_poi", payload={"query": "family"}),
        ToolDefinition(name="search_poi", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is None


def test_route_unavailable_profile_does_not_inject_write_tools() -> None:
    injector = build_benchmark_failure_injector(ROUTE_UNAVAILABLE_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="reserve_restaurant",
            payload={"restaurant_id": "restaurant"},
            user_confirmed=True,
            target_id="restaurant",
            idempotency_key="reserve-1",
        ),
        ToolDefinition(name="reserve_restaurant", tool_type="write", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is None


def test_unknown_failure_profile_raises_benchmark_harness_error() -> None:
    with pytest.raises(BenchmarkHarnessError, match="Unknown benchmark failure profile"):
        build_benchmark_failure_injector("missing_profile")


def test_failure_profile_metadata_is_sanitized() -> None:
    metadata = failure_profile_metadata(ROUTE_UNAVAILABLE_PROFILE_ID)

    assert metadata["profile_id"] == "route_unavailable_v0"
    assert metadata["rules"] == [
        {
            "rule_id": "route_unavailable_v0.check_route",
            "tool_name": "check_route",
            "effect_kind": "hard_failure",
            "effect_type": "route_infeasible",
            "gateway_status": "failed",
        }
    ]


def test_route_and_dining_unavailable_profile_overrides_queue_response() -> None:
    injector = build_benchmark_failure_injector(ROUTE_AND_DINING_UNAVAILABLE_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_queue",
            payload={"poi_id": "restaurant-queue-1"},
        ),
        ToolDefinition(name="check_queue", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "succeeded"
    assert decision.response_json == {
        "queue": {
            "poi_id": "restaurant-queue-1",
            "status": "closed",
            "wait_minutes": 90,
            "parties_ahead": 18,
        }
    }
    assert decision.error_json == {
        "error_type": "failure_injected_response",
        "message": "Benchmark response override injected for tool call.",
        "details": {
            "profile_id": "route_and_dining_unavailable_v0",
            "rule_id": "route_and_dining_unavailable_v0.check_queue",
            "tool_name": "check_queue",
            "effect_kind": "response_override",
            "effect_type": "dining_unavailable",
        },
    }


def test_ticket_sold_out_and_bad_weather_profile_overrides_weather_with_location_placeholder() -> None:
    injector = build_benchmark_failure_injector(TICKET_SOLD_OUT_AND_BAD_WEATHER_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_weather",
            payload={"location": "Shanghai"},
        ),
        ToolDefinition(name="check_weather", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "succeeded"
    assert decision.response_json == {
        "weather": {
            "location": "Shanghai",
            "date": "2026-05-16",
            "condition": "中雨",
            "temperature_c": 20,
            "precipitation_chance": 0.92,
            "advisory": "强降雨，建议室内或取消户外活动。",
        }
    }


def test_ticket_sold_out_and_route_unavailable_profile_overrides_ticket_response() -> None:
    injector = build_benchmark_failure_injector(TICKET_SOLD_OUT_AND_ROUTE_UNAVAILABLE_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_ticket_availability",
            payload={"poi_id": "activity-7"},
        ),
        ToolDefinition(name="check_ticket_availability", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "succeeded"
    assert decision.response_json == {
        "ticket_availability": {
            "poi_id": "activity-7",
            "available": False,
            "time_slots": [],
            "remaining": 0,
            "price_cents": 0,
        }
    }
    assert decision.error_json["details"]["effect_type"] == "ticket_sold_out"


def test_queue_closed_and_budget_constraint_profile_overrides_queue_without_provider_call() -> None:
    injector = build_benchmark_failure_injector(QUEUE_CLOSED_AND_BUDGET_CONSTRAINT_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_queue",
            payload={"poi_id": "restaurant-queue-9"},
        ),
        ToolDefinition(name="check_queue", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "succeeded"
    assert decision.response_json == {
        "queue": {
            "poi_id": "restaurant-queue-9",
            "status": "closed",
            "wait_minutes": 120,
            "parties_ahead": 24,
        }
    }
    assert decision.error_json["details"]["effect_type"] == "queue_closed"


def test_table_unavailable_and_replan_required_profile_overrides_table_response() -> None:
    injector = build_benchmark_failure_injector(TABLE_UNAVAILABLE_AND_REPLAN_REQUIRED_PROFILE_ID)
    assert injector is not None

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_table_availability",
            payload={"restaurant_id": "restaurant-9"},
        ),
        ToolDefinition(name="check_table_availability", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.status == "succeeded"
    assert decision.response_json == {
        "table_availability": {
            "restaurant_id": "restaurant-9",
            "available": False,
            "time_slots": [],
            "max_party_size": 0,
            "notes": "Chaos profile injected unavailable table capacity.",
        }
    }
    assert decision.error_json["details"]["effect_type"] == "table_unavailable"


def test_failure_profile_metadata_covers_all_supported_benchmark_profiles() -> None:
    assert failure_profile_metadata(TICKET_SOLD_OUT_AND_ROUTE_UNAVAILABLE_PROFILE_ID) == {
        "profile_id": "ticket_sold_out_and_route_unavailable_v0",
        "rules": [
            {
                "rule_id": "ticket_sold_out_and_route_unavailable_v0.check_ticket_availability",
                "tool_name": "check_ticket_availability",
                "effect_kind": "response_override",
                "effect_type": "ticket_sold_out",
                "gateway_status": "succeeded",
            },
            {
                "rule_id": "ticket_sold_out_and_route_unavailable_v0.check_route",
                "tool_name": "check_route",
                "effect_kind": "hard_failure",
                "effect_type": "route_infeasible",
                "gateway_status": "failed",
            },
        ],
    }
    assert failure_profile_metadata(QUEUE_CLOSED_AND_BUDGET_CONSTRAINT_PROFILE_ID) == {
        "profile_id": "queue_closed_and_budget_constraint_v0",
        "rules": [
            {
                "rule_id": "queue_closed_and_budget_constraint_v0.check_queue",
                "tool_name": "check_queue",
                "effect_kind": "response_override",
                "effect_type": "queue_closed",
                "gateway_status": "succeeded",
            }
        ],
    }
    assert failure_profile_metadata(TABLE_UNAVAILABLE_AND_REPLAN_REQUIRED_PROFILE_ID) == {
        "profile_id": "table_unavailable_and_replan_required_v0",
        "rules": [
            {
                "rule_id": "table_unavailable_and_replan_required_v0.check_table_availability",
                "tool_name": "check_table_availability",
                "effect_kind": "response_override",
                "effect_type": "table_unavailable",
                "gateway_status": "succeeded",
            }
        ],
    }


def test_response_override_resolves_restaurant_id_placeholder() -> None:
    injector = StaticToolFailureInjector(
        profile_id="test_profile",
        rules=[
            ToolFailureInjectionRule(
                rule_id="test_profile.check_table_availability",
                tool_name="check_table_availability",
                effect_kind="response_override",
                effect_type="dining_unavailable",
                gateway_status="succeeded",
                response_json_template={
                    "table_availability": {
                        "restaurant_id": "{restaurant_id}",
                        "available": False,
                        "time_slots": [],
                        "max_party_size": 0,
                    }
                },
            )
        ],
    )

    decision = injector.maybe_inject(
        ToolGatewayRequest(
            run_id=uuid4(),
            tool_name="check_table_availability",
            payload={"restaurant_id": "restaurant-9"},
        ),
        ToolDefinition(name="check_table_availability", tool_type="read", default_provider="mock_world"),
        "mock_world",
    )

    assert decision is not None
    assert decision.response_json == {
        "table_availability": {
            "restaurant_id": "restaurant-9",
            "available": False,
            "time_slots": [],
            "max_party_size": 0,
        }
    }
