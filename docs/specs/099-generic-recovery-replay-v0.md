# Spec: 099 Generic Recovery Replay v0

## 1. Goal

Generalize the existing recovery replay review flow so it is no longer pinned to `family_route_failure_v1` only. The repository already has a working single-case reviewer closure command, but both the runner and the CLI are hardcoded around one family failure case and one canonical latest alias.

This task must make the recovery replay review reusable for any recovery-capable benchmark case and for the existing recovery benchmark suite, while preserving the current no-argument reviewer flow. After this task, developers must be able to run recovery replay review for a specific case or for the `recovery_focused` suite, compare the resulting review artifacts, and still rely on the existing `latest-family_route_failure_v1-review.json` alias and schema for the default reviewer-facing evidence path.

## 2. Project Context

This task fits `docs/PROJECT_BLUEPRINT.md` in the harness engineering and failure-handling areas:

- Failure injection and replay harness
- LocalLife-Bench
- Observability
- Bounded recovery behavior
- Reviewer-facing evidence artifacts

It maps primarily to milestone `M5. 恢复与记忆治理` in `docs/NEXT_PHASE_ROADMAP.md`, specifically the roadmap direction around making recovery behavior more replayable, auditable, and comparable across multiple failure scenarios. It also supports later integrity work by making recovery evidence reusable as an input to aggregate summary and review surfaces, without changing the confirmation boundary, Tool Gateway rules, benchmark grading semantics, or frontend behavior.

Relevant current repository state:

- Task `067` added one canonical single-case recovery replay review closure flow.
- Task `092` and `093` established additive V2 integrity benchmark structure.
- Task `094` added repeatable stability reporting.
- Tasks `095` through `098` just completed memory-governance integrity work.
- The next smallest useful gap is not more recovery UI or more failure fixtures. It is making the existing recovery replay review tooling generic enough to cover the repository’s registered recovery cases.

## 3. Requirements

- The backend must continue to support the existing default recovery review flow for `family_route_failure_v1` with no CLI arguments.
- Add a generic selection layer so the recovery replay review can be invoked in exactly one of these modes:
  - default mode with no selector, which means `family_route_failure_v1`
  - explicit `case` mode via `--case-id <case_id>`
  - explicit `suite` mode via `--suite-id <suite_id>`
- `--case-id` and `--suite-id` must be mutually exclusive.
- The only supported suite IDs in this v0 task are recovery-capable suite IDs:
  - `recovery_focused`
  - its existing alias `failures`
- If a selected case is not recovery-capable, the runner must fail fast with a typed error before replay execution starts.
- For this task, “recovery-capable” means all of the following are true in the loaded benchmark case:
  - `failure_profile` is present
  - `expected.expected_workflow_status == "failed"`
  - `expected.expected_recovery_action` is a non-empty string
  - `expected.min_action_count == 0`
- The runner must stop using hardcoded `family_route_failure_v1` failure-profile assumptions for all validation except the default alias behavior.
- Per-case review validation must be derived from the selected benchmark case plus the actual benchmark/replay/observability outputs:
  - source benchmark `status` must be `passed`
  - source `workflow_status` must equal `case.expected.expected_workflow_status`
  - source `action_count` must be `0`
  - source `failure_chain_summary.profile_id` must equal `case.failure_profile`
  - source `failure_chain_summary.recovery_actions` must equal `[case.expected.expected_recovery_action]`
  - source `failure_chain_summary.bounded` must be `true`
  - source `failure_chain_summary.injected_effects` must be non-empty
  - `len(source failure_chain_summary.injected_effects)` must be greater than or equal to `case.expected.min_injected_failure_count`
- Replay validation for each selected case must require:
  - replay `status == "passed"`
  - replay `mismatches == []`
  - replay `replay_benchmark_status == "passed"`
  - replay `source.workflow_status` equals the case’s expected workflow status
  - replay `replay.workflow_status` equals the case’s expected workflow status
  - replay `source.failure_chain_signature` equals the source benchmark’s injected effects
  - replay `replay.failure_chain_signature` equals the source benchmark’s injected effects
- Observability validation for each selected case must require:
  - `benchmark_artifact_summary` exists
  - `benchmark_artifact_summary.case_id == case.case_id`
  - `benchmark_artifact_summary.report_path == source_report_path`
  - `recovery_path_summary` exists
  - `recovery_path_summary.attempt_count >= 1`
  - `recovery_path_summary.max_attempts == source failure_chain_summary.max_attempts`
  - the final recovery attempt has `recovery_action == case.expected.expected_recovery_action`
  - if the expected recovery action is `stop_safely`, the final recovery attempt `status == "stopped"`
  - `recovery_path_summary.replay_source` exists
  - `recovery_path_summary.replay_source.case_id == case.case_id`
  - `recovery_path_summary.replay_source.benchmark_report_path == source_report_path`
- Keep the existing per-case artifact schema compatible:
  - existing `RecoveryReplayReviewResult` must remain readable for current canonical alias consumers
  - existing `schema_version == "weekendpilot_recovery_replay_review_v1"` must remain valid for single-case artifacts
- Add one additive run-level schema for generic invocations:
  - a new run report object must summarize one or more per-case review results
  - the run report must not replace the existing per-case schema
- Output layout must be deterministic:
  - single-case mode must keep the current shape under one unique run directory
  - suite mode must write one aggregate run report plus one per-case review subdirectory per case
- Single-case mode must write:
  - source benchmark report
  - replay report
  - review trace buffer
  - one per-case review artifact
- Suite mode must write:
  - one aggregate run report at the run root
  - one per-case review artifact tree for every selected case
- The default and explicit `--case-id family_route_failure_v1` flow must continue to refresh:
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Explicit single-case runs for other recovery cases must refresh:
  - `var/recovery-reviews/latest-<case_id>-review.json`
  only when that case review passes
- Suite runs may refresh per-case latest aliases for passed case results, but they must not overwrite an alias for any failed or errored case result.
- This task must not remove, rename, or repurpose:
  - `python scripts/run_recovery_replay_review.py`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- The CLI must print a concise summary that changes by mode:
  - default and `case` mode print the selected case, run ID, source report path, replay report path, review artifact path, and latest alias path
  - `suite` mode prints the suite ID, run directory, aggregate run report path, pass/fail/error counts, and one short line per case result
- Exit behavior must be:
  - `0` only when all selected case reviews pass
  - `1` when any selected case review fails or errors
- Update repository docs so they explain:
  - the default canonical family flow is unchanged
  - `--case-id` and `--suite-id` are additive generic entry points
  - current canonical reviewer evidence still points at the family alias

## 4. Non-goals

- Do not change benchmark case JSON fixtures.
- Do not change recovery routing policy, retry budgets, or failure profiles.
- Do not change replay comparison semantics in `backend/app/benchmark/replay.py`.
- Do not add HTTP replay APIs, frontend replay controls, or internal observability UI changes.
- Do not add new benchmark suite members, new suite IDs, or new failure scenarios.
- Do not replace the current reviewer-facing canonical evidence alias.
- Do not widen this task into chaos-case creation, integrity summary APIs, or release-evidence refresh.
- Do not commit `.env`, API keys, tokens, secrets, or generated `var/` artifacts.

## 5. Interfaces and Contracts

### Inputs

- Existing single-case runner entry point:
  - `python scripts/run_recovery_replay_review.py`
- New explicit single-case CLI mode:
  - `python scripts/run_recovery_replay_review.py --case-id family_route_and_dining_unavailable_v1`
- New suite CLI mode:
  - `python scripts/run_recovery_replay_review.py --suite-id recovery_focused`
- Existing suite alias must also work:
  - `python scripts/run_recovery_replay_review.py --suite-id failures`

Backend functions should separate compatibility and generic execution:

- Backward-compatible single-case wrapper:
  - `run_recovery_replay_review(...) -> RecoveryReplayReviewResult`
- New generic runner:
  - `run_generic_recovery_replay_review(...) -> RecoveryReplayReviewRunReport`

Recommended generic runner shape:

```text
run_generic_recovery_replay_review(
    *,
    case_id: str | None = None,
    suite_id: str | None = None,
    output_root: Path | str | None = None,
    start_services: bool = True,
    timeout_seconds: float = 60.0,
    poll_interval_seconds: float = 1.0,
) -> RecoveryReplayReviewRunReport
```

### Outputs

- Existing per-case artifact remains:
  - `var/recovery-reviews/recovery-review-<uuid>/recovery-review.json`
- Existing latest alias remains:
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- New non-family case aliases are additive:
  - `var/recovery-reviews/latest-<case_id>-review.json`
- New run-level suite artifact:
  - `var/recovery-reviews/recovery-review-<uuid>/recovery-review-run.json`

### Schemas

Per-case schema remains compatible and still validates with `RecoveryReplayReviewResult`.

Add a new run-level report schema such as:

```json
{
  "schema_version": "weekendpilot_recovery_replay_review_run_v1",
  "status": "passed",
  "selection_mode": "suite",
  "suite_id": "recovery_focused",
  "requested_case_ids": [
    "family_route_failure_v1",
    "family_route_and_dining_unavailable_v1",
    "rainy_day_ticket_sold_out_v1"
  ],
  "run_directory": "var/recovery-reviews/recovery-review-123",
  "report_path": "var/recovery-reviews/recovery-review-123/recovery-review-run.json",
  "passed_count": 3,
  "failed_count": 0,
  "error_count": 0,
  "case_results": [
    {
      "case_id": "family_route_failure_v1",
      "status": "passed",
      "review_artifact_path": "var/recovery-reviews/recovery-review-123/cases/family_route_failure_v1/recovery-review.json",
      "latest_review_path": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
    }
  ]
}
```

The run-level schema must be additive only. Existing code that reads `RecoveryReplayReviewResult` from the family alias must continue to work unchanged.

## 6. Observability

This task must reuse the existing sources of truth for evidence:

- benchmark case report JSON from `BenchmarkHarness`
- replay case report JSON from `BenchmarkReplayHarness`
- `InternalObservabilityService.get_run_summary(...)`
- persisted benchmark artifact summaries
- persisted recovery path summaries

No new API route, database table, migration, or LangSmith-only dependency is required.

The new run-level report is a local file artifact only. It must remain sanitized and must not include:

- raw prompts
- tracebacks
- stack traces
- tokens
- API keys
- authorization headers
- raw write payload dumps
- unstable internal identifiers that are already excluded from existing replay reports

## 7. Failure Handling

- If both `case_id` and `suite_id` are provided, the CLI and runner must reject the invocation before execution.
- If an unknown case ID is provided, the runner must return an `error`.
- If an unknown suite ID is provided, the runner must return an `error`.
- If a suite resolves to zero cases, the runner must return an `error`.
- If a selected case is not recovery-capable under this task’s contract, the runner must return an `error`.
- If runtime bootstrap fails, the run status must be `error`.
- If one case in a suite fails contract validation but the orchestration completes, that case result must be `failed` and the aggregate run status must be `failed`.
- If one case in a suite errors during benchmark, replay, or observability lookup, that case result must be `error` and the aggregate run status must be `error`.
- A failed or errored per-case result must never overwrite that case’s latest alias.
- A suite run must still write its aggregate run report even when one or more case results fail or error.
- Existing single-case canonical evidence verification must remain valid after the task.

## 8. Acceptance Criteria

- [ ] `docs/specs/` and `docs/plans/` remain continuous and matched after adding Task `099`.
- [ ] The repository still supports `python scripts/run_recovery_replay_review.py` with no arguments.
- [ ] No-argument execution still reviews `family_route_failure_v1`.
- [ ] `python scripts/run_recovery_replay_review.py --case-id <case_id>` works for registered recovery-capable cases.
- [ ] `python scripts/run_recovery_replay_review.py --suite-id recovery_focused` works.
- [ ] `python scripts/run_recovery_replay_review.py --suite-id failures` works as an alias.
- [ ] The CLI rejects invocations that provide both `--case-id` and `--suite-id`.
- [ ] Non-recovery cases are rejected with a typed failure before replay execution.
- [ ] Existing per-case review artifacts still validate through `RecoveryReplayReviewResult`.
- [ ] A new additive run-level report schema exists for suite or generic multi-case review output.
- [ ] Single-case mode continues to write a per-case review artifact and latest alias on pass only.
- [ ] Suite mode writes one aggregate run report and one per-case review artifact subtree per selected case.
- [ ] The default family alias path `var/recovery-reviews/latest-family_route_failure_v1-review.json` is unchanged.
- [ ] The default family alias content remains compatible with existing verification code.
- [ ] Per-case validation uses the selected case’s expected recovery metadata instead of fixed family-only constants.
- [ ] Replay validation compares against the selected case’s source failure signature.
- [ ] Observability validation compares against the selected case’s source report path and case ID.
- [ ] `README.md` documents the additive `--case-id` and `--suite-id` usage without changing the canonical default reviewer flow.
- [ ] `docs/WEB_DEMO_README.md` clarifies that the family default remains the canonical reviewer closure path, while generic selectors are additive tooling.
- [ ] No `.env`, API key, token, secret, or generated `var/` artifact is tracked by git.
- [ ] The working tree is clean after commit.

## 9. Verification Commands

```bash
python -m pytest tests/test_recovery_replay_review.py tests/integration/test_recovery_replay_review.py -q
python -m pytest tests/test_review_evidence.py tests/test_demo_support_scripts.py -q
python scripts/run_recovery_replay_review.py
python scripts/run_recovery_replay_review.py --case-id family_route_and_dining_unavailable_v1
python scripts/run_recovery_replay_review.py --suite-id recovery_focused
git diff --check
git status --short
```

## 10. Expected Commit

```text
feat: generalize recovery replay review
```

## 11. Notes for the Implementer

Keep this task focused on generalizing the existing closure tooling, not changing recovery behavior itself.

Important defaults chosen for this task:

- default behavior remains `family_route_failure_v1`
- supported suite selection is limited to `recovery_focused` and `failures`
- per-case schema compatibility is mandatory
- generic suite support is additive through a new run-level report
- the canonical family latest alias must remain unchanged
- non-recovery cases must be rejected explicitly rather than “best-effort” executed

If implementation pressure starts pulling in frontend replay browsing, new benchmark fixtures, or integrity dashboard work, stop and keep that for Tasks `100+`.
