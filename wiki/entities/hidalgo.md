---
title: Hidalgo (ReID 项目与计算层服务)
created: 2026-05-26
updated: 2026-05-26
type: entity
tags: [computer-vision, reid, pipeline, ops]
sources:
  - _living/AI-Applications-and-Ops/ReID-Pipeline-Architecture.md
  - _living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex.md
confidence: high
---

# Hidalgo (ReID 项目与计算层服务)

Hidalgo 是线下零售门店 ReID 重构项目的顶层项目名，也常用于指代其中负责**后续聚合、角色推断与结果回写**的计算层服务。它与 [[trajex]] 的关系不是"一个内部代号 vs 一个正式产品名"，而是同一 ReID 项目下两个边界不同的服务实体：trajex 负责特征推理，Hidalgo 负责消费特征并产出行人级结果。^[[[_living/AI-Applications-and-Ops/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 职责边界

作为计算层服务，Hidalgo 读取 trajex 写入的图像级 / 轨迹级特征表，按店铺、时间窗与运行模式执行离线批处理。它的主流程不做实时消息消费，也不直接做模型推理，而是把已经入库的特征、角色证据、轨迹坐标与事件信息加工为 ReID 结果。

核心职责包括：

- **角色推断 / 重判**：消费感知层给出的角色证据，并在聚类后按簇众数、徽章比例、店员融合分等信号重判角色；
- **多层级聚合**：在 Entrance / Interior / Coupling 三种模式下执行出入口聚合、店内轨迹组装与跨场景匹配，方法学见 [[multi-stage-clustering]]；
- **结果回写**：输出 ReID 结果表与业务宽表，供后续客流加工层消费。

## 与 trajex 的关系

[[trajex]] 是 Hidalgo 项目中的上游特征推理服务。两者之间通过数据库表握手：trajex 生产特征表，Hidalgo 消费特征表并写结果表；双方不通过 RPC 调用，也不共享运行时内存。这种服务边界是 [[schema-as-handoff-contract|DDL 作为契约]] 在 ReID 管线中的具体实践。^[[[_living/AI-Applications-and-Ops/ReID-Perception-Layer-trajex|ReID-Perception-Layer-trajex]]]

因此，[[reid-pipeline]] 是对 Hidalgo / trajex 这套系统分层方法的抽象描述；Hidalgo 本身是其中具体的软件实体。

---

**相关概念**:

- [[trajex]]
- [[reid-pipeline]]
- [[multi-stage-clustering]]
- [[schema-as-handoff-contract]]
- [[trajex-vs-hidalgo]]
