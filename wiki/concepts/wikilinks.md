---
title: Wikilinks & Extension Syntax
created: 2026-05-17
updated: 2026-06-29
type: concept
tags: [markdown, wiki]
sources: [_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md]
confidence: high
---

# Wikilinks & Extension Syntax

为了克服原生 Markdown 的局限，现代 Wiki 架构广泛采用了一套特定的扩展语法来组织知识拓扑。

## 双向链接 (Wikilinks)

核心格式为 `\[\[实体名称\]\]`。
它采用**无路径寻址 (Pathless Addressing)** 机制，优先用目标标题解析到 vault 中的 Markdown 文件，而不是要求作者维护相对路径。标题全局唯一时，`[[Note title]]` 即可表达链接；同名文件需要路径或最短可区分路径消歧。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

常见变体包括：

- `\[\[Note title|Alias\]\]`：别名只改变显示文本，不改变目标。
- `\[\[Note title#Heading\]\]`：链接到目标文档内的标题。
- `\[\[Note title#^block-id\]\]`：链接到段落级块引用。
- `!\[\[Note title\]\]` 或 `!\[\[image.png\]\]`：把目标页面、章节或附件嵌入当前页面。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

在图论语义上，wikilink 是从当前文件指向目标文件的有向边；Backlinks 是对这组有向边的反向查询。Unlinked mentions 只是文本匹配候选，不等价于已经确认的图边。

## 内联脚注 (Inline Footnotes)

核心格式为 `\^\[内联文本\]`。
这种极其紧凑的语法允许作者在不打断行文思路的情况下插入关联与溯源。解析器（如 remark-parse）在 AST 阶段自动剥离该节点，并在渲染时统一在文末生成集中式列表与返回锚点。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

**相关工具应用**:

- 最典型的实现：[[obsidian]]
- 知识库基础协议：[[markdown-llm-protocol]]
