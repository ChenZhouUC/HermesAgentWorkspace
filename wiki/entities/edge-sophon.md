---
title: Sophon (算能) Edge Devices
created: 2026-05-14
updated: 2026-06-29
type: entity
tags:
  - edge-inference
  - sophgo
  - tpu
sources:
  - _living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md
confidence: high
---

# Sophon (算能) Edge Devices

算能（SOPHGO）出品的边缘 TPU 计算盒子系列，定位智能视觉边缘网关与边缘端 LLM/多路视频分析。

## 型号与规格

| 型号                     | AI 算力                                                  | 内存/存储            | 定位                                |
| ------------------------ | -------------------------------------------------------- | -------------------- | ----------------------------------- |
| 7.2T（CV186AH / BM1688） | 7.2 TOPS (INT8)                                          | 4GB RAM + 32GB eMMC  | 高性价比，多路视频流并发 + 轻量推理 |
| 32T（BM1684X）           | 32 TOPS (INT8) / 16 TFLOPS (FP16/BF16) / 2 TFLOPS (FP32) | 16GB RAM + 64GB eMMC | 浮点算力完整，适合 LLM 边缘部署     |

CV186AH 基于 BM1688 架构衍生，设备树底层常仍标识为 `Sophon BM1688 ASIC`。TPU 利用率/温度/功耗经 `bm-smi`（类比 `nvidia-smi`）查看。相比瑞芯微 [[edge-rk3576]] 的 NPU 盒子，算能 32T 的完整浮点算力使其更适合承载边缘大模型。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

**Related:**

- [[edge-rk3576]]
