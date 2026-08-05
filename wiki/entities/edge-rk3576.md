---
title: RK3576 Edge Platform
created: 2026-05-14
updated: 2026-08-05
type: entity
tags: [edge-inference, rk3576, npu]
sources:
  - _living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md
  - _living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations.md
confidence: high
---

# RK3576 Edge Platform

RK3576 是 Rockchip（瑞芯微）的边缘 SoC，而不是完整 AI Box 的整机型号。实际交付设备还包含第三方主板、内存、存储、散热、网口和 BSP；这些整机配置不能仅凭 `RK3576` 芯片名推断。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 平台规格

| 维度         | 参数                                                                   |
| ------------ | ---------------------------------------------------------------------- |
| 芯片厂商     | Rockchip（瑞芯微）                                                     |
| CPU          | 八核 64 位 ARM：4× Cortex-A72 + 4× Cortex-A53                          |
| AI 加速      | 集成 NPU，官方标称 6 TOPS INT8                                         |
| 多媒体与外设 | 集成 GPU、显示、视频编解码、音频及 PCIe / USB / SATA / GMAC 等接口能力 |
| 软件栈       | RKNN-Toolkit2、RKNN-Toolkit-Lite2 / RKNN Runtime、RKNPU 驱动           |
| 模型产物     | 针对 RK3576 转换、量化和编译的 `.rknn`                                 |

RKNN 部署链通常在开发电脑上把训练模型转换、量化为 `.rknn`，再由板端 Runtime 通过 RKNPU 驱动执行。它是通用 [[edge-ai-deployment-stack|边缘 AI 部署栈]]在 Rockchip 平台上的一种实现；模型算子、输入布局、量化配置和 Toolkit/Runtime 兼容性必须在转换与验收阶段确认。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

RK3576 侧重在单颗 SoC 中整合通用计算、多媒体和中等规模 NPU 推理。与 CV186AH、BM1688、BM1684X 的能力边界及选型条件见 [[rk3576-vs-sophon-edge-platforms|RK3576 与 SOPHGO 边缘平台对比]]。具体盒子的主板、OS、驱动版本、频率、内存和运行状态属于实机信息，保留在来源 living 文档中，不视为所有 RK3576 产品的固定规格。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

在 SpaceSight AI Hub 的容量台账中，RK3576 的业务路数记录绑定到具体 [[edge-algo|Edge ALGO]] 融合测试边界：一条记录覆盖出入口 + 店内混合的全场景客流通道，另一条记录覆盖店内客流 + 车门试坐识别通道。这些记录证明的是指定构建、双 NPU 使用方式和测试场景下的稳定性，不能扩展成所有 RK3576 盒子的通用路数或任意端侧模型组合。^[[[_living/Whale-SpaceSight/AI-Hub-ALGO-Capacity-and-Combinations|AI-Hub-ALGO-Capacity-and-Combinations]]]
