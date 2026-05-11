# Spec: 005 Tool Gateway Core

## 1. Goal

Establish the core Tool Gateway layer for WeekendPilot so all future tool calls use one deterministic interface for provider dispatch, read/write permission control, Redis runtime controls, PostgreSQL tool-event logging, and Action Ledger integration.

After this task is complete, later Mock World, real map providers, LangGraph nodes, and deterministic execution workflow should call the gateway instead of calling raw tools directly.

## 2. Project Context

This task implements the Tool Gateway foundation described in `docs/PROJECT_BLUEPRINT.md`.

Previous tasks created:

- FastAPI scaffold and configuration.
- PostgreSQL schema and repositories for runs, tool events, and action ledger rows.
- Redis runtime services for cache, locks, rate limits, and progress streams.

Task 005 connects those foundations into the first gateway boundary. It is still infrastructure only. It must not implement local-life business tools, Mock World data, agents, LangGraph workflow, or execution workflow.

## 3. Requirements

- Add a `backend.app.tool_gateway` package.
- Define typed gateway request/result models for tool calls.
- Define a provider protocol so future mock and real providers can be registered behind the same interface.
- Define a registry for tool definitions and providers.
- Classify tools as `read` or `write`.
- Include the canonical MVP tool names:
  - read tools:
    - `search_poi`
    - `get_poi_detail`
    - `check_route`
    - `check_opening_hours`
    - `check_weather`
    - `check_queue`
    - `check_table_availability`
    - `check_ticket_availability`
  - write tools:
    - `join_queue`
    - `reserve_restaurant`
    - `book_ticket`
    - `order_addon`
    - `send_message`
- Route all provider calls through `ToolGateway.invoke(...)`.
- Block write tools unless `user_confirmed=True`.
- Require write tools to include `target_id` and `idempotency_key`.
- Check `action_ledger` for existing write actions before invoking a write provider.
- Create and update `action_ledger` rows for confirmed write tools.
- Create `tool_events` rows for successful, failed, blocked, rate-limited, cached, and idempotent-replay gateway calls.
- Use `JsonRedisCache` for successful cacheable read tool responses.
- Use `FixedWindowRateLimiter` for tools with configured rate limits.
- Measure and store gateway latency in milliseconds where available.
- Keep LangSmith integration out of this task, but keep `langsmith_trace_id` pass-through fields available.
- Add unit tests for registry, permission, cache-key determinism, and provider failure handling.
- Add integration tests using real PostgreSQL and real Redis with a fake in-test provider.
- Update README with Tool Gateway test prerequisites and commands.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement Mock World provider.
- Do not implement real external API providers.
- Do not implement Tool Gateway HTTP endpoints.
- Do not implement LangGraph nodes, agents, or business workflow.
- Do not implement deterministic Execution Workflow.
- Do not implement Final Review Gate.
- Do not add or modify PostgreSQL migrations.
- Do not change the Redis runtime primitives from Task 004 except for narrowly necessary exports.
- Do not implement LangSmith tracing.
- Do not create benchmark/world/failure tables or fixtures.
- Do not add repository methods unless the existing Task 003 repositories are insufficient for the gateway contracts.

## 5. Interfaces and Contracts

### Inputs

- `ToolGatewayRequest`
- registered `ToolDefinition`
- registered provider implementing `ToolProvider`
- SQLAlchemy `Session`
- Redis-backed cache and rate limiter services
- existing PostgreSQL `agent_runs`, `tool_events`, and `action_ledger` tables

### Outputs

- `ToolGatewayResult`
- `tool_events` PostgreSQL row for each gateway attempt
- `action_ledger` PostgreSQL row for confirmed write tools
- Redis cache entries for successful cacheable read tools
- Redis rate-limit counters for configured tools

### Public Modules

Expected public package shape:

```text
backend.app.tool_gateway.__init__
backend.app.tool_gateway.models
backend.app.tool_gateway.errors
backend.app.tool_gateway.registry
backend.app.tool_gateway.providers
backend.app.tool_gateway.gateway
backend.app.tool_gateway.cache_keys
```

### ToolGatewayRequest

Required fields:

```text
run_id: UUID
tool_name: str
payload: dict[str, Any]
provider: str
user_confirmed: bool = False
target_id: str | None = None
idempotency_key: str | None = None
langsmith_trace_id: str | None = None
```

### ToolGatewayResult

Required fields:

```text
tool_name: str
tool_type: Literal["read", "write"]
provider: str
status: Literal[
    "succeeded",
    "failed",
    "blocked",
    "rate_limited",
    "cached",
    "idempotent_replay",
]
response_json: dict[str, Any] | None
error_json: dict[str, Any] | None
cache_hit: bool
latency_ms: int | None
tool_event_id: UUID | None
action_id: UUID | None
idempotency_key: str | None
```

### ToolDefinition

Required fields:

```text
name: str
tool_type: Literal["read", "write"]
default_provider: str
cache_ttl_seconds: int | None = None
rate_limit: ToolRateLimit | None = None
```

`cache_ttl_seconds` only applies to read tools. Write tools must never be cached.

### ToolProvider

Provider protocol:

```text
name: str
invoke(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]
```

Providers may raise exceptions. The gateway must convert provider exceptions into failed `ToolGatewayResult` objects and durable `tool_events` rows.

### Read Tool Contract

For read tools:

1. Resolve tool definition and provider.
2. Apply rate limit when configured.
3. Check Redis cache when `cache_ttl_seconds` is set.
4. Invoke provider on cache miss.
5. Store successful provider response in cache when cacheable.
6. Write `tool_events`.
7. Return `ToolGatewayResult`.

### Write Tool Contract

For write tools:

1. Resolve tool definition and provider.
2. If `user_confirmed` is false, do not invoke provider and do not create `action_ledger`.
3. Require `target_id` and `idempotency_key`.
4. Check existing `action_ledger` by `idempotency_key`.
5. If an existing ledger row exists, do not invoke provider again. Return `idempotent_replay` and write a `tool_events` row.
6. If no ledger row exists, create `action_ledger` with status `pending`.
7. Invoke provider.
8. Update ledger to `succeeded` or `failed`.
9. Write `tool_events`.
10. Return `ToolGatewayResult`.

### Cache Key Contract

Read cache keys must be deterministic and must not include raw secrets. The same tool name, provider, and JSON payload must produce the same key independent of dictionary insertion order.

## 6. Observability

This task establishes local observability through PostgreSQL:

- Every gateway attempt writes a `tool_events` row.
- `tool_events.request_json` should include normalized request metadata and payload.
- `tool_events.response_json` stores successful provider response or replayed cached response.
- `tool_events.error_json` stores structured error details for blocked, failed, and rate-limited calls.
- `tool_events.cache_hit` is true only for Redis cache hits.
- `tool_events.latency_ms` records provider/gateway execution latency when measurable.
- Confirmed write tools also update `action_ledger`.

LangSmith runtime spans are out of scope. `langsmith_trace_id` should pass through to `tool_events` if supplied.

## 7. Failure Handling

- Unknown tool name returns a failed result and must not call a provider.
- Unknown provider returns a failed result and must not call a provider.
- Read tool provider exception returns failed result and writes `tool_events`.
- Write tool provider exception returns failed result, writes `tool_events`, and updates the pending ledger row to `failed`.
- Write tool without confirmation returns blocked result, writes `tool_events`, and creates no ledger row.
- Write tool missing `target_id` or `idempotency_key` returns failed result and creates no ledger row.
- Rate-limit denial returns rate-limited result, writes `tool_events`, and does not call the provider.
- Cache miss should call the provider.
- Cache hit should not call the provider.
- Duplicate write idempotency key should not call the provider again.
- Database errors may propagate after rollback by the caller; this task does not implement transaction management middleware.
- Redis service errors may propagate unless the implementation can safely degrade without bypassing configured rate limits.

## 8. Acceptance Criteria

- [ ] `backend.app.tool_gateway` package exists.
- [ ] Gateway request/result models are typed and importable.
- [ ] Provider protocol and registry are implemented.
- [ ] Canonical MVP tool definitions exist with read/write classification.
- [ ] Read tools support cacheable responses through `JsonRedisCache`.
- [ ] Read tools support configured fixed-window rate limits.
- [ ] Write tools are blocked before user confirmation.
- [ ] Confirmed write tools require `target_id` and `idempotency_key`.
- [ ] Confirmed write tools create/update `action_ledger`.
- [ ] Duplicate write calls with the same idempotency key do not invoke provider again.
- [ ] Gateway writes `tool_events` for success, failure, blocked, rate-limited, cached, and idempotent replay.
- [ ] Tests use a fake provider only inside tests; no Mock World provider is implemented.
- [ ] `python -m pytest` passes with PostgreSQL and Redis running.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task5` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
git switch task4
git switch -c task5
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

If PostgreSQL or Redis cannot start, stop and report the blocker. Do not replace real integration coverage with pure mocks.

## 10. Expected Commit

```text
feat: add tool gateway core
```

## 11. Notes for the Implementer

If Task 004 Redis runtime files or Task 003 repository files are missing, stop and report the branch/base mismatch.

Do not add business tool behavior in this task. Test providers may return simple deterministic payloads, but production code should only provide gateway infrastructure.
