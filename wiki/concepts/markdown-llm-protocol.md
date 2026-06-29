---
title: Markdown as LLM Protocol
created: 2026-05-14
updated: 2026-06-29
type: concept
tags: [architecture, llm]
sources: [_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md]
confidence: high
---

# Markdown as LLM Protocol

在 AI 时代，文本载体正经历底层重构：Markdown 逐渐取代一部分富文本与二进制文档，成为大模型交互的常用协作格式。这并非偶然，而是 Token 成本、结构可解析性、训练语料分布、工具链兼容性与人机共同编辑需求共同推动的结果。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## 为什么 LLM 时代偏好 Markdown

1. **Token 效率高**：相比 HTML / Word XML，用 `#`、`-`、`*` 等少量字符表达结构，降低 Token 消耗、在上下文窗口保留更多有效信息。
2. **语义边界清晰**：标题、列表、代码块围栏为模型提供明确结构边界，便于区分指令、背景、数据与代码。
3. **训练语料覆盖广**：GitHub、StackOverflow、Reddit 等大量使用 Markdown，使其成为预训练阶段高频接触的文本形态。
4. **工具链兼容**：Markdown 可被 Git diff、静态站点、Obsidian、RAG pipeline、Agent 和人类编辑器共同处理。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

## 格式选择原则

格式选择应先看消费者是谁：

| 消费者        | 主要诉求                 | 推荐格式                                 |
| ------------- | ------------------------ | ---------------------------------------- |
| AI 读、人不读 | 可解析、低 token、低歧义 | JSON, YAML, 极简 Markdown, TSV           |
| AI 和人都读   | 可读、可 diff、结构清楚  | GFM, Mermaid, LaTeX, 简洁表格            |
| 人读、AI 不读 | 展示效率、视觉层级、交互 | HTML/CSS, 原生 UI, 图表组件              |
| 机器严格执行  | schema、类型、安全边界   | JSON Schema, typed JSON, XML with schema |
| RAG 检索      | chunk 稳定、来源清楚     | Markdown + frontmatter + headings        |

核心原则是：模型读语义，人读结构，机器读 schema。越靠近执行层，格式越要严格；越靠近协作层，格式越要可读。

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

## Prompt 与 Agent 上下文协议

长 prompt 应显式隔离 task、context、constraints、examples、tools、output contract 和 user data。Markdown 标题或 XML 风格标签都可以，关键是让模型知道哪些是指令、哪些是不可信数据。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

当输出要被程序消费时，应使用 API 原生结构化输出、function calling 或 JSON Schema；只在 prompt 中写“请输出 JSON”是不够稳的。RAG 文档、网页、日志和用户粘贴文本应标记为 untrusted context，不能覆盖 system/developer 指令、工具权限和输出契约。

## RAG 文档规范

适合 RAG 的 Markdown 不是任意长文，而是能稳定切块、保留来源、chunk 自带上下文的文档：

- frontmatter 保留 title、created/updated、source、confidence 等元数据；
- 标题层级稳定，不跳级；
- 每个二级标题围绕一个主题；
- 代码块带语言；
- 表格前写明含义，复杂表改用 CSV/TSV 或 JSON；
- 结论和证据尽量相邻；
- 图片、图表、音视频保留 alt text、源数据、转写或时间戳。^[[[_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs|Text-Format-Protocol-for-LLMs]]]

常见反模式包括：无标题长文、只有截图没有文本、宽表格、视觉语义丢失、输出契约缺失、指令与数据混杂、无来源元数据。

## 三层数据流转架构

在 AI 软件工程中，数据流可按层次设计：

1. **底层（机器执行 / AI 通信）**：优先 JSON、JSON Schema、严格 TSV/CSV、必要时 XML 标签隔离。
2. **中层（人机协作 / 知识沉淀）**：优先 Markdown、Mermaid、LaTeX、frontmatter。
3. **表层（人类消费 / 汇报展示）**：优先卡片化 UI、交互图表、HTML/CSS、Dashboard。

这一分层与 [[lmm-input-mechanics|多模态输入机制]] 互补：Markdown 是面向人类的 UI 糖，真正进入模型前仍需被解构为底层 Token 序列。

---

**Related:**

- [[lmm-input-mechanics]]
- [[wikilinks]]
