# Plan: 006 AMAP Read Provider

## 1. Spec Reference

Spec file:

```text
docs/specs/006-amap-read-provider.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from Task 005 Tool Gateway Core.
- Work happens on a dedicated `task6` branch.
- Current Task 005 commit is `36fcec8 feat: add tool gateway core`.
- `backend/app/core/config.py` already defines `amap_maps_api_key: SecretStr | None`.
- `backend/app/tool_gateway/providers.py` defines the provider protocol.
- `backend/app/tool_gateway/registry.py` exposes `build_default_registry(default_provider=...)`.
- `backend/app/tool_gateway/gateway.py` owns tool event logging, Redis cache, rate limiting, and write safety.
- No `backend/app/providers` package exists yet.
- `httpx` currently exists only under dev dependencies and must be moved or duplicated into runtime dependencies for provider code.

## 3. Files to Add

- `backend/app/providers/__init__.py` - provider package marker.
- `backend/app/providers/amap/__init__.py` - AMAP provider public exports.
- `backend/app/providers/amap/errors.py` - AMAP provider exceptions.
- `backend/app/providers/amap/client.py` - synchronous AMAP Web Service HTTP client wrapper.
- `backend/app/providers/amap/mapper.py` - AMAP raw response to WeekendPilot JSON mappers.
- `backend/app/providers/amap/provider.py` - `AMapProvider` implementation.
- `backend/app/providers/amap/registry.py` - `build_amap_registry()` helper.
- `tests/test_amap_mapper.py` - mapper unit tests.
- `tests/test_amap_provider.py` - provider unit tests with fake client.
- `tests/integration/test_amap_gateway.py` - Tool Gateway integration tests with fake AMAP responses.
- `tests/integration/test_amap_live.py` - optional live smoke tests skipped by default.

## 4. Files to Modify

- `pyproject.toml` - move/add `httpx>=0.27,<1.0` to runtime dependencies.
- `README.md` - document AMAP key setup and optional live smoke test command.
- `docs/specs/006-amap-read-provider.md` - save Task 006 spec.
- `docs/plans/006-amap-read-provider-plan.md` - save Task 006 plan.

No database migration is expected.

## 5. Implementation Steps

1. Confirm branch and baseline:

```bash
git status --short --branch
rg --files backend/app/tool_gateway backend/app/core backend/app/runtime backend/app/repositories docs/specs docs/plans tests
```

Expected:

- Branch is `task6`.
- Task 005 Tool Gateway files exist.
- `backend/app/providers` does not exist yet.

2. Update `pyproject.toml`.

Move or add this dependency to `[project].dependencies`:

```toml
"httpx>=0.27,<1.0",
```

If it remains in `[project.optional-dependencies].dev` too, remove the duplicate to keep dependency ownership clear.

3. Create `backend/app/providers/__init__.py`.

Keep it minimal:

```python
"""External and mock provider integrations."""
```

4. Create `backend/app/providers/amap/errors.py`.

Implement:

```python
class AMapProviderError(RuntimeError):
    pass


class AMapConfigurationError(AMapProviderError):
    pass


class AMapUnsupportedToolError(AMapProviderError):
    pass
```

Do not include API keys in exception messages.

5. Create `backend/app/providers/amap/client.py`.

Implement a synchronous client wrapper:

```python
class AMapClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://restapi.amap.com",
        timeout_seconds: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        ...

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        ...
```

Requirements:

- Raise `AMapConfigurationError` if `api_key` is empty.
- Merge `key` into params internally.
- Use `httpx.Client(base_url=base_url, timeout=timeout_seconds)` when no client is injected.
- Catch `httpx.TimeoutException` and `httpx.HTTPError`, raising `AMapProviderError` without URL/key leakage.
- Call `response.raise_for_status()`.
- Parse JSON response.
- If AMAP response has `status` and it is not `"1"`, raise `AMapProviderError` with `infocode` and `info`, but not request URL or key.

6. Create `backend/app/providers/amap/mapper.py`.

Implement pure mapper functions:

```python
def map_poi_search(response: dict[str, Any]) -> dict[str, Any]: ...
def map_poi_detail(response: dict[str, Any]) -> dict[str, Any]: ...
def map_route(response: dict[str, Any], origin: str, destination: str, mode: str) -> dict[str, Any]: ...
def map_weather(response: dict[str, Any]) -> dict[str, Any]: ...
```

Mapping requirements:

- Use stable internal keys from the spec.
- Convert route `distance` and `duration` to integers when present.
- Handle empty successful POI search as `{"results": []}`.
- Raise `AMapProviderError` for malformed successful detail/route/weather responses.
- Include `"source": "amap"` in normalized objects.

7. Create `backend/app/providers/amap/provider.py`.

Implement:

```python
class AMapProvider:
    name = "amap"

    def __init__(self, client: AMapClient) -> None:
        self._client = client

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
```

Dispatch explicitly:

- `search_poi` -> `/v3/place/text`
- `get_poi_detail` -> `/v3/place/detail`
- `check_route` with `mode=walking` -> `/v3/direction/walking`
- `check_route` with `mode=driving` -> `/v3/direction/driving`
- `check_weather` -> `/v3/weather/weatherInfo`

Do not use dynamic method lookup based on raw tool input.

8. Implement payload validation in `provider.py`.

Rules:

- `search_poi` requires non-empty `keywords`.
- `get_poi_detail` requires non-empty `poi_id`.
- `check_route` requires non-empty `origin` and `destination`.
- `check_route.mode` defaults to `walking`; only `walking` and `driving` are allowed.
- `check_weather` requires non-empty `city`.
- `check_weather.extensions` defaults to `base`.
- Unsupported tools raise `AMapUnsupportedToolError`.

9. Create `backend/app/providers/amap/registry.py`.

Implement:

```python
from backend.app.core.config import get_settings
from backend.app.tool_gateway.registry import ToolRegistry, build_default_registry


def build_amap_registry() -> ToolRegistry:
    settings = get_settings()
    secret = settings.amap_maps_api_key
    if secret is None:
        raise AMapConfigurationError("AMAP API key is not configured.")
    registry = build_default_registry(default_provider="amap")
    registry.register_provider(AMapProvider(AMapClient(secret.get_secret_value())))
    return registry
```

Do not print or return the secret value.

10. Create `backend/app/providers/amap/__init__.py`.

Export:

```python
AMapClient
AMapConfigurationError
AMapProvider
AMapProviderError
AMapUnsupportedToolError
build_amap_registry
```

11. Write mapper tests in `tests/test_amap_mapper.py`.

Cover:

- POI search maps two POIs.
- POI search maps empty successful response to empty results.
- POI detail maps first returned POI.
- walking/driving route maps distance and duration.
- weather maps live weather fields.
- malformed detail/route/weather raises `AMapProviderError`.

12. Write provider tests in `tests/test_amap_provider.py`.

Use a fake client:

```python
class FakeAMapClient:
    def __init__(self, responses: dict[tuple[str, str], dict]) -> None:
        self.calls = []

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        ...
```

Cover:

- `search_poi` passes expected params.
- `get_poi_detail` passes `id`.
- `check_route` selects walking path by default.
- `check_route` selects driving path when requested.
- `check_weather` defaults `extensions` to `base`.
- missing required fields raise `AMapProviderError`.
- invalid route mode raises `AMapProviderError`.
- unsupported canonical tool such as `check_queue` raises `AMapUnsupportedToolError`.

13. Write client tests in `tests/test_amap_provider.py` or a separate focused section.

Use `httpx.MockTransport` or a fake `httpx.Client` equivalent if simpler.

Cover:

- missing key raises `AMapConfigurationError`.
- `status != "1"` raises `AMapProviderError`.
- raised error does not contain the API key.

14. Write integration tests in `tests/integration/test_amap_gateway.py`.

Use real PostgreSQL and Redis like Task 005 integration tests.

Test setup:

- Use `SessionLocal`.
- Use `UserRepository`, `AgentRunRepository`, `ToolEventRepository`.
- Use `get_redis_client()`, `RedisKeyBuilder(prefix=f"weekendpilot:test:amap:{uuid4()}")`, `JsonRedisCache`, `FixedWindowRateLimiter`.
- Build a `ToolRegistry` using `build_default_registry(default_provider="amap")`.
- Register an `AMapProvider` using fake client responses.
- Do not call the real AMAP network.

Integration cases:

- `test_search_poi_through_gateway_writes_tool_event`
- `test_check_weather_through_gateway_can_use_redis_cache`
- `test_amap_provider_error_becomes_failed_gateway_result`

15. Write optional live smoke tests in `tests/integration/test_amap_live.py`.

Rules:

- Use `pytest.mark.skipif` unless `RUN_AMAP_LIVE_TESTS == "1"`.
- Skip if `get_settings().amap_maps_api_key is None`.
- Do not assert exact live counts or names.
- Check only response shape for:
  - `search_poi`
  - `check_route`
  - `check_weather`

16. Update README.

Add an AMAP section:

```bash
# .env only; never commit this file
AMAP_MAPS_API_KEY=your-local-key

# Default tests do not call AMAP live APIs
python -m pytest

# Optional live smoke test
$env:RUN_AMAP_LIVE_TESTS="1"
python -m pytest tests/integration/test_amap_live.py -v
```

Mention that AMAP currently supports only read tools and that Mock World remains a follow-up for deterministic benchmark/write behavior.

17. Run focused tests:

```bash
python -m pytest tests/test_amap_mapper.py tests/test_amap_provider.py -v
```

18. Run gateway integration tests:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_amap_gateway.py -v
```

19. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

20. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - AMAP response mappers normalize POI search, POI detail, route, and weather.
  - Provider dispatches supported tools to the expected AMAP paths.
  - Provider validates required payload fields.
  - Provider rejects unsupported tools safely.
  - Client handles missing key and AMAP error status without leaking secrets.
- Integration tests:
  - Tool Gateway plus AMAP provider with fake HTTP responses writes `tool_events`.
  - Cacheable `check_weather` can hit Redis through Tool Gateway.
  - Provider errors become failed Tool Gateway results and failed `tool_events`.
- Optional live smoke tests:
  - Real AMAP `search_poi`, `check_route`, and `check_weather` shape checks.
  - Skipped by default.

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

Optional live command:

```bash
$env:RUN_AMAP_LIVE_TESTS="1"
python -m pytest tests/integration/test_amap_live.py -v
```

The optional command may be reported separately and must not be required for commit.

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add amap read provider
```

Expected commands:

```bash
git status --short
git add pyproject.toml README.md backend/app/providers tests/test_amap_mapper.py tests/test_amap_provider.py tests/integration/test_amap_gateway.py tests/integration/test_amap_live.py docs/specs/006-amap-read-provider.md docs/plans/006-amap-read-provider-plan.md
git status --short
git commit -m "feat: add amap read provider"
git push -u origin task6
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement Mock World Provider.
- Do not implement real write providers.
- Do not implement queue/table/ticket availability.
- Do not implement `check_opening_hours` unless explicitly respecified.
- Do not implement FastAPI endpoints.
- Do not implement LangGraph, agents, planner services, execution workflow, or Final Review Gate.
- Do not add benchmark cases, graders, failure injection, or replay harness.
- Do not add database migrations.
- Do not make live AMAP tests mandatory.
- Do not commit `.env`, secrets, caches, virtual environments, generated logs, or Docker volumes.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task6`.
- [ ] Spec and plan exist in `docs/specs` and `docs/plans`.
- [ ] Provider name is exactly `amap`.
- [ ] API key is read through settings and never exposed.
- [ ] `httpx` is a runtime dependency.
- [ ] Only `search_poi`, `get_poi_detail`, `check_route`, and `check_weather` are supported.
- [ ] Unsupported tools fail safely.
- [ ] AMAP responses are normalized.
- [ ] Default tests do not call live AMAP APIs.
- [ ] Gateway integration tests use real PostgreSQL and Redis with fake AMAP responses.
- [ ] Optional live test is skipped by default.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] No secrets are committed.
- [ ] Commit message is `feat: add amap read provider`.
- [ ] Push to `origin/task6` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Focused AMAP unit test result.
- AMAP gateway integration test result.
- Full pytest result.
- Docker Compose result.
- Optional live smoke test result, if run.
- Commit hash.
- Push branch.
- Any deviations from this spec or plan.
