---
title: Hybrid Search and Reciprocal Rank Fusion
created: 2026-06-29
updated: 2026-07-11
type: concept
tags: [algorithm, tool]
sources: [_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md]
confidence: high
---

# Hybrid Search and Reciprocal Rank Fusion

Hybrid Search 是把多个召回器组合起来的检索架构，常见组合包括 BM25 关键词检索、向量语义检索、文件索引、元数据过滤和图遍历。Reciprocal Rank Fusion (RRF) 是一种常用排名融合方法，用每个候选在不同检索器中的名次倒数累加得分，从而把多个排序结果合并为一个更稳的结果集。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 为什么需要混合检索

单一检索机制容易有盲区：

- BM25 对精确关键词、标识符、术语拼写敏感，但不理解语义近义表达；
- 向量检索能召回语义相近内容，但可能漏掉罕见专名、代码符号或精确字段；
- 图遍历能沿实体关系扩展上下文，但依赖图构建质量；
- 文件索引和 frontmatter 过滤能缩小范围，但不能替代内容相关性排序。

混合检索的目标不是让每个召回器都完美，而是让不同召回器的错误不完全重叠。

## RRF 的作用

RRF 不需要直接比较不同检索器的原始分数，而是只使用排名。一个候选如果在多个列表中都排得靠前，就会得到更高融合分；只在单个列表中偶然靠前的候选则更难压过跨检索器一致命中的结果。

这使 RRF 适合组合 BM25 和向量检索，因为两者的原始分数分布不同，直接加权常常不稳定。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 在 LLM 知识库中的位置

在 [[llm-wiki]] 中，Hybrid Search + RRF 常用于从页面、标题、frontmatter、正文块和图谱邻域中稳定召回上下文。它也可与 [[graph-rag]] 结合：先用关键词和向量找到入口实体，再通过图遍历扩展邻域或社区摘要。
