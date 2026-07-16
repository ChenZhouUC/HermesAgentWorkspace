---
title: Wiki Log
created: 2026-05-14
updated: 2026-07-16
type: summary
tags: [wiki, tool]
sources: []
confidence: high
---

# Wiki Log

> 知识库操作追踪日志 (Daily rollup)
> 格式：`## [YYYY-MM-DD] daily | subject`
> 同一天默认最多一条顶层日志；多项维护用 `###` 子段或 bullet 合并。

## [2026-07-16] daily | Edge box memory model clarification

### source + ingest | Unified-memory terminology and accounting

- Trigger: 用户希望理解独立显卡服务器的系统内存 / 显存与 SoC 盒子内存的区别、`free -h` 小于标称容量的原因，并要求给 SoC 等英文简称标注全称。
- Actions:
  - 2026-07-16 对 RK3576、算能 7.2T 和算能 32T 做只读复核，读取 `/proc/meminfo` 与启动内存日志，确认 `free -h total` 对应 `MemTotal`，CMA 包含在 `MemTotal` 中；算能盒子的大额差值主要来自 Linux 普通内存之外的 NPU / VPP / VPU 固定池。
  - 扩写 `_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md` 的口径与术语：新增独立 VRAM 与 SoC 共享 DRAM 对照、标称容量 / `MemTotal` / `MemAvailable` 三层口径、三台实机精确对账表、`free -h` 字段解释和英文简称速查；同步修正实机参数表中会把 reserved 与 CMA 重复相加的旧写法。
  - 根据用户的理解补充一句话口径：盒子标称内存是 CPU、GPU、NPU / TPU 和视频模块共享的板载物理总池；可以粗略类比“CPU 内存 + GPU 显存”，但不是多块独立内存相加，也不代表全部容量都可由 CPU 进程使用。
  - 更新 `concepts/edge-ai-deployment-stack.md`，提炼 SoC 统一物理内存、Linux `MemTotal`、CMA 和固定硬件池的可复用关系，明确 ION heap 只能类比逻辑显存池，通常不是独立显存芯片。
  - 增量 ingest 审计确认两个硬件实体无需重复承载通用内存原理，也不满足新建独立薄节点的必要性；在 `comparisons/rk3576-vs-sophon-edge-platforms.md` 补充选型口径，明确标称内存属于整机 SKU 的 SoC 共享总池，比较容量时需同时看标称值、`MemTotal` 和固定预留。
  - 在实测巡检命令中增加 `/proc/meminfo` 精确字段读取；该命令已在三台设备实际执行。
- Boundary: 未修改盒子配置；当前 `MemAvailable` 等动态值不固化为平台参数；没有把 ION、BMCV、Arm、芯片型号等无通行逐字母展开的名称强行制造成伪全称；未修改 `SCHEMA.md`、lint、index 或 Obsidian 配置。
- Verification: 三台设备均成功执行 `free -k`、`free --version` 和精确 `/proc/meminfo` 字段读取；确认 RK3576 的 procps-ng 4.0.2 与两台算能旧版 `free` 对 `used` 使用不同公式，文档只保留跨版本成立的解释。`python3 scripts/wiki_lint.py` 全部 18 项通过；更新后的 living、concept 与 log 均通过 Pandoc GFM 解析；`git diff --check` 通过。

## [2026-07-15] daily | SpaceSight knowledge maintenance

### ingest | Existing-node-only SpaceSight Q&A sync

- Trigger: 用户要求充分理解 `SCHEMA.md` 后重新注入更新过的 `SpaceSight-QA-List.md`，并明确认为先前提取略散；QA 中内容不足时不新建 entity、concept、comparison 或 query，只按 schema 与现有节点建立有证据的连接。
- Actions:
  - 未新增任何 Layer 2 节点；将产品别名、客流产品形态、相机功能边界、开放场景取舍、Agent / VLM 能力和生成式视频职责边界集中回注到 `entities/spacesight.md`。
  - 复核后删除 `queries/design-spacesight-nonstandard-traffic-plan.md`：其内容高度依附 SpaceSight 产品配置，核心边界已由产品实体承载，剩余交付细节继续留在 Layer 1，不再维护重复 query；同步清理实体引用与 index 登记，Active Layer 2 节点数由 42 调整为 41。
  - 保留并更新 `queries/diagnose-spacesight-traffic-count-mismatch.md`，标题收敛为“如何验证并排查 SpaceSight 客流数据偏差”：把客户人工统计、既有设备或第三方系统结果视为待验证观测值，先用原始视频建立独立基准，再定位 SpaceSight 的事件抽取、ReID 与后处理层。
  - 仅保留有明确输入输出、实现或问题到 SOP 谓词的现有连接；带宽估算、远距小目标、车牌方案、Whale Analytics 操作、API 联系方式等继续留在 Layer 1，不机械拆页。
- Boundary: 未改写用户维护的 `_living/Whale-SpaceSight/SpaceSight-QA-List.md`，未修改 `SCHEMA.md`、lint 规则或 Obsidian 配置；index 仅因删除 active query 做生命周期要求的同步注销。本次不是 schema/lint 共演进，也不触发 Obsidian carrier gate。
- Verification: `python3 scripts/wiki_lint.py` 全部 18 项检查通过；两个更新节点均通过 Pandoc GFM 解析，`git diff --check` 通过；删除节点只在当日操作记录和历史日志中以纯文本路径保留，不再存在 active 图谱引用或 index 登记。

### ingest | Edge compute platform semantic normalization

- Trigger: 用户升级 `_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md` 后要求审计相关 ingest，并授权按审计结论优化 Layer 2。
- Actions:
  - 收敛 `entities/edge-rk3576.md` 与 `entities/edge-sophon.md`：明确 RK3576、CV186AH、BM1688、BM1684X 是 SoC / TPU 平台而非完整盒子 SKU；将表格改为稳定的平台规格，移除单台实机 OS、驱动、内存可见量和无功耗实测支撑的定性评价。
  - 新建 `concepts/edge-ai-deployment-stack.md`，提炼整机、SoC、BSP、编译器 / Runtime、目标模型产物、视频处理链和模型包契约。
  - 新建 `comparisons/rk3576-vs-sophon-edge-platforms.md`，按工具链、算力、视频口径、模型产物、核心 trade-off 和适用场景比较 RK3576、CV186AH、BM1688、BM1684X，并保留 CV186AH / BM1688“同后端但不可推导同 die 或可解锁”的证据边界。
  - 更新 `index.md` 的实体摘要与新节点登记，Active Layer 2 节点数由 41 调整为 43。
- Boundary: 登录凭据、内网地址、单次温度 / 负载 / 磁盘 / ION 状态和实机巡检命令继续只保留在 Layer 1；未新增 Linaro 或单芯片薄节点，未创建尚缺跨设备样本的资源审计 query；未修改 `SCHEMA.md`、lint 规则或 Obsidian 配置。
- Verification: `python3 scripts/wiki_lint.py` 全部 18 项检查通过；两个更新实体与两个新增节点均通过 Pandoc GFM 解析；`git diff --check` 通过。

## [2026-07-14] daily | Wiki lint schema alignment and repair feedback

### tooling | Schema-backed lint hardening

- Trigger: 用户要求按最容易实现、效率最高的方式，让 `scripts/wiki_lint.py` 尽可能符合 `SCHEMA.md` 的设计，并让 lint 失败时能直接反馈问题，便于 Agent 针对性修复和维护。
- Actions:
  - 将 Active Layer 2 `sources` 收紧为 Layer 1 本地来源：只允许 `_living/...` 或 `raw/...`，不再接受直接 HTTP URL 作为 frontmatter source。
  - 新增 living/raw provenance marker 校验：检查紧凑脚注格式、目标文件存在性与路径大小写；living 溯源允许省略 `.md` 后缀以兼容现有写法。
  - 修正 path-qualified wikilink 解析：带目录的 `[[path/to/node]]` 必须按真实路径解析，避免只取 basename 导致跨层或错误路径误通过。
  - 将 `index.md` 中 active section 下格式错误的 bullet 记录为 `invalid_index_entries`，避免 malformed entry 被静默忽略。
  - 将日期校验从正则升级为真实 ISO calendar date 校验。
  - 为 lint issue 增加 rule/fix 提示，并将失败详情中的 list/dict 值输出为 JSON 字符串，方便 Agent 直接定位和修复。
- Boundary: 未改变 `SCHEMA.md` 的 18 项 Validation Invariants 数量；新增规则挂载到现有检查项下。未尝试把 Evidence-Gated Linking 的证据强度、关系谓词等语义判断机械化。
- Verification: `python3 -m py_compile scripts/wiki_lint.py`、`python3 scripts/wiki_lint.py`、`python3 scripts/wiki_lint.py --json` 与 `git diff --check` 均通过。

### audit | Layer 1 ingest completeness and semantic repair

- Trigger: 用户要求充分理解 Schema 后重新审计整个 Wiki，重点确认 `_living` 文档是否被完整、正确且按页面阈值 ingest，避免既遗漏稳定知识对象，也避免把原材料机械包装成 Layer 2 页面。
- Scope: 逐一阅读并建立 20 篇 `_living` 文档与变更前 40 个 Active Layer 2 节点的来源覆盖矩阵，同时复核节点类型、抽象层级、正文证据和现有关系语义。
- Findings:
  - 变更前 19/20 篇 living 文档已被至少一个节点引用；`Model-Context-Protocol.md` 是唯一完全未覆盖、同时又满足“可独立定义的具名协议实体”阈值的来源。
  - RuView 已有实体入口，但原节点只概述产品能力，未提炼可跨产品复用的 WiFi CSI 感知方法；该方法在采集、校准、物理特征、任务推断和硬件可观测性上具备独立研究边界。
  - `llm-benchmark-methodology.md` 仍停留在旧能力分类、阶段性分数和厂商偏好，未 ingest 当前来源中的被测对象层级、指标语义、最小报告契约、结果状态与“当前社区声望”。
  - `agent-harness.md` 把 MCP 描述为沙盒隔离机制；MCP 只标准化能力接入，授权、执行隔离与审计仍属于 Host/Harness 责任。
- Actions:
  - 新建 `entities/model-context-protocol.md`，提炼 Host/Client/Server、Tools/Resources/Prompts、传输版本边界及安全责任。
  - 新建 `concepts/wifi-csi-sensing.md`，分离通用 CSI 感知链与 RuView 产品实现，并明确 RSSI、非相干多节点和同步阵列的能力边界。
  - 重写 `concepts/llm-benchmark-methodology.md`，移除易过期的分数快照与厂商叙事，改为可复用的评测对象、协议、证据状态、组合和维护方法。
  - 同步收紧 `entities/ruview.md` 的产品边界与置信度，修正 `concepts/agent-harness.md` 的 MCP/沙盒混淆，并在 `entities/hermes-agent.md` 建立有来源支持的 MCP 接入关系。
  - 更新 `index.md`，Active Layer 2 节点由 40 增至 42，新增节点均按类型和 slug 字母序唯一注册。
- Boundary: 未把每篇 living 原材料一对一拆成节点；Hermes/RuView 部署命令、产品专属配置、完整 FAQ 和 benchmark 明细表继续保留在 Layer 1。其余长文档已有内聚的 Layer 2 摘要，不因篇幅或“孤立观感”重复拆页；本轮未改 Schema 或 lint 规则。
- Verification: 变更后的 20/20 篇 `_living` 文档均在 Active Layer 2 frontmatter 中有至少一个来源引用；`python3 scripts/wiki_lint.py` 与 JSON 模式均通过全部 18 项检查，6 个新增或更新的知识节点通过 Pandoc 解析，`git diff --check` 通过。

### source | Gödel's Proof reading guide

- Trigger: 用户正在阅读《Gödel's Proof》，希望在 `_living/TCS-and-Math/` 下新增一份沿用现有 living wiki 行文的知识介绍与阅读笔记。
- Actions: 新增 `_living/TCS-and-Math/Godels-Proof-Reading-Notes.md`，从形式系统、元数学、哥德尔编号与对角化出发，梳理两条不完备性定理的证明骨架、适用条件、历史版本差异、常见误读、TCS 联系与递进阅读路径。
- Incidental repair: 全库 lint 暴露 `concepts/llm-benchmark-methodology.md` 的表格 wikilink alias 被 Markdown 列分隔符拆开，导致目标带尾随空格；将其改为语义等价的无 alias 链接，不改变页面主张。
- Boundary: 主体变更是新增 Layer 1 原材料；未向 living 文档加入语义 frontmatter 或图谱链接，未自动提炼新 Layer 2 节点，也未改动 `index.md`、Schema、lint 或 Obsidian 配置。附带的 Layer 2 修改仅修复既有链接语法。
- Verification: 新文档通过 Pandoc + MathJax 解析；`python3 scripts/wiki_lint.py` 与 `git diff --check` 均通过。

## [2026-07-13] daily | Living knowledge update and conservative graph audit

### update | Text protocol and multimodal input knowledge

- Trigger: 用户要求把活体文档作为 updated knowledge wiki 深入更新，并重新审计整个 wiki；连接原则是“没有明确关系就不要建立连接”，且 Meta 文件不得进入知识图谱。
- Actions:
  - 深度更新 `_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md`，按 source、transport、prompt、output/execution 分层整理 Markdown、JSON/Schema、YAML、XML、表格格式、Unicode、RAG、结构化输出与安全边界。
  - 深度更新 `_living/AI-Infrastructure/LMM-Input-Mechanics.md`，补充媒体预处理、编码器、连接器、序列/特征轴拼接、cross-attention、位置机制、计量与 Agent 有序 IR 的数学解释。
  - 同步重写 `concepts/markdown-llm-protocol.md` 与 `concepts/lmm-input-mechanics.md`，删除“所有模态必然归一为同一 Token 序列”“Markdown 相邻必然改善注意力”等过度绝对的旧抽象。
  - 规范 `_living/AI-Infrastructure/Model-Context-Protocol.md` 的中文引号间距，不改变代码块和引用内容。

### audit | Whole-wiki relation review

- Scope: 复核 63 个 Markdown 文件、40 个 Active Layer 2 节点及其正文连接；精确区分 Meta 文件 `SCHEMA.md` 与知识节点 `concepts/schema-as-handoff-contract.md`。
- Actions:
  - 确认 `SCHEMA.md`、`index.md`、`log.md` 没有实际图谱边；Meta 页面继续只使用纯文本和代码路径。
  - 保留能够明确说明实现、依赖、输入输出、抽象或选型关系的正文连接；不为独立节点补连接，也不追求双向率或全图连通率。
  - 将 `entities/spacesight.md` 的页尾链接清单改为故障诊断与方案设计的明确关系说明，并收敛 `entities/trajex.md` 的重复目标链接。
  - 移除 living 文档中唯一会形成源层图边的本地 Markdown 文档链接，改用代码路径。
- Boundary: 未新增、删除、归档或重命名节点；未改变 Obsidian 配置。语义关系仍按人工审查执行，不把不可机械判断的“关系强度”塞入 lint。
- Verification: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json` 均通过 18 项检查；四份更新后的 living/concept 文档通过 Pandoc + MathJax 解析，`git diff --check` 通过；未发现活动的本地 `.md` Markdown 图边或页尾裸 wikilink 清单。

### tooling | Enforce zero-degree Meta pages

- Trigger: 用户明确要求 `SCHEMA.md`、`index.md`、`log.md` 三个 Meta 文档不建立任何 Wiki 文档边，并询问 schema 与 lint 是否能够强制执行。
- Schema: 将 Meta 隔离收紧为本地文档图上的零度约束，即三个文件均满足 `in-degree = out-degree = 0`；同时覆盖 wikilink 与标准 Markdown 本地文档 link/embed，允许外部 URL、同页 anchor、纯文本和代码示例。
- Lint: 扩展第 15 项检查，除现有 wikilink 双向校验外，新增标准 Markdown inline link、image/embed 和 reference-definition 的本地 `.md` 目标解析，并检查 Meta 出边和全库 Meta 入边。
- Verification: `python3 -m py_compile scripts/wiki_lint.py`、文本模式 lint、JSON 模式 lint 与 `git diff --check` 均通过；四类 Meta 边 issue 数组全部为空。临时故障注入进一步确认 Meta Markdown 出边和非 Meta 页面指向 `log.md` 的入边都会被对应检查捕获。

### schema | Evidence-gated linking audit

- Trigger: 用户要求整体审计并精简 `SCHEMA.md`，将“没有显著证据不要关联”设为知识图谱建边原则。
- Corrections:
  - 删除“每页至少 2 条出链”的软目标，明确节点允许零入边、零出边，连通率、反链对称和页尾 Related 清单均不能作为建边理由。
  - 建立 `Evidence-Gated Linking`：每条边必须同时具备明确关系谓词和可追溯证据，并列出可接受证据与不充分信号。
  - 调和“完整流程留在 Layer 1”与“可复用 query SOP 可提炼”的类型冲突；把 200 行拆分规则改为触发评估，而非机械拆页。
  - 修正“较新研究通常覆盖旧研究”为证据质量、方法可靠性和版本适用性优先；收紧 `contradictions` 的使用条件。
  - 将 living 溯源规则的适用范围从仅点名 Concepts/Entities 修正为全部四类 Active Layer 2 页面。
- Lint boundary: 证据强度、关系谓词和适用范围属于语义判断，按 Lint Co-evolution Policy 保持人工审查；现有 lint 已负责断链、目标层级、Meta 隔离等可机械条件，本轮不新增启发式“证据评分”。
- Verification: `python3 scripts/wiki_lint.py` 与 JSON 模式均通过 18 项检查，`SCHEMA.md` 通过 Pandoc + MathJax 解析，`git diff --check` 通过；SCHEMA 与 lint 的检查项数量和标签集合保持一致。

## [2026-07-11] daily | Wiki graph structure audit

### audit | Conservative graph cleanup and Meta isolation

- Trigger: 用户要求完整审计 Wiki 结构，避免 `log.md` 等运维页面进入语义网络，并清理牵强连接、冗余关系及过度提取节点。
- Actions:
  - 完整复核 `SCHEMA.md`、42 个 Active Layer 2 节点、`index.md`、`log.md` 与现有 lint 规则。
  - 将 Meta 页面排除在语义 wikilink 网络之外；`index.md` 注册表改用带目录的代码路径，历史日志中的真实 wikilink 改为行内代码示例或纯文本路径。
  - 删除页尾仅用于反链、对称性或连通度的 `Related / 相关概念` 清单，保留正文中能够具体解释关系的链接。
  - 删除过薄且依附 RuView 才成立的 `entities/esp32-s3.md`，以及与既有 concept 内容高度重复的 `comparisons/reid-embedding-model-families.md`；对应信息仍保留在母体节点中。
  - 收紧 Agent、Benchmark 与 ReID 集群中的间接或传递性连接，不为孤立节点强加弱边。
- Boundary: 未 ingest 或重写 `_living` 原材料；`SpaceSight-QA-List.md` 保持当前未 ingest 状态。未修改用户已有的 Obsidian 插件配置变更。
- Verification: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json` 均通过 18 项检查；Meta 页面真实 wikilink 为 0，`index.md` 恰好登记 40 个 Active 节点，无断链、跨层链接或残留页尾 Related 清单。

## [2026-07-02] daily | SpaceSight Edge ALGO Integration

### Add Edge ALGO to SpaceSight Pipeline

- Trigger: 用户要求在 ReID-Perception-Layer-TRAJEX 之前增补一层：从边缘端盒子 (Edge-Compute-Boxes-RK3576-Sophon) 上运行 ALGO，提取并上传事件、轨迹、坐标与属性等数据，支持弱网缓存。
- Action:
  - 增加 Layer 1 原材料：`_living/Whale-SpaceSight/Edge-Data-Collection-ALGO.md`。
  - 更新现有的 `_living/Whale-SpaceSight/ReID-Perception-Layer-TRAJEX.md` 与 `_living/Whale-SpaceSight/ReID-Pipeline-Architecture.md` 架构流。
  - 创建 Layer 2 实体节点 `entities/edge-algo.md` 并注册到 `index.md`。
  - 深入 `cv/algo` 库源码，提取了具体的功能策略：调用 `BlurImpl` 算子做合规人脸打码；通过判断平行方向的 `passby_walk_ratio` 等剔除"路过"噪音；将空间事件拆解为"驻留 (Approach)/关注 (Front)"（其中 Front 指代发生了正脸交互的关注事件），更新至原文件 4. 业务功能侧实现细节。
  - **全局图谱审计与对齐**：全面审视了 SpaceSight 相关知识节点，将 Edge ALGO 作为极前置流整合进 `entities/spacesight.md`, `concepts/reid-pipeline.md`, `entities/trajex.md`, `comparisons/trajex-vs-hidalgo.md` 等。
  - **后处理与指标加工链路纵深重构**：根据 `airflow/analytics` 的最新源码结构，将 `_living/Whale-SpaceSight/Customer-Flow-Post-Processing.md` 彻底按照数据加工流的生命周期顺序重构为三个阶段：感知侧基础过滤 (Edge & HIDALGO) ➔ 中台二次清洗 (Airflow 营业时间/时区/停留时长/高频次数过滤) ➔ 核心业务指标衍生 (Airflow 批次聚合/接待归因与及时接待/在店时长/区域停留/路过客流)。同步更新了对应的 Layer 2 Concept 节点。
  - **硬件节点图谱回溯补全**：在梳理全量 `spacesight` 相关节点连通性时，发现底层硬件节点 `edge-rk3576` 与 `edge-sophon` 缺乏向上游业务的感知，为此在它们的 Related 区域补充了 `[[spacesight|SpaceSight]]` 与 `[[edge-algo|Edge ALGO]]` 的回溯边，使得软硬件关系的双向图连通度达到 100%。
- Boundary: 明确 Edge ALGO 负责端侧的轻量计算与事件封装，TRAJEX 作为云端的特征推断与查询节点。

### Full SCHEMA Maintenance Flow Execution

- Trigger: 用户要求按照 SCHEMA 要求完整执行一次运维流。
- Action:
  - 检查了 `SCHEMA.md` 的变更要求和 `Lint Co-evolution Policy`，确认当前处于日常维护阶段。
  - 执行 `python3 scripts/wiki_lint.py` 通过所有强一致性检查。
  - 触发了 `Obsidian Carrier Maintenance`，比对了本地与官方 release。更新了 `extended-graph` 插件（从 `2.7.6` 更新至 `2.7.7`）。
  - 修理了 `log.md` 之前残留的重复记录（`创建 Layer 2 实体节点...` 出现了多次）。
- Verification: Lint 全部通过，Obsidian 插件本地版本与远端同步。

## [2026-07-01] daily | Wiki carrier and SpaceSight maintenance

### Obsidian carrier maintenance SOP

- Trigger: Obsidian 是当前 wiki 的主要载体，需要把插件版本、插件配置完整性与前端协作事项纳入 wiki 运维原则，避免后续只检查 Markdown 图谱而忽略 Obsidian 侧体验漂移。
- Action: 在 `SCHEMA.md` 新增 `Obsidian Carrier Maintenance` 小节，要求 wiki 运维时核对 `community-plugins.json`、插件 `manifest.json`、插件版本、`data.json` 默认配置完整性，并在汇报中列出只能由用户在 Obsidian 前端处理的事项。
- Boundary: 该流程涉及联网版本查询、插件代码默认值解析与前端状态确认，暂不纳入 `scripts/wiki_lint.py` 强校验；后续若沉淀稳定脚本，再补充到 SCHEMA。

### Daily log policy

- Trigger: 用户要求 `log.md` 的运维策略改为每天最多一条，避免同一天多次小修产生碎片化顶层日志。
- Action: 在 `SCHEMA.md` 新增 `Daily Log Policy`，规定同一自然日默认只保留一个 `daily` 顶层条目；同日多项维护用 `###` 子段或 bullet 合并，并保留 Trigger / Actions / Boundary / Verification 等审计信息。
- Action: 将 2026-07-01 已有的 Obsidian 载体 SOP 与 SpaceSight Q&A index 两条日志合并为当天 daily rollup。

### SpaceSight Q&A index

- Source: `_living/Whale-SpaceSight/SpaceSight-QA-List.md`
- Action 1: 新增 `entities/spacesight-qa.md`，作为 SpaceSight 产品线历史业务问答清单的 Layer 2 图谱入口。
- Action 2: 将 living 源文档 frontmatter 降为最小必要元数据，避免 `_living/` 承担 active node 语义。
- Action 3: 对齐 `index.md` 中已登记的 `spacesight-qa` 条目与 active 页面。

### SpaceSight Q&A reingest

- Trigger: 用户要求全面运维 SpaceSight Q&A，去掉 `SpaceSight-QA-List.md` 中问题标题序号，方便后续手动调整顺序，并重新 ingest 相关知识点、清理弱价值内容。
- Action 1: 将 `_living/Whale-SpaceSight/SpaceSight-QA-List.md` 的各问题标题从带中文序号改为无序号主题标题，保留正文 Q/A 顺序与内容。
- Action 2: 删除弱语义的 `entities/spacesight-qa.md` 清单索引节点，改建 `entities/spacesight.md` 作为 SpaceSight 产品线实体。
- Action 3: 从当前 QA 清单提炼两个可复用 query SOP：`queries/diagnose-spacesight-traffic-count-mismatch.md` 与 `queries/design-spacesight-nonstandard-traffic-plan.md`。
- Action 4: 移除 `SpaceSight-QA-List.md` 中指向不存在 `SpaceSight-Historical-QA.md` 的 living source 字段，避免虚假溯源。
- Action 5: 同步 `index.md`：移除 `spacesight-qa`，注册 `spacesight` 与两个 query，`Total pages` 39 → 41。

### Full wiki and Obsidian carrier audit

- Wiki result: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json` 均通过；active 节点 41 个（entities 10、concepts 25、comparisons 3、queries 3），与 `index.md` 注册数一致。
- Cleanup result: 未发现 `SpaceSight-QA-List.md` 残留中文序号标题、旧 `[[spacesight-qa]]` 双链或 `SpaceSight-Historical-QA.md` 虚假来源。
- Obsidian result: `community-plugins.json` 与插件目录一致；`color-cycler`、`extended-graph`、`obsidian-linter`、`obsidian-minimal-settings` 均为当前上游 `manifest.json` 版本；四个插件 `data.json` 相对默认配置对象均无缺键。

### Wiki lint coverage update

- Trigger: 新增 `Daily Log Policy` 与 Obsidian 载体运维 SOP 后，需要重新评估 `scripts/wiki_lint.py` 是否应随 SCHEMA 演进。
- Action 1: 补齐 `scripts/wiki_lint.py` fallback `ALLOWED_TAGS` 中的 `spacesight`、`product-management`、`compliance`，避免 SCHEMA 解析失败时退回旧标签库。
- Action 2: 将 `log.md` 同日期唯一 `daily` 顶层条目规则纳入 lint 强校验。
- Action 3: 将 Obsidian 本地 `community-plugins.json` 与插件目录 `manifest.json` 一致性纳入 lint 强校验；联网版本查询、默认配置递归比对和前端状态确认仍保留为人工 / 半自动 SOP。
- Action 4: 新增 SCHEMA-to-tool drift 自检项，使 `wiki_lint.py` 能通过运行自身暴露 Tag Taxonomy / fallback 标签集不同步、Validation Invariants / 默认检查清单数量不同步这类“lint 需要更新”的问题。
- Action 5: 新增 exact-case 校验，要求 active graph 的 wikilink 目标、index 登记 slug、`contradictions` slug 与本地 `sources` 路径必须和真实文件大小写完全一致，避免 macOS 大小写不敏感文件系统掩盖 `HIDALGO` / `hidalgo` 这类差异。

### HIDALGO / TRAJEX naming normalization

- Trigger: 用户要求 wiki 内 HIDALGO / TRAJEX 展示名称统一大写。
- Action 1: 将相关 Layer 2 正文、标题、index 展示文本与 wikilink alias 统一为 `HIDALGO` / `TRAJEX`；active slug 仍保持 `hidalgo`、`trajex`、`trajex-vs-hidalgo` 小写，以符合 Active Layer 2 文件名规则。
- Action 2: 将 living 源文件 `ReID-Perception-Layer-trajex.md` 重命名为 `ReID-Perception-Layer-TRAJEX.md`，并同步所有 frontmatter `sources` 与溯源脚注路径。
- Action 3: 保留真实代码路径、active 文件路径和 slug 的原始大小写，避免历史日志或图谱路径变成不存在的大写文件。

### Verification

- Verification: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json`

## [2026-06-30] daily | Wiki maintenance

### audit | Wiki schema and lint alignment

- Scope: 对照 `SCHEMA.md` 审计当前 wiki 结构、Layer 2 节点、index 注册表、溯源语法、Living topic taxonomy 与 lint 覆盖面
- Findings:
  - 当前 SCHEMA 规则仍匹配 wiki 状态，未发现需要新增 layer、改 frontmatter 契约或调整分层语义的内容变更
  - Active Layer 2 节点 38 个：entities 9、concepts 25、comparisons 3、queries 1；与 `index.md` 的 `Total pages: 38` 一致
  - 无零字节 Markdown、无 root ghost page、无断链、无跨层普通 wikilink、无 `_living/` 图谱污染
  - 最长 active 页面 109 行，未触发 SCHEMA 的 200 行拆分建议
  - 发现工具漂移：`SCHEMA.md` Validation Invariants 为 13 项，但 `scripts/wiki_lint.py` 默认文本报告仍合并为 12 项；脚本内置 fallback `ALLOWED_TAGS` 也缺少部分已注册标签
- Actions:
  - 调整 `scripts/wiki_lint.py` 的 `CHECKS` 分组，使默认文本输出与 SCHEMA 的 13 项强校验一一对应
  - 补齐 `ALLOWED_TAGS` fallback 集合中的 `orchestration`、`harness`、`react`、`context-management`、`sandbox`、`hitl`、`protocol`、`multi-agent`
- Verification: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json` 均通过
- Conclusion: SCHEMA 本身无需调整；本轮修复的是 schema-to-tool 对齐问题

### update | Lint co-evolution policy

- Trigger: 明确 wiki 运维时 `scripts/wiki_lint.py` 是否必须随知识库和 SCHEMA 演进同步维护，避免后续 agent 只改规则、不改校验器
- Existing constraints:
  - `hermes-update.md` 已要求命中 `wiki/**` 前重读 `SCHEMA.md`，并说明 SCHEMA 会演进
  - `SCHEMA.md` 已要求每次同步、重构或批量生成后运行 `python3 scripts/wiki_lint.py`
  - 历史日志中多次记录过标签、目录、Validation Invariants 与 lint 的同步，但此前不是一条显式 schema 契约
- Action: 在 `SCHEMA.md` 新增 `Lint Co-evolution Policy` 小节，规定任何修改 layer、路径、frontmatter、标签、wikilink/provenance、index 或 Validation Invariants 的变更，都必须同步评估 `scripts/wiki_lint.py`
- Boundary: 明确语义判断、颗粒度判断、Conservative Linking、Reusability Filter 等不可可靠机械校验规则应留在 SCHEMA 人工约束中，不强行塞进 lint
- Verification: `python3 scripts/wiki_lint.py` 与 `python3 scripts/wiki_lint.py --json`

## [2026-05-14] daily | Wiki maintenance

### create | Wiki initialized

- Domain: AI Infrastructure, Edge Inference, TCS & Math
- Action: Created base directory structure, SCHEMA.md, index.md, and log.md.

### ingest | Batch import from Feishu Living Docs

- Source: 5 Feishu Docs into `_living/AI-Infrastructure` and `_living/TCS-and-Math`
- Created: `concepts/markdown-llm-protocol.md`, `concepts/agent-frameworks.md`, `concepts/llm-benchmark-methodology.md`, `concepts/llm-computational-complexity.md`, `concepts/set-theory-reading.md`
- Updated: `index.md`

### ingest | Expand Domain and New Docs

- Action: Expanded SCHEMA.md domains to include Algorithm Engineering, Statistics, Full-Stack Ops.
- Source: 2 Feishu Docs into \_living/AI-Infrastructure and \_living/AI-Applications
- Created: entities/edge-rk3576.md, entities/edge-sophon.md, concepts/hermes-mac-ops.md
- Updated: SCHEMA.md, index.md

### lint | Deep Sync Executed

- Action: Full graph traversal (Deep Sync) on \_living/.
- Discovered new structural files: RuView-Technical-Research-Deployment.md
- Rebuilt Layer 2 links for newly structured contents. Ghosts purged.
- Added: entities/ruview.md, entities/esp32-s3.md

### update | True Deep Sync: Content Revision

- Action: Reread all 5 modified living docs. Overwrote Layer 2 concepts.
- Stripped old Feishu metadata references from concepts.
- Updated: `concepts/markdown-llm-protocol.md`, `concepts/agent-frameworks.md`, `concepts/llm-benchmark-methodology.md`, `concepts/llm-computational-complexity.md`.

## [2026-05-15] daily | Wiki maintenance

### ingest | LMM Input Mechanics

- Source: New living doc `_living/AI-Infrastructure/LMM-Input-Mechanics.md`
- Created: `concepts/lmm-input-mechanics.md` with links mapping
- Updated: `index.md`, `concepts/markdown-llm-protocol.md`, and added frontmatter to living doc.

### update | Global Linkage Sync

- Action: Full linkage sync across all living docs, concepts, and entities.
- Detail: Injected missing `[[wikilinks]]` at the bottom of 17 legacy files to weave the Knowledge Graph.

## [2026-05-17] daily | Wiki maintenance

### ingest | Markdown 进阶语法与 Obsidian 解析机制

- 创建了源文档：`_living/AI-Infrastructure/Advanced-Markdown-Syntax.md`
- 更新了 Layer 2 概念页：`concepts/advanced-markdown-syntax.md`
- 关联了相关文档：`concepts/markdown-llm-protocol.md`
- 更新了：`index.md`

### ingest | 知识图谱的技术演进：从符号主义到大语言模型

- 创建了源文档：\_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md (遵循极简元数据原则)
- 提炼了 Layer 2 概念页：concepts/traditional-knowledge-graph.md
- 提炼了 Layer 2 概念页：concepts/ontology.md
- 关联了相关文档：concepts/advanced-markdown-syntax.md, concepts/markdown-llm-protocol.md
- 更新了：index.md

### update | 本体论架构重组：从概念到实体

- 移除了本体论错误的流程化概念卡片：`concepts/hermes-mac-ops.md`
- 基于 `_living/AI-Applications/Hermes-Agent-macOS-Ops.md`，重新提取并建立了软件实体页：`entities/hermes-agent.md`
- 拆分建立了前代遗产软件实体页：`entities/openclaw.md`
- 全面使用紧凑型内联语法重做了 Layer 2 溯源脚注
- 更新了：`index.md`

### lint | Schema compliance and ghost-node repair

- Removed zero-byte ghost pages: `hermes-mac-ops.md`, `set-theory-reading.md`
- Repointed stale wikilinks to active Layer 2 nodes: `[[hermes-agent]]`, `[[openclaw]]`, `[[set-theory]]`
- Added missing `sources` frontmatter to affected Layer 2 pages
- Registered `math` and `logic` in `SCHEMA.md` tag taxonomy
- Reconciled `index.md` page count and normalized malformed log section formatting
- Pruned nonexistent entries from `.obsidian/workspace.json` last-open state
- Linked `index.md`, `SCHEMA.md`, and `log.md` to reduce meta-page graph isolation

### update | Strengthen Layer 2 schema and registry rules

- Scoped hard constraints explicitly to Active Layer 2 pages (`entities/`, `concepts/`, `comparisons/`, `queries/`)
- Added strict invariants for unique slugs, non-empty `sources`/`tags`, resolved wikilinks, and directory-to-type matching
- Added lifecycle rules for create / rename / replace / split / merge / archive / delete
- Declared `index.md` the single registry for active Layer 2 nodes and formalized registration rules

## [2026-05-18] daily | Wiki maintenance

### lint | Registry sync after Obsidian mechanics ingest

- Replaced stale `[[advanced-markdown-syntax]]` links with `[[wikilinks]]`
- Added missing `sources` frontmatter to `concepts/wikilinks.md`, `concepts/graph-centrality.md`, and `entities/obsidian.md`
- Registered `[[obsidian]]`, `[[graph-centrality]]`, and `[[wikilinks]]` in `index.md`
- Removed deleted `[[advanced-markdown-syntax]]` from `index.md` and reconciled total page count

### tooling | Add wiki Layer 2 consistency linter

- Added `scripts/wiki_lint.py` as the canonical post-maintenance validator for Layer 2 graph consistency
- Updated `SCHEMA.md` to require `python3 scripts/wiki_lint.py` after wiki sync, rebuild, or batch generation

## [2026-05-24] daily | Wiki maintenance

### ingest | LLM Reasoning: Thinking 与 Effort 全景调研

- 创建了源文档：`_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md`（含发展历史、实现思路、最新研究、各厂商实践）
- 提炼了 Layer 2 概念页：`concepts/chain-of-thought.md`、`concepts/test-time-compute-scaling.md`、`concepts/reasoning-effort-control.md`
- 提炼了 Layer 2 对比页：`comparisons/reasoning-model-apis.md`（首个填充 Comparisons 区块的节点）
- 在 `SCHEMA.md` 标签库与 `scripts/wiki_lint.py` 的 ALLOWED_TAGS 中注册了新标签 `reasoning`
- 关联了相关文档：`concepts/agent-frameworks.md`、`concepts/llm-benchmark-methodology.md`、`concepts/llm-computational-complexity.md`
- 更新了：`index.md`（Total pages 17 → 21）

### update | Graph review: reciprocal links + re-ingest thin pages

- 修复 reasoning 集群「单向桥」：在 `llm-computational-complexity`、`agent-frameworks`、`llm-benchmark-methodology` 补反向链接至 `chain-of-thought` / `test-time-compute-scaling`
- 深度重提炼 `concepts/llm-computational-complexity.md`：补全四篇核心论文（Merrill&Sabharwal TC0/P、Li et al. 串行下界、Faith and Fate、Hahn 形式语言限制）及溯源脚注
- 深度重提炼 `concepts/llm-benchmark-methodology.md`：从单一 MMLU 扩展为评测方法学原语 + 六类基准分类法 + 厂商偏好 + 推理预算新挑战
- 给 `concepts/agent-frameworks.md` 补 `llm` 标签
- 未改动 `_living/` 任何源文档（严守单向引用原则）

### update | 全库 Layer1↔Layer2 覆盖度审计 + 欠提炼修补

- 审计：逐一比对全部 11 个 `_living` 源文档与对应 Layer 2 页面的覆盖度
- 重写 `concepts/agent-frameworks.md`：从仅认知澄清段，扩为五大阵营 14 框架全景 + 7 场景化选型
- 重写 `concepts/markdown-llm-protocol.md`：补全三受众场景（AI 读/人机共读/人读）与三层数据流转架构
- 补全 `entities/edge-rk3576.md`、`entities/edge-sophon.md` 的核心规格表（CPU/TOPS/内存/型号定位）
- 补全 `concepts/graph-centrality.md` 漏掉的「紧密中心性 (Closeness Centrality)」
- 修复 `entities/edge-sophon.md` 重复的 `updated` frontmatter 键
- 未改动 `_living/` 任何源文档；`wiki_lint: OK`

## [2026-05-25] daily | Wiki maintenance

### refactor | ReID & Customer Flow: 整体重组

- 审计：上一轮 ingest 把 8 篇飞书文档原文堆在 `_living/Computer-Vision/ReID/` 目录，并把 `_living/` 路径直接登记到 `index.md` Queries 区，违反 SCHEMA（Layer 2 注册表不得登记 `_living/` 节点）；wiki_lint 报 9 个 stale_index_entries + 1 个 duplicate_index_entry
- \_living 重组：删除整个 `_living/Computer-Vision/` 目录；将可复用知识合并为两篇现位于 `_living/Whale-SpaceSight/` 下的文档：`ReID-Pipeline-Architecture.md`、`Customer-Flow-Post-Processing.md`
- 命名风格统一：Title-Case-With-Hyphens.md，与现有 `Hermes-Agent-macOS-Ops.md` / `RuView-Technical-Research-Deployment.md` 对齐
- 内容裁剪（第一轮）：剔除具体表名/字段名/SQL/分区脚本/单店实验细节/项目排期甘特图等实现专属信息，保留架构、方法学、效果总结
- 内容裁剪（第二轮，深度脱敏）：进一步剔除所有项目内私有命名（如 `hidalgo_*` 表名、`cloth_detection` / `entrance_embed` 等模型节点名、`seq_sn_threshold` / `clstentrance_pars` 等配置键）、所有具体数值阈值（聚类阈值、时间窗、像素距离、6 维评分规则参数）、具体维度（768 维 / 2048 维）、具体效果数字（AUC / 准确率范围 / 去重率）、具体产品/库版本（Milvus / pgvector / Airflow / KubernetesExecutor / Spark 等）；保留可复现的架构、范式、设计原则
- Layer 2 提炼：创建 `concepts/reid-pipeline.md`、`concepts/multi-stage-clustering.md`、`concepts/customer-flow-post-processing.md`（3 个 concepts，无 entity——该系统无专有产品名）
- 关联性审计：删除 3 条牵强的跨主题域出链（`hermes-agent` / `ruview` / `graph-centrality`）；ReID 3 个 concept 形成闭合三角，不向其他主题域强行牵线
- 标签注册：在 `SCHEMA.md` 标签库与 `scripts/wiki_lint.py` 的 ALLOWED_TAGS 中新增 `computer-vision`、`reid`、`clustering`、`pipeline`
- 索引同步：移除 `index.md` Queries 区 9 条 `_living/` 误注册项；在 Concepts 区按字母序新增 3 条；`Total pages` 21 → 24
- 未改动 `_living/` 中已有的非 ReID 文档；`wiki_lint: OK`

### update | ReID 知识库基于真实代码事实核查 + 重写

- 触发：用户指出 ReID 实际实现位于 `~/Documents/GithubRepo/VisitorTRACE-REID/HIDALGO/`，让我据此核对并修正前一轮基于二手飞书文档构建的知识库
- 代码审计：通过 general-purpose agent 通读 `HIDALGO/` 包的 17 个核心源文件并产出结构化报告，覆盖管线形态 / 聚类算法 / 角色过滤 / 接待识别 / 客流过滤 / 模型推理 / 存储 / 调度 / 评估指标 9 大维度
- 关键修正：
  - **管线形态**：从二手文档假设的"Kafka 流式管线"修正为**离线批处理函数** `(店铺, 时间窗, 模式) → 结果`；上游感知（模型推理 / 底库相似度查询）与下游编排（DAG 调度）都在本系统职责外
  - **聚类结构**：从假设的"4 阶段（在线 / 离线 / 属性约束 / 兜底）"修正为底层是**相似度图连通分量** + 多层级 tier（Entrance 7 层 / Interior 5 档 / Coupling 4 阶段）；明确不是经典 HAC 的 single linkage
  - **三模式对偶**：补全此前完全缺失的 Entrance / Interior / Coupling 三模式架构（Coupling 是生产主模式）
  - **角色判定两阶段**：把单纯的"前置过滤"修正为**预判 + 后重判**（聚类后按簇取众数 + 徽章比例覆写 + 融合分兜底）
  - **接待识别 / 假人 / 嵌套过滤**：在 HIDALGO 代码中**完全不存在**——只有小门框过店过滤是真实的（loc_x/loc_y_filter + 单调方向检测）。在 customer-flow-post-processing 的 \_living 和 Layer 2 中加上"代码边界说明"，明确这部分来源是二手设计/测试报告（独立下游服务，不在 HIDALGO 仓库），confidence 改为 medium
  - **存储**：确认 PG + pgvector，**Milvus 在该仓库未运行时调用**（处理器存在但不被调用），底库相似度查询发生在更上游
  - **调度**：确认 Airflow DAG **不在本仓库**，外部调度器 + 本地轻量任务进度表是分工边界
  - **评估指标**：删除 `Rank-N / mAP / mCP`——这些**不在 HIDALGO 实现**（可能在训练侧仓库）；本系统只评角色精/召 + 双向熵
- 补全此前漏掉的设计模式：按店参数覆写表（JSON 列 + deep merge）、有偏下采样（保进店、采出店）、推理服务共享内存优化、多套环境配置中心、历史变体与实验代码并存
- 文档操作：
  - 重写 `_living/Whale-SpaceSight/ReID-Pipeline-Architecture.md`（含三模式对偶 / 角色两阶段 / 按店覆写 / 反作弊采样 等新章节）
  - 重写 `_living/Whale-SpaceSight/Customer-Flow-Post-Processing.md`，顶部加上"代码边界说明"
  - 重写 `concepts/reid-pipeline.md`、`concepts/multi-stage-clustering.md`、`concepts/customer-flow-post-processing.md`，对齐新事实
  - `concepts/customer-flow-post-processing.md` 的 `confidence` 由 `high` 降为 `medium`
  - 更新 `index.md` 中 `reid-pipeline` 与 `multi-stage-clustering` 的一句话摘要
- `wiki_lint: OK`

## [2026-05-26] daily | Wiki maintenance

### ingest | ReID Embedding Models 模型选型调研

- 触发：用户要求调研 ReID 特征向量模型现状（FastReid 已用过，关心 ViT 等新 SOTA），并落地到 \_living + Layer 2
- 调研路径：WebSearch 拉取近年 ReID 特征模型现状（FastReid / TransReID / SOLIDER / CLIP-ReID / PersonViT / LUPerson / DINOv2 / ViT 边缘部署），覆盖学术 SOTA + 实战部署 + 跨域泛化三个维度
- 新建 `_living/Whale-SpaceSight/ReID-Embedding-Models.md`：技术谱系（BoT/FastReid → TransReID → SOLIDER/CLIP-ReID → PersonViT）、选型决策框架（域泛化/算力/微调成本/遮挡）、部署约束（TensorRT 延迟、256×128 输入、跨域掉点幅度）、评估方法学局限（学术数据集 vs 零售门店的 domain gap）
- Layer 2 提炼：新增 `concepts/reid-embedding-models.md`——独立的"特征提取器"主题，与 `[[reid-pipeline]]`（管线架构）解耦；颗粒度对齐现有"技术谱系类" concepts（chain-of-thought / test-time-compute-scaling）；无 entity（无专有产品名）
- 关联性：与 ReID 三角连成"四点闭合"——`reid-embedding-models ↔ reid-pipeline / multi-stage-clustering / customer-flow-post-processing`；body 内显式引用前两者
- 索引同步：`index.md` Concepts 区按字母序插入；`Total pages` 24 → 25
- 内容控制：调研结果包含学术 mAP 数字（用以体现谱系差异）；本次不强行剔除——这些是"可复现的学术事实"而非"项目内部实现细节"，与之前 ReID Layer 1 脱敏的初衷不冲突
- `wiki_lint: OK`

### audit | 全量关联性 + Schema 合规审计

- 触发：用户要求做整体审计——关联性保守、L2 提取准确完备、最终 lint 合规
- 完备性：逐一比对 15 篇 `_living` 与 25 个 L2 节点，**全部 \_living 都有对应 L2 提炼**（其中 5 篇被拆为多个 L2）
- Schema 合规：25 个 L2 节点全部满足 frontmatter 完整、type 与目录匹配、tags 在 taxonomy、sources 非空
- 关联性收紧（删除以下 body 不引用、纯主题词重叠的 Related 区链接）：
  - `concepts/llm-computational-complexity.md` Related → 删 `set-theory`
  - `concepts/set-theory.md` Related → 删 `llm-benchmark-methodology`（集合论与基准方法学跨主题域无关联）
  - `concepts/llm-benchmark-methodology.md` Related → 删 `markdown-llm-protocol`
  - `concepts/markdown-llm-protocol.md` Related → 删 `llm-benchmark-methodology` + `chain-of-thought`；body 第 29 行内一个语义错链 `[[chain-of-thought\|工具调用]]` 改为纯文本"工具调用"（CoT 不等于工具调用）
  - `entities/obsidian.md` Related → 把 `markdown-llm-protocol` 换为 `wikilinks`（后者是 Obsidian 真正的核心机制，body 显式提及双向链接）
  - `entities/edge-rk3576.md` Related → 删 `ruview`（视觉 NPU 与 WiFi CSI 跨主题域）
  - `entities/edge-sophon.md` Related → 删 `ruview`（同上）
  - `entities/esp32-s3.md` Related → 删 `edge-rk3576`（CSI 微控制器与视觉 NPU 跨主题域）
  - `entities/ruview.md` Related → 删 `edge-rk3576`（反向同上）
- 残留软约束：5 个 entity/concept 出链数 < 2（`graph-centrality`、`set-theory`、`edge-rk3576`、`edge-sophon`、`esp32-s3`、`ruview`），但按用户"谨慎保守"原则不强加跨主题域 sibling；当前 `wiki_lint.py` 不强制 ≥ 2 出链检查，lint 通过
- 未修改任何 \_living 源文档；未新增/删除任何 L2 节点
- `wiki_lint: OK`

### update | SCHEMA 升级：写入用户六条运维原则

- 触发：用户提出 6 条 wiki 运维原则，要求按 LLM 可解析的命令式语言写入 `SCHEMA.md`，并明确这些是"原则上要求"（含主观判断成分，不同模型在不同参数下执行可能有差异）
- 修改的章节：
  - `Scope`：补 **Raw Reference Sources** 一段——`raw/**` 承载公开版本属性的外部内容（网页/论文/书刊），与 `_living/` 的区别在于来源（私有手写 vs 外部已发布）
  - `Page Thresholds`：新增 **Granularity Heuristics** 小节——给出"整体研究对象"判据、过细/过粗的反模式、父子并存允许条件；明确这是启发式而非硬阈值
  - 新建 **Type Semantics** 章节——为 entity / concept / comparison / query 四种类型分别给出定位、触发条件、必含内容、不要建的反例；其中 comparison 明确要求"对比表格 + Trade-offs + 适用场景"三件套，query 明确"问题驱动 SOP 而非名词解释"
  - `Layer 2 Graph Invariants`：补 **关联谨慎保守原则**——要求 wikilink 必须能在 body 里用具体一句话陈述关系本质，仅"同主题词"不足以构成关联；本原则强度优先于"每页 ≥ 2 出链"的软建议
  - `Living Documents Policy`：补第 8 条 **Reusability Filter**——`_living/` 只承载可复用知识，实现细节（私有命名/具体阈值/产品版本号/单店数据）应被剥离；并提示 ingest 工具输出只是布局转换，语义脱敏需手动完成
- 行文风格：每条原则附"判据 + 反例"，便于不同模型一致执行；同时显式承认"原则上要求"的弹性，让边界情形保守处理而非教条
- 未修改任何 \_living 源文档或 L2 节点
- `wiki_lint: OK`

### audit | 按升级后的 SCHEMA 做全量复审

- 触发：SCHEMA 升级后（新增 Raw Reference Sources / Granularity Heuristics / Type Semantics / Conservative Linking / Reusability Filter），需要把新规则反向应用到现有 26 个 L2 节点
- SCHEMA 自身的三处自检修正：
  - `updated` 字段刷新到 2026-05-26（自我违反"updated 必须随内容刷新"）
  - `Conventions` 第 5 条把"每页至少 2 个出链"从硬约束改为"鼓励 + 软建议"，与新增的"关联谨慎保守原则"协调一致
  - `Conventions` 中 `Provenance markers` 拆为两种语法：`_living/` 用紧凑内联脚注 `^[[[...|alias]]]`、`raw/` 用简洁脚注 `^[raw/...]`，消除原模糊语法
- L2 类型语义复核（25 个老节点 + 1 个新节点全部通过）
- 关联性进一步收紧（按新增 Conservative Linking 原则）：
  - `concepts/lmm-input-mechanics.md` Related → 删 `llm-computational-complexity`（跨主题域，body 无引用）
  - `concepts/traditional-knowledge-graph.md` Related → 删 `markdown-llm-protocol`（KG 与 Markdown LLM 协议不是替代关系）
- Comparison 三件套合规修正：
  - `comparisons/reasoning-model-apis.md` 原本只有"对比表格"，**补齐 Trade-offs 段与 When to use 决策段**；frontmatter `updated` 同步刷新
- 完备性补建（按新 SCHEMA comparison 触发条件）：
  - `_living/Whale-SpaceSight/ReID-Embedding-Models.md` 通篇是 5 候选选型分析，明显满足 comparison 三大触发信号（选型分析 / 优劣对比 / A vs B）
  - 新建 `comparisons/reid-embedding-model-families.md`——含五候选对比表、四组核心 Trade-offs、五条 When-to-use 决策；与 `concepts/reid-embedding-models.md` 形成 concept（技术谱系）+ comparison（横向决策）的互补
  - `concepts/reid-embedding-models.md` body 显式 reference 该 comparison，Related 区按字母序追加
- 索引同步：`index.md` Comparisons 区新增条目；`Total pages` 25 → 26
- 不动 \_living 已有内容（Reusability Filter 面向未来 ingest，不回溯）
- `wiki_lint: OK`

### ingest | TRAJEX ReID 感知层服务

- 触发：用户提供 `~/Documents/WhaleRepo/whds/project_hidalgo_reid/trajex/` 的 ReID 推理服务代码，要求按最新 SCHEMA 设计融入
- 代码审计：通过 general-purpose agent 通读 TRAJEX 仓库（README、`src/trajex/{inference,queue,database,cluster,models,setting,config,commands}/`、KAFKA_DEDUPLICATION.md、5 个 rebuild/rerun 脚本、trajex-api/admin/alert 子服务），产出 1200 字结构化报告
- 关键事实确认：
  - TRAJEX 与 HIDALGO 之间**只通过数据库表握手，无 RPC 无共享内存**——schema 即契约
  - TRAJEX 只做"逐轨迹特征化 + 角色 1-NN 库查询"，**不做聚类、不分配行人 ID**
  - 推理走 Triton + 本机共享内存直连；模型旧主特征轴 / 新统一特征轴可并行写入
  - 两层 Redis 集合去重（按天滚动 TTL，曾用 Bloom filter 后替换以避免假阳性）
  - 三种回放模式：scheduled rebuild / manual rerun / cache rebuild
  - Milvus → pgvector 按集合渐进迁移，dispatcher 层切换不动业务代码
- \_living 新建：`_living/Whale-SpaceSight/ReID-Perception-Layer-TRAJEX.md`（10 节，覆盖职责边界 / 数据流 / 模型推理 / 库查询 / 去重 / 回放 / 模型升级 / hybrid 存储 / 运维 / 设计哲学）；按 Reusability Filter 剥离所有项目内私有命名（具体表名、列名、Kafka topic 名、模型节点名、配置键、Redis key 命名等）
- L2 提炼（按 Conservative Linking 严格筛选，agent 提议 14 个新节点，砍剪到 6 个）：
  - `entities/trajex.md` — 具体服务实体
  - `concepts/reid-library-lookup.md` — 把 1-NN 角色判定上移到感知层的方法学
  - `concepts/model-shadow-deployment.md` — 配对特征轴并行的模型升级模式
  - `concepts/schema-as-handoff-contract.md` — DDL 作为生产者/消费者契约的通用范式
  - `comparisons/trajex-vs-hidalgo.md` — 感知层 vs 计算层分工对比（含三件套：对比表 + Trade-offs + When to use）
  - `queries/how-to-roll-out-a-new-reid-model.md` — **wiki 中第一个 query 节点**，端到端 SOP 串联 reid-embedding-models / model-shadow-deployment / TRAJEX / reid-pipeline / reid-library-lookup
- 砍掉的候选（颗粒度过细 / 厂商绑定 / 重复）：
  - `entities/hidalgo` — 已在 reid-pipeline concept 中作为方法学描述；HIDALGO 是内部代号，作为 entity 颗粒度模糊
  - `entities/triton-inference-server` — 过于通用，没有专属 \_living 详述
  - `concepts/kafka-dedup-pre-producer` — 厂商绑定（Kafka + Redis 具体组合），并入 \_living 实施细节
  - `concepts/triton-shared-memory-deployment` — 厂商绑定 Triton，并入 \_living
  - `concepts/replay-source-tagging` — 颗粒度过细，已并入 model-shadow-deployment body
  - `comparisons/online-vs-offline-reid-compute-split` — 与 TRAJEX-vs-HIDALGO 高度重叠
  - `queries/where-do-reid-features-come-from` — 太薄，不构成 SOP
- 反向链补充（按 Conservative Linking，仅在 body 有显式陈述时建立）：
  - `concepts/reid-pipeline.md` body 中"上游感知层"段引入 `[[trajex|TRAJEX]]` 与 `[[reid-library-lookup]]`；Related 区新增 `[[trajex|TRAJEX]]`、`[[trajex-vs-hidalgo|TRAJEX vs HIDALGO]]`
- 索引同步：`index.md` Entities/Concepts/Comparisons/Queries 四个区都新增条目；`Total pages` 26 → 32
- `wiki_lint: OK`

### audit | TRAJEX ingest 二次核事实

- 触发：上一轮 ClaudeCode 已完成主体 ingest；本轮按源码对照复核，重点看 `src/trajex/inference/processor.py`、`src/trajex/inference/worker.py`、`src/trajex/database/db_manager.py`、`src/trajex/database/redis.py`、`src/trajex/queue/kafka_shared_queue.py`、回放脚本与 pgvector/Milvus 检索路径
- 修正事实表述：
  - 将"v1/v2 双列"改为"旧主 ReID 特征轴 / 新统一特征轴并行"，避免把通用模式误读成源码里的字面列名
  - 将质量模型表述改为"可选 / 预留"，因为当前主处理链路保留质量字段与旧客户端能力，但并非每条图像都实际写入质量结果
  - 将底库分层改为"通用角色服饰库 / 公司或店铺工服库 / 店员 ReID 底库"，贴合源码中的角色服饰检索、员工工服检索与店员 ReID 检索三路
  - 将 query SOP 中的具体脚本名与具体生产列名抽象为 reembedding 任务与生产特征列，符合 Reusability Filter
- 同步更新：`_living/Whale-SpaceSight/ReID-Perception-Layer-TRAJEX.md`、`entities/trajex.md`、`concepts/model-shadow-deployment.md`、`comparisons/trajex-vs-hidalgo.md`、`queries/how-to-roll-out-a-new-reid-model.md`、`index.md`
- 元数据修正：`index.md` 与 `log.md` frontmatter `updated` 刷新到 2026-05-26
- 验证：从 git repo 根目录运行 `python3 scripts/wiki_lint.py`，返回 `wiki_lint: OK`

### audit | ReID 命名边界与 SCHEMA 再审计

- 触发：用户补充 `HIDALGO` 与 `TRAJEX` 都是内部项目名，并指出 `project_hidalgo_reid/` 的目录结构可作为术语关系证据；要求连同 `_living` 文档一起审计 ReID 相关 wiki 是否有谬误
- 代码/目录事实核对：
  - 顶层仓库 `/Users/chenzhou/Documents/WhaleRepo/whds/project_hidalgo_reid` 的 README 标题与顶层 `pyproject.toml` 均确认项目/包名为 `HIDALGO`
  - `trajex/` 是该仓库下独立子项目，拥有独立 `pyproject.toml` 与 `src/trajex/` 服务代码
  - `hidalgo/coreprime.py` 主流程确认当前计算层按 `(shop_id, time range, mode)` 批处理，读取特征表，执行角色重判、聚合 / 匹配与结果回写；主流程不直接做模型推理或消息消费
- 结论修正：上一轮“`entities/hidalgo` 因为是内部代号不建”理由不成立；正确判据应是**是否具备边界清晰的软件项目/服务身份**。按最新 SCHEMA 的 entity 语义，HIDALGO 与 TRAJEX 都应是 entity：`HIDALGO` 是顶层 ReID 项目与计算层服务，`TRAJEX` 是其中特征推理 / 感知层服务
- L2 修正：
  - 新建 `entities/hidalgo.md`
  - 将 `entities/trajex.md`、`comparisons/trajex-vs-hidalgo.md`、`concepts/reid-pipeline.md`、`concepts/schema-as-handoff-contract.md`、`concepts/reid-library-lookup.md`、`concepts/model-shadow-deployment.md`、`queries/how-to-roll-out-a-new-reid-model.md` 中的“ReID 计算层 / HIDALGO”指代收敛到 `[[hidalgo|HIDALGO]]`
  - 保留 `concepts/reid-pipeline.md` 作为系统分层方法学节点，不再让它兼任 HIDALGO 实体身份
  - `concepts/customer-flow-post-processing.md` 与 `concepts/multi-stage-clustering.md` 补充到 `[[hidalgo|HIDALGO]]` 的明确语义链路
- \_living 修正：
  - `ReID-Pipeline-Architecture.md` 补“命名边界”段：HIDALGO 是顶层项目名 / 计算层服务，TRAJEX 是特征推理子项目 / 服务
  - `ReID-Perception-Layer-TRAJEX.md` 补同样的命名边界，并将下游统一称为 HIDALGO 计算层
  - `Customer-Flow-Post-Processing.md` 将“ReID 核心引擎”泛称收敛为 HIDALGO 计算层，避免服务边界混淆
- 工具修正：`scripts/wiki_lint.py` 不再把 `_living` 紧凑溯源脚注 `^[[[_living/...]]]` 当作普通 graph wikilink，也移除“少于 2 出链”的硬失败项，以对齐当前 SCHEMA 的 Conservative Linking 软约束
- 索引同步：`index.md` Entities 区新增 `[[hidalgo|HIDALGO]]`，`Total pages` 32 → 33
- 审计结果：未发现需要推翻 ReID 管线职责、TRAJEX 感知层职责、库查询/影子部署/DDL 契约等核心事实的谬误；主要问题是 HIDALGO/TRAJEX 的 entity 判定标准与术语指代不一致
- `wiki_lint: OK`

### update | Clarify Layer 1 source-material scope

- 将 Layer 1 从仅 `_living/**` 扩展为 `_living/**` + `raw/**` 的原始材料层
- 在 `SCHEMA.md` 中区分 Living Sources 与 Raw Reference Sources，收窄 `_living/` 专属约束
- 同步 `index.md` 注册规则，明确 `_living/` 与 `raw/` 都不登记为 active Layer 2 节点

### tooling | Strengthen wiki_lint schema coverage and reporting

- 对照 `SCHEMA.md` Validation Invariants 扩展 `scripts/wiki_lint.py`：补 Meta frontmatter、全库 active slug 唯一性、index 分区一致性、非 active wikilink、source 文件、日期、confidence、contradictions 等检查
- 将默认文本输出改为固定顺序 checklist，逐项显示 `[OK]` / `[FAIL]`；保留 `--json` 机器可读输出
- 同步 `SCHEMA.md` 验证章节，明确 lint 输出格式与普通 wikilink 不得指向 Layer 1 / Meta / Archive 的约束

### audit | Full schema compliance pass

- 执行全库严格审计：`wiki_lint.py`、目录/文件名盘点、Layer 1 元数据检查、溯源语法检查、comparison/query 结构检查、出链统计、index 计数与分区检查
- 修正 `SCHEMA.md` 内部不一致：Active 文件名规则明确只作用于 Layer 2；Create 生命周期中的"至少 2 个出链"改回 Conservative Linking 下的软建议；Deep Sync 示例改为当前紧凑溯源语法
- 扩展 `scripts/wiki_lint.py`：新增 Active 文件名 kebab-case 检查与 `_living/` 语义型 frontmatter 禁止项检查

## [2026-05-27] daily | Wiki maintenance

### update | Hermes Agent 运维手册

- 追加更新了“第六章：忙时输入模式 (Busy Input Mode) 与连续对话机制”
- 说明了 interrupt、queue 和 steer 三种模式的时序表现，以及极快发消息时因为空闲回退而产生的“并行/排队回复幻觉”。
- 涉及文件：\_living/AI-Applications/Hermes-Agent-macOS-Ops.md

### create | agent-mid-turn-input-modes

- 从 `_living/AI-Applications/Hermes-Agent-macOS-Ops.md` 第 6.6 节提炼新 concept：`concepts/agent-mid-turn-input-modes.md`
- 描述 Agent 在用户 mid-turn 追加输入时的 interrupt / queue / steer 三模式调度对偶（围绕"是否终止当前回合"和"是否保留 Prompt Cache"两个轴）
- `entities/hermes-agent.md` 新增"连续对话调度"段落与底部双链；`updated` 同步刷新
- `index.md` Concepts 区登记新节点；`Total pages` 33 → 34

## [2026-06-02] daily | Wiki maintenance

### ingest | AI Agent Harness 工程架构研究报告

- Source: 个人深度调研报告（13 个框架对比、五层架构分析、工程原则）
- Action: 创建 `_living/AI-Infrastructure/AI-Agent-Harness-Engineering.md`
- Content: Harness 定义、五层架构（编排/上下文/沙盒/HITL/协议）、13 个框架全景、框架对比、工程原则、2026 发展趋势、术语手册、参考文献
- Layer 2: 未提炼独立节点（内容已在 `concepts/agent-frameworks.md` 覆盖核心概念）
- Note: 本次 ingest 为 living document，按最小元数据原则不添加语义型 frontmatter

## [2026-06-03] daily | Wiki maintenance

### cleanup | 孤立节点清理

- Action: 删除 `wiki/Checkpointing.md`、`wiki/MCP.md`（0 字节孤立文件）
- Reason: 这两个文件是 2026-06-02 ingest 时误创建的占位符，违反 SCHEMA（Layer 2 节点不得漂浮在根目录）
- Verification: `wiki_lint.py` 检查 `root_floating_nodes` 从 2 项 → 0 项

### refactor | Living document 合规性修复

- Target: `_living/AI-Infrastructure/AI-Agent-Harness-Engineering.md`
- Action 1: 移除 frontmatter 中的语义字段（`type: living-document`, `tags: [...]`），保留最小必要元数据（title, created, updated, review-date, sources）
- Action 2: 将正文中的 graph wikilinks（`[[ReAct]]`、`[[Checkpointing]]`、`[[HITL]]`、`[[MCP]]`）改为普通文本 + Markdown 锚点链接
- Action 3: 修改标题从"深度调研报告"改为"工程实践指南"，更符合 living document 定位
- Action 4: 添加代码示例版本说明与免责声明
- Action 5: 删除重复的 1.3 节"核心术语解释"（与第六章术语手册重复）
- Action 6: 补全版本历史日期（Version 1.0: 2026-06-02, Version 1.1: 2026-06-03）
- Action 7: 新增第四章"Agent Harness 选型决策指南"（决策树、场景化选型矩阵、评估维度、迁移路径）
- Action 8: 修复脚注引用机制（将 `[^1]` `[^2]` 改为行内引用格式）
- Reason: 符合 SCHEMA §12 Living Documents Policy（不得包含 graph wikilinks 或语义型 frontmatter）
- Verification: `wiki_lint.py` 检查 `living_wikilinks` 与 `living_semantic_frontmatter` 从各 1 项 → 0 项

### fix | 跨层引用修复

- Target: `concepts/agent-frameworks.md`
- Action 1: 删除指向 `_living/AI-Infrastructure/AI-Agent-Harness-Engineering.md` 的 wikilink
- Action 2: 从 frontmatter `sources` 中移除该 \_living 文件
- Reason: Active Layer 2 节点不得用普通 wikilink 指向 Layer 1（应使用溯源脚注语法）
- Verification: `wiki_lint.py` 检查 `non_active_wikilinks` 从 1 项 → 0 项

### update | SCHEMA 标签库扩充与日期同步

- Action 1: 在 Tag Taxonomy 中新增 **Agent 与编排 (Agent & Orchestration)** 类别
- Tags added: `orchestration`, `harness`, `react`, `context-management`, `sandbox`, `hitl`, `protocol`, `multi-agent`
- Action 2: 将原 `agent` 标签从"全栈与运维"移至新类别
- Action 3: 同步 `scripts/wiki_lint.py` 中的 `ALLOWED_TAGS` 集合
- Action 4: 更新 `SCHEMA.md` frontmatter `updated: 2026-07-02`
- Reason: 覆盖 AI Agent Harness 领域的核心术语，支持未来相关节点创建
- Verification: `wiki_lint.py` 全部 11 项检查通过

### audit | Wiki 全面审计与优化

- Scope: 知识库结构、lint 脚本、SCHEMA 规范、文档质量、\_living 文档合规性
- Findings:
  - ✅ Lint 检查通过率：100% (11/11)
  - ✅ Active Layer 2 节点：34 个（与 index.md 声明一致）
  - ✅ Living Documents：17 个（均符合最小元数据原则）
  - ✅ 孤立节点：0 个
  - ✅ Index 完整性：34/34 全部注册
  - ✅ Wikilinks：无死链，无跨层误引用
- Actions: 清理孤立节点、修复 living document 违规、扩充标签库、更新日志与 SCHEMA 日期
- Result: 知识库健康度从 ⭐⭐⭐ (3/5) 提升至 ⭐⭐⭐⭐ (4/5)

### create | agent-harness 概念节点与知识关联建立

- Trigger: 发现 AI-Agent-Harness-Engineering.md (\_living 层) 提及 Hermes Agent 和 Claude Code，但缺少正式的知识图谱链接
- Analysis: "Agent Harness" 是重要的独立架构概念，应从 \_living 提炼为 Layer 2 concept 节点
- Action 1: 创建 `concepts/agent-harness.md`，提炼核心内容：
  - Harness 定义与核心职责
  - 五层架构（编排/上下文/沙盒/HITL/协议）详解
  - 与 Agent 框架的区别
  - 实现案例（Hermes Agent / OpenClaw）
  - 工程原则
- Action 2: 建立知识图谱关联：
  - `concepts/agent-frameworks.md` → 正文中将 "Agent Harness" 改为 `[[agent-harness]]` wikilink
  - `entities/hermes-agent.md` → 正文声明实现了 Harness 五层架构，Related 区新增 `[[agent-harness]]`
  - `entities/openclaw.md` → 正文声明实现了 Harness 模式，Related 区新增 `[[agent-harness]]`
  - `concepts/agent-harness.md` → Related 区建立双向链接：`[[agent-frameworks]]`, `[[hermes-agent]]`, `[[openclaw]]`, `[[chain-of-thought]]`, `[[agent-mid-turn-input-modes]]`, `[[markdown-llm-protocol]]`
- Action 3: 同步元数据：
  - `agent-frameworks.md`, `hermes-agent.md`, `openclaw.md` 的 `updated` 字段刷新到 2026-06-03
  - `index.md` 注册新节点，Total pages 34 → 35
- Verification: `wiki_lint: OK`
- Result: 建立了清晰的"概念 → 实现"映射，Harness 架构知识与现有实体（Hermes/OpenClaw）形成完整的知识网络

## [2026-06-29] daily | Wiki maintenance

### reinject | Evolution of Knowledge Graphs

- Source: `_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md`
- Action 1: 对 living 源文档做格式化重组，补充 Graph RAG、Hybrid Search / RRF，并将 LLM Wiki v1 / v2 的来源分别校正为 Karpathy idea file 与 Rohit LLM Wiki v2 gist
- Action 2: 更新既有节点：
  - `concepts/traditional-knowledge-graph.md` 扩展推理路线为逻辑规则、表示学习、神经符号/LLM 三类
  - `concepts/ontology.md` 补充拓扑、集合、逻辑行为、实体一致性四类约束，并说明 OWL / SHACL 分工
- Action 3: 新增 Layer 2 concepts：
  - `concepts/llm-wiki.md`
  - `concepts/graph-rag.md`
  - `concepts/hybrid-search-rrf.md`
- Action 4: 同步 `index.md` Concepts 区登记新节点，`Total pages` 35 → 38
- Verification: `wiki_lint: OK`

### update | Obsidian Knowledge Base Mechanics

- Source: `_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md`
- Action 1: 扩充 living 源文档，新增 vault 文件模型、wikilinks 变体、backlinks/outgoing links、embeds、Properties/frontmatter、MetadataCache/API、搜索与插件生态、Graph View 与外部图分析边界、Obsidian 与 LLM Wiki 接口
- Action 2: 修正过度实现绑定：不再把 Obsidian 的元数据层写死为 IndexedDB，也不把高级中心性指标写成核心 Graph View 的默认能力
- Action 3: 同步更新 `entities/obsidian.md`、`concepts/wikilinks.md`、`concepts/graph-centrality.md` 的正文与 `updated` 字段
- Verification: `wiki_lint: OK`

### update | Graph algorithms for node status and relation strength

- Source: `_living/AI-Infrastructure/Obsidian-Knowledge-Base-Mechanics.md`
- Action 1: 深化第 5 章 Graph View / 图论渲染中的算法部分，按“节点地位”“关系强度”“KG 表示学习”“社区发现”拆分
- Action 2: 补充算法：Weighted Degree/Strength、k-core、Common Neighbors、Adamic-Adar、Resource Allocation、Preferential Attachment、Katz、SimRank、TransE/TransH/TransR、DistMult/ComplEx、RotatE、GNN/R-GCN
- Action 3: 同步扩展 `concepts/graph-centrality.md`，作为后续检索节点地位、关系强度、链接预测和知识补全算法的 Layer 2 入口
- Verification: `wiki_lint: OK`

### update | Text Format Protocol for LLMs

- Source: `_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md`
- Action 1: 扩充 living 源文档，从原有三受众场景扩展为完整文本格式协议指南
- Action 2: 新增格式选择矩阵、Markdown 子集规范、JSON/YAML/XML/CSV/HTML 适用边界、Prompt/Agent 上下文隔离、结构化输出契约、RAG 文档规范、多模态文本化原则和常见反模式
- Action 3: 同步更新 `concepts/markdown-llm-protocol.md`，补充格式选择原则、Prompt/Agent 上下文协议和 RAG Markdown 规范
- Verification: `wiki_lint: OK`

### refactor | Living topic taxonomy for Whale SpaceSight

- Action 1: 新建 `_living/Whale-SpaceSight/`，承载 Whale Tech 下 SpaceSight 产品相关知识
- Action 2: 移入 SpaceSight 相关源文档：`Edge-Compute-Boxes-RK3576-Sophon.md`、`ReID-Pipeline-Architecture.md`、`ReID-Perception-Layer-TRAJEX.md`、`ReID-Embedding-Models.md`、`Customer-Flow-Post-Processing.md`
- Action 3: 将 `_living/AI-Applications-and-Ops/` 重命名为 `_living/AI-Applications/`，保留 `Hermes-Agent-macOS-Ops.md` 与 `RuView-Technical-Research-Deployment.md`
- Action 4: 全库更新 Layer 2 `sources` 与紧凑型溯源脚注中的 `_living` 路径，并同步刷新受影响节点 `updated` 字段
- Action 5: 在 `SCHEMA.md` 和 `scripts/wiki_lint.py` 中新增 `_living` 一级分类目录 2-3 词段 kebab-case 主题命名规则
- Verification: `python3 scripts/wiki_lint.py`
