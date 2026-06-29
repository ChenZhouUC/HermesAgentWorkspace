---
title: Ontology (本体论)
created: 2026-05-17
updated: 2026-06-29
type: concept
tags: [architecture]
sources: [_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md]
confidence: high
---

# Ontology (本体论)

在传统知识图谱与信息工程领域，Ontology（本体）扮演着数据库中 Schema（表结构）的角色。

它是对某一特定领域知识概念及概念之间关系的**形式化、显式规范说明**。
在知识录入（如构建 SPO 三元组）之前，系统必须先依靠 Ontology 来定义世界上存在哪些“类 (Class)”（例如 Person, Organization），以及这些类之间能够合法发生哪些“关系 (Relation)”（例如 Person `born_in` City）。

## 约束类型

Ontology 的约束不只是“有哪些类”。在传统知识图谱中，它通常承担四类校验职责：

- **拓扑结构约束**：定义关系的 Domain / Range、字面量数据类型和关系基数。
- **集合与分类约束**：声明类之间的互斥、包含、局部取值范围等关系。
- **逻辑推演与行为约束**：声明关系的对称性、传递性、函数性或属性链，使系统能从显式边推导隐式边。
- **实体一致性约束**：通过唯一键或标识符减少重复实体。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

OWL 更偏向表达本体和推理规则，SHACL 更偏向在数据入口做形状校验和报错。二者经常在工程上互补：前者描述世界模型，后者约束数据质量。

## 与轻量 Wiki 的关系

在大语言模型和现代 Wiki 架构普及后，极其刚性的 Ontology 设计可以被弱类型文本组织、[[wikilinks]] 和 LLM 泛化能力部分替代，从而降低知识工程冷启动成本。但这不是纯粹淘汰关系：当业务需要强一致性、合规审计或复杂多跳推理时，Ontology 仍然是 [[traditional-knowledge-graph]] 和 [[graph-rag]] 的重要结构基础。^[[[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]]]

---

**相关概念**:

- 隶属于 [[traditional-knowledge-graph]]
- 对比于免 Schema 的图谱连线设计：[[wikilinks]]
