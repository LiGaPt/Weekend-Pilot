from __future__ import annotations

from backend.app.planning.errors import QueryPlanError
from backend.app.planning.schemas import LocalLifeIntent, PlannedToolCall, QueryPlan, ToolCallTemplate
from backend.app.tool_gateway.registry import WRITE_TOOLS


class DeterministicQueryPlanner:
    planner_version = "deterministic_query_planner_v1"
    _SUPPORTED_PROFILES = {"mock_world", "amap"}

    def build(self, intent: LocalLifeIntent, provider_profile: str = "mock_world") -> QueryPlan:
        if provider_profile not in self._SUPPORTED_PROFILES:
            raise QueryPlanError(f"Unsupported provider_profile: {provider_profile}")

        initial_tool_calls = self._build_initial_tool_calls(intent, provider_profile)

        if provider_profile == "mock_world":
            enrichment_templates = self._build_mock_world_enrichment_templates(provider_profile)
            route_templates = self._build_route_templates(provider_profile)
            notes = ["Planning only; planned tool calls are not executed by the query planner."]
        else:
            enrichment_templates = self._build_amap_enrichment_templates(provider_profile)
            route_templates = self._build_route_templates(provider_profile)
            notes = ["AMAP query planning only includes read tools supported by Task 006."]

        return QueryPlan(
            intent=intent,
            provider_profile=provider_profile,
            initial_tool_calls=initial_tool_calls,
            candidate_enrichment_templates=enrichment_templates,
            route_templates=route_templates,
            forbidden_write_tools_before_confirmation=list(WRITE_TOOLS),
            planner_version=self.planner_version,
            notes=notes,
        )

    def _build_initial_tool_calls(self, intent: LocalLifeIntent, provider_profile: str) -> list[PlannedToolCall]:
        if provider_profile == "amap":
            return self._build_amap_initial_tool_calls(intent, provider_profile)

        activity_tags = []
        if intent.constraints.child_friendly:
            activity_tags.append("child_friendly")

        dining_tags = []
        if intent.constraints.child_friendly:
            dining_tags.append("child_friendly")
        for preference in intent.dining_preferences:
            if preference not in dining_tags:
                dining_tags.append(preference)

        return [
            PlannedToolCall(
                tool_name="search_poi",
                provider=provider_profile,
                payload={
                    "query": self._mock_world_activity_query(intent),
                    "category": "activity",
                    "tags": activity_tags,
                    "limit": 5,
                },
            ),
            PlannedToolCall(
                tool_name="search_poi",
                provider=provider_profile,
                payload={
                    "query": self._mock_world_dining_query(intent),
                    "category": "dining",
                    "tags": dining_tags,
                    "limit": 5,
                },
            ),
            PlannedToolCall(
                tool_name="check_weather",
                provider=provider_profile,
                payload={"location": intent.origin_text or "徐汇"},
            ),
        ]

    def _build_amap_initial_tool_calls(self, intent: LocalLifeIntent, provider_profile: str) -> list[PlannedToolCall]:
        return [
            PlannedToolCall(
                tool_name="search_poi",
                provider=provider_profile,
                payload={
                    "keywords": self._activity_query(intent),
                    "city": "Shanghai",
                    "page_size": 5,
                },
            ),
            PlannedToolCall(
                tool_name="search_poi",
                provider=provider_profile,
                payload={
                    "keywords": self._dining_query(intent),
                    "city": "Shanghai",
                    "page_size": 5,
                },
            ),
            PlannedToolCall(
                tool_name="check_weather",
                provider=provider_profile,
                payload={"city": "310000", "extensions": "base"},
            ),
        ]

    def _build_mock_world_enrichment_templates(self, provider_profile: str) -> list[ToolCallTemplate]:
        return [
            ToolCallTemplate(
                tool_name="get_poi_detail",
                provider=provider_profile,
                required_inputs=["poi_id"],
                payload_template={"poi_id": "{poi_id}"},
            ),
            ToolCallTemplate(
                tool_name="check_opening_hours",
                provider=provider_profile,
                required_inputs=["poi_id"],
                payload_template={"poi_id": "{poi_id}"},
            ),
            ToolCallTemplate(
                tool_name="check_queue",
                provider=provider_profile,
                required_inputs=["poi_id"],
                payload_template={"poi_id": "{poi_id}"},
            ),
            ToolCallTemplate(
                tool_name="check_table_availability",
                provider=provider_profile,
                required_inputs=["restaurant_id"],
                payload_template={"restaurant_id": "{restaurant_id}"},
            ),
            ToolCallTemplate(
                tool_name="check_ticket_availability",
                provider=provider_profile,
                required_inputs=["poi_id"],
                payload_template={"poi_id": "{poi_id}"},
            ),
        ]

    def _build_amap_enrichment_templates(self, provider_profile: str) -> list[ToolCallTemplate]:
        return [
            ToolCallTemplate(
                tool_name="get_poi_detail",
                provider=provider_profile,
                required_inputs=["poi_id"],
                payload_template={"poi_id": "{poi_id}"},
            )
        ]

    def _build_route_templates(self, provider_profile: str) -> list[ToolCallTemplate]:
        if provider_profile == "amap":
            return [
                ToolCallTemplate(
                    tool_name="check_route",
                    provider=provider_profile,
                    required_inputs=["origin", "destination"],
                    payload_template={
                        "origin": "{origin}",
                        "destination": "{destination}",
                        "mode": "walking",
                    },
                )
            ]

        return [
            ToolCallTemplate(
                tool_name="check_route",
                provider=provider_profile,
                required_inputs=["origin_id", "destination_id"],
                payload_template={
                    "origin_id": "{origin_id}",
                    "destination_id": "{destination_id}",
                    "mode": "walking",
                },
            )
        ]

    def _activity_query(self, intent: LocalLifeIntent) -> str:
        if intent.scenario_type == "family" or intent.constraints.child_friendly:
            return "family child friendly activity"
        return "local activity"

    def _dining_query(self, intent: LocalLifeIntent) -> str:
        if "lighter_options" in intent.dining_preferences and intent.constraints.child_friendly:
            return "lighter family dining"
        if "lighter_options" in intent.dining_preferences:
            return "lighter dining"
        if intent.constraints.child_friendly:
            return "family dining"
        return "local dining"

    def _mock_world_activity_query(self, intent: LocalLifeIntent) -> str:
        if intent.constraints.child_friendly:
            return "child_friendly"
        return "activity"

    def _mock_world_dining_query(self, intent: LocalLifeIntent) -> str:
        if "lighter_options" in intent.dining_preferences:
            return "lighter_options"
        if intent.constraints.child_friendly:
            return "child_friendly"
        return "restaurant"
