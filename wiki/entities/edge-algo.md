---
title: Edge ALGO (边缘端算法服务)
created: 2026-07-02
updated: 2026-08-05
type: entity
tags: [edge-inference, computer-vision, pipeline]
sources:
  - _living/Whale-SpaceSight/Edge-Data-Collection-ALGO.md
  - _living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations.md
confidence: high
---

# Edge ALGO (边缘端算法服务)

Edge ALGO 是部署在 [[edge-rk3576|RK3576]] 或 [[edge-sophon|Sophon 算能]] 等边缘计算盒子上的前置算法工程。它是整个 [[spacesight|SpaceSight]] 客流与 ReID 流水线的**最前端**。

## 职责边界

Edge ALGO 负责直接拉取门店相机的 RTSP 流，执行轻量级的目标检测与多目标追踪，并截取代表性事件。其输出是包裹好的**事件与图像序列包**，经由消息队列上传至云端的 [[trajex|TRAJEX 感知层服务]]。^[[[_living/Whale-SpaceSight/Edge-Data-Collection-ALGO|Edge-Data-Collection-ALGO]]]

具体能力：

- 提取出入口 (Entrance/Exit) 与空间驻留与关注 (Approach/Front/Passby) 轨迹事件，支持 AreaMap 与多边形虚拟线圈配置；
- 抓取轨迹图像与坐标时间戳序列，内置 `BlurImpl` 算子执行合规化人脸局部打码脱敏；
- 提取预估年龄、性别、是否戴口罩等基础属性，并在端侧结合轨迹向量判定“纯路过”等伪进店噪音。

## AI Hub 包型与容量口径

在 SpaceSight AI Hub 中，Edge ALGO 的业务负载至少要区分出入口版本、标准店内版本和视线店内版本：出入口版本支持脚部划线与头肩划线，标准店内版本默认包含可关闭的试乘试驾 / 试乘试坐能力，视线检测则使用独立的店内版本序列。不同版本序列的并发路数不能互相替换，端侧检测 + ReID 也属于不同于标准客流的研发负载。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

排队和看车不是 Edge ALGO 包型，而是下游 [[customer-flow-post-processing|Airflow 客流后处理]]消费端侧轨迹与区域数据后生成的业务逻辑；它们可以与店内或视线能力组成同一项目方案，但不应折算为盒子上的 ALGO 视频路数。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]

## 弱网缓存机制

由于线下门店网络可能存在波动，Edge ALGO 内置了**本地缓存续传**保障。当遇到弱网或断网情况时，算法会将抽取的轨迹特征和图片暂存于本地文件系统或 SQLite 中，并在后台监测网络连通性，待网络恢复后自动完成补传。此机制有效防止了弱网环境下的前端数据丢失。

## 场景复用

该算法底层代码库采用 C/C++ 与 CMake 构建，支持多平台编译。同时，通过读取不同的配置文件，同一套代码可分别打包用于**客流 (Customer Flow)** 或 **车行 (Vehicle Flow)** 场景。
