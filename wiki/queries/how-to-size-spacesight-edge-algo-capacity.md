---
title: 如何为 SpaceSight Edge ALGO 做包型与容量选型
created: 2026-08-05
updated: 2026-08-05
type: query
tags: [spacesight, edge-inference, computer-vision, ops]
sources:
  - _living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations.md
  - _living/Whale-SpaceSight/Edge-Data-Collection-ALGO.md
  - _living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md
  - _living/Whale-SpaceSight/Customer-Flow-Post-Processing.md
confidence: high
---

# 如何为 SpaceSight Edge ALGO 做包型与容量选型

> **问题场景**：一个 SpaceSight 项目要把视频分析负载放到 AI Hub / AI Box 上，需要同时确认硬件盒子、ALGO 包型、相机路数、视线 / 试乘 / ReID 等叠加能力、NVR / IPC 接入方式和弱网边界。如何避免把厂商 TOPS、历史路数、云端业务逻辑或其他版本的测试结果误用成当前项目的交付承诺？

这个 SOP 的对象是 [[spacesight|SpaceSight]] 项目中运行在 AI Hub 上的 [[edge-algo|Edge ALGO]]。Edge ALGO 负责拉流、检测、跟踪、事件抽取、截图与上报；容量选型要围绕“这台盒子在这个 ALGO 序列和这组输入流下能稳定处理多少路”展开，而不是围绕“这颗芯片标称多少 TOPS”展开。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

## Step 1：先逐路列功能清单

先为每路相机写清楚它承担的端侧功能，再查容量记录：

- 出入口客流：标记脚部划线或头肩划线，但二者仍属于同一出入口版本序列；
- 标准店内客流：确认是否开启试乘试驾 / 试乘试坐能力；
- 视线检测：使用独立的视线店内版本序列，不能继承标准店内容量；
- 端侧 ReID、车门检测或其他专项模型：作为新的端侧负载处理，不能复用标准客流路数；
- 排队和看车：登记为云端业务依赖，不登记为端侧 ALGO 包型。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

排队和看车属于 [[customer-flow-post-processing|Airflow 客流后处理]]消费端侧轨迹与区域数据后的业务加工结果；这条关系说明它们依赖 Edge ALGO 的上游数据，但不说明它们运行在盒子上。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

## Step 2：用测试边界匹配硬件

[[edge-rk3576|RK3576]] 与 [[edge-sophon|SOPHGO CV186AH / BM1688 / BM1684X]] 是计算平台，不是完整交付能力。容量记录必须同时匹配 SoC、整机 SKU、OS / BSP、Runtime、ALGO 包版本、模型组合、输入码流、运行模式和长稳条件；任一条件变化，都应把旧记录降级为参考。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

厂商标称的视频分析路数、TOPS 或同总路数的其他组合，只能触发复核，不能直接产生交付路数。当前台账中，CV186AH 和 BM1688 有标准客流与视线版本记录，RK3576 有特定融合测试记录，BM1684X 尚无可承诺的固定容量矩阵；这些状态应回到 living 主台账查最新 `CAP-*` 记录，不在本 SOP 中复制维护。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

## Step 3：不要跨负载替换

以下替换都不成立：

- 用标准店内容量推断视线店内容量；
- 用标准客流容量推断端侧 ReID 容量；
- 用“相同总路数”插值出未测试的出入口 / 店内混合比例；
- 用新版本号覆盖旧测试记录，而没有同组合、同码流、同运行模式复测；
- 用 NVR / IPC 拓扑测试 PASS 替代 ALGO 容量 PASS；
- 用断网恢复 PASS 覆盖满载离线缓存压力。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

这些反模式本质上都是把 [[edge-ai-deployment-stack|边缘 AI 部署栈]]的一层局部事实外推成整条链路能力。真实容量由视频解码、预处理、模型推理、内存池、后处理、上传、温度和缓存共同决定。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## Step 4：验收时同时看业务正确性与资源余量

验收不应只看进程是否存活。至少要记录：

- 现场真实 IPC / NVR、编码、分辨率、FPS、码率、GOP 与取流路径；
- 每路输入 FPS、推理 FPS、事件计数、截图上传和数据补传；
- CPU、NPU / TPU、VPU / VPP / ION、普通内存、温度、磁盘和缓存积压；
- 峰值人数、遮挡、区域重叠、视线关注区域和试乘 / 车门等专项场景；
- 正常联网、短时断网恢复和预计离线缓存时长；
- 长稳测试中的丢帧、`reopen`、内存分配失败、服务重启和客流漏记。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

## 交付口径

对外承诺时只引用已经匹配的容量记录，并带上适用边界：硬件、ALGO 序列、版本、输入流、端侧功能组合、云端业务依赖、拓扑和联网模式。没有明确测试记录时，应写“未测试 / 待专项压测”，不要用估算值、厂商标称值或相邻组合补齐。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]
