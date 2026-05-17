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

## Scope (规则作用域)

- **Layer 1 / Source of Truth:** `_living/**` 由用户维护，作为原材料层。除本节与 `Living Documents Policy` 外，下文硬约束**默认不作用于 Layer 1**。
- **Layer 2 / Active Knowledge Nodes:** `entities/*.md`、`concepts/*.md`、`comparisons/*.md`、`queries/*.md`。这些页面由 Agent 维护，必须满足下文全部硬约束。
- **Meta Pages:** `SCHEMA.md`、`index.md`、`log.md`。这些页面也必须有 frontmatter，但不参与 Layer 2 节点计数。
- **Archive Pages:** `_archive/**/*.md`。归档页不属于 active graph，不得继续作为 Layer 2 的正常目标节点被引用。

## Conventions

- File names: 小写字母，连字符分隔，无空格 (e.g., `model-quantization-ptq.md`)
- Active Layer 2 页面只允许放在 `entities/`、`concepts/`、`comparisons/`、`queries/` 下；**不得**漂浮在仓库根目录
- Active Layer 2 slug 必须全库唯一；**禁止**出现同名节点
- 所有 Active Layer 2 与 Meta 页面必须以 YAML frontmatter 开头；Layer 1 只要求保持最小必要元数据
- Active Layer 2 页面使用 `[[wikilinks]]` 进行图谱连线，且每页至少 2 个**已解析**出链；指向 `_living` 的溯源脚注**不计入**出链数
- Active Layer 2 页面中，所有非代码块/非行内代码中的 `[[wikilinks]]` 都必须能解析到现存页面；**禁止 unresolved links**
- Active Layer 2 页面更新正文、frontmatter、slug 或出链时，必须同步更新 `updated` 字段
- 所有 Active Layer 2 页面必须注册到 `index.md` 的对应区块下，且**恰好出现一次**
- create / rename / replace / split / merge / archive / delete 这类核心操作需追加至 `log.md`
- **Provenance markers (溯源标记):** 当页面综合了 3 个以上来源时，在段落末尾添加 `^[raw/papers/source-file.md]` 以实现精确溯源。

## Frontmatter

_下列模板适用于 Active Layer 2 页面。Meta pages 可使用 `type: summary` 且允许 `sources: []`。_

```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query
tags: [必须从下方 Taxonomy 中选择]
sources: [_living/path/to/source.md or raw/papers/source-name.md]
confidence: high | medium | low
contested: true | false
contradictions: [other-page-slug]
---
```

### Frontmatter Invariants

- `type` 必须与目录一致：`entities/ -> entity`，`concepts/ -> concept`，`comparisons/ -> comparison`，`queries/ -> query`
- `tags` 对 Active Layer 2 页面必须为**非空列表**，且所有标签都必须已注册到下方 Taxonomy
- `sources` 对 Active Layer 2 页面必须为**非空列表**
- `updated` 必须在每次内容、结构或链接变更时同步刷新
- `contradictions` 中的 slug 必须存在，且应指向 active 页面而非 archive 页面

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

## Layer 2 Graph Invariants

- Active Layer 2 页面中的语义连线目标，默认应为其他 Active Layer 2 页面
- 示例代码、语法展示中的 `[[...]]` 必须放在代码块或行内代码中；**只有这样**才不参与 unresolved-link 校验
- Active Layer 2 页面不得引用零字节节点、根目录幽灵页或已被替换的旧 slug
- 已归档节点不得继续作为 active 页面中的正常关联目标

## Node Lifecycle (节点生命周期)

### Create

创建 Active Layer 2 节点时，必须在同一变更中完成以下动作：

1. 新建到正确目录，并使用全库唯一 slug
2. 写入完整 frontmatter（含非空 `sources`）
3. 添加至少 2 个已解析的 Layer 2 出链
4. 注册到 `index.md`
5. 追加 `log.md`

### Rename

重命名 Active Layer 2 节点时，必须在同一变更中完成：

1. 重命名文件本身
2. 全库更新旧 slug 的所有引用（正文 wikilinks、`contradictions`、`index.md`、相关 meta 页面）
3. 删除旧文件

**禁止**保留空文件、占位跳转页或零字节旧 slug 作为“兼容层”。

### Replace / Split / Merge

当一个旧节点被一个或多个新节点替代时，必须在同一变更中：

1. 建立新节点
2. 将所有 active 页面中的旧引用改指向新节点
3. 更新 `index.md`
4. 记录到 `log.md`

如果旧节点只是误建、过薄或被更精确节点完全吸收，优先直接删除，不要保留幽灵残骸。

### Archive / Delete

- **误建页、零字节页、短命 ghost page：** 直接删除，**不要归档**
- **确有历史价值但不再 active 的页面：** 移入 `_archive/`，并同时：
  1. 从 `index.md` 移除
  2. 清除所有来自 active Layer 2 页面的引用
  3. 确保不再作为 graph 的正常目标节点

## Validation Invariants (强校验清单)

每次同步、重构或批量生成后，至少满足以下条件：

1. `entities/`、`concepts/`、`comparisons/`、`queries/` 中不存在零字节 Markdown 文件
2. 仓库根目录不存在漂浮的 Active Layer 2 节点
3. Active Layer 2 slug 全库唯一
4. Active Layer 2 页面全部具备完整 frontmatter，且 `sources`、`tags` 非空
5. Active Layer 2 页面中不存在 unresolved wikilinks（代码块/行内代码中的示例除外）
6. 每个 Active Layer 2 页面在 `index.md` 中**恰好登记一次**
7. `index.md` 不得登记不存在、已归档或已被替换的 slug
8. 若 `index.md` 维护 `Total pages` 字段，则该值必须等于已登记的 Active Layer 2 节点数

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
