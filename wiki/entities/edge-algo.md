---
title: Edge ALGO (边缘端算法服务)
created: 2026-07-02
updated: 2026-07-11
type: entity
tags: [edge-inference, computer-vision, pipeline]
sources: [_living/Whale-SpaceSight/Edge-Data-Collection-ALGO.md]
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

## 弱网缓存机制

由于线下门店网络可能存在波动，Edge ALGO 内置了**本地缓存续传**保障。当遇到弱网或断网情况时，算法会将抽取的轨迹特征和图片暂存于本地文件系统或 SQLite 中，并在后台监测网络连通性，待网络恢复后自动完成补传。此机制有效防止了弱网环境下的前端数据丢失。

## 场景复用

该算法底层代码库采用 C/C++ 与 CMake 构建，支持多平台编译。同时，通过读取不同的配置文件，同一套代码可分别打包用于**客流 (Customer Flow)** 或 **车行 (Vehicle Flow)** 场景。
