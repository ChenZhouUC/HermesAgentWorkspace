---
title: LLM Wiki
created: 2026-06-29
updated: 2026-06-29
type: concept
tags: [llm, wiki, markdown]
sources: [_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md]
confidence: high
---

# LLM Wiki

LLM Wiki 是一种让大语言模型维护 Markdown 知识库的架构模式：系统把原始材料提炼为可读页面、索引和轻量链接，而不是把所有知识强制压缩成三元组。它适合把稳定知识提前编译成可审计的文本节点，减少每次查询时对原始材料的重复推导。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 基础结构

LLM Wiki 通常包含三层：

1. **原始信息源**：文章、聊天记录、系统日志、会议纪要或私有研究笔记。
2. **知识页面与索引**：由 LLM 提炼出的 Markdown 页面网络，以及用于入口导航的 `index.md`。
3. **Schema / Agent Instructions**：约束页面类型、命名、链接、来源、更新和清理方式的规则文件。

它和 [[traditional-knowledge-graph]] 的关键差异在于表示单元：传统 KG 以实体关系三元组为中心，LLM Wiki 以自然语言页面为中心，并用 [[wikilinks]]、frontmatter、目录和 lint 规则提供轻量结构。

## v1 与 v2

Karpathy 的 LLM Wiki idea file 是文档优先的 v1 构想：用 LLM 从原材料维护 Markdown 页面和索引。Rohit 的 LLM Wiki v2 则 fork 自这个 idea file，并结合 agentmemory 的长期记忆经验，把它扩展为更生产化的智能体知识系统。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 核心操作

- **Ingest**：从 Layer 1 原材料中提炼稳定、可复用的知识，写入或更新 Layer 2 页面。
- **Query**：通过索引、关键词搜索、页面阅读和图谱跳转回答问题。
- **Lint / Cleanup**：修复断链、重复节点、过时知识、未注册页面和格式违规。

## 生产化扩展

文档优先架构在规模变大后会遇到索引过长、旧知识污染和召回不稳的问题。因此 LLM Wiki v2 重新吸收检索系统、图谱系统和质量控制系统的做法：

- 用 [[hybrid-search-rrf]] 组合关键词召回、向量召回和图遍历；
- 在页面之上叠加实体、概念、事件和关系等 Typed Knowledge Graph；
- 用知识生命周期记录置信度、更新时间、显式更替和归档状态；
- 在代码变更、会话结束或文档更新后自动触发 ingest、冲突检测和 lint；
- 在需要跨文档推理时接入 [[graph-rag]]，把页面网络进一步组织为实体关系图或社区摘要。

LLM Wiki v2 有明确来源文本，但不是标准组织定义的规范；使用时应把它理解为 Karpathy v1 构想的社区工程化扩展。

**相关概念**:

- [[traditional-knowledge-graph]]
- [[wikilinks]]
- [[hybrid-search-rrf]]
- [[graph-rag]]
