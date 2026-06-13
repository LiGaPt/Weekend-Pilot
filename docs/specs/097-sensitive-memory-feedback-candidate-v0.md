# Spec: 097 Sensitive memory + feedback candidate v0

## 1. Goal

Add one narrow, deterministic post-execution memory path so that the feedback writer can persist only low-risk `candidate` memory records while minimizing sensitive information and avoiding any automatic promotion to governable `active` memory.

Today the repository has explicit memory lifecycle support, including `candidate`, but the feedback writer still only produces user-facing execution feedback and does not generate memory at all. That leaves a gap in the remaining memory-governance closure: there is no bounded, auditable path for turning completed execution outcomes into future memory candidates, and there is no enforced minimization rule that prevents feedback-shaped free text or location/contact-like fields from leaking into memory rows. After this task, feedback writing must be able to derive a very small set of supported preference candidates from reviewed-plan tags, persist them as `candidate`, and guarantee that raw text, address-like, phone-like, token-like, or secret-like data is not copied into durable memory.

## 2. Project Context

This task fits into `docs/PROJECT_BLUEPRINT.md` Sections 10, 14, 18, and 19:

- Section 10 requires memory to be governable, structured, and minimized where possible.
- Section 14 requires observability and safe metadata handling.
- Section 18 requires each task to be small, independently testable, and reviewable.
- Section 19 requires no secrets or unsafe payloads to be committed or persisted casually.

In `docs/NEXT_PHASE_ROADMAP.md`, the repository default priority remains benchmark and observability infrastructure, but the roadmap also explicitly lists the remaining long-term memory-governance closure as including stronger sensitive-information minimization. The latest completed task chain already covers:

- Task `095`: memory decision audit log and compact policy summary
- Task `096`: explicit lifecycle states including `candidate`

That makes this task the next smallest M5 follow-up because it uses the new `candidate` lifecycle state without widening into memory CRUD or user-facing controls. This task must stay backend-only and additive.

## 3. Requirements

### A. Add a bounded feedback-to-candidate path

- `DeterministicFeedbackWriter` must continue to generate user-safe execution feedback exactly as before.
- After building execution feedback, the writer must deterministically derive zero or more memory candidates from the selected reviewed plan.
- Every memory created by this path must persist with:
  - `memory_type = "preference"`
  - `status = "candidate"`
  - `text = null`
- This task must not create any `active`, `expired`, `ignored`, or `disabled` memory rows from feedback.
- This task must not change `load_memory(...)`, `list_governable_for_user(...)`, or current read-memory policy semantics.

### B. Restrict candidate extraction to explicit supported signals

- Candidate extraction in v0 must support exactly these memory keys:
  - `activity_style`
  - `spouse_lighter_meals`
- `activity_style` may be inferred only from the selected draft activity tags.
- `spouse_lighter_meals` may be inferred only from the selected draft dining tags.
- The exact tag-to-value mapping rules must be:
  - activity tags:
    - if tags contain `citywalk`, candidate value is `citywalk`
    - else if tags contain `indoor`, candidate value is `indoor`
    - else if tags contain `outdoor`, candidate value is `outdoor`
    - else no `activity_style` candidate is emitted
  - dining tags:
    - if tags contain `lighter_options`, candidate value is `lighter_options`
    - else no `spouse_lighter_meals` candidate is emitted
- `citywalk` must take priority over `outdoor`, matching current intent/parser preference ordering.
- This task must not infer memory from free-form titles, summaries, notes, messages, addresses, locations, or action payload text.

### C. Enforce sensitive-memory minimization by structure, not by copying text

- Feedback-generated memory must store only normalized structured values in `value_json`.
- `value_json` for feedback-generated candidate memory must use this minimal shape:

```json
{
  "preference": "indoor",
  "source": "feedback_writer_v0",
  "evidence": "selected_candidate_tags"
}
```

- `text` must always be `null` for feedback-generated candidate memory.
- Candidate extraction must not read from or persist values taken from:
  - `address`
  - `location`
  - `message`
  - `message_preview`
  - `headline`
  - `final_arrangement_message`
  - `next_steps`
  - execution `response_json`
  - execution `error_json`
  - action labels/messages
  - any mapping key whose name contains:
    - `token`
    - `secret`
    - `password`
    - `authorization`
    - `api_key`
    - `apikey`
    - `prompt`
    - `debug_trace`
- Candidate extraction must therefore structurally exclude phone/address/secret-like inputs instead of trying to preserve or redact them into memory text.

### D. Define write semantics under the existing uniqueness constraint

- The task must respect the existing unique constraint on `(user_id, memory_type, key)`.
- If no existing row matches `(user_id, "preference", key)`, feedback writing must create a new `candidate` row.
- If an existing row matches and its persisted status is `candidate`, feedback writing must update that existing row in place.
- Updating an existing candidate row must refresh:
  - `value_json`
  - `text`
  - `confidence`
  - `status`
  - `source_run_id`
  - `expires_at`
- Updating an existing candidate row must keep it in lifecycle `candidate`.
- If an existing row matches and its persisted status is not `candidate`, feedback writing must skip that key and must not overwrite the existing row.
- Existing `active`, `expired`, `ignored`, or `disabled` memory must therefore remain untouched by this task.

### E. Define exact persisted candidate defaults

- All feedback-generated candidate memory in v0 must use:
  - `confidence = Decimal("0.6000")`
  - `expires_at = null`
  - `source_run_id = current run_id`
  - `source_langsmith_trace_id = null`
- Candidate rows created or updated by this task must remain compatible with the lifecycle helper introduced in Task `096`.

### F. Add one additive, safe candidate-generation summary to feedback payloads

- `ExecutionFeedbackResult` must gain one additive field:
  - `memory_candidate_summary`
- Persisted `plan_json["feedback"]` must gain one additive field:
  - `memory_candidate_summary`
- The summary must be safe for user-facing or reviewer-facing serialization.
- The summary must not include raw text, addresses, phone numbers, action IDs, tool event IDs, memory IDs, or free-form payload fragments.
- The summary shape must be:

```json
{
  "schema_version": "feedback_memory_candidates_v0",
  "generation_status": "completed",
  "created_keys": ["activity_style"],
  "updated_keys": [],
  "skipped_keys": ["spouse_lighter_meals"]
}
```

- `generation_status` must be one of:
  - `completed`
  - `degraded`
  - `not_applicable`

### G. Keep feedback and benchmark behavior backward compatible

- Existing feedback headline/message/final-arrangement output must remain backward compatible.
- Existing benchmark `feedback` grader expectations and `expected_feedback_status` semantics must remain unchanged.
- This task must not add new benchmark suites or change benchmark thresholds.
- This task must not change public API routes or frontend rendering requirements.

## 4. Non-goals

- Do not implement candidate review, approval, promotion, or user-controlled memory CRUD.
- Do not make `candidate` memory affect current planning or read-memory governance.
- Do not create high-confidence `active` memory automatically from feedback.
- Do not infer memory from free-form user text, feedback prose, execution messages, or raw provider payloads.
- Do not add new database tables, columns, indexes, or Alembic revisions.
- Do not add frontend UI for candidate-memory display.
- Do not change benchmark suite membership, release-gate semantics, or observability API contracts.
- Do not commit `.env`, API keys, tokens, secrets, or generated artifacts.

## 5. Interfaces and Contracts

### Inputs

- selected reviewed-plan JSON from `Plan.plan_json`
- selected draft activity tags
- selected draft dining tags
- current `run_id`
- current run `user_id`
- existing `memory_items` row for `(user_id, memory_type, key)` when present

### Outputs

- zero or more persisted `memory_items` rows with:
  - `memory_type = "preference"`
  - `key in {"activity_style", "spouse_lighter_meals"}`
  - `status = "candidate"`
  - `text = null`
  - structured `value_json`
- additive feedback result field:
  - `ExecutionFeedbackResult.memory_candidate_summary`
- additive persisted feedback field:
  - `plan_json["feedback"]["memory_candidate_summary"]`

### Schemas

Candidate memory row payload:

```json
{
  "memory_type": "preference",
  "key": "activity_style",
  "value_json": {
    "preference": "citywalk",
    "source": "feedback_writer_v0",
    "evidence": "selected_candidate_tags"
  },
  "text": null,
  "confidence": "0.6000",
  "status": "candidate",
  "expires_at": null,
  "source_run_id": "f2338dd5-9df8-47b7-ae73-408933dfbb08",
  "source_langsmith_trace_id": null
}
```

Candidate-summary payload:

```json
{
  "schema_version": "feedback_memory_candidates_v0",
  "generation_status": "completed",
  "created_keys": ["activity_style"],
  "updated_keys": ["spouse_lighter_meals"],
  "skipped_keys": []
}
```

Write semantics:

- same key, no existing row -> create `candidate`
- same key, existing `candidate` -> update in place
- same key, existing non-`candidate` -> skip

## 6. Observability

This task must stay lightweight.

It must record:

- durable candidate-memory rows in `memory_items`
- one additive safe `memory_candidate_summary` inside persisted feedback JSON

It must not record:

- raw source text copied from feedback prose
- addresses or phone numbers inside durable memory payloads
- tool event IDs, action IDs, idempotency keys, debug traces, or prompt-like content inside memory payloads or candidate summary

This task does not add a new public API or a new internal observability panel.

## 7. Failure Handling

- If the selected draft has no supported tags, feedback writing must still succeed and record `generation_status = "not_applicable"`.
- If a supported key resolves to no normalized value, that key must be skipped without failing feedback.
- If a same-key existing row is non-`candidate`, that key must be skipped without failing feedback.
- If a same-key existing row is `candidate`, it must be updated in place.
- If candidate extraction encounters address-like, phone-like, token-like, or secret-like fields elsewhere in the plan payload, they must be ignored and must not appear in stored memory.
- If candidate-generation logic encounters an unexpected per-key error, feedback writing should continue for other keys and mark the summary `generation_status = "degraded"`.
- Unexpected feedback-core failures that already would have broken the writer before this task should continue to raise `FeedbackWriterError`.

## 8. Acceptance Criteria

- [ ] Feedback writing can persist `candidate` memory rows after successful execution feedback.
- [ ] Feedback-generated memory never persists as `active`, `expired`, `ignored`, or `disabled`.
- [ ] Feedback-generated memory stores only structured `value_json` and always sets `text = null`.
- [ ] Candidate extraction only uses selected draft tags and does not infer from free-form text.
- [ ] Address-like, phone-like, token-like, and secret-like source fields are structurally excluded from memory generation and do not appear in stored memory payloads.
- [ ] `activity_style` extraction follows priority `citywalk > indoor > outdoor`.
- [ ] `spouse_lighter_meals` extraction only emits `lighter_options` when the selected dining tags support it.
- [ ] Existing non-`candidate` memory rows are not overwritten by feedback candidate generation.
- [ ] Existing same-key `candidate` rows are updated in place rather than duplicated.
- [ ] Candidate-memory writes remain compatible with the current lifecycle contract from Task `096`.
- [ ] Persisted feedback gains additive `memory_candidate_summary` without changing existing feedback status semantics.
- [ ] Existing feedback message content remains user-safe and benchmark-compatible.
- [ ] No benchmark suite membership, release-gate semantics, public API route, or frontend UI requirement changes.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] The working tree is clean after commit, excluding unrelated pre-existing local files.

## 9. Verification Commands

```bash
git status --short
python -m pytest tests/test_feedback_memory_candidates.py tests/test_feedback_writer.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_feedback_writer_gateway.py tests/integration/test_langgraph_workflow_gateway.py -k "feedback or candidate" -q
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add sensitive memory minimization
```

## 11. Notes for the Implementer

Keep this task intentionally narrow.

The most important constraint is that `candidate` is now a real lifecycle state, but it is still non-governable. This task must use that state to create bounded, auditable future-memory hints without touching current planning behavior. The safest implementation is to derive candidate memory only from explicit selected-candidate tags, store normalized enums only, and treat all free-form feedback text and contact/location-like fields as out of scope for persistence.

If implementation pressure suggests introducing memory promotion, CRUD, migration work, or a public API contract for candidate review, stop and report that scope expansion instead of folding it into this task.
