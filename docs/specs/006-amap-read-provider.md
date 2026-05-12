# Spec: 006 AMAP Read Provider

## 1. Goal

Add a real AMAP read provider behind the Tool Gateway so WeekendPilot can use the `AMAP_MAPS_API_KEY` from local `.env` for POI search, POI detail, route checking, and weather lookup.

After this task is complete, the system should be able to call supported AMAP read tools through the existing Tool Gateway while keeping default tests deterministic and safe to run without a real API key or live network access.

## 2. Project Context

Task 005 established the Tool Gateway core: provider registration, read/write classification, Redis cache/rate limiting, PostgreSQL `tool_events`, and Action Ledger integration.

Task 006 adds the first real external read provider. This is useful for demos and local exploration, but it does not replace the later Mock World Provider because LocalLife-Bench still needs deterministic fixtures, availability, write-tool simulation, failure injection, and replayability.

The main product must still remain runnable without LangSmith, real map keys, or real local-life APIs. AMAP live calls are optional and must never be required by the default test suite.

## 3. Requirements

- Add an AMAP provider package under `backend/app/providers/amap`.
- Provider name must be exactly `amap`.
- Use `backend.app.core.config.Settings.amap_maps_api_key`.
- Read the API key from `.env` through existing settings; do not read `.env` manually.
- Add `httpx` as a runtime dependency because provider code needs it outside dev tests.
- Implement synchronous HTTP client code to match existing synchronous SQLAlchemy, Redis, and Tool Gateway services.
- Support these Tool Gateway read tools:
  - `search_poi`
  - `get_poi_detail`
  - `check_route`
  - `check_weather`
- Do not support AMAP for:
  - `check_opening_hours`
  - `check_queue`
  - `check_table_availability`
  - `check_ticket_availability`
  - all write tools
- Unsupported tools must raise a provider error that Tool Gateway records as a failed `tool_events` row.
- Missing API key must produce a safe configuration error without exposing secrets.
- HTTP timeout must have a bounded default such as 5 seconds.
- AMAP responses with `status != "1"` must become structured provider errors.
- Normalize AMAP responses into WeekendPilot JSON shapes instead of exposing raw full AMAP payloads.
- Do not write the AMAP API key into logs, exceptions, `tool_events`, README, test fixtures, snapshots, or committed files.
- Add unit tests with fake AMAP clients/responses; no default unit test may call the real network.
- Add Tool Gateway integration tests using fake AMAP HTTP responses with real PostgreSQL and Redis.
- Add an optional live smoke test skipped unless `RUN_AMAP_LIVE_TESTS=1` and `AMAP_MAPS_API_KEY` are both present.
- Update README with AMAP setup and optional live smoke test commands.
- Keep `.env`, API keys, tokens, and secrets out of git.

## 4. Non-goals

- Do not implement Mock World Provider.
- Do not implement real write tools.
- Do not implement queue/table/ticket availability through AMAP.
- Do not implement `check_opening_hours` through AMAP unless there is a stable documented endpoint and the scope is explicitly updated.
- Do not implement LangGraph, agents, planner services, execution workflow, or Final Review Gate.
- Do not implement benchmark cases, graders, failure injection, or replay harness.
- Do not add FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not make live AMAP calls part of default `python -m pytest`.
- Do not commit `.env`, API keys, tokens, secrets, caches, virtualenvs, logs, or Docker volumes.

## 5. Interfaces and Contracts

### Inputs

- `AMAP_MAPS_API_KEY`
- `ToolGatewayRequest`
- AMAP provider payloads
- Tool Gateway registry/provider calls

### Outputs

- Normalized provider response dictionaries.
- `ToolGatewayResult` when invoked through Tool Gateway.
- PostgreSQL `tool_events` rows through existing Tool Gateway behavior.
- Redis cache entries through existing Tool Gateway behavior for cacheable read tools.

### Public Modules

Expected package shape:

```text
backend.app.providers.__init__
backend.app.providers.amap.__init__
backend.app.providers.amap.client
backend.app.providers.amap.errors
backend.app.providers.amap.mapper
backend.app.providers.amap.provider
backend.app.providers.amap.registry
```

### Provider Contract

```python
class AMapProvider:
    name = "amap"

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
```

### Registry Contract

```python
def build_amap_registry() -> ToolRegistry:
    ...
```

`build_amap_registry()` should:

- call `build_default_registry(default_provider="amap")`
- register `AMapProvider`
- use `get_settings().amap_maps_api_key`

### Client Contract

The provider should use a small client wrapper around AMAP Web Service endpoints.

Required endpoint paths:

```text
/v3/place/text
/v3/place/detail
/v3/direction/walking
/v3/direction/driving
/v3/weather/weatherInfo
```

The client must inject `key` internally and must not expose the key in raised errors.

### Payload Contracts

`search_poi`:

```json
{
  "keywords": "family museum",
  "city": "Shanghai",
  "types": "140000",
  "location": "121.4737,31.2304",
  "radius": 5000,
  "page_size": 10
}
```

Required: `keywords`.

`get_poi_detail`:

```json
{
  "poi_id": "B0FF..."
}
```

Required: `poi_id`.

`check_route`:

```json
{
  "origin": "121.4737,31.2304",
  "destination": "121.4998,31.2397",
  "mode": "walking"
}
```

Required: `origin`, `destination`.

Allowed `mode`: `walking`, `driving`. Default: `walking`.

`check_weather`:

```json
{
  "city": "310000",
  "extensions": "base"
}
```

Required: `city`.

Default `extensions`: `base`.

### Normalized Response Contracts

`search_poi` returns:

```json
{
  "results": [
    {
      "poi_id": "string",
      "name": "string",
      "category": "string",
      "address": "string",
      "location": "lng,lat",
      "city": "string",
      "source": "amap"
    }
  ]
}
```

`get_poi_detail` returns:

```json
{
  "poi": {
    "poi_id": "string",
    "name": "string",
    "category": "string",
    "address": "string",
    "location": "lng,lat",
    "city": "string",
    "source": "amap"
  }
}
```

`check_route` returns:

```json
{
  "route": {
    "origin": "lng,lat",
    "destination": "lng,lat",
    "mode": "walking",
    "distance_meters": 1200,
    "duration_seconds": 900,
    "source": "amap"
  }
}
```

`check_weather` returns:

```json
{
  "weather": {
    "city": "string",
    "condition": "string",
    "temperature_celsius": "string",
    "wind_direction": "string",
    "wind_power": "string",
    "report_time": "string",
    "source": "amap"
  }
}
```

## 6. Observability

The AMAP provider must not write observability records directly.

When called through Tool Gateway:

- successful calls write `tool_events` through existing gateway behavior
- failed AMAP/config/HTTP errors write failed `tool_events`
- cacheable reads may use Redis cache through existing gateway behavior

No LangSmith tracing is added in this task. The AMAP API key must never appear in observability payloads.

## 7. Failure Handling

- Missing API key raises `AMapConfigurationError`.
- Unsupported tool raises `AMapUnsupportedToolError`.
- Missing required payload fields raise `AMapProviderError`.
- Invalid route mode raises `AMapProviderError`.
- AMAP HTTP timeout or network errors raise `AMapProviderError`.
- AMAP response with `status != "1"` raises `AMapProviderError`.
- Empty POI/weather/route responses should return an empty normalized result only when AMAP reports success; malformed successful responses should raise `AMapProviderError`.
- Default tests must not depend on network availability or real AMAP quota.

## 8. Acceptance Criteria

- [ ] `backend.app.providers.amap` package exists.
- [ ] `AMapProvider.name == "amap"`.
- [ ] Provider uses `Settings.amap_maps_api_key`.
- [ ] Provider never logs or stores the AMAP API key.
- [ ] `httpx` is available as a runtime dependency.
- [ ] `search_poi` is implemented and normalized.
- [ ] `get_poi_detail` is implemented and normalized.
- [ ] `check_route` supports `walking` and `driving`.
- [ ] `check_weather` is implemented and normalized.
- [ ] Unsupported canonical tools fail safely.
- [ ] `build_amap_registry()` registers provider with Tool Gateway defaults.
- [ ] Unit tests use fake client/responses and do not call the real network.
- [ ] Gateway integration tests use real PostgreSQL and Redis with fake AMAP responses.
- [ ] Optional live AMAP test is skipped by default.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task6` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
git switch task5
git switch -c task6
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

Optional live smoke test:

```bash
$env:RUN_AMAP_LIVE_TESTS="1"
python -m pytest tests/integration/test_amap_live.py -v
```

The optional live test requires `AMAP_MAPS_API_KEY` in local `.env`. It must remain skipped by default.

## 10. Expected Commit

```text
feat: add amap read provider
```

## 11. Notes for the Implementer

If Task 005 Tool Gateway files are missing, stop and report the branch/base mismatch.

This task intentionally prioritizes real AMAP read capability over Mock World. Mock World should be a follow-up task so benchmark determinism and write-tool simulation are not lost.
