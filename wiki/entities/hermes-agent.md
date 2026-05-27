---
title: Hermes Agent
created: 2026-05-17
updated: 2026-05-27
type: entity
tags: [agent, ops, macos]
sources: [_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops.md]
confidence: high
---

# Hermes Agent

Hermes Agent 是一个先进的多模态大语言模型（LLM）端到端框架。它的底层设计高度注重工程化实践与全栈运维集成，使得其可以在多环境（如本地 macOS 以及公有云环境）稳定长期运行。

## 核心架构与环境集成

在 macOS 等本地环境下，Hermes Agent 被设计为与系统的底层守护进程（Daemon）紧密融合：

- **进程拓扑**：Hermes 作为一个长期运行的常驻 Gateway 进程启动。它集成了飞书 (Feishu) Bot、定时任务 (Cron)、Dashboard 及 API 提供服务。
- **环境隔离**：使用高速 Python 包管理器 `uv` 在独立虚拟环境中构建隔离运行依赖。^[[[_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

## 多模型 Fallback 机制

Hermes 框架内置了强大的模型冗余与故障转移能力，旨在降低生产环境的推断停机时间：

- **主模型 (Main Model)**：原生支持无缝桥接至企业级云端算力节点。例如将流量接入到基于 Google GCP Service Account 鉴权的 **Vertex AI** 兼容端点上。由于该 Token 具备时效限制（通常为 1 小时），需要搭配系统的 `launchd` 以及唤醒守护脚本（Wake Watcher）自动刷期。
- **备用模型 (Fallback Model)**：当主端点由于网络抖动、频控或限流导致 4xx/5xx 报错时，系统会自动切轨到备用提供商（例如阿里云的 DashScope/Qwen），直到原通道恢复。^[[[_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

## 核心演进

Hermes 是前代智能体架构 OpenClaw 的继任者，不仅支持核心技能与记忆库的无缝平滑迁移，更是强化了如 MCP (Model Context Protocol) 协议与 PTY 交互终端的内置能力。^[[[_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

## 连续对话调度

Hermes Gateway 在用户 mid-turn 追加输入时实现了 [[agent-mid-turn-input-modes]] 三种调度模式（interrupt / queue / steer），通过 `/busy` 命令热切换；其中 `steer` 模式利用工具调用边界注入引导上下文，避免破坏 Prompt Cache。^[[[_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

---

**相关图谱概念**:

- 所属类别：[[agent-frameworks]]
- 底层交互协议关联：[[markdown-llm-protocol]]
- 历史继任前代实体：[[openclaw]]
- 连续对话机制：[[agent-mid-turn-input-modes]]
