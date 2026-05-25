---
title: Wiki Log
created: 2026-05-14
updated: 2026-05-17
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
