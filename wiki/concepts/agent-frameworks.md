---
title: AI Agent Frameworks Selection
created: 2026-05-14
updated: 2026-07-11
type: concept
tags: [agent, ops, llm]
sources: [_living/AI-Infrastructure/AI-Agent-Frameworks.md]
confidence: high
---

# AI Agent Frameworks Selection

从工程视角审视 AI Agent 框架的选型。"Agent" 一词被严重泛化，不同框架产出的"东西"完全不同——本页按产物形态把主流框架归为五大阵营，并给出二次开发的场景化选型。

## 认知澄清：什么是真正的 "Agent 框架"

一个真正符合直觉的 Agent 框架（[[agent-harness|Agent Harness]] / OS）应满足：开发者只提供工具（Tools/API/数据库）与系统设定（System Prompt），框架在底层接管大模型的调度循环（思考 → 调用工具 → 观察结果 → 再思考），并处理死循环、上下文截断、入参错误重试等复杂逻辑，最终产出能自主决策、长期运行、解决开放性任务的智能程序实例。这个「思考 - 行动」循环是 ReAct 模式的工程化落地。^[[[_living/AI-Infrastructure/AI-Agent-Frameworks|AI-Agent-Frameworks]]]

## 五大阵营全景

### 阵营一：真正的 Agent 底座 (Harness / OS)

接管底层 ReAct 循环，是私有化 Agent 的核心引擎：

- **Dify**：企业级 LLM 应用编排平台（低代码），产出带可视化后台 + RESTful API 的成型系统，私有化路径清晰。
- **Agno（原 Phidata）**：纯 Python 极简框架，一行代码实例化 Agent；支持记忆持久化、多模态、Pydantic 函数级工具、RAG。
- **Pydantic AI**：追求极致类型安全与依赖注入，专治大模型输出格式错乱与全局状态安全传递。
- **DeepAgents（LangChain 官方）**：为长线、重产出（Long-Horizon, Artifact-Heavy）任务设计，自带虚拟文件系统、长期记忆与子智能体；灵感来自 Claude Code / Manus / Deep Research，把上下文管理从"塞进对话框"转向文件系统 + Todo + Planner。
- **OpenAI Agents SDK**：OpenAI 官方轻量 SDK，主打 Tool Calling 与 Handoff 多 Agent 协作。^[[[_living/AI-Infrastructure/AI-Agent-Frameworks|AI-Agent-Frameworks]]]

### 阵营二：多智能体编排与工作流 (Multi-Agent / Workflow)

- **LangGraph**：把 Agent 工作流画成有向图 + 状态机，适合需要 Human-in-the-loop、确定性重试、状态持久化的生产系统。
- **CrewAI**：静态角色扮演，大模型被约束在既定 SOP 内流转。
- **AutoGen（微软）**：对话驱动的多智能体群聊/辩论，适合代码生成与研究型实验。
- **Swarm（OpenAI）**：轻量级 Handoff 路由框架，适合任务分发实验。

### 阵营三：代码驱动与沙盒执行 (CodeAgents)

- **SmolAgents（Hugging Face）**：Code as Action——大模型直接输出 Python 并在沙盒一次性运行，缓解海量数据经 JSON 函数调用传输的 Token 压力。

### 阵营四：数据管道与系统集成 (Copilot / RAG)

- **LlamaIndex**：数据框架与 RAG 核心，通常挂载到 Agno/Dify 或自研服务承担索引检索。
- **Semantic Kernel（微软）**：企业级 Copilot 插件化总线，把 ERP 等接口封装为原生插件，内部 Planner 自动编排。
- **RAGFlow**：重型知识库 Agent，擅长啃复杂表格/扫描件/复杂排版 PDF，适合 Agentic RAG。

### 阵营五：Prompt 编译器

- **DSPy**：声明式、编译型框架，用优化器自动改写提示词/示例，离线优化复杂 Prompt 管线后回注生产。^[[[_living/AI-Infrastructure/AI-Agent-Frameworks|AI-Agent-Frameworks]]]

## 私有化二开场景选型

基于"定义工具/数据库/API，部署到自己服务器，尽量少碰底层调度"的诉求：

- **开箱即用产品化底座**：Dify
- **轻量纯 Python 单体业务**：Agno
- **强一致性后端 / C#·Java 集成**：Semantic Kernel；格式防弹用 Pydantic AI
- **企业中枢智能分发**：Swarm（Handoff 构建总闸）
- **重度数据分析报表**：SmolAgents（沙盒跑代码避免 Token 爆炸）
- **极长周期复杂软件工程**：DeepAgents（虚拟文件系统 + 任务列表引擎）
- **多模态感知 + 垂直业务（安防/IoT）**：Agno（多模态较好 + Pydantic 工具挂载控制 API）^[[[_living/AI-Infrastructure/AI-Agent-Frameworks|AI-Agent-Frameworks]]]

本仓库自身的多模态 Agent 实体 [[hermes-agent]]（及其前代 [[openclaw]]）即属于阵营一的 [[agent-harness|Harness]] 形态，并以 Markdown 作为人机交互的底层文本载体。
