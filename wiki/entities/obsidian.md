---
title: Obsidian
created: 2026-05-17
updated: 2026-07-11
type: entity
tags: [obsidian, tool, markdown]
sources: [_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md]
confidence: high
---

# Obsidian

Obsidian 是一款基于本地 Markdown vault 构建的现代知识管理工具。它的核心数据模型不是封闭数据库，而是普通文件夹中的 Markdown 文件、附件、Canvas JSON 和 `.obsidian/` 配置。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

它的核心护城河在于用 [[wikilinks]]、backlinks、Properties/frontmatter、embeds 和 MetadataCache 把普通文本文件提升为可导航、可查询的半结构化知识网络。插件 API 中的 MetadataCache 会暴露 links、embeds、tags、headings、blocks、frontmatter、resolved links 和 unresolved links 等解析结果，使 Graph View、Backlinks 面板和社区插件能增量响应文件变化。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]

Obsidian 核心 Graph View 会把笔记作为节点、links 作为边，用力导向布局做全局或局部图谱导航。更复杂的 [[graph-centrality]]、重复主题检测、外部图数据库导出和结构化查询通常来自 Dataview、Extended Graph、脚本或其他社区扩展，而不是核心图谱视图的全部默认能力。^[[[_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics|Obsidian-Knowledge-Base-Mechanics]]]
