from __future__ import annotations

import pytest

from backend.app.planning import (
    DeterministicIntentParser,
    DeterministicQueryPlanner,
    QueryPlanError,
)
from backend.app.tool_gateway.registry import WRITE_TOOLS


def _family_intent():
    return DeterministicIntentParser().parse(
        "This afternoon I want to go out with my wife and child for a few hours. "
        "Not too far. My child is 5, and my wife is trying to eat lighter."
    )


def test_mock_world_query_plan_includes_initial_read_calls() -> None:
    plan = DeterministicQueryPlanner().build(_family_intent())

    initial_by_name = {call.tool_name: call for call in plan.initial_tool_calls}

    assert plan.provider_profile == "mock_world"
    assert initial_by_name["search_poi"].provider == "mock_world"
    activity_calls = [
        call
        for call in plan.initial_tool_calls
        if call.tool_name == "search_poi" and call.payload["category"] == "activity"
    ]
    dining_calls = [
        call
        for call in plan.initial_tool_calls
        if call.tool_name == "search_poi" and call.payload["category"] == "dining"
    ]
    assert len(activity_calls) == 1
    assert len(dining_calls) == 1
    assert activity_calls[0].payload["tags"] == ["child_friendly"]
    assert "lighter_options" in dining_calls[0].payload["tags"]
    assert "child_friendly" in dining_calls[0].payload["tags"]
    assert any(call.tool_name == "check_weather" for call in plan.initial_tool_calls)
    assert all(call.tool_name not in WRITE_TOOLS for call in plan.initial_tool_calls)


def test_mock_world_query_plan_includes_enrichment_and_route_templates() -> None:
    plan = DeterministicQueryPlanner().build(_family_intent())

    enrichment_names = {template.tool_name for template in plan.candidate_enrichment_templates}
    route_names = {template.tool_name for template in plan.route_templates}

    assert {
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
        "check_ticket_availability",
    } <= enrichment_names
    assert route_names == {"check_route"}
    route_template = plan.route_templates[0]
    assert route_template.required_inputs == ["origin_id", "destination_id"]
    assert route_template.payload_template["mode"] == "walking"


def test_query_plan_forbids_all_write_tools_before_confirmation() -> None:
    plan = DeterministicQueryPlanner().build(_family_intent())

    assert plan.forbidden_write_tools_before_confirmation == list(WRITE_TOOLS)


def test_amap_query_plan_excludes_mock_only_availability_templates() -> None:
    plan = DeterministicQueryPlanner().build(_family_intent(), provider_profile="amap")

    assert plan.provider_profile == "amap"
    assert all(call.provider == "amap" for call in plan.initial_tool_calls)
    assert {call.tool_name for call in plan.initial_tool_calls} == {"search_poi", "check_weather"}
    assert {template.tool_name for template in plan.candidate_enrichment_templates} == {"get_poi_detail"}
    assert {template.tool_name for template in plan.route_templates} == {"check_route"}
    assert not {
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
        "check_ticket_availability",
    } & {template.tool_name for template in plan.candidate_enrichment_templates}


def test_unsupported_provider_profile_is_rejected() -> None:
    with pytest.raises(QueryPlanError, match="Unsupported provider_profile"):
        DeterministicQueryPlanner().build(_family_intent(), provider_profile="real_world")
