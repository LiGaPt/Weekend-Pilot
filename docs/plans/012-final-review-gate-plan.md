# Plan: 012 Final Review Gate

## 1. Spec Reference

Spec file:

```text
docs/specs/012-final-review-gate.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task11`.
- Current Task 011 commit is `ee6d6c6 feat: add deterministic itinerary draft generation`.
- `backend/app/planning/itinerary_drafts.py` defines itinerary draft schemas.
- `backend/app/planning/itinerary_generation.py` defines `DeterministicItineraryGenerator`.
- `backend/app/planning/enriched_candidates.py` defines candidate enrichment result schemas.
- `backend/app/planning/enrichment.py` defines `CandidateEnricher`.
- No `backend/app/review` package exists yet.
- No `PlanRepository` exists and this task must not add one.

## 3. Files to Add

- `backend/app/review/__init__.py` - exports final review public API.
- `backend/app/review/schemas.py` - Pydantic schemas for final review results and checks.
- `backend/app/review/final_review_gate.py` - deterministic `FinalReviewGate`.
- `tests/test_final_review_gate.py` - unit tests with constructed drafts/enrichment.
- `tests/integration/test_final_review_gate_gateway.py` - Mock World full read/draft/review integration test.
- `docs/specs/012-final-review-gate.md` - Task 012 spec.
- `docs/plans/012-final-review-gate-plan.md` - Task 012 plan.

## 4. Files to Modify

- `README.md` - add focused final review test command.

No dependency, Docker Compose, Alembic, database model, repository, Tool Gateway, provider, Redis, planning generator, or API endpoint changes are expected.

## 5. Implementation Steps

1. Create branch:

```bash
git switch task11
git switch -c task12
```

2. Confirm baseline:

```bash
git status --short --branch
rg --files backend/app/planning backend/app/tool_gateway backend/app/providers tests docs/specs docs/plans
```

Expected:

- Branch is `task12`.
- Task 011 files exist.
- `backend/app/review` does not exist yet.
- Working tree is clean before implementation.

3. Add `backend/app/review/schemas.py`.

Create these Pydantic models:

```python
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReviewDecision = Literal["approved", "approved_with_warnings", "blocked"]
ReviewStatus = Literal["passed", "warning", "failed"]
ReviewSeverity = Literal["info", "warning", "error"]


class ReviewCheck(BaseModel):
    check_name: str
    status: ReviewStatus
    severity: ReviewSeverity
    message: str
    draft_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ReviewedDraft(BaseModel):
    draft_id: str
    decision: ReviewDecision
    safe_to_present: bool
    checks: list[ReviewCheck] = Field(default_factory=list)
    errors: list[ReviewCheck] = Field(default_factory=list)
    warnings: list[ReviewCheck] = Field(default_factory=list)


class FinalReviewResult(BaseModel):
    run_id: UUID
    provider_profile: str
    decision: ReviewDecision
    safe_to_present: bool
    reviewed_drafts: list[ReviewedDraft] = Field(default_factory=list)
    checks: list[ReviewCheck] = Field(default_factory=list)
    errors: list[ReviewCheck] = Field(default_factory=list)
    warnings: list[ReviewCheck] = Field(default_factory=list)
    gate_version: str
```

4. Add `backend/app/review/final_review_gate.py`.

Implement:

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

The class must not import or instantiate:

- `ToolGateway`
- providers
- SQLAlchemy repositories
- Redis clients
- LangSmith clients
- LLM clients

5. Implement top-level result construction.

Rules:

- Use `drafts.run_id` and `drafts.provider_profile` for the result.
- Run global checks first.
- Review each draft independently.
- Top-level decision:
  - `blocked` if any global error exists or no reviewed draft is safe to present
  - `approved_with_warnings` if at least one draft is safe but any warnings exist
  - `approved` if at least one draft is safe and no warnings/errors exist
- `safe_to_present=True` only when top-level decision is not `blocked`.

6. Implement helper methods for checks.

Use stable check helpers:

```python
_pass(check_name, message, draft_id=None, details=None)
_warn(check_name, message, draft_id=None, details=None)
_fail(check_name, message, draft_id=None, details=None)
```

Each returns `ReviewCheck`.

7. Implement global checks.

Global checks:

- `run_id_consistency`
  - pass if `enrichment.run_id == drafts.run_id`
  - fail otherwise
- provider consistency
  - include inside `run_id_consistency` details or separate details field
  - fail if `enrichment.provider_profile != drafts.provider_profile`
- `pre_confirmation_no_actions`
  - pass when `pre_confirmation_action_count == 0`
  - fail when greater than zero
- `draft_exists`
  - pass when at least one draft exists
  - fail when `drafts.drafts` is empty

8. Build enrichment evidence indexes.

Before per-draft review:

```python
activity_ids = {item.candidate.candidate_id for item in enrichment.enriched_activity_candidates}
dining_ids = {item.candidate.candidate_id for item in enrichment.enriched_dining_candidates}
route_keys = {
    (entry.origin_candidate_id, entry.destination_candidate_id)
    for entry in enrichment.route_matrix
    if entry.status in {"succeeded", "cached"}
}
queue_ids_by_dining_id = {
    dining.candidate.candidate_id: dining.queue.get("queue_id")
    for dining in enrichment.enriched_dining_candidates
    if isinstance(dining.queue, dict)
}
```

Also preserve candidate tags/evidence for child-friendly and dining preference checks.

9. Implement per-draft checks.

For each draft, run these checks:

- `activity_present`
  - fail if `draft.activity` is missing or candidate ID empty
- `dining_present`
  - fail if `draft.dining` is missing or candidate ID empty
- `candidate_ids_verified`
  - fail if activity ID not in `activity_ids` or dining ID not in `dining_ids`
- `route_present`
  - fail if `draft.route is None`
- `route_verified`
  - fail if route origin/destination do not match draft activity/dining
  - fail if `(origin, destination)` not in usable `route_keys`
- `timeline_duration`
  - pass when total duration fits requested duration or default MVP range
  - warn when outside range but timeline exists
  - fail only when timeline is empty or contains non-positive durations
- `child_friendly_constraint`
  - if `plan.intent.constraints.child_friendly` is false, pass
  - if true, pass when activity and dining tags/evidence include `child_friendly`
  - warn when evidence is missing or weak
- `dining_preference_constraint`
  - if no light dining preference, pass
  - if `lighter_options` requested, pass when dining tags/evidence include `lighter_options`
  - warn when evidence is missing or weak
- `distance_constraint`
  - if no `max_distance_km` or no route distance, pass with info
  - warn when route distance exceeds max distance
- `actions_require_confirmation`
  - fail if any proposed action has `requires_confirmation is not True`
- `actions_reference_draft_objects`
  - fail if proposed action targets do not correspond to draft activity/dining/queue evidence
- `actions_have_no_execution_fields`
  - fail if action payload contains `idempotency_key`, `confirmation_id`, or `action_id`
- `sensitive_payload_scan`
  - fail if draft serialized payload contains sensitive/debug/internal key names

10. Implement timeline duration rule.

Use:

- requested min/max from `plan.intent.time_window.duration_hours_min/max` when both exist
- otherwise MVP default:
  - min 240 minutes
  - max 360 minutes

Calculate:

```python
total_duration = sum(item.duration_minutes for item in draft.timeline)
```

Rules:

- fail if timeline is empty
- fail if any required activity, transfer, or dining item duration is `<= 0`
- fail if any optional buffer item duration is `< 0`; zero-minute buffer items are allowed
- pass if within min/max
- warning if outside min/max

11. Implement action target validation.

Rules:

- `book_ticket` target must equal `draft.activity.candidate_id`
- `reserve_restaurant` target must equal `draft.dining.candidate_id`
- `join_queue` target must equal:
  - queue ID from dining evidence, or
  - `draft.dining.candidate_id`
- unknown action types should fail `actions_reference_draft_objects`
- empty `proposed_actions` should warn, not fail

12. Implement sensitive payload scan.

Recursively scan `draft.model_dump(mode="json")`.

Fail when any dictionary key contains one of these case-insensitive fragments:

```text
api_key
apikey
token
secret
password
prompt
trace
debug
```

Do not scan values for arbitrary string matches in Task 012; key scanning is sufficient and avoids false positives.

13. Implement per-draft decision.

For each reviewed draft:

- `blocked` if any per-draft error exists
- `approved_with_warnings` if no errors but warnings exist
- `approved` if no errors and no warnings
- `safe_to_present=True` if decision is `approved` or `approved_with_warnings`

14. Add `backend/app/review/__init__.py`.

Export:

```python
FinalReviewGate
FinalReviewResult
ReviewCheck
ReviewDecision
ReviewedDraft
```

15. Add unit tests in `tests/test_final_review_gate.py`.

Use constructed `QueryPlan`, `CandidateEnrichmentResult`, and `ItineraryDraftResult` objects.

Cover:

- valid draft is approved
- valid draft with non-blocking timeline warning is `approved_with_warnings`
- empty drafts result is blocked with `draft_exists`
- missing activity blocks the draft
- missing dining blocks the draft
- unverified candidate ID blocks the draft
- missing route blocks the draft
- mismatched route blocks the draft
- route not present in enrichment evidence blocks the draft
- action with `requires_confirmation=False` blocks
- action with `idempotency_key` blocks
- action with unknown target blocks
- nonzero `pre_confirmation_action_count` blocks globally
- sensitive key in draft payload blocks
- child-friendly and light-dining evidence gaps warn
- distance over max constraint warns
- one bad draft plus one good draft still allows top-level `approved_with_warnings`

16. Add integration test in `tests/integration/test_final_review_gate_gateway.py`.

Use the setup style from `tests/integration/test_itinerary_generation_gateway.py`:

- `SessionLocal`
- `UserRepository`
- `AgentRunRepository`
- `ToolEventRepository`
- `ActionLedgerRepository`
- `JsonRedisCache`
- `FixedWindowRateLimiter`
- `RedisKeyBuilder`
- `build_mock_world_registry`
- `ToolGateway`
- `DeterministicIntentParser`
- `DeterministicQueryPlanner`
- `QueryPlanExecutor`
- `CandidateEnricher`
- `DeterministicItineraryGenerator`
- `FinalReviewGate`

Scenario:

1. Create an `AgentRun`.
2. Parse the MVP family request.
3. Build Mock World query plan.
4. Execute initial tool calls.
5. Enrich candidates.
6. Generate itinerary drafts.
7. Count Action Ledger rows before review.
8. Count Tool Event rows before review.
9. Review drafts with `pre_confirmation_action_count=action_ledger_count`.
10. Assert:
    - result decision is `approved` or `approved_with_warnings`
    - `safe_to_present is True`
    - at least one reviewed draft is safe to present
    - no reviewed draft marked safe has errors
    - Tool Event count does not increase during final review
    - Action Ledger count remains zero

17. Update README.

Add focused final review command:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_final_review_gate.py tests/integration/test_final_review_gate_gateway.py -v
```

Do not claim LangGraph, persistence, user confirmation, or execution exists.

18. Run focused unit tests:

```bash
python -m pytest tests/test_final_review_gate.py -v
```

19. Run focused integration test:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_final_review_gate_gateway.py -v
```

20. Run full verification:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest
docker compose config
git status --short
```

21. Inspect tracked files and secrets:

```bash
git status --short
git ls-files
```

Confirm `.env`, API keys, tokens, secrets, virtualenvs, caches, logs, Docker volumes, and generated artifacts are not tracked.

## 6. Testing Plan

- Unit tests:
  - global review checks
  - per-draft structural checks
  - candidate and route evidence verification
  - timeline duration warnings/failures
  - child-friendly, dining preference, and distance warnings
  - proposed action confirmation and target validation
  - execution field rejection
  - sensitive key scan
  - mixed good/bad draft aggregation
- Integration tests:
  - parser -> query planner -> query executor -> candidate enricher -> itinerary generator -> final review
  - real PostgreSQL and Redis for upstream gateway path
  - no Action Ledger rows
  - Tool Event count unchanged during final review
- Smoke:
  - full `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_final_review_gate.py -v
python -m pytest tests/integration/test_final_review_gate_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add final review gate
```

Expected branch:

```text
task12
```

Expected commands:

```bash
git switch task11
git switch -c task12
git status --short
git add README.md backend/app/review tests/test_final_review_gate.py tests/integration/test_final_review_gate_gateway.py docs/specs/012-final-review-gate.md docs/plans/012-final-review-gate-plan.md
git status --short
git commit -m "feat: add final review gate"
git push -u origin task12
```

The implementer must confirm `.env` and secrets are not staged.

## 9. Out-of-scope Changes

- Do not implement LangGraph.
- Do not implement agents, prompts, or LLM calls.
- Do not implement optional LLM reviewer.
- Do not implement user confirmation.
- Do not execute write tools.
- Do not create Action Ledger rows.
- Do not persist into `plans`.
- Do not add `PlanRepository`.
- Do not add API endpoints.
- Do not add migrations.
- Do not add dependencies.
- Do not add benchmark harness or graders.
- Do not implement recovery routing.
- Do not commit `.env`, API keys, tokens, or secrets.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] Work is on `task12`.
- [ ] Spec and plan are saved in expected docs paths.
- [ ] `FinalReviewGate` is deterministic and importable.
- [ ] Gate consumes Task 011 draft result and Task 010 enrichment result.
- [ ] Gate does not call Tool Gateway/providers/DB/Redis/LangSmith/LLMs.
- [ ] Valid Mock World draft is safe to present.
- [ ] Invalid draft structures are blocked.
- [ ] Proposed actions require confirmation and contain no execution fields.
- [ ] Candidate and route IDs are verified against enrichment evidence.
- [ ] Pre-confirmation action count blocks when nonzero.
- [ ] Sensitive/debug/internal keys are blocked.
- [ ] Integration test proves Tool Event count unchanged during review.
- [ ] Integration test proves Action Ledger remains empty.
- [ ] `python -m pytest` passed.
- [ ] `docker compose config` passed.
- [ ] Commit message is `feat: add final review gate`.
- [ ] Push to `origin/task12` succeeds.

## 11. Handoff Notes

Execution session should report:

- Changed files.
- Focused final review unit test result.
- Focused integration test result.
- Full pytest result.
- Docker Compose result.
- Commit hash.
- Push branch.
- Any deviation from spec/plan.

## 12. Assumptions

- Task 012 starts from `task11`.
- Final Review Gate is deterministic rule checking only.
- Mock World remains the required deterministic integration provider.
- Plan persistence, user confirmation, execution, LangGraph, agents, recovery routing, and benchmark graders are follow-up tasks.
