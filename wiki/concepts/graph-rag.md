---
title: Graph RAG
created: 2026-06-29
updated: 2026-07-11
type: concept
tags: [llm, architecture, reasoning]
sources: [_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md]
confidence: high
---

# Graph RAG

Graph RAG 是把知识图谱或文档图作为检索中间层的 RAG 架构。它不只检索相似文本块，而是先定位实体、关系、路径、邻域子图或社区摘要，再把结构化上下文交给大语言模型生成答案。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 解决的问题

普通文本块 RAG 擅长局部事实问答，但在以下场景中容易漏召回或缺少全局视野：

- 一个问题跨越多个实体或多篇文档；
- 答案依赖多跳关系路径；
- 用户要求总结整个语料库的主题、风险或趋势；
- 原文块相似度不高，但实体关系高度相关。

Graph RAG 用图结构补足这些弱点。图谱中的实体、边和社区结构充当检索路由，让系统可以沿关系扩展上下文。

## Local Search 与 Global Search

Graph RAG 常见两类查询路径：

- **Local Search**：围绕查询相关实体取邻域、边、源文本片段和路径，适合具体实体或局部关系问题。
- **Global Search**：先读取图社区或主题摘要，再综合回答全局归纳类问题。

Microsoft Research 的 GraphRAG 工作强调社区摘要对 query-focused summarization 的价值：系统先从语料抽取实体关系图，再为图社区生成摘要，使 LLM 可以回答跨文档的全局问题。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 与其他架构的关系

Graph RAG 继承了 [[traditional-knowledge-graph]] 的结构化表示能力，但把最终推理和语言生成交给 LLM。它也可以作为 [[llm-wiki]] 的生产化增强：当 Markdown 页面网络不足以支撑复杂多跳问题时，系统可在页面之上叠加实体关系图和社区摘要。

代价是索引构建更重，需要实体抽取、关系抽取、图维护和摘要刷新；在数据源频繁变化的场景中，更新成本高于普通文本检索。
