from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.benchmark.failure_profiles import (
    ROUTE_UNAVAILABLE_PROFILE_ID,
    build_benchmark_failure_injector,
    failure_profile_metadata,
)
from backend.app.tool_gateway import ToolDefinition, ToolGatewayRequest


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
        "injected_error_type": "route_infeasible",
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
            "injected_error_type": "route_infeasible",
        }
    ]
