---
title: Edge AI Deployment Stack
created: 2026-07-15
updated: 2026-07-16
type: concept
tags: [edge-inference, edge-computing, architecture, pipeline]
sources: [_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon.md]
confidence: high
---

# Edge AI Deployment Stack

边缘 AI 部署栈是把训练模型变成可在 AI Box 上稳定运行的完整软硬件链路。AI Hub / AI Box 是整机，SoC（System on Chip，片上系统）只是其中一个计算层；芯片名称不能替代主板、BSP（Board Support Package，板级支持包）、Runtime（运行时）、模型产物和应用契约的资产信息。[[edge-rk3576|RK3576]] 与 [[edge-sophon|SOPHGO 边缘 SoC]]分别提供了 Rockchip NPU（Neural Processing Unit，神经网络处理器）和 SOPHGO TPU（Tensor Processing Unit，张量处理器）的平台实现。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 分层结构

| 层次             | 职责                                     | 交付时应记录的内容                      |
| ---------------- | ---------------------------------------- | --------------------------------------- |
| 整机             | 机箱、供电、散热、网口、内存和存储       | 整机 SKU、主板版本、BOM、散热与网络能力 |
| SoC / 加速器     | 提供 ARM CPU、NPU/TPU、视频和外设能力    | 芯片目标、标称精度与算力、视频能力      |
| BSP / OS         | 启动链、内核、设备树和板级驱动           | OS、内核、设备树、固件及厂商 BSP 版本   |
| 编译器 / Runtime | 转换模型并驱动加速器执行                 | 转换工具、Runtime、驱动和兼容矩阵       |
| 模型产物         | 保存目标芯片专用的量化与内存规划结果     | `.rknn`、`.bmodel`、校验值和目标芯片    |
| AI 应用          | 视频接入、预处理、推理、后处理和业务输出 | 输入契约、前后处理、资源预算与验收指标  |

这套分层避免把“使用 Linaro 用户”“设备树出现某 ASIC 字符串”或“芯片支持某接口”误当成整机身份和交付能力。资产盘点应分别记录整机、SoC、BSP、Runtime 和模型目标。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## SoC 盒子的内存模型

独立显卡服务器通常把 CPU 系统 DRAM（Dynamic Random-Access Memory，动态随机存取存储器）和 GPU VRAM（Video Random-Access Memory，显存）做成两套物理内存；`free -h` 只统计 Linux 系统内存。RK3576、CV186AH、BM1688 和 BM1684X 这类 SoC 盒子的标称内存则是 CPU、GPU、NPU / TPU 和视频模块共享的板载 DDR（Double Data Rate，双倍数据速率）物理总池。可以把它粗略理解成服务器的“CPU 内存 + GPU 显存”，但盒子没有把这两部分做成独立内存；系统会在同一个总池中划分以下软件用途：

- Linux `MemTotal`：普通进程、内核和缓存能够参与管理的范围，也是 `free -h total`。
- CMA（Contiguous Memory Allocator，连续内存分配器）：包含在 `MemTotal` 内，为需要连续物理页的设备服务，空闲时仍可承载可移动页面。
- 固定 `reserved-memory` / ION heap：可由 NPU、TPU、VPU（Video Processing Unit，视频处理单元）和 VPP（Video Post-Processing，视频后处理）使用；完全预切出的部分不进入 Linux 普通内存，因而不出现在 `free -h`。

所以算能 NPU heap 可以类比“逻辑显存池”，但它通常来自标称内存所代表的同一组板载 DRAM，而不是标称容量之外的另一组独立显存芯片。不能把 `free -h used` 与 ION `allocated` 机械相加，也不能把 `free -h total` 当作整机焊接的全部 DRAM。日常判断 Linux 应用余量优先看动态的 `MemAvailable`；盘点整机容量则要同时记录标称内存、启动日志、`MemTotal`、CMA 和各硬件预留池。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 模型编译与运行边界

典型部署链为：

```text
PyTorch / ONNX 等来源模型
        ↓  转换、校准、量化和目标芯片编译
Rockchip .rknn / SOPHGO .bmodel
        ↓  板端 Runtime 与驱动加载
      NPU / TPU 执行
```

Rockchip 通常使用 RKNN-Toolkit2 生成 `.rknn`，板端由 RKNN Runtime / RKNPU 执行；SOPHGO 通常使用 TPU-MLIR 生成目标芯片专用 `.bmodel`，板端由 TPU Runtime / libsophon 执行。来源网络相同不代表编译产物可跨芯片复用，模型包必须固定目标平台和工具链版本。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 视频 AI 数据路径

视频分析通常不是把压缩码流直接送入 NPU / TPU，而是由多个硬件模块协作：

```text
RTSP → VPU 解码 → VPP / RGA 预处理 → NPU / TPU 推理
     → ARM CPU 后处理、业务规则与结果上传
```

ISP 负责摄像头原始图像处理，VPU / JPU 负责视频或 JPEG 编解码，VPP / BMCV / RGA 负责 resize、crop 和色彩空间转换，加速器执行模型，CPU 负责任务编排和后处理。因此，峰值 TOPS 不能单独推导整机并发路数；视频解码、预处理吞吐、内存带宽、模型输入和后处理都可能成为瓶颈。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]

## 模型包最小契约

| 信息               | 作用                                          |
| ------------------ | --------------------------------------------- |
| 目标芯片           | 决定编译后端和 Runtime                        |
| 来源模型与版本     | 追溯权重与算子图                              |
| 编译工具与版本     | 固定转换、量化和兼容行为                      |
| 模型文件与校验值   | 识别目标专用产物并检查完整性                  |
| 精度与量化信息     | 记录校准集、量化方式和精度回归                |
| 输入契约           | 固定尺寸、布局、色彩顺序、归一化和 batch      |
| 前后处理           | 固定 resize、letterbox、NMS、坐标映射和类别表 |
| Runtime / 驱动要求 | 避免模型与板端软件栈不兼容                    |
| 资源预算           | 约束加速器内存、视频路数、延迟和温度          |

完整模型包将“模型文件”提升为可复现的部署契约。选型阶段还需要结合 [[rk3576-vs-sophon-edge-platforms|RK3576 与 SOPHGO 边缘平台对比]]，决定目标芯片、精度和资源档位。^[[[_living/Whale-SpaceSight/Edge-Compute-Boxes-RK3576-Sophon|Edge-Compute-Boxes-RK3576-Sophon]]]
