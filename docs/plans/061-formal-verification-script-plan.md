# Plan: 061 Formal Verification Script

## 1. Spec Reference

Spec file:

```text
docs/specs/061-formal-verification-script.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/customer-demo-replan-flow-v0`。
- `docs/specs` 与 `docs/plans` 已连续到 `060`，且编号完全匹配。
- 最新 task commit 是 `dbe50d9 feat: add customer demo replan flow`，说明 `060` 已经提交并推送。
- 当前没有更新编号的 spec/plan，也没有 git 历史覆盖 `docs/COMPETITION_SUBMISSION_DESIGN.md` 或 `docs/artifacts/benchmark-all-registered-formal-report.json`，它们是本地草稿，不是已正式落地的 task 输出。
- 现有 benchmark harness 已支持 `run_suite("all_registered")`，并会把 suite report 写到可配置 `report_dir`。
- 现有 benchmark reporting 已负责 JSON 清洗，因此 formal verification 不应复制或绕过这层逻辑。
- 当前工作树有无关本地脏文件：`.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`。执行本 plan 时必须保持它们 unstaged。
- `var/` 已忽略，适合作为 formal verification 的输出根目录。

## 3. Files to Add

- `backend/app/benchmark/formal_verification.py` - formal verification orchestration、runtime bootstrap、success/failure gating、CLI `main(...)`。
- `scripts/run_formal_verification.py` - repo-root 一键入口，调用 formal verification `main(...)`。
- `tests/test_formal_verification.py` - unit tests for orchestration, latest alias refresh, failure exit code, bootstrap error handling.
- `tests/integration/test_formal_verification.py` - integration test that runs the current `all_registered` suite through the formal verification entrypoint with real PostgreSQL/Redis and temp output paths.

## 4. Files to Modify

- `README.md` - add a dedicated formal verification section with the exact command, prerequisites, output locations, and the meaning of the latest alias file.

## 5. Implementation Steps

1. 阅读并确认现有 benchmark 执行与输出边界。
2. 以 `backend/app/benchmark/harness.py`、`backend/app/benchmark/reporting.py`、`backend/app/benchmark/suites.py` 为基线，确定 formal verification 只做 orchestration，不复制 suite execution、report serialization 或 sanitization。
3. 在 `backend/app/benchmark/formal_verification.py` 中定义一个内部结果对象，至少包含：
   - `suite_id`
   - `run_status`
   - `case_count`
   - `passed_count`
   - `failed_count`
   - `error_count`
   - `overall_score`
   - `run_directory`
   - `suite_report_path`
   - `latest_report_path`
   - `trace_buffer_path`
4. 在同一模块中实现 runtime bootstrap helper。
5. bootstrap helper 必须按这个顺序工作：
   - 运行 `docker compose up -d postgres redis`
   - 轮询 PostgreSQL 与 Redis readiness，直到连接成功或超时
   - 执行 Alembic upgrade head
6. readiness 轮询不要引入新依赖。
7. PostgreSQL readiness 使用现有 SQLAlchemy session/engine 进行轻量连接检查。
8. Redis readiness 使用现有 Redis client 的 `ping()`。
9. bootstrap 失败时抛出清晰异常，供 CLI 转换为非零退出码和 stderr 文案。
10. 在 `backend/app/benchmark/formal_verification.py` 中实现 formal run path builder。
11. 默认输出根目录固定为 `var/formal-benchmarks`。
12. 每次运行生成唯一目录 `formal-<uuid>`。
13. trace buffer 文件固定放在唯一目录下，例如 `formal-traces.jsonl`。
14. stable latest alias 固定为 `var/formal-benchmarks/latest-all_registered-run-report.json`。
15. 在 `backend/app/benchmark/formal_verification.py` 中实现正式验证主流程：
   - bootstrap runtime
   - 构造 `BenchmarkHarness`
   - 指定本次唯一 `report_dir`
   - 指定本次唯一 `trace_buffer_path`
   - 调用 `run_suite("all_registered")`
16. formal verification 主流程必须校验：
   - `suite_id == "all_registered"`
   - `run_status == "passed"`
   - `failed_count == 0`
   - `error_count == 0`
   - `report.report_path` 非空且文件存在
17. 只有在第 16 步全部满足时，才把 suite report 拷贝到 latest alias。
18. latest alias 必须直接复制 suite report 文件内容，不得重写 JSON 内部字段。
19. 如果 suite run 失败或报错，保留唯一运行目录，不更新 latest alias，并把失败信息返回给 CLI。
20. 为 CLI 生成统一的 human-readable summary formatter，成功时打印 suite/case/score/timing/path 信息，失败时打印简洁错误信息。
21. 在 `scripts/run_formal_verification.py` 中实现 repo-root wrapper，仅负责调用 `backend.app.benchmark.formal_verification.main()` 并把返回值映射为进程退出码。
22. 在 `tests/test_formal_verification.py` 中添加 formal verification unit tests。
23. 单测至少覆盖：
   - 成功路径会调用 bootstrap、执行 `all_registered`、写 unique run dir、刷新 latest alias
   - latest alias 是拷贝而不是 JSON rewrite
   - suite 失败时 latest alias 不更新
   - bootstrap 失败时 CLI 返回非零退出码
24. 单测中对 `docker compose`、readiness、Alembic、`BenchmarkHarness.run_suite(...)` 做 monkeypatch，避免真实 infra 依赖。
25. 在 `tests/integration/test_formal_verification.py` 中添加正式验证集成测试。
26. 集成测试调用正式验证主流程，而不是直接调 harness。
27. 集成测试使用临时 `output_root`，避免写入共享目录。
28. 集成测试可设置 `start_services=False`，依赖测试命令预先执行的 `docker compose up`；但迁移执行逻辑应继续走正式 runner 本身。
29. 集成测试至少断言：
   - 返回 suite ID 为 `all_registered`
   - `run_status == "passed"`
   - `failed_count == 0`
   - `error_count == 0`
   - unique suite report 存在
   - latest alias 存在
   - latest alias 内容仍保留内部 `report_path` 指向 unique run dir
   - 输出报告不包含被 reporting 层禁止的敏感 key
30. 更新 `README.md`。
31. README 新增正式验证 section，明确：
   - 入口命令是 `python scripts/run_formal_verification.py`
   - 会自动启动 `postgres` 和 `redis`
   - 会自动运行 Alembic
   - 输出在 `var/formal-benchmarks/`
   - stable latest alias 是 `var/formal-benchmarks/latest-all_registered-run-report.json`
   - 本 task 不会自动发布到 `docs/artifacts/`
32. 运行本 plan 的验证命令。
33. 只 stage 本 task 文件与本 task 的 spec/plan。
34. 提交前再次确认 `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`、`var/` 保持 unstaged。

## 6. Testing Plan

- Unit tests: `tests/test_formal_verification.py`
- Unit tests must cover successful orchestration, latest alias refresh rules, bootstrap failure handling, and non-zero exit code behavior.
- Unit tests must monkeypatch runtime/bootstrap and benchmark harness rather than using real PostgreSQL/Redis.
- Integration tests: `tests/integration/test_formal_verification.py`
- Integration tests must run the formal verification entrypoint against real PostgreSQL/Redis and the real current `all_registered` suite, but write to temp output directories.
- Integration tests must assert unique report creation, latest alias creation, passing suite summary, and sanitized JSON output.
- Regression tests: keep `tests/test_benchmark_harness.py` and `tests/test_benchmark_suites.py` in the focused verification set so the new runner does not accidentally change suite membership or benchmark report semantics.
- Regression integration: keep the `all_registered` path in `tests/integration/test_benchmark_harness_gateway.py` in the focused verification set so the formal runner and direct harness path stay aligned.
- Smoke test: run `python scripts/run_formal_verification.py` from repo root after focused tests pass.

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_formal_verification.py tests/test_benchmark_harness.py tests/test_benchmark_suites.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_formal_verification.py tests/integration/test_benchmark_harness_gateway.py -k "formal_verification or all_registered" -v
python scripts/run_formal_verification.py
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: add formal verification script
```

Expected commands:

```bash
git status --short
git add README.md backend/app/benchmark/formal_verification.py scripts/run_formal_verification.py tests/test_formal_verification.py tests/integration/test_formal_verification.py docs/specs/061-formal-verification-script.md docs/plans/061-formal-verification-script-plan.md
git commit -m "feat: add formal verification script"
git push -u origin codex/formal-verification-script
```

The implementer must confirm `.env`、secrets、`.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc`、`var/` are not staged.

## 9. Out-of-scope Changes

- Do not change benchmark suite definitions, case fixtures, taxonomy, score rules, replay rules, or harness output schema.
- Do not modify `docs/COMPETITION_SUBMISSION_DESIGN.md` or publish any tracked artifact into `docs/artifacts/`.
- Do not add frontend, public API, internal observability, migration, or dependency changes.
- Do not add GitHub Actions, package entry points, shell-specific wrappers, or extra developer tooling beyond the Python runner and README notes.
- Do not revert or absorb the current local `.gitignore` change or any other pre-existing dirty file that is unrelated to task `061`.

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] `python scripts/run_formal_verification.py` is the repo-root one-click entrypoint.
- [ ] The runner starts runtime dependencies, waits for readiness, runs Alembic, and then runs `all_registered`.
- [ ] Unique formal run directories are created under `var/formal-benchmarks/`.
- [ ] The latest alias is refreshed only on success.
- [ ] The latest alias is a copy and does not rewrite nested `report_path` values.
- [ ] Required tests and smoke commands passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, secret, `var/`, or unrelated local draft file was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- The exact verification commands run and whether each passed
- The exact success summary from `python scripts/run_formal_verification.py`
- The exact unique formal run directory produced during smoke verification
- Commit hash
- Push result
- Confirmation that `.gitignore`、`docs/COMPETITION_SUBMISSION_DESIGN.md`、`docs/NEXT_PHASE_ROADMAP.md`、`docs/TASK_WORKFLOW_PROMPTS.md`、`docs/artifacts/`、`qc` and `var/` were not staged
- Whether a follow-up task should formalize submission-doc publication from the runner output
