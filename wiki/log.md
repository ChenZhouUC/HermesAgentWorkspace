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
