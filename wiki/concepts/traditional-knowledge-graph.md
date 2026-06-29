---
title: 传统知识图谱 (Traditional Knowledge Graph)
created: 2026-05-17
updated: 2026-06-29
type: concept
tags: [architecture, tcs]
sources: [_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md]
confidence: high
---

# 传统知识图谱 (Traditional Knowledge Graph)

传统知识图谱是大语言模型（LLM）爆发前，符号主义（Symbolic AI）在知识表示领域的典型代表架构。它以实体、关系和三元组为核心，用本体约束保证数据一致性，并用规则或向量表示完成推理。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 核心原子结构

传统 KG 在数学上是一个**有向有标签的多重图**，其核心组件包括：

- **Entity (实体)**：等同于图的节点（Node）。
- **Relation (关系)**：等同于有向边（Edge），必须是预先定义好的类型。
- **Triple (三元组)**：即 SPO 结构（Subject 主语，Predicate 谓语，Object 宾语），是传统 KG 存储知识的最小单元。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

这种设计的局限性在于其**刚性压缩**：将丰富的自然语言强制降维成三元组时，会严重丢失语境（如时间条件、概率模糊性等复杂上下文）。

## Ontology (本体论)

Ontology 是图谱的元模型（Schema）。它预先规定了系统中存在哪些“类（Class）”，以及类与类之间允许发生什么“关系”。任何三元组的录入都必须通过本体论的规则校验。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

## 知识推理机制

传统 KG 的推理主要分为三条路线：

1. **基于逻辑规则**：利用描述逻辑与霍恩子句，进行确定性的离散符号推演。优点是可解释、可审计，缺点是对脏数据脆弱。
2. **基于表示学习 (Knowledge Embedding)**：以 **TransE** 算法为代表，将图谱结构映射到低维连续向量空间中，追求 `h + r ~= t` 的向量代数关系。
3. **基于神经符号和 LLM**：用图结构约束检索范围，再交给大模型处理自然语言语境和复杂问答，是 [[graph-rag]] 等路线的基础。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

---

**相关概念**:

- [[ontology]]
- [[graph-rag]]
- 轻量知识库替代路径：[[llm-wiki]]
