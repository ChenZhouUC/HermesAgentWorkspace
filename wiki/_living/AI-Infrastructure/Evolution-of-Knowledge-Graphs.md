---
title: Evolution of Knowledge Graphs
created: 2026-05-17
updated: 2026-05-17
---

# 知识图谱的技术演进：从符号主义到大语言模型 (Evolution of Knowledge Graphs)

在讨论现代基于 LLM 和 Markdown 构建的下一代知识库之前，有必要回溯大模型爆发前的传统知识图谱（Knowledge Graph, KG）架构。这是理解从“符号主义（Symbolic AI）”向“连接主义（Connectionism）”范式迁移的核心。

## 1. 传统知识图谱的核心概念 (The Symbolic Meta-Model)

传统 KG 在数学上被定义为一个**有向有标签的多重图 (Directed Labeled Multigraph)**，其原子结构是极其刚性的。

- **Entity (实体 / 节点 Node)**：真实世界中的具体对象或抽象概念。相当于图的顶点（Vertex）。
- **Relation (关系 / 边 Edge)**：连接两个实体的有向边，描述它们之间的相互作用或属性归属。
- **Triple (三元组 / SPO 结构)**：知识的最小存储单元，格式为 `(Subject 主语, Predicate 谓语, Object 宾语)`。例如：`(姚明, 出生于, 上海)`。
- **Ontology (本体论 / Schema)**：知识库的“表结构”。预先定义实体类（Class）以及允许存在的边类型。在录入三元组前，必须先受到 Ontology 的规则约束。

## 2. 传统知识工程的 Pipeline (Traditional KG Construction)

在大语言模型出现之前，构建 KG 是一个高门槛的“信息抽取工程”：

1. **信息抽取 (Information Extraction)**：通过级联的小模型完成 **NER (命名实体识别)** 和 **RE (关系抽取)**。
2. **知识融合 (Knowledge Fusion)**：包括实体消歧 (Disambiguation) 和共指消解 (Coreference Resolution)，用于对齐不同文本中的相同指代物。
3. **知识推理 (Knowledge Reasoning)**：
   - _逻辑规则_：基于描述逻辑和霍恩子句 (Horn Clause) 的离散符号推演。
   - _表示学习_：经典算法如 **TransE**，要求在向量空间中满足 $Head + Relation \approx Tail$。

## 3. 范式演进：传统 KG vs. LLM Wiki

现代基于 LLM 和 Markdown 的知识架构（如 Karpathy's LLM Wiki 模式）对传统 KG 实现了“降维打击”，其核心差异体现在对上下文（Context）和模糊性（Ambiguity）的容忍度上：

- **知识压缩 vs. 知识保留**：传统 KG 将丰富的自然语言强制压缩成离散的 SPO 三元组，极易丢失“特定历史条件”、“概率不确定性”等语境；而 LLM Wiki 保留了全量 Markdown 上下文，仅通过 `\[\[Wikilinks\]\]` 提供弱类型寻址。
- **构建成本的断崖式下降**：无需训练专门的 NER/RE 模型，无需设计死板的 Ontology。只需将 raw text 喂给 LLM 即可提取核心 Concepts。
- **计算复杂性视角的转换**：从图同构 (Subgraph Isomorphism) 这种 TCS 领域的强逻辑判定，转向了连续高维空间中的概率采样生成。

现代系统实际上是一种“半结构化图谱”：由文件层级的拓扑（图谱边）与文件内部的非结构化语义（LLM 注意力层）共同构成。
