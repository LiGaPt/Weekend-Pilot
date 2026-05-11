# Plan: 005 Tool Gateway Core

## 1. Spec Reference

Spec file:

```text
docs/specs/005-tool-gateway-core.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from Task 004 Redis runtime service baseline.
- Work happens on a dedicated `task5` branch.
- `backend/app/repositories/tool_events.py` exposes `ToolEventRepository.create(...)`.
- `backend/app/repositories/action_ledger.py` exposes `ActionLedgerRepository.create(...)`, `get_by_idempotency_key(...)`, and `update_status(...)`.
- `backend/app/runtime/cache.py` exposes `JsonRedisCache`.
- `backend/app/runtime/rate_limit.py` exposes `FixedWindowRateLimiter` and `RateLimitDecision`.
- `backend/app/runtime/keys.py` exposes `RedisKeyBuilder`.
- PostgreSQL and Redis integration tests already run against Docker services.
- No Tool Gateway package exists yet.
- No production Mock World provider exists yet.

## 3. Files to Add

- `backend/app/tool_gateway/__init__.py` - public exports for gateway models, registry, provider protocol, and gateway class.
- `backend/app/tool_gateway/models.py` - Pydantic or dataclass models for requests, results, definitions, and rate-limit config.
- `backend/app/tool_gateway/errors.py` - gateway-specific exception/error helpers.
- `backend/app/tool_gateway/providers.py` - `ToolProvider` protocol.
- `backend/app/tool_gateway/registry.py` - provider and tool definition registry plus canonical MVP tool definitions.
- `backend/app/tool_gateway/cache_keys.py` - deterministic read cache key builder.
- `backend/app/tool_gateway/gateway.py` - core `ToolGateway.invoke(...)` implementation.
- `tests/test_tool_gateway_registry.py` - unit tests for registry and canonical tool definitions.
- `tests/test_tool_gateway_cache_keys.py` - unit tests for deterministic cache key generation.
- `tests/integration/test_tool_gateway.py` - real PostgreSQL/Redis integration tests using fake in-test providers.

## 4. Files to Modify

- `README.md` - add Tool Gateway verification prerequisites and focused test commands.
- `backend/app/runtime/__init__.py` - modify only if Task 004 forgot to export cache or rate-limit classes needed by gateway.
- `backend/app/repositories/__init__.py` - modify only if Task 003 forgot to export repositories needed by gateway.

No dependency changes are expected.

## 5. Implementation Steps

1. Confirm branch and baseline:

```bash
git status --short --branch
rg --files backend/app docs/specs docs/plans tests
```

Expected:

- Branch is `task5`.
- Task 003 repository files exist.
- Task 004 runtime files exist.
- `backend/app/tool_gateway` does not exist yet.

2. Create `backend/app/tool_gateway/models.py`.

Use either Pydantic models or frozen dataclasses. Prefer Pydantic because the project already depends on it through FastAPI.

Required model constants:

```python
from typing import Any, Literal
from uuid import UUID

ToolType = Literal["read", "write"]
GatewayStatus = Literal[
    "succeeded",
    "failed",
    "blocked",
    "rate_limited",
    "cached",
    "idempotent_replay",
]
```

Required models:

```python
class ToolRateLimit(BaseModel):
    limit: int
    window_seconds: int


class ToolDefinition(BaseModel):
    name: str
    tool_type: ToolType
    default_provider: str
    cache_ttl_seconds: int | None = None
    rate_limit: ToolRateLimit | None = None


class ToolGatewayRequest(BaseModel):
    run_id: UUID
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    user_confirmed: bool = False
    target_id: str | None = None
    idempotency_key: str | None = None
    langsmith_trace_id: str | None = None


class ToolGatewayResult(BaseModel):
    tool_name: str
    tool_type: ToolType
    provider: str
    status: GatewayStatus
    response_json: dict[str, Any] | None = None
    error_json: dict[str, Any] | None = None
    cache_hit: bool = False
    latency_ms: int | None = None
    tool_event_id: UUID | None = None
    action_id: UUID | None = None
    idempotency_key: str | None = None
```

Validation requirements:

- `ToolRateLimit.limit` and `window_seconds` must be positive.
- `ToolDefinition.cache_ttl_seconds` must be positive when provided.
- Do not allow cache TTL on write tools.

3. Create `backend/app/tool_gateway/providers.py`.

Define:

```python
from typing import Any, Protocol


class ToolProvider(Protocol):
    name: str

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
```

Keep this synchronous to match existing SQLAlchemy and Redis services.

4. Create `backend/app/tool_gateway/errors.py`.

Add lightweight helpers:

```python
class ToolGatewayError(Exception):
    code: str


def error_json(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    ...
```

Use structured fields:

```json
{
  "code": "write_not_confirmed",
  "message": "Write tool requires user confirmation.",
  "details": {}
}
```

5. Create `backend/app/tool_gateway/registry.py`.

Implement:

```python
class ToolRegistry:
    def register_tool(self, definition: ToolDefinition) -> None: ...
    def register_provider(self, provider: ToolProvider) -> None: ...
    def get_tool(self, name: str) -> ToolDefinition | None: ...
    def get_provider(self, name: str) -> ToolProvider | None: ...
```

Also provide:

```python
READ_TOOLS = (...)
WRITE_TOOLS = (...)

def build_default_registry(default_provider: str = "mock_world") -> ToolRegistry:
    ...
```

Canonical defaults:

- Read tools default to provider `mock_world`.
- Write tools default to provider `mock_world`.
- At least `check_weather`, `check_queue`, `check_table_availability`, and `check_ticket_availability` should be cacheable with a short TTL such as `60`.
- At least one read tool and one write tool should have a fixed-window rate limit so rate-limit behavior is testable without adding business logic.

6. Create `backend/app/tool_gateway/cache_keys.py`.

Implement:

```python
def build_tool_cache_key(tool_name: str, provider: str, payload: dict[str, Any]) -> str:
    ...
```

Requirements:

- Use `json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)`.
- Hash the normalized payload with SHA-256.
- Return a concise key such as `tool:{provider}:{tool_name}:{digest}`.
- Same payload with different dictionary insertion order must produce the same key.

7. Write unit tests before gateway implementation.

In `tests/test_tool_gateway_registry.py`:

- default registry contains all canonical read/write tools.
- read and write classifications match the spec.
- duplicate tool registration is rejected or replaces deterministically. Prefer rejecting duplicates with a clear error.
- unknown tools return `None`.

In `tests/test_tool_gateway_cache_keys.py`:

- same payload in different dict order has same cache key.
- different payload changes cache key.
- key contains provider and tool name but not raw payload text.

Run:

```bash
python -m pytest tests/test_tool_gateway_registry.py tests/test_tool_gateway_cache_keys.py -v
```

Expected before implementation: FAIL because modules do not exist.

8. Implement registry, models, errors, provider protocol, and cache key helper until unit tests pass.

Run:

```bash
python -m pytest tests/test_tool_gateway_registry.py tests/test_tool_gateway_cache_keys.py -v
```

Expected: PASS.

9. Create `backend/app/tool_gateway/gateway.py`.

Constructor should accept dependencies explicitly:

```python
class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        tool_events: ToolEventRepository,
        action_ledger: ActionLedgerRepository,
        cache: JsonRedisCache,
        rate_limiter: FixedWindowRateLimiter,
    ) -> None:
        ...
```

Main method:

```python
def invoke(self, request: ToolGatewayRequest) -> ToolGatewayResult:
    ...
```

Do not create database sessions inside the gateway. The caller owns session lifecycle and commit/rollback.

10. Implement read tool flow in `ToolGateway.invoke(...)`.

Required behavior:

- Resolve definition by `request.tool_name`.
- Resolve provider by `request.provider or definition.default_provider`.
- Apply rate limit when configured.
- Check cache for read tools when `definition.cache_ttl_seconds` is set.
- On cache hit:
  - do not call provider
  - write `tool_events` with status `cached`
  - return `cache_hit=True`
- On cache miss:
  - invoke provider
  - cache successful response when cacheable
  - write `tool_events` with status `succeeded`
  - return successful result
- On provider exception:
  - write `tool_events` with status `failed`
  - return failed result with structured error.

11. Implement write tool permission and idempotency flow.

Required behavior:

- If `user_confirmed` is false:
  - do not create action ledger
  - do not call provider
  - write `tool_events` with status `blocked`
  - return blocked result.
- If `target_id` or `idempotency_key` is missing:
  - do not create action ledger
  - do not call provider
  - write `tool_events` with status `failed`
  - return failed result.
- If `action_ledger.get_by_idempotency_key(...)` returns an existing row:
  - do not call provider
  - write `tool_events` with status `idempotent_replay`
  - return existing ledger response/error/action id.
- Otherwise:
  - create action ledger with status `pending`
  - invoke provider
  - update ledger to `succeeded` with response on success
  - update ledger to `failed` with error on provider exception
  - write matching `tool_events`
  - return result.

12. Keep event payloads structured and minimal.

For `ToolEventRepository.create(...)`, use:

```python
request_json = {
    "tool_name": request.tool_name,
    "provider": provider_name,
    "payload": request.payload,
    "user_confirmed": request.user_confirmed,
    "target_id": request.target_id,
    "idempotency_key": request.idempotency_key,
}
```

Do not include secrets or raw environment variables.

13. Export public objects from `backend/app/tool_gateway/__init__.py`.

Include:

```python
ToolGateway
ToolGatewayRequest
ToolGatewayResult
ToolDefinition
ToolRateLimit
ToolRegistry
ToolProvider
build_default_registry
build_tool_cache_key
```

14. Write integration tests in `tests/integration/test_tool_gateway.py`.

Use real PostgreSQL and Redis.

Test setup:

- Use `SessionLocal`.
- Use existing repository helpers or create local helper functions for user/run setup.
- Use `get_redis_client()`, `RedisKeyBuilder(prefix="weekendpilot:test:gateway")`, `JsonRedisCache`, and `FixedWindowRateLimiter`.
- Clean only keys under `weekendpilot:test:gateway:*` before and after tests.
- Use a fake provider class inside the test file with `name = "fake"` and a call counter.
- Register only tool definitions needed for each test or use default definitions with fake provider overrides.

Integration cases:

- `test_read_tool_logs_event_and_returns_provider_response`
- `test_cacheable_read_tool_uses_redis_cache_on_second_call`
- `test_rate_limited_tool_blocks_provider_call`
- `test_write_tool_is_blocked_before_confirmation`
- `test_confirmed_write_creates_and_updates_action_ledger`
- `test_duplicate_write_idempotency_key_replays_existing_action`
- `test_provider_exception_writes_failed_event_and_failed_ledger_for_write`

15. Run focused integration tests.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_tool_gateway.py -v
```

Expected: PASS.

16. Run full tests.

```bash
python -m pytest
```

Expected: PASS.

17. Update README.

Add a small Tool Gateway test section:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_tool_gateway.py -v
```

Do not describe any Mock World behavior as implemented.

18. Run final verification.

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

19. Inspect tracked files and secrets before commit.

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - default registry includes canonical MVP tools
  - read/write classification is correct
  - duplicate registration behavior is deterministic
  - cache key generation is deterministic and hashed
- Integration tests:
  - read call returns provider response and writes `tool_events`
  - cacheable read call hits Redis cache on second call
  - rate-limited call denies provider invocation
  - unconfirmed write call is blocked and creates no ledger row
  - confirmed write call creates pending ledger and updates to succeeded
  - duplicate idempotency key replays existing action without provider call
  - provider exception records failed event and failed ledger for write tools
- Smoke tests:
  - full pytest suite
  - Docker Compose config validation

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

If Docker services fail to start, stop and report the blocker. Do not replace real PostgreSQL/Redis integration coverage with mocks.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add tool gateway core
```

Expected commands:

```bash
git status --short
git add README.md backend/app/tool_gateway tests/test_tool_gateway_registry.py tests/test_tool_gateway_cache_keys.py tests/integration/test_tool_gateway.py docs/specs/005-tool-gateway-core.md docs/plans/005-tool-gateway-core-plan.md
git status --short
git commit -m "feat: add tool gateway core"
git push -u origin task5
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement Mock World provider.
- Do not implement real map/local-life providers.
- Do not implement API endpoints.
- Do not implement LangGraph workflow or agents.
- Do not implement Execution Workflow.
- Do not implement Final Review Gate.
- Do not modify PostgreSQL schema or migrations.
- Do not add benchmark/world/failure fixtures.
- Do not change Redis runtime behavior except for necessary exports.
- Do not add new dependencies unless a blocker is reported and approved.
- Do not commit `.env`, secrets, caches, virtual environments, generated logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task5`.
- [ ] Spec and plan exist in `docs/specs` and `docs/plans`.
- [ ] Gateway package is infrastructure-only and contains no business provider behavior.
- [ ] Canonical tool names and read/write classifications match the blueprint.
- [ ] Read cache uses deterministic hashed keys.
- [ ] Rate limit denial avoids provider invocation.
- [ ] Write tools are blocked before confirmation.
- [ ] Blocked writes do not create `action_ledger` rows.
- [ ] Confirmed writes create/update `action_ledger`.
- [ ] Idempotent replay avoids duplicate provider calls.
- [ ] Tool events are recorded for success, failure, blocked, rate-limited, cached, and replay paths.
- [ ] Tests use fake providers only inside tests.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] No secrets are committed.
- [ ] Commit message is `feat: add tool gateway core`.
- [ ] Push to `origin/task5` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Focused unit test results.
- Tool Gateway integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviations from this spec or plan.
