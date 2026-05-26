# Plan: 066 Memory Governance Release Closure v1

## 1. Spec Reference

Spec file:

```text
docs/specs/066-memory-governance-release-closure-v1.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap context:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- Current branch is `codex/benchmark-release-gate-v0`.
- Latest completed task in the repository is `065`.
- Latest relevant commit is `592c3d6 feat: add benchmark release gate`.
- `docs/specs/` and `docs/plans/` are continuous and matched from `001` through `065`.
- The current repository already contains:
  - `memory_query_policy_v1`
  - the three memory benchmark fixtures
  - the `memory_governance` suite
  - `release_gate_v1`
  - current latest benchmark evidence under `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - current latest benchmark evidence under `var/formal-benchmarks/latest-all_registered-run-report.json`
- The worktree is already dirty before this task. Pre-existing local changes currently visible are:
  - `.gitignore`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/NEXT_PHASE_ROADMAP.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/`
  - `qc`
- This task assumes only `docs/NEXT_PHASE_ROADMAP.md` becomes task-scoped. All other pre-existing local changes must remain unstaged.
- Historical Task `053` documents older suite-count snapshots that are no longer current after Tasks `055` and `065`. This task must not rewrite those historical files.

## 3. Files to Add

- `docs/MEMORY_GOVERNANCE_RUNBOOK.md` - canonical release-facing runbook for the existing memory governance V1 slice.

## 4. Files to Modify

- `README.md` - add a concise `Memory Governance V1` section and link to the new runbook.
- `docs/NEXT_PHASE_ROADMAP.md` - refine the memory-governance milestone wording so it distinguishes the closed read-memory V1 slice from still-open future work.

## 5. Implementation Steps

1. Freeze the current canonical memory-governance contract from code, tests, and reports.
   Inspect:
   - `backend/app/planning/memory_query_policy.py`
   - `backend/app/benchmark/cases/family_memory_override_v1.json`
   - `backend/app/benchmark/cases/family_memory_advisory_fill_v1.json`
   - `backend/app/benchmark/cases/family_memory_expired_advisory_v1.json`
   - `tests/test_memory_query_policy.py`
   - `tests/test_benchmark_suites.py`
   - `tests/test_benchmark_harness.py`
   - `tests/integration/test_benchmark_harness_gateway.py`
   - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
   - `var/formal-benchmarks/latest-all_registered-run-report.json`
   Record the exact V1 runtime truths this task will document:
   - supported keys and normalized values
   - trusted / advisory / weak tier rules
   - user-input precedence behavior
   - exact benchmark-backed case IDs
   - exact release-gate and formal-verification summary counts
   Do not invent broader scope.

2. Write `docs/MEMORY_GOVERNANCE_RUNBOOK.md`.
   Structure it with these exact sections:
   - `Overview`
   - `V1 Scope Boundary`
   - `Rule Matrix`
   - `Benchmark Evidence`
   - `Release Acceptance`
   - `Open Follow-ups`
   The runbook content must include:
   - one matrix row for explicit user override
   - one matrix row for advisory fill
   - one matrix row for expired-memory downgrade
   - one row that documents supported-key scope
   - one row that documents weak / unsupported suppression
   - a clear label for which rows are benchmark-backed and which rows are unit-test-backed only
   - exact evidence mapping for the three benchmark-backed memory cases
   - explicit explanation that `tag_counts.memory_governance == 2` because the override case is tagged `memory_override`, not `memory_governance`
   - blocking acceptance based on `release_gate_v1`
   - broader supporting evidence based on `all_registered`
   - a short future-work list limited to memory CRUD, user controls, and sensitive-data minimization

3. Update `README.md`.
   Add one short `Memory Governance V1` section near the benchmark/release-verification area.
   The section must:
   - summarize the V1 scope in one short paragraph
   - link to `docs/MEMORY_GOVERNANCE_RUNBOOK.md`
   - state that the release contract is benchmark-backed
   - state that V1 remains read-only and does not include memory CRUD or user-facing controls
   Keep README concise and avoid duplicating the full runbook.

4. Update `docs/NEXT_PHASE_ROADMAP.md`.
   Change the memory-governance wording so it no longer reads as if the current slice is absent.
   The update must:
   - keep `M5` open overall
   - explicitly state that the current read-memory governance slice is implemented and benchmarked
   - explicitly list what still remains future work
   Do not reorder the entire roadmap or rewrite unrelated milestones.

5. Validate the documentation against the current repository truth.
   Before staging docs, re-run the focused tests and benchmark scripts.
   Use the refreshed outputs to confirm the runbook and README values exactly match:
   - the three case-level memory outcomes
   - `release_gate_v1` summary counts
   - `all_registered` summary counts
   If any command fails or any value drifts, stop and update the docs only after resolving the factual mismatch with the user.

6. Stage only task-scoped files.
   Stage:
   - `README.md`
   - `docs/MEMORY_GOVERNANCE_RUNBOOK.md`
   - `docs/NEXT_PHASE_ROADMAP.md`
   - `docs/specs/066-memory-governance-release-closure-v1.md`
   - `docs/plans/066-memory-governance-release-closure-v1-plan.md`
   Do not stage:
   - `.gitignore`
   - `docs/COMPETITION_SUBMISSION_DESIGN.md`
   - `docs/TASK_WORKFLOW_PROMPTS.md`
   - `docs/artifacts/`
   - `qc`
   - any `var/` report file

## 6. Testing Plan

- Document review checks:
  - Compare the runbook rule matrix against `backend/app/planning/memory_query_policy.py`.
  - Compare benchmark-backed rows against the three benchmark fixture JSON files and gateway integration assertions.
  - Compare release summary values against refreshed `latest-release_gate_v1-run-report.json`.
  - Compare broader summary values against refreshed `latest-all_registered-run-report.json`.
- Unit tests:
  - `tests/test_memory_query_policy.py`
  - `tests/test_benchmark_suites.py`
  - `tests/test_benchmark_harness.py`
- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py` filtered to memory-policy and release-gate coverage
- Smoke / release checks:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_formal_verification.py`
- Explicit non-tests:
  - no frontend tests
  - no API contract tests
  - no benchmark fixture changes
  - no runtime behavior changes

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_memory_query_policy.py tests/test_benchmark_suites.py tests/test_benchmark_harness.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_benchmark_harness_gateway.py -k "memory_policy or release_gate_v1" -v
python scripts/run_benchmark_release_gate.py
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
docs: close memory governance v1 release scope
```

Expected commands:

```bash
git status --short
git switch -c codex/memory-governance-release-closure-v1
git add README.md
git add docs/MEMORY_GOVERNANCE_RUNBOOK.md
git add docs/NEXT_PHASE_ROADMAP.md
git add docs/specs/066-memory-governance-release-closure-v1.md
git add docs/plans/066-memory-governance-release-closure-v1-plan.md
git diff --cached --check
git commit -m "docs: close memory governance v1 release scope"
git push -u origin codex/memory-governance-release-closure-v1
```

The implementer must confirm the staged set does not include:

- `.gitignore`
- `docs/COMPETITION_SUBMISSION_DESIGN.md`
- `docs/TASK_WORKFLOW_PROMPTS.md`
- `docs/artifacts/`
- `qc`
- `var/`
- any secret or local `.env` file

## 9. Out-of-scope Changes

- Do not modify `backend/app/planning/memory_query_policy.py`.
- Do not modify benchmark fixture content, benchmark suite membership, benchmark schemas, or graders.
- Do not add a new benchmark script or report parser.
- Do not commit refreshed `var/formal-benchmarks/*.json` outputs.
- Do not migrate historical task docs to newer suite counts.
- Do not change unrelated roadmap milestones.
- Do not add new dependencies.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches `docs/specs/066-memory-governance-release-closure-v1.md`.
- [ ] The runbook defines the V1 scope as read-only and narrow.
- [ ] The runbook rule matrix matches the current runtime policy and does not overclaim unsupported behavior.
- [ ] The runbook correctly distinguishes benchmark-backed rows from unit-test-backed-only rows.
- [ ] The three benchmark-backed rows map to the exact expected case IDs and outcome values.
- [ ] The runbook uses the current canonical report paths under `var/formal-benchmarks/`.
- [ ] The documented `release_gate_v1` and `all_registered` counts match the refreshed reports exactly.
- [ ] README links to the runbook and states the acceptance boundary clearly.
- [ ] The roadmap update distinguishes the closed V1 slice from future memory work.
- [ ] No runtime code or benchmark logic changed.
- [ ] Required tests and verification commands passed.
- [ ] No generated benchmark report under `var/` or `docs/artifacts/` was staged.
- [ ] Git status was clean after commit except for the pre-existing unrelated local files outside task scope.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.

## 11. Handoff Notes

After implementation, report back with:

- The exact files changed.
- The refreshed report paths used as evidence:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
- The three documented memory case summaries:
  - override case observed dimension sources and outcomes
  - advisory-fill case observed dimension tier and outcome
  - expired-advisory case observed dimension tier and outcome
- The verification commands that were run and their results.
- The commit hash and push result.
- Confirmation that no runtime behavior changed.
- Confirmation that no `var/` or `docs/artifacts/` report file was committed.
- Any remaining future-work items that still belong to broader M5 memory governance.
