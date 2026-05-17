---
title: Wiki Schema
created: 2026-05-14
updated: 2026-05-17
type: summary
tags: [wiki, tool]
sources: []
confidence: high
---

# Wiki Schema

## Domain

AI 基础设施与推理计算 (AI Infrastructure & Edge Inference)
AI 算法工程与统计学习 (Algorithm Engineering & Statistical Learning)
全栈 AI 应用与软硬件运维 (AI Applications, Edge/Cloud & HW/SW Ops)
理论计算机科学与数学推导 (TCS & Math in AI)

## Conventions

- File names: 小写字母，连字符分隔，无空格 (e.g., `model-quantization-ptq.md`)
- 所有页面必须以 YAML frontmatter 开头
- 使用 `[[wikilinks]]` 进行双向链接（每页至少 2 个出链）
- 更新页面时，必须更新 `updated` 字段
- 所有新页面必须注册到 `index.md` 的对应区块下
- 核心操作记录需追加至 `log.md`
- **Provenance markers (溯源标记):** 当页面综合了 3 个以上来源时，在段落末尾添加 `^[raw/papers/source-file.md]` 以实现精确溯源。

## Frontmatter

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [必须从下方 Taxonomy 中选择]
sources: [raw/papers/source-name.md]
confidence: high | medium | low
contested: true
contradictions: [other-page-slug]
---
```

## Tag Taxonomy (标签库)

_新增标签前必须在此处注册_

- **硬件与边缘节点 (Hardware & Edge):** `edge-inference`, `rk3576`, `sophgo`, `npu`, `tpu`, `edge-computing`
- **模型与架构 (Models & Arch):** `architecture`, `llm`, `vlm`, `transformer`, `state-space`
- **优化与工程 (Optimization):** `quantization`, `tensorrt`, `onnx`, `system-prompt`, `alignment`
- **全栈与运维 (Applications & Ops):** `agent`, `macos`, `ops`, `gateway`
- **算法与数学 (Algorithms & Math):** `tcs`, `statistics`, `proof`, `complexity`, `algorithm`, `math`, `logic`
- **知识管理与工具 (Knowledge Management & Tools):** `wiki`, `markdown`, `obsidian`, `tool`
- **元数据 (Meta):** `comparison`, `benchmark`, `paper`

## Page Thresholds (页面创建标准)

- **实体与流程解耦 (Entity-Process Decoupling)**：严格区分名词与动词。软件、硬件、理论（名词）应作为独立的 Entity 或 Concept 提取；操作手册、部署流程、业务流水线（动词/流程）应保留在 Layer 1 中。**绝不能**将“XX 操作指南”直接打包为一个图谱节点，提取时必须“粉碎重组”出核心实体，并让这些实体单向溯源至该流程文档。
- **创建页面：** 实体/概念在独立文献中作为核心探讨，或在多个文档中出现 2 次以上。
- **拆分页面：** 页面超过 200 行时，按子主题拆分。
- **归档页面：** 内容被完全推翻或过时，移入 `_archive/` 并从 index 移除。

## Update Policy (更新策略)

当新信息与旧信息冲突时：

1. 检查日期，通常较新的研究覆盖旧研究。
2. 属于学术争议时，必须同时保留两种观点，并附带各自的来源和日期。
3. 在 Frontmatter 中标记 `contradictions: [page-name]`。

## Living Documents Policy (活体文档同步规则)

对于外部持续更新的个人笔记或配置文档：

1. **绝不放入 `raw/`**：统一存放或镜像至 `_living/` 目录，且不添加 `sha256` 校验。
2. **保持高内聚，禁止污染源文档 (单向引用原则)**：`_living` 目录下的文档作为原材料 (Source of Truth)，必须保持纯净，由用户手动维护。Agent **绝不允许**向 `_living` 下的文档底部或正文中主动写入任何指向图谱的 `[[wikilinks]]` 或隔离线。
3. **原材料元数据极简化 (No Semantic Metadata in Layer 1)**：`_living` 中的文档不需要（也不推荐）包含上层知识图谱的结构化元数据（如 `tags`, `type`, 或显式的 `concepts` 链接）。原材料只需陈述事实和业务逻辑。知识体系的分类（Tags）和概念提炼（Concepts）完全由 Agent 在同步时于 Layer 2 自行负责构建。
4. **通过 Layer 2 溯源建立图谱关系**：所有的知识网状连线，必须由 Layer 2 (Concepts/Entities) 页面通过**紧凑的内联脚注语法**（例如：`^[[[_living/xxx/xxx|显示别名]]]`）**单向、主动地指向** Layer 1。
   - **核心红线**：在 `^[` 和 `[[` 之间，以及 `]]` 和 `]` 之间，**绝对不允许有任何空格**。空格会触发 Obsidian 渲染器的 Bug 导致显示残留的 `] ]`。
   - 采用此紧凑语法后，正文中会被无缝渲染成干净的 `[1]` 上标，并在阅读视图末尾由 Obsidian 引擎**自动生成**包含双链的回溯列表，从而免去手动维护文末 `[^1]: ...` 的冗余文本。
5. **常规同步 (Incremental)**：默认模式。读取新内容，提取最新主张 (Claims)，去 Layer 2 对碰。修改冲突、补充新增，但*不自动清理静默删除的幽灵知识*。
6. **深度同步/重构 (Deep Sync)**：必须由用户显式声明触发（如“已做大规模删减，请做深度同步”）。Agent 会顺着该文档的溯源标记 (`^[_living/xxx.md]`) 反向遍历 Layer 2，清理掉所有在新草稿中已丢失的旧陈述。
7. **单点重置 (Override)**：当该篇活体文档是某领域的绝对唯一真理时，允许直接重置/覆写对应的 Layer 2 页面。
