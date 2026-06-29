---
title: Text Format Protocol for LLMs
created: 2026-05-14
updated: 2026-06-29
---

# AI 时代文本载体协议：基于大模型交互场景的格式架构设计

在 AI 时代，文本载体正在发生底层重构。Markdown 逐渐取代一部分富文本和传统二进制文档，成为大模型（LLM）交互中的常用格式。这并不是偶然，而是由 Token 成本、结构可解析性、训练语料分布、工具链兼容性和人机共同编辑需求共同推动的结果。

本文讨论的“文本格式协议”不是单一文件格式，而是一组工程约定：什么信息用 Markdown，什么信息用 JSON/YAML/XML/CSV，什么信息应该渲染给人看，什么信息应该保留为模型可解析的底层结构。

## 1. 为什么大模型时代偏好 Markdown？

### 1.1 Token 效率高

相比 HTML 或 Word 底层 XML，Markdown 用较少字符表达标题、列表、引用、代码块和链接。例如：

```markdown
## Error Handling

- Retry transient errors
- Escalate permission errors
```

等价 HTML 会引入大量标签噪音。对上下文窗口有限的 LLM 来说，格式 token 越少，有效语义 token 越多。

### 1.2 语义边界清晰

Markdown 的标题、列表、引用块、表格和代码围栏提供了明确的层级边界。模型更容易区分：

- 指令与背景；
- 结论与证据；
- 自然语言与代码；
- 正文与结构化数据；
- 主任务与附录。

尤其是 fenced code block 可以稳定承载 JSON、YAML、SQL、Python、Mermaid 等子语言，避免模型把代码和解释混在一起。

### 1.3 训练语料覆盖广

GitHub、StackOverflow、Reddit、技术博客、README、issue、PR 描述中大量使用 Markdown。许多模型在预训练和指令微调阶段高频接触这种文本形态，因此对 Markdown 的标题、列表、代码块和链接语义有较强先验。

### 1.4 工具链兼容

Markdown 可以同时被人类编辑器、Git diff、静态站点生成器、Obsidian、RAG pipeline、LLM agent 和文档系统处理。它的优势不是渲染能力最强，而是“足够结构化 + 足够可读 + 足够可迁移”。

## 2. 格式选择的核心原则

选择文本格式时，应先判断信息流的消费者是谁。

| 消费者        | 主要诉求                 | 推荐格式                                 | 避免格式                      |
| ------------- | ------------------------ | ---------------------------------------- | ----------------------------- |
| AI 读，人不读 | 可解析、低 token、低歧义 | JSON, YAML, 极简 Markdown, CSV/TSV       | 富文本、复杂 HTML、图片化表格 |
| AI 和人都读   | 可读、可 diff、结构清楚  | GFM, Mermaid, LaTeX, 简洁表格            | 复杂嵌套 JSON、无标题长文本   |
| 人读，AI 不读 | 展示效率、视觉层级、交互 | HTML/CSS, 原生 UI, 图表组件              | 为 AI 优化的冗长结构          |
| 机器严格执行  | schema、类型、安全边界   | JSON Schema, typed JSON, XML with schema | 自由 Markdown、宽松 YAML      |
| RAG 检索      | chunk 稳定、来源清楚     | Markdown + frontmatter + headings        | PDF 扫描图、无结构长文        |

核心原则：

1. **模型读语义，人读结构，机器读 schema**。
2. **越靠近执行层，格式越要严格**；越靠近协作层，格式越要可读。
3. **不要把视觉排版当成语义结构**。颜色、分栏、图标对人有用，但对模型和检索系统不稳定。
4. **不要为了省 token 牺牲边界清晰度**。短但歧义的 prompt 往往比稍长但结构明确的 prompt 更贵。

## 3. 常见格式的适用边界

### 3.1 Markdown / GFM

适合：

- Prompt 模板；
- 人机协作文档；
- RAG 原始知识页；
- README、设计文档、操作手册；
- LLM Wiki / Obsidian vault。

优势：

- 人类可读；
- Git diff 友好；
- 标题层级天然适合 chunk；
- 代码块可嵌入子语言；
- 链接、表格、列表能表达轻量结构。

风险：

- 标准方言多，GFM、CommonMark、Obsidian 扩展不完全一致；
- 表格不适合复杂嵌套数据；
- 任意 Markdown 不等于严格 schema；
- heading 层级混乱会降低 RAG chunk 质量。

推荐子集：

- 标题：只用 `#` 到 `####`，避免跳级；
- 列表：同一层级保持同一种 bullet 风格；
- 代码块：必须带语言标识；
- 表格：只用于小规模二维数据；
- 链接：给出可读 anchor text；
- 图片：必须写有信息量的 alt text。

### 3.2 JSON

适合：

- 工具调用参数；
- API payload；
- 结构化输出；
- 严格 schema 校验；
- 多模态消息数组。

优势是类型明确、解析器成熟、生态稳定。缺点是 token 开销较高，长文本中大量引号、括号和转义会降低可读性。

适用原则：

- 机器必须解析和执行时，优先 JSON；
- 输出必须进入下游程序时，优先 JSON + JSON Schema；
- 人类长期维护大段文本时，不优先 JSON。

### 3.3 YAML

适合：

- frontmatter；
- 配置文件；
- 短结构化元数据；
- 人类可读的参数块。

优势是比 JSON 更紧凑、可读性更好。风险是缩进敏感、隐式类型和多行字符串语义容易出错，例如 `yes`、`on`、日期、冒号、缩进层级都可能产生歧义。

适用原则：

- 人类编辑的轻量配置可用 YAML；
- 安全敏感、严格执行、跨语言 API 不应依赖宽松 YAML；
- LLM 输出 YAML 时，应给定字段模板和示例。

### 3.4 XML / 标签化文本

适合：

- prompt 中显式划分区域；
- 嵌套结构清晰的长上下文；
- 需要防止指令和数据混淆的场景。

示例：

```xml
<task>
Summarize the document.
</task>
<context>
User-provided content goes here.
</context>
```

XML 比 Markdown 更啰嗦，但标签边界显式，适合在 prompt 中隔离 system instruction、developer instruction、user data、examples 和 output contract。

### 3.5 CSV / TSV

适合：

- 大量同构行；
- 简单二维表；
- 数据分析和批处理；
- token 效率优先的列表数据。

风险：

- 列含义必须明确；
- 单元格内换行、逗号、引号容易破坏解析；
- 不适合嵌套对象；
- 缺少类型信息。

LLM 场景中，TSV 往往比 CSV 更少转义问题。

### 3.6 HTML / 富文本 / 原生 UI

适合：

- 最终展示；
- Dashboard；
- 富交互报告；
- 对人类视觉扫描优化的交付物。

不适合直接作为模型输入的原因：

- 标签噪音多；
- 样式和语义混杂；
- DOM 层级可能远比实际语义复杂；
- 大量 class、style、script 对模型任务无效。

如果必须让 LLM 读取网页，最好先抽取正文、标题、列表、表格和链接，转换为简化 Markdown 或结构化 JSON。

## 4. 基于不同受众场景的文本与多媒体架构

### 场景一：AI 读，人不读

适用场景：AI-to-AI 通信、system prompt、RAG 知识检索、系统日志、工具调用。

核心诉求：确定性、低 token 占用、严格解析规则。人类阅读体验不是重点。

推荐文本格式：

- JSON：用于工具调用、API payload、结构化输出。
- YAML：用于短配置、frontmatter、人工可维护参数。
- 极简结构化 Markdown：用于传递背景知识、步骤、策略和长上下文。
- TSV/CSV：用于同构行数据。

推荐多媒体格式：

- 图片 / 视频：使用 URL、文件引用或模型 API 支持的多 part 输入。
- 图表 / 逻辑关系：转化为 Mermaid、Graph edge list、JSON 树、邻接表或矩阵数组。
- 表格截图：优先 OCR 或源数据导出，不要把视觉图像当成唯一数据源。

### 场景二：AI 和人都读

适用场景：chat 交互上下文、prompt 模板设计、人机协作文档、技能库、LLM Wiki。

核心诉求：人机认知同频。既要方便人类阅读和编辑，也要让 AI 能稳定理解逻辑层级。

推荐文本格式：

- GitHub Flavored Markdown：在人类可读性和机器可解析性之间取得较好平衡。
- Mermaid / PlantUML：人类端可渲染为流程图、时序图，AI 端可直接读写纯文本定义。
- LaTeX：数学公式的主格式。
- Markdown table：适合短表；复杂表应改为 CSV/TSV 或 JSON。

推荐多媒体格式：

- 图片：使用带语义描述的 Markdown 图片语法，让 alt text 成为 AI 理解图片上下文的提示。
- 图表：保留生成图表的源数据和文本定义，不只保留渲染图。
- 音视频：附转写文本、章节时间戳和摘要。

### 场景三：人读，AI 不读

适用场景：最终分析交付物、数据 Dashboard、汇报演示文稿、BI 看板。

核心诉求：降低认知负担、提升可视化表达效率和信息吸收速度。

推荐文本格式：

- 原生 UI 组件 / HTML+CSS：如飞书 Block 卡片、Notion 交互式页面。
- 卡片、分栏、高亮块、徽标、进度条：适合人类快速浏览。

推荐多媒体格式：

- ECharts、D3.js、Vega-Lite 等交互图表；
- MP4 或流媒体组件；
- 可悬停、下钻、筛选的 BI 组件。

注意：这些格式适合最终消费，但不一定适合进入 RAG 或 Agent 工作记忆。需要被 AI 复用的结论，应另存为 Markdown 摘要或结构化数据。

## 5. Prompt / Agent 上下文的格式协议

### 5.1 区块隔离

长 prompt 应显式区分：

- task：当前要完成什么；
- context：背景材料；
- constraints：硬约束；
- examples：示例；
- tools：可用工具或 API；
- output contract：输出格式；
- user data：不可信输入。

可用 Markdown 标题，也可用 XML 风格标签。关键是避免让模型把用户提供的数据误读成更高优先级指令。

### 5.2 输出契约

当输出要被程序消费时，必须给出明确契约：

````markdown
Return only valid JSON:

```json
{
  "decision": "approve | reject | needs_more_info",
  "reasons": ["..."],
  "confidence": "high | medium | low"
}
```
````

````

工程上更稳的做法是使用 API 原生结构化输出、function calling 或 JSON Schema，而不是只在 prompt 中说“请输出 JSON”。

### 5.3 示例格式

few-shot 示例应保持输入输出边界清晰：

```text
<example>
<input>
...
</input>
<output>
...
</output>
</example>
````

示例数量不宜过多。过多示例会挤占上下文，并可能让模型模仿无关细节。

### 5.4 不可信内容隔离

RAG 文档、网页、用户粘贴文本和日志都应视为不可信内容。格式上应明确标记：

```xml
<untrusted_context>
...
</untrusted_context>
```

模型指令中应声明：不可信内容只能作为数据，不得覆盖 system/developer 指令、工具权限和输出契约。

## 6. RAG 文档的 Markdown 规范

RAG 不是把所有文档原样塞进向量库。好的 RAG 文档应让 chunk 自带上下文。

推荐规范：

- 每篇文档保留 title、created/updated、source、confidence 等 frontmatter；
- 标题层级稳定，不跳级；
- 每个二级标题下围绕一个主题；
- 长列表拆成小节；
- 表格前写一句说明表格含义；
- 代码块带语言；
- 结论和证据尽量相邻；
- 每个 chunk 能独立回答“它在讲什么”。

反模式：

- 无标题长文；
- 只有截图没有文本；
- 表格过宽；
- 把多个主题堆在一个段落；
- 大量“如上”“见下图”“这个问题”等依赖视觉上下文的指代；
- 链接只有“点击这里”而无语义 anchor。

## 7. 多模态输入的文本化原则

多模态模型可以读图，但工程上仍应尽量保留文本结构：

- 图片：提供 alt text、来源、拍摄/生成时间、关键区域说明；
- 图表：保留源数据、坐标轴、单位、图例和生成代码；
- 视频：提供转写、时间戳、关键帧描述；
- 音频：提供转写、说话人、时间戳；
- PDF：优先抽取正文、标题、表格和脚注，再附原文件。

对 LLM 来说，渲染后的视觉对象通常是高成本输入；底层结构才是稳定可复用的信息。

## 8. 常见反模式

1. **伪结构化 Markdown**：看起来有列表，实际层级混乱、字段不固定、无法解析。
2. **过度 JSON 化**：把长篇解释文本塞进深层 JSON，导致人类难以维护。
3. **宽松 YAML 执行层**：让 LLM 生成 YAML 后直接执行，容易被缩进、类型和转义坑住。
4. **HTML 原样入模**：大量 class/style/script 稀释有效语义。
5. **视觉语义丢失**：只保留图表截图，不保留数据和说明。
6. **输出契约缺失**：下游要解析，却只要求“按清晰格式回答”。
7. **指令与数据混杂**：RAG 内容、用户文本和系统指令没有边界，增加 prompt injection 风险。
8. **无来源元数据**：知识进入系统后无法判断版本、可信度和更新时间。

## 9. 架构总结

在 AI 软件工程中，数据流转可以按以下层次设计：

1. **底层（机器执行 / AI 通信）**：优先 JSON、JSON Schema、严格 TSV/CSV、必要时 XML 标签隔离。
2. **中层（人机协作 / 知识沉淀）**：优先 Markdown、Mermaid、LaTeX、frontmatter。
3. **表层（人类消费 / 汇报展示）**：优先卡片化 UI、交互图表、HTML/CSS、Dashboard。

最终原则：底层要可解析，中层要可协作，表层要可感知。不要指望一种格式同时优化所有层。
