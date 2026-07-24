# AIGC Studio

**面向 AI 产品、App 和独立游戏的多模态内容发布与本地化工作室**（三引擎结构：垂直服务现金流 → 内部自动化软件 → 自有 IP 孵化）。

总体定位（[ADR 005](docs/adr/005-three-engine-studio.md)）：用 AIGC 卖结果，用自动化积累软件资产，用自有 IP 保留非线性收益。精力分配 70/20/10；套餐制服务，不打价格战。

首个垂直场景（[ADR 004](docs/adr/004-business-positioning.md)）：AI 短剧/漫剧——IP 概念样片/试播集/整剧三档交付 + 数据驱动漏斗，同时作为自有 IP 的孵化载体。

生产策略（[ADR 003](docs/adr/003-shot-level-multi-model-routing.md)）：角色参考图驱动的分镜级多模型路由——Wan Flash / Hailuo 跑廉价镜头，HappyHorse 做主力，Wan 2.7 管对白连续性，Kling 救场，Seedance/Gemini 只做 5–10% Hero 镜头；Animatic 先行、配音优先、成本按可用秒核算。

## 策略与决策文档

- [三引擎工作室策略](docs/strategy/three-engine-studio.md)（最新定位）
- [商业策略：B2B + IP 孵化](docs/strategy/business-model.md)
- [生产策略：多模型路由](docs/strategy/multi-model-routing.md)
- [ADR 目录](docs/adr/)（001 Monorepo / 002 Provider 抽象 / 003 多模型路由 / 004 商业定位 / 005 三引擎定位）

## 仓库结构（Monorepo）

```
packages/
  aigc-core/        领域模型、配置、Provider 抽象、流水线骨架
  aigc-generation/  视频/图片生成 Provider（当前为 Dummy 实现）
  aigc-audio/       TTS/音乐/音效/字幕 Provider（当前为 Dummy 实现）
  aigc-editing/     合成与多平台导出（规划中）
  aigc-storyboard/  分镜与角色一致性（规划中）
  aigc-ideation/    选题与剧本生成（规划中）
  aigc-review/      三阶人工审核状态机（规划中）
  aigc-web/         运营/审核 Web 面板（规划中）
projects/           实际短剧项目数据（不入库，仅 .gitkeep）
docs/adr/           架构决策记录
```

## 快速开始

```bash
# 安装（含开发依赖）
pip install -e ".[dev]"

# 代码检查
ruff check packages
black --check packages
mypy packages

# 测试
pytest

# CLI
aigc version
```

## 设计原则

- **Provider 抽象**：视频、TTS、音乐、字幕等能力都面向接口编程，替换
  Seedance/Kling/Runway 等供应商不改业务代码（见 `docs/adr/002`）。
- **配置驱动**：模型名、价格、并发、重试策略走配置，不硬编码进业务逻辑。
- **可审计**：每次生成记录模型、成本、耗时、结果，支撑后续 A/B 与成本优化。
- **三阶人工审核**：剧本 → 分镜/素材 → 成片，关键节点人审后才放行。

## 路线图

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 0 | 工程底座：Monorepo、Provider 抽象、测试骨架 | 进行中 |
| Phase 1 | 手动跑通 MVP：剧本 → 分镜 → 单镜头视频 → 合成 | 未开始 |
| Phase 2 | 半自动化：角色一致性、任务队列、审核面板、多平台导出 | 未开始 |
| Phase 3 | 规模化：数据回流、提示词库、自动发布、成本自动降级 | 未开始 |
