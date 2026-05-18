---
title: Wikilinks & Extension Syntax
created: 2026-05-17
updated: 2026-05-17
type: concept
tags: [markdown, wiki]
sources: [_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md]
confidence: high
---

# Wikilinks & Extension Syntax

为了克服原生 Markdown 的局限，现代 Wiki 架构广泛采用了一套特定的扩展语法来组织知识拓扑。

## 双向链接 (Wikilinks)

核心格式为 `\[\[实体名称\]\]`。
它采用**无路径寻址 (Pathless Addressing)** 机制，依赖全局实体表与哈希/B 树索引，而非传统文件系统的绝对或相对路径。这使得即使文件在目录间移动，知识网络连线依然保持韧性不断裂。遇到同名冲突时，才回退至最短唯一路径策略。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

## 内联脚注 (Inline Footnotes)

核心格式为 `\^\[内联文本\]`。
这种极其紧凑的语法允许作者在不打断行文思路的情况下插入关联与溯源。解析器（如 remark-parse）在 AST 阶段自动剥离该节点，并在渲染时统一在文末生成集中式列表与返回锚点。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

**相关工具应用**:

- 最典型的实现：[[obsidian]]
- 知识库基础协议：[[markdown-llm-protocol]]
