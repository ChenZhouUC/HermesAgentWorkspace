---
title: AI Agent Harness
created: 2026-06-03
updated: 2026-07-14
type: concept
tags: [agent, orchestration, harness, architecture]
sources:
  - _living/AI-Infrastructure/AI-Agent-Harness-Engineering.md
  - _living/AI-Infrastructure/Model-Context-Protocol.md
  - _living/AI-Applications/Hermes-Agent-macOS-Ops.md
confidence: high
---

# AI Agent Harness

AI Agent Harness（也称 Agent OS 或 Agent Runtime）是围绕大语言模型（LLM）构建的系统层软件栈，负责将模型从"单次问答"转变为"可自主决策、长期运行、解决复杂任务的智能程序"。^[[[_living/AI-Infrastructure/AI-Agent-Harness-Engineering|AI-Agent-Harness-Engineering]]]

## 核心职责

Harness 接管了 Agent 运行时的基础设施层，开发者只需提供工具（Tools/API）和系统设定（System Prompt），Harness 自动处理：

- **自主循环控制（Autonomous Loop）**：接管 ReAct 循环（Reason → Act → Observe）的底层调度
- **上下文管理（Context Management）**：处理对话历史、长期记忆、上下文窗口溢出、状态持久化
- **工具调用编排（Tool Orchestration）**：解析工具调用请求、验证参数、执行工具、处理错误、返回结果
- **可观测性与容错（Observability & Resilience）**：日志、监控、调试、死循环检测、超时保护

## 五层架构

一个完整的 Harness 通常由以下层次构成：

### 1. 编排层（Orchestration Layer）

接管 Agent 的主循环控制逻辑。典型实现模式：

- **状态机驱动**（如 LangGraph）：显式定义状态转移规则，强确定性
- **事件驱动**（如 AutoGen）：基于消息传递的 Actor 模型，适合多 Agent 协作
- **纯代码循环**（如 Agno）：直接用 while 循环实现 ReAct，极简透明

### 2. 上下文层（Context Layer）

管理 Agent 的"记忆"与"工作区"：

- **短期记忆**：当前对话历史、中间状态、推理轨迹
- **长期记忆**：跨会话的持久化知识（用户偏好、项目约定、历史决策）
- **工作区管理**：虚拟文件系统、任务列表、草稿缓存
- **上下文压缩**：在窗口满时通过摘要、截断、优先级排序保留关键信息

### 3. 沙盒层（Sandbox Layer）

为 Agent 提供安全的代码执行与工具调用环境：

- **代码沙盒**：隔离运行 Agent 生成的代码（Docker、VM、WebAssembly）
- **工具隔离**：限制可访问的 API、文件系统、网络资源
- **资源限制**：CPU/内存/时间配额，防止资源耗尽
- **审计日志**：记录所有工具调用与代码执行

### 4. HITL 层（Human-in-the-Loop）

在关键决策点引入人类监督：

- **决策审批**：高风险操作（删除数据、发送消息）需人类确认
- **实时干预**：人类可随时暂停、修正或接管 Agent
- **可解释性**：展示推理过程、工具调用链、决策依据

### 5. 协议层（Protocol Layer）

定义 Agent 与外部系统的交互标准：

- **工具协议**：如何定义工具（OpenAI Function Calling、MCP）
- **消息协议**：Agent 间的通信格式（Handoff、Event Bus）
- **API 标准**：如何暴露 Agent 为 RESTful API 或 WebSocket 服务

## 与 Agent 框架的区别

Harness 是"底座/运行时"，与"框架"有细微差异：

- **[[agent-frameworks]]** 讨论的是更广义的 Agent 开发工具，包括工作流编排（LangGraph）、多智能体协作（CrewAI）、数据管道（LlamaIndex）等
- **Harness** 特指接管 ReAct 循环的运行时系统，强调自主性与长期运行能力
- 真正的 Harness 包括：Dify、Agno、Pydantic AI、DeepAgents、[[hermes-agent]]
- 不是 Harness 的框架：LangGraph（工作流编排）、LlamaIndex（数据管道）、DSPy（Prompt 编译器）

## 实现案例

本仓库的 [[hermes-agent]]（及其前代 [[openclaw]]）是典型的 Harness 实现：^[[[_living/AI-Applications/Hermes-Agent-macOS-Ops|Hermes-Agent-macOS-Ops]]]

- **编排层**：事件驱动 + 连续对话调度（[[agent-mid-turn-input-modes]]）
- **上下文层**：技能库（skills）+ 记忆系统（memories）+ 工作区
- **沙盒层**：通过独立执行环境、权限控制和资源配额隔离工具副作用；MCP 本身不提供沙盒
- **HITL 层**：飞书 Bot 交互界面，支持实时干预
- **协议层**：通过 [[model-context-protocol|MCP]] 接入外部 tools/resources/prompts，并以 Markdown 等格式承载模型可见内容

这里的协议接入与执行隔离是两个不同职责：MCP 统一 Host 与能力提供方之间的接口，Host/Harness 仍需自行实施授权、沙盒和审计。^[[[_living/AI-Infrastructure/Model-Context-Protocol|Model-Context-Protocol]]]

## 工程原则

生产级 Harness 应遵循：

- **可观测性（Observability）**：日志分层、链路追踪、实时监控、可视化调试
- **容错性（Resilience）**：幂等性保证、超时保护、死循环检测、降级策略
- **安全性（Security）**：最小权限原则、敏感操作审批、输入验证、审计日志
- **成本优化（Cost Efficiency）**：智能缓存、上下文压缩、模型分层、按需计算
