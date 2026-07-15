---
title: Wiki Index
created: 2026-05-14
updated: 2026-07-15
type: summary
tags: [wiki, tool]
sources: []
confidence: high
---

# Wiki Index

> 内容目录中枢。每个生成的知识节点都会在此处登记（一行一个代码路径 + 一句话摘要）。
> 本文件是 Active Layer 2（尤其 `concepts/` 与 `entities/`）的**唯一注册表**；检索、新增、重命名、归档、删除前，Agent 都必须先检查并同步此文件。
> Last structural update: 2026-07-15 | Total pages: 43
> (Content updates tracked in individual page frontmatter)
> 结构规范参见 `SCHEMA.md`；操作追踪参见 `log.md`。Meta 页面使用纯文本路径，避免进入语义图谱。

<!--
Registry Rules
1. 仅登记 active Layer 2 节点；不登记 Layer 1 原材料（`_living/`、`raw/`）、`_archive/`、root ghost pages 或 meta pages。
2. 每个 active 节点必须且只能出现一次，且分区必须与目录/`type` 一致。
3. 条目格式固定为：- `entities/slug.md` - 一句话摘要（路径使用行内代码，目录按节点类型替换；禁止 wikilink）
4. 各分区按 slug 字母序排列。
5. rename / replace / archive / delete 时，必须在同一变更中同步更新本文件。
6. `Total pages` 是派生字段，必须精确等于下方已登记 active 节点数。
-->

## Entities (实体：模型/公司/硬件/框架)

<!-- Alphabetical within section -->

- `entities/edge-algo.md` - 边缘端算法服务：轨迹与事件抽取、弱网缓存机制
- `entities/edge-rk3576.md` - RK3576 边缘 SoC 的稳定规格、RKNN 工具链与整机边界
- `entities/edge-sophon.md` - SOPHGO CV186AH、BM1688、BM1684X 边缘 SoC 平台
- `entities/hermes-agent.md` - 多模态 Agent 端到端框架，包含 macOS 核心网关与 Fallback 机制
- `entities/hidalgo.md` - ReID 顶层项目与计算层服务：特征数据 → 行人 ID + 角色 + 轨迹
- `entities/model-context-protocol.md` - 连接 AI Host 与外部 tools、resources、prompts 的开放协议
- `entities/obsidian.md` - 本地 Markdown 知识库与双链图谱工具
- `entities/openclaw.md` - 早期的智能体前代框架（现已被 Hermes 继承并自动迁移）
- `entities/ruview.md` - 将 WiFi CSI 转换为人体感知结果的应用平台
- `entities/spacesight.md` - 线下门店与展陈场景的视觉智能产品线
- `entities/trajex.md` - ReID 感知层服务：边缘轨迹 + 图像 → 特征数据 + 角色标签

## Concepts (概念：机制/算法/理论)

- `concepts/agent-frameworks.md` - 什么是真正的 Agent 框架及深度选型分析
- `concepts/agent-harness.md` - Agent Harness 底座架构：五层系统（编排/上下文/沙盒/HITL/协议）
- `concepts/agent-mid-turn-input-modes.md` - Agent 在用户 mid-turn 追加输入时的 interrupt/queue/steer 三模式调度对偶
- `concepts/chain-of-thought.md` - 思维链提示词族（CoT/Zero-shot/Self-Consistency/ToT/ReAct）
- `concepts/customer-flow-post-processing.md` - 客流加工的三阶段顺序漏斗：感知侧基础过滤、中台清洗与核心业务指标衍生
- `concepts/edge-ai-deployment-stack.md` - 从整机、SoC、BSP、Runtime 到模型包和视频处理的边缘 AI 部署栈
- `concepts/graph-centrality.md` - 网络中心性算法及其在知识图谱分析中的应用
- `concepts/graph-rag.md` - 以实体关系图、路径和社区摘要增强 RAG 的检索架构
- `concepts/hybrid-search-rrf.md` - BM25、向量检索、图遍历等多路召回的排名融合方法
- `concepts/llm-benchmark-methodology.md` - LLM 评测对象、指标协议、证据状态与基准组合方法
- `concepts/llm-computational-complexity.md` - 大语言模型在 TCS 领域的计算复杂性与严格下界
- `concepts/llm-wiki.md` - 由 LLM 维护 Markdown 页面、索引和 schema 的轻量知识库架构
- `concepts/lmm-input-mechanics.md` - 多模态内容从媒体预处理、编码器与连接器到序列拼接或 cross-attention 的输入机制
- `concepts/markdown-llm-protocol.md` - LLM 系统中存储、传输、Prompt、结构化输出与执行边界的文本格式协议
- `concepts/model-shadow-deployment.md` - 模型升级时配对特征轴并行的影子部署模式
- `concepts/multi-stage-clustering.md` - 轨迹相似度图上的多层级连通分量聚合（由严到松、由同向到异向）
- `concepts/ontology.md` - 知识工程中的本体论概念及其规范边界
- `concepts/reasoning-effort-control.md` - 推理努力程度/思考预算控制及过度思考与逆向扩展
- `concepts/reid-embedding-models.md` - 行人 ReID 特征向量模型选型：从 BoT/FastReid 到 ViT/SOLIDER/CLIP-ReID
- `concepts/reid-library-lookup.md` - 把角色判定以 1-NN 库检索的方式融进特征提取阶段（区别于聚类）
- `concepts/reid-pipeline.md` - 行人重识别系统的"采集/计算/编排"三段分层与三模式对偶架构
- `concepts/schema-as-handoff-contract.md` - DDL 作为生产者/消费者契约的数据管线握手范式
- `concepts/set-theory.md` - 集合论基础、公理体系与异见理论
- `concepts/test-time-compute-scaling.md` - 推理时计算扩展范式与推理模型的 RL 训练实现
- `concepts/traditional-knowledge-graph.md` - 大模型爆发前的符号主义知识图谱架构（KG）及三元组原理
- `concepts/wifi-csi-sensing.md` - 从子载波级 WiFi CSI 到存在、活动、定位和生命体征推断的感知方法
- `concepts/wikilinks.md` - Wikilinks 与内联脚注等 Markdown 扩展语法机制

## Comparisons (横向对比表)

- `comparisons/reasoning-model-apis.md` - 各厂商推理模型「思考/努力」API 参数与档位横向对比
- `comparisons/rk3576-vs-sophon-edge-platforms.md` - RK3576 与 CV186AH、BM1688、BM1684X 的工具链、算力和场景选型
- `comparisons/trajex-vs-hidalgo.md` - ReID 系统的感知层与计算层分工对比（何时该拆、何时该合）

## Queries (深度问答/探索存档)

- `queries/diagnose-spacesight-traffic-count-mismatch.md` - 如何先验证客户基准，再分层排查 SpaceSight 客流数据偏差
- `queries/how-to-roll-out-a-new-reid-model.md` - 如何把一个新的 ReID 特征模型安全上线到生产（影子部署 + 灰度切换 + 回滚 SOP）
