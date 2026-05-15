# Plan: 020 Bounded Agent Contracts and Deterministic Adapters

## 1. Spec Reference

Spec file:

```text
docs/specs/020-bounded-agent-contracts.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task19`.
- Current Task 019 commit is `6b7ca64 feat: add langgraph workflow skeleton`.
- `backend.app.workflow` exists and exposes `WeekendPilotWorkflowRunner`.
- Task 019 workflow supports `auto_confirm=False` and `auto_confirm=True`.
- Task 019 graph topology is stable and should not be changed in Task 020.
- There is no `backend.app.agents` package yet.
- Task 020 should not add LLM calls or prompt templates.

## 3. Files to Add

- `backend/app/agents/__init__.py` - public exports.
- `backend/app/agents/errors.py` - agent contract and policy errors.
- `backend/app/agents/schemas.py` - role, policy, result, assignment, and recovery schemas.
- `backend/app/agents/policies.py` - default role policies and validation helpers.
- `backend/app/agents/deterministic.py` - deterministic agent adapters.
- `tests/test_agents.py` - unit tests for schemas, policies, adapters, and sanitization.
- `tests/integration/test_workflow_agents_gateway.py` - workflow integration tests with agent metadata.
- `docs/specs/020-bounded-agent-contracts.md` - Task 020 spec.
- `docs/plans/020-bounded-agent-contracts-plan.md` - Task 020 plan.

## 4. Files to Modify

- `backend/app/workflow/schemas.py` - add `agent_results` to state and result schemas.
- `backend/app/workflow/nodes.py` - call deterministic agent adapters and persist sanitized metadata.
- `backend/app/workflow/runner.py` - copy `agent_results` from final state to public result.
- `backend/app/workflow/__init__.py` - export agent-aware workflow result types only if needed.
- `README.md` - document focused bounded-agent verification commands.

Do not modify `pyproject.toml`; no new dependency is needed.

## 5. Implementation Steps

1. Confirm clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create `task20` from `task19`.

```bash
git switch task19
git switch -c task20
```

3. Add `backend/app/agents/errors.py`.

Define:

```python
class AgentContractError(RuntimeError):
    """Raised when deterministic agent contract inputs are invalid."""


class AgentPolicyError(RuntimeError):
    """Raised when an agent attempts to violate its bounded tool policy."""
```

4. Add schemas in `backend/app/agents/schemas.py`.

Include:

- `AgentRole`
- `AgentStatus`
- `AgentInvocationContext`
- `AgentToolPolicy`
- `AgentResult`
- `SupervisorAssignment`
- `SupervisorAssignmentPlan`
- `RecoveryDecision`

Use Pydantic models. Keep `output_json` structured and sanitized.

5. Add policies in `backend/app/agents/policies.py`.

Implement:

```python
def default_agent_policy(role: AgentRole) -> AgentToolPolicy:
    ...


def default_agent_policies() -> dict[AgentRole, AgentToolPolicy]:
    ...


def validate_agent_tool_usage(role: AgentRole, tool_names: list[str]) -> None:
    ...
```

Rules:

- Every role has `may_execute_write_tools=False`.
- Every role has `allowed_write_tools=[]`.
- Any tool name in `WRITE_TOOLS` raises `AgentPolicyError`.
- Unknown tools raise `AgentPolicyError`.
- Empty tool lists are valid.

Recommended read-tool references:

- `supervisor`: none
- `discovery`: `search_poi`, `get_poi_detail`, `check_opening_hours`, `check_queue`, `check_ticket_availability`, `check_route`
- `dining`: `search_poi`, `get_poi_detail`, `check_opening_hours`, `check_queue`, `check_table_availability`, `check_route`
- `itinerary_planner`: none
- `validator_recovery`: none

6. Add deterministic adapters in `backend/app/agents/deterministic.py`.

Create classes:

- `DeterministicSupervisorAgent`
- `DeterministicDiscoveryAgent`
- `DeterministicDiningAgent`
- `DeterministicItineraryPlannerAgent`
- `DeterministicValidatorRecoveryAgent`

Each class should expose a single method with typed inputs and return `AgentResult`. Itinerary Planner should also return `ItineraryDraftResult`; Validator/Recovery should also return `FinalReviewResult` and `RecoveryDecision`.

Use adapter version strings:

- `deterministic_supervisor_v1`
- `deterministic_discovery_v1`
- `deterministic_dining_v1`
- `deterministic_itinerary_planner_v1`
- `deterministic_validator_recovery_v1`

7. Implement metadata sanitizer in `deterministic.py` or a small helper inside `agents`.

Sanitize recursive dict/list values. Remove or redact keys containing:

```text
api_key
token
secret
password
authorization
prompt
debug_trace
tool_event_id
action_id
```

This helper should be unit-tested. If Task 017 redaction helper is convenient and safe, reuse it and add the extra ID key filtering here.

8. Modify workflow schemas.

In `WeekendPilotWorkflowResult`, add:

```python
agent_results: list[AgentResult] = Field(default_factory=list)
```

In `WeekendPilotWorkflowState`, add:

```python
agent_results: list[Any]
supervisor_assignment_plan: Any
recovery_decision: Any
```

Use `Any` in state if importing concrete agent schemas would create awkward import cycles. Public result should use typed `AgentResult`.

9. Modify workflow runner initial and final state.

Initial state should include:

```python
agent_results=[]
```

`_to_result()` should copy typed or dict agent results into `WeekendPilotWorkflowResult.agent_results`.

10. Modify workflow nodes to instantiate adapters.

In `WeekendPilotWorkflowNodes.__init__`, create deterministic agent instances as attributes. Do not create LLM clients.

11. Modify `build_query_plan` node.

After building the query plan:

- build `AgentInvocationContext` for `supervisor`
- call `DeterministicSupervisorAgent`
- append result to `agent_results`
- store `supervisor_assignment_plan`

12. Modify `enrich_candidates` node.

After enrichment:

- call Discovery adapter
- call Dining adapter
- append both results

Do not execute additional tools. These adapters only summarize existing collection/enrichment outputs.

13. Modify `generate_itinerary` node.

Replace direct `DeterministicItineraryGenerator().generate(...)` call with `DeterministicItineraryPlannerAgent`.

The returned `ItineraryDraftResult` must remain identical in behavior to the previous deterministic generator path.

14. Modify `final_review` node.

Replace direct `FinalReviewGate().review(...)` call with `DeterministicValidatorRecoveryAgent`.

Store:

- `final_review_result`
- `recovery_decision`
- validator agent result

Do not route or retry based on recovery decision in Task 020.

15. Persist agent metadata.

Add helper in workflow nodes:

```python
def _persist_agent_metadata(self, run_id: UUID, agent_results: list[AgentResult]) -> None:
    ...
```

Behavior:

- Load current run metadata.
- Preserve existing `workflow` and `observability` keys.
- Add or replace `metadata_json["agents"]`.
- Use sanitized agent result payloads.
- Flush through `AgentRunRepository.update_metadata_json`.
- Do not commit.

Call this helper after each agent-producing node or at least before every terminal workflow result. Recommended: persist after `final_review`, `wait_confirmation`, and `record_observability` to cover both paused and completed paths.

16. Add exports in `backend/app/agents/__init__.py`.

Export:

- schemas
- deterministic adapter classes
- policy helpers
- errors

17. Add unit tests in `tests/test_agents.py`.

Required tests:

- all five roles exist
- every default policy forbids write tools
- `validate_agent_tool_usage` rejects each `WRITE_TOOLS` value
- supervisor returns assignments for discovery, dining, itinerary planner, and validator/recovery
- discovery summary includes activity count and not dining count as its primary category
- dining summary includes dining count and not activity count as its primary category
- itinerary planner adapter returns an `AgentResult` and an `ItineraryDraftResult`
- validator/recovery returns `RecoveryDecision(verdict="passed")` for safe review
- sanitizer removes sensitive keys and raw IDs

18. Add integration tests in `tests/integration/test_workflow_agents_gateway.py`.

Reuse the Task 019 workflow integration fixture shape:

- `SessionLocal`
- Redis runtime with unique prefix
- trace path under `var/test-traces`

Test `auto_confirm=False`:

```text
runner.run(request auto_confirm=False)
-> status == "awaiting_confirmation"
-> agent_results include supervisor, discovery, dining, itinerary_planner, validator_recovery
-> run metadata has agents.version == "bounded_agents_v1"
-> no ActionLedger rows
-> metadata has no action_id/tool_event_id/debug_trace
```

Test `auto_confirm=True`:

```text
runner.run(request auto_confirm=True)
-> status == "completed"
-> all five agent roles exist in result
-> run metadata has sanitized agents results
-> execution_status == "succeeded"
-> feedback_status == "completed"
-> trace propagation still works
```

19. Keep existing workflow tests passing.

If `WeekendPilotWorkflowResult` equality or serialization changes, update tests only with additive assertions. Do not weaken confirmation-boundary assertions.

20. Update README.

Add:

````markdown
## Bounded Agent Contracts

Task 020 adds deterministic bounded-agent adapters for Supervisor, Discovery, Dining, Itinerary Planner, and Validator/Recovery. These adapters do not call LLMs and do not execute write tools.

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_agents.py tests/integration/test_workflow_agents_gateway.py -v
```
````

21. Run focused verification.

```bash
python -m pytest tests/test_agents.py -v
python -m pytest tests/integration/test_workflow_agents_gateway.py -v
```

22. Run workflow and benchmark regression verification.

```bash
python -m pytest tests/test_langgraph_workflow.py tests/integration/test_langgraph_workflow_gateway.py -v
python -m pytest tests/test_benchmark_harness.py tests/integration/test_benchmark_harness_gateway.py -v
```

23. Run full verification.

```bash
python -m pytest
docker compose config
git diff --check
git status --short
```

24. Commit and push.

```bash
git add README.md backend/app/agents backend/app/workflow tests/test_agents.py tests/integration/test_workflow_agents_gateway.py docs/specs/020-bounded-agent-contracts.md docs/plans/020-bounded-agent-contracts-plan.md
git commit -m "feat: add bounded agent contracts"
git push origin task20
```

## 6. Follow-up Task Order

After Task 020:

1. Task 021: refactor LocalLife-Bench harness to call the official workflow.
2. Task 022: CLI demo runner.
3. Task 023: recovery routing v0.
4. Task 024: LocalLife-Bench case expansion.
5. Task 025: first LLM-backed bounded agent behind the existing contracts.

Do not pull these follow-up scopes into Task 020.
