---
title: Wiki Index
created: 2026-05-14
updated: 2026-05-18
type: summary
tags: [wiki, tool]
sources: []
confidence: high
---

# Wiki Index

> 内容目录中枢。每个生成的知识节点都会在此处登记（一行一个双链 + 一句话摘要）。
> 本文件是 Active Layer 2（尤其 `concepts/` 与 `entities/`）的**唯一注册表**；检索、新增、重命名、归档、删除前，Agent 都必须先检查并同步此文件。
> Last updated: 2026-05-25 | Total pages: 24
> 结构规范参见 [[SCHEMA]]；操作追踪参见 [[log]]。

<!--
Registry Rules
1. 仅登记 active Layer 2 节点；不登记 `_living/`、`_archive/`、root ghost pages 或 meta pages。
2. 每个 active 节点必须且只能出现一次，且分区必须与目录/`type` 一致。
3. 条目格式固定为：- `[[slug]]` - 一句话摘要
4. 各分区按 slug 字母序排列。
5. rename / replace / archive / delete 时，必须在同一变更中同步更新本文件。
6. `Total pages` 是派生字段，必须精确等于下方已登记 active 节点数。
-->

## Entities (实体：模型/公司/硬件/框架)

<!-- Alphabetical within section -->

- [[edge-rk3576]] - RK3576 边缘 NPU 设备参数与定位
- [[edge-sophon]] - 算能 (Sophgo) 边缘 TPU 盒子系列
- [[esp32-s3]] - WiFi CSI 信号采集核心微控制器
- [[hermes-agent]] - 多模态 Agent 端到端框架，包含 macOS 核心网关与 Fallback 机制
- [[obsidian]] - 本地 Markdown 知识库与双链图谱工具
- [[openclaw]] - 早期的智能体前代框架（现已被 Hermes 继承并自动迁移）
- [[ruview]] - 基于 WiFi CSI 的穿墙无感知检测平台

## Concepts (概念：机制/算法/理论)

- [[agent-frameworks]] - 什么是真正的 Agent 框架及深度选型分析
- [[chain-of-thought]] - 思维链提示词族（CoT/Zero-shot/Self-Consistency/ToT/ReAct）
- [[customer-flow-post-processing]] - ReID 下游的接待识别、客流过滤与配置化设计方法学
- [[graph-centrality]] - 网络中心性算法及其在知识图谱分析中的应用
- [[llm-benchmark-methodology]] - AI 大模型基准测试系统调研
- [[llm-computational-complexity]] - 大语言模型在 TCS 领域的计算复杂性与严格下界
- [[lmm-input-mechanics]] - LMM (多模态大模型) 从 Markdown 到 Token 的处理机制
- [[markdown-llm-protocol]] - Markdown 在 LLM 交互场景下的格式协议架构
- [[multi-stage-clustering]] - 多阶段降维分治聚类：由严到松的四阶段聚合策略
- [[ontology]] - 知识工程中的本体论概念及其规范边界
- [[reasoning-effort-control]] - 推理努力程度/思考预算控制及过度思考与逆向扩展
- [[reid-pipeline]] - 行人重识别系统的前后端解耦架构与角色过滤策略
- [[set-theory]] - 集合论基础、公理体系与异见理论
- [[test-time-compute-scaling]] - 推理时计算扩展范式与推理模型的 RL 训练实现
- [[traditional-knowledge-graph]] - 大模型爆发前的符号主义知识图谱架构（KG）及三元组原理
- [[wikilinks]] - Wikilinks 与内联脚注等 Markdown 扩展语法机制

## Comparisons (横向对比表)

- [[reasoning-model-apis]] - 各厂商推理模型「思考/努力」API 参数与档位横向对比

## Queries (深度问答/探索存档)
