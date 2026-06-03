# Plan: 088 Customer Demo Multi-Scenario Chinese Display v0

## 1. Spec Reference

Spec file:

```text
docs/specs/088-customer-demo-multi-scenario-chinese-display-v0.md
```

Project blueprint:

```text
docs/PROJECT_BLUEPRINT.md
```

## 2. Current Repository Assumptions

- 当前分支是 `codex/elder-mock-world-expansion-v0`。
- `git status --short --branch` 显示当前分支跟踪 `origin/codex/elder-mock-world-expansion-v0`，只有无关未跟踪文件 `.git-ssh-known-hosts`。
- 最新完成 task 是 `087`，最新 commit `1e7c361 feat: add elder mock world benchmark coverage` 与 `087` 对应。
- `docs/specs` 与 `docs/plans` 连续、无缺号、slug 对齐到 `087`。
- customer page 已公开六个固定 Mock World scenario chips：
  - `family_afternoon`
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- 当前后端 itinerary 生成文案仍写死：
  - `summary` 使用亲子/清淡晚餐语义
  - `feasibility.reasons` 使用亲子/清淡晚餐语义
  - activity/dining timeline notes 使用亲子/清淡晚餐语义
- 当前前端 `frontend/src/chat/thread.ts` 的中文 display mapping 主要覆盖 family path，五个非亲子公开 profile 仍有英文 `name / address / route summary / tag / target label` 泄漏。
- 当前 `README.md` 与 `docs/WEB_DEMO_README.md` 已将 customer page 描述为 reviewer-facing 中文 surface，因此实际可见输出必须补齐到与文档承诺一致。

## 3. Files to Add

- None.

## 4. Files to Modify

- `backend/app/planning/itinerary_generation.py` - 新增最小内部 `display_copy_profile` 推断，并替换 family-only summary/reasons/timeline notes。
- `tests/test_itinerary_generation.py` - 扩展 helper，增加五个非亲子 profile 的场景 copy regression tests。
- `tests/integration/test_demo_api_gateway.py` - 基于现有 explicit `mock_world_profile` 参数化样例，增加对后端生成文案的场景感知断言。
- `frontend/src/chat/thread.ts` - 补齐五个非亲子公开 fixture 的 `EXACT_USER_TEXT_LABELS`、`INLINE_USER_TEXT_REPLACEMENTS`、`TARGET_ID_LABELS`、`tagLabel()`。
- `frontend/src/chat/thread.test.ts` - 增加 `userFacingText()`、`tagLabel()`、`actionTargetLabel()` 的多场景中文映射断言。
- `frontend/src/chat/ConversationThread.test.tsx` - 增加混合英文 fixture 数据的渲染回归，验证 customer thread 不再显示英文 fallback 或 raw target id。
- `frontend/e2e/demo.spec.ts` - 强化现有 friends-group / preset-selector smoke，对 reviewer 可见文本增加英文泄漏回归断言。
- `README.md` - 将 customer Web demo 描述从 family-localized 调整为 six-chip public surface localized。
- `docs/WEB_DEMO_README.md` - 将 reviewer runbook 文案更新为“公开多场景 customer surface 已中文化”。

## 5. Implementation Steps

1. 新开任务分支，不继续使用已完成的 `087` 分支。
   - 从当前 `HEAD` 新建 `codex/customer-demo-multi-scenario-chinese-display-v0`。
   - 不处理 `.git-ssh-known-hosts`。
   - 不触碰 `docs/specs/087-*`、`docs/plans/087-*` 的已完成内容。

2. 在 `backend/app/planning/itinerary_generation.py` 增加内部场景 copy profile 推断 helper。
   - 新增一个私有 helper，输入至少包含：
     - `QueryPlan`
     - 当前 `_DraftPair`
   - 返回内部字符串之一：
     - `family`
     - `rainy`
     - `budget`
     - `friends`
     - `couple`
     - `solo`
     - `generic`
   - 命中优先级固定为：
     1. `family`
     2. `rainy`
     3. `budget`
     4. `friends`
     5. `couple`
     6. `solo`
     7. `generic`
   - 命中条件固定按 spec 实现，不允许在执行时改顺序或扩出新枚举。

3. 用场景 copy profile 替换后端 family-only 文案。
   - `draft.title` 保持 `"{activity} + {dining}"` 的现有组合方式，不做新模板。
   - 只替换以下可见字段：
     - `draft.summary`
     - `draft.feasibility.reasons`
     - activity timeline note
     - dining timeline note
   - activity/dining note、summary、reasons 必须精确使用 spec 中定义的文本模板。
   - transfer note 与 buffer note 保持现有通用中文文案。
   - `route_text` 继续复用当前已有逻辑；本任务不重做 route summary 算法。

4. 保留后端 fallback contract，不改 public schema。
   - 不修改 `LocalLifeIntent`
   - 不修改 `ScenarioType`
   - 不修改 `DemoRunSummary`
   - 不修改 `DemoPlanPreview`
   - 不把 `display_copy_profile` 写入 API
   - 若所有显式 profile 条件都不命中，则回到 `generic` 模板，而不是回到 `family`

5. 扩展 `tests/test_itinerary_generation.py` 的 helper，使其可参数化构造非 family plan。
   - 扩展 `_intent(...)` 与 `_plan(...)` helper，至少支持：
     - `raw_text`
     - `scenario_type`
     - `adults`
     - `children_ages`
     - `activity_preferences`
     - `dining_preferences`
   - 扩展 `_activity(...)` 与 `_dining(...)` helper，允许传入 tag list，便于触发 rainy/budget/couple copy inference。
   - 保持现有 family regression test 继续成立。

6. 在 `tests/test_itinerary_generation.py` 新增五个非亲子 profile 的精确 copy regression。
   - `friends_gathering`
     - 断言 `summary` 包含 `和朋友散步聊天`
     - 断言 `reasons == ["已选择适合朋友聚会的活动", "已选择适合分享的用餐", "活动到餐厅路线已验证"]`
     - 断言 activity note / dining note 使用 friends 模板
     - 断言不包含 `亲子`
   - `solo_afternoon`
     - 断言 `summary` 包含 `一个人轻松逛逛`
     - 断言 `reasons == ["已选择适合单人放松的活动", "已选择轻量简餐", "活动到餐厅路线已验证"]`
     - 断言不包含 `亲子`
   - `couple_afternoon`
     - 断言 `summary` 包含 `和伴侣慢慢逛`
     - 断言 `reasons == ["已选择适合两人同行的活动", "已选择适合约会节奏的用餐", "活动到餐厅路线已验证"]`
     - 断言不包含 `亲子`
   - `rainy_day_fallback`
     - 断言 `summary` 包含 `室内避雨活动`
     - 断言 `reasons == ["已选择雨天可行的室内活动", "已选择适合雨天的热食简餐", "活动到餐厅路线已验证"]`
     - 断言不包含 `亲子`
   - `budget_lite`
     - 断言 `summary` 包含 `低预算活动`
     - 断言 `reasons == ["已选择免费或低价活动", "已选择预算友好的用餐", "活动到餐厅路线已验证"]`
     - 断言不包含 `亲子`
   - 再加一条 `generic` fallback 测试，验证 ambiguous case 会走 `generic` 文案，而不是 family-only。

7. 在 `tests/integration/test_demo_api_gateway.py` 基于现有 explicit preset 参数化，增加后端 copy 断言。
   - 复用现有 `EXPLICIT_MOCK_WORLD_PRESETS`。
   - 对五个非亲子 profile 新增 selected plan 文案断言：
     - `summary` 使用相应场景模板
     - `feasibility.reasons` 使用相应场景 reasons
     - `timeline[0].notes[0]` 与 dining note 使用相应模板
     - 不再出现 `已选择亲子活动`、`已选择清淡用餐`
   - 不对 API 中仍保留的英文 fixture `name / address / route.summary` 做失败断言；这些字段将在前端 display-layer 被翻译。
   - 保持现有 world_profile persistence 断言不变。

8. 在 `frontend/src/chat/thread.ts` 补齐五个非亲子 fixture 的 display-layer 映射。
   - `EXACT_USER_TEXT_LABELS`
     - 补充当前 customer thread 可直接显示的整句英文 route summary / feedback message / fallback sentence。
   - `INLINE_USER_TEXT_REPLACEMENTS`
     - 补充五个 fixture 当前会进入 customer thread 的英文 `name`、`address`、英文 route summary 片段。
   - `TARGET_ID_LABELS`
     - 为 spec 中列出的 40 个 activity / restaurant target ids 增加中文 label。
   - `tagLabel()`
     - 精确加入 spec 中列出的 22 个 tag 映射。
   - 不修改 `statusLabel()`、`actionLabel()` 等现有已稳定 contract，除非测试明确暴露新的英文漏点。

9. 前端 display mapping 的 source-of-truth 以五个 fixture 文件当前可见字符串为准。
   - 实施时逐个扫描：
     - `friends_gathering.json`
     - `solo_afternoon.json`
     - `couple_afternoon.json`
     - `rainy_day_fallback.json`
     - `budget_lite.json`
   - 只补 customer thread 会显示出来的可见字段：
     - POI name
     - address
     - route summary
     - feedback target label / message
   - 不为当前 customer thread 不显示的 `description` 字段加无用映射。

10. 在 `frontend/src/chat/thread.test.ts` 增加纯函数级回归。
   - 新增 `userFacingText()` 用例，覆盖五个 fixture 中当前残留的英文 route summary 与 English name/address replacement。
   - 新增 `tagLabel()` 用例，覆盖 spec 列出的 22 个新增 tag。
   - 新增 `actionTargetLabel()` 用例，覆盖至少每个 profile 1 个 activity id 和 1 个 dining id，确保不返回 raw target id。
   - 保留现有 family-path mapping tests。

11. 在 `frontend/src/chat/ConversationThread.test.tsx` 增加渲染级回归。
   - 新增一个参数化或 grouped test，构造五个非亲子 profile 的混合英文 `DemoRunSummary` 假数据。
   - 对每个 profile 至少断言：
     - plan heading 为中文
     - candidate line 不显示 English name/address
     - route feasibility 区域不显示 English route summary
     - action / feedback row 不显示 raw target id
     - 至少一个新增 tag 的中文 label 可见
   - 保持现有 family-only localization regression 不删。

12. 强化 `frontend/e2e/demo.spec.ts` 的现有 live smoke。
   - 保留现有 friends-group 路径作为 live browser 主 smoke。
   - 在该 smoke 中增加 reviewer-visible 断言：
     - 展开 `活动与餐厅` 后不再允许 `group_friendly`、`Patio Queue House`、`Quiet Bistro Corner` 之类英文 fallback 可见
     - 展开 `路线与可执行性` 后不再允许 English route summary 可见
   - 保留 `scenario preset selector` 请求体断言。
   - 不新增更多 live scenario smoke；其余四个 profile 由单测和 API integration 覆盖。

13. 更新文档，使其与收口后的 customer surface 一致。
   - `README.md`
     - 将 Web demo/customer surface 的描述从“family-afternoon content localized in Chinese”改为“公开 six-chip Mock World customer surface localized in Chinese”
   - `docs/WEB_DEMO_README.md`
     - 将 Overview 中关于 visible Chinese copy 的描述扩展为六个公开场景
     - 保留 AMap 仍为 API-only read preview 的说明
     - 不扩写新流程，不新增 runbook 章节

14. 运行验证命令，检查 diff scope。
   - 先跑 `tests/test_itinerary_generation.py`
   - 再起 `postgres/redis` 并跑 `tests/integration/test_demo_api_gateway.py`
   - 再跑前端单测与 build
   - 再跑 desktop/mobile smoke
   - 最后检查 `git diff --check` 与 `git status --short --branch`
   - 确认未暂存：
     - `.git-ssh-known-hosts`
     - `.env`
     - `frontend/dist/`
     - Playwright artifacts
     - `var/`

## 6. Testing Plan

- Unit tests:
  - `tests/test_itinerary_generation.py`
    - family 保持原有语义
    - friends/solo/couple/rainy/budget 的 `summary / reasons / notes` 精确命中新模板
    - ambiguous input 回到 `generic`
  - `frontend/src/chat/thread.test.ts`
    - `userFacingText()` 补齐五个 fixture 的可见英文字符串
    - `tagLabel()` 覆盖 22 个新增 tag
    - `actionTargetLabel()` 对五个 profile 不再返回 raw target ids
  - `frontend/src/chat/ConversationThread.test.tsx`
    - 渲染级断言 customer thread 不再显示英文 fallback 或 raw target ids

- Integration tests:
  - `tests/integration/test_demo_api_gateway.py`
    - 基于现有 explicit `mock_world_profile` 参数化，断言 selected plan 的后端生成文案已场景化
    - 保持 world_profile persistence 断言

- Smoke tests:
  - `frontend/e2e/demo.spec.ts`
    - `friends-group` live smoke 断言 reviewer-visible 文本不再泄漏英文
    - `scenario preset selector` smoke 继续验证 explicit `mock_world_profile`
    - mobile no-horizontal-overflow smoke 继续验证布局稳定

- Document review checks:
  - `README.md` 与 `docs/WEB_DEMO_README.md` 都不再把中文化能力表述为 family-only
  - 文档仍准确说明 AMap 是 API-only read preview，不是 customer first-screen selector

## 7. Verification Commands

Commands the implementer must run before committing:

```bash
python -m pytest tests/test_itinerary_generation.py -q
docker compose up -d postgres redis
python -m alembic upgrade head
python -m pytest tests/integration/test_demo_api_gateway.py -k "mock_world_profile" -q
npm --prefix frontend run test -- --run src/chat/thread.test.ts src/chat/ConversationThread.test.tsx
npm --prefix frontend run build
npm --prefix frontend run e2e -- --project=desktop-chromium --grep "friends-group|scenario preset selector"
npm --prefix frontend run e2e -- --project=mobile-chromium --grep "loads the main flow without document-level horizontal overflow"
git diff --check
git status --short --branch
```

## 8. Commit and Push Plan

Expected commit message:

```text
fix: localize multi-scenario customer demo display
```

Expected commands:

```bash
git status --short --branch
git switch -c codex/customer-demo-multi-scenario-chinese-display-v0
git add backend/app/planning/itinerary_generation.py
git add tests/test_itinerary_generation.py tests/integration/test_demo_api_gateway.py
git add frontend/src/chat/thread.ts frontend/src/chat/thread.test.ts frontend/src/chat/ConversationThread.test.tsx
git add frontend/e2e/demo.spec.ts
git add README.md docs/WEB_DEMO_README.md
git commit -m "fix: localize multi-scenario customer demo display"
git push -u origin codex/customer-demo-multi-scenario-chinese-display-v0
```

The implementer must confirm `.env`, `.git-ssh-known-hosts`, `frontend/dist/`, Playwright artifacts, and `var/` are not staged.

## 9. Out-of-scope Changes

- 不新增新的 public scenario chip。
- 不新增新的 public field 或 public response localization contract。
- 不新增 `ScenarioType` 枚举值。
- 不重写 query planner、intent parser、candidate enrichment 或 workflow DAG。
- 不修改 benchmark suite membership、coverage gate、release gate。
- 不修改 internal observability surface。
- 不把 elder 场景加入 customer page。
- 不引入 i18n framework、locale switcher、新依赖或 migration。
- 不把五个 fixture 全量改写成中文源数据。

## 10. Review Checklist

After implementation, the reviewer should check:

- [ ] The implementation matches the spec.
- [ ] The implementation stayed within the plan scope.
- [ ] 当前最新完成 task 仍清晰是 `087`，本次工作是新的 `088`。
- [ ] `itinerary_generation.py` 不再对五个非亲子公开 profile 生成 family-only 文案。
- [ ] `thread.ts` 已覆盖五个 fixture 当前可见的英文 strings、target ids、missing tags。
- [ ] customer thread 不再显示 raw target id、英文 route summary、英文 fallback name/address。
- [ ] public API shape 没变。
- [ ] friends live smoke 仍可跑通 confirm boundary，并且 reviewer-visible 文本已中文化。
- [ ] mobile no-horizontal-overflow smoke 仍通过。
- [ ] 文档表述与实际 customer surface 一致。
- [ ] Required tests or document checks passed.
- [ ] Git status was clean after commit.
- [ ] Commit message matches the plan.
- [ ] Push succeeded.
- [ ] No `.env`, API key, token, or secret was committed.

## 11. Handoff Notes

Add what the implementer should report back after finishing:

- Changed files
- Verification commands and results
- Commit hash
- Push result
- 五个已验证的公开 profile：
  - `friends_gathering`
  - `solo_afternoon`
  - `couple_afternoon`
  - `rainy_day_fallback`
  - `budget_lite`
- 后端新增的 `display_copy_profile` 推断顺序与命中规则
- 前端新增 tag 映射和 target id 映射是否完整覆盖 spec 列表
- customer thread 中已消除的英文 visible strings 范围
- Known limitations or follow-up tasks:
  - elder 仍只在 benchmark，不在 public customer page
  - backend API 仍可包含部分英文 fixture 原值，但 customer thread 已通过 display-layer 显示中文
  - 若后续继续扩新 public scenario，需要复用同一 display-layer 收口方式