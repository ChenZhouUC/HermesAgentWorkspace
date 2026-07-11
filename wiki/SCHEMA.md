---
title: Wiki Schema
created: 2026-05-14
updated: 2026-07-11
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

- **Layer 1 / Source Materials:** `_living/**` 与 `raw/**` 共同构成原始材料层，供 Layer 2 提炼、引用和溯源。下文面向 Active Layer 2 的硬约束**默认不作用于 Layer 1**。
  - **Living Sources:** `_living/**`。用户私有手写、持续更新的运维知识与研究笔记；由用户维护，Agent 不主动污染正文或添加图谱链接。
  - **Raw Reference Sources:** `raw/**`。承载具有**公开版本属性**的外部内容——互联网网页、论文、书籍、杂志期刊等；用于给 Layer 2 提供可复核的外部引用锚点，推荐保留来源 URL、访问/发布日期与 sha256 校验以追踪版本。
- **Layer 2 / Active Knowledge Nodes:** `entities/*.md`、`concepts/*.md`、`comparisons/*.md`、`queries/*.md`。这些页面由 Agent 维护，必须满足下文全部硬约束。
- **Meta Pages:** `SCHEMA.md`、`index.md`、`log.md`。这些页面也必须有 frontmatter，但不参与 Layer 2 节点计数或语义 wikilink 网络；它们之间以及其他页面指向它们的导航使用纯文本 / 代码路径，不使用普通 wikilink。
- **Archive Pages:** `_archive/**/*.md`。归档页不属于 active graph，不得继续作为 Layer 2 的正常目标节点被引用。

## Maintenance Entry Checklist (运维入口检查)

任何 agent 会话只要用户请求涉及 `wiki/**` 的读取、审计、同步、重构、ingest、删除、Obsidian 载体配置或 `scripts/wiki_lint.py`，都必须在动手前执行本入口检查；不得只依赖记忆中的旧 schema。

1. **先读当前 SCHEMA**：完整读取本文件，确认最新 Layer 边界、Frontmatter、Tag Taxonomy、Lifecycle、Validation、Daily Log 与 Obsidian Carrier 规则。
2. **判定变更类别**：把本轮操作归类为只读审计、Layer 1 原材料更新、Layer 2 节点维护、Meta 页面维护、Obsidian 载体维护或 lint/tooling 维护；不同类别按对应章节执行。
3. **触发 lint 共演进 gate**：若本轮改动 `SCHEMA.md`，或新增/移动标签，或改变 layer/path/frontmatter/wikilink/provenance/index/log/Obsidian 本地配置规则，必须执行 `Lint Co-evolution Policy`，明确哪些新增规则进入 `scripts/wiki_lint.py`，哪些保持人工判断。
4. **触发 Obsidian carrier gate**：若本轮触及 `wiki/.obsidian/**`、Obsidian 插件体验、插件配置或 wiki 运维 SOP，必须执行 `Obsidian Carrier Maintenance`；本地 manifest/list 一致性由 lint 校验，版本、默认配置与前端事项需在汇报中说明。
5. **收尾验证与日志**：任何写操作后至少运行 `python3 scripts/wiki_lint.py`；若改动 `SCHEMA.md`、`scripts/wiki_lint.py` 或机器读取格式，也必须运行 `python3 scripts/wiki_lint.py --json`。所有结构性维护按 `Daily Log Policy` 记录到 `log.md`。

## Conventions

- Active Layer 2 file names: 小写字母，连字符分隔，无空格 (e.g., `model-quantization-ptq.md`)；Layer 1 原材料可保留来源标题的大小写以减少导入损耗
- `_living/` 一级分类目录必须是 2 或 3 个词段组成的 kebab-case 主题名（如 `AI-Infrastructure`、`TCS-and-Math`、`Whale-SpaceSight`）；词段允许大小写字母与数字，禁止空格、下划线、单词数 < 2 或 > 3 的泛化桶目录
- Active Layer 2 页面只允许放在 `entities/`、`concepts/`、`comparisons/`、`queries/` 下；**不得**漂浮在仓库根目录
- Active Layer 2 slug 必须全库唯一；**禁止**出现同名节点
- 所有 Active Layer 2 与 Meta 页面必须以 YAML frontmatter 开头；`_living/` 只要求保持最小必要元数据；`raw/` 推荐保留外部来源、访问/发布日期与 sha256 等可复核元数据
- Active Layer 2 页面使用 `\[\[wikilinks\]\]` 进行图谱连线；**鼓励**每页至少 2 个**已解析**出链以维持图连通性，但若严格遵守"关联谨慎保守原则"后只能给出 0 或 1 条强关联，则保留少链优于强加弱链（详见 `Layer 2 Graph Invariants` 章节）。指向 Layer 1（`_living/` / `raw/`）的溯源脚注**不计入**出链数。
- Active Layer 2 页面中，所有非代码块/非行内代码中的 `\[\[wikilinks\]\]` 都必须能解析到现存页面；**禁止 unresolved links**
- Active Layer 2 页面更新正文、frontmatter、slug 或出链时，必须同步更新 `updated` 字段
- 所有 Active Layer 2 页面必须注册到 `index.md` 的对应区块下，且**恰好出现一次**；登记行以带类型目录的行内代码路径开头（如 `entities/slug.md`），后接一句话摘要，不得使用 wikilink，以免索引页成为语义图谱的伪中心节点
- create / rename / replace / split / merge / archive / delete 这类核心操作需记录到 `log.md`；同一天的多项维护按 `Daily Log Policy` 合并到当天唯一条目
- **Provenance markers (溯源标记):** 两种语法按目标层级选择：
  - 指向 `_living/` 私有文档：使用紧凑内联脚注 `^[[[_living/path/to/file|显示别名]]]`（详见 `Living Documents Policy` 第 4 条的红线约束）。
  - 指向 `raw/` 公开版本资源：使用简洁脚注 `^[raw/papers/source-file.md]`，多源混合页面（综合 3 个以上来源）在段落末尾追加以实现精确溯源。

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
contested: true | false # optional; only required for contested pages
contradictions: [other-page-slug] # optional; only required when explicit contradictions exist
---
```

### Frontmatter Invariants

- `type` 必须与目录一致：`entities/ -> entity`，`concepts/ -> concept`，`comparisons/ -> comparison`，`queries/ -> query`
- `tags` 对 Active Layer 2 页面必须为**非空列表**，且所有标签都必须已注册到下方 Taxonomy
- `sources` 对 Active Layer 2 页面必须为**非空列表**
- `updated` 必须在每次内容、结构或链接变更时同步刷新
- `contested` / `contradictions` 为条件字段；存在明确争议或冲突时才需要填写
- `contradictions` 中的 slug 必须存在，且应指向 active 页面而非 archive 页面

## Tag Taxonomy (标签库)

_新增标签前必须在此处注册_

- **硬件与边缘节点 (Hardware & Edge):** `edge-inference`, `rk3576`, `sophgo`, `npu`, `tpu`, `edge-computing`
- **模型与架构 (Models & Arch):** `architecture`, `llm`, `vlm`, `transformer`, `state-space`, `reasoning`
- **优化与工程 (Optimization):** `quantization`, `tensorrt`, `onnx`, `system-prompt`, `alignment`
- **计算机视觉 (Computer Vision):** `computer-vision`, `reid`, `clustering`
- **Agent 与编排 (Agent & Orchestration):** `agent`, `orchestration`, `harness`, `react`, `context-management`, `sandbox`, `hitl`, `protocol`, `multi-agent`
- **全栈与运维 (Applications & Ops):** `macos`, `ops`, `gateway`, `pipeline`
- **业务与项目 (Business & Projects):** `spacesight`, `product-management`, `compliance`
- **算法与数学 (Algorithms & Math):** `tcs`, `statistics`, `proof`, `complexity`, `algorithm`, `math`, `logic`
- **知识管理与工具 (Knowledge Management & Tools):** `wiki`, `markdown`, `obsidian`, `tool`
- **元数据 (Meta):** `comparison`, `benchmark`, `paper`

## Page Thresholds (页面创建标准)

- **实体与流程解耦 (Entity-Process Decoupling)**：严格区分名词与动词。软件、硬件、理论（名词）应作为独立的 Entity 或 Concept 提取；操作手册、部署流程、业务流水线（动词/流程）应保留在 Layer 1 原材料中。**绝不能**将"XX 操作指南"直接打包为一个图谱节点，提取时必须"粉碎重组"出核心实体，并让这些实体单向溯源至该流程文档。
- **创建页面：** 实体/概念在独立文献中作为核心探讨，或在多个文档中出现 2 次以上。
- **拆分页面：** 页面超过 200 行时，按子主题拆分。
- **归档页面：** 内容被完全推翻或过时，移入 `_archive/` 并从 index 移除。

### Granularity Heuristics (颗粒度启发式)

> **以下为原则性指引，不是硬阈值**。不同模型/不同参数下执行效果会有差异，按"原则上要求"理解；遇到边界情形，优先保守不提取，等下次复核再决定。

- **理想颗粒度判据**：一个 Layer 2 节点应当是**作为整体研究有意义的研究对象**——既能用一句话给出它的定义，也值得围绕它写出一篇独立的、超过几段的描述。
- **过细的反模式**：把"某函数"、"某配置项"、"某表的某列"提成 entity——这些是实现细节，应留在 Layer 1 原材料中。判据：**如果离开它的母体上下文就讲不清楚**，则颗粒度过细。
- **过粗的反模式**：把"AI 系统"、"知识库"这种主题词提成 concept——内涵过宽、不能聚焦讨论。判据：**如果一句话定义需要列举三个以上独立子主题**，则颗粒度过粗。
- **父子并存允许**：如果父节点（如某个框架）和子节点（如该框架的某个核心子模块）**双方独立都满足"整体研究对象"判据**，允许同时提取。父子节点之间通过 wikilinks 显式声明关系。
- **优先粉碎重组而非整体打包**：来源 Layer 1 文档常是混合材料；Agent 不应一对一映射 Layer 1 → Layer 2，而应识别其中可独立成立的研究对象、按主题颗粒度重组。

## Type Semantics (四种类型的语义与触发条件)

> **以下为原则性指引**。Layer 2 的类型选择带有主观判断成分；不同模型在不同参数下执行可能存在差异。Agent 应当按以下意图理解，遇到模糊情形优先选择保守判断（宁可不建，也不强建）。

### entity (实体)

- **定位**：具体存在的"名词性"对象——软件、产品、硬件设备、公司、模型、框架、协议规范。
- **触发**：该对象在 Layer 1 文档中作为被讨论的主语反复出现，且具备独立的"产品级"身份（有名字、有版本、有边界）。
- **不要建**：抽象方法学、设计原则、算法思想——这些归 concept。

### concept (概念)

- **定位**："动词/方法学性"的抽象——算法范式、设计模式、技术原理、理论框架、能力分类。
- **触发**：可以独立讨论"这是什么 / 为什么有用 / 何时使用"，且**不依附于某个具体产品名**。
- **不要建**：某个产品的特定功能描述（归该产品的 entity）；过细的实现技巧（归 \_living）。

### comparison (横向对比)

- **触发**：当 Layer 1 原始文档中明显存在以下任一信号时，提取为 comparison：
  - **选型分析**：作者明确在权衡多个候选方案；
  - **优劣势对比**：分别列出各方案的强项弱项；
  - **A vs B 架构比较**：明确以"对比"为论述结构。
- **跨文档触发**：即便两个对象出自不同 Layer 1 文档，只要它们之间存在**强相关、强可比、且现实场景里需要二选一**的关系，也允许提炼为 comparison。
- **必须包含的内容结构**（缺一不可）：
  1. **对比维度表格**：以表格形式列出各候选在关键维度上的差异；
  2. **核心 Trade-offs**：用文字明确陈述各方案放弃了什么、换到了什么；
  3. **适用场景（When to use A vs B）**：给出可操作的选型决策——什么情形下选 A、什么情形下选 B。
- **不要建**：仅仅"提到了多个相关项"但没有对比意图的列表——这种应留在 concept/entity 节点的 body 内。

### query (问题驱动指南)

- **定位**：以**问题或排障情景**为驱动的方法论节点，而非名词解释。本质是把散落在长篇文档里的 FAQ、经验教训、决策推演**提取成独立的可检索节点**。
- **典型形态**：标题以问句或动词起头——"如何诊断 X"、"为什么系统会 Y"、"X 故障的处理流程"、"在 X 场景下如何选型"、"X 架构决策推演"。
- **必须具备**：
  - 有明确的**问题陈述**（场景 + 触发条件）；
  - 有**可操作的步骤化方法论**（类似 SOP），而不是仅陈述事实；
  - 串联多个相关 entity/concept，形成一条贯穿的指南。
- **不要建**：单纯名词解释、纯背景介绍——那些归 concept/entity。

## Layer 2 Graph Invariants

- Active Layer 2 页面中的语义连线目标，默认应为其他 Active Layer 2 页面
- 示例代码、语法展示中的 `[[...]]` 必须放在代码块或行内代码中；**只有这样**才不参与 unresolved-link 校验
- Active Layer 2 页面不得引用零字节节点、根目录幽灵页或已被替换的旧 slug
- 已归档节点不得继续作为 active 页面中的正常关联目标
- **关联谨慎保守原则 (Conservative Linking)**：仅在两个节点之间存在**明显、可在 body 中具体陈述**的语义关系时才建立 wikilink。**禁止**仅凭"同一主题词"、"都属于 AI 领域"等抽象共性主观臆断地连接两个节点。判据：如果要在 body 里描述这条关联，找不到一句可以具体说出关系本质的话（如"是 X 的父类"、"由 Y 提出"、"被 Z 实现"、"与 W 互为选型替代"），则**不应建立**该 wikilink。本原则的强度优先于 SCHEMA 中"每页至少 2 个出链"的软性建议——宁可少链不连错。
- **正文优先，不建页尾凑数边**：关系应出现在能够解释其语义的正文句子中；禁止仅为反向链接、对称性、连通率或凑足出链数而维护无解释的 `Related / 相关概念` 页尾清单。正文已存在同目标链接时，不再在页尾重复一次。

### Meta Graph Isolation

- Meta 页面是运维载体，不是知识节点，不得通过普通 wikilink 进入语义网络。
- `index.md` 使用带目录的代码路径登记 Active Layer 2 节点，不使用 wikilink；该注册表由 lint 解析并验证。
- `log.md` 只记录纯文本或代码路径，不得包含普通 wikilink；任何 Wiki 页面也不得用普通 wikilink 指向 `log.md`。
- `SCHEMA.md` 中若需展示 wikilink 语法，必须转义或放入代码块 / 行内代码，不能产生真实图边。

## Node Lifecycle (节点生命周期)

### Create

创建 Active Layer 2 节点时，必须在同一变更中完成以下动作：

1. 新建到正确目录，并使用全库唯一 slug
2. 写入必需 frontmatter（含非空 `sources`）
3. 添加已解析的 Layer 2 出链；鼓励至少 2 个，但若严格遵守"关联谨慎保守原则"后只能给出 0 或 1 条强关联，则保留少链优于强加弱链
4. 注册到 `index.md`
5. 按 `Daily Log Policy` 记录到 `log.md`

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

每次同步、重构或批量生成后，必须从仓库根目录运行：

```bash
python3 scripts/wiki_lint.py
```

该脚本的默认文本输出必须按固定顺序打印检查清单，逐项标记 `[OK]` / `[FAIL]`；若失败，继续输出 issue details。机器读取场景可使用 `--json`。脚本最终必须返回 `wiki_lint: OK` 且退出码为 0。它至少校验以下条件：

1. `entities/`、`concepts/`、`comparisons/`、`queries/` 中不存在零字节 Markdown 文件
2. Active Layer 2 文件名符合小写 kebab-case
3. 仓库根目录不存在漂浮的 Active Layer 2 节点
4. Active Layer 2 slug 全库唯一
5. Meta pages 存在且以 YAML frontmatter 开头
6. Active Layer 2 页面全部具备必需 frontmatter 字段，且 `sources`、`tags` 非空
7. Active Layer 2 页面中不存在 unresolved wikilinks（代码块/行内代码中的示例除外）
8. Active Layer 2 页面不得用普通 wikilink 指向 Layer 1、Meta 或 Archive 页面；此类来源必须使用对应溯源脚注语法
9. 每个 Active Layer 2 页面在 `index.md` 中**恰好登记一次**
10. `index.md` 不得登记不存在、已归档或已被替换的 slug
11. 若 `index.md` 维护 `Total pages` 字段，则该值必须等于已登记的 Active Layer 2 节点数
12. `_living/` 文档不得包含图谱 wikilinks 或语义型 frontmatter 字段（如 `type`, `tags`, `concepts`）
13. `_living/` 一级分类目录必须符合 2–3 词段 kebab-case 主题命名规则
14. `log.md` 顶层维护日志必须按 `Daily Log Policy` 使用同一日期唯一的 `## [YYYY-MM-DD] daily | ...` 条目
15. Meta 页面不得包含真实图谱 wikilink，任何 Wiki 页面也不得用普通 wikilink 指向 Meta 页面；`index.md` 必须使用代码路径而非 wikilink 注册 Active Layer 2 节点
16. Obsidian 本地启用插件清单必须与 `wiki/.obsidian/plugins/*/manifest.json` 保持一致
17. `SCHEMA.md` 的 Tag Taxonomy 与 Validation Invariants 必须和 `scripts/wiki_lint.py` 的 fallback 标签集与默认检查清单保持一致
18. Active graph 的 wikilink 目标、index 登记 slug、`contradictions` slug 与本地 `sources` 路径必须使用与真实文件完全一致的大小写；不得依赖大小写不敏感文件系统自动兜底

### Lint Co-evolution Policy (校验工具随 Schema 演进)

`SCHEMA.md` 是 wiki 结构与运维规则的单一权威来源；`scripts/wiki_lint.py` 是这些规则中**可机械校验部分**的执行器。因此，任何修改 `SCHEMA.md` 的变更都必须在同一轮维护中完成以下检查：

1. 若变更涉及 layer 定义、路径约定、Active/Meta/Archive 范围、frontmatter 必填字段、Tag Taxonomy、wikilink / provenance 语法、index 注册表规则或 Validation Invariants，必须同步评估并更新 `scripts/wiki_lint.py`。
2. 若新增规则可以机械校验，必须把对应 issue key 与默认文本检查项加入 `scripts/wiki_lint.py`；默认输出的检查清单应与本节 Validation Invariants 保持一一对应或明确的聚合关系。
3. 若新增规则属于语义判断、颗粒度判断、保守链接原则、实现细节过滤等不可可靠机械校验内容，必须在 `SCHEMA.md` 中明确标注为原则性约束，不强行塞进 lint。
4. 若新增或移动标签，必须同步 `Tag Taxonomy` 与 `scripts/wiki_lint.py` 的 fallback `ALLOWED_TAGS` 集合，避免 SCHEMA 解析失败时退回旧标签库。
5. 完成 SCHEMA 或 lint 调整后，必须运行 `python3 scripts/wiki_lint.py`；涉及机器消费或报告格式变更时，也必须运行 `python3 scripts/wiki_lint.py --json`。
6. `scripts/wiki_lint.py` 必须自检 SCHEMA-to-tool drift：至少检查 Tag Taxonomy 与 fallback `ALLOWED_TAGS` 是否一致，以及本节强校验编号项数量与默认 `CHECKS` 数量是否一致。
7. 所有 SCHEMA / lint 共演进变更都必须按 `Daily Log Policy` 记录到 `log.md`，说明改了哪些规则、哪些规则进入 lint、哪些规则刻意保持人工判断。

### Daily Log Policy (`log.md` 日志合并策略)

`log.md` 是 wiki 维护审计线索，不是逐操作流水账。默认每天最多保留一条顶层日志，避免同一天的多次小修把运维历史切碎。

1. **每日唯一顶层条目**：同一自然日（按本地时区）内，优先使用一个 `## [YYYY-MM-DD] daily | ...` 顶层条目承载当天所有 wiki 维护事项；当天已有日志时，不新建第二个同日期顶层条目，而是在现有日期条目内追加 `###` 子段或合并 bullet。
2. **允许历史例外**：本策略生效前已有的多条同日历史日志不要求大规模重排；若当天仍在继续维护，可顺手合并当天新近条目。
3. **保留可审计信息**：合并后仍需保留 Trigger / Actions / Boundary / Verification 等关键信息；不得为了压缩条目而丢失核心操作、删除/归档/重命名记录或校验结果。
4. **跨日不回填**：跨自然日的维护必须新开对应日期条目，不把今天的操作写回昨天，也不把昨天的未提交事项并入今天除非今天实际完成了复核或修复。
5. **报告口径**：最终汇报可按当天 daily 条目的子段概括，不需要逐条复述所有小修。
6. **图谱隔离**：日志正文只使用纯文本或代码路径记录节点与文件，不使用普通 wikilink，也不接受其他页面的 wikilink 导航；日志可审计性不得依赖图谱反向链接。

### Obsidian Carrier Maintenance (载体插件运维)

Obsidian 是本 wiki 的主要交互载体；维护 wiki 时，Agent 不只检查 Markdown 图谱，也必须检查 `wiki/.obsidian/` 下插件与配置是否仍能支撑当前运维体验。

1. **插件清单核对**：检查 `wiki/.obsidian/community-plugins.json` 与 `wiki/.obsidian/plugins/*/manifest.json` 是否一致；已启用插件必须有对应插件目录，插件目录中的 `id` 必须与启用清单一致。
2. **版本核对**：对已安装社区插件，优先通过 Obsidian 官方社区插件目录或插件仓库的 `manifest.json` 核对当前版本；若本地版本落后，且插件文件已在仓库中跟踪，可更新插件文件并说明版本变化。
3. **配置完整性核对**：对每个已安装插件，将当前 `data.json` 与该插件当前版本代码中的默认配置对象递归比对；缺失但有默认值的配置项应补入 `data.json`，值保持默认，避免未来 Agent 或不同 Obsidian 实例看到不完整配置。
4. **前端协作边界**：若插件更新、授权、迁移弹窗、外观确认、插件市场操作或 Obsidian 内部命令只能在前端完成，Agent 不应臆造结果；必须在汇报中明确列出需要用户在 Obsidian 前端处理的动作、原因与完成后的复核项。
5. **报告要求**：每次 wiki 运维汇报中若触及 Obsidian 配置，必须单列 Obsidian 载体检查结果，至少说明插件版本是否最新、配置是否完整、是否有仅能前端处理的遗留动作。
6. **校验边界**：本地可稳定检查的启用清单与插件 `manifest.json` 一致性已纳入 `scripts/wiki_lint.py`；联网版本查询、插件代码默认值解析与前端状态确认仍属于人工 / 半自动 SOP，不纳入强校验清单。若后续沉淀出稳定脚本，可在本节补充脚本路径与执行命令。

## Update Policy (更新策略)

当新信息与旧信息冲突时：

1. 检查日期，通常较新的研究覆盖旧研究。
2. 属于学术争议时，必须同时保留两种观点，并附带各自的来源和日期。
3. 在 Frontmatter 中标记 `contradictions: [page-name]`。

## Living Documents Policy (`_living/` 活体文档同步规则)

对于外部持续更新的个人笔记或配置文档：

1. **绝不放入 `raw/`**：统一存放或镜像至 `_living/` 目录，且不添加 `sha256` 校验。
2. **保持高内聚，禁止污染源文档 (单向引用原则)**：`_living` 目录下的文档作为原材料 (Source of Truth)，必须保持纯净，由用户手动维护。Agent **绝不允许**向 `_living` 下的文档底部或正文中主动写入任何指向图谱的 `\[\[wikilinks\]\]` 或隔离线。
3. **原材料元数据极简化 (No Semantic Metadata in Living Sources)**：`_living` 中的文档不需要（也不推荐）包含上层知识图谱的结构化元数据（如 `tags`, `type`, 或显式的 `concepts` 链接）。原材料只需陈述事实和业务逻辑。知识体系的分类（Tags）和概念提炼（Concepts）完全由 Agent 在同步时于 Layer 2 自行负责构建。
4. **通过 Layer 2 溯源建立图谱关系**：所有的知识网状连线，必须由 Layer 2 (Concepts/Entities) 页面通过**紧凑的内联脚注语法**（例如：`^[[[_living/xxx/xxx|显示别名]]]`）**单向、主动地指向** `_living/` 子层。
   - **核心红线**：在 `^[` 和 `[[` 之间，以及 `]]` 和 `]` 之间，**绝对不允许有任何空格**。空格会触发 Obsidian 渲染器的 Bug 导致显示残留的 `] ]`。
   - 采用此紧凑语法后，正文中会被无缝渲染成干净的 `[1]` 上标，并在阅读视图末尾由 Obsidian 引擎**自动生成**包含双链的回溯列表，从而免去手动维护文末 `[^1]: ...` 的冗余文本。
5. **常规同步 (Incremental)**：默认模式。读取新内容，提取最新主张 (Claims)，去 Layer 2 对碰。修改冲突、补充新增，但**不自动清理静默删除的幽灵知识**。
6. **深度同步/重构 (Deep Sync)**：必须由用户显式声明触发（如“已做大规模删减，请做深度同步”）。Agent 会顺着 Layer 2 中指向该文档的溯源标记（如 `^[[[_living/xxx/xxx|显示别名]]]`）反向遍历 Layer 2，清理掉所有在新草稿中已丢失的旧陈述。
7. **单点重置 (Override)**：当该篇活体文档是某领域的绝对唯一真理时，允许直接重置/覆写对应的 Layer 2 页面。
8. **可复用知识 vs 实现细节 (Reusability Filter)**：`_living/` 文档中**只承载具备复用性的知识与实用性技术**——架构思想、方法学、设计原则、跨场景共通的工程经验。**实现细节应被剥离**——包括但不限于：
   - 项目内私有命名（具体函数名、类名、表名、列名、配置键名、私有模型节点名）；
   - 具体数值阈值与维度（除非该数值本身就是公开发表的学术事实或行业标准）；
   - 具体产品/库版本号绑定（应抽象为"分布式计算引擎"、"关系库的向量扩展"等技术类别）；
   - 单店/单次实验数据、项目排期、内部沟通记录。

   **判据**：写入 `_living/` 的内容应满足"换一家公司、换一个产品、换一组实现，这段知识仍然有指导价值"。Agent 在 ingest 外部文档（如飞书原始文档、内部 wiki 导出）时，**必须主动剥离实现细节**而不是原样复制——批量 ingest 工具的输出只是布局转换，语义级的脱敏需手动完成。

   > **以上为原则性约束**。是否构成"实现细节"含主观判断成分；不同模型在不同参数下执行可能存在差异。Agent 应当按以上意图理解，边界情形保守处理：宁可剔除某条疑似实现细节，也不要在 `_living/` 中留下污染。
