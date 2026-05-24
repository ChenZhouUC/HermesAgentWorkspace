---
title: Network Centrality Algorithms (网络中心性算法)
created: 2026-05-17
updated: 2026-05-24
type: concept
tags: [algorithm, math, wiki]
sources: [_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md]
confidence: high
---

# Network Centrality Algorithms (网络中心性算法)

在知识图谱与图论（Graph Theory）中，网络中心性算法用于量化节点（Node）或连线（Link）在网络结构中的重要性、枢纽作用或关系强度。

## 节点重要性评估

- **度中心性 (Degree Centrality)**：最基础的指标，考察节点的入度（In-Degree）和出度（Out-Degree）。在知识库中，入度往往代表概念的热度，出度代表综述性文档的广度。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **中介中心性 (Betweenness Centrality)**：计算图中跨越该节点的最短路径数量。高得分节点通常扮演连接不同知识领域的“跨界桥梁”角色。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **紧密中心性 (Closeness Centrality)**：衡量节点到网络中所有其他节点的平均最短距离。得分高者往往是知识库的“通识入口”，能以最少跳数触达全局。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **特征向量中心性与 PageRank**：基于“被高权重节点指向则自身权重也高”的思想，挖掘真正的骨干知识点。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **HITS 算法 (Hub & Authority)**：将网络角色分为两类。在分层架构的 Wiki 中，高 Authority 得分通常映射到处于理论底层的“概念/实体”，而高 Hub 得分映射到作为信息集散地的“目录/手册”。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## 连线关系强度评估

用于判断未显式连接或弱连接节点间的潜在关系：

- **共引分析 (Co-citations)**：两个节点频繁在同一文档中被同时引用，揭示知识“暗网”中的强关联。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **杰卡德相似度 (Jaccard Similarity)**：比较相邻节点群的重合度，用于判定文档间的内容相似性。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

**相关工具应用**:

- 该算法组被深度集成于现代笔记图谱引擎中：[[obsidian]]
