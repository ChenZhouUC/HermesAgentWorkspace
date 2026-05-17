---
title: Ontology (本体论)
created: 2026-05-17
updated: 2026-05-17
type: concept
tags: [architecture]
confidence: high
---

# Ontology (本体论)

在传统知识图谱与信息工程领域，Ontology（本体）扮演着数据库中 Schema（表结构）的角色。

它是对某一特定领域知识概念及概念之间关系的**形式化、显式规范说明**。
在知识录入（如构建 SPO 三元组）之前，系统必须先依靠 Ontology 来定义世界上存在哪些“类 (Class)”（例如 Person, Organization），以及这些类之间能够合法发生哪些“关系 (Relation)”（例如 Person `born_in` City）。

在大语言模型和现代 Wiki 架构普及后，极其刚性和死板的 Ontology 设计开始被弱类型的文本组织（如 Wikilinks）和 LLM 强大的泛化理解能力所替代，从而大幅降低了知识工程的构建门槛。^[ [[_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs|Evolution-of-Knowledge-Graphs]] ]] ]

---

**相关概念**:

- 隶属于 [[traditional-knowledge-graph]]
- 对比于免 Schema 的图谱连线设计：[[advanced-markdown-syntax]]
