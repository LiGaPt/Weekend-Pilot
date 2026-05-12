# Plan: 007 Mock World Provider

## 1. Spec Reference

Spec file:

```text
docs/specs/007-mock-world-provider.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task6`.
- Current Task 006 commit is `6975edb feat: add amap read provider`.
- Existing provider package root is `backend/app/providers`.
- AMAP provider lives under `backend/app/providers/amap`.
- Tool Gateway exposes `ToolGateway`, `ToolGatewayRequest`, `ToolRegistry`, and `build_default_registry`.
- No `backend/app/providers/mock_world` package exists yet.

## 3. Files to Add

- `backend/app/providers/mock_world/__init__.py` - public exports.
- `backend/app/providers/mock_world/errors.py` - `MockWorldError`.
- `backend/app/providers/mock_world/loader.py` - fixture loading and validation.
- `backend/app/providers/mock_world/provider.py` - `MockWorldProvider`.
- `backend/app/providers/mock_world/registry.py` - `build_mock_world_registry()`.
- `backend/app/providers/mock_world/fixtures/family_afternoon.json` - deterministic fixture.
- `tests/test_mock_world_loader.py` - fixture loader tests.
- `tests/test_mock_world_provider.py` - direct provider tests.
- `tests/integration/test_mock_world_gateway.py` - Tool Gateway integration tests.

## 4. Files to Modify

- `README.md` - add Mock World test section.
- `docs/specs/007-mock-world-provider.md` - save Task 007 spec.
- `docs/plans/007-mock-world-provider-plan.md` - save Task 007 plan.

No dependency or migration changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task6
git switch -c task7
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/providers backend/app/tool_gateway tests docs/specs docs/plans
```

3. Add `MockWorldError`:

```python
class MockWorldError(ValueError):
    pass
```

4. Add `family_afternoon.json`.

Fixture should use stable, non-secret data and include:

- child-friendly activities
- lighter dining option
- family dining option
- noodle/simple dining option
- add-on drinks/snacks vendor
- deterministic routes
- deterministic opening/availability/weather data

5. Add `loader.py`.

Implement:

```python
def load_mock_world(profile: str = "family_afternoon") -> dict[str, Any]:
    ...
```

Requirements:

- use `importlib.resources.files`
- support only `family_afternoon`
- validate required top-level keys
- validate POI IDs are unique
- raise `MockWorldError` for unsupported profile or malformed fixture

6. Add `provider.py`.

Implement `MockWorldProvider` with explicit dispatch:

```python
class MockWorldProvider:
    name = "mock_world"

    def __init__(self, world: dict[str, Any] | None = None) -> None:
        self._world = world or load_mock_world()

    def invoke(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...
```

Do not use dynamic `getattr` based on raw tool input.

7. Implement read tools.

Payload contracts:

```text
search_poi:
  optional: query, category, tags, limit

get_poi_detail:
  required: poi_id

check_route:
  required: origin_id, destination_id
  optional: mode

check_opening_hours:
  required: poi_id
  optional: at

check_weather:
  optional: location, date

check_queue:
  required: poi_id or queue_id

check_table_availability:
  required: restaurant_id
  optional: party_size, time

check_ticket_availability:
  required: poi_id
  optional: quantity, time
```

8. Implement write tools.

Payload contracts:

```text
join_queue:
  required: queue_id
  optional: party_size

reserve_restaurant:
  required: restaurant_id, party_size, time_slot

book_ticket:
  required: poi_id, quantity, time_slot

order_addon:
  required: vendor_id, items

send_message:
  required: recipient, message
```

Confirmation IDs must be deterministic strings derived from tool name and target fields. Do not generate random UUIDs inside provider write responses.

9. Add `registry.py`.

```python
def build_mock_world_registry(profile: str = "family_afternoon") -> ToolRegistry:
    registry = build_default_registry(default_provider="mock_world")
    registry.register_provider(MockWorldProvider(load_mock_world(profile)))
    return registry
```

10. Add exports in `__init__.py`.

Export:

```python
MockWorldError
MockWorldProvider
build_mock_world_registry
load_mock_world
```

11. Add loader tests.

Cover:

- default fixture loads
- required top-level keys exist
- POI IDs are unique
- unsupported profile raises `MockWorldError`

12. Add provider tests.

Cover:

- search returns deterministic activity results
- search filters dining category
- detail returns known POI
- route returns deterministic distance/duration
- opening hours returns open/closed structure
- weather returns deterministic weather
- queue/table/ticket availability return expected structures
- every write tool returns confirmation shape
- unknown tool and missing required field raise `MockWorldError`

13. Add Gateway integration tests.

Use real PostgreSQL and Redis. Build gateway with `build_mock_world_registry()` and existing repository/runtime services.

Cover:

- `search_poi` through gateway succeeds and writes `tool_events`
- `check_weather` through gateway is cached on second identical call
- unconfirmed `reserve_restaurant` is blocked before provider execution
- confirmed `reserve_restaurant` succeeds and creates Action Ledger row
- duplicate idempotency key replays without duplicate provider effect
- invalid `poi_id` becomes failed gateway result and failed `tool_events`

14. Update README with focused command:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/integration/test_mock_world_gateway.py -v
```

15. Run verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

16. Commit and push:

```bash
git status --short
git add README.md backend/app/providers/mock_world tests/test_mock_world_loader.py tests/test_mock_world_provider.py tests/integration/test_mock_world_gateway.py docs/specs/007-mock-world-provider.md docs/plans/007-mock-world-provider-plan.md
git status --short
git commit -m "feat: add mock world provider"
git push -u origin task7
```

## 6. Testing Plan

- Unit tests:
  - fixture loader validation
  - direct read tool behavior
  - direct write tool confirmation behavior
  - invalid payload/entity errors
- Integration tests:
  - Tool Gateway + Mock World + PostgreSQL `tool_events`
  - Tool Gateway + Redis cache for cacheable reads
  - Tool Gateway + Action Ledger for confirmed writes
  - blocked write before confirmation
  - idempotent replay through gateway
- Smoke:
  - full `python -m pytest`
  - `docker compose config`

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

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add mock world provider
```

Expected branch:

```text
task7
```

The implementer must confirm `.env`, secrets, caches, virtualenvs, logs, and Docker volumes are not staged.

## 9. Out-of-scope Changes

- Do not modify AMAP provider behavior.
- Do not add real external API calls.
- Do not add failure injection.
- Do not add benchmark cases or graders.
- Do not implement planner, workflow, LangGraph, agents, or execution workflow.
- Do not add FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task7`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] Provider name is exactly `mock_world`.
- [ ] All canonical Tool Gateway tools are supported.
- [ ] Fixture data is deterministic and committed without secrets.
- [ ] Provider direct tests cover read/write behavior.
- [ ] Gateway integration tests use real PostgreSQL and Redis.
- [ ] Write tools remain blocked before confirmation through Tool Gateway.
- [ ] Confirmed writes create/update Action Ledger through Tool Gateway.
- [ ] Cacheable reads use Redis through Tool Gateway.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add mock world provider`.
- [ ] Push to `origin/task7` succeeded.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Mock World focused test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 007 is Mock World Provider because Task 006 explicitly deferred it.
- Fixture profile is `family_afternoon`.
- Provider package follows the existing Task 006 pattern under `backend.app.providers`.
- Mock write tools are deterministic and stateless; Tool Gateway owns confirmation, idempotency, and Action Ledger writes.
