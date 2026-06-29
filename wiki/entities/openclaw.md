---
title: OpenClaw
created: 2026-05-17
updated: 2026-06-29
type: entity
tags: [agent, ops]
sources: [_living/AI-Applications/Hermes-Agent-macOS-Ops.md]
confidence: high
---

# OpenClaw

OpenClaw 是一款较早期的 AI Agent 开源框架，实现了 [[agent-harness|Agent Harness]] 模式，最初采用 NPM 等包管理方式构建，在系统底层通过 `launchd` 进行守护进程管理与唤醒劫持（Override）。

随着大模型框架的工程化演进，基于 Python/uv 构建的 [[hermes-agent]] 取代了其生态位置。Hermes 官方提供了自动化的迁移通道，能够无缝接管并沿用 OpenClaw 遗留的记忆库（Memory）、用户画像（User Profile）以及技能组件（Skills）。^[[[_living/AI-Applications/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

---

**相关图谱概念**:

- 实现模式：[[agent-harness]]
- 所属类别：[[agent-frameworks]]
- 继任框架实体：[[hermes-agent]]
