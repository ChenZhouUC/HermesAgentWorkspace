---
title: SpaceSight
created: 2026-07-01
updated: 2026-07-01
type: entity
tags: [spacesight, product-management, computer-vision]
sources:
  - _living/Whale-SpaceSight/SpaceSight-QA-List.md
  - _living/Whale-SpaceSight/ReID-Pipeline-Architecture.md
  - _living/Whale-SpaceSight/Customer-Flow-Post-Processing.md
confidence: high
---

# SpaceSight

SpaceSight 是面向线下门店与展陈场景的视觉智能产品线，围绕摄像头、边缘计算、ReID 与客流后处理，把出入口轨迹、店内轨迹和视觉检测结果转化为业务指标与现场排障动作。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

在当前 wiki 中，SpaceSight 不是一个单独算法，而是承载多个可复用工程主题的产品实体：底层依赖边缘盒子与视频推流，上游通过 [[trajex|TRAJEX]] 产生 ReID 特征，下游由 [[hidalgo|HIDALGO]] 与 [[customer-flow-post-processing]] 生成客流、接待和异常排查所需的业务事实。^[[[_living/Whale-SpaceSight/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 运维与方案边界

SpaceSight 相关问题通常分三类：

- **算力与部署成本**：私有化部署时，核心权衡是云端 GPU 推理与边缘端算力下沉，相关硬件节点见 [[edge-sophon]] 与 [[edge-rk3576]]。
- **客流与 ReID 质量**：出入口人数偏差、店内替代出入口、全店客流口径等问题，本质上落在 [[reid-pipeline]] 与 [[customer-flow-post-processing]] 的分层边界上。
- **非标视觉场景**：车展、巡检、质检等场景需要先确认摄像机视角、遮挡、实时性与可交付口径，不能直接把标准门店客流能力外推。

## 相关问答入口

完整业务问答保留在 living 文档中，Layer 2 只提取可复用 SOP：

- [[diagnose-spacesight-traffic-count-mismatch]]
- [[design-spacesight-nonstandard-traffic-plan]]

**相关概念**:

- [[reid-pipeline]]
- [[customer-flow-post-processing]]
- [[edge-sophon]]
- [[edge-rk3576]]
