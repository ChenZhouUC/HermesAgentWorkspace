---
title: Hermes Agent
created: 2026-05-17
updated: 2026-09-03
type: entity
tags: [agent, ops, macos]
sources: [_living/AI-Applications/Hermes-Agent-macOS-Ops.md]
confidence: high
---

# Hermes Agent

Hermes Agent 是一个可长期运行的多模态 Agent Runtime，也是 [[agent-harness|Agent Harness]] 的具体实现。它把模型调用、工具编排、会话状态、长期记忆、定时任务、平台适配和本地服务管理组织在同一运行边界内。^[[[_living/AI-Applications/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

## 运行组成

- **Gateway**：承接消息平台和长期运行任务，并由操作系统服务管理器监督。
- **模型路由**：主模型、fallback 和辅助任务可以使用不同 provider/transport；每条路由独立鉴权和验证。
- **状态层**：SOUL、用户画像、长期记忆、会话、cron 和业务数据库构成持久状态，不能与可重建源码混在一起覆盖。
- **能力层**：内置 tools、外部 skills、插件和 [[model-context-protocol|MCP]] 服务共同提供可调用能力；协议接入本身不等同于授权或沙盒。
- **安全层**：平台身份、群聊 allowlist、工具权限、人工审批、进程沙箱和敏感信息脱敏共同限制副作用。

## 运维边界

Hermes 的安装目录不是一个可以整体复制的同质目录。源码与 lockfile 属于可复现代码；SOUL、memory、sessions、cron 和数据库属于目标机状态；`.env` 与 credentials 属于独立的秘密平面；skills、插件和专用运行时则需要按功能 allowlist 迁移。^[[[_living/AI-Applications/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

这种分层决定了升级和跨机器迁移必须使用“重建代码、保留状态、重建配置、逐项授权凭据”的方式。具体决策流程见 [[how-to-migrate-stateful-agent-runtime|如何迁移有状态 Agent Runtime]]。

## 模型与凭据

模型路由应通过配置中的 provider 身份和环境变量引用声明，避免内联密钥。主模型、每个 fallback 和 compression 路由都需要通过 Hermes 自身做最小端到端调用；供应商的模型目录或手写 HTTP 请求不能替代真实 transport 验证。

标准云认证应优先使用 SDK 的原生生命周期。例如 Vertex service account 由进程内认证库获取并刷新短期访问令牌，不需要额外的定时刷新脚本或唤醒守护进程。^[[[_living/AI-Applications/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

## macOS 服务模型

生产运行应由唯一的 gateway LaunchAgent 托管。验证时既要确认 plist 指向当前解释器和源码，也要确认 launchd supervisor 与实际子进程都存在；普通 detached 进程即使有 PID，也不具备登录自启和崩溃拉起语义。

退役旧服务时，必须同时清理脚本、plist、launchd 注册和残留进程。迁移暂存、回滚快照和过程文档只能在验收期存在，用户确认后应从目标机删除。
