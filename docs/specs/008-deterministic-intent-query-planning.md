# Spec: 008 Deterministic Intent and Query Planning

## 1. Goal

Add deterministic intent parsing and query planning services for WeekendPilot.

After this task, the system should be able to convert a user's natural-language local-life request into a structured `LocalLifeIntent`, then into a deterministic `QueryPlan` that later workflow nodes, discovery agents, or direct tool executors can consume.

This task does not call LLMs, Tool Gateway, Redis, PostgreSQL, AMAP, or Mock World. It only produces structured planning inputs.

## 2. Project Context

Task 005 added Tool Gateway, Task 006 added AMAP read provider, and Task 007 added Mock World provider.

Task 008 starts the deterministic service layer described in `docs/PROJECT_BLUEPRINT.md`:

```text
User Input
  -> Intent Parser
  -> Memory Retriever
  -> Query Planner
  -> Supervisor / Discovery / Dining
```

This task covers only:

- Intent Parser
- Query Planner
- shared planning schemas

It intentionally does not implement Memory Retriever, Candidate Merger, Route & Time Calculator, Availability Checker, LangGraph, Agents, Final Review Gate, Execution Workflow, or benchmark graders.

## 3. Requirements

- Add `backend.app.planning` package.
- Add typed Pydantic schemas for parsed intent and query plans.
- Implement deterministic rule-based `DeterministicIntentParser`.
- Implement deterministic `DeterministicQueryPlanner`.
- Parser must handle the MVP family-afternoon request:
  - "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter."
- Parser should also handle a Chinese equivalent:
  - "今天下午想带老婆和5岁孩子出去玩几个小时，别太远，吃清淡点。"
- Parser must extract:
  - raw text
  - scenario/group type
  - adult count
  - child ages
  - time preference
  - duration preference
  - distance constraint
  - child-friendly constraint
  - dining preference such as lighter food
  - activity/dining hints
- Parser must be deterministic and testable with a supplied `reference_now`.
- Query planner must generate a `QueryPlan` with:
  - initial read tool calls that can run immediately
  - enrichment templates that require later candidate IDs
  - route templates that require later selected/candidate IDs
  - forbidden write tools before confirmation
- Query planner default provider must be `mock_world`.
- Query planner may accept `provider_profile="mock_world"` or `provider_profile="amap"`, but `mock_world` is the only fully supported default for Task 008.
- Query planner must never include write tool calls as executable pre-confirmation steps.
- Add focused unit tests.
- No database migration, external API call, Redis access, Tool Gateway invocation, or LLM call is allowed.

## 4. Non-goals

- Do not implement Memory Retriever.
- Do not implement Candidate Merger.
- Do not implement Availability Checker.
- Do not implement Route & Time Calculator execution.
- Do not implement LangGraph.
- Do not implement agents or prompts.
- Do not call Tool Gateway.
- Do not call AMAP or Mock World providers.
- Do not add FastAPI endpoints.
- Do not add PostgreSQL migrations.
- Do not commit `.env`, API keys, tokens, or secrets.

## 5. Interfaces and Contracts

### Public Modules

```text
backend.app.planning.__init__
backend.app.planning.errors
backend.app.planning.schemas
backend.app.planning.intent_parser
backend.app.planning.query_planner
```

### Public API

```python
class DeterministicIntentParser:
    def parse(
        self,
        text: str,
        reference_now: datetime | None = None,
    ) -> LocalLifeIntent:
        ...

class DeterministicQueryPlanner:
    def build(
        self,
        intent: LocalLifeIntent,
        provider_profile: str = "mock_world",
    ) -> QueryPlan:
        ...
```

### Core Schemas

Required models in `backend/app/planning/schemas.py`:

```text
TimeWindow
ParticipantProfile
IntentConstraints
LocalLifeIntent
PlannedToolCall
ToolCallTemplate
QueryPlan
```

### LocalLifeIntent Contract

Required fields:

```text
raw_text: str
scenario_type: "family" | "friends" | "solo" | "unknown"
participants: ParticipantProfile
time_window: TimeWindow
constraints: IntentConstraints
activity_preferences: list[str]
dining_preferences: list[str]
origin_text: str | None
parser_version: str
```

### QueryPlan Contract

Required fields:

```text
intent: LocalLifeIntent
provider_profile: str
initial_tool_calls: list[PlannedToolCall]
candidate_enrichment_templates: list[ToolCallTemplate]
route_templates: list[ToolCallTemplate]
forbidden_write_tools_before_confirmation: list[str]
planner_version: str
notes: list[str]
```

### Initial Tool Calls

For `provider_profile="mock_world"`, the planner should produce at least:

```text
search_poi activity query
search_poi dining query
check_weather query
```

The activity search should prefer `category="activity"` and child-friendly tags.

The dining search should prefer `category="dining"` and lighter/child-friendly tags when detected.

### Enrichment Templates

The query plan should include templates for later stages to apply after candidate IDs are known:

```text
get_poi_detail
check_opening_hours
check_queue
check_table_availability
check_ticket_availability
```

### Route Templates

The query plan should include route templates for later stages to evaluate activity-to-dining combinations:

```text
check_route
```

## 6. Observability

This task does not write observability records.

The returned `LocalLifeIntent` and `QueryPlan` should include `parser_version` and `planner_version` so later workflow/tool traces can record which deterministic planning logic produced the plan.

## 7. Failure Handling

- Empty or whitespace-only user text raises `IntentParseError`.
- Unsupported or vague input should not fail if text is non-empty; parser should return `scenario_type="unknown"` and conservative defaults.
- Relative time parsing must use `reference_now` when provided.
- If `reference_now` is omitted, parser may keep relative labels without concrete datetimes.
- Query planner must reject unsupported `provider_profile` values with `QueryPlanError`.
- Query planner must not create write tool calls before confirmation.

## 8. Acceptance Criteria

- [ ] `backend.app.planning` package exists.
- [ ] Planning schemas are typed and importable.
- [ ] Intent parser is deterministic and rule-based.
- [ ] Query planner is deterministic and rule-based.
- [ ] MVP English family request parses into family scenario, 2 adults, one 5-year-old child, child-friendly constraints, light dining preference, and afternoon/duration intent.
- [ ] Chinese family request parses equivalently enough for MVP tests.
- [ ] Query planner produces immediate read tool calls for activity search, dining search, and weather.
- [ ] Query planner includes enrichment and route templates.
- [ ] Query planner includes all canonical write tools in forbidden-before-confirmation list.
- [ ] No Tool Gateway/provider/network/database/Redis calls occur in Task 008 services or tests.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task8` branch.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task7
git switch -c task8
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add deterministic intent and query planning
```

## 11. Notes for the Implementer

If Task 007 Mock World provider files are missing, stop and report the branch/base mismatch.

Keep this task pure and deterministic. Do not turn the parser or planner into an agent, and do not execute tools from the query planner.
