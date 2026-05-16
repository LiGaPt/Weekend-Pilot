# WeekendPilot Project Blueprint

## 1. Project Goal

WeekendPilot is a benchmark-driven local-life planning and execution system for short weekend activities. A user provides one natural-language goal, such as wanting to spend a free afternoon with family or friends without going too far from home. The system should turn that request into executable plans, ask for confirmation, and then simulate the required booking, queueing, ordering, and messaging actions.

The product goal is not to return a recommendation list. The product goal is to help the user finish the whole arrangement:

```text
understand request -> search candidates -> verify feasibility -> generate plans
-> ask for confirmation -> execute actions -> record feedback
```

## 2. Competition Context

The competition topic is "local exploration: weekend idle-time activity planning." The required deliverables are:

- A runnable demo through a minimal Web UI.
- Complete tool implementation code, including Mock API calls.
- A short design document describing the planning strategy, tool call chain, and exception handling mechanism.

The expected system should plan a 4-6 hour afternoon route, including activities, dining, optional add-ons, availability checks, queue or reservation status, and final executable actions after user confirmation.

## 3. Product Scope

### MVP

- Family scenario as the main path.
- Input example: "This afternoon I want to go out with my wife and child for a few hours. Not too far. My child is 5, and my wife is trying to eat lighter."
- Mock local-life world for activities, restaurants, queues, reservations, tickets, orders, and messages.
- PostgreSQL for durable business state and memory.
- Redis for runtime cache, locks, progress events, and rate limits.
- LangSmith for tracing, token usage, latency, tool calls, and evaluation metadata.
- Bounded multi-agent workflow with no more than 5 LLM agents.
- Human confirmation before any write tool.
- Action Ledger for all side-effect actions.
- Basic LocalLife-Bench cases for happy path and fallback path.
- Minimal Web UI as the first demo surface. CLI is optional developer tooling, not the MVP demo path.

### V1

- Friend group scenario.
- Long-term memory governance.
- Failure injection and replay harness.
- LocalLife-Bench L1-L3 cases.
- Richer Web UI with planning, explicit confirmation, execution timeline, trace summaries, benchmark reports, and recovery visualization.

### V2

- Richer L4-L5 benchmark cases.
- Success@1, Avg@4, Pass@4, and Pass^4 stability metrics.
- Real map provider integration through AMap or Baidu MCP.
- More complete feedback learning and personalization.

## 4. Architecture Principles

- **Benchmark-driven:** The system must be designed so that behavior can be tested by LocalLife-Bench, not only judged by final text quality.
- **Centralized bounded multi-agent:** Use a central Supervisor and a small number of specialist agents. Avoid unconstrained peer-to-peer agent collaboration.
- **Deterministic where possible:** Routing, execution, route calculation, idempotency, action ledger writes, and benchmark grading should be deterministic whenever possible.
- **Human confirmation before side effects:** No reservation, queue join, ticket booking, order, or message send can happen before explicit user confirmation.
- **Observable by default:** Agent calls, tool calls, token usage, latency, recovery decisions, and final scores should be traceable.
- **PostgreSQL as source of truth:** Durable business facts live in PostgreSQL.
- **Redis as runtime layer:** Redis is for short-lived cache, progress events, locks, and rate limits only.
- **LangSmith as observability layer:** LangSmith is used for trace visualization and evaluation workflows, but the core product must still run when LangSmith is unavailable.
- **Small, reviewable tasks:** Every implementation task should have its own spec, plan, tests, commit, and push.

## 5. Technology Stack

Planned stack:

- Python
- FastAPI
- LangGraph
- LangSmith
- PostgreSQL
- Redis
- SQLAlchemy and Alembic
- Pydantic
- pytest
- Docker Compose
- React/Vite Web UI for the demo, with FastAPI serving workflow APIs.

The first implementation should prioritize backend workflow, benchmark harness, and a minimal Web UI before frontend polish. CLI can be deferred unless needed for developer tooling.

## 6. Agent Architecture

WeekendPilot uses a centralized bounded multi-agent architecture. The system should stay within 5 LLM agents:

1. **Supervisor Agent**
   - Owns high-level orchestration.
   - Coordinates specialist agents.
   - Aggregates structured outputs.
   - Decides when to ask the user for clarification.
   - Does not directly execute write tools.

2. **Discovery Agent**
   - Explores local activity candidates.
   - Handles family activities, children-friendly venues, exhibitions, malls, citywalk routes, and snack streets.
   - Returns structured candidates with evidence and risks.

3. **Dining Agent**
   - Explores restaurant candidates.
   - Interprets diet constraints, child-friendliness, queue status, table availability, and dining suitability.
   - Does not perform reservations directly.

4. **Itinerary Planner Agent**
   - Combines activities, dining, route data, time windows, and preferences into 2-3 executable plans.
   - Produces structured itineraries and proposed action lists.

5. **Validator & Recovery Agent**
   - Reviews plan feasibility.
   - Identifies typed failure reasons.
   - Chooses recovery actions such as retry, replace candidate, expand search, ask user, or stop safely.
   - Must output structured recovery decisions with retry budgets.

The following capabilities should not be implemented as free-form LLM agents:

- Intent Parser
- Memory Retriever
- Query Planner
- Candidate Merger
- Route & Time Calculator
- Tool Gateway
- Availability Checker
- Execution Workflow
- Action Ledger Writer
- Final Review Gate rule checks
- Benchmark Graders
- Feedback Writer

## 7. Main Workflow

Normal workflow:

```text
User Input
  -> Intent Parser
  -> Memory Retriever
  -> Query Planner
  -> Supervisor
  -> Discovery Agent + Dining Agent
  -> Candidate Merger
  -> Availability Checker + Route & Time Calculator
  -> Itinerary Planner Agent
  -> Validator & Recovery Agent
  -> Final Review Gate
  -> User Confirmation
  -> Execution Workflow
  -> Feedback Writer
```

The first parallel section should only happen after the Query Planner has produced a clear search plan. Discovery and Dining can search in parallel. Route and detailed availability checks should run after concrete candidates exist.

## 8. Routing Strategy

The normal route should be controlled by a LangGraph state machine, not by free-form LLM routing:

```text
parse_intent
-> load_memory
-> build_query_plan
-> discover_candidates
-> enrich_candidates
-> generate_itinerary
-> validate
-> final_review
-> wait_confirmation
-> execute
-> write_feedback
```

Dynamic recovery routing is allowed only through structured decisions from Validator & Recovery:

```json
{
  "verdict": "failed",
  "error_type": "restaurant_queue_too_long",
  "recovery_action": "replace_restaurant",
  "route_to": "dining_agent",
  "retry_budget": 1
}
```

No recovery loop should be unbounded.

## 8.1 Workflow State and Node Separation

LangGraph should use a strict typed global state. State should store structured domain models, not raw dictionaries, whenever project schemas exist.

Preferred state values include:

- `user_request`
- `parsed_intent` as `LocalLifeIntent`
- `user_memory` as structured memory records
- `query_plan` as `QueryPlan`
- `candidate_blackboard` as structured candidate/evidence records
- `screened_candidate_ids`
- `logical_plan` as a bounded semantic plan proposal
- `final_itinerary` as deterministic itinerary output
- `validation_errors`
- `action_ledger_plan` or confirmed action specs

Nodes should be separated by responsibility:

Deterministic nodes own:

- memory retrieval
- query planning in the MVP
- tool execution through Tool Gateway
- pre-flight availability checks
- route and time calculation
- final itinerary timestamp compilation
- confirmation boundary
- execution workflow
- feedback writing
- benchmark grading

Bounded semantic agent nodes may own:

- candidate scoring
- logical planning
- semantic validation
- supervisor coordination
- discovery and dining interpretation

LLM-backed nodes must stay behind typed contracts, must not call raw providers, and must not execute write tools.

### V1 Optimized Workflow Target

The V1 workflow should evolve toward this DAG:

```text
initialize
-> parse_intent
-> load_memory
-> generate_queries
-> execute_searches
-> populate_candidate_blackboard
-> pre_flight_check_availability
-> logical_planner_agent
-> route_and_time_engine
-> semantic_validator
-> final_review
-> present_to_user
-> wait_confirmation
-> saga_execution_engine
-> generate_summary_message
```

Key design rules:

- Pre-flight checks should filter closed, full, unavailable, or obviously unsuitable POIs before planning.
- Logical planning should decide sequence and rationale, not exact timestamps.
- Route and time calculation should be deterministic.
- If route/time math is impossible, later recovery routing may loop back to planning with an explicit retry budget.
- Semantic validation may detect constraint misses, but recovery loops must remain bounded.
- Execution remains deterministic and writes to Action Ledger.

## 9. Tool Gateway

All tool calls must go through Tool Gateway. Agents should not call raw external or mock APIs directly.

Tool Gateway responsibilities:

- Provide one normalized interface for all tools.
- Support mock and real providers.
- Record tool events.
- Create LangSmith tool spans where possible.
- Write durable tool call metadata to PostgreSQL.
- Use Redis cache for short-lived expensive reads.
- Support rate limits.
- Support failure injection for benchmark mode.
- Classify tools as read tools or write tools.
- Block write tools before user confirmation.

Read tools:

- `search_poi`
- `get_poi_detail`
- `check_route`
- `check_opening_hours`
- `check_weather`
- `check_queue`
- `check_table_availability`
- `check_ticket_availability`

Write tools:

- `join_queue`
- `reserve_restaurant`
- `book_ticket`
- `order_addon`
- `send_message`

The MVP must work with Mock World even when real map APIs are unavailable.

## 10. Data Design

PostgreSQL is the source of truth for durable state.

Initial tables:

- `users`
- `user_profiles`
- `memory_items`
- `agent_runs`
- `plans`
- `tool_events`
- `action_ledger`
- `activity_history`
- `benchmark_cases`
- `benchmark_runs`
- `benchmark_scores`
- `world_fixtures`
- `failure_injections`

Long-term memory fields:

- `memory_type`
- `key`
- `value_json`
- `text`
- `confidence`
- `source_run_id`
- `source_langsmith_trace_id`
- `last_used_at`
- `expires_at`
- `status`

Memory rules:

- Current user input overrides long-term memory.
- Low-confidence memory should not strongly influence plans.
- Expired memory should be ignored or downgraded.
- Sensitive details should be structured and minimized rather than stored as raw text when possible.

Redis responsibilities:

- Runtime cache.
- Progress stream.
- Distributed lock.
- Rate limit counters.
- Short-lived session state.

Redis must not be treated as a durable fact store.

## 11. Execution Workflow and Action Ledger

Execution must be deterministic. It should not be a free-form agent.

Execution flow:

```text
planner proposes action list
-> user confirms action list
-> execution workflow runs actions
-> each action writes Action Ledger
-> failures trigger recovery or user-facing partial completion
```

Action Ledger fields:

- `action_id`
- `run_id`
- `action_type`
- `target_id`
- `idempotency_key`
- `status`
- `request_json`
- `response_json`
- `error_json`
- `created_at`
- `updated_at`

Every write tool must use an idempotency key. Duplicate confirmations or repeated clicks should not create duplicate reservations, tickets, orders, queues, or messages.

## 12. Human-in-the-loop

The workflow must pause before side-effect execution.

Before confirmation:

- The system may search.
- The system may check availability.
- The system may generate plans.
- The system may propose action lists.
- The system must not execute write tools.

After confirmation:

- The deterministic Execution Workflow may run the confirmed action list.
- The Action Ledger must record each action.
- Partial success must be reported accurately.

## 13. Final Review Gate

The Final Review Gate is a pre-output review node, not a full autonomous agent.

It combines:

- Rule Checker
- Structured Consistency Checker
- Optional lightweight LLM Reviewer

Plan Review checks:

- The plan includes at least one activity and one dining option.
- The timeline covers the requested 4-6 hour range unless explicitly explained.
- The plan respects core constraints such as distance, child-friendliness, and diet preferences.
- IDs in the final plan come from verified candidates.
- Proposed actions reference objects in the final selected plan.
- No write tool has executed before confirmation.
- The response does not expose internal traces, prompts, secrets, or irrelevant debug data.

Execution Review checks:

- The final message accurately reflects which actions succeeded or failed.
- Partial failures are not hidden.
- Follow-up recovery steps are clear.

## 14. Observability

LangSmith should record:

- Run traces.
- Agent spans.
- Tool call spans.
- LLM token usage.
- Latency.
- Cost where available.
- Model name.
- Prompt version.
- Agent version.
- Evaluator scores.
- User feedback.

Each run should carry metadata:

- `run_id`
- `user_id`
- `case_id`
- `agent_version`
- `prompt_version`
- `tool_profile`
- `world_profile`
- `failure_profile`

LangSmith upload failure must not fail the user workflow. The system should keep a local JSONL trace buffer or PostgreSQL run summary so that key events remain recoverable.

## 15. Failure Handling and Recovery

Fallback is a full-chain failure handling system, not just replacement of a restaurant or activity.

Error classes:

- `user_input_error`
- `memory_conflict`
- `tool_timeout`
- `empty_result`
- `rate_limited`
- `invalid_tool_response`
- `route_infeasible`
- `availability_failed`
- `plan_invalid`
- `user_changed_request`
- `execution_failed`
- `observability_failed`

Recovery strategies:

- `retry`
- `use_cache`
- `switch_provider`
- `expand_search_radius`
- `replace_candidate`
- `regenerate_plan`
- `ask_user`
- `degrade_to_mock`
- `compensate_action`
- `stop_safely`

Key constraints:

- Retry budgets must be explicit.
- Recovery decisions must be traceable.
- Confirmation boundaries must remain intact.
- Partially successful execution must be visible and recoverable.
- Observability failure cannot break the main product flow.

## 16. Harness Engineering

Harness is part of the product engineering design, not just a testing add-on.

Harness components:

- Scenario Harness
- World Harness
- Run Harness
- Eval Harness
- Replay Harness
- Chaos Harness

Responsibilities:

- Load scenario definitions.
- Initialize user memory.
- Initialize Mock World.
- Inject tool failures.
- Drive the full workflow.
- Collect trace, tool events, and action ledger data.
- Run rubric graders.
- Generate reports.
- Replay failed cases.

## 17. LocalLife-Bench

LocalLife-Bench evaluates the full behavior trajectory of the local-life agent system.

It is inspired by interactive real-world agent benchmark ideas such as VitaBench / LongCat AgentBenchmark. The benchmark should test the whole planning and execution process instead of only final answer quality.

Complexity dimensions:

- Reasoning complexity:
  - time constraints
  - spatial constraints
  - group constraints
  - preference constraints
  - implicit reasoning

- Tool complexity:
  - number of tools
  - tool dependency depth
  - read/write tool ratio
  - cross-tool result composition

- Interaction complexity:
  - vague user requests
  - mid-run requirement changes
  - confirmation behavior
  - user feedback

Difficulty levels:

- L1: single-scenario planning
- L2: multi-constraint planning
- L3: dynamic interaction
- L4: cross-scenario execution
- L5: failure recovery

Scoring dimensions:

- Intent Accuracy
- Tool Trajectory
- Plan Quality
- Constraint Satisfaction
- Execution Safety
- Recovery Capability
- Memory Usage
- Observability
- Cost and Latency

Metrics:

- Success@1
- Avg@4
- Pass@4
- Pass^4
- Trajectory Score
- Safety Score
- Recovery Score
- Memory Score
- Cost Score

Each benchmark case should include:

- `case_id`
- `level`
- `input`
- `initial_memory`
- `world_state`
- `failure_injection`
- `expected_tool_subgraph`
- `forbidden_tools_before_confirmation`
- `rubrics`

The first benchmark version should start small, around 5-10 cases, and grow after the core workflow is stable.

## 18. Development Workflow

Development should follow:

```text
project blueprint
-> task spec
-> implementation plan
-> implementation
-> verification
-> commit
-> push
-> review
```

Every task should have:

- A spec.
- A plan.
- Clear non-goals.
- Acceptance criteria.
- Verification commands.
- A single commit message.

The implementation session should only modify files relevant to the task.

## 19. Coding and Repository Rules

- Never commit `.env`, API keys, tokens, or secrets.
- Keep `.env.example` updated.
- Use small commits.
- Use conventional commit messages.
- Keep each task independently reviewable.
- Prefer structured schemas over ad hoc strings.
- Prefer deterministic code for routing, execution, grading, locking, and durable state.
- Use LLM calls only where semantic reasoning is actually needed.
- Mock provider must remain available even if real provider integration is added.
- The project must stay runnable without LangSmith, real map keys, or real local-life APIs.

## 20. Initial Task Roadmap

Suggested first tasks:

1. Add project blueprint.
2. Add task spec and plan templates.
3. Scaffold backend project.
4. Add Docker Compose for PostgreSQL and Redis.
5. Add configuration management.
6. Add PostgreSQL schema and repositories.
7. Add Redis runtime services.
8. Add Tool Gateway.
9. Add Mock World Provider.
10. Add deterministic planning services.
11. Add LangGraph workflow skeleton.
12. Add bounded multi-agent layer.
13. Add Action Ledger and human confirmation.
14. Add Execution Workflow.
15. Add LangSmith observability.
16. Add LocalLife-Bench harness.
17. Add Web demo API surface.
18. Add minimal Web UI demo.
19. Add Web end-to-end tests and demo README.
20. Add V1 workflow state and DAG optimization.
21. Add recovery routing v0.
22. Expand LocalLife-Bench cases.

## 21. Open Questions

Resolved decisions:

- MVP starts with a minimal Web UI, not CLI.
- CLI is deferred unless needed as developer tooling.
- First demo remains fully Mock World until the Web path is stable.
- V1 workflow optimization should happen after the first Web demo is usable.

Remaining open questions:

- How many benchmark cases should be included in the first expanded suite: 5, 10, or 20?
- Which bounded agent should become LLM-backed first after deterministic adapters are stable?
- How much recovery routing should be implemented before adding real provider support?
