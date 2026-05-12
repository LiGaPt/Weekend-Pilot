# Spec: 007 Mock World Provider

## 1. Goal

Add a deterministic `mock_world` provider behind Tool Gateway so WeekendPilot can run local-life planning and execution tests without real external APIs, live availability systems, reservations, tickets, queues, ordering, or messaging services.

After this task, all canonical Tool Gateway tools should be callable through `mock_world`, including read tools, availability checks, and write-tool simulations. This restores the benchmark-first path after Task 006 added optional AMAP read support.

## 2. Project Context

Task 005 created the Tool Gateway. Task 006 added an optional real AMAP read provider for POI search, route, and weather. AMAP is useful for demos, but it cannot provide deterministic availability, write-tool simulation, failure replay, or stable LocalLife-Bench trajectories.

Task 007 adds the deterministic Mock World provider required by `docs/PROJECT_BLUEPRINT.md`. It should coexist with AMAP and use the same provider interface, but it must not call external services or require secrets.

## 3. Requirements

- Add `backend.app.providers.mock_world`.
- Provider name must be exactly `mock_world`.
- Use local JSON fixture data committed to the repo.
- Add default fixture profile: `family_afternoon`.
- Support all canonical Tool Gateway tools:
  - read:
    - `search_poi`
    - `get_poi_detail`
    - `check_route`
    - `check_opening_hours`
    - `check_weather`
    - `check_queue`
    - `check_table_availability`
    - `check_ticket_availability`
  - write:
    - `join_queue`
    - `reserve_restaurant`
    - `book_ticket`
    - `order_addon`
    - `send_message`
- Add `build_mock_world_registry(profile="family_afternoon")`.
- Fixture must contain at least:
  - 3 activity POIs
  - 3 dining POIs
  - 1 add-on/vendor POI
  - route records between important POIs
  - opening hours
  - weather
  - queue statuses
  - table availability
  - ticket availability
- Provider responses must be deterministic and JSON-serializable.
- Write tools must return simulated confirmation payloads, but idempotency remains owned by Tool Gateway and Action Ledger.
- Unit tests must cover fixture loading, direct provider read tools, direct provider write tools, and invalid payload/entity handling.
- Integration tests must call Mock World through Tool Gateway with real PostgreSQL and Redis.
- README must document focused Mock World test commands.
- No `.env`, API keys, tokens, or secrets may be committed.

## 4. Non-goals

- Do not implement failure injection profiles.
- Do not implement benchmark cases, graders, replay harness, or chaos harness.
- Do not implement LangGraph, agents, planner services, execution workflow, or Final Review Gate.
- Do not implement FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not store Mock World fixture state in PostgreSQL.
- Do not replace AMAP provider or change its public API.
- Do not call real network services.

## 5. Interfaces and Contracts

### Inputs

- `tool_name: str`
- `payload: dict[str, Any]`
- local fixture profile, default `family_afternoon`
- Tool Gateway requests when invoked through gateway

### Outputs

- JSON-serializable provider response dictionaries
- Tool Gateway results through existing gateway behavior
- PostgreSQL `tool_events` and `action_ledger` rows when invoked through Tool Gateway

### Public Modules

```text
backend.app.providers.mock_world.__init__
backend.app.providers.mock_world.errors
backend.app.providers.mock_world.loader
backend.app.providers.mock_world.provider
backend.app.providers.mock_world.registry
backend.app.providers.mock_world.fixtures.family_afternoon.json
```

### Provider Contract

```python
class MockWorldProvider:
    name = "mock_world"

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
```

### Registry Contract

```python
def build_mock_world_registry(profile: str = "family_afternoon") -> ToolRegistry:
    ...
```

It must call `build_default_registry(default_provider="mock_world")` and register `MockWorldProvider`.

### Fixture Shape

```json
{
  "profile": "family_afternoon",
  "location": {"city": "Shanghai", "area": "Xuhui"},
  "pois": [],
  "routes": [],
  "weather": {},
  "queues": {},
  "table_availability": {},
  "ticket_availability": {},
  "addons": []
}
```

Recommended stable IDs:

```text
activity_museum_001
activity_playground_001
activity_walk_001
restaurant_light_001
restaurant_family_001
restaurant_noodle_001
addon_drinks_001
```

### Tool Response Contracts

- `search_poi` returns `{"results": [...]}` sorted deterministically.
- `get_poi_detail` returns `{"poi": {...}}`.
- `check_route` returns `{"route": {...}}`.
- `check_opening_hours` returns `{"opening_hours": {...}}`.
- `check_weather` returns `{"weather": {...}}`.
- `check_queue` returns `{"queue": {...}}`.
- `check_table_availability` returns `{"table_availability": {...}}`.
- `check_ticket_availability` returns `{"ticket_availability": {...}}`.
- Write tools return `{"confirmation": {...}}`.

## 6. Observability

Mock World must not write observability records directly.

When invoked through Tool Gateway:

- every attempt writes `tool_events`
- confirmed write tools create/update `action_ledger`
- cacheable reads may use Redis cache through existing Tool Gateway behavior

No LangSmith tracing is added in this task.

## 7. Failure Handling

- Unknown fixture profile raises `MockWorldError`.
- Malformed fixture raises `MockWorldError`.
- Unknown tool raises `MockWorldError`.
- Missing required payload fields raise `MockWorldError`.
- Unknown POI, route, queue, restaurant, ticket, add-on, or recipient raises `MockWorldError`.
- Empty search results return `{"results": []}` instead of raising.
- Provider must never read `.env` or call external network services.

## 8. Acceptance Criteria

- [ ] `backend.app.providers.mock_world` package exists.
- [ ] `MockWorldProvider.name == "mock_world"`.
- [ ] `family_afternoon` JSON fixture exists and is committed.
- [ ] Fixture loader validates required top-level keys and unique POI IDs.
- [ ] All canonical read tools are implemented.
- [ ] All canonical write tools are implemented.
- [ ] `build_mock_world_registry()` registers provider with Tool Gateway defaults.
- [ ] Direct provider tests cover read tools, write tools, and error paths.
- [ ] Gateway integration tests use real PostgreSQL and Redis.
- [ ] Unconfirmed write through Tool Gateway is blocked before provider execution.
- [ ] Confirmed write through Tool Gateway creates/updates Action Ledger.
- [ ] Cacheable read through Tool Gateway can hit Redis.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task7` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after the implementation commit.

## 9. Verification Commands

```bash
git switch task6
git switch -c task7
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add mock world provider
```

## 11. Notes for the Implementer

If Task 006 AMAP provider files are missing, stop and report the branch/base mismatch.

Do not add failure injection in this task. Mock World should be deterministic baseline behavior only; failure profiles belong in a later harness/failure task.
