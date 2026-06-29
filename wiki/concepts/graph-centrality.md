---
title: Network Centrality Algorithms (网络中心性算法)
created: 2026-05-17
updated: 2026-06-29
type: concept
tags: [algorithm, math, wiki]
sources: [_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md]
confidence: high
---

# Network Centrality Algorithms (网络中心性算法)

在知识图谱与图论（Graph Theory）中，网络中心性算法用于量化节点（Node）或连线（Link）在网络结构中的重要性、枢纽作用或关系强度。对 Obsidian 这类 Markdown vault 来说，核心 Graph View 主要提供链接网络的可视化和导航；高级中心性指标通常属于插件、脚本或外部图分析层。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## 图谱建模边界

在 Markdown vault 中，最稳定的图模型是“note 作为节点，resolved wikilinks 作为边”。Unlinked mentions 只是文本匹配候选，不应直接当作语义边；tags 和 Properties 可以派生为节点或分组属性，但这是建模选择，会显著改变中心性结果。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## 节点重要性评估

- **度中心性 (Degree Centrality)**：最基础的指标，考察节点的入度（In-Degree）和出度（Out-Degree）。在知识库中，入度往往代表概念的热度，出度代表综述性文档的广度。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **加权度 / Strength**：在有权图中累加边权，而不是只计数边数。适合把引用次数、来源数量、人工置信度或访问行为纳入节点地位。
- **中介中心性 (Betweenness Centrality)**：计算图中跨越该节点的最短路径数量。高得分节点通常扮演连接不同知识领域的“跨界桥梁”角色。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **紧密中心性 (Closeness Centrality)**：衡量节点到网络中所有其他节点的平均最短距离。得分高者往往是知识库的“通识入口”，能以最少跳数触达全局。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **特征向量中心性与 PageRank**：基于“被高权重节点指向则自身权重也高”的思想，挖掘真正的骨干知识点。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **HITS 算法 (Hub & Authority)**：将网络角色分为两类。在分层架构的 Wiki 中，高 Authority 得分通常映射到处于理论底层的“概念/实体”，而高 Hub 得分映射到作为信息集散地的“目录/手册”。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **k-core / Core Number**：反复剥离低度节点，识别图中紧密互联的核心层。它衡量节点是否处在稳定核心群，而不是单点热度。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

指标解释必须结合写作习惯：入度高可能是真核心，也可能是模板或导航页噪音；出度高可能是优秀综述，也可能是过粗页面需要拆分；中介中心性高的节点尤其值得审计，因为它们控制跨主题跳转路径。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## 连线关系强度评估

用于判断未显式连接或弱连接节点间的潜在关系：

- **出现次数 / Frequency**：同一链接出现次数可用于估计显式关系强度，但要排除模板重复。
- **共引分析 (Co-citations)**：两个节点频繁在同一文档中被同时引用，揭示知识“暗网”中的强关联。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **共享出链 / Bibliographic Coupling**：两个节点指向相同对象越多，主题越可能接近。
- **杰卡德相似度 (Jaccard Similarity)**：比较相邻节点群的重合度，用于判定文档间的内容相似性。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
- **Common Neighbors**：共享邻居越多，越可能存在潜在关系；简单但偏向高度节点。
- **Adamic-Adar Index**：共享邻居越稀有，贡献越大，适合强调共同连接到小众节点的强信号。
- **Resource Allocation Index**：对高度共享邻居惩罚更强，常用于链接预测。
- **Preferential Attachment**：用两个节点度数乘积估计未来连边概率，反映“强者愈强”的网络增长机制。
- **Katz Index**：统计两个节点之间所有路径，并按路径长度衰减，用于捕捉多跳潜在关系。
- **SimRank**：如果两个节点被相似节点指向，则它们相似，适合有向引用网络中的结构相似度。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## KG 表示学习与知识补全

在传统知识图谱中，还可以用 embedding 模型估计三元组可信度和潜在边：

- **TransE**：用 `h + r ~= t` 建模关系平移，简单高效，但对复杂多重关系表达较弱。
- **TransH / TransR**：把实体投影到关系相关空间，增强复杂关系表达。
- **DistMult / ComplEx**：用双线性或复数向量打分，后者能更好处理反对称关系。
- **RotatE**：把关系建模为复数空间旋转，适合表达对称、反对称、逆关系和组合关系。
- **GNN / R-GCN**：通过邻域消息传递聚合多跳结构，将拓扑和节点特征合并建模。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

这类方法适合 KG completion、link prediction 和实体相似度估计，但需要训练数据、负采样和评估集。对个人 wiki 更现实的做法是先用局部相似度、中心性和社区发现生成候选，再由人工或 LLM 判断是否建立真实语义链接。

## 社区发现与审计用途

Louvain、Leiden、Label Propagation 等社区发现算法可以根据边密度识别主题簇。对大型 vault 来说，它们适合发现自然主题域、跨主题桥接节点、错误归类页面和可能需要拆分的大主题。但社区边界会被目录页、模板链接、标签建模和过滤规则影响，因此应作为审计线索，而不是最终分类真理。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

**相关工具应用**:

- 该算法组被深度集成于现代笔记图谱引擎中：[[obsidian]]
