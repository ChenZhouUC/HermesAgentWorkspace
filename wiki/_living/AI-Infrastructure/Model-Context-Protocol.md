---
title: Model Context Protocol (MCP)
created: 2026-06-14
updated: 2026-07-13
---

> **关于版本**：截至 2026-07-13，MCP 当前标记为 Current 的规范版本仍是 `2025-11-25`。官方已经公开面向 `2026-07-28` 的 release candidate / draft，但本文仍以 Current 版本为实现基线；draft / RC 内容只作为“下一版观察项”，不混入现行实现要求。具体字段名、错误码、能力标志请以 modelcontextprotocol.io 的最新 schema 为准；本文不追求与某次微小修订完全字面一致，而是抽取**长期不变的工程要点**。

# Model Context Protocol：缘起、设计与实现

## 一、缘起：为什么需要 MCP

### 1.1 大模型的“上下文孤岛”问题

LLM 在原始形态下是一个**无状态的、与世界隔离的**函数：输入文本进、输出文本出。它没有文件系统、没有数据库、没有最新邮件、没有公司 wiki。所有能力都来自训练语料的“封存知识”。

工程上为了打破这种孤岛，有三条路线：

1. **RAG（检索增强生成）**：把外部知识先索引，再按需注入 prompt。问题是检索质量不可控，且只能“读”不能“写”。
2. **Function / Tool Calling**：让模型输出结构化的函数调用意图，宿主程序执行后回填结果。问题是各家 API 形态不同，每个工具都要为每个模型/客户端各写一遍适配。
3. **完整的 Agent 框架**：把工具调用、对话循环、记忆、错误处理全部封装。问题是框架本身又成了一个不互通的“小宇宙”。

### 1.2 M×N 集成爆炸

更深层的问题是 **M×N 集成**：

- 有 M 个 AI 宿主（Claude Desktop、Cursor、Cline、Continue、Zed、Goose……）
- 有 N 个工具源（GitHub、Slack、Postgres、本地文件系统、Jira、Notion……）
- 朴素做法需要 M×N 个集成器；每加一个宿主或工具，扩张都是乘法级的。

LSP（Language Server Protocol）在 2016 年解决了同构问题：M 个编辑器 × N 种编程语言 → M+N 个适配。MCP 就是把这套思路搬到 AI Agent 与工具源之间。

### 1.3 协议化的本质收益

引入一层标准协议后，工程上获得的是：

- **解耦**：工具作者只针对协议实现 server，不关心是哪个 AI 宿主调用；宿主作者只实现一次 client，可消费任意 server。
- **可组合**：一个宿主可同时挂多个 server（文件系统 + git + Slack），并发提供能力。
- **可治理**：协议规定了 capability 协商、权限边界、生命周期，给 OAuth / 审计 / 沙盒留出明确的 hook 点。
- **可演化**：协议版本化后，新功能可以在双方都支持时启用，不破坏老 client/server。

## 二、历史来源与设计灵感

### 2.1 直接前身：Anthropic 的 Tool Use 与 OpenAI Function Calling

- 2023 年中，OpenAI 推出 Function Calling，确立了“模型输出 JSON 工具调用 → 宿主执行 → 回填结果”的范式。
- 2024 年，Anthropic 在 Claude 3 中提供了同质的 Tool Use API（结构上是 `tool_use` / `tool_result` 内容块，更贴合多模态的“内容数组”模型）。
- 但这些都是**模型 - 客户端**之间的 API 约定，工具本身是宿主进程内的 Python/TS 函数，跨宿主无法移植。

### 2.2 显性灵感：Language Server Protocol（LSP）

MCP 的整体形态明显师承 LSP：

| 维度 | LSP                                           | MCP                                            |
| ---- | --------------------------------------------- | ---------------------------------------------- |
| 传输 | JSON-RPC 2.0 over stdio/socket                | JSON-RPC 2.0 over stdio/HTTP                   |
| 握手 | `initialize` + capability 协商                | `initialize` + capability 协商                 |
| 角色 | Editor (client) ↔ Language Server             | AI Host/Client ↔ MCP Server                    |
| 原语 | hover / completion / definition / diagnostics | tools / resources / prompts                    |
| 通知 | server→client 推送诊断信息                    | server→client 推送 list_changed、log、progress |

LSP 的核心智慧 MCP 全盘继承：**让客户端“哑”一点，把领域知识封在 server 里**；客户端只需懂协议，不需要懂每种工具的内部语义。

### 2.3 协议本身：JSON-RPC 2.0

MCP 直接复用 [JSON-RPC 2.0](https://www.jsonrpc.org/specification)：

- 三种消息：`request`（带 `id`，要求回复）、`response`（带相同 `id`）、`notification`（无 `id`，单向）。
- 错误格式标准化：`{ code, message, data? }`。
- 双向请求：MCP 的特点之一是 server 也可以向 client 发请求（如 sampling、roots 查询），而不仅仅是 client → server。

选 JSON-RPC 而非 REST/gRPC 的原因：

- 文本流友好（适配 stdio 进程间通信）；
- 双向语义天然（server 主动通知客户端是一等公民，不需要 webhook/long-polling 绕路）；
- LSP 已经验证其工程可行性。

## 三、发展历程

> 时间线只列关键里程碑；具体小版本号以官方 changelog 为准。

- **2024-11-25**：Anthropic 宣布 MCP，并开放初版规范（协议版本 `2024-11-05`）、TypeScript / Python SDK，以及一批 reference servers（filesystem、git、postgres、sqlite、slack、github、gdrive、puppeteer 等）。Claude Desktop 成为最早的本地主机之一。
- **2024 年末 ~ 2025 年初**：第三方宿主迅速加入——Cline、Continue、Cursor、Zed、Goose、Sourcegraph Cody、Windsurf 等编辑器/Agent 工具陆续支持 MCP。
- **2025-03-26**：规范大幅修订。最重要的变化：
  - **Streamable HTTP transport** 替代早期的 HTTP+SSE 双端点设计，统一为单端点；
  - **OAuth 2.1 授权框架**进入规范；
  - 增加 JSON-RPC batching、tool annotations、audio content、progress message、completion capability 等能力。
- **2025-06-18**：规范继续收敛生产实现经验：
  - **移除 JSON-RPC batching**，回到单消息请求，降低传输和状态管理复杂度；
  - 增加 **structured tool output**、tool result 中的 **resource links**、**elicitation**；
  - 强化 OAuth Resource Server / Protected Resource Metadata、Resource Indicators、安全最佳实践；
  - HTTP 后续请求要求携带协商后的 `MCP-Protocol-Version`。
- **2025-11-25**：当前稳定规范。主要变化包括：
  - 支持 OpenID Connect Discovery；
  - 工具、资源、提示可带 icons 等展示元数据；
  - OAuth 推荐引入 Client ID Metadata Documents，DCR 退为兼容/回退机制；
  - sampling 可带 `tools` / `toolChoice`；
  - URL mode elicitation、枚举 schema 改进；
  - 引入实验性的 **Tasks**，用于长任务、轮询和延迟取结果；
  - JSON Schema 2020-12 成为默认 schema dialect；
  - 项目治理、Working Groups / Interest Groups、SDK tiering 逐步制度化。
- **2026**：MCP 从“Anthropic 提出的协议”演化为多公司共同维护的开放标准，项目治理落在 LF Projects LLC 体系下；官方 MCP Registry 进入 preview；路线图把重点放在可扩展传输、无状态/可横向扩展部署、Server Cards、Tasks 生命周期、企业审计/鉴权/网关、conformance tests 上。面向 `2026-07-28` 的 release candidate / draft 已经把 stateless core、MCP Apps、Tasks extension、Skills over MCP、Multi Round-Trip Requests（MRTR）等方向写入草案，但在正式发布前不作为本文的稳定实现基线。

值得注意的是：截至 `2025-11-25 Current`，协议的**核心面（三原语 + JSON-RPC + initialize 握手）**保持稳定，演化主要集中在传输层、鉴权、安全、可观测性、长任务和“长尾扩展能力”上。但 `2026-07-28` draft 明确开始重构 protocol-level session 与初始化模型，所以更长期的稳定心智模型应当收敛为：**server 暴露 tools/resources/prompts，client/host 负责发现、筛选、授权与执行，底层仍是 JSON-RPC 风格的结构化消息**；不要把 `initialize`、`MCP-Session-Id`、`Last-Event-ID` 这类 `2025-11-25` 机制当成永久不变的事实。

### 3.1 最新草案观察：2026-07-28 draft / release candidate

以下内容来自官方 draft / release candidate，适合作为路线预判，不应直接替换 `2025-11-25 Current` 的实现：

- **Stateless-first**：draft 移除 protocol-level sessions 与 `MCP-Session-Id`，并计划移除 `initialize` / `notifications/initialized` 握手。协议版本、client identity、client capabilities 改为随请求放入 `_meta`。
- **List 不再依赖连接状态**：`tools/list`、`resources/list`、`prompts/list` 这类列表端点不应随单个连接/session 变化；需要跨调用状态时，server 应显式返回自己铸造的 handle，并由后续 tool 参数携带。
- **SSE 恢复语义收缩**：draft 移除 `Last-Event-ID` / SSE event id 的重放恢复语义。断开的响应流应视为丢失 in-flight request，client 需要用新的 request id 重新发起。
- **Tasks 从实验核心能力转为官方 extension**：`2025-11-25` 里的实验性 Tasks 在 draft 中被迁移到 `io.modelcontextprotocol/tasks` extension，并调整状态轮询、输入补充和 task 列表能力。实现端不要把 `2025-11-25` 的 Tasks 方法形态当成长期稳定 API。
- **MRTR 替代部分 server-initiated requests**：draft 引入 Multi Round-Trip Requests，用 `input_required` 结果表达“还需要 roots / sampling / elicitation 等输入”，client 在重试原请求时带回 `inputResponses`。这会弱化当前文档中“server 反向向 client 发请求”的实现形态，但不改变“server 可以请求 host 协助补充能力”这一抽象。
- **MCP Apps 与 Skills over MCP**：draft 把交互式 UI（图表、表单等）和结构化技能包作为扩展方向，说明 MCP 正从“工具/资源协议”扩展到更完整的 agent 能力分发与交互载体。
- **授权与 schema 细节继续收敛**：draft 进一步强化 OAuth / OpenID Connect 兼容性，DCR 被明确推向兼容/回退路径；同时放宽 `inputSchema` / `outputSchema` 对 JSON Schema 2020-12 关键字的支持并补充 `$ref` 解析要求。

工程判断：如果今天实现生产 MCP server/client，仍应按 `2025-11-25 Current` 做兼容；但新架构设计应避免强依赖长生命周期 session、sticky routing、SSE replay 和 Tasks 当前方法名。远程 server 的状态最好尽早外置成显式 handle / task / job，而不是藏在连接或 session 里。

## 四、协议总体架构

### 4.1 三个角色

```
┌──────────────────────────────────────────────────────────┐
│  Host  (Claude Desktop / Cursor / Cline / Your Agent)    │
│                                                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐      │
│  │  Client A  │    │  Client B  │    │  Client C  │      │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘      │
└────────┼─────────────────┼─────────────────┼─────────────┘
         │                 │                 │
       stdio             HTTP              stdio
         │                 │                 │
         ▼                 ▼                 ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │ Server A │      │ Server B │      │ Server C │
   │   (fs)   │      │ (github) │      │(postgres)│
   └──────────┘      └──────────┘      └──────────┘
```

- **Host**：用户面对的 AI 应用，持有 LLM 调用权和用户授权。
- **Client**：Host 内部的协议适配层，**一个 client 对应一个 server**，负责该 server 的连接、握手、消息路由。
- **Server**：能力提供方，可以是本地子进程也可以是远程 HTTP 服务。

这个“一对一 client-server”的设计很关键：它避免了多路复用带来的状态污染，host 可以在不同 server 之间做能力裁剪、权限隔离、用户提示。

### 4.2 数据 vs 行为的分离

MCP 在 server 暴露给 host 的能力上做了**显式的语义切分**：

| 原语          | 控制方                             | 副作用                     | 类比               |
| ------------- | ---------------------------------- | -------------------------- | ------------------ |
| **Resources** | 由 host/用户**显式选择**注入上下文 | 只读                       | GET 请求 / 文件读  |
| **Tools**     | 由**模型**自主决定调用             | 可写、可有副作用           | POST 请求 / RPC    |
| **Prompts**   | 由**用户**显式触发（如斜杠命令）   | 不直接执行，仅产出消息模板 | 文本模板 / Snippet |

这是 MCP 区别于“所有东西都是工具”的最重要的设计选择。它的工程意义是：

- 数据进上下文不消耗“模型决策权”——读文件不需要模型先想“我要不要读”；
- 副作用操作经过模型 → 用户确认的链路，可以加入 HITL 关卡；
- 用户主动调用的能力（如“/总结这段会议”）不被模型自由发挥，保持确定性。

### 4.3 关键心智模型：服务发现（List）vs 意图执行（Call）

理解 MCP 时有一个常见误解：以为 LLM 会自己先向 MCP server 发 `tools/list` 查看可用工具，然后再发 `tools/call` 执行工具。

按 MCP 的分层，这两者应分开看：

- **`list` 是 client/host 对 server 的服务发现 RPC**：`tools/list`、`resources/list`、`prompts/list` 由 MCP client 发起，用于获取并缓存 server 暴露的能力清单。常见 host 会在初始化后预取，也可以按需懒加载；规范并不要求一次性列完所有能力。
- **`call` 是模型/用户意图经 host 转换后的执行 RPC**：LLM 不直接向 MCP server 发送 JSON-RPC。Host 会把已发现并筛选后的工具 schema、资源内容或 prompt 模板转成模型可见的上下文；模型只输出调用意图，最终由 host/client 转成 `tools/call`、`resources/read` 或 `prompts/get`。

简而言之：**模型不会直接发起 MCP `list` 请求；是否预取、缓存、懒加载，是 host/client 的实现策略。**

## 五、三大核心原语

### 5.1 Tools（工具）

最常用、最直观的原语。Server 暴露一组可调用的函数，模型根据对话决定何时调用。

每个 tool 的形态：

```json
{
  "name": "search_issues",
  "title": "Search GitHub Issues",
  "description": "Search issues in a repo by keyword.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "repo": { "type": "string" },
      "query": { "type": "string" }
    },
    "required": ["repo", "query"]
  },
  "outputSchema": { "...": "可选；新版规范支持 structured output" }
}
```

关键 RPC：

- `tools/list`：client 列出 server 的 tools；
- `tools/call`：client 调用某 tool；
- `notifications/tools/list_changed`：server 主动通知列表变化（如插件热加载）。

**设计要点**：

- `inputSchema` 用 JSON Schema 表达，让 host 可在调用前做参数校验、也可作为模型的“工具说明书”喂入 prompt。
- 从 `2025-11-25` 起，未显式声明 `$schema` 的 schema 默认按 **JSON Schema 2020-12** 解释；实现端至少要支持 2020-12，并对不支持的 dialect 给出清晰错误。
- 调用结果是一个**内容数组**（content list），可以是 text、image、resource link 等多种类型——这意味着 tool 可以返回结构化数据，也可以“指向”一个 resource（避免大数据塞进对话）。
- 新版工具结果可同时包含 `content` 和 `structuredContent`。`content` 面向模型/用户呈现，`structuredContent` 必须匹配 `outputSchema`，适合 host 稳定解析、展示表格或交给后续程序处理。
- Tool 应当对应**幂等性可推理**的语义：能区分“查询”和“修改”，并在 `annotations` 中暴露 hint（如 `readOnlyHint`、`destructiveHint`、`idempotentHint`），让 host 决定是否需要二次确认。注意 annotations 只是 server 给出的提示；不可信 server 的 annotations 不能直接当安全事实。
- Tool 名称应当控制在 1~128 个字符内，使用 ASCII 字母、数字、下划线、连字符、点号，避免空格和逗号；不同 server 之间是否重名由 host 处理，单个 server 内应唯一。
- `tools/list` 支持分页；工具数量较多时不要假设一次 list 就能取全。

### 5.2 Resources（资源）

Server 暴露一组**可被 host 读取**的数据条目，每条由 URI 标识：

```json
{
  "uri": "file:///workspace/README.md",
  "name": "README.md",
  "mimeType": "text/markdown"
}
```

关键 RPC：

- `resources/list`：列出可用资源；
- `resources/read`：按 URI 读取内容；
- `resources/subscribe` + `notifications/resources/updated`：订阅资源变更；
- `resources/templates/list`：声明 URI 模板（如 `git://commits/{sha}`）让 host 动态生成 URI。

**关键区别**：Resources 是“等待被引用”的素材库。按 MCP 的控制模型，resource 读取由 application/host 管理：用户、host UI 或 host 内部检索逻辑选定内容后，再把它注入上下文。这避免了模型在“先列资源 → 再读资源”上耗费多轮 turn。

Resources 也支持分页、订阅、`size`、annotations、icons 等元数据。`resources/read` 返回的是文本或 base64 blob 内容；如果内容很大，优先让 tool 返回 `resource_link`，由 host 决定是否读取、展示或注入上下文。

### 5.3 Prompts（提示模板）

Server 提供一组**用户可触发**的 prompt 模板，本质是“参数化的消息序列生成器”：

```json
{
  "name": "summarize_pr",
  "description": "Summarize a GitHub PR",
  "arguments": [{ "name": "pr_url", "required": true }]
}
```

调用 `prompts/get` 时返回的是一组 `messages`，host 把它注入对话作为新一轮的起点。

典型 UX：编辑器里的斜杠命令（“/summarize-pr ...”）、命令面板里的“重构这段”等。这部分原语在很多 MCP 实现中被低估，但它实际上是“标准化提示工程”的极佳挂载点。

### 5.4 反向能力：Sampling 与 Roots（client 也要实现的部分）

MCP 不是单向的。Server 也可以反过来向 client 发请求：

- **Sampling**：server 请求 client“帮我调一次 LLM”。意义巨大——它让 server 能在自己的工作流中嵌入 LLM 推理，但**不用自带 API key**：模型调用走 host 的 quota、host 的模型选择、host 的用户授权。这把 server 从“硬编码逻辑”升级为“也能用 LLM 推理的可组合单元”。
- **Roots**：client 告诉 server“你可以访问的文件系统根目录是这些”。这是一个权限边界声明，让 server 在调用 host 提供的文件读写能力时知道自己活动的沙盒范围。
- **Elicitation**（较新）：server 在执行中要求 client/用户补充输入，比纯靠“参数缺失就报错”更自然。

实现 MCP client 时，sampling 和 roots 是**必须考虑要不要支持**的；不支持也行，但要在 capability 里声明清楚。

`2025-11-25` 之后还要注意两个变化：

- Sampling 可以携带 `tools` 和 `toolChoice`，即 server 请求 client 采样时，也能让那次模型调用使用一组工具。Host 必须把这类调用和主对话的工具权限隔离开，避免 server 借 sampling 绕过用户确认。
- Tasks 是实验性能力，但已经进入规范正文。它不是第四个业务原语，而是给 `tools/call`、`sampling/createMessage`、`elicitation/create` 这类请求增加“立即返回任务句柄、后续轮询/取结果”的执行模式。

## 六、传输层

### 6.1 stdio

最简单：host 把 server 作为**子进程**启动，stdin/stdout 是 JSON-RPC 帧的双向管道。

- **优点**：零网络配置、零鉴权、进程级隔离、生命周期跟随 host。
- **约束**：stdout 严格只承载协议帧；**任何日志必须走 stderr**，否则解析炸掉。
- **典型场景**：本地工具——文件系统、git、本地数据库、shell 沙盒。

帧格式简单但很严格：每条消息是一行 UTF-8 JSON-RPC 消息，使用换行分隔，消息内部**不能包含嵌入换行**。`Content-Length` header 是 LSP 常见帧格式，不是 MCP stdio 标准格式；自己写 server 时不要混用，否则 host 很容易解析失败。

### 6.2 HTTP+SSE（已弃用的旧形态）

早期 MCP 远程 server 使用两个 endpoint：

- `POST /messages` 客户端发消息；
- `GET /sse` server 通过 Server-Sent Events 推消息回来。

这套设计很快暴露了问题：两个端点状态难同步、负载均衡复杂、session 绑定脆弱。

### 6.3 Streamable HTTP（当前主流）

2025-03 修订引入。核心改变：**单一 endpoint，由响应内容协商是否启用流式**。本节描述 `2025-11-25 Current`；`2026-07-28` draft 已经计划移除部分 session 与 SSE 恢复语义，见 3.1 节。

请求/响应规则（简化版）：

1. Client 向 `POST /mcp` 发 JSON-RPC 消息：
   - 请求头必须声明 `Accept: application/json, text/event-stream`；
   - 请求体是一条 JSON-RPC request / notification / response；不要再依赖 JSON-RPC batch，batch 在 `2025-06-18` 已从 MCP 规范移除；
   - 若该消息是 `notification` 或 `response`：server 接受后返回 **HTTP 202 Accepted 且无 body**；不能返回普通 JSON-RPC result；
   - 若该消息是 request：server 可以返回普通 JSON 响应（`Content-Type: application/json`）。
   - 若 server 想流式回包（多步进度、中间通知）：返回 `Content-Type: text/event-stream`，把响应作为 SSE 流。
2. 长连接 / server 主动推送：client 可以发 `GET /mcp`，请求头声明 `Accept: text/event-stream`，由 server 用 SSE 推送 notification / request（如 `tools/list_changed`、log、sampling 请求）。若 server 不支持独立 GET stream，应返回 405。
3. **Protocol Version Header**：HTTP 初始化之后，client 后续请求必须带 `MCP-Protocol-Version: <协商版本>`，例如 `2025-11-25`。这是 `2025-06-18` 以后很多手写 client 漏掉的兼容坑。
4. **Session ID**：握手时 server 可以在响应头中返回 `MCP-Session-Id`；后续所有请求都带上它。session ID 允许 server 在水平扩展时把同一会话路由到同一实例，或在状态丢失时显式让 client 重新初始化。若带 session id 的请求收到 404，client 必须重新初始化。
5. **断线恢复**：SSE event 上可以带 `id`，client 在断线后重连时通过 `Last-Event-ID` 头让 server 补发未送达事件。`2025-11-25` 明确：无论原流由 POST 还是 GET 创建，恢复都通过 GET；event id 应编码足够信息来定位原 stream。
6. **Origin 防护**：Streamable HTTP server 必须校验 `Origin`，非法 Origin 返回 403；本地 HTTP server 应只绑定 `127.0.0.1`，避免 DNS rebinding 攻击。

工程上的关键提醒：

- Streamable HTTP 是**普通 HTTP 请求/响应 + 可选 SSE 流**；它不依赖 WebSocket，也不要求 HTTP/2 push。多数反向代理可以支持，但要显式处理流式响应缓冲。
- 但 SSE 流不能经过会“缓冲整条响应再返回”的中间件——常见坑是某些 CDN / nginx 默认配置会缓冲。
- Server 端若想水平扩展，`2025-11-25` 下必须尽量支持**无状态**或外置 session 状态（Redis / DB）。draft 的方向更激进：协议层默认 stateless，跨调用状态用显式 handle / task 表达，而不是依赖 `MCP-Session-Id` 或 sticky routing。

### 6.4 选择建议

| 场景                            | 推荐                                  |
| ------------------------------- | ------------------------------------- |
| 本地工具（文件、git、本地 LLM） | stdio                                 |
| 团队内网共享工具                | Streamable HTTP（无鉴权或简单 token） |
| 多租户 SaaS server              | Streamable HTTP + OAuth 2.1           |
| 调试期                          | stdio（可直接打开终端看 stderr）      |

## 七、协议机制详解

### 7.1 生命周期

本节描述 `2025-11-25 Current` 的生命周期。`2026-07-28` draft 正在尝试移除 `initialize` / `notifications/initialized` 握手，把版本、client 信息和 capabilities 放到每个请求的 `_meta` 中；因此下面的图应视为 Current 版本实现图，而不是长期协议不变量。

```
Client                                       Server
  |                                             |
  |----- initialize(capabilities) ------------->|
  |<---- InitializeResult(capabilities) --------|
  |                                             |
  |----- notifications/initialized ------------>|
  |                                             |
  |   [ discovery/cache (client initiated) ]    |
  |----- tools/list, resources/list, ... ------>|
  |<---- list results --------------------------|
  |                                             |
  | [ execution (host maps model/user intent) ] |
  |----- tools/call, resources/read, ... ------>|
  |<---- call/read results ---------------------|
  |                                             |
  |----- shutdown(transport-specific) --------->|
```

要点：

- `initialize` 必须是 client-server 的第一阶段。Client 在 server 回复前不应发送除 ping 外的其它 request；server 在收到 `notifications/initialized` 前不应发送除 ping / logging 外的其它 request。
- `notifications/initialized` 必须由 client 在收到 initialize 结果后发送，server 此时才能开始正常的服务端通知和反向请求。
- **服务发现/缓存**：完成初始化后，client 可以发起 `tools/list`、`resources/list`、`prompts/list` 等请求获取能力清单。常见 host 会预取并缓存；也可以按需懒加载。规范要求的是由 client 通过 RPC 发现能力，而不是 LLM 直接向 server 发 `list`。
- **业务执行**：只有当 LLM 决策需要调用工具，或用户/host 明确触发资源读取、prompt 获取时，client 才会发起 `tools/call`、`resources/read`、`prompts/get` 等请求。
- 关闭：stdio 下先关闭子进程 stdin，再等待退出/发送 SIGTERM/SIGKILL；HTTP 下关闭关联连接即可。Streamable HTTP 还建议 client 在不再需要 session 时发送 DELETE `/mcp`（带 `MCP-Session-Id`），但 server 可以用 405 表示不支持显式删除。

### 7.2 能力协商

`initialize` 请求/响应里双方都携带 `capabilities` 对象，声明自己**支持什么**：

```jsonc
// Client → Server
{
  "protocolVersion": "2025-11-25",
  "capabilities": {
    "sampling": {},        // client 能响应 sampling 请求
    "roots": { "listChanged": true },
    "elicitation": {
      "form": {},
      "url": {}
    }
  },
  "clientInfo": { "name": "my-host", "version": "1.0.0" }
}

// Server → Client
{
  "protocolVersion": "2025-11-25",
  "capabilities": {
    "tools": { "listChanged": true },
    "resources": { "subscribe": true, "listChanged": true },
    "prompts": { "listChanged": true },
    "logging": {}
  },
  "serverInfo": { "name": "github-mcp", "version": "0.5.2" }
}
```

握手后双方都知道哪些功能可用；调用未声明的功能必须报 `MethodNotFound`。

`protocolVersion` 是字符串日期形式（如 `2025-11-25`），表示 client 支持的协议版本，通常应发送 client 支持的最新版本。若 server 支持该版本，必须原样返回；否则返回自己支持的另一个版本，通常是 server 支持的最新版本。Client 若不支持 server 回复的版本，应断开连接。HTTP transport 在握手后还要把该版本写入后续请求的 `MCP-Protocol-Version` 头。

### 7.3 错误处理

复用 JSON-RPC 错误码 + MCP 自定义扩展：

- `-32700` Parse error
- `-32600` Invalid Request
- `-32601` Method not found
- `-32602` Invalid params
- `-32603` Internal error
- `-32000` 到 `-32099` 是 JSON-RPC implementation-defined 区间，MCP 规范会在其中定义少量专用错误。不要随意假设“资源未找到”等业务场景一定有稳定全局错误码，除非当前 schema 明确列出。

工具调用的“业务错误”（如调用 GitHub API 返回 404、参数校验不通过、上游 API 返回权限不足）通常不应当走 JSON-RPC error，而是在 `tools/call` 的成功响应中通过 `isError: true` + content 字段返回——因为这种错误**是模型需要看到并据此调整的**，不是协议层的崩溃。这是一个容易踩错的设计点。

### 7.4 取消、进度、日志

- **取消**：client 发 `notifications/cancelled`，携带要取消的 request id。Server 应尽快停止并返回（但 race condition 下也可能已经完成）。
- **进度**：发请求时附带 `_meta.progressToken`，接收方在执行过程中发 `notifications/progress`，携带 `progress`、可选 `total` 和 `message`。`progress` 不要求是 0~100 的百分比，但必须单调递增；可以是浮点数。
- **日志**：server 发 `notifications/message`，携带 syslog 风格 level（debug/info/notice/warning/error/critical/alert/emergency）、可选 logger 名、JSON-serializable data。Client 可用 `logging/setLevel` 设置最低日志等级。

这三者在长任务（爬虫、大文件分析、Agent 子任务）里几乎必须实现，否则用户体验会极差。

## 八、动手实现：从零做一个 MCP Server

下面以 **Python + stdio** 为例，给出最小骨架。换成 TypeScript/Go/Rust 思路完全一致。

### 8.1 整体结构

```
my-mcp-server/
├── server.py            # 入口：读 stdin / 写 stdout
├── dispatcher.py        # JSON-RPC 方法路由
├── handlers/
│   ├── tools.py         # tools/list, tools/call
│   ├── resources.py     # resources/list, resources/read
│   └── prompts.py
└── schema.py            # 静态注册的 tool/resource/prompt 定义
```

### 8.2 主循环（stdio）

```python
import sys, json

def run():
    for line in sys.stdin:                # 一行一条 JSON-RPC 消息
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error")
            continue
        handle(msg)

def send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()                    # 不 flush 会卡死 host

def send_error(msg_id, code, message, data=None):
    error = { "code": code, "message": message }
    if data is not None:
        error["data"] = data
    send({ "jsonrpc": "2.0", "id": msg_id, "error": error })

def log(*args):
    print(*args, file=sys.stderr)          # 日志只能走 stderr
```

### 8.3 Dispatcher

```python
HANDLERS = {
    "initialize": on_initialize,
    "tools/list": on_tools_list,
    "tools/call": on_tools_call,
    "resources/list": on_resources_list,
    "resources/read": on_resources_read,
    "ping": lambda req: {},
}

INITIALIZED = False

def handle(msg):
    global INITIALIZED
    method = msg.get("method")
    has_id = "id" in msg
    msg_id = msg.get("id")

    # notification 是没有 id；request id 显式为 null 是非法请求
    if not has_id:
        if method == "notifications/initialized":
            INITIALIZED = True
        return
    if msg_id is None:
        return send_error(None, -32600, "Request id must not be null")

    # 正常 request 必须先 initialize；ping 可用于生命周期探测
    if method not in ("initialize", "ping") and not INITIALIZED:
        return send_error(msg_id, -32002, "Server not initialized")

    handler = HANDLERS.get(method)
    if handler is None:
        return send_error(msg_id, -32601, f"Method not found: {method}")

    try:
        result = handler(msg.get("params") or {})
        send({"jsonrpc": "2.0", "id": msg_id, "result": result})
    except Exception as e:
        log("handler error:", e)
        send_error(msg_id, -32603, str(e))
```

### 8.4 Initialize 握手

```python
PROTOCOL_VERSION = "2025-11-25"

def on_initialize(params):
    requested = params.get("protocolVersion")
    # 简化：只支持一个版本；生产实现应检查 requested 是否兼容。
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {
            "tools": { "listChanged": False },
            "resources": { "subscribe": False, "listChanged": False },
        },
        "serverInfo": { "name": "demo-server", "version": "0.1.0" },
    }
```

### 8.5 一个 Tool 的全链路

```python
TOOLS = [
    {
        "name": "add",
        "description": "Add two integers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": { "type": "integer" },
                "b": { "type": "integer" },
            },
            "required": ["a", "b"],
        },
    }
]

def on_tools_list(params):
    return { "tools": TOOLS }

def on_tools_call(params):
    name = params["name"]
    args = params.get("arguments") or {}
    if name == "add":
        result = args["a"] + args["b"]
        return {
            "content": [
                { "type": "text", "text": f"Sum = {result}" }
            ],
            "isError": False,
        }
    # 未知工具
    return {
        "content": [{ "type": "text", "text": f"Unknown tool: {name}" }],
        "isError": True,
    }
```

宿主（如 Claude Desktop）配置中加入：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["/abs/path/to/server.py"]
    }
  }
}
```

重启 host 后即可在对话里被模型调用 `add`。

### 8.6 升级到 Streamable HTTP

骨架上的差异：

1. 用 FastAPI / aiohttp / Express 起一个 `POST /mcp` 路由；
2. 入参是一条 JSON-RPC 消息；不要实现或依赖 JSON-RPC batch；
3. 决定本次响应是普通 JSON 还是 SSE：
   - request 的简单响应：直接返回 `application/json`；
   - request 需要 progress / 多步通知：返回 `text/event-stream`，把相关消息按 SSE 格式写出；
   - notification / response：接受后返回 HTTP 202，无 body。
4. 同时实现 `GET /mcp` 用于 server 主动推送通知和反向请求；不支持时明确返回 405。
5. 初始化成功后如果 server 需要有状态 session，在响应头写 `MCP-Session-Id`；后续请求校验 `MCP-Protocol-Version` 与 `MCP-Session-Id`。
6. 对所有连接校验 `Origin`；本地 server 只监听 `127.0.0.1`；生产环境配置反向代理关闭 SSE 缓冲。
7. 用 Redis / DB 把 session 状态外置，或者走无状态设计，让多副本部署成为可能。

### 8.7 鉴权（远程 server）

OAuth 2.1 在协议层的约定要点：

- 受保护的 MCP server 在 OAuth 里是 **Resource Server**，需要实现 OAuth 2.0 Protected Resource Metadata（RFC 9728）；
- Client 遇到 401 时优先解析 `WWW-Authenticate` 里的 `resource_metadata`；若没有该头，则按 `.well-known/oauth-protected-resource/...` 路径回退发现；
- 授权服务器发现支持 OAuth Authorization Server Metadata（RFC 8414）和 OpenID Connect Discovery；
- 授权码流程使用 PKCE；
- Client ID Metadata Documents 是 `2025-11-25` 推荐的无预先信任关系注册方式；预注册仍适合企业内控场景；Dynamic Client Registration（DCR）主要作为兼容/回退；
- Access token 以 `Authorization: Bearer ...` 形式带在 `POST /mcp` 上；
- 401 响应可通过 `WWW-Authenticate` 指明 resource metadata 和当前请求需要的 scope，让 client 触发用户授权或增量授权。

实务上：内网 MVP 可以先用简单的 `Authorization: Bearer <static-token>` 或网关鉴权，但一旦变成多用户/多租户/公网 remote server，应尽快切到标准 OAuth，并把 token 校验、scope、audience/resource indicator、审计日志和撤权机制做完整。

## 九、设计权衡与常见陷阱

### 9.1 Tool 与 Resource 的界线

新手最常见的错误是**把读文件做成 tool**。这会导致：

- 模型必须显式决定“读不读”，多绕一轮；
- 文件大时每次都把内容塞进 tool call 结果，token 浪费严重；
- 失去了“host 主动管理上下文”的能力。

**判据**：纯读、可缓存、host 想直接给用户“勾选注入”的——做成 resource；有副作用、参数可变、模型应自主决定时机的——做成 tool。

### 9.2 Tool description 是 prompt 工程

`tools/list` 返回的 description 字段，**会原封不动进入模型 prompt**。这意味着：

- 描述不清模型就调不准，比传统 RPC 文档要求高得多；
- 边界条件要写明：“当 X 为空时返回错误”会显著降低误调用率；
- 千万不要在 description 里塞内部代号、缩写、隐含上下文。

### 9.3 stdout 的“圣洁”

stdio 传输下 stdout 是协议生命线。常见踩坑：

- print 调试信息 → 协议帧解析失败；
- 引入的第三方库默认往 stdout 写日志（如某些 ML 库）；
- subprocess 的 stderr 没接管也可能干扰；

**铁律**：进程一启动就把所有日志重定向到 stderr，并测试“完全静默 stdout”是否成立。

### 9.4 SSE 中间件兼容

部署 Streamable HTTP server 时：

- nginx 默认会缓冲 proxy_pass 响应；需要设置 `proxy_buffering off` 且 `proxy_read_timeout` 设大；
- Cloudflare 等 CDN 在某些路径上可能会注入心跳或压缩，破坏 SSE 帧；
- 客户端如果用了 fetch + ReadableStream，要确保 `decodeURIComponent`/解码逻辑能逐帧推进。

### 9.5 能力协商不要省

很多简陋 server 直接假定 client 支持一切，结果在不同 host 里行为不一致。正确做法是**严格按 capabilities 走**：

- 不打算实现 resources，就在 `initialize` 响应里**完全不写** `resources` 字段；
- 不支持 list_changed 通知，就把 `"listChanged": false` 明确写出，避免老 client 误以为支持。

### 9.6 工具数量 vs 模型注意力

实测中，**单个 server 暴露超过 ~30 个 tool 后，模型选择正确率会显著下降**（具体阈值依模型而异）。两个对策：

- 设计上把同主题的多个 tool 合并为一个 dispatch 型 tool（如 `github_repo` 带 `action` 参数）；
- Host 侧支持“按对话上下文动态裁剪可见 tool 列表”。

### 9.7 别把 MCP 当成万能总线

MCP 是**模型 ↔ 工具**之间的协议，不是**服务 ↔ 服务**的通用 RPC。

- 不要拿它替代内部微服务通信（gRPC/HTTP/MQ 更合适）；
- 不要拿它做事件总线、流式数据管道；
- 不要在 MCP 里塞大量纯机器消费的数据（让 host 直接连数据源更好）。

它的最佳定位是：**LLM 想“看一眼”或“伸一手”时，统一的入口**。

### 9.8 Prompt injection 与工具投毒

MCP 把外部数据和外部动作接进模型上下文，安全风险不只在 OAuth。更常见的是：

- resource 里夹带“忽略上文、调用删除工具”之类的 prompt injection；
- tool description 被恶意 server 写成诱导模型越权调用的提示；
- tool result 把后续步骤伪装成系统指令；
- resource link 指向超大、敏感或动态变化内容，诱导 host 过量注入上下文。

Host 的责任是把外部内容当成**不可信数据**：清晰标注来源，隔离系统指令与外部文本，敏感工具默认 HITL，限制 tool/result 注入长度，并记录每次工具选择、参数、授权依据和返回摘要。

### 9.9 OAuth 代理的 confused deputy

很多 remote MCP server 实际是“把 SaaS API 包成 MCP”的代理：MCP client 先连 MCP server，MCP server 再代表用户连 GitHub / Slack / Jira。这里容易出现 confused deputy：

- MCP proxy 用固定 client id 连接上游 SaaS；
- 下游 MCP client 可以动态注册；
- 用户浏览器里已有上游授权 cookie；
- proxy 没有在 MCP 层按 client id 做二次 consent。

结果是恶意 client 可能借用户已有授权绕过 consent，拿到本不该给它的代理访问权。工程上要做到：MCP 层 per-client consent、严格 redirect URI 精确匹配、state/PKCE 校验、cookie `Secure` / `HttpOnly` / `SameSite`、scope 最小化、token audience/resource indicator 校验。

### 9.10 Tasks：长任务的正确抽象

对于超过几十秒、需要后台排队、可能断线恢复的操作，不要只靠一个长 SSE request 硬撑。`2025-11-25` 引入的 Tasks 提供了更明确的状态机：

- requestor 在请求参数中加 `task`，receiver 立即返回 `taskId`、`status`、`pollInterval`、TTL；
- requestor 用 `tasks/get` 轮询状态，用 `tasks/result` 在完成后取原请求类型对应的结果；
- 可选 `notifications/tasks/status` 提前推送状态变化，但 requestor 不能依赖它，仍要能轮询；
- task 取消应走 `tasks/cancel`，不要用普通 `notifications/cancelled` 取消 task。

适用场景：代码库全量分析、长时间爬取、报表生成、视频/音频处理、企业搜索批处理、调用外部异步 job API。短工具调用仍用普通 `tools/call`，否则会把 host 和模型循环复杂化。

但要注意：`2025-11-25` 里的 Tasks 仍是实验性能力；`2026-07-28` draft 已经把它迁移为官方 extension 并重做了部分方法形态。生产系统可以采用“长任务句柄 + 轮询 + TTL + 授权绑定”这个抽象，但不要把 `tasks/result`、`tasks/list` 等具体方法名设计成不可迁移的内部硬依赖。

### 9.11 Registry 与供应链

MCP server 是可执行代码或公网服务，安装体验越顺滑，供应链风险越高。官方 MCP Registry 的定位是**公开 server 的元数据仓库**，不是代码仓库，也不是安全审计保证：

- 代码仍在 npm / PyPI / Docker Hub / GitHub / remote URL 等位置；
- registry 通过反向 DNS / GitHub / DNS / HTTP challenge 管理 namespace；
- 下游 marketplace 可以做额外评分、扫描、签名、审核；
- 私有 server 不应发布到官方 registry，企业应维护私有 registry 或 marketplace。

Host 安装本地 server 时要把命令、参数、环境变量、文件访问 roots、网络访问、包来源、版本锁定展示给用户；企业环境要做 allowlist、SBOM、漏洞扫描、签名验证和集中撤回。

## 十、与相关概念的边界

| 概念                                                | 与 MCP 的关系                                                                                                                    |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| OpenAI Function Calling / Anthropic Tool Use        | 模型 API 层。MCP 在其之上把“工具”标准化为可移植的进程外组件。一个 MCP server 在 host 里仍然会被翻译成各自模型的 tool call 格式。 |
| Agent Framework（LangGraph / Agno / DeepAgents 等） | 这些是 host 端的运行时；MCP 是它们插入外部能力的标准协议。Agent 框架可以“消费”MCP server，但 MCP 不替代 Agent 调度逻辑。         |
| LSP                                                 | 设计灵感来源。MCP 借鉴了 initialize/capabilities/notification 模型，但服务面向 LLM 而不是编辑器。                                |
| OpenAPI / Swagger                                   | 描述 REST API。MCP 可以“包装”一个 OpenAPI 服务为 MCP server，但 MCP 暴露的语义更窄（专为 LLM 消费），不是 REST 替代品。          |
| Plugin 体系（如 ChatGPT plugins，已退场）           | 早期尝试，缺乏 client-host 分层和 capability 协商，被 MCP 取代。                                                                 |
| Function-as-a-Service（Lambda 等）                  | MCP server 可以部署到 FaaS 平台，但协议本身不规定运行时形态。                                                                    |

## 十一、生态治理与路线图

MCP 的重要性不只在协议本身，还在它把“Agent 连接外部世界”这件事变成了一个生态协作问题：

- **Host / framework 侧支持**：Claude Desktop / Claude Code、Cursor、Cline、Continue、Zed、Windsurf 等开发工具，以及 OpenAI Agents SDK、Google ADK、Microsoft Semantic Kernel 等 Agent 工具栈都提供了 MCP 使用路径。更准确地说，MCP 是 host / framework 的外部能力接入层，不是某个模型权重本身的“原生能力”。
- **SDK 与参考实现**：TypeScript、Python、Java、Kotlin、C#、Swift、Rust 等 SDK 逐渐分层维护。2025-11 之后的 SDK tiering 让开发者能区分“紧跟规范”和“社区可用但覆盖不全”的实现。
- **Registry / marketplace**：官方 MCP Registry 进入 preview，定位是公共 server metadata 仓库；Smithery、mcp.run、PulseMCP、awesome-mcp-servers 等更像发现、安装、评分或社区索引层。企业会需要私有 registry、审批流和配置下发。
- **治理结构**：MCP 项目已进入 LF Projects LLC 体系，使用 Maintainers / Core Maintainers / Lead Maintainers、Working Groups / Interest Groups、Specification Enhancement Proposals（SEPs）来推进规范。这意味着未来变化会更多走公开 SEP，而不是单一厂商内部迭代。
- **近期路线图**：官方 2026-03 路线图把重点放在 transport scalability、无状态/session 迁移、Server Cards、Tasks 生命周期、企业审计和网关、conformance tests、SDK tiering、reference implementations。

工程判断上可以这样理解：MCP 已经越过“一个厂商的插件格式”阶段，但还没到“所有能力都完全稳定”阶段。核心协议可放心采用；远程部署、安全、长任务、registry、企业治理仍要按规范版本持续跟踪。

## 十二、自己设计/实现 MCP 的路线建议

如果目标是**自研一个领域内的 MCP server**：

1. **先用 stdio + 官方 SDK 跑通**：TypeScript 或 Python SDK 都成熟。先在本地用 Claude Desktop / MCP Inspector 跑通一个 echo 工具，建立心智模型。
2. **梳理领域语义**：列出所有可暴露的能力，按“读 / 写 / 模板”分类到 resources / tools / prompts；纯读且可缓存的数据优先做 resource，动作和查询型操作做 tool，可复用工作流做 prompt。
3. **优先做 1 个高价值 tool 而不是 N 个**：tool description 写细比 tool 数量多重要得多；输入 schema 要收窄，错误信息要让模型能自我修正。
4. **设计输出形态**：人读的结果放 `content`，机器稳定消费的结果放 `structuredContent` + `outputSchema`，大对象返回 `resource_link`。
5. **加 progress、cancellation、timeouts**：任何超过 2 秒的 tool 都应该支持 progress；任何可能卡住的上游调用都要有 timeout；支持用户取消。
6. **长任务再上 Tasks**：后台队列、外部 job、批处理适合 task-augmented `tools/call`；短操作不要过度 task 化。
7. **再考虑远程化**：本地 stdio 跑顺后再上 Streamable HTTP；先内网 token / 网关，公网或多租户再实现 OAuth + Protected Resource Metadata + scope/audience 校验。
8. **做安全与运维基线**：stderr 日志、结构化审计、输入验证、速率限制、依赖锁定、secret 管理、最小权限 roots、HITL 策略、MCP Inspector/host 兼容性测试都要进入发布流程。

如果目标是**自研一个 MCP host / client**：

1. **从单 server stdio 开始**：先打通一个进程的生命周期管理、消息收发、能力协商。
2. **再做多 server 并发**：每个 server 独立 client 实例，隔离连接、capabilities、roots、授权 token、日志和错误。
3. **实现完整 lifecycle**：initialize / initialized / ping / timeout / cancellation / logging / progress / pagination 都要有，不要只实现 `tools/list` 和 `tools/call`。
4. **做好“能力裁剪”UI**：让用户能逐 server / 逐 tool 启停，展示 server 来源、命令、参数、env、roots、remote URL 和权限范围。
5. **HITL 兜底**：所有破坏性、外发数据、付费、权限变更类工具默认走二次确认；`destructiveHint: true` 只是提示，不能替代 host 自己的策略。
6. **沙盒与权限**：通过 `roots` 限制 server 能访问的文件系统；通过 OAuth scope / resource indicator / audience 限制远程 server 能调用的资源。
7. **工具注入策略**：不要把所有 server 的所有 tool 永久塞进模型上下文；按对话、工作区、用户选择、最近使用和权限动态裁剪。
8. **远程 server 生产化**：支持 `MCP-Protocol-Version`、`MCP-Session-Id`、GET SSE、Last-Event-ID、Origin 校验、OAuth discovery、token refresh、401 incremental scope、审计日志。

若按 `2026-07-28` draft 方向预留演进空间，还要避免把业务状态绑死在 session / SSE replay 上；优先用显式 handle、task/job id、幂等 request 和可重试执行来承载长流程状态。

最终判据：用户应当感受不到协议存在——它只让“AI 知道更多、能做更多”变成自然的事，而背后所有的工程边界都被协议固化在了正确的位置。

## 参考资料

Model Context Protocol. "Specification 2025-11-25." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/

Model Context Protocol. "Key Changes 2025-03-26 / 2025-06-18 / 2025-11-25." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/changelog

Model Context Protocol. "Versioning." Accessed July 2026. https://modelcontextprotocol.io/docs/learn/versioning

Model Context Protocol. "Transports." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/basic/transports

Model Context Protocol. "Lifecycle." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle

Model Context Protocol. "Authorization." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization

Model Context Protocol. "Tools / Resources / Prompts." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/server/tools

Model Context Protocol. "Tasks." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks

Model Context Protocol. "Security Best Practices." Accessed July 2026. https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices

Model Context Protocol. "Roadmap." Last updated 2026-03-05. https://modelcontextprotocol.io/development/roadmap

Model Context Protocol Blog. "The 2026-07-28 MCP Specification Release Candidate." Accessed July 2026. https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/

Model Context Protocol. "Draft Specification Changelog." Accessed July 2026. https://modelcontextprotocol.io/specification/draft/changelog

Model Context Protocol. "SEP-2575: Stateless MCP." Accessed July 2026. https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/seps/2575-stateless-mcp.mdx

Model Context Protocol. "The MCP Registry." Accessed July 2026. https://modelcontextprotocol.io/registry/about

Model Context Protocol. "Governance and Stewardship." Accessed July 2026. https://modelcontextprotocol.io/community/governance

Anthropic. "Introducing the Model Context Protocol." 2024-11-25. https://www.anthropic.com/news/model-context-protocol

OpenAI. "Model context protocol (MCP) - OpenAI Agents SDK." Accessed July 2026. https://openai.github.io/openai-agents-python/mcp/

Google. "MCP Tools - Agent Development Kit." Accessed July 2026. https://google.github.io/adk-docs/tools-custom/mcp-tools/

Microsoft. "Give agents access to MCP Servers." Updated 2026-05-26. https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/adding-mcp-plugins
