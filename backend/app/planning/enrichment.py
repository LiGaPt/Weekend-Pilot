from __future__ import annotations

import math
from typing import Any

from backend.app.planning.candidates import Candidate, CandidateCollectionResult
from backend.app.planning.enriched_candidates import (
    CandidateEnrichmentResult,
    EnrichedCandidate,
    EnrichmentToolResult,
    RouteMatrixEntry,
)
from backend.app.planning.errors import CandidateEnrichmentError
from backend.app.planning.schemas import LocalLifeIntent, QueryPlan, ToolCallTemplate
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest, ToolGatewayResult
from backend.app.tool_gateway.registry import WRITE_TOOLS


_MISSING = object()


class CandidateEnricher:
    enricher_version = "candidate_enricher_v1"
    _USABLE_STATUSES = {"succeeded", "cached"}
    _ACTIVITY_TOOL_ORDER = ("get_poi_detail", "check_opening_hours", "check_ticket_availability")
    _DINING_TOOL_ORDER = (
        "get_poi_detail",
        "check_opening_hours",
        "check_queue",
        "check_table_availability",
    )
    _OTHER_TOOL_ORDER = ("get_poi_detail", "check_opening_hours")
    _RESPONSE_KEYS = {
        "get_poi_detail": ("poi", "poi_detail"),
        "check_opening_hours": ("opening_hours", "opening_hours"),
        "check_queue": ("queue", "queue"),
        "check_table_availability": ("table_availability", "table_availability"),
        "check_ticket_availability": ("ticket_availability", "ticket_availability"),
    }

    def __init__(
        self,
        gateway: ToolGateway,
        max_activity_candidates: int = 3,
        max_dining_candidates: int = 3,
        max_other_candidates: int = 0,
    ) -> None:
        self._gateway = gateway
        self._max_activity_candidates = max(0, max_activity_candidates)
        self._max_dining_candidates = max(0, max_dining_candidates)
        self._max_other_candidates = max(0, max_other_candidates)

    def enrich(
        self,
        plan: QueryPlan,
        collection: CandidateCollectionResult,
        fail_fast: bool = False,
        langsmith_trace_id: str | None = None,
    ) -> CandidateEnrichmentResult:
        self._reject_write_templates(plan)

        activity_candidates = self._select_candidates(
            collection.activity_candidates,
            self._max_activity_candidates,
        )
        dining_candidates = self._select_candidates(
            collection.dining_candidates,
            self._max_dining_candidates,
        )
        other_candidates = self._select_candidates(
            collection.other_candidates,
            self._max_other_candidates,
        )
        result = CandidateEnrichmentResult(
            run_id=collection.run_id,
            provider_profile=plan.provider_profile,
            world_profile=collection.world_profile,
            enricher_version=self.enricher_version,
        )
        templates_by_tool = {
            template.tool_name: template
            for template in plan.candidate_enrichment_templates
        }

        result.enriched_activity_candidates = [
            self._enrich_candidate(
                candidate,
                templates_by_tool,
                self._ACTIVITY_TOOL_ORDER,
                plan,
                result,
                fail_fast,
                langsmith_trace_id,
            )
            for candidate in activity_candidates
        ]
        result.enriched_dining_candidates = [
            self._enrich_candidate(
                candidate,
                templates_by_tool,
                self._DINING_TOOL_ORDER,
                plan,
                result,
                fail_fast,
                langsmith_trace_id,
            )
            for candidate in dining_candidates
        ]
        result.enriched_other_candidates = [
            self._enrich_candidate(
                candidate,
                templates_by_tool,
                self._OTHER_TOOL_ORDER,
                plan,
                result,
                fail_fast,
                langsmith_trace_id,
            )
            for candidate in other_candidates
        ]

        route_template = self._route_template(plan)
        if route_template is not None:
            self._build_route_matrix(
                route_template,
                activity_candidates,
                dining_candidates,
                other_candidates,
                collection,
                result,
                fail_fast,
                langsmith_trace_id,
            )

        return result

    def _reject_write_templates(self, plan: QueryPlan) -> None:
        for index, template in enumerate(plan.candidate_enrichment_templates + plan.route_templates):
            if template.tool_name in WRITE_TOOLS:
                raise CandidateEnrichmentError(
                    f"Template {index} is a write tool and cannot be executed before confirmation: "
                    f"{template.tool_name}"
                )

    def _enrich_candidate(
        self,
        candidate: Candidate,
        templates_by_tool: dict[str, ToolCallTemplate],
        tool_order: tuple[str, ...],
        plan: QueryPlan,
        result: CandidateEnrichmentResult,
        fail_fast: bool,
        langsmith_trace_id: str | None,
    ) -> EnrichedCandidate:
        enriched = EnrichedCandidate(candidate=candidate)
        for tool_name in tool_order:
            template = templates_by_tool.get(tool_name)
            if template is None:
                continue

            payload, missing_input = self._candidate_payload(template, candidate, plan.intent)
            if missing_input is not None:
                local_result = self._missing_input_result(
                    stage="candidate_enrichment",
                    tool_name=template.tool_name,
                    provider=template.provider,
                    missing_input=missing_input,
                    candidate_id=candidate.candidate_id,
                )
                self._record_failed_tool_result(result, local_result, fail_fast, enriched)
                continue

            gateway_result = self._gateway.invoke(
                ToolGatewayRequest(
                    run_id=result.run_id,
                    tool_name=template.tool_name,
                    provider=template.provider,
                    payload=payload,
                    user_confirmed=False,
                    langsmith_trace_id=langsmith_trace_id,
                )
            )
            tool_result = self._tool_result_from_gateway(
                gateway_result,
                stage="candidate_enrichment",
                candidate_id=candidate.candidate_id,
            )
            self._record_tool_result(result, tool_result, enriched)
            if gateway_result.status not in self._USABLE_STATUSES:
                self._record_failed_tool_result(result, tool_result, fail_fast, enriched, already_recorded=True)
                continue

            malformed_result = self._attach_candidate_response(enriched, gateway_result)
            if malformed_result is not None:
                self._record_failed_tool_result(result, malformed_result, fail_fast, enriched)

        return enriched

    def _build_route_matrix(
        self,
        template: ToolCallTemplate,
        activity_candidates: list[Candidate],
        dining_candidates: list[Candidate],
        other_candidates: list[Candidate],
        collection: CandidateCollectionResult,
        result: CandidateEnrichmentResult,
        fail_fast: bool,
        langsmith_trace_id: str | None,
    ) -> None:
        self._append_route_matrix_pairs(
            template,
            activity_candidates,
            dining_candidates,
            collection,
            result,
            fail_fast,
            langsmith_trace_id,
        )
        self._append_route_matrix_pairs(
            template,
            dining_candidates,
            other_candidates,
            collection,
            result,
            fail_fast,
            langsmith_trace_id,
        )

    def _append_route_matrix_pairs(
        self,
        template: ToolCallTemplate,
        origin_candidates: list[Candidate],
        destination_candidates: list[Candidate],
        collection: CandidateCollectionResult,
        result: CandidateEnrichmentResult,
        fail_fast: bool,
        langsmith_trace_id: str | None,
    ) -> None:
        for origin in origin_candidates:
            for destination in destination_candidates:
                payload, missing_input = self._route_payload(template, origin, destination)
                mode = self._route_mode(payload)
                if missing_input is not None:
                    local_result = self._missing_input_result(
                        stage="route_matrix",
                        tool_name=template.tool_name,
                        provider=template.provider,
                        missing_input=missing_input,
                        origin_candidate_id=origin.candidate_id,
                        destination_candidate_id=destination.candidate_id,
                    )
                    result.route_matrix.append(
                        RouteMatrixEntry(
                            origin_candidate_id=origin.candidate_id,
                            destination_candidate_id=destination.candidate_id,
                            provider=template.provider,
                            mode=mode,
                            status="failed",
                            error_json=local_result.error_json,
                        )
                    )
                    self._record_failed_tool_result(result, local_result, fail_fast)
                    continue

                gateway_result = self._gateway.invoke(
                    ToolGatewayRequest(
                        run_id=collection.run_id,
                        tool_name=template.tool_name,
                        provider=template.provider,
                        payload=payload,
                        user_confirmed=False,
                        langsmith_trace_id=langsmith_trace_id,
                    )
                )
                tool_result = self._tool_result_from_gateway(
                    gateway_result,
                    stage="route_matrix",
                    origin_candidate_id=origin.candidate_id,
                    destination_candidate_id=destination.candidate_id,
                )
                self._record_tool_result(result, tool_result)
                if gateway_result.status not in self._USABLE_STATUSES:
                    result.route_matrix.append(
                        RouteMatrixEntry(
                            origin_candidate_id=origin.candidate_id,
                            destination_candidate_id=destination.candidate_id,
                            provider=gateway_result.provider,
                            mode=mode,
                            status=gateway_result.status,
                            tool_event_id=gateway_result.tool_event_id,
                            error_json=gateway_result.error_json,
                        )
                    )
                    self._record_failed_tool_result(result, tool_result, fail_fast, already_recorded=True)
                    continue

                route = gateway_result.response_json.get("route") if isinstance(gateway_result.response_json, dict) else None
                if not isinstance(route, dict):
                    error = self._malformed_response_error(template.tool_name, "route")
                    result.route_matrix.append(
                        RouteMatrixEntry(
                            origin_candidate_id=origin.candidate_id,
                            destination_candidate_id=destination.candidate_id,
                            provider=gateway_result.provider,
                            mode=mode,
                            status="failed",
                            tool_event_id=gateway_result.tool_event_id,
                            error_json=error,
                        )
                    )
                    local_result = self._local_failed_result(
                        stage="route_matrix",
                        tool_name=template.tool_name,
                        provider=template.provider,
                        error_json=error,
                        response_json=gateway_result.response_json,
                        origin_candidate_id=origin.candidate_id,
                        destination_candidate_id=destination.candidate_id,
                    )
                    self._record_failed_tool_result(result, local_result, fail_fast)
                    continue

                result.route_matrix.append(
                    RouteMatrixEntry(
                        origin_candidate_id=origin.candidate_id,
                        destination_candidate_id=destination.candidate_id,
                        provider=gateway_result.provider,
                        mode=str(route.get("mode") or mode),
                        status=gateway_result.status,
                        route_json=route,
                        distance_meters=self._int_or_none(route.get("distance_meters")),
                        duration_minutes=self._duration_minutes(route),
                        tool_event_id=gateway_result.tool_event_id,
                    )
                )

    def _candidate_payload(
        self,
        template: ToolCallTemplate,
        candidate: Candidate,
        intent: LocalLifeIntent,
    ) -> tuple[dict[str, Any], str | None]:
        party_count = max(1, intent.participants.adults + len(intent.participants.children_ages))
        context = {
            "poi_id": self._text_or_none(candidate.raw_payload.get("poi_id")) or candidate.candidate_id,
            "restaurant_id": self._text_or_none(candidate.raw_payload.get("restaurant_id")) or candidate.candidate_id,
            "party_size": party_count,
            "quantity": party_count,
        }
        return self._resolve_payload(template, context)

    def _route_payload(
        self,
        template: ToolCallTemplate,
        origin: Candidate,
        destination: Candidate,
    ) -> tuple[dict[str, Any], str | None]:
        context = {
            "origin_id": origin.candidate_id,
            "destination_id": destination.candidate_id,
            "origin": origin.location if isinstance(origin.location, str) and origin.location.strip() else _MISSING,
            "destination": destination.location if isinstance(destination.location, str) and destination.location.strip() else _MISSING,
            "mode": "walking",
        }
        return self._resolve_payload(template, context)

    def _resolve_payload(
        self,
        template: ToolCallTemplate,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], str | None]:
        payload: dict[str, Any] = {}
        for key, template_value in template.payload_template.items():
            value = self._resolve_template_value(template_value, context)
            if value is _MISSING:
                continue
            payload[key] = value

        for input_name in template.required_inputs:
            value = payload.get(input_name, _MISSING)
            if value is _MISSING and input_name in context and context[input_name] is not _MISSING:
                value = context[input_name]
                payload[input_name] = value
            if value is _MISSING or value is None or value == "":
                return payload, input_name
        return payload, None

    def _resolve_template_value(self, template_value: Any, context: dict[str, Any]) -> Any:
        if not isinstance(template_value, str):
            return template_value
        if template_value.startswith("{") and template_value.endswith("}") and len(template_value) > 2:
            return context.get(template_value[1:-1], _MISSING)
        return template_value

    def _attach_candidate_response(
        self,
        enriched: EnrichedCandidate,
        gateway_result: ToolGatewayResult,
    ) -> EnrichmentToolResult | None:
        expected = self._RESPONSE_KEYS.get(gateway_result.tool_name)
        if expected is None:
            return None

        response_key, attribute_name = expected
        response_value = (
            gateway_result.response_json.get(response_key)
            if isinstance(gateway_result.response_json, dict)
            else None
        )
        if not isinstance(response_value, dict):
            return self._local_failed_result(
                stage="candidate_enrichment",
                tool_name=gateway_result.tool_name,
                provider=gateway_result.provider,
                error_json=self._malformed_response_error(gateway_result.tool_name, response_key),
                response_json=gateway_result.response_json,
                candidate_id=enriched.candidate.candidate_id,
            )

        setattr(enriched, attribute_name, response_value)
        return None

    def _record_tool_result(
        self,
        result: CandidateEnrichmentResult,
        tool_result: EnrichmentToolResult,
        enriched: EnrichedCandidate | None = None,
    ) -> None:
        result.tool_results.append(tool_result)
        if enriched is not None:
            enriched.tool_results.append(tool_result)

    def _record_failed_tool_result(
        self,
        result: CandidateEnrichmentResult,
        tool_result: EnrichmentToolResult,
        fail_fast: bool,
        enriched: EnrichedCandidate | None = None,
        *,
        already_recorded: bool = False,
    ) -> None:
        if not already_recorded:
            self._record_tool_result(result, tool_result, enriched)
        result.failed_tool_results.append(tool_result)
        if enriched is not None:
            enriched.failed_tool_results.append(tool_result)
        if fail_fast:
            if tool_result.error_json and tool_result.error_json.get("code") == "missing_template_input":
                raise CandidateEnrichmentError(
                    f"{tool_result.tool_name} failed because of missing template input "
                    f"{tool_result.error_json.get('missing_input')!r}."
                )
            raise CandidateEnrichmentError(
                f"{tool_result.tool_name!r} failed with status {tool_result.status!r}."
            )

    def _tool_result_from_gateway(
        self,
        gateway_result: ToolGatewayResult,
        *,
        stage: str,
        candidate_id: str | None = None,
        origin_candidate_id: str | None = None,
        destination_candidate_id: str | None = None,
    ) -> EnrichmentToolResult:
        return EnrichmentToolResult(
            stage=stage,
            candidate_id=candidate_id,
            origin_candidate_id=origin_candidate_id,
            destination_candidate_id=destination_candidate_id,
            tool_name=gateway_result.tool_name,
            provider=gateway_result.provider,
            status=gateway_result.status,
            response_json=gateway_result.response_json,
            error_json=gateway_result.error_json,
            tool_event_id=gateway_result.tool_event_id,
        )

    def _missing_input_result(
        self,
        *,
        stage: str,
        tool_name: str,
        provider: str,
        missing_input: str,
        candidate_id: str | None = None,
        origin_candidate_id: str | None = None,
        destination_candidate_id: str | None = None,
    ) -> EnrichmentToolResult:
        return self._local_failed_result(
            stage=stage,
            tool_name=tool_name,
            provider=provider,
            error_json={
                "code": "missing_template_input",
                "message": "Required template input could not be resolved.",
                "missing_input": missing_input,
            },
            candidate_id=candidate_id,
            origin_candidate_id=origin_candidate_id,
            destination_candidate_id=destination_candidate_id,
        )

    def _local_failed_result(
        self,
        *,
        stage: str,
        tool_name: str,
        provider: str,
        error_json: dict[str, Any],
        response_json: dict[str, Any] | None = None,
        candidate_id: str | None = None,
        origin_candidate_id: str | None = None,
        destination_candidate_id: str | None = None,
    ) -> EnrichmentToolResult:
        return EnrichmentToolResult(
            stage=stage,
            candidate_id=candidate_id,
            origin_candidate_id=origin_candidate_id,
            destination_candidate_id=destination_candidate_id,
            tool_name=tool_name,
            provider=provider,
            status="failed",
            response_json=response_json,
            error_json=error_json,
            tool_event_id=None,
        )

    def _malformed_response_error(self, tool_name: str, expected_key: str) -> dict[str, Any]:
        return {
            "code": "malformed_tool_response",
            "message": f"{tool_name} response must include an object at {expected_key!r}.",
            "expected_key": expected_key,
        }

    def _route_template(self, plan: QueryPlan) -> ToolCallTemplate | None:
        for template in plan.route_templates:
            if template.tool_name == "check_route":
                return template
        return None

    def _select_candidates(self, candidates: list[Candidate], limit: int) -> list[Candidate]:
        if limit <= 0:
            return []

        selected = []
        seen = set()
        for candidate in candidates:
            if candidate.candidate_id in seen:
                continue
            seen.add(candidate.candidate_id)
            selected.append(candidate)
            if len(selected) >= limit:
                break
        return selected

    def _route_mode(self, payload: dict[str, Any]) -> str:
        mode = payload.get("mode")
        return mode if isinstance(mode, str) and mode else "walking"

    def _duration_minutes(self, route: dict[str, Any]) -> int | None:
        duration_minutes = self._int_or_none(route.get("duration_minutes"))
        if duration_minutes is not None:
            return duration_minutes

        duration_seconds = self._int_or_none(route.get("duration_seconds"))
        if duration_seconds is None:
            return None
        return math.ceil(duration_seconds / 60)

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    @staticmethod
    def _text_or_none(value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None
