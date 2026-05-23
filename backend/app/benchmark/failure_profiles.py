from __future__ import annotations

from typing import Any

from backend.app.benchmark.errors import BenchmarkHarnessError
from backend.app.tool_gateway import StaticToolFailureInjector, ToolFailureInjectionRule


ROUTE_UNAVAILABLE_PROFILE_ID = "route_unavailable_v0"
ROUTE_AND_DINING_UNAVAILABLE_PROFILE_ID = "route_and_dining_unavailable_v0"
TICKET_SOLD_OUT_AND_BAD_WEATHER_PROFILE_ID = "ticket_sold_out_and_bad_weather_v0"

_ROUTE_UNAVAILABLE_RULE = ToolFailureInjectionRule(
    rule_id="route_unavailable_v0.check_route",
    tool_name="check_route",
    effect_kind="hard_failure",
    effect_type="route_infeasible",
    gateway_status="failed",
)
_ROUTE_AND_DINING_UNAVAILABLE_RULES = [
    ToolFailureInjectionRule(
        rule_id="route_and_dining_unavailable_v0.check_queue",
        tool_name="check_queue",
        effect_kind="response_override",
        effect_type="dining_unavailable",
        gateway_status="succeeded",
        response_json_template={
            "queue": {
                "poi_id": "{poi_id}",
                "status": "closed",
                "wait_minutes": 90,
                "parties_ahead": 18,
            }
        },
    ),
    ToolFailureInjectionRule(
        rule_id="route_and_dining_unavailable_v0.check_table_availability",
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
                "notes": "Chaos profile injected unavailable dining capacity.",
            }
        },
    ),
    ToolFailureInjectionRule(
        rule_id="route_and_dining_unavailable_v0.check_route",
        tool_name="check_route",
        effect_kind="hard_failure",
        effect_type="route_infeasible",
        gateway_status="failed",
    ),
]
_TICKET_SOLD_OUT_AND_BAD_WEATHER_RULES = [
    ToolFailureInjectionRule(
        rule_id="ticket_sold_out_and_bad_weather_v0.check_ticket_availability",
        tool_name="check_ticket_availability",
        effect_kind="response_override",
        effect_type="ticket_sold_out",
        gateway_status="succeeded",
        response_json_template={
            "ticket_availability": {
                "poi_id": "{poi_id}",
                "available": False,
                "time_slots": [],
                "remaining": 0,
                "price_cents": 0,
            }
        },
    ),
    ToolFailureInjectionRule(
        rule_id="ticket_sold_out_and_bad_weather_v0.check_weather",
        tool_name="check_weather",
        effect_kind="response_override",
        effect_type="bad_weather",
        gateway_status="succeeded",
        response_json_template={
            "weather": {
                "location": "{location}",
                "date": "2026-05-16",
                "condition": "中雨",
                "temperature_c": 20,
                "precipitation_chance": 0.92,
                "advisory": "强降雨，建议室内或取消户外活动。",
            }
        },
    ),
]
_PROFILE_RULES = {
    ROUTE_UNAVAILABLE_PROFILE_ID: [_ROUTE_UNAVAILABLE_RULE],
    ROUTE_AND_DINING_UNAVAILABLE_PROFILE_ID: _ROUTE_AND_DINING_UNAVAILABLE_RULES,
    TICKET_SOLD_OUT_AND_BAD_WEATHER_PROFILE_ID: _TICKET_SOLD_OUT_AND_BAD_WEATHER_RULES,
}


def build_benchmark_failure_injector(profile_id: str | None):
    if profile_id is None:
        return None
    rules = _PROFILE_RULES.get(profile_id)
    if rules is not None:
        return StaticToolFailureInjector(profile_id=profile_id, rules=rules)
    raise BenchmarkHarnessError(f"Unknown benchmark failure profile: {profile_id}")


def failure_profile_metadata(profile_id: str | None) -> dict[str, Any] | None:
    if profile_id is None:
        return None
    rules = _PROFILE_RULES.get(profile_id)
    if rules is not None:
        return {
            "profile_id": profile_id,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "tool_name": rule.tool_name,
                    "effect_kind": rule.effect_kind,
                    "effect_type": rule.effect_type,
                    "gateway_status": rule.gateway_status,
                }
                for rule in rules
            ],
        }
    raise BenchmarkHarnessError(f"Unknown benchmark failure profile: {profile_id}")
