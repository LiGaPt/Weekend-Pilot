# Plan: 097 Sensitive memory + feedback candidate v0

## 1. Spec Reference

Spec file:

```text
docs/specs/097-sensitive-memory-feedback-candidate-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/096-memory-lifecycle-v1`.
- Latest commit is `881e6f4 feat: add memory lifecycle states`, which matches Task `096`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `096`.
- The current repository already supports memory lifecycle states `active`, `expired`, `disabled`, `ignored`, and `candidate`.
- `list_governable_for_user(...)` already excludes `candidate`, so feedback-created candidate memory will not affect current planning in the same code path.
- `DeterministicFeedbackWriter` currently persists only execution feedback into `plan_json["feedback"]`.
- `memory_items` has a unique constraint on `(user_id, memory_type, key)`, so naive repeated inserts are not safe.
- There are unrelated untracked local docs in the working tree:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- No spec/plan continuity break or higher-priority repair task currently blocks continuing the memory-governance sequence.

## 3. Files to Add

- `backend/app/feedback/memory_candidates.py` - deterministic extraction and normalization of feedback-derived candidate memories plus safe candidate-summary building.
- `tests/test_feedback_memory_candidates.py` - focused unit coverage for allowed inputs, disallowed sources, normalization priority, and minimization rules.

## 4. Files to Modify

- `backend/app/feedback/schemas.py` - add the additive safe summary model and attach it to `ExecutionFeedbackResult`.
- `backend/app/feedback/writer.py` - generate candidate memories after building feedback, persist create/update/skip behavior, and store safe summary in feedback payload.
- `backend/app/repositories/memory.py` - add lookup/update helpers needed for same-key candidate upsert without overwriting non-candidate rows.
- `tests/test_feedback_writer.py` - cover candidate creation, candidate update, non-overwrite of governable memory, and persisted feedback summary.
- `tests/integration/test_feedback_writer_gateway.py` - verify mock-world execution plus feedback writes candidate memories with minimized payloads.
- `tests/integration/test_langgraph_workflow_gateway.py` - verify workflow auto-confirm path still completes and leaves candidate memories outside governable read semantics.

## 5. Implementation Steps

1. Read the spec, current feedback writer, current memory repository, Task `096` lifecycle helper, and current feedback tests together before editing.
2. Add one new feedback-candidate helper module in `backend/app/feedback/memory_candidates.py`.
3. In that module, define one internal candidate-draft contract with exact fields needed for persistence:
   - `memory_type`
   - `key`
   - `value_json`
   - `text`
   - `confidence`
   - `status`
   - `expires_at`
4. Keep the helper deterministic and tag-based only.
5. Implement activity candidate extraction so it reads only `draft.activity.tags`.
6. Map activity tags with strict priority:
   - `citywalk`
   - `indoor`
   - `outdoor`
7. Implement dining candidate extraction so it reads only `draft.dining.tags`.
8. Emit dining candidate only when the selected dining tags contain `lighter_options`.
9. Do not read candidate values from:
   - title
   - summary
   - timeline notes
   - address
   - location
   - message
   - message preview
   - final arrangement message
   - next steps
   - execution payloads
   - response/error JSON
10. Hardcode candidate memory defaults in the helper:
    - `memory_type = "preference"`
    - `text = None`
    - `confidence = Decimal("0.6000")`
    - `status = "candidate"`
    - `expires_at = None`
11. Build `value_json` with exactly:
    - `preference`
    - `source = "feedback_writer_v0"`
    - `evidence = "selected_candidate_tags"`
12. Do not put run IDs, memory IDs, action IDs, tool event IDs, addresses, phone numbers, or free-form text into `value_json`.
13. In `backend/app/feedback/schemas.py`, add:
    - `FeedbackMemoryCandidateGenerationStatus = Literal["completed", "degraded", "not_applicable"]`
    - `FeedbackMemoryCandidateSummary`
14. Add one additive field to `ExecutionFeedbackResult`:
    - `memory_candidate_summary: FeedbackMemoryCandidateSummary | None = None`
15. In `backend/app/repositories/memory.py`, add a deterministic lookup helper for one user/key pair.
16. Name it explicitly, for example:
    - `get_by_user_memory_key(user_id, memory_type, key)`
17. Add one repository update helper for existing rows so the feedback writer does not need to mutate ORM fields ad hoc.
18. The update helper must allow refreshing:
    - `value_json`
    - `text`
    - `confidence`
    - `source_run_id`
    - `source_langsmith_trace_id`
    - `expires_at`
    - `status`
19. Do not add a generic broad “update everything” API. Keep the helper narrow to memory rows used here.
20. Update `DeterministicFeedbackWriter` to load the actual run object, not just existence, because candidate writes need `user_id`.
21. Keep all existing feedback headline/message/final-arrangement logic unchanged first.
22. After the `ExecutionFeedbackResult` core payload is assembled, invoke the new candidate helper on the selected reviewed plan JSON.
23. If the helper returns no supported candidates, set `memory_candidate_summary.generation_status = "not_applicable"`.
24. For each extracted candidate draft:
    - look up an existing row by `(user_id, memory_type, key)`
    - if no row exists, create a new `candidate`
    - if an existing row exists with `status == "candidate"`, update it in place
    - if an existing row exists with `status != "candidate"`, skip it
25. Do not overwrite existing `active`, `expired`, `ignored`, or `disabled` rows.
26. When updating an existing `candidate`, keep the same `memory_id`; only refresh the approved fields.
27. For feedback-generated candidate writes, set:
    - `source_run_id = current run_id`
    - `source_langsmith_trace_id = None`
28. Build the safe summary while writing:
    - `created_keys`
    - `updated_keys`
    - `skipped_keys`
29. Set summary `generation_status` rules exactly:
    - `not_applicable` when no supported candidate signals exist
    - `completed` when extraction ran and no unexpected candidate-write exception occurred
    - `degraded` when extraction found candidates but one or more unexpected per-key exceptions had to be skipped
30. Treat “existing non-candidate row” as a normal skip, not a degraded error.
31. Persist `memory_candidate_summary` into:
    - returned `ExecutionFeedbackResult`
    - persisted `plan_json["feedback"]["memory_candidate_summary"]`
32. Keep the persisted summary safe:
    - key names only
    - no IDs
    - no raw text
    - no addresses
    - no phone-like strings
33. In `tests/test_feedback_memory_candidates.py`, write focused unit tests for the helper before wiring all writer paths if practical.
34. Cover exact extraction cases:
    - `citywalk` beats `outdoor`
    - `indoor` emits `activity_style = "indoor"`
    - `lighter_options` emits `spouse_lighter_meals = "lighter_options"`
    - unsupported/no tags emit no candidate
35. Add one minimization test where the reviewed-plan payload contains:
    - address-like strings
    - phone-like strings
    - token/secret-like fields
    Assert the helper does not read them and does not emit them into `value_json` or `text`.
36. In `tests/test_feedback_writer.py`, extend the existing executed-plan fixtures to include tags on selected activity and dining candidates.
37. Add a unit test proving successful feedback persistence creates `candidate` memory rows with:
    - `status == "candidate"`
    - `text is None`
    - minimal `value_json`
38. Add a unit test proving the writer does not overwrite an existing same-key `active` memory row.
39. Add a unit test proving the writer updates an existing same-key `candidate` row in place.
40. Add a unit test proving the persisted feedback JSON contains `memory_candidate_summary` and that the summary is safe to serialize.
41. In `tests/integration/test_feedback_writer_gateway.py`, extend the successful mock-world execution path to verify:
    - at least one candidate row is written for a case with supported tags
    - candidate rows contain structured payload only
    - `text` is null
    - feedback still reports `status == "completed"`
42. In `tests/integration/test_langgraph_workflow_gateway.py`, add one end-to-end auto-confirm or post-feedback assertion proving:
    - workflow still completes
    - candidate rows are created after feedback
    - created candidate rows are not pulled into governable memory in the same existing read path
43. Do not modify benchmark suite IDs, release gates, or public API tests unless a narrow fixture adjustment is strictly necessary to keep current assertions compiling.
44. Run the smallest useful test slices first:
    - helper unit tests
    - feedback writer unit tests
45. Start `postgres` and `redis`, run Alembic, then run the focused integration tests.
46. Finish with `git diff --check` and `git status --short`.
47. Stage only task-relevant files. Do not stage unrelated local docs.
48. Commit with the expected message.

## 6. Testing Plan

- Unit tests:
  - helper extracts `activity_style` from `citywalk`, `indoor`, and `outdoor` tags with the correct priority
  - helper extracts `spouse_lighter_meals` only from `lighter_options`
  - helper emits no candidate when supported tags are absent
  - helper never copies address/phone/token/secret-like inputs into memory payloads
  - feedback writer creates new `candidate` memory rows after successful feedback
  - feedback writer updates same-key existing `candidate` rows in place
  - feedback writer skips same-key existing non-`candidate` rows
  - persisted `feedback["memory_candidate_summary"]` contains only safe key-level information
- Integration tests:
  - mock-world execution plus feedback writes candidate memories with structured payloads only
  - workflow end-to-end feedback path still completes and candidate memory does not change governable loading semantics
- Smoke tests:
  - `git diff --check`
  - `git status --short`

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
git status --short
python -m pytest tests/test_feedback_memory_candidates.py tests/test_feedback_writer.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_feedback_writer_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "feedback or candidate" -q
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add sensitive memory minimization
```

Expected commands:

```bash
git status --short
git add backend/app/feedback/memory_candidates.py
git add backend/app/feedback/schemas.py
git add backend/app/feedback/writer.py
git add backend/app/repositories/memory.py
git add tests/test_feedback_memory_candidates.py
git add tests/test_feedback_writer.py
git add tests/integration/test_feedback_writer_gateway.py
git add tests/integration/test_langgraph_workflow_gateway.py
git add docs/specs/097-sensitive-memory-feedback-candidate-v0.md
git add docs/plans/097-sensitive-memory-feedback-candidate-v0-plan.md
git diff --cached --check
git commit -m "feat: add sensitive memory minimization"
git push -u origin codex/097-sensitive-memory-feedback-candidate-v0
```

The implementer must confirm `.env`, secrets, generated artifacts, and the unrelated untracked local docs are not staged.

## 9. Out-of-scope Changes

- Do not implement memory CRUD, user-facing review, approval, or deletion.
- Do not add candidate-to-active promotion logic.
- Do not make candidate memory affect current query planning or memory policy reads.
- Do not change benchmark suite membership, release gates, or score semantics.
- Do not add frontend UI or public API fields for candidate-memory management.
- Do not add Alembic migrations, new tables, or schema changes to `memory_items`.
- Do not stage unrelated local files:
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/097-sensitive-memory-feedback-candidate-v0.md`.
- [ ] Feedback-generated memory rows are always persisted with `status == "candidate"`.
- [ ] Feedback-generated memory rows store structured `value_json` only and `text == null`.
- [ ] Only selected draft tags are used as candidate sources.
- [ ] Address-like, phone-like, token-like, and secret-like inputs are not copied into durable memory.
- [ ] Existing same-key non-`candidate` rows are not overwritten.
- [ ] Existing same-key `candidate` rows are updated in place rather than duplicated.
- [ ] Persisted feedback includes a safe additive `memory_candidate_summary`.
- [ ] Existing feedback status behavior and benchmark expectations remain unchanged.
- [ ] Required unit tests passed.
- [ ] Required integration tests passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit, excluding unrelated pre-existing local files.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

After implementation, report back with:

- exact files changed
- the final tag-to-memory mapping implemented
- the exact create/update/skip rule used under the uniqueness constraint
- whether same-key existing non-`candidate` rows were skipped as planned
- one example persisted candidate payload showing `text = null` and minimal `value_json`
- verification commands run and their results
- commit hash
- push result
- any follow-up task recommendation, especially if the next step should be candidate review/promotion controls or broader memory-governance benchmark coverage
