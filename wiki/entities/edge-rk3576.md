---
title: RK3576 Edge Device
created: 2026-05-14
updated: 2026-06-29
type: entity
tags: [edge-inference, rk3576, npu]
sources: [_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md]
confidence: high
---

# RK3576 Edge Device

瑞芯微（Rockchip）出品的边缘 AI 计算盒子，以自带 NPU 为核心，定位泛安防、智能家居、IPC 等视觉推理场景。

## 核心规格

| 维度      | 参数                                                        |
| --------- | ----------------------------------------------------------- |
| 厂商      | Rockchip（瑞芯微）                                          |
| CPU       | 八核 ARM（4×Cortex-A72 @2.2GHz + 4×Cortex-A53 @1.8GHz）     |
| AI 算力   | 6 TOPS (INT8)，支持 INT4/INT8/INT16/FP16/BF16/TF32 混合精度 |
| 内存/存储 | 4GB RAM + 32GB eMMC                                         |
| 特性      | 发热与功耗控制好，视频编解码能力强                          |

算力以 INT8 吞吐为主要衡量口径；NPU 利用率可经 `/sys/kernel/debug/rknpu/load` 实时查看。相比同系列 [[edge-sophon]] 的 TPU 盒子，RK3576 偏轻量视觉推理。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

**Related:**

- [[edge-sophon]]
