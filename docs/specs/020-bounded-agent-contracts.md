# Spec: 020 Bounded Agent Contracts and Deterministic Adapters

## 1. Goal

Add the bounded multi-agent contract layer described in the project blueprint, using deterministic adapters first.

Task 020 should define the Supervisor, Discovery, Dining, Itinerary Planner, and Validator/Recovery agent boundaries, wire their deterministic adapters into the Task 019 LangGraph workflow, and preserve current deterministic behavior.

This task must not add LLM calls. It creates the agent interface and enforcement layer so later tasks can replace selected adapters with LLM-backed bounded agents without changing workflow contracts.

## 2. Project Context

Task 019 added `backend.app.workflow` as the official LangGraph orchestration path. Its nodes still call deterministic services directly.

Task 020 should introduce `backend.app.agents` and make the workflow agent-aware while keeping the same Mock World happy path.

Blueprint constraints:

- Use a centralized bounded multi-agent architecture.
- Stay within five agent roles.
- Agents must not call raw external or mock APIs directly.
- Agents must not execute write tools.
- Deterministic components such as Tool Gateway, Execution Workflow, Final Review Gate rule checks, benchmark graders, and Feedback Writer remain non-agent services.

## 3. Requirements

- Add `backend.app.agents`.
- Define exactly these agent roles:
  - `supervisor`
  - `discovery`
  - `dining`
  - `itinerary_planner`
  - `validator_recovery`
- Add typed schemas for:
  - agent role and status
  - agent invocation context
  - tool policy
  - agent result
  - supervisor assignment plan
  - recovery decision
- Add tool-policy enforcement:
  - agents may only reference approved read tools
  - agents may never execute write tools
  - write tools remain owned by confirmation plus deterministic execution workflow
- Add deterministic adapters:
  - Supervisor creates structured assignments after query planning.
  - Discovery summarizes activity candidate evidence from existing candidate collection and enrichment outputs.
  - Dining summarizes dining candidate evidence from existing candidate collection and enrichment outputs.
  - Itinerary Planner wraps `DeterministicItineraryGenerator`.
  - Validator/Recovery wraps `FinalReviewGate` and emits a structured recovery decision without executing recovery loops.
- Modify the LangGraph workflow to call these adapters at the relevant points and store sanitized agent summaries in workflow state.
- Add agent summary fields to `WeekendPilotWorkflowResult`, limited to role, status, summary, adapter version, and decision metadata.
- Persist sanitized agent summaries under `agent_runs.metadata_json["agents"]`.
- Preserve existing workflow statuses and confirmation behavior.
- Existing Task 019 workflow tests and Task 018 benchmark tests must keep passing.
- Add focused unit and integration tests.

## 4. Non-goals

- Do not add LLM calls, prompt templates, model routing, or provider configuration.
- Do not add LangSmith agent spans beyond existing local metadata.
- Do not execute raw tools inside agents.
- Do not execute write tools before confirmation.
- Do not add recovery loops, retries, or route changes.
- Do not add CLI, API endpoint, Web UI, or benchmark harness refactor.
- Do not add database migrations unless an existing schema defect blocks metadata storage.
- Do not require LLM credentials, LangSmith credentials, or live provider access for default tests.

## 5. Interfaces and Contracts

### Public Modules

```text
backend.app.agents.__init__
backend.app.agents.errors
backend.app.agents.schemas
backend.app.agents.policies
backend.app.agents.deterministic
```

### Agent Roles

```python
AgentRole = Literal[
    "supervisor",
    "discovery",
    "dining",
    "itinerary_planner",
    "validator_recovery",
]

AgentStatus = Literal["completed", "failed", "blocked", "skipped"]
```

### Invocation Context

```python
class AgentInvocationContext(BaseModel):
    run_id: UUID
    trace_id: str | None = None
    role: AgentRole
    agent_version: str
    prompt_version: str
    tool_profile: str
    world_profile: str
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Tool Policy

```python
class AgentToolPolicy(BaseModel):
    role: AgentRole
    allowed_read_tools: list[str] = Field(default_factory=list)
    allowed_write_tools: list[str] = Field(default_factory=list)
    may_execute_write_tools: bool = False
```

Default policy:

- All five roles have `may_execute_write_tools=False`.
- `allowed_write_tools` is empty for all five roles.
- Supervisor may reference no tools directly.
- Discovery may reference activity discovery and activity evidence read tools.
- Dining may reference dining discovery and dining evidence read tools.
- Itinerary Planner may reference no tools directly.
- Validator/Recovery may reference no tools directly in Task 020.

### Agent Result

```python
class AgentResult(BaseModel):
    role: AgentRole
    status: AgentStatus
    summary: str
    adapter_version: str
    tool_names_used: list[str] = Field(default_factory=list)
    output_json: dict[str, Any] = Field(default_factory=dict)
    error_json: dict[str, Any] | None = None
```

### Supervisor Assignment

```python
class SupervisorAssignment(BaseModel):
    assignment_id: str
    target_role: AgentRole
    objective: str
    required_inputs: list[str] = Field(default_factory=list)
    allowed_tool_names: list[str] = Field(default_factory=list)
```


class SupervisorAssignmentPlan(BaseModel):
    role: Literal["supervisor"] = "supervisor"
    assignments: list[SupervisorAssignment] = Field(default_factory=list)
    summary: str
```

### Recovery Decision

```python
class RecoveryDecision(BaseModel):
    verdict: Literal["passed", "failed"]
    error_type: str | None = None
    recovery_action: Literal[
        "none",
        "retry",
        "replace_candidate",
        "expand_search_radius",
        "ask_user",
        "stop_safely",
    ] = "none"
    route_to: str | None = None
    retry_budget: int = 0
    reason: str
```

### Workflow Result Addition

Add:

```python
agent_results: list[AgentResult] = Field(default_factory=list)
```

to `WeekendPilotWorkflowResult`.

Workflow state should also store `agent_results`.

## 6. Deterministic Adapter Behavior

### Supervisor

Input:

- workflow context
- parsed intent
- query plan

Output:

- assignments for `discovery`, `dining`, `itinerary_planner`, and `validator_recovery`
- no tool calls
- no write-tool references

### Discovery

Input:

- query plan
- candidate collection
- enrichment result

Output:

- count and names of activity candidates
- evidence status summary
- read tool names referenced from activity-related tool results
- no direct tool execution

### Dining

Input:

- query plan
- candidate collection
- enrichment result

Output:

- count and names of dining candidates
- queue/table evidence summary
- read tool names referenced from dining-related tool results
- no direct tool execution

### Itinerary Planner

Input:

- query plan
- enrichment result

Output:

- `ItineraryDraftResult`
- typed `AgentResult`
- adapter wraps `DeterministicItineraryGenerator`

### Validator/Recovery

Input:

- query plan
- enrichment result
- itinerary drafts
- pre-confirmation action count

Output:

- `FinalReviewResult`
- `RecoveryDecision`
- typed `AgentResult`

Rules:

- If final review is safe, recovery decision is `verdict="passed"`, `recovery_action="none"`, `retry_budget=0`.
- If final review is blocked, recovery decision is `verdict="failed"`, `recovery_action="stop_safely"`, `retry_budget=0`.
- Do not execute any recovery route in Task 020.

## 7. Workflow Integration

Modify `backend.app.workflow.nodes`:

- After `build_query_plan`, call Supervisor and store its `AgentResult`.
- After `enrich_candidates`, call Discovery and Dining and store their `AgentResult` values.
- In `generate_itinerary`, call the Itinerary Planner adapter instead of calling `DeterministicItineraryGenerator` directly.
- In `final_review`, call the Validator/Recovery adapter instead of calling `FinalReviewGate` directly.
- Persist sanitized agent summaries to `agent_runs.metadata_json["agents"]`.

Keep the Task 019 graph topology stable. Do not add parallel graph execution or new recovery branches in Task 020.

## 8. Sanitization and Metadata

Persist only sanitized summaries:

```json
{
  "version": "bounded_agents_v1",
  "results": [
    {
      "role": "supervisor",
      "status": "completed",
      "summary": "Created deterministic assignments.",
      "adapter_version": "deterministic_supervisor_v1",
      "tool_names_used": [],
      "output_json": {}
    }
  ]
}
```

Do not persist:

- secrets
- prompts
- raw traces
- raw provider payloads
- `tool_event_id`
- `action_id`

## 9. Acceptance Criteria

- [ ] `backend.app.agents` imports cleanly.
- [ ] All five bounded agent roles exist.
- [ ] Default policies forbid write-tool execution by every agent role.
- [ ] Deterministic adapters return typed `AgentResult` objects.
- [ ] Workflow result includes agent summaries for successful runs.
- [ ] Agent summaries are persisted in `agent_runs.metadata_json["agents"]`.
- [ ] `auto_confirm=False` still stops before execution and creates no Action Ledger rows.
- [ ] `auto_confirm=True` still completes through execution, feedback, and observability.
- [ ] Existing Task 019 workflow tests pass.
- [ ] Existing Task 018 benchmark tests pass.
- [ ] Default tests require no LLM credentials, LangSmith credentials, or live provider access.
- [ ] No secrets, prompts, raw traces, `tool_event_id`, or `action_id` are exposed in agent metadata.
- [ ] README documents focused agent-contract verification.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task20` branch created from `task19`.
- [ ] No `.env`, API key, token, or secret is tracked by git.

## 10. Verification Commands

```bash
git switch task19
git switch -c task20
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_agents.py -v
python -m pytest tests/integration/test_workflow_agents_gateway.py -v
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
python -m pytest
docker compose config
git diff --check
git status --short
```

## 11. Expected Commit

```text
feat: add bounded agent contracts
```

## 12. Notes for the Implementer

This task makes agents visible and enforceable, but deterministic. Do not add LLM-backed behavior yet. The main implementation risk is scope creep: keep graph topology, execution behavior, and benchmark behavior stable.
