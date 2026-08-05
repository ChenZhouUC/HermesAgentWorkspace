---
title: SpaceSight
created: 2026-07-01
updated: 2026-08-05
type: entity
tags: [spacesight, product-management, computer-vision, compliance]
sources:
  - _living/Whale-SpaceSight/SpaceSight-QA-List.md
  - _living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations.md
  - _living/Whale-SpaceSight/ReID-Pipeline-Architecture.md
  - _living/Whale-SpaceSight/Customer-Flow-Post-Processing.md
confidence: high
---

# SpaceSight

SpaceSight（历史简称包括 SDP、SS、SI / Space Intelligence、数智空间）是面向线下门店与展陈场景的视觉智能产品线。它基于真实相机画面做事件发现、目标检测、轨迹还原、行为分析、数据统计与结果查询，核心是把现场事实转化为可复核的结构化结果，而不是生成新的音视频内容。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

在当前 wiki 中，SpaceSight 不是一个单独算法，而是承载多个可复用工程主题的产品实体：底层依赖边缘盒子（搭载 [[edge-algo|Edge ALGO]]）完成视频拉流与极前置事件抽取，上游通过 [[trajex|TRAJEX]] 产生 ReID 特征，下游由 [[hidalgo|HIDALGO]] 与 [[customer-flow-post-processing]] 生成客流、接待和异常排查所需的业务事实。^[[[_living/Whale-SpaceSight/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 产品形态与指标边界

普通 IPC + AI Box 是当前多路标准门店及存量相机利旧场景的主要部署形态；将算力放进相机的 AI Camera 更适合新店、小店、外展店等路数较少的场景。客流产品则按相机承担的功能分为三种：出入口客流只包含出入口相机能力，纯店内客流只包含店内相机能力，全店客流是两类能力的组合。指标能否交付应由相机功能、机位与现场验证共同决定，不能只根据产品名称推断。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

标准出入口相机优先从店内向外拍，以保留正面属性与跨相机 ReID 特征，并减少相机下方盲区对过店统计的影响。开放式展台、柜台或快闪场景没有稳定出入口时，通常优先采用纯店内客流并接受进出边界精度下降；同一相机兼做出入口与店内分析只是受预算或施工条件约束时的非标折中，需要现场样片和 PoC 验证。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

新店同时要求客流、店内分析、视线检测和排队分析时，方案设计应先以视线检测作为相机选型门槛，因为它对算力、视角、画质和安装位置的约束最高；客流、店内分析和排队分析再分别校验覆盖范围与区域配置。相邻双门只有在同一稳定视野内、可以作为一个整体出入口定义时，才适合由单相机覆盖；若要独立统计两个门，仍应拆成独立机位或配置。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

SpaceSight 的自动画线是基于 SAM 系列分割模型的辅助配置能力，不是免人工复核的自动交付结果。门店平面图或货架变化时，应先判断相机位置、地面映射和实际位置关系是否变化；只有这些关系变化时才需要重新处理平面图映射，且替换平面图会清除原有店内配置。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

## 系统能力与职责边界

在当前实现中，SpaceSight Claw 提供自然语言事件搜索、视频回溯和数据指标生成；视觉大模型能力同时存在云端与端侧形态，其中端侧方案运行在 [[edge-sophon|32T SOPHGO 盒子]]上，以较低时延和本地推理换取弱于云端大模型的能力上限。此类能力仍属于对现场内容的识别与分析；自动剪辑、竖屏重构、字幕包装和内容分发等生成式视频工作流不属于 SpaceSight 的产品职责。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

AI 巡检和一键式洞察报告可以作为 SpaceSight 的上层应用形态评估，但不应被当作通用能力直接承诺。巡检成本随相机数、营业时长、巡检频率、运行天数、单次调用价格和检测项数量增长；洞察报告需要围绕目标指标和业务场景设计专用提示词或模板，并在交付前复核数据口径、分析边界和输出稳定性。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

短视频自动生成、AI 剪辑、内容重构、字幕包装和内容分发属于生成类业务，应转派 Alivia 产研团队评估；即使 Alivia 的平台定位高于这些任务，实际交付能力也需要通过产品试用和产研确认验证，不能由 SpaceSight 侧直接承诺。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

系统中存在顾客旅程和轨迹查看能力，但“能按测试照片核对轨迹”不等于可以把真实顾客检索作为标准产品能力承诺。涉及顾客照片、身份关联或个人轨迹时，应优先使用已授权测试人员做验收，并按客户所在地法规和项目要求完成隐私与合规评估。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

面向客户的多语言词条维护属于跨产品线口径管理：可通过 Adam 后台、native speaker 在线修改或离线表格批量导入来修订，但应由 PD 团队协调统一，避免单条产品线单独改动导致全产品语言口径不一致。^[[[_living/Whale-SpaceSight/SpaceSight-QA-List|SpaceSight-QA-List]]]

## 运维与方案边界

SpaceSight 相关工程问题通常分三类：

- **算力与部署成本**：私有化部署时，核心权衡是云端 GPU 推理与边缘端算力下沉；AI Hub 上的 ALGO 包型、路数和版本边界应按 [[how-to-size-spacesight-edge-algo-capacity|SpaceSight Edge ALGO 容量选型 SOP]] 逐路确认，相关硬件节点见 [[edge-sophon]] 与 [[edge-rk3576]]。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]
- **客流与 ReID 质量**：出入口人数偏差、店内替代出入口、全店客流口径等问题，本质上落在 [[reid-pipeline]] 与 [[customer-flow-post-processing]] 的分层边界上。
- **非标视觉场景**：开放展台、巡检、质检等场景需要先确认摄像机功能、视角、遮挡、实时性与可交付口径，不能直接把标准门店客流能力外推。

## 客流异常诊断入口

当客户提供的基准数与系统结果出现偏差时，[[diagnose-spacesight-traffic-count-mismatch|客流数据偏差验证与排查 SOP]] 先验证客户基准是否可信，再按原始事件、ReID 去重与业务过滤三层定位误差来源。开放展台、纯店内客流和单摄复用等方案边界属于 SpaceSight 产品配置，不另设 query 节点。
