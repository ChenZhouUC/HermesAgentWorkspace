---
title: AI Agent Harness Engineering
created: 2026-06-02
updated: 2026-06-03
---

> **关于代码示例**：本文档中的代码示例基于 2026 年 6 月的主流框架版本（LangGraph 0.2+, AutoGen 0.3+, Anthropic Claude 3.5）。框架 API 可能随版本更新而变化，实际使用时请参考官方文档。代码仅供架构理解参考，非生产级实现。

# AI Agent Harness 工程实践指南

## 一、什么是 AI Agent Harness？

### 1.1 定义与核心职责

**AI Agent Harness**（或 Agent OS / Agent Runtime）是一个围绕大语言模型（LLM）构建的系统层软件栈，专门负责让模型从"一次性问答"转变为"可以自主决策、长期运行、解决复杂任务的智能程序"。

Harness 的核心职责包括：

- **自主循环控制（Autonomous Loop）**：接管 ReAct（Reason + Act）循环的底层调度逻辑，让大模型自主决策"思考 → 行动 → 观察结果 → 再次思考"的迭代过程。
- **上下文管理（Context Management）**：在长期运行任务中，处理上下文窗口截断、记忆持久化、关键信息提炼等问题。
- **工具调用与集成（Tool Orchestration）**：负责工具（API、数据库、文件系统等）的注册、调用、入参解析、结果传递与错误处理。
- **可观测性与容错（Observability & Resilience）**：提供日志、监控、调试能力，并处理工具调用失败、死循环检测、超时保护等异常情况。

**开发者视角**：工程师只需要提供工具（Tools/API/数据库连接）和系统设定（System Prompt），Harness 接管底层复杂逻辑。

**产物视角**：产出一个能够自主决策、长期运行、解决复杂开放性任务的智能程序实例。

### 1.2 Harness 与其他概念的区分

- **与 Agent 框架的关系**：Harness 是真正的 Agent 底座，而很多所谓的"Agent 框架"实际上是工作流编排工具（如 LangGraph）或多智能体协作框架（如 CrewAI、AutoGen）。
- **与 LLM API 的区别**：原始的 LLM API（如 OpenAI Chat Completion）只提供单次对话能力，Harness 在其之上构建了完整的运行时环境。
- **与 Copilot 的区别**：Copilot 通常指辅助人类的工具（如代码补全），而 Harness 支持的 Agent 可以独立完成复杂任务。

> **术语说明**：本文档涉及大量专业术语（如 ReAct、Checkpointing、HITL、MCP 等），详细定义请参考文末的[核心术语手册](#七核心术语手册glossary)章节。

---

## 二、Agent Harness 的层次架构

一个完整的 Agent Harness 通常由以下五层构成：

### 2.1 编排层（Orchestration Layer）

**职责**：接管 Agent 的主循环控制逻辑。

**核心能力**：

- ReAct 循环调度（Reason → Act → Observe）
- 多步骤任务规划与执行
- 子任务分解与依赖管理
- 死循环检测与终止条件判断

**典型实现模式**：

#### (1) 状态机驱动（LangGraph）

LangGraph 将 Agent 建模为 **StateGraph**，其核心机制包括：

- **State Schema**：使用 TypedDict 定义状态结构，每个节点读取和更新状态的特定字段
- **Reducer 函数**：定义字段如何合并（如 messages 字段通过 `add_messages` reducer 累加对话历史）
- **条件边（Conditional Edges）**：根据状态内容动态路由到不同节点（如 `should_continue` 函数判断是否继续工具调用）
- **Checkpointer**：支持 MemorySaver（内存）、SqliteSaver（本地持久化）、PostgresSaver（生产级持久化），通过 `thread_id` 实现会话隔离

**优势**：强确定性、可预测的流程控制、易于调试和单元测试  
**权衡**：需要显式定义所有状态转移，灵活性低于纯大模型驱动的 Agent

#### (2) 事件驱动（AutoGen）

AutoGen 采用 **Actor 模型** + **消息传递**：

- **Agents 作为 Actors**：每个 Agent 是独立的计算单元，通过消息通信
- **选择器机制（Selector）**：决定下一个发言的 Agent（如轮询、基于规则、由 LLM 动态选择）
- **终止条件（Termination）**：通过回调函数或 LLM 判断对话是否结束
- **群聊模式（GroupChat）**：多个 Agent 在共享上下文中协作，类似辩论或评审会议

**优势**：自然建模多角色协作场景，Agent 行为更加自主  
**权衡**：流程不确定性高，难以保证收敛，调试困难

#### (3) 纯代码循环（Agno / Pydantic AI）

直接用 Python `while` 循环实现 ReAct：

```python
while not task_completed:
    # 1. 模型推理
    response = agent.run(user_input)

    # 2. 执行工具调用
    if response.tool_calls:
        results = execute_tools(response.tool_calls)
        context.add_observation(results)

    # 3. 检查终止条件
    if response.is_final or iteration > max_iterations:
        break
```

**优势**：极简透明，完全控制执行逻辑，易于定制  
**权衡**：缺少高级特性（状态持久化、分布式支持），需自行实现容错逻辑

### 2.2 上下文层（Context Layer）

**职责**：管理 Agent 的"记忆"与"工作区"。

**核心能力**：

- **短期记忆（Working Memory）**：当前任务的对话历史、中间状态、推理轨迹
- **长期记忆（Long-Term Memory）**：跨会话的持久化知识（如用户偏好、项目约定、历史决策）
- **工作区管理（Workspace Management）**：虚拟文件系统、任务列表（Todo List）、草稿缓存
- **上下文压缩（Context Compression）**：在窗口满时，通过摘要、截断、重要性排序等方式保留关键信息
- **状态持久化（State Persistence）**：支持任务暂停/恢复、故障重启、时光旅行调试

#### 核心挑战与解决方案

**(1) 上下文窗口溢出问题**

当对话历史超过模型上下文限制（如 Claude 3.5 Sonnet 的 200K tokens）时，需要智能压缩策略：

| 策略       | 实现方式                                              | 优势           | 劣势                             |
| ---------- | ----------------------------------------------------- | -------------- | -------------------------------- |
| 滚动窗口   | 保留最近 N 条消息，丢弃旧消息                         | 实现简单       | 丢失历史信息，无法引用早期上下文 |
| 摘要压缩   | 定期调用 LLM 将旧对话摘要为关键信息                   | 保留语义核心   | 额外 API 成本，可能丢失细节      |
| 优先级排序 | 根据重要性保留（用户指令 > 工具结果 > 推理步骤）      | 最大化信息密度 | 需要设计评分函数                 |
| 结构化提取 | 将非结构化对话转换为结构化记忆（key-value、知识图谱） | 高效检索       | 提取精度依赖 LLM 质量            |

**(2) 状态持久化机制**

**LangGraph Checkpointer 实现对比**：

```python
# 1. MemorySaver（进程内存）
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()  # 重启丢失

# 2. SqliteSaver（本地文件）
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# 3. PostgresSaver（生产级）
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string("postgresql://...")
```

| Checkpointer  | 存储介质    | 隔离粒度  | 生产可用       | 典型场景             |
| ------------- | ----------- | --------- | -------------- | -------------------- |
| MemorySaver   | 进程内存    | thread_id | ❌（重启丢失） | 开发调试             |
| SqliteSaver   | 本地 SQLite | thread_id | ✅（单机）     | 个人工具、小规模部署 |
| PostgresSaver | PostgreSQL  | thread_id | ✅（分布式）   | 生产环境、多实例     |

**(3) 长期记忆实现模式**

**向量数据库 + RAG**：

- 将历史对话、项目文档存储为向量嵌入（Vector Embeddings）
- 根据当前查询检索最相关片段注入上下文
- 典型工具：Pinecone、Weaviate、Chroma

**结构化 KV 存储**：

- 显式提取关键信息（用户名、偏好、项目设置）存储为 key-value
- Claude Code 的 `/remember` 命令实现此模式，将用户指令持久化为 memory files

**文件系统 + 索引（DeepAgents 模式）**：

- 将中间产物（代码、文档、数据）保存为虚拟文件
- Agent 通过文件路径引用历史工作，而非将所有内容塞进对话

#### 典型实现对比

- **DeepAgents**：自带虚拟文件系统和任务列表引擎，支持通过文件路径组织长期工作
- **LangGraph**：通过 State 对象和 Checkpointer 实现状态持久化，支持 SQLite/PostgreSQL 后端
- **Agno**：支持记忆持久化（Memory Persistence）和上下文窗口管理
- **Claude Code**：结合短期对话压缩 + 长期文件系统记忆（`~/.claude/projects/.../memory/`）

### 2.3 沙盒层（Sandbox Layer）

**职责**：为 Agent 提供安全的代码执行与工具调用环境。

**核心能力**：

- **代码沙盒（Code Sandbox）**：隔离运行用户代码或 Agent 生成的代码（如 Python、JavaScript）
- **工具隔离（Tool Isolation）**：限制 Agent 可访问的 API、文件系统、网络资源
- **资源限制（Resource Quotas）**：CPU/内存/时间配额，防止资源耗尽攻击
- **审计日志（Audit Logging）**：记录所有工具调用与代码执行的详细日志
- **权限控制（Permission System）**：基于用户审批的危险操作拦截

#### 代码沙盒技术对比

| 隔离技术         | 隔离强度                  | 性能开销       | 适用场景           | 典型实现                       |
| ---------------- | ------------------------- | -------------- | ------------------ | ------------------------------ |
| 进程级隔离       | 低（共享内核）            | 极低           | 受信环境、简单脚本 | Python `subprocess`            |
| 容器隔离         | 中（Namespace + cgroups） | 低             | 通用生产环境       | Docker、Podman                 |
| 虚拟机隔离       | 高（独立内核）            | 高             | 多租户、零信任环境 | Firecracker、gVisor            |
| WebAssembly 沙盒 | 高（语言级隔离）          | 中             | 浏览器/边缘计算    | Wasmtime、Wasmer               |
| 云端沙盒         | 高（物理隔离）            | 中（网络延迟） | SaaS 产品          | E2B、Replit、GitHub Codespaces |

#### 安全威胁与防护机制

**(1) 代码注入攻击**

**威胁场景**：Agent 生成的代码包含恶意指令（如 `os.system("rm -rf /")）`

**防护措施**：

- **静态检查**：在执行前扫描代码，禁止危险函数（`eval`、`exec`、`__import__`）
- **白名单模式**：仅允许预定义的安全库（如 numpy、pandas），禁止 `os`、`subprocess`
- **只读文件系统**：限制写权限到特定工作目录

**(2) 资源耗尽（DoS）**

**威胁场景**：Agent 生成死循环或内存炸弹

**防护措施**：

```python
# Docker 资源限制示例
docker run \
  --memory="512m" \           # 内存上限 512MB
  --cpus="1.0" \              # CPU 配额 1 核
  --pids-limit=100 \          # 最大进程数
  --network=none \            # 禁止网络访问
  --timeout=30s \             # 30 秒超时
  agent-sandbox
```

**(3) 数据泄露**

**威胁场景**：Agent 访问敏感文件（如 `.env`、`~/.ssh/id_rsa`）

**防护措施**：

- **最小权限原则**：仅挂载必要的目录到容器
- **秘密管理**：环境变量通过专用服务注入（如 Vault、AWS Secrets Manager）
- **日志脱敏**：自动检测并遮盖日志中的 API 密钥、Token

#### 典型实现

- **SmolAgents**：Code as Action 范式，直接在沙盒中运行 Agent 生成的 Python 代码（基于 Docker）
- **E2B（Code Interpreter）**：云端代码沙盒服务，支持多语言、文件系统隔离、实时协作
- **Claude Code**：结合 Permission System（用户审批危险操作）+ Bash Tool（受限 shell 执行）
- **OpenHands/DevOpsGPT**：基于 Docker 的完整开发环境隔离，支持多容器编排

### 2.4 Human-in-the-Loop (HITL) 层

**职责**：在关键决策点引入人类监督与确认，确保 Agent 行为可控、可信、可纠正。

**核心能力**：

- **决策审批（Approval System）**：高风险操作（如删除数据、发送邮件、修改生产配置）需人类显式确认
- **实时干预（Real-time Intervention）**：人类可随时暂停、修正或接管 Agent 的执行流程
- **反馈收集（Feedback Loop）**：将人类的纠正反馈用于改进 Agent 行为（如 RLHF、Preference Learning）
- **可解释性（Explainability）**：向人类展示 Agent 的推理过程、工具调用链、决策依据
- **权限分级（Permission Tiers）**：根据操作风险（低/中/高）设置不同的审批策略

#### HITL 设计模式

**(1) 阻塞式审批（Blocking Approval）**

Agent 在执行危险操作前暂停，等待人类确认：

```python
# LangGraph 伪代码示例
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

def human_approval_node(state):
    """暂停执行，等待人类审批"""
    return Command(goto="wait_for_human")

graph = StateGraph()
graph.add_node("plan_action", plan_action)
graph.add_node("human_approval", human_approval_node)
graph.add_node("execute_action", execute_action)
graph.add_edge("plan_action", "human_approval")
graph.add_conditional_edges(
    "human_approval",
    lambda state: "approved" if state["human_approved"] else "rejected"
)
```

**适用场景**：金融交易、数据删除、生产部署等零容错场景。

**(2) 非阻塞式监控（Non-blocking Monitoring）**

Agent 自主执行，但实时向人类展示日志与状态，允许随时干预：

```python
# Claude Code 的 Permission System 示例
# 用户可配置 auto-approve 规则，但保留随时拦截的能力
# 工具调用时显示 description + 风险等级，用户点击批准/拒绝
```

**适用场景**：开发辅助、内容生成等允许试错的场景。

**(3) 事后审计（Post-hoc Audit）**

Agent 先执行，所有操作记录到审计日志，人类事后复盘：

```python
# 审计日志示例
{
  "timestamp": "2025-01-15T10:30:45Z",
  "agent_id": "hermes-agent-v1",
  "action": "file_delete",
  "target": "/data/old_logs/*.log",
  "risk_level": "medium",
  "human_reviewed": false
}
```

**适用场景**：批处理任务、离线分析等非实时场景。

#### 可解释性技术

**(1) 推理链展示（Reasoning Trace）**

- **Chain-of-Thought (CoT)**：展示 LLM 的逐步推理过程
- **ReAct Loop 可视化**：展示 Reason → Act → Observe 的完整循环

**(2) 工具调用透明化**

- 每个工具调用显示：输入参数、返回结果、执行时长
- Claude Code 的 Execution Log：实时展示 Bash/Read/Edit 等工具的输出

**(3) 状态图可视化**

- LangGraph Studio：可视化 Agent 的状态转移图，支持单步调试
- Dify：拖拽式工作流编辑器，每个节点展示执行状态

#### 典型实现对比

| 框架            | HITL 模式                   | 审批粒度 | 可解释性工具                     | 适用场景                          |
| --------------- | --------------------------- | -------- | -------------------------------- | --------------------------------- |
| **LangGraph**   | 原生 Human-in-the-loop 节点 | 状态级   | LangGraph Studio（状态图可视化） | 需要灵活审批策略的复杂工作流      |
| **Dify**        | 可视化审核节点              | 工作流级 | 拖拽式编辑器 + 日志面板          | 低代码场景，非技术用户审批        |
| **Claude Code** | Permission System           | 工具级   | Execution Log + Thinking Mode    | 开发工具，代码生成审批            |
| **Agno**        | Approval Hooks              | 函数级   | 终端日志 + 异步通知              | Python 开发者，编程式审批         |
| **AutoGen**     | `UserProxyAgent`            | 消息级   | Group Chat 历史记录              | 多 Agent 协作，需要人类作为协调者 |

#### 反馈循环实现

**(1) 即时纠正（Immediate Correction）**

- 用户修改 Agent 生成的代码 → 保存到 memory 作为偏好
- Claude Code 的 `/remember` 命令：显式记录用户指令

**(2) 负反馈强化（Negative Feedback）**

- 用户拒绝某操作 → 记录拒绝原因 → 训练分类器预测未来拒绝
- Dify 的审批历史：统计拒绝率，优化工作流设计

**(3) 人类演示学习（Learning from Demonstration）**

- Agent 失败后，用户手动完成任务 → Agent 观察并学习
- AutoGen 的 `teach` 模式：用户展示正确步骤，Agent 记录到示例库

### 2.5 协议层（Protocol Layer）

**职责**：定义 Agent 与外部系统的交互标准，确保互操作性与可扩展性。

**核心能力**：

- **工具协议（Tool Protocol）**：如何定义工具（函数签名、参数 Schema、返回值类型）
- **消息协议（Message Protocol）**：Agent 间的通信格式（如 Handoff、Event Bus、Pub/Sub）
- **API 标准（API Standards）**：如何暴露 Agent 为 RESTful API 或 WebSocket 服务
- **互操作性（Interoperability）**：支持与其他 Agent 框架、外部系统的集成
- **序列化规范（Serialization）**：状态持久化的格式（JSON、Protobuf、MessagePack）

#### 工具协议深度对比

**(1) OpenAI Function Calling**

最广泛采用的工具调用协议，基于 JSON Schema 定义工具签名：

```json
{
  "name": "get_weather",
  "description": "Get current weather in a given location",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "City name, e.g. San Francisco"
      },
      "unit": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"]
      }
    },
    "required": ["location"]
  }
}
```

**特点**：

- LLM 原生支持（GPT-4、Claude 3.5+、Gemini 1.5+）
- 严格的类型验证（基于 JSON Schema）
- 支持嵌套对象、数组、枚举等复杂类型
- **局限**：不支持流式返回、二进制数据

**(2) Anthropic Tool Use（Claude 专属）**

与 OpenAI 兼容，但增强了错误处理：

```python
tools = [{
    "name": "bash",
    "description": "Execute bash commands",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "number"}
        },
        "required": ["command"]
    }
}]

# Claude 返回格式
{
    "type": "tool_use",
    "id": "toolu_01A09q90qw90lq917835lq9",
    "name": "bash",
    "input": {"command": "ls -la", "timeout": 5}
}
```

**增强特性**：

- `tool_use_id` 追踪每个工具调用
- 支持并行工具调用（一次返回多个 tool_use block）
- 错误时返回 `tool_result` 类型的消息

**(3) MCP (Model Context Protocol)**

Anthropic 于 2024 年底推出的标准化协议，用于 LLM 与外部数据源的连接：

```typescript
// MCP Server 定义示例
{
  "name": "filesystem",
  "version": "1.0.0",
  "capabilities": {
    "tools": [
      {
        "name": "read_file",
        "description": "Read file contents",
        "inputSchema": {
          "type": "object",
          "properties": {
            "path": {"type": "string"}
          }
        }
      }
    ],
    "resources": [
      {
        "uri": "file:///path/to/doc",
        "name": "Project Documentation",
        "mimeType": "text/markdown"
      }
    ]
  }
}
```

**核心创新**：

- **统一资源模型**：工具（Tools）、资源（Resources）、提示（Prompts）三位一体
- **双向通信**：Server 可主动推送上下文更新（如文件变更通知）
- **标准化握手**：版本协商、能力发现、认证流程
- **生态系统**：Claude Desktop/Code 原生支持，社区已有 100+ MCP servers

**(4) LangChain Tools**

Python 生态的工具抽象层：

```python
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

class WeatherInput(BaseModel):
    location: str = Field(description="City name")
    unit: str = Field(default="celsius", description="Temperature unit")

class WeatherTool(BaseTool):
    name = "get_weather"
    description = "Get current weather"
    args_schema = WeatherInput

    def _run(self, location: str, unit: str = "celsius") -> str:
        # 实现逻辑
        return f"Weather in {location}: 20°{unit[0].upper()}"
```

**特点**：

- 基于 Pydantic 的强类型验证
- 支持同步/异步执行（`_run` / `_arun`）
- 内置工具：Google Search、Wikipedia、Wolfram Alpha 等
- **问题**：与 OpenAI Function Calling 需要额外转换层

#### Agent 间通信协议

**(1) Handoff（任务移交）**

OpenAI Swarm 引入的轻量级 Agent 切换协议：

```python
# Swarm 示例
def transfer_to_sales_agent():
    """Transfer the conversation to sales specialist"""
    return Agent(
        name="Sales Agent",
        instructions="You are a sales specialist"
    )

# 使用
client.run(
    agent=triage_agent,
    messages=[{"role": "user", "content": "I want to buy"}]
)
# triage_agent 返回 transfer_to_sales_agent() → 自动切换
```

**适用场景**：客服分流、多领域专家路由

**(2) Event Bus（事件驱动）**

AutoGen 的核心通信机制：

```python
# AutoGen 事件驱动示例
from autogen import AssistantAgent, UserProxyAgent, GroupChat

groupchat = GroupChat(
    agents=[coder, reviewer, tester],
    messages=[],
    max_round=10,
    speaker_selection_method="auto"  # 自动选择下一个发言者
)

# 消息格式
{
    "role": "assistant",
    "content": "Code review complete",
    "name": "reviewer",
    "metadata": {
        "event": "review_completed",
        "approved": True
    }
}
```

**特点**：

- 松耦合：Agent 无需知道下游是谁
- 广播模式：一条消息可触发多个 Agent
- **挑战**：消息风暴、顺序依赖难控制

**(3) Direct Messaging（点对点）**

CrewAI 的任务链模式：

```python
from crewai import Task

task1 = Task(
    description="Write code",
    agent=coder,
    expected_output="Python script"
)

task2 = Task(
    description="Review code",
    agent=reviewer,
    context=[task1],  # 直接依赖 task1 的输出
    expected_output="Review report"
)

crew = Crew(agents=[coder, reviewer], tasks=[task1, task2])
```

**特点**：

- 强依赖关系，执行顺序明确
- 上游输出自动注入下游 context
- **局限**：不支持动态路由

#### API 暴露模式

**(1) RESTful API**

将 Agent 包装为 HTTP 服务：

```python
# FastAPI 示例
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AgentRequest(BaseModel):
    message: str
    session_id: str

@app.post("/agent/run")
async def run_agent(request: AgentRequest):
    result = await agent.run(
        input=request.message,
        session_id=request.session_id
    )
    return {"output": result}
```

**适用场景**：微服务集成、无状态调用

**(2) WebSocket（长连接）**

支持流式输出和双向通信：

```python
# WebSocket 示例
from fastapi import WebSocket

@app.websocket("/agent/stream")
async def agent_stream(websocket: WebSocket):
    await websocket.accept()
    async for chunk in agent.stream(input=await websocket.receive_text()):
        await websocket.send_text(chunk)
```

**适用场景**：实时对话、进度更新

**(3) gRPC（高性能）**

用于内部 Agent 间的高效通信：

```protobuf
// agent.proto
service AgentService {
  rpc Execute(ExecuteRequest) returns (stream ExecuteResponse);
}

message ExecuteRequest {
  string input = 1;
  string session_id = 2;
}

message ExecuteResponse {
  string output = 1;
  string status = 2;
}
```

**适用场景**：微服务架构、跨语言调用

#### 互操作性案例

**(1) LangGraph ↔ LangChain Tools**

原生兼容，LangGraph 可直接使用 LangChain 的工具生态：

```python
from langchain.tools import DuckDuckGoSearchRun
from langgraph.prebuilt import create_react_agent

search = DuckDuckGoSearchRun()
agent = create_react_agent(model, tools=[search])
```

**(2) Hermes Agent ↔ MCP Servers**

通过 MCP 协议连接外部数据源：

```yaml
# Hermes config.yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/data"]
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

**(3) Dify ↔ OpenAI-Compatible APIs**

通过 OpenAI SDK 接入任何兼容服务：

```python
# Dify 调用 Ollama 本地模型
{
  "provider": "openai",
  "api_base": "http://localhost:11434/v1",
  "model": "llama3.1",
  "api_key": "ollama"  # 占位符
}
```

---

## 三、业界主流 Agent Harness 对比分析

### 3.1 真正的 Agent 底座（Harness）

#### 1. Dify（平台化 / 低代码）

- **定位**：企业级 LLM 应用开发与编排平台
- **产物**：带可视化 UI 后台的完整软件系统
- **开发流**：90% 写后端微服务 + 10% UI 拖拽编排
- **特性**：私有化部署路径清晰，编排和调度能力成熟
- **适用场景**：希望开箱即用的 B 端产品化团队

#### 2. Agno（纯代码 / 轻量级）

- **定位**：专为构建"Agent 软件"设计的 Python 极简框架
- **产物**：纯 Python 工程，轻量级部署
- **开发流**：80% 写业务函数 + 20% 实例化 Agent
- **特性**：开箱即用体验好，支持记忆、多模态、RAG、监控
- **适用场景**：追求轻量化的单体业务首选

#### 3. Pydantic AI（强类型 / 工程化极致）

- **定位**：追求极致类型安全与依赖注入的 Agent 框架
- **产物**：类型约束更强、结构化输出更稳定的 Agent
- **开发流**：70% 定义 Pydantic Schema + 30% 注入给 Agent
- **特性**：专注解决大模型输出格式错乱及企业全局状态安全传递痛点
- **适用场景**：需要强类型保证的企业级系统

#### 4. DeepAgents（长线任务 / 重型 Harness）

- **定位**：专为"长线、重度产出（Long-Horizon, Artifact-Heavy）"任务设计，灵感来源于 Claude Code、Manus 和 Deep Research
- **产物**：自带虚拟文件系统、长期记忆和子智能体生成能力的重型 Agent（类似开源版 Devin/Claude Code）
- **特性**：把上下文管理从"把历史塞进对话框"转向文件系统、任务列表和规划器（Planner）
- **适用场景**：长周期、多步骤、需要中间产物沉淀的工程任务

#### 5. OpenAI Agents SDK（官方原生）

- **定位**：OpenAI 官方轻量级 SDK，重点支持工具调用、Handoff 和多 Agent 协作
- **特性**：与 OpenAI 模型深度集成，Tool Calling 与 Handoff 支持稳定
- **适用场景**：技术栈主要使用 OpenAI 模型的团队

### 3.2 多智能体编排与工作流（Multi-Agent / Workflow）

#### 6. LangGraph（LangChain 官方 / 工业级状态机）

- **定位**：将 Agent 工作流建模为有向图（Graph）和状态机
- **特性**：强可控性、确定性重试、状态持久化、Human-in-the-loop 支持
- **适用场景**：对流程可控性要求高的生产系统

#### 7. CrewAI（流水线与角色扮演）

- **定位**：静态角色扮演与多智能体协作框架
- **特性**：大模型被限制在既定 SOP 内流转
- **适用场景**：流水线式的多角色协作任务

#### 8. AutoGen（微软出品 / 群聊辩论）

- **定位**：对话驱动（Conversation-Driven）的多智能体框架
- **特性**：通过多角色对话实现协作、评审和自我修正
- **适用场景**：代码生成与研究型实验

#### 9. Swarm（OpenAI 官方轻量级 Handoff）

- **定位**：轻量级的网络路由与交接（Handoff）框架
- **特性**：通过 Handoff 函数移交上下文
- **适用场景**：轻量级任务分发和路由实验

### 3.3 代码驱动与沙盒执行（CodeAgents）

#### 10. SmolAgents（Hugging Face 出品）

- **定位**：代码即行动（Code as Action）的沙盒执行框架
- **特性**：大模型直接输出 Python 代码并在沙盒中运行
- **适用场景**：避免海量数据通过 JSON 函数调用传输的 Token 压力

### 3.4 数据管道与系统集成（Copilot / RAG）

#### 11. LlamaIndex（数据与检索）

- **定位**：数据框架与 RAG 领域的重要工具
- **特性**：承担数据连接、索引和检索增强生成能力
- **适用场景**：挂载到 Agno、Dify 或自研服务中作为 RAG 层

#### 12. Semantic Kernel（微软出品）

- **定位**：企业级 Copilot 插件化（Plugin Architecture）总线
- **特性**：以业务逻辑为中心，将 ERP 接口封装为原生插件
- **适用场景**：企业系统集成与强一致性后端重构

#### 13. RAGFlow（深层文档检索与 Agentic RAG）

- **定位**：专门用来处理硬骨头文档的"重型知识库 Agent"
- **特性**：深层解析能力，处理复杂表格、扫描件或排版复杂的 PDF
- **适用场景**：企业知识库和 Agentic RAG

---

## 四、Agent Harness 选型决策指南

### 4.1 决策树

```
开始选型
│
├─ 需要可视化低代码平台？
│  └─ 是 → Dify（企业级平台化方案）
│  └─ 否 → 继续
│
├─ 主要编程语言是？
│  ├─ Python → 继续
│  ├─ C# / Java → Semantic Kernel
│  └─ TypeScript → LangGraph.js / AutoGen
│
├─ 任务类型是？
│  ├─ 长期任务（多天、大量中间产物）→ DeepAgents
│  ├─ 数据密集型（大规模数据处理）→ SmolAgents（Code as Action）
│  ├─ 多角色协作辩论 → AutoGen
│  └─ 通用业务逻辑 → 继续
│
├─ 对流程控制的要求？
│  ├─ 需要强确定性、可预测 → LangGraph（状态机）
│  ├─ 需要灵活路由切换 → Swarm（Handoff）
│  └─ 追求极简轻量 → Agno / Pydantic AI
│
└─ 类型安全重要性？
   ├─ 高（企业级严格类型） → Pydantic AI
   └─ 中（快速迭代） → Agno
```

### 4.2 场景化选型矩阵

| 场景               | 推荐方案                            | 理由                                | 备选方案                  |
| ------------------ | ----------------------------------- | ----------------------------------- | ------------------------- |
| **企业知识问答**   | Dify + RAGFlow                      | 低代码平台 + 深度文档解析           | LlamaIndex + Agno         |
| **代码生成与审查** | AutoGen                             | 多角色协作（Coder/Reviewer/Tester） | LangGraph + Claude Code   |
| **客服分流路由**   | Swarm                               | 轻量级 Handoff，易于理解和维护      | LangGraph 条件路由        |
| **长期研究任务**   | DeepAgents                          | 虚拟文件系统 + 任务列表 + 长期记忆  | LangGraph + 自建文件系统  |
| **金融交易决策**   | LangGraph + PostgreSQL Checkpointer | 强确定性 + HITL + 审计日志          | Pydantic AI（强类型验证） |
| **数据分析 Agent** | SmolAgents                          | Code as Action 避免 JSON Token 开销 | Agno + E2B 沙盒           |
| **快速原型验证**   | Agno                                | 极简框架，80/20 法则                | Pydantic AI               |

### 4.3 关键评估维度

#### (1) 学习曲线 vs 灵活性

```
学习曲线（低→高）：Dify < Agno < Swarm < LangGraph < AutoGen < DeepAgents
灵活性  （低→高）：Dify < Swarm < Agno < LangGraph < AutoGen < DeepAgents
```

**权衡建议**：

- 快速交付 MVP → 选学习曲线低的（Dify、Agno）
- 复杂业务定制 → 选灵活性高的（LangGraph、DeepAgents）

#### (2) 生产就绪度

| 维度           | Dify          | LangGraph        | Agno     | Pydantic AI | AutoGen   | DeepAgents |
| -------------- | ------------- | ---------------- | -------- | ----------- | --------- | ---------- |
| **状态持久化** | ✅ 内置       | ✅ 多后端        | ✅ 支持  | ✅ 支持     | ⚠️ 需自建 | ✅ 内置    |
| **可观测性**   | ✅ UI 面板    | ✅ Studio        | ⚠️ 日志  | ⚠️ 日志     | ⚠️ 日志   | ✅ 内置    |
| **HITL 支持**  | ✅ 可视化审批 | ✅ 原生节点      | ✅ Hooks | ✅ 依赖注入 | ⚠️ 需自建 | ✅ 内置    |
| **容错机制**   | ✅ 工作流重试 | ✅ Checkpointing | ⚠️ 基础  | ⚠️ 基础     | ⚠️ 需自建 | ✅ 内置    |
| **企业部署**   | ✅ 完整方案   | ✅ 文档齐全      | ✅ 支持  | ✅ 支持     | ⚠️ 实验性 | ⚠️ 早期    |

#### (3) 成本考量

**开发成本**：

- 最低：Dify（低代码）、Agno（极简）
- 中等：LangGraph、Swarm、Pydantic AI
- 较高：AutoGen（调试复杂）、DeepAgents（学习曲线陡）

**运行成本（Token 消耗）**：

- SmolAgents < Agno < Swarm < LangGraph < AutoGen（群聊 Token 开销大）

**维护成本**：

- 低代码平台（Dify）锁定风险高，迁移成本大
- 纯代码框架（Agno、LangGraph）可控性强，但需自建周边工具

### 4.4 迁移路径建议

#### 从 LangChain 迁移到 LangGraph

- **原因**：LangChain 适合原型，LangGraph 适合生产（状态管理、容错、HITL）
- **策略**：复用 LangChain Tools，逐步将链（Chain）改写为图（Graph）

#### 从 Agno 迁移到 LangGraph

- **时机**：需要复杂工作流编排、多 Agent 协作、时光旅行调试
- **成本**：中等（需要重构为状态机模型）

#### 从 AutoGen 迁移到其他框架

- **原因**：AutoGen 实验性强，生产环境不确定性高
- **目标**：LangGraph（需要确定性）或 Swarm（需要轻量路由）

---

## 五、Agent Harness 工程原则

### 5.1 可观测性原则（Observability）

- **日志分层**：区分系统日志（Harness 内部）、推理日志（LLM 输出）、工具日志（外部调用）
- **链路追踪**：为每个任务生成唯一 Trace ID，跨工具调用全链路可追溯
- **实时监控**：Token 消耗、延迟、成功率、错误率等关键指标
- **可视化调试**：展示 Agent 的推理过程、决策树、工具调用序列

### 5.2 容错性原则（Resilience）

- **幂等性保证**：工具调用失败后可安全重试
- **超时保护**：为每个工具调用设置合理超时
- **死循环检测**：检测 Agent 陷入重复行为，触发人工干预或自动终止
- **降级策略**：在关键工具不可用时，自动切换备用方案或人工接管

### 5.3 安全性原则（Security）

- **最小权限原则**：Agent 只能访问完成任务所需的最小资源集
- **敏感操作审批**：删除数据、发送消息、修改配置等操作需人类确认
- **输入验证**：严格验证工具参数，防止注入攻击
- **审计日志**：记录所有敏感操作，支持事后审计

### 5.4 成本优化原则（Cost Efficiency）

- **智能缓存**：对重复查询的结果进行缓存
- **上下文压缩**：通过摘要、截断、重要性排序减少 Token 消耗
- **模型分层**：简单任务用小模型，复杂任务用大模型
- **按需计算**：推理时计算（Test-Time Compute）根据任务难度动态调整

---

## 六、2026 年 Agent Harness 发展趋势

### 6.1 Agent REPL (Read-Eval-Print Loop)

Claude Code、Cursor 等工具引入了"Agent 即开发环境"的概念：

- Agent 直接在本地文件系统中读写代码
- 实时执行并观察结果
- 支持多轮交互式调试

### 6.2 自适应路由（Adaptive Routing）

根据任务类型自动选择最合适的模型或 Agent：

- 简单查询 → 小模型快速响应
- 复杂推理 → 大模型深度思考
- 专业领域 → 领域微调模型

### 6.3 多 Agent 协作编排（Multi-Agent Orchestration）

从单一 Agent 转向 Agent 网络：

- Swarm 式的去中心化协作
- LangGraph 式的中心化编排
- AutoGen 式的对话驱动协作

### 6.4 推理时计算（Test-Time Compute）

OpenAI o1 系列模型开创的新范式：

- Agent 在推理时"多想一会儿"，而非单纯扩大模型规模
- 通过强化学习训练模型自己的思维链
- 根据任务难度动态分配计算资源

### 6.5 标准化协议（MCP 与互操作性）

Claude Code 引入的 Model Context Protocol (MCP) 开始推动行业标准化：

- 统一的工具定义格式
- 跨平台的 Agent 互操作
- 插件生态的繁荣

---

## 七、核心术语手册（Glossary）

本节提供 Agent Harness 领域的核心术语解释，帮助理解技术细节和架构设计。

### 7.1 基础概念

#### Agent（智能体）

基于大语言模型（LLM）的自主决策系统，能够感知环境、制定计划、执行操作并从反馈中学习。与传统软件的最大区别在于：Agent 通过自然语言推理来决定下一步行动，而非硬编码逻辑。

#### Harness（底座/运行时）

围绕 LLM 构建的系统层软件栈，负责接管 ReAct 循环、工具调用、状态管理、错误处理等基础设施职责，让开发者专注于业务逻辑而非底层编排。类似于 Web 应用的框架（如 Django、Express），Harness 是 Agent 应用的框架。

#### Tool / Function Calling（工具调用）

LLM 调用外部函数或 API 的能力。模型输出结构化的函数调用请求（JSON），Harness 解析并执行，将结果返回给模型。这是 Agent 与外部世界交互的核心机制。

#### Prompt（提示词）

发送给 LLM 的输入文本，包括系统指令、用户请求、历史对话、工具定义等。Prompt Engineering 是设计高质量 Prompt 以引导模型行为的技术。

### 7.2 编排与控制流

#### ReAct（Reason + Act）

经典的 Agent 推理模式（Yao et al., 2022），循环执行三步：

1. **Reason**：模型推理下一步该做什么
2. **Act**：执行工具调用或输出结果
3. **Observe**：观察执行结果，更新上下文

该模式是大多数 Agent 框架的核心循环。

#### State Graph（状态图）

将 Agent 工作流建模为有向图，每个节点代表一个状态或操作，边代表转移条件。LangGraph 采用此范式，提供确定性的流程控制和可视化能力。

#### Orchestration（编排）

协调多个 Agent、工具、模型之间的交互逻辑。编排范式包括：

- **状态机**（State Machine）：显式定义状态转移规则
- **事件驱动**（Event-Driven）：通过消息传递触发行为
- **纯代码循环**（Code Loop）：用 while/for 循环直接控制流程

#### Handoff（任务移交）

一个 Agent 将任务转交给另一个 Agent 的机制。OpenAI Swarm 将 Handoff 设计为一等公民，通过函数调用实现 Agent 间的上下文传递和控制权转移。

### 7.3 上下文与记忆

#### Context Window（上下文窗口）

LLM 单次推理能处理的最大 Token 数量。Claude 3.5 Sonnet 支持 200K tokens，GPT-4 Turbo 支持 128K tokens。超出窗口的内容需要通过上下文管理策略处理。

#### Checkpointing（检查点）

将 Agent 的执行状态持久化到存储（数据库、文件系统），支持任务暂停、恢复、回滚。LangGraph 的 Checkpointing 机制是实现 Human-in-the-loop 和容错的基础。

#### Short-Term Memory（短期记忆）

存储在当前对话上下文中的临时信息，随对话结束而消失。通常通过 Prompt 中的历史消息实现。

#### Long-Term Memory（长期记忆）

持久化存储的知识和经验，跨会话保留。实现方式包括：

- **向量数据库**（Vector DB）：存储嵌入向量，支持语义检索
- **知识图谱**（Knowledge Graph）：存储结构化关系
- **文件系统**（File System）：存储文档、代码等产物

#### RAG (Retrieval-Augmented Generation)

检索增强生成，通过外部知识库检索相关信息并注入 Prompt，增强模型的知识覆盖和准确性。Agent Harness 中常用于长期记忆和领域知识增强。

### 7.4 安全与沙盒

#### Sandboxing（沙盒隔离）

在受控环境中执行不可信代码或操作，防止恶意行为影响主系统。常见技术包括：

- **容器隔离**（Docker、Firecracker）
- **虚拟机**（VM）
- **进程隔离**（seccomp、AppArmor）

#### HITL（Human-in-the-Loop）

在 Agent 执行流程中插入人类审批或干预环节。关键场景包括：

- 敏感操作（删除数据、发送消息）
- 不确定决策（多个方案选择）
- 异常情况（错误恢复、安全检查）

#### Jailbreak（越狱攻击）

通过精心设计的 Prompt 绕过 LLM 的安全限制，诱导模型输出有害内容或执行危险操作。Harness 需通过输入验证、输出过滤、权限控制等机制防御。

#### Prompt Injection（提示词注入）

攻击者通过工具返回值、文件内容等途径注入恶意指令，篡改 Agent 行为。防御措施包括：

- 明确区分系统指令和用户输入
- 对外部数据进行转义或标记
- 限制 Agent 的操作权限

### 7.5 协议与标准

#### MCP (Model Context Protocol)

Anthropic 提出的标准化协议（2024），定义 LLM 与外部工具、数据源的交互规范。MCP 包含三大组件：

- **Resources**：可读取的数据源（文件、API、数据库）
- **Tools**：可调用的函数
- **Prompts**：预定义的提示词模板

#### Tool Protocol（工具协议）

定义工具的输入输出格式、错误处理、权限控制等规范。OpenAI Function Calling 使用 JSON Schema 描述工具参数。

#### OpenAPI / Swagger

RESTful API 的标准描述格式，可自动转换为 LLM 可调用的工具定义。许多 Harness 支持导入 OpenAPI 规范自动生成工具。

### 7.6 性能与优化

#### Prompt Caching（提示词缓存）

缓存 Prompt 的部分内容（如系统指令、工具定义），避免重复计算。Anthropic 的 Prompt Caching 可减少 90% 的重复 Token 处理成本，降低延迟。

#### Streaming（流式输出）

LLM 逐 Token 生成响应，而非等待完整输出后返回。Harness 需支持流式解析和实时渲染，提升用户体验。

#### Test-Time Compute（推理时计算）

在推理阶段增加计算资源（如 o1 模型的内部思维链），而非单纯扩大模型规模。这是继 Scaling Law 之后的新性能提升范式。

#### Token Budget（Token 预算）

限制单次任务或单轮对话的最大 Token 消耗，防止成本失控。Harness 需监控累计消耗并在接近预算时触发降级或终止。

### 7.7 多 Agent 系统

#### Swarm（蜂群）

去中心化的 Agent 网络，通过局部交互涌现全局智能。OpenAI Swarm 框架实现了轻量级的 Agent 路由和协作。

#### Supervisor Pattern（监督者模式）

中心化编排，一个 Supervisor Agent 负责分解任务、分配给 Worker Agents、汇总结果。

#### Debate / Reflection（辩论/反思）

多个 Agent 扮演不同角色（如 Proposer、Critic、Judge），通过对话达成更优决策。AutoGen 支持此模式。

---

## 八、总结与展望

**AI Agent Harness** 正在从实验性工具走向生产级基础设施。关键演进方向包括：

1. **从单次对话到长期运行**：Harness 让 Agent 能够处理跨天、跨周的复杂任务
2. **从黑盒到透明**：可观测性、可解释性成为工程必需品
3. **从通用到专用**：针对不同场景（代码生成、数据分析、企业集成）的专用 Harness 涌现
4. **从独立到协作**：多 Agent 系统成为解决复杂问题的标准模式
5. **从扩展训练到扩展推理**：推理时计算成为性能提升的新杠杆

对于工程团队而言，选择合适的 Harness 需要综合考虑：

- **任务复杂度**：简单任务用轻量级框架（Agno），复杂任务用重型框架（DeepAgents）
- **可控性需求**：需要强可控性用状态机编排（LangGraph），容忍黑盒用纯 RL Agent
- **集成深度**：轻度集成用 API 封装，深度集成用企业总线（Semantic Kernel）
- **团队技能**：Python 团队用 Agno/Pydantic AI，C#/Java 团队用 Semantic Kernel

随着大模型能力的持续提升与 Harness 工程的成熟，我们正在见证"AI Agent 作为软件工程基本单元"这一愿景逐步成为现实。

---

## 九、参考文献（References）

### 学术论文

Yao, Shunyu, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao. "ReAct: Synergizing Reasoning and Acting in Language Models." _arXiv preprint arXiv:2210.03629_ (2022). https://arxiv.org/abs/2210.03629

Wei, Jason, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, and Denny Zhou. "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." _arXiv preprint arXiv:2201.11903_ (2022). https://arxiv.org/abs/2201.11903

Schick, Timo, Jane Dwivedi-Yu, Roberto Dessì, Roberta Raileanu, Maria Lomeli, Luke Zettlemoyer, Nicola Cancedda, and Thomas Scialom. "Toolformer: Language Models Can Teach Themselves to Use Tools." _arXiv preprint arXiv:2302.04761_ (2023). https://arxiv.org/abs/2302.04761

Wu, Qingyun, Gagan Bansal, Jieyu Zhang, Yiran Wu, Shaokun Zhang, Erkang Zhu, Beibin Li, et al. "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation." _arXiv preprint arXiv:2308.08155_ (2023). https://arxiv.org/abs/2308.08155

### 框架官方文档

LangChain AI. "LangGraph Documentation." Accessed June 2026. https://langchain-ai.github.io/langgraph/

Microsoft. "AutoGen: Enable Next-Gen Large Language Model Applications." Accessed June 2026. https://microsoft.github.io/autogen/

Anthropic. "Model Context Protocol Specification." Accessed June 2026. https://modelcontextprotocol.io/

OpenAI. "Swarm: A Framework for Multi-Agent Orchestration." Accessed June 2026. https://github.com/openai/swarm

Hugging Face. "SmolAgents Documentation." Accessed June 2026. https://huggingface.co/docs/smolagents/

Dify.AI. "Dify Platform Documentation." Accessed June 2026. https://docs.dify.ai/

E2B. "Code Interpreter SDK Documentation." Accessed June 2026. https://e2b.dev/docs

Pydantic. "Pydantic AI Documentation." Accessed June 2026. https://ai.pydantic.dev/

Anthropic. "Claude Code Documentation." Accessed June 2026. https://docs.anthropic.com/

### 技术博客与工程报告

Anthropic Engineering Blog. "Introducing Claude Code: AI-Powered Development Environment." June 2026. https://www.anthropic.com/blog/claude-code

LangChain Blog. "Building Production-Ready AI Agents with LangGraph." 2025. https://blog.langchain.dev/langgraph-production/

OpenAI. "Introducing GPT-4 Turbo with Vision." November 2023. https://openai.com/blog/gpt-4-turbo

Microsoft Research. "From Copilot to Agent: The Evolution of AI Assistance." 2025.

Hugging Face Blog. "Code as Action: A New Paradigm for Agent Tooling." 2024. https://huggingface.co/blog/

### 行业标准与规范

OpenAPI Initiative. "OpenAPI Specification v3.1.0." 2021. https://spec.openapis.org/oas/v3.1.0

JSON Schema. "JSON Schema: A Media Type for Describing JSON Documents." 2020. https://json-schema.org/

W3C. "Web of Things (WoT) Thing Description." 2020. https://www.w3.org/TR/wot-thing-description/

### 开源项目

LlamaIndex. "LlamaIndex: Data Framework for LLM Applications." GitHub repository. https://github.com/run-llama/llama_index

Semantic Kernel. "Semantic Kernel: Integrate Large Language Models with Conventional Programming Languages." GitHub repository. https://github.com/microsoft/semantic-kernel

CrewAI. "CrewAI: Framework for Orchestrating Role-Playing, Autonomous AI Agents." GitHub repository. https://github.com/joaomdmoura/crewAI

RAGFlow. "RAGFlow: Deep Document Understanding for Agentic RAG." GitHub repository. https://github.com/infiniflow/ragflow

Hermes. "Hermes Agent: Production-Grade LLM Agent Runtime." GitHub repository. https://github.com/anthropics/hermes

---

## 附录：文档变更历史

**Version 1.0** (2026-06-02)

- 初始版本：五层架构分析、13 个框架对比、工程原则
- 来源：个人研究报告迁移

**Version 1.1** (2026-06-03)

- 技术深度扩充：术语手册、参考文献
- 补充代码示例和实现细节
- 符合 Chicago 引用标准

**Version 1.2** (2026-06-03)

- 运维优化：删除冗余术语解释、添加代码版本说明
- 改进文档定位：从"调研报告"改为"实践指南"
- 添加选型决策树和季度审查计划
