# Plan: 008 Deterministic Intent and Query Planning

## 1. Spec Reference

Spec file:

```text
docs/specs/008-deterministic-intent-query-planning.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task7`.
- Current Task 007 commit is `6f76d3b feat: add mock world provider`.
- Existing providers:
  - `backend.app.providers.amap`
  - `backend.app.providers.mock_world`
- Existing Tool Gateway canonical tool names are in `backend/app/tool_gateway/registry.py`.
- No `backend/app/planning` package exists yet.

## 3. Files to Add

- `backend/app/planning/__init__.py` - public exports.
- `backend/app/planning/errors.py` - `IntentParseError` and `QueryPlanError`.
- `backend/app/planning/schemas.py` - Pydantic schemas.
- `backend/app/planning/intent_parser.py` - deterministic parser.
- `backend/app/planning/query_planner.py` - deterministic query planner.
- `tests/test_intent_parser.py` - parser tests.
- `tests/test_query_planner.py` - query planner tests.

## 4. Files to Modify

- `README.md` - optional short test command section for planning services.
- `docs/specs/008-deterministic-intent-query-planning.md` - save Task 008 spec.
- `docs/plans/008-deterministic-intent-query-planning-plan.md` - save Task 008 plan.

No dependency or migration changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task7
git switch -c task8
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/providers backend/app/tool_gateway backend/app/planning tests docs/specs docs/plans
```

Expected:

- Branch is `task8`.
- Task 007 Mock World provider exists.
- `backend/app/planning` does not exist yet.

3. Add `errors.py`:

```python
class IntentParseError(ValueError):
    pass

class QueryPlanError(ValueError):
    pass
```

4. Add schemas in `schemas.py`.

Use Pydantic `BaseModel`.

Required literals:

```python
ScenarioType = Literal["family", "friends", "solo", "unknown"]
ProviderProfile = Literal["mock_world", "amap"]
```

Required models:

```python
TimeWindow
ParticipantProfile
IntentConstraints
LocalLifeIntent
PlannedToolCall
ToolCallTemplate
QueryPlan
```

Important defaults:

- `ParticipantProfile.adults = 1`
- `ParticipantProfile.children_ages = []`
- `IntentConstraints.child_friendly = False`
- `IntentConstraints.max_distance_km = None`
- `TimeWindow.duration_hours_min = None`
- `TimeWindow.duration_hours_max = None`

5. Implement `DeterministicIntentParser`.

Rules:

- Strip text; raise `IntentParseError` if empty.
- Detect family scenario from English and Chinese spouse/child keywords:
  - `wife`, `husband`, `child`, `kid`, `family`
  - `老婆`, `妻子`, `丈夫`, `孩子`, `小孩`, `亲子`
- Adult count:
  - default `1`
  - family with spouse keywords should be at least `2`
- Child ages:
  - parse English patterns like `child is 5`, `5-year-old`
  - parse Chinese patterns like `5岁孩子`, `孩子5岁`
- Time:
  - detect `this afternoon`, `afternoon`, `今天下午`
  - if `reference_now` is provided, set same-day approximate afternoon window, e.g. `13:30` to `18:30`
  - if no `reference_now`, keep label `this_afternoon` without concrete datetimes
- Duration:
  - `few hours` / `几个小时` maps to min `4`, max `6`
- Distance:
  - `not too far` / `别太远` maps to `max_distance_km=8`
- Dining:
  - `lighter`, `light`, `eat lighter`, `清淡` maps to dining preference `lighter_options`
- Child-friendly:
  - any child/family signal sets `child_friendly=True`

6. Implement `DeterministicQueryPlanner`.

Rules:

- Support `provider_profile="mock_world"` and `"amap"`.
- Default to `"mock_world"`.
- Reject unsupported provider with `QueryPlanError`.
- Never execute tools.
- Never include write tools in `initial_tool_calls`.
- Always include canonical write tools in `forbidden_write_tools_before_confirmation`.

For `mock_world`, initial calls:

```python
search_poi activity:
{
  "query": "family child friendly activity",
  "category": "activity",
  "tags": ["child_friendly"],
  "limit": 5
}

search_poi dining:
{
  "query": "lighter family dining",
  "category": "dining",
  "tags": ["child_friendly", "lighter_options"],
  "limit": 5
}

check_weather:
{
  "location": "Xuhui"
}
```

The dining query may omit `lighter_options` only if the parsed intent does not include that preference.

For `amap`, initial calls should only include tools AMAP supports:

```text
search_poi activity
search_poi dining
check_weather
```

Do not include AMAP queue/table/ticket templates.

7. Add enrichment templates.

For `mock_world` plans include templates with required input markers:

```text
get_poi_detail requires poi_id
check_opening_hours requires poi_id
check_queue requires poi_id or queue_id
check_table_availability requires restaurant_id
check_ticket_availability requires poi_id
```

8. Add route templates.

Include:

```text
check_route requires origin_id and destination_id
mode walking
```

9. Export public API in `backend/app/planning/__init__.py`.

Export:

```python
DeterministicIntentParser
DeterministicQueryPlanner
IntentParseError
QueryPlanError
LocalLifeIntent
QueryPlan
```

10. Add parser tests.

Cover:

- English MVP family request.
- Chinese MVP family request.
- Empty text raises `IntentParseError`.
- Non-empty vague text returns `scenario_type="unknown"` with conservative defaults.
- `reference_now` produces deterministic afternoon datetimes.

11. Add query planner tests.

Cover:

- Mock World query plan includes activity search, dining search, weather.
- Light dining preference adds `lighter_options`.
- Planned calls use `provider="mock_world"`.
- Enrichment templates include detail/opening/queue/table/ticket checks.
- Route templates include walking route template.
- Write tools are forbidden before confirmation.
- AMAP plan excludes Mock-only availability templates.
- Unsupported provider raises `QueryPlanError`.
- Planner does not invoke Tool Gateway or providers.

12. Optionally update README.

Add:

```bash
python -m pytest tests/test_intent_parser.py tests/test_query_planner.py -v
```

Do not add demo claims yet.

13. Run focused tests:

```bash
python -m pytest tests/test_intent_parser.py tests/test_query_planner.py -v
```

14. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

15. Commit and push:

```bash
git status --short
git add README.md backend/app/planning tests/test_intent_parser.py tests/test_query_planner.py docs/specs/008-deterministic-intent-query-planning.md docs/plans/008-deterministic-intent-query-planning-plan.md
git status --short
git commit -m "feat: add deterministic intent and query planning"
git push -u origin task8
```

## 6. Testing Plan

- Unit tests:
  - English MVP request parsing
  - Chinese MVP request parsing
  - empty/vague input handling
  - deterministic relative-time parsing with `reference_now`
  - query plan shape for `mock_world`
  - query plan shape for `amap`
  - forbidden write tool list
  - unsupported provider error
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
feat: add deterministic intent and query planning
```

Expected branch:

```text
task8
```

The implementer must confirm `.env`, secrets, caches, virtualenvs, logs, and Docker volumes are not staged.

## 9. Out-of-scope Changes

- Do not call Tool Gateway.
- Do not call AMAP or Mock World.
- Do not add LangGraph.
- Do not add LLM agents.
- Do not add prompts.
- Do not implement Memory Retriever.
- Do not implement Candidate Merger.
- Do not implement Availability Checker.
- Do not implement Route & Time Calculator execution.
- Do not add API endpoints.
- Do not add database migrations.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task8`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] Parser and planner are deterministic.
- [ ] Parser handles English and Chinese MVP requests.
- [ ] Query plan includes immediate read calls and later enrichment templates.
- [ ] Query plan forbids write tools before confirmation.
- [ ] No provider, Tool Gateway, DB, Redis, or LLM calls occur in planning services.
- [ ] Focused parser/planner tests pass.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Commit message is `feat: add deterministic intent and query planning`.
- [ ] Push to `origin/task8` succeeds.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused planning test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 008 is the first deterministic planning-service task after providers.
- Scope is intentionally limited to Intent Parser + Query Planner.
- `mock_world` remains the default provider profile because it supports all canonical tools deterministically.
- AMAP planning support is limited to the read tools Task 006 supports.
