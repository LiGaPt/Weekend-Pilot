from __future__ import annotations

import time
from typing import Any

from backend.app.repositories import ActionLedgerRepository, ToolEventRepository
from backend.app.runtime import FixedWindowRateLimiter, JsonRedisCache
from backend.app.tool_gateway.cache_keys import build_tool_cache_key
from backend.app.tool_gateway.errors import error_json
from backend.app.tool_gateway.failure_injection import ToolFailureInjector
from backend.app.tool_gateway.models import ToolDefinition, ToolGatewayRequest, ToolGatewayResult, ToolType
from backend.app.tool_gateway.registry import ToolRegistry


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        tool_events: ToolEventRepository,
        action_ledger: ActionLedgerRepository,
        cache: JsonRedisCache,
        rate_limiter: FixedWindowRateLimiter,
        failure_injector: ToolFailureInjector | None = None,
    ) -> None:
        self._registry = registry
        self._tool_events = tool_events
        self._action_ledger = action_ledger
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._failure_injector = failure_injector

    def invoke(self, request: ToolGatewayRequest) -> ToolGatewayResult:
        started_at = time.perf_counter()
        definition = self._registry.get_tool(request.tool_name)
        if definition is None:
            return self._failed_without_definition(request, started_at)

        provider_name = request.provider or definition.default_provider
        provider = self._registry.get_provider(provider_name)
        if provider is None:
            error = error_json(
                "unknown_provider",
                f"Provider {provider_name!r} is not registered.",
            )
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="failed",
                response_json=None,
                error_json=error,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        if definition.tool_type == "read":
            return self._invoke_read(request, definition, provider_name, provider, started_at)

        return self._invoke_write(request, definition, provider_name, provider, started_at)

    def _invoke_read(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
        provider: Any,
        started_at: float,
    ) -> ToolGatewayResult:
        injected = (
            self._failure_injector.maybe_inject(request, definition, provider_name)
            if self._failure_injector is not None
            else None
        )
        if injected is not None:
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status=injected.status,
                response_json=injected.response_json,
                error_json=injected.error_json,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        rate_limited = self._check_rate_limit(definition, provider_name)
        if rate_limited is not None:
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="rate_limited",
                response_json=None,
                error_json=rate_limited,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        cache_key = None
        if definition.cache_ttl_seconds is not None:
            cache_key = build_tool_cache_key(definition.name, provider_name, request.payload)
            cached_value = self._cache.get_json(cache_key)
            if cached_value is not None:
                response_json = cached_value if isinstance(cached_value, dict) else {"value": cached_value}
                return self._record_result(
                    request=request,
                    definition=definition,
                    provider_name=provider_name,
                    status="cached",
                    response_json=response_json,
                    error_json=None,
                    cache_hit=True,
                    latency_ms=self._latency_ms(started_at),
                    action_id=None,
                )

        try:
            response_json = provider.invoke(definition.name, request.payload)
        except Exception as exc:
            error = error_json(
                "provider_error",
                str(exc),
                {"exception_type": type(exc).__name__},
            )
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="failed",
                response_json=None,
                error_json=error,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        if cache_key is not None and definition.cache_ttl_seconds is not None:
            self._cache.set_json(cache_key, response_json, ttl_seconds=definition.cache_ttl_seconds)

        return self._record_result(
            request=request,
            definition=definition,
            provider_name=provider_name,
            status="succeeded",
            response_json=response_json,
            error_json=None,
            cache_hit=False,
            latency_ms=self._latency_ms(started_at),
            action_id=None,
        )

    def _invoke_write(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
        provider: Any,
        started_at: float,
    ) -> ToolGatewayResult:
        if not request.user_confirmed:
            error = error_json(
                "write_not_confirmed",
                "Write tool requires user confirmation.",
            )
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="blocked",
                response_json=None,
                error_json=error,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        if not request.target_id or not request.idempotency_key:
            missing_fields = [
                field
                for field, value in {
                    "target_id": request.target_id,
                    "idempotency_key": request.idempotency_key,
                }.items()
                if not value
            ]
            error = error_json(
                "missing_write_fields",
                "Confirmed write tools require target_id and idempotency_key.",
                {"missing_fields": missing_fields},
            )
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="failed",
                response_json=None,
                error_json=error,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        existing_action = self._action_ledger.get_by_idempotency_key(request.idempotency_key)
        if existing_action is not None:
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="idempotent_replay",
                response_json=existing_action.response_json,
                error_json=existing_action.error_json,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=existing_action.action_id,
            )

        rate_limited = self._check_rate_limit(definition, provider_name)
        if rate_limited is not None:
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="rate_limited",
                response_json=None,
                error_json=rate_limited,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=None,
            )

        action = self._action_ledger.create(
            run_id=request.run_id,
            action_type=definition.name,
            target_id=request.target_id,
            idempotency_key=request.idempotency_key,
            status="pending",
            request_json=self._request_json(request, provider_name),
        )

        try:
            response_json = provider.invoke(definition.name, request.payload)
        except Exception as exc:
            error = error_json(
                "provider_error",
                str(exc),
                {"exception_type": type(exc).__name__},
            )
            self._action_ledger.update_status(
                action.action_id,
                "failed",
                error_json=error,
            )
            return self._record_result(
                request=request,
                definition=definition,
                provider_name=provider_name,
                status="failed",
                response_json=None,
                error_json=error,
                cache_hit=False,
                latency_ms=self._latency_ms(started_at),
                action_id=action.action_id,
            )

        self._action_ledger.update_status(
            action.action_id,
            "succeeded",
            response_json=response_json,
        )
        return self._record_result(
            request=request,
            definition=definition,
            provider_name=provider_name,
            status="succeeded",
            response_json=response_json,
            error_json=None,
            cache_hit=False,
            latency_ms=self._latency_ms(started_at),
            action_id=action.action_id,
        )

    def _failed_without_definition(self, request: ToolGatewayRequest, started_at: float) -> ToolGatewayResult:
        provider_name = request.provider or "unknown"
        error = error_json(
            "unknown_tool",
            f"Tool {request.tool_name!r} is not registered.",
        )
        event = self._tool_events.create(
            run_id=request.run_id,
            tool_name=request.tool_name,
            tool_type="read",
            provider=provider_name,
            request_json=self._request_json(request, provider_name),
            response_json=None,
            error_json=error,
            status="failed",
            cache_hit=False,
            latency_ms=self._latency_ms(started_at),
            langsmith_trace_id=request.langsmith_trace_id,
        )
        return ToolGatewayResult(
            tool_name=request.tool_name,
            tool_type="read",
            provider=provider_name,
            status="failed",
            response_json=None,
            error_json=error,
            cache_hit=False,
            latency_ms=event.latency_ms,
            tool_event_id=event.event_id,
            action_id=None,
            idempotency_key=request.idempotency_key,
        )

    def _record_result(
        self,
        request: ToolGatewayRequest,
        definition: ToolDefinition,
        provider_name: str,
        status: str,
        response_json: dict[str, Any] | None,
        error_json: dict[str, Any] | None,
        cache_hit: bool,
        latency_ms: int | None,
        action_id: Any,
    ) -> ToolGatewayResult:
        event = self._tool_events.create(
            run_id=request.run_id,
            tool_name=definition.name,
            tool_type=definition.tool_type,
            provider=provider_name,
            request_json=self._request_json(request, provider_name),
            response_json=response_json,
            error_json=error_json,
            status=status,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            langsmith_trace_id=request.langsmith_trace_id,
        )
        return ToolGatewayResult(
            tool_name=definition.name,
            tool_type=definition.tool_type,
            provider=provider_name,
            status=status,
            response_json=response_json,
            error_json=error_json,
            cache_hit=cache_hit,
            latency_ms=latency_ms,
            tool_event_id=event.event_id,
            action_id=action_id,
            idempotency_key=request.idempotency_key,
        )

    def _check_rate_limit(self, definition: ToolDefinition, provider_name: str) -> dict[str, Any] | None:
        if definition.rate_limit is None:
            return None

        decision = self._rate_limiter.allow(
            f"tool:{provider_name}:{definition.name}",
            limit=definition.rate_limit.limit,
            window_seconds=definition.rate_limit.window_seconds,
        )
        if decision.allowed:
            return None

        return error_json(
            "rate_limited",
            "Tool rate limit exceeded.",
            {
                "remaining": decision.remaining,
                "reset_after_seconds": decision.reset_after_seconds,
            },
        )

    @staticmethod
    def _request_json(request: ToolGatewayRequest, provider_name: str) -> dict[str, Any]:
        return {
            "tool_name": request.tool_name,
            "provider": provider_name,
            "payload": request.payload,
            "user_confirmed": request.user_confirmed,
            "target_id": request.target_id,
            "idempotency_key": request.idempotency_key,
        }

    @staticmethod
    def _latency_ms(started_at: float) -> int:
        return max(0, int((time.perf_counter() - started_at) * 1000))
