# Plan: 016 Deterministic Feedback Writer

## 1. Spec Reference

Spec file:

```text
docs/specs/016-deterministic-feedback-writer.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Work starts from `task15`.
- Current Task 015 commit is `29af228 feat: add deterministic execution workflow`.
- `backend/app/execution` exists and exposes `ExecutionWorkflowResult`.
- `DeterministicExecutionWorkflow` writes execution metadata to `plans.plan_json["execution"]`.
- `PlanRepository` exposes `get_by_id` and `update_plan_json`.
- `AgentRunRepository` exposes `get_by_id` and `update_status`.
- No `backend/app/feedback` package exists yet.
- No feedback writer tests exist yet.
- No database migration is needed because feedback can be stored in existing JSONB fields and run status already exists.

## 3. Files to Add

- `backend/app/feedback/__init__.py` - exports feedback writer public API.
- `backend/app/feedback/errors.py` - `FeedbackWriterError`.
- `backend/app/feedback/schemas.py` - feedback result schemas.
- `backend/app/feedback/writer.py` - deterministic feedback writer service.
- `tests/test_feedback_writer.py` - unit tests for validation, status mapping, persistence, message safety, and transaction behavior.
- `tests/integration/test_feedback_writer_gateway.py` - full Mock World path through execution feedback.
- `docs/specs/016-deterministic-feedback-writer.md` - Task 016 spec.
- `docs/plans/016-deterministic-feedback-writer-plan.md` - Task 016 plan.

## 4. Files to Modify

- `README.md` - add focused feedback writer test command.
- No migrations unless existing schema is unexpectedly missing `plans.plan_json` or `agent_runs.status`.

## 5. Implementation Steps

1. Confirm branch and clean baseline.

```bash
git status --short --branch
git log --oneline -5
```

2. Create and switch to `task16` from `task15`.

```bash
git switch task15
git switch -c task16
```

3. Add `backend/app/feedback/errors.py`.

```python
class FeedbackWriterError(Exception):
    """Raised when deterministic execution feedback cannot be generated."""
```

4. Add `backend/app/feedback/schemas.py` with `FeedbackStatus`, `FeedbackActionStatus`, `FeedbackActionSummary`, and `ExecutionFeedbackResult` exactly as defined in the spec.

5. Add `backend/app/feedback/writer.py`.

Implementation requirements:

- Load plan with `PlanRepository.get_by_id`.
- Load run with `AgentRunRepository.get_by_id`.
- Validate `plan.run_id == run_id`.
- Validate `plan.selected is True`.
- Validate `plan.plan_json["schema_version"] == "reviewed_plan_v1"`.
- Validate `plan.plan_json["execution"]["schema_version"] == "execution_workflow_v1"`.
- Map execution status:
  - `succeeded` -> feedback `completed`, run `completed`
  - `partially_succeeded` -> feedback `partially_completed`, run `partially_completed`
  - `failed` -> feedback `failed`, run `failed`
  - `skipped` -> feedback `skipped`, run `skipped`
- Convert execution action statuses:
  - `succeeded` -> `completed`
  - `idempotent_replay` -> `already_completed`
  - `failed` -> `failed`
  - `blocked` -> `blocked`
  - `rate_limited` -> `rate_limited`
- Build target labels from draft activity/dining names when possible; fallback to `target_id`.
- Persist `plan_json["feedback"]`.
- Call `AgentRunRepository.update_status`.
- Flush through repositories only; do not commit.

6. Add `backend/app/feedback/__init__.py` exports.

```python
from backend.app.feedback.errors import FeedbackWriterError
from backend.app.feedback.schemas import ExecutionFeedbackResult, FeedbackActionStatus, FeedbackActionSummary, FeedbackStatus
from backend.app.feedback.writer import DeterministicFeedbackWriter
```

7. Add unit tests in `tests/test_feedback_writer.py`.

Required coverage:

- successful execution creates `completed` feedback and run status
- partial execution creates `partially_completed` feedback with completed and failed actions
- all failed execution creates `failed` feedback
- skipped execution creates `skipped` feedback and no action summaries
- missing plan, wrong run, missing run, unselected plan, malformed plan JSON, and missing execution raise `FeedbackWriterError`
- feedback message does not include `tool_event_id`, `action_id`, or raw UUID internals from execution actions
- writer overwrites existing feedback deterministically on rerun
- writer and repositories do not self-commit; rollback removes feedback/run status changes

8. Add integration test in `tests/integration/test_feedback_writer_gateway.py`.

Flow:

```text
create user/run
-> parse intent
-> build query plan
-> execute query-plan read calls
-> enrich candidates
-> generate itinerary drafts
-> final review
-> persist reviewed drafts
-> select plan
-> confirm plan
-> execute confirmed plan
-> write execution feedback
```

Assertions:

- feedback status is `completed`
- run status is `completed`
- `plans.plan_json["feedback"]["schema_version"] == "execution_feedback_v1"`
- feedback message mentions completed action count
- feedback does not expose internal `tool_event_id` or `action_id`
- no extra Action Ledger rows are created by feedback writer

9. Update `README.md` with:

````markdown
## Deterministic Feedback Writer

Focused feedback writer tests require PostgreSQL and Redis for the upstream gateway integration path:

```bash
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_feedback_writer.py tests/integration/test_feedback_writer_gateway.py -v
```
````

10. Run focused verification.

```bash
python -m pytest tests/test_feedback_writer.py -v
python -m pytest tests/integration/test_feedback_writer_gateway.py -v
```

11. Run full verification.

```bash
python -m pytest
docker compose config
git status --short
```

12. Inspect changes and secrets.

```bash
git status --short
git diff --check
```

13. Commit and push.

```bash
git add README.md backend/app/feedback tests/test_feedback_writer.py tests/integration/test_feedback_writer_gateway.py docs/specs/016-deterministic-feedback-writer.md docs/plans/016-deterministic-feedback-writer-plan.md
git commit -m "feat: add deterministic feedback writer"
git push origin task16
```

## 6. Testing Plan

- Unit tests:
  - validation errors
  - execution-to-feedback status mapping
  - action summary grouping
  - user-safe message generation
  - feedback persistence
  - run status update
  - no self-commit behavior
- Integration tests:
  - full Mock World planning/execution path through feedback
  - feedback writer creates no Tool Event or Action Ledger rows
- Smoke tests:
  - `python -m pytest`
  - `docker compose config`

## 7. Verification Commands

```bash
python -m pip install -e ".[dev]"
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/test_feedback_writer.py -v
python -m pytest tests/integration/test_feedback_writer_gateway.py -v
python -m pytest
docker compose config
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add deterministic feedback writer
```

Expected push target:

```text
origin/task16
```

## 9. Out-of-scope Changes

- Do not implement LangGraph.
- Do not add LangSmith tracing.
- Do not add benchmark harnesses or graders.
- Do not add API, CLI, or Web UI.
- Do not modify Tool Gateway or Execution Workflow behavior.
- Do not execute tools from the feedback writer.
- Do not write Action Ledger or Tool Event rows.
- Do not add memory learning or user preference updates.
- Do not commit `.env`, keys, tokens, secrets, caches, virtualenvs, or Docker volumes.

## 10. Review Checklist

- [ ] Implementation matches `docs/specs/016-deterministic-feedback-writer.md`.
- [ ] Feedback writer is deterministic and does not call LLMs.
- [ ] Feedback writer does not call tools or providers.
- [ ] Feedback payload is persisted in `plans.plan_json["feedback"]`.
- [ ] Run status is updated through `AgentRunRepository`.
- [ ] User-facing message does not expose internal IDs, prompts, traces, or secrets.
- [ ] Full Mock World integration path reaches feedback.
- [ ] No Action Ledger or Tool Event rows are created by feedback writer.
- [ ] Focused tests pass.
- [ ] Full `python -m pytest` passes.
- [ ] `docker compose config` passes.
- [ ] Commit message is `feat: add deterministic feedback writer`.
- [ ] Push to `origin/task16` succeeds.

## 11. Handoff Notes

The execution session should report back with:

- Changed files.
- Verification commands and results.
- Commit hash.
- Push result.
- Any deviations from this spec/plan.
- Whether Task 017 should move to LangGraph orchestration skeleton, LangSmith observability, LocalLife-Bench harness, or CLI demo based on current roadmap needs.
