# AIGC Studio

面向抖音 / B 站 / YouTube / Instagram 的 AI 短剧自动化生产工作流。

参考 Seedance、可灵（Kling）等工具实现电视剧/电影质感的短剧内容，采用**混合技术栈**
（Python 编排 + 付费 API 生成核心素材）、**关键环节人工审核**、**成本与质量平衡**的路线。

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
