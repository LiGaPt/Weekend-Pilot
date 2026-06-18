# Plan: 116 Mock World Scenario Taxonomy Expansion v0

## 1. Spec Reference

Spec file:

```text
docs/specs/116-mock-world-scenario-taxonomy-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

Roadmap reference:

```text
docs/NEXT_PHASE_ROADMAP.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/115-customer-observability-ui-split-v0`。
- 最新提交是 `bfc88fd feat: split customer and observability plan detail surfaces`，对应 Task `115`。
- `docs/specs` 和 `docs/plans` 已连续且 slug-matched 到 `115`，其中 `113.5` 是已接受的插入型任务，不构成断档。
- 当前仓库已经包含 expanded Mock World assets：
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
  - `elder_afternoon`
- 当前 canonical suite baseline 是：
  - `default = 11`
  - `expanded = 5`
  - `recovery_focused = 8`
  - `v2_integrity = 20`
  - `all_registered = 30`
- 当前工作树有与本任务无关的未跟踪文件：
  - `docs/NEW_WORKFLOW_PROMPT.md`
  - `docs/TASK_INFO.md`
  - `docs/superpowers/`
- 这些无关文件在实现时必须保持 untouched。

## 3. Files to Add

- `tests/test_mock_world_scenario_taxonomy.py` - focused regression file that locks the current Mock World scenario breadth, supported profiles, and canonical suite counts in one place.

## 4. Files to Modify

- `tests/test_benchmark_v2_taxonomy.py` - replace stale `28` / `18` expectations with the current inventory and summary counts.
- `tests/test_benchmark_suites.py` - update only if any stale suite-count or matrix-summary assumption is still present.
- `README.md` - update only the Mock World / benchmark taxonomy wording needed to match the current scenario breadth and current suite counts.
- `docs/WEB_DEMO_README.md` - update only if stale family-only or obsolete inventory wording is still present.

## 5. Implementation Steps

1. Inspect the current source of truth before editing.
   - Read `backend/app/benchmark/fixtures.py`, `backend/app/benchmark/suites.py`, `backend/app/benchmark/schemas.py`, and `backend/app/benchmark/matrix.py`.
   - Confirm the canonical counts are still `30 / 20 / 8 / 11 / 5`.
   - Search for stale `28` or `18` references with `rg -n "28|18" tests README.md docs/WEB_DEMO_README.md`.

2. Add the focused regression file first.
   - Create `tests/test_mock_world_scenario_taxonomy.py`.
   - Cover all supported Mock World profiles via `load_mock_world(...)`.
   - Assert the current suite counts for `default`, `expanded`, `recovery_focused`, `v2_integrity`, and `all_registered`.
   - Assert the canonical registered case count remains `30`.
   - Keep the test file compact and taxonomy-focused.

3. Update the stale V2 taxonomy test surface.
   - In `tests/test_benchmark_v2_taxonomy.py`, replace the obsolete inventory assertions.
   - Update the registered-case expectation from the stale `28` baseline to the current canonical `30`.
   - Update the focused V2 taxonomy summary expectation from the stale `18` baseline to the current canonical `20` where applicable.
   - Do not broaden the test into unrelated benchmark behavior.

4. Update any remaining stale suite assertions only if they actually exist.
   - Touch `tests/test_benchmark_suites.py` only when the file still contains obsolete counts or stale taxonomy expectations.
   - Keep `backend/app/benchmark/suites.py` unchanged unless inspection proves the suite source of truth itself is wrong.

5. Check documentation consistency last.
   - Review `README.md` and `docs/WEB_DEMO_README.md`.
   - Update only lines that still understate current Mock World breadth or reference an obsolete inventory.
   - Keep the documentation aligned with the current public story:
     - six public demo scenarios
     - benchmark-only elder coverage still exists in canonical Mock World inventory
     - `30 / 20 / 8` remains the current benchmark evidence baseline

6. Run focused verification.
   - Run the unit test group first.
   - Run the integration harness smoke second.
   - Run `rg` again to confirm the stale `28` / `18` references are gone from the focused taxonomy surface.
   - Finish with `git diff --check` and `git status --short`.

7. Stage only task-relevant files and commit.
   - Do not stage unrelated local docs or generated artifacts.
   - Use the exact commit message from the spec.

## 6. Testing Plan

- Unit tests:
  - `tests/test_mock_world_loader.py` must continue to prove all supported profiles load.
  - `tests/test_mock_world_scenario_taxonomy.py` must prove current Mock World breadth and canonical suite counts.
  - `tests/test_benchmark_v2_taxonomy.py` must prove current registered inventory and current V2 taxonomy summary counts.
  - `tests/test_benchmark_suites.py` must remain green and authoritative for suite membership.

- Integration tests:
  - `tests/integration/test_benchmark_harness_gateway.py` must remain green to show the expanded inventory still runs end to end.

- Documentation checks:
  - `README.md` and `docs/WEB_DEMO_README.md` must not contradict the current taxonomy baseline.

## 7. Verification Commands

```bash
python -m pytest tests/test_mock_world_loader.py tests/test_benchmark_suites.py tests/test_benchmark_v2_taxonomy.py tests/test_benchmark_harness.py -q
python -m pytest tests/integration/test_benchmark_harness_gateway.py -q
rg -n "28|18" tests README.md docs/WEB_DEMO_README.md
git diff --check
git status --short
```

## 8. Commit and Push Plan

Expected commit message:

```text
feat: expand mock world scenario taxonomy
```

Expected commands:

```bash
git status --short
git add tests/test_mock_world_scenario_taxonomy.py tests/test_benchmark_v2_taxonomy.py
git add tests/test_benchmark_suites.py README.md docs/WEB_DEMO_README.md
git diff --cached --check
git commit -m "feat: expand mock world scenario taxonomy"
git push -u origin codex/116-mock-world-scenario-taxonomy-v0
```

The implementer must confirm that:
- unrelated untracked local docs remain unstaged
- no `var/` artifacts are staged
- no secrets are staged

## 9. Out-of-scope Changes

- Do not add new Mock World profiles or new benchmark case IDs.
- Do not add a seventh public scenario chip.
- Do not change `backend/app/demo/world_profile.py`.
- Do not change parser rules, workflow routing, confirmation behavior, or recovery policy.
- Do not change `release_gate_v1`, `coverage_gate_v1_5`, `v2_integrity_gate`, or `safe_stop_gate_v1` semantics.
- Do not add dependencies or migrations.
- Do not touch `docs/NEW_WORKFLOW_PROMPT.md`, `docs/TASK_INFO.md`, or `docs/superpowers/`.

## 10. Review Checklist

- [ ] The implementation matches `docs/specs/116-mock-world-scenario-taxonomy-v0.md`.
- [ ] The task stayed a convergence slice and did not turn into a fresh feature wave.
- [ ] The supported Mock World profile set stayed unchanged.
- [ ] The canonical suite counts stayed `11 / 5 / 8 / 20 / 30`.
- [ ] The focused taxonomy regression file clearly locks the current scenario breadth.
- [ ] Stale `28` / `18` expectations were removed from the focused taxonomy surface.
- [ ] `README.md` and `docs/WEB_DEMO_README.md` do not contradict the current taxonomy baseline.
- [ ] Focused unit and integration checks passed.
- [ ] `git diff --check` passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

完成后应回报：

- 新增或修改了哪些测试文件
- 是否发现真实 source-of-truth 漂移，还是仅仅修复了 stale tests / docs
- 当前 canonical Mock World counts 的最终确认值
- 运行了哪些验证命令以及结果
- commit hash
- push 结果
- 是否有后续建议任务，例如更进一步的 scenario matrix generation 或 benchmark taxonomy 自动化检查
