# Spec: 045 Demo Plan Version Lineage v0

## 1. Goal

Add the first stable public plan-version lineage contract for the Web demo so follow-up replans are understandable and testable as `v1`, `v2`, `v3`, rather than as unrelated run IDs.

Task `044` added `POST /demo/runs/{run_id}/replan` and correctly creates a new run in the same internal conversation session, but the public response still has no explicit version semantics. A reviewer can see that a new `run_id` exists, but cannot tell whether it is the first plan, a follow-up version, or what prior run it came from. After this task, every public demo run summary must include a compact, safe `plan_version` object that makes the current version explicit and links follow-up runs back to their immediate source run and selected source plan.

This task intentionally does not redesign the execution-preview surface. The public demo already renders `draft.proposed_actions` as a pre-confirmation action preview, so the smallest useful slice of roadmap item `8. plan versioning 与执行前 action manifest` is to formalize version lineage first and leave action-manifest normalization for a later task.

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` defines the product as a conversation-style planning system rather than a one-shot recommendation endpoint, with PostgreSQL as the durable source of truth and the Web demo as the primary MVP review surface. `docs/NEXT_PHASE_ROADMAP.md` places the current work under `M4. 多轮对话与方案版本` and lists `8. plan versioning 与执行前 action manifest` immediately after `6. session / conversation 数据模型` and `7. 多轮澄清与 replan 工作流`.

The repository state already reflects that sequence:

- Tasks `033` through `042` cover the current M1/M2/M3 baseline for timing, benchmark summaries, internal observability, public/internal view separation, benchmark taxonomy, suite catalog, artifact panels, and recovery visualization.
- Task `043` added durable `conversation_sessions`, `conversation_turns`, and `agent_runs.session_id`.
- Task `044` added the first follow-up replan API path and same-session follow-up run creation.

That means the next gap is not another observability scaffold and not another generic replan path. The next missing contract is public version lineage for those new follow-up runs.

This task touches these blueprint areas directly:

- PostgreSQL source of truth
- Minimal Web UI / Web demo API path
- Human-in-the-loop presentation boundary
- Future multi-turn planning and plan version evolution

## 3. Requirements

- Add a new public response model `DemoPlanVersionSummary`.
- Add a new required field `plan_version` to public `DemoRunSummary`.
- `DemoPlanVersionSummary` must include:
  - `version_number: int`
  - `version_label: str`
  - `source_run_id: UUID | None`
  - `source_selected_plan_id: UUID | None`
- `version_number` must be `>= 1`.
- `version_label` must be derived as `v<version_number>`.
- Every successful public demo response from these existing routes must include `plan_version`:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- A newly started run from `POST /demo/runs` must return:
  - `version_number = 1`
  - `version_label = "v1"`
  - `source_run_id = null`
  - `source_selected_plan_id = null`
- A follow-up run created by `POST /demo/runs/{run_id}/replan` must return:
  - `version_number = source_version_number + 1`
  - `version_label` matching that incremented number
  - `source_run_id = <source run id>`
  - `source_selected_plan_id = <source selected plan id or null>`
- Repeated replans must continue incrementing monotonically along the same immediate chain, for example `v1 -> v2 -> v3`.
- Version lineage must be persisted in durable run metadata under `agent_runs.metadata_json["demo"]["plan_version"]`.
- The persisted `demo.plan_version` metadata must remain compact and include only:
  - `version_number`
  - `source_run_id`
  - `source_selected_plan_id`
- `build_summary(...)` must derive `version_label` from the stored version number rather than relying on stored label text.
- Existing runs that predate this task and do not have `demo.plan_version` metadata must remain readable.
- When a run has no stored `demo.plan_version` metadata, public summary generation must fall back to:
  - `version_number = 1`
  - `version_label = "v1"`
  - `source_run_id = null`
  - `source_selected_plan_id = null`
- Replanning from a legacy source run with missing `demo.plan_version` metadata must still work and must treat the source as `v1`.
- The source run’s public summary must remain unchanged after a successful replan.
- Do not expose `session_id`, conversation-turn payloads, or other conversation-history structures in the new version summary.
- Keep the current public plan preview surface unchanged apart from the additive version metadata:
  - `plans`
  - `selected_plan_id`
  - `proposed_actions`
  - confirmation / execution / feedback fields
- Do not rename or reserialize `proposed_actions` in this task.
- The public demo frontend must render the version label for the loaded run, using the new `plan_version.version_label`.
- The public demo frontend must not add a replan button or any new history browser in this task.
- Update `README.md` and `docs/WEB_DEMO_README.md` to document the visible version behavior:
  - initial run starts at `v1`
  - follow-up replan returns a new `run_id` and increments the visible version label
- Add or update focused tests for:
  - public response serialization
  - version fallback behavior
  - first replan version increment
  - repeated replan version increment
  - public demo UI version rendering
- Do not add or modify any Alembic revision in this task.
- Do not add new dependencies.

## 4. Non-goals

- Do not add frontend controls for follow-up replanning in the public demo UI.
- Do not expose `session_id`, conversation history, or conversation lineage lists in `DemoRunSummary`.
- Do not add `GET /demo/runs/{run_id}/history`, `GET /demo/sessions`, or any new public history endpoint.
- Do not redesign `draft.proposed_actions` into a new `action_manifest` schema in this task.
- Do not move from the current “one replan creates one new run” model to “one run stores multiple plan versions.”
- Do not modify workflow-core request/response contracts, benchmark harness contracts, or internal observability response contracts.
- Do not add or modify Alembic revisions, tables, indexes, or nullable columns.
- Do not add new dependencies.
- Do not commit `.env`, API keys, tokens, secrets, generated `var/` artifacts, or unrelated untracked files such as `docs/NEXT_PHASE_ROADMAP.md` and `docs/TASK_WORKFLOW_PROMPTS.md`.

## 5. Interfaces and Contracts

### Inputs

- Existing public requests remain unchanged:
  - `POST /demo/runs`
  - `GET /demo/runs/{run_id}`
  - `POST /demo/runs/{run_id}/replan`
  - `POST /demo/runs/{run_id}/confirm`
  - `POST /demo/runs/{run_id}/decline`
- No new request fields are added in this task.

### Outputs

- Public `DemoRunSummary` becomes additively richer by requiring a new `plan_version` object.
- Existing `agent_runs.metadata_json["demo"]` gains a compact `plan_version` metadata block.
- Existing public `plans` content remains unchanged in shape.

### Schemas

Public response excerpt:

```json
{
  "run_id": "00000000-0000-0000-0000-000000000010",
  "status": "awaiting_confirmation",
  "selected_plan_id": "00000000-0000-0000-0000-000000000020",
  "plan_version": {
    "version_number": 2,
    "version_label": "v2",
    "source_run_id": "00000000-0000-0000-0000-000000000001",
    "source_selected_plan_id": "00000000-0000-0000-0000-000000000002"
  },
  "plans": []
}
```

Persisted internal metadata excerpt:

```json
{
  "demo": {
    "plan_version": {
      "version_number": 2,
      "source_run_id": "00000000-0000-0000-0000-000000000001",
      "source_selected_plan_id": "00000000-0000-0000-0000-000000000002"
    }
  }
}
```

## 6. Observability

This task does not add a new observability endpoint or public observability field.

The required durable record is the compact version-lineage metadata stored under `agent_runs.metadata_json["demo"]["plan_version"]`. That metadata must be stable across refreshes and across later confirm/decline requests for the same run. Existing internal observability, workflow timing, trace buffers, benchmark artifacts, and recovery summaries remain unchanged.

## 7. Failure Handling

- If a run predates this task and has no `demo.plan_version` metadata, `GET /demo/runs/{run_id}` must still succeed and must fall back to `v1`.
- If `demo.plan_version.version_number` is missing, non-integer, or `< 1`, public summary generation must sanitize it to `v1` rather than failing the request.
- If a replan source run predates this task and has no version metadata, the source must be treated as `v1` and the new follow-up run must become `v2`.
- If `POST /demo/runs` or `POST /demo/runs/{run_id}/replan` fails before commit, version metadata updates must roll back with the rest of the transaction.
- Existing replan validation failures from task `044` must remain unchanged; this task must not widen or alter those status-code rules.
- Existing confirm/decline behavior must remain unchanged except for the additive `plan_version` field in the response payload.

## 8. Acceptance Criteria

- [ ] `docs/specs/045-demo-plan-version-lineage-v0.md` exists and matches this task.
- [ ] `docs/plans/045-demo-plan-version-lineage-v0-plan.md` exists and matches this task.
- [ ] Public `DemoRunSummary` always includes `plan_version`.
- [ ] A brand-new demo run returns `plan_version.version_number = 1` and `plan_version.version_label = "v1"`.
- [ ] A successful replan run returns a new `run_id` and `plan_version.version_number = source version + 1`.
- [ ] Replanning twice in sequence produces a monotonic visible chain such as `v1 -> v2 -> v3`.
- [ ] The follow-up run’s `plan_version.source_run_id` points to the immediate source run.
- [ ] The follow-up run’s `plan_version.source_selected_plan_id` points to the immediate source selected plan when one exists, otherwise `null`.
- [ ] The source run’s public summary remains unchanged after a follow-up replan succeeds.
- [ ] Legacy runs without stored version metadata still serialize as `v1`.
- [ ] Public demo UI renders the version label for the current run.
- [ ] Public demo UI still does not expose `session_id`, conversation history, trace fields, or internal observability fields.
- [ ] `proposed_actions` remains unchanged and continues to represent the pre-confirmation action preview in this task.
- [ ] No Alembic revision is added or modified in this task.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` document the version behavior.
- [ ] No `.env`, API key, token, secret, generated `var/` artifact, or unrelated untracked local file is committed.
- [ ] `git diff --check` passes.
- [ ] Focused verification commands listed below pass, or any blocker is reported clearly.
- [ ] The working tree is clean after commit except for pre-existing intentionally untracked local files outside this task.

## 9. Verification Commands

```bash
python -m pytest tests/test_demo_api.py tests/test_demo_versioning.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -v
npm --prefix frontend run test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: add demo plan version lineage
```

## 11. Notes for the Implementer

Keep this task as the narrow first half of roadmap item `8. plan versioning 与执行前 action manifest`.

The sequencing rationale matters:

- Task `044` already made follow-up replanning real and durable.
- The public demo already renders `proposed_actions`, so there is already a visible execution-preview surface.
- The missing contract is explicit version lineage, not another action-preview redesign.

Keep the implementation inside the demo layer and additive run metadata. Do not widen this task into new workflow-core abstractions, new DB schema, new public history endpoints, or a frontend replan workflow. If the current execution branch does not contain commit `c1231b7 feat: add demo follow-up replan workflow` or an equivalent merged base, stop and reconcile repository state before implementing.
