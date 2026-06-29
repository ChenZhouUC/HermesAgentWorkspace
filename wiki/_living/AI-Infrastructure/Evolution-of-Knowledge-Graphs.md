---
title: Evolution of Knowledge Graphs
created: 2026-05-17
updated: 2026-06-29
---

# 知识图谱的技术演进：从符号主义到大语言模型 (Evolution of Knowledge Graphs)

在讨论基于 LLM 和 Markdown 构建的下一代知识库之前，需要先回溯大模型爆发前的传统知识图谱（Knowledge Graph, KG）架构。传统 KG 是符号主义 AI 在知识表示领域的典型工程形态；现代 LLM Wiki、Graph RAG 与智能体长期记忆系统，则是在不同程度上重新组合“结构化图谱”和“非结构化文本语义”的产物。

## 1. 传统知识图谱的核心概念 (The Symbolic Meta-Model)

传统 KG 在数学上通常可视为一个有向、有标签的多重图 (Directed Labeled Multigraph)。它的原子结构严格，适合表达实体、关系和约束明确的领域知识。

### 1.1 Entity / Relation / Triple

- **Entity (实体 / 节点 Node)**：真实世界中的具体对象或抽象概念，相当于图的顶点 (Vertex)。
- **Relation (关系 / 边 Edge)**：连接两个实体的有向边，描述实体之间的作用、归属或约束关系。
- **Triple (三元组 / SPO 结构)**：知识的最小存储单元，格式为 `(Subject 主语, Predicate 谓语, Object 宾语)`。

在 RDF / OWL 等语义网体系中，三元组常见分型包括：

- **关系三元组 (Object Property Triples)**：连接两个实体节点，描述实体间的社会、空间或逻辑关系。例如：`(姚明, 出生于, 上海)`。
- **属性三元组 (Datatype Property Triples)**：连接实体与字面量，描述实体的数值、字符串、日期等属性。例如：`(姚明, 身高, 2.26)`。
- **元数据三元组 (Reification / Meta-Triples)**：描述“三元组本身”的三元组，用于给边补充时间范围、来源、置信度等信息。现代属性图 (Property Graph) 或 RDF-star 规范常用类似思想处理边属性。例如：`(<<姚明, 效力于, 火箭队>>, 发生年份, 2002)`。

### 1.2 Ontology / Schema

Ontology（本体论 / Schema）是知识库的“表结构”与“逻辑质检员”。它预先定义实体类 (Class)、允许存在的边类型，以及数据进入图谱前必须满足的约束。

常见约束机制包括：

- **拓扑结构约束 (Topological / Structural Constraints)**：包括起点/终点约束 (Domain / Range)、数据类型约束 (Data Type) 和基数约束 (Cardinality)。
- **集合与分类约束 (Set & Class Constraints)**：包括互斥性约束 (Disjointness) 和局部范围约束 (Value Restrictions)，用于避免实体分类冲突或越界。
- **逻辑推演与行为约束 (Logical & Behavioral Constraints)**：定义关系的特性，如对称性、非对称性、传递性、函数性，以及属性链约束。例如 `雇佣于` + `子公司` 可推导出 `隶属于总公司`。
- **实体一致性约束 (Identity & Uniqueness Constraints)**：接近数据库的联合主键，通过 Keys 约束保障唯一现实对象不会被重复录入。

在现代工程架构中，OWL 常用于定义底层本体和逻辑规则；SHACL (Shapes Constraint Language) 则更偏向数据流入口处的形状校验和可读报错。

Ontology 的维护价值在于可以通过上位概念 (Superclass) 继承规则。例如先约束“动物”吃“食物”，猫、狗等子类即可继承这条规则。这样既能保障图谱一致性，也能降低规则维护成本。

## 2. 传统知识工程 Pipeline (Traditional KG Construction)

在大语言模型普及前，构建 KG 通常是高门槛的信息抽取工程。

1. **信息抽取 (Information Extraction)**：通过 NER (命名实体识别) 和 RE (关系抽取) 从文本中抽取实体与关系候选。
2. **知识融合 (Knowledge Fusion)**：通过实体消歧 (Disambiguation) 和共指消解 (Coreference Resolution) 对齐不同文本中的相同对象。
3. **知识推理 (Knowledge Reasoning)**：从静态数据库走向可推导知识库，主要经历三条路线。

### 2.1 逻辑规则推理 (Symbolic Reasoning)

逻辑规则流派基于描述逻辑 (Description Logic, DL)、霍恩子句 (Horn Clause) 等形式系统做离散符号推演。例如：

```text
IF 父 (A,B) AND 父 (B,C) THEN 爷 (A,C)
```

它的优势是确定性强、可解释、适合红线业务兜底；缺点是对脏数据和不完整数据脆弱，且规则建设成本高。

### 2.2 表示学习推理 (Knowledge Embedding)

表示学习流派受 Word2Vec 等分布式表示思想影响，将离散实体和关系映射到低维连续向量空间。TransE 是该路线的代表算法之一，其核心假设是：

```text
h + r ~= t
```

即真三元组中的头实体向量加关系向量后，应接近尾实体向量。此后 RotatE、ComplEx、图神经网络 (GNN) 等方法进一步增强了对复杂关系和局部图拓扑的建模能力。该路线比纯规则系统更能容忍噪声，但可解释性和严格一致性较弱。

### 2.3 神经符号与 LLM 推理 (Neuro-symbolic & LLM Reasoning)

神经符号路线试图同时利用图谱的结构约束和神经模型的泛化能力。典型做法包括：

- 用 LLM 生成的文本向量或实体描述作为图谱节点特征；
- 用图谱检索增强生成 (Graph RAG) 抽取子图、路径或社区摘要，再交给 LLM 生成答案；
- 用 LLM 辅助抽取实体关系、修复本体冲突、生成候选规则或解释推理链。

这条路线不是简单替代传统 KG，而是把图结构作为 LLM 的可控上下文组织方式。

## 3. Graph RAG：从文本块检索到图结构检索

传统 RAG 常以文本块为最小检索单位，擅长回答局部事实问题，但在全局归纳、跨文档关系、多跳问题上容易漏召回。Graph RAG 将知识图谱或文档图作为检索中间层，让系统先定位实体、关系、路径、子图或社区摘要，再把结构化上下文注入 LLM。

以 Microsoft Research 的 GraphRAG 思路为例，它的关键补充不只是“把图谱塞进 prompt”，而是把语料组织成实体关系图，并在图上生成社区摘要 (Community Summaries)。查询时可分为：

- **Local Search**：围绕查询相关实体，取邻域、边、源文本片段，适合具体实体或局部关系问题。
- **Global Search**：利用图社区摘要汇总全局主题，适合“整个语料库里有哪些主要模式/风险/趋势”这类综合问题。

因此，Graph RAG 适合处理跨文档、多实体、多跳路径和全局主题归纳；代价是索引构建、实体抽取、图维护和摘要刷新成本更高。

## 4. 范式演进：从传统 KG 到 LLM Wiki

基于 LLM 和 Markdown 的知识架构并不是传统 KG 的简单替代品，而是把“结构化索引”和“可读文本页面”重新组合。它的核心思想可以概括为：不要在每次查询时重复从原始材料里推导，而是把稳定知识提前编译成可读、可链接、可审计的 Markdown 页面。

### 4.1 LLM Wiki v1: 文档优先的基础架构原型

Andrej Karpathy 的 LLM Wiki idea file 提出：让 LLM 扮演“自动图书管理员”，从原始材料中维护一个由 Markdown 页面和索引组成的知识库。需要注意的是，这更接近公开构想或实践模式，而不是正式论文或行业标准。

其基础架构可以拆成三层：

1. **原始信息源 (Raw Sources)**：文章、聊天记录、系统日志、会议纪要等。
2. **知识页面 (Wiki Pages & Index)**：LLM 提炼出的 Markdown 页面网络，以及一个全局 `index.md` 索引。
3. **元数据模式 (Schema / Agent Instructions)**：类似 `CLAUDE.md` 或 `AGENTS.md` 的规则文件，定义页面类型、命名、链接、更新和清理方式。

核心操作包括：

- **Ingest**：从原材料提炼稳定知识，写入或更新 Wiki 页面。
- **Query**：通过索引、搜索和页面阅读来回答问题。
- **Lint / Cleanup**：定期修复断链、重复节点、过时知识和格式违规。

与传统 KG 相比，LLM Wiki 不强制把所有知识压缩成三元组，而是保留 Markdown 的自然语言上下文，只用 wikilinks、目录、frontmatter 和 schema 提供轻量结构。这降低了冷启动成本，但也弱化了严格推理和强类型校验能力。

### 4.2 LLM Wiki v2: 面向智能体的生产化扩展

Rohit 的 LLM Wiki v2 gist 明确把自己定位为 Karpathy 原始 LLM Wiki idea file 的 fork，并结合 agentmemory 的长期记忆实践，把 v1 的文档优先架构扩展为面向智能体的生产化知识系统。它指出：当页面数量增长后，单靠一次性读取 `index.md` 不再可靠；旧知识如果没有生命周期，也会污染后续回答。

因此，LLM Wiki v2 重新吸收传统 KG、检索系统和质量控制系统的思想：

- **记忆生命周期 (Memory Lifecycle)**：为知识设置置信度、更新时间、访问频率、显式更替关系和归档策略，避免所有知识永久等权。
- **Typed Knowledge Graph**：在 Markdown 页面之上叠加实体、概念、事件和关系等更强类型的结构层，支持多跳遍历和冲突追踪。
- **混合检索 (Hybrid Search)**：结合 BM25、向量检索、图遍历和文件索引，以更稳定地召回相关页面。
- **倒数秩融合 (Reciprocal Rank Fusion, RRF)**：对多个检索器的排名做融合，减少单一召回机制失效的影响。
- **事件驱动自动化 (Event-driven Automation)**：在代码变动、会话结束、文档更新等事件后触发后台 ingest、冲突检测、子图对齐或 lint。
- **质量控制 (Quality Controls)**：通过 schema 校验、断链检查、来源追踪、重复合并和 stale knowledge 清理，降低长期记忆腐化。

LLM Wiki v2 的实质是半结构化图谱：文件层级、frontmatter、wikilinks、索引和图遍历提供结构；页面正文仍保留 LLM 易读的非结构化语义。它不是传统标准组织定义的规范，但有明确的来源文本和设计主张。

## 5. References / 参考文献

- **W3C OWL 2 Web Ontology Language**: W3C 推荐标准，用于定义语义网中的类、属性、约束和可推理本体。
- **W3C SHACL (Shapes Constraint Language)**: W3C 推荐标准，面向 RDF 图的数据形状校验和约束报错。
- **Mikolov et al., Word2Vec (2013)**: 提出以连续稠密向量捕捉词语分布式语义的代表性工作。
- **Bordes et al., TransE (2013)**: 将分布式表示思想引入多关系数据建模，通过向量平移建模三元组关系。
- **Microsoft Research, From Local to Global: A Graph RAG Approach to Query-Focused Summarization (2024)**: GraphRAG 代表性工作，强调实体关系图、社区摘要、local/global search 对全局问答的价值。<https://arxiv.org/abs/2404.16130>
- **Microsoft GraphRAG documentation**: GraphRAG 官方文档，说明基于输入语料构建知识图谱、社区摘要，并在查询时增强 prompt。<https://microsoft.github.io/graphrag/>
- **Andrej Karpathy, LLM Wiki idea file**: 提出由 LLM 维护 Markdown Wiki、索引和规则文件的轻量知识库构想。<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- **Rohit, LLM Wiki v2**: Fork 自 Karpathy 的 LLM Wiki idea file，结合 agentmemory 实践提出生命周期、Typed Knowledge Graph、混合检索、事件驱动自动化和质量控制。<https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2>
- **Cormack, Clarke & Buettcher, Reciprocal Rank Fusion (2009)**: 提出 RRF 排名融合方法，用于整合多个检索器的排序结果。<https://dl.acm.org/doi/10.1145/1571941.1572114>
