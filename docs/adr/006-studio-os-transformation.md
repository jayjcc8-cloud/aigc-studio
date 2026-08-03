# ADR 006：Studio OS 转型——通用数据层与工作流模板化

- 状态：已接受
- 日期：2026-07-25
- 关联：ADR 005（三引擎定位）、ADR 002（Provider 抽象）

## 背景

ADR 005 把业务定位为多模态内容工作室后，系统需要支撑的不止漫剧一种业务：
产品发布包、游戏宣传、多语言本地化、自有 IP 等都是同一套能力的不同组装。
继续让 `Story/Scene/Shot` 充当系统核心模型，会把每种新业务都变成一次伤筋动骨的改造。

## 仓库审计结论（2026-07-25 实地核实）

仓库为新建 Monorepo，无遗留漫剧系统：A 类（通用基础设施）直接保留；
B 类（Project/Asset/ReviewDecision/prompts）重构保留；C 类冻结项与 D 类
死代码均不存在（自动发布、整季生成、账号矩阵等从未实现）。

## 决策

1. **通用 OS 数据层**：新增 `Workspace / KnowledgeBase / ContentItem / Task /
   Generation / Version / Approval / Export / CostRecord` 九个模型。
2. **ContentItem = 通用外壳 + 类型化 payload**：`content_type + payload: dict`。
   漫剧的 `Story` 作为 `drama_script` 类型的 payload 被引用，**不重写
   Story/Scene/Shot**——可扩展性与已验证链路兼得。
3. **Approval 泛化取代 ReviewDecision**（`entity_type/entity_id/status`，含
   `revision_required`）；ReviewDecision 保留为 deprecated 兼容别名。
4. **ProviderRegistry**：工作流 YAML 按 `(capability, name)` 引用 provider；
   `BaseProvider` 增加 `estimate_cost()`。
5. **工作流模板化**：业务工作流用 YAML 声明（步骤/审批点/预算/重试），
   引擎解释执行；漫剧链路封装为 `ai_drama` 模板，首个新模板为
   `product_launch`（AI 产品海外发布内容包）。
6. **持久化 JSON 先行**：Task/Generation/CostRecord 先落盘为项目目录下的
   JSON 状态文件，模型即 schema，验证后再迁 PostgreSQL。本轮不引入数据库。
7. **交互 CLI 优先**：Web 面板延后到 Phase 2 审核面板一并实现。
8. **失败策略**：第 1 次原参数重试 → 第 2 次降级参数 → 第 3 次转人工，
   不无限重试。

## 后果

- `Project` 扩展 workspace/project_type/多语言/预算/截止日期字段（向后兼容）。
- `Asset` 扩展 source_type/copyright_status/language 等合规字段（ADR 003
  合规要求的落地基础）。
- 存储目录统一为 `projects/{workspace}/{project}/{source,generated,approved,
  exports,archive}`。
- 基线打 tag `archive/ai-drama-v1`。
