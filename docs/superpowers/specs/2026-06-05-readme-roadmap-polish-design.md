# README 技术路线图与美化设计

日期：`2026-06-05`

## 背景

当前 `README.md` 已经完成中文化，并补齐了项目完成情况、`Mock World`、`Benchmark` 覆盖和测试结果等核心内容。

下一步目标不是继续扩展功能，而是把 `README` 提升为一份更适合评委和外部读者阅读的项目首页：

- 首屏更容易理解当前版本项目的功能闭环
- 清楚展示系统分层与技术支撑
- 让 `Mock World`、`Benchmark`、`Recovery Review` 这些当前版本特点更直观
- 在保持 Markdown 可维护性的前提下，提升整体视觉完成度
- 最终通过 SSH 推送到远程 `GitHub`

## 目标

本次工作需要完成四件事：

1. 为当前版本项目设计一张高可读的技术路线图
2. 将路线图插入 `README.md`
3. 对 `README.md` 做整体美化与结构收束
4. 在完成验证后，通过 SSH 推送到 `origin`

## 非目标

以下内容不在本次范围内：

- 不新增产品功能或 API
- 不改变 `Mock World`、`AMap`、`Benchmark` 的实际行为
- 不改动用户未要求修改的业务逻辑文件
- 不重做整套站点视觉系统，本次只优化 `README` 展示层

## 已确认的设计决策

### 路线图表达方式

路线图采用 `Hybrid` 形式：

- 主路线图使用单独的 `SVG` 文件
- `README.md` 中引用该 `SVG`
- `README` 其余说明继续使用 Markdown 小节、表格和简短说明承接

选择原因：

- 比纯 `Mermaid` 更适合评委阅读
- 比纯内联大图更容易维护
- 能把视觉展示和结构化文档结合起来

### 路线图信息结构

路线图采用 “`C` 为主，加入 `A` 分层感” 的合成方案。

#### 上层：公开用户主链

上层优先展示评委最容易理解的公开产品闭环：

- `5173 Public Demo`
- `Planning Flow`
- `clarification / replan`
- `Human Boundary`
- `confirm / decline`
- `Execution Result`

这部分的目标是先回答“这个系统对用户来说是怎么工作的”。

#### 中层：系统分层

中层加入工程结构层次，让图不只是用户流程图：

- `Frontend Layer`
- `API Layer`
- `Workflow Layer`
- `Gateway Layer`

这部分的目标是回答“这个闭环是如何被系统结构支撑起来的”。

#### 下层：数据面 / 支撑面 / 验证面

下层展示当前版本的核心支撑能力：

- `Mock World`
- `AMap read-only preview`
- `Observability`
- `Benchmark`
- `Recovery Review`

这部分的目标是回答“这个系统为什么稳定、可审计、可验证”。

## README 目标结构

`README.md` 调整后的目标阅读顺序如下：

1. 项目名称与一句话定位
2. 当前版本特点摘要
3. `SVG` 技术路线图
4. `项目完成情况`
5. `Mock World`
6. `启动方式`
7. `Benchmark 覆盖`
8. `测试结果`
9. `详细文档`

### 阅读策略

这个结构的阅读策略是：

- 首屏先让读者理解系统总览
- 中段用结构化章节承接细节
- 下段用 `Benchmark` 和测试结果证明当前状态

## README 美化策略

### 文字层面

- 保持中文为主，仅保留必要专有名词英文
- 压缩过长段落，避免大块说明性文字
- 合并重复信息，避免同一事实在多个章节反复出现
- 将“当前版本特点”前置，而不是埋在细节段落中

### 结构层面

- 保持现有主章节，但提升章节节奏与层次一致性
- 对关键信息使用更紧凑的表格和列表
- 让路线图成为首屏主视觉锚点，而不是附属插图

### 视觉层面

路线图的视觉方向已确认如下：

- 温暖浅底，不使用黑底技术图
- 使用三组颜色区分层次：
  - 绿色：用户主链
  - 蓝色：系统层
  - 金色：数据面与支撑面
- 标题、卡片和分区要更像作品展示页，而不是内部白板

## Mock World 在路线图中的表达

`Mock World` 在路线图和 `README` 说明中必须准确表达以下事实：

- 它是当前公开 demo、正式 `Benchmark` 与大部分自动化验证的默认确定性数据面
- 它不依赖外部地图或真实写接口
- 它不是只包含“最终标准答案点位”
- 它故意包含额外候选、`distractor`、不可用候选，以及部分 `route` 不可行组合
- 它承担的是筛选、`fallback`、排序稳定性、安全停机等能力验证职责

## Benchmark 在 README 中的表达

`README` 需要保留当前 canonical latest evidence 的核心事实，但不堆叠过长实现细节。

必须保留的重点包括：

- `release_gate_v1` 当前通过状态
- `coverage_gate_v1_5` 当前通过状态
- `all_registered` 当前通过状态
- `family_route_failure_v1` recovery review 当前通过状态
- 当前版本的重要覆盖特征：
  - 场景广度
  - world profile 分布
  - 代表性 tag 覆盖
  - failure mode 与 recovery 链

## 文件与交付物

本次改动的目标交付物包括：

- 更新后的 `README.md`
- 新增的路线图 `SVG` 文件
- 如有必要，新增或调整 README 相关测试

路线图文件应放在仓库内、适合 README 引用的位置，并保持路径稳定。

## 验证要求

在宣称完成前，至少要重新验证以下内容：

- `README` 相关契约测试
- `review_evidence` 相关测试
- 当前 `README` 中引用的前端聚焦测试命令

目标验证命令：

```bash
python -m pytest tests/test_demo_support_scripts.py tests/test_review_evidence.py -q
npm --prefix frontend test -- --run src/chat/ConversationThread.test.tsx src/App.test.tsx
```

## Git 与推送要求

完成实现并通过验证后：

- 检查当前工作区状态
- 只提交与本次 `README` / 路线图 / 必要测试相关的变更
- 使用现有 `origin` 远程
- 通过 SSH 推送当前分支到 `GitHub`

当前已知远程：

- `origin = git@github.com:LiGaPt/Weekend-Pilot.git`

## 风险与控制

### 风险 1：路线图太像工程图

控制方式：

- 保持用户主链在视觉上优先
- 避免整张图只剩模块盒子

### 风险 2：路线图太像海报，缺少技术层次

控制方式：

- 保留 `Frontend / API / Workflow / Gateway` 分层
- 将 `Mock World / Benchmark / Recovery` 放入明确的支撑层

### 风险 3：README 信息过度重复

控制方式：

- 路线图只做总览
- 细节章节只解释图中各层，不重复整段概述

### 风险 4：推送时误带无关改动

控制方式：

- 提交前明确核对文件清单
- 只暂存与本次任务相关的文件

## 实施顺序

1. 设计并生成路线图 `SVG`
2. 将路线图插入 `README.md`
3. 收束并美化 `README.md`
4. 如有必要，更新 `README` 相关测试
5. 运行聚焦验证
6. 检查 git 状态
7. 提交并通过 SSH 推送

## 当前结论

本次实现应以 `SVG 主图 + Markdown 结构承接` 为中心，目标不是“再加一点说明”，而是把 `README` 升级为当前版本项目的正式首页，总结当前功能特点，并让 `Mock World`、`Benchmark`、`Recovery Review` 的价值更容易被评委理解。
