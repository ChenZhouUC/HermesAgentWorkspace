---
title: Model Context Protocol (MCP)
created: 2026-07-14
updated: 2026-07-14
type: entity
tags: [protocol, agent, tool]
sources: [_living/AI-Infrastructure/Model-Context-Protocol.md]
confidence: high
---

# Model Context Protocol (MCP)

Model Context Protocol（MCP）是 AI Host 接入外部能力提供方的开放协议。它把原本由每个 Host 分别适配每个工具源的 M×N 集成问题，收敛为 Host 实现 MCP client、能力提供方实现 MCP server 的 M+N 接口问题。MCP 标准化的是能力发现、结构化调用和结果返回，不是模型权重本身的能力。^[[[_living/AI-Infrastructure/Model-Context-Protocol|Model-Context-Protocol]]]

## 三个角色

| 角色       | 职责                                                                           | 不负责什么                    |
| ---------- | ------------------------------------------------------------------------------ | ----------------------------- |
| **Host**   | 面向用户的 AI 应用；持有模型调用权、上下文和最终授权决策                       | 不把外部 server 默认视为可信  |
| **Client** | Host 内部的一对一协议适配器；连接一个 server，负责消息路由、能力协商与生命周期 | 不替模型自主决定业务目标      |
| **Server** | 通过本地进程或远程服务暴露能力                                                 | 不接管 Host 的 Agent 调度循环 |

Host 可以同时维护多个 client；每个 client 对应一个 server，使连接状态、能力、凭证和错误能够分别隔离。

## 三类核心原语

| 原语          | 典型控制方                          | 语义                                  | 副作用边界               |
| ------------- | ----------------------------------- | ------------------------------------- | ------------------------ |
| **Tools**     | 模型提出调用意图，Host 决定是否执行 | 带 schema 的可调用动作                | 可以写入或产生外部副作用 |
| **Resources** | Host、用户或 Host 内部检索逻辑选择  | 由 URI 标识、可读取并注入上下文的数据 | 原语本身按只读素材理解   |
| **Prompts**   | 用户显式触发                        | 参数化消息模板                        | 生成消息，不直接执行动作 |

`tools/list`、`resources/list` 和 `prompts/list` 是 client/host 对 server 的服务发现调用。LLM 不直接向 MCP server 发送 JSON-RPC：Host 先发现、筛选并向模型呈现可见能力，模型输出调用意图后，再由 client 转成 `tools/call`、`resources/read` 或 `prompts/get`。^[[[_living/AI-Infrastructure/Model-Context-Protocol|Model-Context-Protocol]]]

## 传输与版本

- **stdio**：Host 把 server 作为本地子进程启动，以 stdin/stdout 传递 JSON-RPC 消息，适合文件系统、Git、本地数据库等本机工具。
- **Streamable HTTP**：通过 HTTP 请求/响应与可选 SSE 流承载远程连接，适合内网共享或多租户服务。
- **版本与 capability**：实现必须按所用规范版本完成协商或声明，并依据双方 capability 启用功能；session、握手和扩展机制可能随版本演进，不能把某一版的传输细节当成永久不变量。

长期稳定的心智模型是：server 暴露 tools/resources/prompts，client/host 负责发现、筛选、授权和执行，底层使用 JSON-RPC 风格的结构化消息。

## 与 Agent Harness 的边界

MCP 是 [[agent-harness|Agent Harness]] 可以消费的外部能力接入协议，而不是 Agent runtime 本身。它不提供自主循环、上下文压缩、memory、重试策略、HITL 工作流或代码执行隔离；这些仍由 Host/Harness 负责。MCP 也不应替代服务间通用 RPC、消息总线或内部微服务协议。^[[[_living/AI-Infrastructure/Model-Context-Protocol|Model-Context-Protocol]]]

## 安全责任

- `roots`、tool annotations 和 OAuth scope 是边界声明或授权信号，不等同于操作系统级沙盒，也不能自动证明 server 可信。
- Host 应动态裁剪模型可见的能力，对敏感工具设置用户确认，并用独立执行环境、最小文件/网络权限和资源配额限制副作用。
- Resource、Prompt 和 Tool result 都属于外部不可信内容；需要隔离系统指令、限制注入长度，并防范 prompt injection。
- 远程 server 还需处理 token scope/audience、Origin、OAuth state/PKCE 和审计；本地 server 则需控制命令、依赖、环境变量、文件 roots 与供应链来源。

因此，采用 MCP 解决的是“如何用统一接口接入能力”，并不免除 Host 对授权、隔离、审计和结果治理的责任。
