from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.planning.candidates import (
    Candidate,
    CandidateCollectionResult,
    InitialToolExecutionResult,
)
from backend.app.planning.errors import QueryExecutionError
from backend.app.planning.schemas import PlannedToolCall, QueryPlan
from backend.app.tool_gateway import ToolGateway, ToolGatewayRequest, ToolGatewayResult
from backend.app.tool_gateway.registry import WRITE_TOOLS


class QueryPlanExecutor:
    executor_version = "query_plan_executor_v1"
    _USABLE_STATUSES = {"succeeded", "cached"}

    def __init__(self, gateway: ToolGateway) -> None:
        self._gateway = gateway

    def execute_initial_calls(
        self,
        plan: QueryPlan,
        run_id: UUID,
        fail_fast: bool = False,
        langsmith_trace_id: str | None = None,
    ) -> CandidateCollectionResult:
        self._reject_initial_write_tools(plan)
        collection = CandidateCollectionResult(
            run_id=run_id,
            provider_profile=plan.provider_profile,
            executor_version=self.executor_version,
        )

        for source_call_index, call in enumerate(plan.initial_tool_calls):
            gateway_result = self._gateway.invoke(
                ToolGatewayRequest(
                    run_id=run_id,
                    tool_name=call.tool_name,
                    payload=call.payload,
                    provider=call.provider,
                    user_confirmed=False,
                    langsmith_trace_id=langsmith_trace_id,
                )
            )

            execution_result = self._execution_result(source_call_index, gateway_result)
            if gateway_result.status not in self._USABLE_STATUSES:
                self._record_failed_result(collection, execution_result, fail_fast)
                continue

            if call.tool_name == "search_poi":
                malformed_result = self._append_search_candidates(
                    collection,
                    call,
                    source_call_index,
                    gateway_result,
                )
                if malformed_result is not None:
                    self._record_failed_result(collection, malformed_result, fail_fast)
                    continue

            if call.tool_name == "check_weather":
                self._capture_weather(collection, gateway_result.response_json)

            collection.tool_results.append(execution_result)

        return collection

    def _reject_initial_write_tools(self, plan: QueryPlan) -> None:
        for index, call in enumerate(plan.initial_tool_calls):
            if call.tool_name in WRITE_TOOLS:
                raise QueryExecutionError(
                    f"Initial tool call {index} is a write tool and cannot be executed before confirmation: "
                    f"{call.tool_name}"
                )

    def _record_failed_result(
        self,
        collection: CandidateCollectionResult,
        result: InitialToolExecutionResult,
        fail_fast: bool,
    ) -> None:
        collection.tool_results.append(result)
        collection.failed_tool_results.append(result)
        if fail_fast:
            raise QueryExecutionError(
                f"Initial tool call {result.source_call_index} {result.tool_name!r} failed with status "
                f"{result.status!r}."
            )

    def _append_search_candidates(
        self,
        collection: CandidateCollectionResult,
        call: PlannedToolCall,
        source_call_index: int,
        gateway_result: ToolGatewayResult,
    ) -> InitialToolExecutionResult | None:
        response_json = gateway_result.response_json
        results = response_json.get("results") if isinstance(response_json, dict) else None
        if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
            return InitialToolExecutionResult(
                source_call_index=source_call_index,
                tool_name=gateway_result.tool_name,
                provider=gateway_result.provider,
                status="failed",
                response_json=response_json,
                error_json={
                    "code": "malformed_search_response",
                    "message": "search_poi response must include a results list of objects.",
                },
                tool_event_id=gateway_result.tool_event_id,
            )

        for item_index, item in enumerate(results):
            candidate = self._candidate_from_payload(
                item,
                call=call,
                provider=call.provider,
                source_call_index=source_call_index,
                item_index=item_index,
                tool_event_id=gateway_result.tool_event_id,
            )
            self._append_candidate(collection, candidate)
        return None

    def _candidate_from_payload(
        self,
        payload: dict[str, Any],
        *,
        call: PlannedToolCall,
        provider: str,
        source_call_index: int,
        item_index: int,
        tool_event_id: UUID | None,
    ) -> Candidate:
        candidate_id = (
            self._text_or_none(payload.get("poi_id"))
            or self._text_or_none(payload.get("id"))
            or f"{provider}:{source_call_index}:{item_index}"
        )
        category = self._text_or_none(payload.get("category")) or "unknown"
        if provider == "amap":
            hinted_category = self._text_or_none(call.payload.get("canonical_category"))
            if hinted_category in {"activity", "dining"}:
                category = hinted_category
        tags = payload.get("tags")
        return Candidate(
            candidate_id=candidate_id,
            name=self._text_or_none(payload.get("name")) or candidate_id,
            category=category,
            provider=provider,
            source=self._text_or_none(payload.get("source")),
            address=self._text_or_none(payload.get("address")),
            location=self._location_or_none(payload.get("location")),
            tags=tags if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags) else [],
            raw_payload=payload,
            source_call_index=source_call_index,
            tool_event_id=tool_event_id,
        )

    def _append_candidate(self, collection: CandidateCollectionResult, candidate: Candidate) -> None:
        category = candidate.category.casefold()
        if category == "activity":
            collection.activity_candidates.append(candidate)
        elif category == "dining":
            collection.dining_candidates.append(candidate)
        else:
            collection.other_candidates.append(candidate)

    def _capture_weather(
        self,
        collection: CandidateCollectionResult,
        response_json: dict[str, Any] | None,
    ) -> None:
        if not isinstance(response_json, dict):
            return
        weather = response_json.get("weather")
        if isinstance(weather, dict):
            collection.weather = weather

    @staticmethod
    def _execution_result(
        source_call_index: int,
        gateway_result: ToolGatewayResult,
    ) -> InitialToolExecutionResult:
        return InitialToolExecutionResult(
            source_call_index=source_call_index,
            tool_name=gateway_result.tool_name,
            provider=gateway_result.provider,
            status=gateway_result.status,
            response_json=gateway_result.response_json,
            error_json=gateway_result.error_json,
            tool_event_id=gateway_result.tool_event_id,
        )

    @staticmethod
    def _text_or_none(value: Any) -> str | None:
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _location_or_none(value: Any) -> dict[str, Any] | str | None:
        if isinstance(value, dict) or isinstance(value, str):
            return value
        return None
