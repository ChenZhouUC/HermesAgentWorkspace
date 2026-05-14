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
