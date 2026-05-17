from __future__ import annotations

from typing import Any

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.tool_gateway import StaticToolFailureInjector, ToolFailureInjectionRule


ROUTE_UNAVAILABLE_PROFILE_ID = "route_unavailable_v0"

_ROUTE_UNAVAILABLE_RULE = ToolFailureInjectionRule(
    rule_id="route_unavailable_v0.check_route",
    tool_name="check_route",
    injected_error_type="route_infeasible",
)


def build_benchmark_failure_injector(profile_id: str | None):
    if profile_id is None:
        return None
    if profile_id == ROUTE_UNAVAILABLE_PROFILE_ID:
        return StaticToolFailureInjector(
            profile_id=ROUTE_UNAVAILABLE_PROFILE_ID,
            rules=[_ROUTE_UNAVAILABLE_RULE],
        )
    raise BenchmarkHarnessError(f"Unknown benchmark failure profile: {profile_id}")


def failure_profile_metadata(profile_id: str | None) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    if profile_id == ROUTE_UNAVAILABLE_PROFILE_ID:
        return {
            "profile_id": ROUTE_UNAVAILABLE_PROFILE_ID,
            "rules": [
                {
                    "rule_id": _ROUTE_UNAVAILABLE_RULE.rule_id,
                    "tool_name": _ROUTE_UNAVAILABLE_RULE.tool_name,
                    "injected_error_type": _ROUTE_UNAVAILABLE_RULE.injected_error_type,
                }
            ],
        }
    raise BenchmarkHarnessError(f"Unknown benchmark failure profile: {profile_id}")
