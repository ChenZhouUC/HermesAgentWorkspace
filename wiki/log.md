---
title: Wiki Log
created: 2026-05-14
updated: 2026-05-26
type: summary
tags: [wiki, tool]
sources: []
confidence: high
---

# Wiki Log

> 知识库操作追踪日志 (Append-only)
> 格式：`## [YYYY-MM-DD] action | subject`

## [2026-05-14] create | Wiki initialized

- Domain: AI Infrastructure, Edge Inference, TCS & Math
- Action: Created base directory structure, SCHEMA.md, index.md, and log.md.

## [2026-05-14] ingest | Batch import from Feishu Living Docs

- Source: 5 Feishu Docs into `_living/AI-Infrastructure` and `_living/TCS-and-Math`
- Created: `concepts/markdown-llm-protocol.md`, `concepts/agent-frameworks.md`, `concepts/llm-benchmark-methodology.md`, `concepts/llm-computational-complexity.md`, `concepts/set-theory-reading.md`
- Updated: `index.md`

## [2026-05-14] ingest | Expand Domain and New Docs

- Action: Expanded SCHEMA.md domains to include Algorithm Engineering, Statistics, Full-Stack Ops.
- Source: 2 Feishu Docs into \_living/AI-Infrastructure and \_living/AI-Applications-and-Ops
- Created: entities/edge-rk3576.md, entities/edge-sophon.md, concepts/hermes-mac-ops.md
- Updated: SCHEMA.md, index.md

## [2026-05-14] lint | Deep Sync Executed

- Action: Full graph traversal (Deep Sync) on \_living/.
- Discovered new structural files: RuView-Technical-Research-Deployment.md
- Rebuilt Layer 2 links for newly structured contents. Ghosts purged.
- Added: entities/ruview.md, entities/esp32-s3.md

## [2026-05-14] update | True Deep Sync: Content Revision

- Action: Reread all 5 modified living docs. Overwrote Layer 2 concepts.
- Stripped old Feishu metadata references from concepts.
- Updated: `concepts/markdown-llm-protocol.md`, `concepts/agent-frameworks.md`, `concepts/llm-benchmark-methodology.md`, `concepts/llm-computational-complexity.md`.

## [2026-05-15] ingest | LMM Input Mechanics

- Source: New living doc `_living/AI-Infrastructure/LMM-Input-Mechanics.md`
- Created: `concepts/lmm-input-mechanics.md` with links mapping
- Updated: `index.md`, `concepts/markdown-llm-protocol.md`, and added frontmatter to living doc.

## [2026-05-15] update | Global Linkage Sync

- Action: Full linkage sync across all living docs, concepts, and entities.
- Detail: Injected missing `[[wikilinks]]` at the bottom of 17 legacy files to weave the Knowledge Graph.

## [2026-05-17] ingest | Markdown 进阶语法与 Obsidian 解析机制

- 创建了源文档：`_living/AI-Infrastructure/Advanced-Markdown-Syntax.md`
- 更新了 Layer 2 概念页：`concepts/advanced-markdown-syntax.md`
- 关联了相关文档：`concepts/markdown-llm-protocol.md`
- 更新了：`index.md`

## [2026-05-17] ingest | 知识图谱的技术演进：从符号主义到大语言模型

- 创建了源文档：\_living/AI-Infrastructure/Evolution-of-Knowledge-Graphs.md (遵循极简元数据原则)
- 提炼了 Layer 2 概念页：concepts/traditional-knowledge-graph.md
- 提炼了 Layer 2 概念页：concepts/ontology.md
- 关联了相关文档：concepts/advanced-markdown-syntax.md, concepts/markdown-llm-protocol.md
- 更新了：index.md

## [2026-05-17] update | 本体论架构重组：从概念到实体

- 移除了本体论错误的流程化概念卡片：`concepts/hermes-mac-ops.md`
- 基于 `_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops.md`，重新提取并建立了软件实体页：`entities/hermes-agent.md`
- 拆分建立了前代遗产软件实体页：`entities/openclaw.md`
- 全面使用紧凑型内联语法重做了 Layer 2 溯源脚注
- 更新了：`index.md`

## [2026-05-17] lint | Schema compliance and ghost-node repair

- Removed zero-byte ghost pages: `hermes-mac-ops.md`, `set-theory-reading.md`
- Repointed stale wikilinks to active Layer 2 nodes: `[[hermes-agent]]`, `[[openclaw]]`, `[[set-theory]]`
- Added missing `sources` frontmatter to affected Layer 2 pages
- Registered `math` and `logic` in `SCHEMA.md` tag taxonomy
- Reconciled `index.md` page count and normalized malformed log section formatting
- Pruned nonexistent entries from `.obsidian/workspace.json` last-open state
- Linked `index.md`, `SCHEMA.md`, and `log.md` to reduce meta-page graph isolation

## [2026-05-17] update | Strengthen Layer 2 schema and registry rules

- Scoped hard constraints explicitly to Active Layer 2 pages (`entities/`, `concepts/`, `comparisons/`, `queries/`)
- Added strict invariants for unique slugs, non-empty `sources`/`tags`, resolved wikilinks, and directory-to-type matching
- Added lifecycle rules for create / rename / replace / split / merge / archive / delete
- Declared `index.md` the single registry for active Layer 2 nodes and formalized registration rules

## [2026-05-18] lint | Registry sync after Obsidian mechanics ingest

- Replaced stale `[[advanced-markdown-syntax]]` links with `[[wikilinks]]`
- Added missing `sources` frontmatter to `concepts/wikilinks.md`, `concepts/graph-centrality.md`, and `entities/obsidian.md`
- Registered `[[obsidian]]`, `[[graph-centrality]]`, and `[[wikilinks]]` in `index.md`
- Removed deleted `[[advanced-markdown-syntax]]` from `index.md` and reconciled total page count

## [2026-05-18] tooling | Add wiki Layer 2 consistency linter

- Added `scripts/wiki_lint.py` as the canonical post-maintenance validator for Layer 2 graph consistency
- Updated `SCHEMA.md` to require `python3 scripts/wiki_lint.py` after wiki sync, rebuild, or batch generation

## [2026-05-24] ingest | LLM Reasoning: Thinking 与 Effort 全景调研

- 创建了源文档：`_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md`（含发展历史、实现思路、最新研究、各厂商实践）
- 提炼了 Layer 2 概念页：`concepts/chain-of-thought.md`、`concepts/test-time-compute-scaling.md`、`concepts/reasoning-effort-control.md`
- 提炼了 Layer 2 对比页：`comparisons/reasoning-model-apis.md`（首个填充 Comparisons 区块的节点）
- 在 `SCHEMA.md` 标签库与 `scripts/wiki_lint.py` 的 ALLOWED_TAGS 中注册了新标签 `reasoning`
- 关联了相关文档：`concepts/agent-frameworks.md`、`concepts/llm-benchmark-methodology.md`、`concepts/llm-computational-complexity.md`
- 更新了：`index.md`（Total pages 17 → 21）

## [2026-05-24] update | Graph review: reciprocal links + re-ingest thin pages

- 修复 reasoning 集群「单向桥」：在 `llm-computational-complexity`、`agent-frameworks`、`llm-benchmark-methodology` 补反向链接至 `chain-of-thought` / `test-time-compute-scaling`
- 深度重提炼 `concepts/llm-computational-complexity.md`：补全四篇核心论文（Merrill&Sabharwal TC0/P、Li et al. 串行下界、Faith and Fate、Hahn 形式语言限制）及溯源脚注
- 深度重提炼 `concepts/llm-benchmark-methodology.md`：从单一 MMLU 扩展为评测方法学原语 + 六类基准分类法 + 厂商偏好 + 推理预算新挑战
- 给 `concepts/agent-frameworks.md` 补 `llm` 标签
- 未改动 `_living/` 任何源文档（严守单向引用原则）

## [2026-05-24] update | 全库 Layer1↔Layer2 覆盖度审计 + 欠提炼修补

- 审计：逐一比对全部 11 个 `_living` 源文档与对应 Layer 2 页面的覆盖度
- 重写 `concepts/agent-frameworks.md`：从仅认知澄清段，扩为五大阵营 14 框架全景 + 7 场景化选型
- 重写 `concepts/markdown-llm-protocol.md`：补全三受众场景（AI 读/人机共读/人读）与三层数据流转架构
- 补全 `entities/edge-rk3576.md`、`entities/edge-sophon.md` 的核心规格表（CPU/TOPS/内存/型号定位）
- 补全 `concepts/graph-centrality.md` 漏掉的「紧密中心性 (Closeness Centrality)」
- 修复 `entities/edge-sophon.md` 重复的 `updated` frontmatter 键
- 未改动 `_living/` 任何源文档；`wiki_lint: OK`

## [2026-05-25] refactor | ReID & Customer Flow: 整体重组

- 审计：上一轮 ingest 把 8 篇飞书文档原文堆在 `_living/Computer-Vision/ReID/` 目录，并把 `_living/` 路径直接登记到 `index.md` Queries 区，违反 SCHEMA（Layer 2 注册表不得登记 `_living/` 节点）；wiki_lint 报 9 个 stale_index_entries + 1 个 duplicate_index_entry
- \_living 重组：删除整个 `_living/Computer-Vision/` 目录；将可复用知识合并为两篇位于 `_living/AI-Applications-and-Ops/` 下的文档：`ReID-Pipeline-Architecture.md`、`Customer-Flow-Post-Processing.md`
- 命名风格统一：Title-Case-With-Hyphens.md，与现有 `Hermes-Agent-macOS-Ops.md` / `RuView-Technical-Research-Deployment.md` 对齐
- 内容裁剪（第一轮）：剔除具体表名/字段名/SQL/分区脚本/单店实验细节/项目排期甘特图等实现专属信息，保留架构、方法学、效果总结
- 内容裁剪（第二轮，深度脱敏）：进一步剔除所有项目内私有命名（如 `hidalgo_*` 表名、`cloth_detection` / `entrance_embed` 等模型节点名、`seq_sn_threshold` / `clstentrance_pars` 等配置键）、所有具体数值阈值（聚类阈值、时间窗、像素距离、6 维评分规则参数）、具体维度（768 维 / 2048 维）、具体效果数字（AUC / 准确率范围 / 去重率）、具体产品/库版本（Milvus / pgvector / Airflow / KubernetesExecutor / Spark 等）；保留可复现的架构、范式、设计原则
- Layer 2 提炼：创建 `concepts/reid-pipeline.md`、`concepts/multi-stage-clustering.md`、`concepts/customer-flow-post-processing.md`（3 个 concepts，无 entity——该系统无专有产品名）
- 关联性审计：删除 3 条牵强的跨主题域出链（`hermes-agent` / `ruview` / `graph-centrality`）；ReID 3 个 concept 形成闭合三角，不向其他主题域强行牵线
- 标签注册：在 `SCHEMA.md` 标签库与 `scripts/wiki_lint.py` 的 ALLOWED_TAGS 中新增 `computer-vision`、`reid`、`clustering`、`pipeline`
- 索引同步：移除 `index.md` Queries 区 9 条 `_living/` 误注册项；在 Concepts 区按字母序新增 3 条；`Total pages` 21 → 24
- 未改动 `_living/` 中已有的非 ReID 文档；`wiki_lint: OK`

## [2026-05-25] update | ReID 知识库基于真实代码事实核查 + 重写

- 触发：用户指出 ReID 实际实现位于 `~/Documents/GithubRepo/VisitorTRACE-REID/hidalgo/`，让我据此核对并修正前一轮基于二手飞书文档构建的知识库
- 代码审计：通过 general-purpose agent 通读 `hidalgo/` 包的 17 个核心源文件并产出结构化报告，覆盖管线形态 / 聚类算法 / 角色过滤 / 接待识别 / 客流过滤 / 模型推理 / 存储 / 调度 / 评估指标 9 大维度
- 关键修正：
  - **管线形态**：从二手文档假设的"Kafka 流式管线"修正为**离线批处理函数** `(店铺, 时间窗, 模式) → 结果`；上游感知（模型推理 / 底库相似度查询）与下游编排（DAG 调度）都在本系统职责外
  - **聚类结构**：从假设的"4 阶段（在线 / 离线 / 属性约束 / 兜底）"修正为底层是**相似度图连通分量** + 多层级 tier（Entrance 7 层 / Interior 5 档 / Coupling 4 阶段）；明确不是经典 HAC 的 single linkage
  - **三模式对偶**：补全此前完全缺失的 Entrance / Interior / Coupling 三模式架构（Coupling 是生产主模式）
  - **角色判定两阶段**：把单纯的"前置过滤"修正为**预判 + 后重判**（聚类后按簇取众数 + 徽章比例覆写 + 融合分兜底）
  - **接待识别 / 假人 / 嵌套过滤**：在 hidalgo 代码中**完全不存在**——只有小门框过店过滤是真实的（loc_x/loc_y_filter + 单调方向检测）。在 customer-flow-post-processing 的 \_living 和 Layer 2 中加上"代码边界说明"，明确这部分来源是二手设计/测试报告（独立下游服务，不在 hidalgo 仓库），confidence 改为 medium
  - **存储**：确认 PG + pgvector，**Milvus 在该仓库未运行时调用**（处理器存在但不被调用），底库相似度查询发生在更上游
  - **调度**：确认 Airflow DAG **不在本仓库**，外部调度器 + 本地轻量任务进度表是分工边界
  - **评估指标**：删除 `Rank-N / mAP / mCP`——这些**不在 hidalgo 实现**（可能在训练侧仓库）；本系统只评角色精/召 + 双向熵
- 补全此前漏掉的设计模式：按店参数覆写表（JSON 列 + deep merge）、有偏下采样（保进店、采出店）、推理服务共享内存优化、多套环境配置中心、历史变体与实验代码并存
- 文档操作：
  - 重写 `_living/AI-Applications-and-Ops/ReID-Pipeline-Architecture.md`（含三模式对偶 / 角色两阶段 / 按店覆写 / 反作弊采样 等新章节）
  - 重写 `_living/AI-Applications-and-Ops/Customer-Flow-Post-Processing.md`，顶部加上"代码边界说明"
  - 重写 `concepts/reid-pipeline.md`、`concepts/multi-stage-clustering.md`、`concepts/customer-flow-post-processing.md`，对齐新事实
  - `concepts/customer-flow-post-processing.md` 的 `confidence` 由 `high` 降为 `medium`
  - 更新 `index.md` 中 `reid-pipeline` 与 `multi-stage-clustering` 的一句话摘要
- `wiki_lint: OK`

## [2026-05-26] ingest | ReID Embedding Models 模型选型调研

- 触发：用户要求调研 ReID 特征向量模型现状（FastReid 已用过，关心 ViT 等新 SOTA），并落地到 \_living + Layer 2
- 调研路径：WebSearch 拉取近年 ReID 特征模型现状（FastReid / TransReID / SOLIDER / CLIP-ReID / PersonViT / LUPerson / DINOv2 / ViT 边缘部署），覆盖学术 SOTA + 实战部署 + 跨域泛化三个维度
- 新建 `_living/AI-Applications-and-Ops/ReID-Embedding-Models.md`：技术谱系（BoT/FastReid → TransReID → SOLIDER/CLIP-ReID → PersonViT）、选型决策框架（域泛化/算力/微调成本/遮挡）、部署约束（TensorRT 延迟、256×128 输入、跨域掉点幅度）、评估方法学局限（学术数据集 vs 零售门店的 domain gap）
- Layer 2 提炼：新增 `concepts/reid-embedding-models.md`——独立的"特征提取器"主题，与 [[reid-pipeline]]（管线架构）解耦；颗粒度对齐现有"技术谱系类" concepts（chain-of-thought / test-time-compute-scaling）；无 entity（无专有产品名）
- 关联性：与 ReID 三角连成"四点闭合"——`reid-embedding-models ↔ reid-pipeline / multi-stage-clustering / customer-flow-post-processing`；body 内显式引用前两者
- 索引同步：`index.md` Concepts 区按字母序插入；`Total pages` 24 → 25
- 内容控制：调研结果包含学术 mAP 数字（用以体现谱系差异）；本次不强行剔除——这些是"可复现的学术事实"而非"项目内部实现细节"，与之前 ReID Layer 1 脱敏的初衷不冲突
- `wiki_lint: OK`

## [2026-05-26] audit | 全量关联性 + Schema 合规审计

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

## [2026-05-26] update | SCHEMA 升级：写入用户六条运维原则

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

## [2026-05-26] audit | 按升级后的 SCHEMA 做全量复审

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
  - `_living/AI-Applications-and-Ops/ReID-Embedding-Models.md` 通篇是 5 候选选型分析，明显满足 comparison 三大触发信号（选型分析 / 优劣对比 / A vs B）
  - 新建 `comparisons/reid-embedding-model-families.md`——含五候选对比表、四组核心 Trade-offs、五条 When-to-use 决策；与 `concepts/reid-embedding-models.md` 形成 concept（技术谱系）+ comparison（横向决策）的互补
  - `concepts/reid-embedding-models.md` body 显式 reference 该 comparison，Related 区按字母序追加
- 索引同步：`index.md` Comparisons 区新增条目；`Total pages` 25 → 26
- 不动 \_living 已有内容（Reusability Filter 面向未来 ingest，不回溯）
- `wiki_lint: OK`

## [2026-05-26] ingest | trajex ReID 感知层服务

- 触发：用户提供 `~/Documents/WhaleRepo/whds/project_hidalgo_reid/trajex/` 的 ReID 推理服务代码，要求按最新 SCHEMA 设计融入
- 代码审计：通过 general-purpose agent 通读 trajex 仓库（README、`src/trajex/{inference,queue,database,cluster,models,setting,config,commands}/`、KAFKA_DEDUPLICATION.md、5 个 rebuild/rerun 脚本、trajex-api/admin/alert 子服务），产出 1200 字结构化报告
- 关键事实确认：
  - trajex 与 hidalgo 之间**只通过数据库表握手，无 RPC 无共享内存**——schema 即契约
  - trajex 只做"逐轨迹特征化 + 角色 1-NN 库查询"，**不做聚类、不分配行人 ID**
  - 推理走 Triton + 本机共享内存直连；模型旧主特征轴 / 新统一特征轴可并行写入
  - 两层 Redis 集合去重（按天滚动 TTL，曾用 Bloom filter 后替换以避免假阳性）
  - 三种回放模式：scheduled rebuild / manual rerun / cache rebuild
  - Milvus → pgvector 按集合渐进迁移，dispatcher 层切换不动业务代码
- \_living 新建：`_living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex.md`（10 节，覆盖职责边界 / 数据流 / 模型推理 / 库查询 / 去重 / 回放 / 模型升级 / hybrid 存储 / 运维 / 设计哲学）；按 Reusability Filter 剥离所有项目内私有命名（具体表名、列名、Kafka topic 名、模型节点名、配置键、Redis key 命名等）
- L2 提炼（按 Conservative Linking 严格筛选，agent 提议 14 个新节点，砍剪到 6 个）：
  - `entities/trajex.md` — 具体服务实体
  - `concepts/reid-library-lookup.md` — 把 1-NN 角色判定上移到感知层的方法学
  - `concepts/model-shadow-deployment.md` — 配对特征轴并行的模型升级模式
  - `concepts/schema-as-handoff-contract.md` — DDL 作为生产者/消费者契约的通用范式
  - `comparisons/trajex-vs-hidalgo.md` — 感知层 vs 计算层分工对比（含三件套：对比表 + Trade-offs + When to use）
  - `queries/how-to-roll-out-a-new-reid-model.md` — **wiki 中第一个 query 节点**，端到端 SOP 串联 reid-embedding-models / model-shadow-deployment / trajex / reid-pipeline / reid-library-lookup
- 砍掉的候选（颗粒度过细 / 厂商绑定 / 重复）：
  - `entities/hidalgo` — 已在 reid-pipeline concept 中作为方法学描述；hidalgo 是内部代号，作为 entity 颗粒度模糊
  - `entities/triton-inference-server` — 过于通用，没有专属 \_living 详述
  - `concepts/kafka-dedup-pre-producer` — 厂商绑定（Kafka + Redis 具体组合），并入 \_living 实施细节
  - `concepts/triton-shared-memory-deployment` — 厂商绑定 Triton，并入 \_living
  - `concepts/replay-source-tagging` — 颗粒度过细，已并入 model-shadow-deployment body
  - `comparisons/online-vs-offline-reid-compute-split` — 与 trajex-vs-hidalgo 高度重叠
  - `queries/where-do-reid-features-come-from` — 太薄，不构成 SOP
- 反向链补充（按 Conservative Linking，仅在 body 有显式陈述时建立）：
  - `concepts/reid-pipeline.md` body 中"上游感知层"段引入 [[trajex]] 与 [[reid-library-lookup]]；Related 区新增 [[trajex]]、[[trajex-vs-hidalgo]]
- 索引同步：`index.md` Entities/Concepts/Comparisons/Queries 四个区都新增条目；`Total pages` 26 → 32
- `wiki_lint: OK`

## [2026-05-26] audit | trajex ingest 二次核事实

- 触发：上一轮 ClaudeCode 已完成主体 ingest；本轮按源码对照复核，重点看 `src/trajex/inference/processor.py`、`src/trajex/inference/worker.py`、`src/trajex/database/db_manager.py`、`src/trajex/database/redis.py`、`src/trajex/queue/kafka_shared_queue.py`、回放脚本与 pgvector/Milvus 检索路径
- 修正事实表述：
  - 将"v1/v2 双列"改为"旧主 ReID 特征轴 / 新统一特征轴并行"，避免把通用模式误读成源码里的字面列名
  - 将质量模型表述改为"可选 / 预留"，因为当前主处理链路保留质量字段与旧客户端能力，但并非每条图像都实际写入质量结果
  - 将底库分层改为"通用角色服饰库 / 公司或店铺工服库 / 店员 ReID 底库"，贴合源码中的角色服饰检索、员工工服检索与店员 ReID 检索三路
  - 将 query SOP 中的具体脚本名与具体生产列名抽象为 reembedding 任务与生产特征列，符合 Reusability Filter
- 同步更新：`_living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex.md`、`entities/trajex.md`、`concepts/model-shadow-deployment.md`、`comparisons/trajex-vs-hidalgo.md`、`queries/how-to-roll-out-a-new-reid-model.md`、`index.md`
- 元数据修正：`index.md` 与 `log.md` frontmatter `updated` 刷新到 2026-05-26
- 验证：从 git repo 根目录运行 `python3 scripts/wiki_lint.py`，返回 `wiki_lint: OK`

## [2026-05-26] audit | ReID 命名边界与 SCHEMA 再审计

- 触发：用户补充 `hidalgo` 与 `trajex` 都是内部项目名，并指出 `project_hidalgo_reid/` 的目录结构可作为术语关系证据；要求连同 `_living` 文档一起审计 ReID 相关 wiki 是否有谬误
- 代码/目录事实核对：
  - 顶层仓库 `/Users/chenzhou/Documents/WhaleRepo/whds/project_hidalgo_reid` 的 README 标题与顶层 `pyproject.toml` 均确认项目/包名为 `hidalgo`
  - `trajex/` 是该仓库下独立子项目，拥有独立 `pyproject.toml` 与 `src/trajex/` 服务代码
  - `hidalgo/coreprime.py` 主流程确认当前计算层按 `(shop_id, time range, mode)` 批处理，读取特征表，执行角色重判、聚合 / 匹配与结果回写；主流程不直接做模型推理或消息消费
- 结论修正：上一轮“`entities/hidalgo` 因为是内部代号不建”理由不成立；正确判据应是**是否具备边界清晰的软件项目/服务身份**。按最新 SCHEMA 的 entity 语义，hidalgo 与 trajex 都应是 entity：`hidalgo` 是顶层 ReID 项目与计算层服务，`trajex` 是其中特征推理 / 感知层服务
- L2 修正：
  - 新建 `entities/hidalgo.md`
  - 将 `entities/trajex.md`、`comparisons/trajex-vs-hidalgo.md`、`concepts/reid-pipeline.md`、`concepts/schema-as-handoff-contract.md`、`concepts/reid-library-lookup.md`、`concepts/model-shadow-deployment.md`、`queries/how-to-roll-out-a-new-reid-model.md` 中的“ReID 计算层 / hidalgo”指代收敛到 `[[hidalgo]]`
  - 保留 `concepts/reid-pipeline.md` 作为系统分层方法学节点，不再让它兼任 hidalgo 实体身份
  - `concepts/customer-flow-post-processing.md` 与 `concepts/multi-stage-clustering.md` 补充到 `[[hidalgo]]` 的明确语义链路
- \_living 修正：
  - `ReID-Pipeline-Architecture.md` 补“命名边界”段：Hidalgo 是顶层项目名 / 计算层服务，trajex 是特征推理子项目 / 服务
  - `ReID-Perception-Layer-trajex.md` 补同样的命名边界，并将下游统一称为 hidalgo 计算层
  - `Customer-Flow-Post-Processing.md` 将“ReID 核心引擎”泛称收敛为 hidalgo 计算层，避免服务边界混淆
- 工具修正：`scripts/wiki_lint.py` 不再把 `_living` 紧凑溯源脚注 `^[[[_living/...]]]` 当作普通 graph wikilink，也移除“少于 2 出链”的硬失败项，以对齐当前 SCHEMA 的 Conservative Linking 软约束
- 索引同步：`index.md` Entities 区新增 `[[hidalgo]]`，`Total pages` 32 → 33
- 审计结果：未发现需要推翻 ReID 管线职责、trajex 感知层职责、库查询/影子部署/DDL 契约等核心事实的谬误；主要问题是 hidalgo/trajex 的 entity 判定标准与术语指代不一致
- `wiki_lint: OK`

## [2026-05-26] update | Clarify Layer 1 source-material scope

- 将 Layer 1 从仅 `_living/**` 扩展为 `_living/**` + `raw/**` 的原始材料层
- 在 `SCHEMA.md` 中区分 Living Sources 与 Raw Reference Sources，收窄 `_living/` 专属约束
- 同步 `index.md` 注册规则，明确 `_living/` 与 `raw/` 都不登记为 active Layer 2 节点

## [2026-05-26] tooling | Strengthen wiki_lint schema coverage and reporting

- 对照 `SCHEMA.md` Validation Invariants 扩展 `scripts/wiki_lint.py`：补 Meta frontmatter、全库 active slug 唯一性、index 分区一致性、非 active wikilink、source 文件、日期、confidence、contradictions 等检查
- 将默认文本输出改为固定顺序 checklist，逐项显示 `[OK]` / `[FAIL]`；保留 `--json` 机器可读输出
- 同步 `SCHEMA.md` 验证章节，明确 lint 输出格式与普通 wikilink 不得指向 Layer 1 / Meta / Archive 的约束

## [2026-05-26] audit | Full schema compliance pass

- 执行全库严格审计：`wiki_lint.py`、目录/文件名盘点、Layer 1 元数据检查、溯源语法检查、comparison/query 结构检查、出链统计、index 计数与分区检查
- 修正 `SCHEMA.md` 内部不一致：Active 文件名规则明确只作用于 Layer 2；Create 生命周期中的"至少 2 个出链"改回 Conservative Linking 下的软建议；Deep Sync 示例改为当前紧凑溯源语法
- 扩展 `scripts/wiki_lint.py`：新增 Active 文件名 kebab-case 检查与 `_living/` 语义型 frontmatter 禁止项检查

## [2026-05-27] update | Hermes Agent 运维手册

- 追加更新了“第六章：忙时输入模式 (Busy Input Mode) 与连续对话机制”
- 说明了 interrupt、queue 和 steer 三种模式的时序表现，以及极快发消息时因为空闲回退而产生的“并行/排队回复幻觉”。
- 涉及文件：\_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops.md

## [2026-05-27] create | agent-mid-turn-input-modes

- 从 `_living/AI-Applications-and-Ops/Hermes-Agent-macOS-Ops.md` 第 6.6 节提炼新 concept：`concepts/agent-mid-turn-input-modes.md`
- 描述 Agent 在用户 mid-turn 追加输入时的 interrupt / queue / steer 三模式调度对偶（围绕"是否终止当前回合"和"是否保留 Prompt Cache"两个轴）
- `entities/hermes-agent.md` 新增"连续对话调度"段落与底部双链；`updated` 同步刷新
- `index.md` Concepts 区登记新节点；`Total pages` 33 → 34
