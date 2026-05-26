---
title: Markdown as LLM Protocol
created: 2026-05-14
updated: 2026-05-24
type: concept
tags: [architecture, llm]
sources: [_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md]
confidence: high
---

# Markdown as LLM Protocol

在 AI 时代，文本载体正经历底层重构：Markdown 逐渐取代富文本与二进制文档，成为大模型交互的默认格式。这并非偶然，而是 Token 成本、结构可解析性与训练语料分布共同推动的结果。

## 为什么 LLM 时代偏好 Markdown

1. **Token 效率高**：相比 HTML / Word XML，用 `#`、`-`、`*` 等少量字符表达结构，降低 Token 消耗、在上下文窗口保留更多有效信息。
2. **语义边界清晰**：标题、列表、代码块围栏为模型提供明确结构边界，便于区分指令、背景、数据与代码，也与 LLM 注意力机制契合。
3. **训练语料覆盖广**：GitHub、StackOverflow、Reddit 等大量使用 Markdown，使其成为预训练阶段高频接触的文本形态。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## 按受众场景的格式架构

核心洞察：信息封装格式应随**人机协作阶段**而变，不存在单一最优格式。

### 场景一：AI 读、人不读

适用 AI-to-AI 通信、System Prompt、RAG 检索、系统日志。诉求是确定性、低 Token、严格解析；人类阅读体验非重点。

- 文本：**YAML / JSON**（结构化参数与工具调用，YAML 更省 Token 但要防缩进/类型歧义）；**极简结构化 Markdown** 传递背景知识。
- 多媒体：图片/视频用 URL 绝对路径或 Base64；图表/逻辑关系转为纯文本 Graph 节点列表、JSON 树或矩阵——AI 要底层结构而非渲染后的视觉。

### 场景二：AI 和人都读

适用 Chat 上下文、Prompt 模板、人机协作文档、技能库。诉求是人机认知同频。

- 文本：**GitHub Flavored Markdown (GFM)**，在可读性与可解析性间平衡，便于在飞书/Obsidian/GitHub 间迁移。
- 多媒体：架构图用 **Mermaid.js / PlantUML**（人端渲染流程图、AI 端直接读写纯文本定义）；公式用 **LaTeX**；图片用带语义 Alt text 的 Markdown 语法。

### 场景三：人读、AI 不读

适用最终交付物、Dashboard、汇报演示、BI 看板。诉求是降低认知负担、提升可视化效率。

- 文本：**原生 UI 组件 / HTML+CSS**（飞书 Block 卡片、Notion 交互页），分栏/卡片/高亮更适合人类快速浏览，但对原生模型解析成本高。
- 多媒体：ECharts/D3.js 交互图表、MP4/流媒体、状态徽标/进度条。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## 三层数据流转架构

在 AI 软件工程中，数据流可按层次设计：

1. **底层（AI 通信）**：优先 YAML / JSON。
2. **中层（人机协作）**：优先 Markdown / Mermaid。
3. **表层（人类消费）**：优先卡片化与可视化 UI。

这一分层与 [[lmm-input-mechanics|多模态输入机制]] 互补：Markdown 是面向人类的 UI 糖，真正进入模型前仍需被解构为底层 Token 序列。

---

**Related:**

- [[lmm-input-mechanics]]
- [[wikilinks]]
