---
title: SOPHGO Edge SoC Platforms
created: 2026-05-14
updated: 2026-07-15
type: entity
tags:
  - edge-inference
  - sophgo
  - tpu
sources:
  - _living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md
confidence: high
---

# SOPHGO Edge SoC Platforms

CV186AH、BM1688 与 BM1684X 是 SOPHGO（算能）生态中的边缘 SoC / TPU 平台，不等同于完整计算盒子的整机型号。市场上的 7.2T、16T、32T 盒子还包含主板、内存、存储、散热、网络接口和 BSP，整机厂商及配置需要按具体 SKU 核对。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 型号与规格

| 芯片平台                | CPU                        | 官方标称 AI 能力                                    | 官方视频侧能力                              | 平台定位                                  |
| ----------------------- | -------------------------- | --------------------------------------------------- | ------------------------------------------- | ----------------------------------------- |
| CV186AH（常见 7.2T 档） | 6× Cortex-A53              | 7.2 TOPS INT8，支持混合精度                         | 8 路高清视频智能分析；16 路解码、10 路编码  | 低功耗、8 路级视觉分析                    |
| BM1688（常见 16T 档）   | 8× Cortex-A53              | 16 TOPS INT8，支持混合精度                          | 16 路高清视频智能分析；16 路解码、10 路编码 | 16 路级视觉分析与中档边缘推理             |
| BM1684X（常见 32T 档）  | 8× Cortex-A53，最高 2.3GHz | 32 TOPS INT8 / 16 TFLOPS FP16、BF16 / 2 TFLOPS FP32 | 32 路高清视频智能分析；32 路解码、12 路编码 | 复杂模型、较高推理密度和部分边缘 LLM 场景 |

算能部署链通常使用 TPU-MLIR 将 PyTorch、ONNX 等来源模型编译为指定 `cv186ah`、`bm1688` 或 `bm1684x` 目标的 `.bmodel`，再由板端 TPU Runtime / libsophon 加载执行。它是通用 [[edge-ai-deployment-stack|边缘 AI 部署栈]]在 SOPHGO 平台上的实现；不同目标生成的 BModel 不应被假定为可直接互换。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

TPU-MLIR 源码表明内部目标 CV186X 与 BM1688 共用 BM1688 backend：CV186X 强制按单 TPU core 编译，BM1688 后端最多支持双 core。这支持“CV186AH 是同平台低档 SKU”的判断，但官方规格同时存在 6/8 个 CPU 核、7.2/16 TOPS 和 8/16 路视频分析等差异；公开资料不足以证明两者使用完全相同的物理 die、仅由软件或 eFuse 锁定，或可以安全解锁。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

各档位与 Rockchip RK3576 的工具链、精度、视频能力和适用场景差异见 [[rk3576-vs-sophon-edge-platforms|RK3576 与 SOPHGO 边缘平台对比]]。具体盒子的 OS、SDK、预留内存、温度和存储占用属于实机状态，保留在来源 living 文档中。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]
