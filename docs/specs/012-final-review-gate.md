# Spec: 012 Final Review Gate

## 1. Goal

Add a deterministic Final Review Gate for WeekendPilot itinerary drafts.

After Task 011, WeekendPilot can generate structured itinerary drafts with timeline, feasibility summary, evidence, and proposed actions. Task 012 should review those drafts before they are shown to the user, enforcing safety and consistency rules from the project blueprint.

The Final Review Gate is a deterministic review node, not an autonomous LLM agent. It must return structured review decisions and reasons so later workflow, CLI/Web demo, and benchmark harness code can decide whether a draft is safe to present, should be blocked, or needs recovery.

## 2. Project Context

This task follows the blueprint workflow:

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
```

Task 012 implements the deterministic rule-checking portion of `final_review`.

It supports these blueprint requirements:

- Final Review Gate is an审查节点, not a new autonomous Agent.
- It checks that a plan includes activity and dining.
- It checks that timeline coverage matches the requested 4-6 hour range or reports warnings.
- It checks that IDs in the final plan come from verified candidates.
- It checks that proposed actions reference objects in the selected draft.
- It checks that no write tool has executed before confirmation.
- It checks that user-facing draft payloads do not expose prompts, secrets, debug traces, or internal implementation details.

## 3. Requirements

- Add a deterministic Final Review Gate package under `backend.app.review`.
- Consume:
  - `QueryPlan`
  - `CandidateEnrichmentResult`
  - `ItineraryDraftResult`
  - `pre_confirmation_action_count: int = 0`
- Produce a structured `FinalReviewResult`.
- Review every draft in the `ItineraryDraftResult`.
- Return a top-level decision:
  - `approved`
  - `approved_with_warnings`
  - `blocked`
- Return per-draft review decisions.
- A draft must be blocked if:
  - it has no activity candidate
  - it has no dining candidate
  - its activity/dining IDs are not present in enrichment evidence
  - its route is missing
  - its route does not connect the draft activity to the draft dining candidate
  - its route is not present in enrichment route evidence
  - proposed actions do not require confirmation
  - proposed actions include durable execution fields such as `idempotency_key`, `confirmation_id`, or `action_id`
  - proposed actions reference targets outside the draft activity/dining/queue evidence
  - `pre_confirmation_action_count > 0`
  - sensitive/debug/internal fields are detected in the draft payload
- A draft should receive warnings, not blocking errors, when:
  - timeline duration is outside requested duration but still structurally valid
  - child-friendly intent is present but candidate evidence is weak or missing
  - light dining preference is present but dining evidence is weak or missing
  - route distance exceeds `max_distance_km`
  - proposed actions are empty
- The top-level result should be:
  - `blocked` if no drafts pass review or any global blocking check fails
  - `approved_with_warnings` if at least one draft passes but warnings exist
  - `approved` if at least one draft passes and no warnings/errors exist
- The gate must not call Tool Gateway.
- The gate must not call providers directly.
- The gate must not write PostgreSQL, Redis, or Action Ledger rows.
- The gate must not call LLMs or LangSmith.
- Add unit tests with constructed draft/enrichment inputs.
- Add an integration test running the existing Mock World read-only pipeline through Final Review Gate.
- README should include a focused final review test command.
- Do not commit `.env`, API keys, tokens, or secrets.

## 4. Non-goals

- Do not implement LangGraph.
- Do not implement Supervisor, Discovery, Dining, Itinerary Planner, or Validator agents.
- Do not call LLMs.
- Do not implement optional lightweight LLM reviewer.
- Do not implement user confirmation.
- Do not execute write tools.
- Do not write Action Ledger rows.
- Do not implement Execution Workflow.
- Do not persist plans into PostgreSQL.
- Do not add `PlanRepository`.
- Do not add database migrations.
- Do not add FastAPI endpoints.
- Do not add benchmark cases or graders.
- Do not implement recovery routing.

## 5. Interfaces and Contracts

### Inputs

- `QueryPlan`
- `CandidateEnrichmentResult`
- `ItineraryDraftResult`
- `pre_confirmation_action_count: int = 0`

### Outputs

- `FinalReviewResult`
- no Tool Gateway calls
- no PostgreSQL writes
- no Redis writes
- no Action Ledger writes

### Public Modules

Task 012 may add:

```text
backend.app.review.__init__
backend.app.review.schemas
backend.app.review.final_review_gate
```

### Public API

```python
class FinalReviewGate:
    gate_version = "final_review_gate_v1"

    def review(
        self,
        plan: QueryPlan,
        enrichment: CandidateEnrichmentResult,
        drafts: ItineraryDraftResult,
        pre_confirmation_action_count: int = 0,
    ) -> FinalReviewResult:
        ...
```

### FinalReviewResult Schema

Required fields:

```text
run_id: UUID
provider_profile: str
decision: "approved" | "approved_with_warnings" | "blocked"
safe_to_present: bool
reviewed_drafts: list[ReviewedDraft]
checks: list[ReviewCheck]
errors: list[ReviewCheck]
warnings: list[ReviewCheck]
gate_version: str
```

### ReviewedDraft Schema

Required fields:

```text
draft_id: str
decision: "approved" | "approved_with_warnings" | "blocked"
safe_to_present: bool
checks: list[ReviewCheck]
errors: list[ReviewCheck]
warnings: list[ReviewCheck]
```

### ReviewCheck Schema

Required fields:

```text
check_name: str
status: "passed" | "warning" | "failed"
severity: "info" | "warning" | "error"
message: str
draft_id: str | None
details: dict
```

### Required Check Names

The implementation should use stable check names:

```text
run_id_consistency
pre_confirmation_no_actions
draft_exists
activity_present
dining_present
candidate_ids_verified
route_present
route_verified
timeline_duration
child_friendly_constraint
dining_preference_constraint
distance_constraint
actions_require_confirmation
actions_reference_draft_objects
actions_have_no_execution_fields
sensitive_payload_scan
```

## 6. Observability

Task 012 does not write new durable observability records.

The result must preserve enough structured review data for later logging or benchmark scoring:

- `gate_version`
- top-level decision
- per-draft decision
- stable check names
- check severity and status
- details for failed/warning checks

No LangSmith tracing is added in this task.

## 7. Failure Handling

- If `drafts.drafts` is empty, return `blocked` with `draft_exists` failed.
- If `plan`, `enrichment`, and `drafts` have inconsistent `run_id` or provider profile values, return `blocked`.
- If `pre_confirmation_action_count > 0`, return `blocked`.
- If some drafts fail but at least one draft passes, the result may still be `approved_with_warnings`.
- Malformed optional evidence should produce warnings unless it makes candidate/action/route verification impossible.
- Sensitive key detection should scan draft JSON recursively for keys containing:
  - `api_key`
  - `apikey`
  - `token`
  - `secret`
  - `password`
  - `prompt`
  - `trace`
  - `debug`
- The gate must never execute tools or write durable state.

## 8. Acceptance Criteria

- [ ] `FinalReviewGate` exists and is importable.
- [ ] Final review schemas are typed and importable.
- [ ] Gate consumes `QueryPlan`, `CandidateEnrichmentResult`, and `ItineraryDraftResult`.
- [ ] Gate returns top-level and per-draft structured decisions.
- [ ] Valid Mock World MVP draft is approved or approved with warnings.
- [ ] Draft without activity is blocked.
- [ ] Draft without dining is blocked.
- [ ] Draft with unverified candidate IDs is blocked.
- [ ] Draft with missing or mismatched route is blocked.
- [ ] Draft actions without confirmation are blocked.
- [ ] Draft actions with execution/idempotency fields are blocked.
- [ ] Draft actions targeting unknown objects are blocked.
- [ ] Nonzero pre-confirmation action count blocks the result.
- [ ] Sensitive/debug/internal payload keys are blocked.
- [ ] Timeline/constraint mismatches produce warnings where appropriate.
- [ ] Integration test runs parser -> planner -> executor -> enricher -> itinerary generator -> final review with Mock World.
- [ ] Integration test confirms no Action Ledger rows are created.
- [ ] Integration test confirms Tool Event count does not increase during final review.
- [ ] `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Work happens on `task12` branch created from `task11`.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
git switch task11
git switch -c task12
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_final_review_gate.py -v
python -m pytest tests/integration/test_final_review_gate_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 10. Expected Commit

```text
feat: add final review gate
```

## 11. Notes for the Implementer

If Task 011 files are missing, stop and report the branch/base mismatch.

Keep Task 012 focused on deterministic review. Do not add persistence, LangGraph, agents, user confirmation, execution, benchmark graders, or API endpoints in this task.
