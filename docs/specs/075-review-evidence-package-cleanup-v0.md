# Spec: 075 V1.5 Review Evidence Package Cleanup v0

## 1. Goal

WeekendPilot 的正式代码/benchmark/task 链已经推进到 Task `074`，但当前 reviewer / submission 证据包还没有收口。工作区里存在未跟踪的 `docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/V1_DEVELOPMENT_REPORT.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/` 和 `qc`，其中 submission 草稿仍引用 `docs/artifacts/benchmark-all-registered-formal-report.json` 这份旧的 `17/17` 快照，而仓库当前 canonical V1.5 证据已经切换到 `var/` 下的 latest aliases，并覆盖 `release_gate_v1`、`all_registered` formal verification、`coverage_gate_v1_5` 和 `recovery review`。

这个任务要把 reviewer 入口、正式报告路径、提交材料引用和本地 scratch 归属一次性固定下来。完成后，仓库必须有一个 tracked 的 V1.5 review evidence 总览文档，submission 文档必须引用 canonical latest aliases 而不是 `docs/artifacts/` 的复制件，`.gitignore` 必须明确屏蔽当前本地 scratch / 临时产物，避免 `.env`、`var/`、`docs/artifacts/`、`qc` 以及无关草稿误进入提交。

## 2. Project Context

`docs/PROJECT_BLUEPRINT.md` 将 WeekendPilot 定义为 benchmark-driven、observable-by-default、small-reviewable-tasks 的系统。`docs/NEXT_PHASE_ROADMAP.md` 的默认阶段仍是 `M1. 评测与观测基础设施`，核心目标是把“能跑”收口成“可量化比较、可稳定复现、可直接作为评审基线”。

当前代码和正式 task 已经给出完整的 evidence contract：

- Task `061` 固定了 `python scripts/run_formal_verification.py` 与 `var/formal-benchmarks/latest-all_registered-run-report.json`
- Task `065` 固定了 `python scripts/run_benchmark_release_gate.py` 与 `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- Task `067` 固定了 `python scripts/run_recovery_replay_review.py` 与 `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Task `071` 固定了 release gate 的 latency SLO evidence contract
- Task `074` 固定了 `python scripts/run_benchmark_coverage_gate.py` 与 `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`

所以这个任务仍属于 `M1`，但它不是新增 infra 或新增 benchmark 能力，而是把已有 evidence contract 变成正式 reviewer / submission 使用方式。它的优先级高于继续做 M3/M4 新功能，因为当前最大的风险不是功能缺失，而是“正式代码状态”和“提交材料引用”已经出现漂移。

## 3. Requirements

- Add one new tracked reviewer-facing document:
  - `docs/V1_5_REVIEW_EVIDENCE.md`

- `docs/V1_5_REVIEW_EVIDENCE.md` must become the single canonical entrypoint for local V1.5 reviewer evidence.
- It must list these exact repo-root commands:
  - `python scripts/run_benchmark_release_gate.py`
  - `python scripts/run_benchmark_coverage_gate.py`
  - `python scripts/run_formal_verification.py`
  - `python scripts/run_recovery_replay_review.py`

- It must map those commands to these exact canonical latest aliases:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`

- It must explicitly state that:
  - `docs/artifacts/` is not the source of truth for benchmark or recovery evidence
  - canonical generated evidence stays under `var/`
  - reviewers should cite latest aliases, not copied JSON snapshots under `docs/`

- It must include one explicit ownership section that classifies paths into:
  - official tracked docs
  - local scratch docs
  - generated runtime evidence
  - secrets / local env files

- The default ownership decision for this task must be:
  - official tracked docs:
    - `docs/COMPETITION_SUBMISSION_DESIGN.md`
    - `docs/V1_5_REVIEW_EVIDENCE.md`
  - local scratch / ignored:
    - `docs/V1_DEVELOPMENT_REPORT.md`
    - `docs/TASK_WORKFLOW_PROMPTS.md`
    - `docs/artifacts/`
    - `qc`
  - generated runtime evidence / ignored:
    - `var/`
  - secrets / ignored:
    - `.env`
    - `.env.*` except `.env.example`

- Update `docs/COMPETITION_SUBMISSION_DESIGN.md` so it becomes a tracked official submission-facing doc.
- It must remove the stale reference to:
  - `docs/artifacts/benchmark-all-registered-formal-report.json`
- It must replace that stale reference with:
  - a concise pointer to `docs/V1_5_REVIEW_EVIDENCE.md`
  - canonical latest-alias based evidence wording under `var/formal-benchmarks/` and `var/recovery-reviews/`
- It must not rely on copied benchmark JSON committed under `docs/artifacts/`.

- Update `README.md` with one concise pointer to `docs/V1_5_REVIEW_EVIDENCE.md` as the canonical V1.5 review-evidence entrypoint.
- The README update must stay additive and concise. Do not rewrite existing benchmark sections.

- Update `.gitignore` so the following become ignored:
  - `docs/artifacts/`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `qc`

- Preserve existing ignore behavior for:
  - `.env`
  - `.env.*`
  - `var/`

- Do not ignore:
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `README.md`
  - `docs/V1_5_REVIEW_EVIDENCE.md`

- Do not modify:
  - `backend/`
  - `scripts/`
  - `tests/`
  - `frontend/`
  - any JSON artifact under `var/`

- Do not add new runtime code, benchmark thresholds, suites, report schemas, APIs, or frontend panels.

## 4. Non-goals

- Do not implement unrelated modules.
- Do not change public interfaces outside this task unless listed in this spec.
- Do not commit `.env`, API keys, tokens, or secrets.
- Do not regenerate or overwrite benchmark/recovery outputs under `var/` as part of this task.
- Do not track `docs/artifacts/benchmark-all-registered-formal-report.json`.
- Do not turn `docs/V1_DEVELOPMENT_REPORT.md` into an official tracked deliverable in this task.
- Do not turn `docs/TASK_WORKFLOW_PROMPTS.md` into an official tracked deliverable in this task.
- Do not change benchmark counts, latency SLOs, coverage thresholds, suite membership, or latest-alias semantics.
- Do not add generic artifact publishing automation or new docs/CI tooling in this task.

## 5. Interfaces and Contracts

### Inputs

- Existing latest aliases:
  - `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
  - `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
  - `var/formal-benchmarks/latest-all_registered-run-report.json`
  - `var/recovery-reviews/latest-family_route_failure_v1-review.json`
- Existing docs and local scratch files:
  - `README.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
  - `docs/V1_DEVELOPMENT_REPORT.md`
  - `docs/TASK_WORKFLOW_PROMPTS.md`
  - `docs/artifacts/benchmark-all-registered-formal-report.json`
  - `.gitignore`

### Outputs

- New tracked doc:
  - `docs/V1_5_REVIEW_EVIDENCE.md`
- Updated tracked docs:
  - `README.md`
  - `docs/COMPETITION_SUBMISSION_DESIGN.md`
- Updated ignore contract:
  - `.gitignore`

### Schemas

Expected evidence-package mapping shape:

```json
{
  "review_commands": {
    "release_gate_v1": "python scripts/run_benchmark_release_gate.py",
    "coverage_gate_v1_5": "python scripts/run_benchmark_coverage_gate.py",
    "formal_verification": "python scripts/run_formal_verification.py",
    "recovery_replay_review": "python scripts/run_recovery_replay_review.py"
  },
  "latest_reports": {
    "release_gate_v1": "var/formal-benchmarks/latest-release_gate_v1-run-report.json",
    "coverage_gate_v1_5": "var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json",
    "formal_verification": "var/formal-benchmarks/latest-all_registered-run-report.json",
    "recovery_replay_review": "var/recovery-reviews/latest-family_route_failure_v1-review.json"
  },
  "official_tracked_docs": [
    "docs/COMPETITION_SUBMISSION_DESIGN.md",
    "docs/V1_5_REVIEW_EVIDENCE.md"
  ],
  "ignored_local_paths": [
    "docs/artifacts/",
    "docs/TASK_WORKFLOW_PROMPTS.md",
    "docs/V1_DEVELOPMENT_REPORT.md",
    "qc",
    ".env",
    "var/"
  ]
}
```

## 6. Observability

This task does not add new runtime observability, tracing, benchmark schemas, or persisted metadata.

It must formalize which existing generated artifacts are canonical review evidence:

- `var/formal-benchmarks/latest-release_gate_v1-run-report.json`
- `var/formal-benchmarks/latest-coverage_gate_v1_5-run-report.json`
- `var/formal-benchmarks/latest-all_registered-run-report.json`
- `var/recovery-reviews/latest-family_route_failure_v1-review.json`

It must not:

- copy benchmark JSON into tracked docs/artifact folders
- introduce new “published artifact” directories under `docs/`
- mutate `var/` evidence during documentation cleanup

## 7. Failure Handling

- If any canonical latest alias is missing locally, the new review-evidence doc must instruct the reviewer to run the corresponding existing command first.
- If `docs/COMPETITION_SUBMISSION_DESIGN.md` still contains `docs/artifacts/benchmark-all-registered-formal-report.json`, the task is incomplete.
- If `.gitignore` changes would accidentally ignore an official tracked doc, stop and correct the rule.
- If current hard-coded evidence language conflicts with the latest alias files, align the doc to the latest aliases or remove the stale hard-coded claim; do not keep contradictory wording.
- If implementing this task would require changing benchmark code or regenerating reports to make docs “look correct,” stop and report the conflict instead of widening scope.

## 8. Acceptance Criteria

- [ ] `docs/specs/075-review-evidence-package-cleanup-v0.md` exists and matches this task.
- [ ] `docs/plans/075-review-evidence-package-cleanup-v0-plan.md` exists and matches this task.
- [ ] `docs/V1_5_REVIEW_EVIDENCE.md` exists, is tracked, and is the canonical reviewer-evidence entrypoint.
- [ ] `docs/V1_5_REVIEW_EVIDENCE.md` lists the exact four review commands and the exact four canonical latest report paths from this spec.
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` is tracked and no longer references `docs/artifacts/benchmark-all-registered-formal-report.json`.
- [ ] `docs/COMPETITION_SUBMISSION_DESIGN.md` points readers to `docs/V1_5_REVIEW_EVIDENCE.md` and canonical latest aliases under `var/`.
- [ ] `README.md` contains a concise pointer to `docs/V1_5_REVIEW_EVIDENCE.md`.
- [ ] `.gitignore` ignores `docs/artifacts/`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/V1_DEVELOPMENT_REPORT.md`, and `qc`.
- [ ] Existing ignore behavior for `.env` and `var/` remains intact.
- [ ] `docs/V1_DEVELOPMENT_REPORT.md`, `docs/TASK_WORKFLOW_PROMPTS.md`, `docs/artifacts/benchmark-all-registered-formal-report.json`, `qc`, `.env`, and `var/` evidence do not appear as stageable task outputs after the ignore cleanup.
- [ ] No files under `backend/`, `scripts/`, `tests/`, or `frontend/` are modified by this task.
- [ ] No generated JSON artifact under `var/` is committed by this task.
- [ ] Focused verification commands listed below pass, or any blocker is reported clearly.
- [ ] No `.env`, API key, token, or secret is tracked by git.
- [ ] `git diff --check` passes.
- [ ] The working tree is clean after commit except intentionally ignored local runtime outputs.

## 9. Verification Commands

```bash
python -m pytest tests/test_benchmark_release_gate.py tests/test_benchmark_coverage_gate.py tests/test_formal_verification.py tests/test_recovery_replay_review.py -q
rg -n "python scripts/run_benchmark_release_gate.py|python scripts/run_benchmark_coverage_gate.py|python scripts/run_formal_verification.py|python scripts/run_recovery_replay_review.py" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
rg -n "latest-release_gate_v1-run-report.json|latest-all_registered-run-report.json|latest-coverage_gate_v1_5-run-report.json|latest-family_route_failure_v1-review.json" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
rg -n "docs/artifacts/benchmark-all-registered-formal-report.json" README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
# Expected: no matches
git check-ignore -v docs/artifacts/benchmark-all-registered-formal-report.json docs/TASK_WORKFLOW_PROMPTS.md docs/V1_DEVELOPMENT_REPORT.md qc .env var/formal-benchmarks/latest-all_registered-run-report.json
git ls-files --error-unmatch .gitignore README.md docs/COMPETITION_SUBMISSION_DESIGN.md docs/V1_5_REVIEW_EVIDENCE.md
git diff --check
git status --short
```

## 10. Expected Commit

```text
docs: clean up v1.5 review evidence package
```

## 11. Notes for the Implementer

This is a docs + repository-hygiene convergence task, not a product/runtime task.

Default decisions for this task are fixed:

1. `docs/COMPETITION_SUBMISSION_DESIGN.md` becomes an official tracked submission-facing doc.
2. `docs/V1_5_REVIEW_EVIDENCE.md` becomes the official tracked reviewer-evidence doc.
3. `docs/V1_DEVELOPMENT_REPORT.md` and `docs/TASK_WORKFLOW_PROMPTS.md` remain local scratch and should be ignored, not promoted.
4. `docs/artifacts/` remains non-canonical and ignored.
5. `var/` remains the only canonical location for generated benchmark/recovery evidence.

Do not solve this by copying `var/` JSON into `docs/`. If a future task wants published static artifacts, that must be a separate scoped task with its own spec and plan.
