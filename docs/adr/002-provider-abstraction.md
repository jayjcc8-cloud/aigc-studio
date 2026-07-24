# ADR 002：以 Provider 抽象隔离 AI 供应商

- 状态：已接受
- 日期：2026-07-24

## 背景

短剧工作流重度依赖外部 AI 服务：视频生成（Seedance / 可灵 Kling / Runway）、
配音（ElevenLabs / Fish Audio）、音乐（Suno / Udio）等。这些服务：

- 接口风格差异大（同步/异步、轮询/webhook）；
- 价格、质量、稳定性持续变化，需要频繁 A/B 切换；
- 单一供应商可能限流、涨价或停服。

如果业务代码直接调用某个 SDK，换供应商会演变成全仓库改动（"屎山"主要来源之一）。

## 决策

在 `aigc-core` 中定义一组抽象基类（`VideoProvider`、`ImageProvider`、
`TtsProvider`、`MusicProvider`、`SfxProvider`、`SubtitleProvider`），
统一输入为 `GenerationRequest`、输出为 `GenerationResult`（含成本、耗时、错误信息）。

- 业务流水线只依赖抽象接口，不知道背后是哪家 API。
- 每个供应商是一个独立实现类，通过配置选择启用哪个。
- 所有实现必须提供 Dummy 版本，用于离线开发和 CI 冒烟测试。

## 后果

- 优点：换供应商 = 新增一个类 + 改一行配置；成本/质量可按供应商维度统计对比；
  支持"主供应商失败自动降级到备用"策略。
- 代价：抽象层会损失个别供应商的专有高级参数——通过 `GenerationRequest.params`
  透传缓解，确属关键能力时再升级为一等字段。
