---
title: Edge Compute Boxes RK3576 Sophon
created: 2026-05-14
updated: 2026-07-16
---

# AI 边缘计算盒子：RK3576 与算能系列

本文记录三台内网边缘计算盒子的登录方式、硬件与系统参数、AI Hub 平台背景知识、已实测巡检命令，以及 2026-07-15 的只读审计结果。

> [!note]
> 初次实机审计时间为 2026-07-15 约 21:00（Asia/Shanghai）；内存口径于 2026-07-16 只读复核。温度、负载、利用率、当前可用内存和剩余空间会随运行状态变化。芯片算力和视频能力为厂商标称值；主板、系统、内存、分区、频率和运行状态为实机值。

## 1. 口径与术语

### 1.1 服务器的内存/显存与盒子的内存有什么不同

> [!tip] 一句话理解
> **本文这些盒子的“标称内存”，本质上是整颗 SoC 可共同使用的板载总物理内存。** 可以先粗略理解为“CPU 内存 + GPU 显存”，但更完整的说法还要包括 NPU / TPU 和视频模块使用的内存；它不是几块独立内存相加，而是 CPU、GPU、NPU / TPU、VPU / VPP 等模块共享同一组 DDR，再由系统划分用途。

带独立显卡的传统服务器通常有两套物理内存：

- 系统内存：主板上的 DRAM（Dynamic Random-Access Memory，动态随机存取存储器），主要由 CPU（Central Processing Unit，中央处理器）和操作系统管理；`free -h` 查看的是这一侧。
- 独立显存：显卡上的 VRAM（Video Random-Access Memory，视频随机存取存储器），主要由 GPU（Graphics Processing Unit，图形处理器）使用；通常由显卡厂商工具查看，不计入 `free -h`。
- CPU 与独立 GPU 之间通常需要通过 PCIe（Peripheral Component Interconnect Express，高速串行计算机扩展总线）和 DMA（Direct Memory Access，直接内存访问）搬运或映射数据。

本文三台盒子采用 SoC（System on Chip，片上系统）：CPU、NPU（Neural Processing Unit，神经网络处理器）/ TPU（Tensor Processing Unit，张量处理器）、GPU 和视频模块集成在同一平台上，物理上主要使用板载的同一组 DDR（Double Data Rate，双倍数据速率）内存，而不是再给加速器焊一组独立 GDDR 显存。因此，盒子标称 4 GB 或 16 GB 时，说的是这组**共享总池**的容量，不是“CPU 独占 4/16 GB，另外再送一份 GPU/NPU 显存”。**物理内存统一，不代表软件上所有容量都能由 CPU 进程自由使用。** 启动时仍会把同一组 DRAM 划成不同用途：

```text
标称 DRAM：CPU + GPU + NPU/TPU + 视频模块共享的物理总池
├── 固件、启动链、设备寄存器映射等系统预留
├── NPU / TPU / VPU / VPP 等固定硬件池（部分平台存在）
└── Linux MemTotal（也就是 free -h 的 total）
    ├── 普通 Linux 页面：进程、内核、文件缓存等
    └── CMA 连续内存区：仍在 Linux 管理范围内，按需借给设备
```

因此，算能盒子的 NPU heap 可以类比“逻辑上的加速器显存池”，但它通常仍来自同一组板载 DRAM，不是独立显存芯片。本文实机中，RK3576 没有观察到像算能盒子那样巨大的固定 NPU heap；两台算能盒子则为 NPU、VPP 和 VPU 提前切出了较大的专用区域。

ION 是 Android/Linux 多媒体内存分配器的名称，不是另一种物理内存，也没有需要强行展开的通行英文全称。一个 ION heap 可以基于固定 carveout（预切区域）或 CMA 等底层内存建立；是否计入 `MemTotal` 要看该 heap 的具体实现和设备树配置。

### 1.2 为什么 `free -h` 小于标称内存

要区分三层容量：

1. **标称容量**：采购或整机规格中的 4 GB、16 GB，描述 CPU、GPU、NPU / TPU 和视频模块共享的板载物理内存总档位，不是 CPU 可独占的容量。
2. **Linux 可管理容量**：`/proc/meminfo` 的 `MemTotal`，也是 `free -h` 的 `total`。它已经扣除了 Linux 普通页分配器无法使用的固件和固定硬件预留，但包含 CMA。
3. **当前可分配容量**：`MemAvailable`，也是 `free -h` 的 `available`。它会随进程和缓存变化，是判断“现在还能启动多大应用”更有用的字段。

`free -h` 的常见列含义如下：

| 列           | 含义                                     | 阅读方式                                                                                                                                                            |
| ------------ | ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `total`      | Linux `MemTotal`                         | 不是整机标称 DRAM，也不包含完全排除在 Linux 普通内存之外的硬件池                                                                                                    |
| `used`       | 由 `free` 根据其他字段计算的派生值       | 新版常按 `total - available`，两台旧版算能实机按 `total - free - buff/cache`；不要跨版本硬套公式，也不要当作所有进程 RSS（Resident Set Size，常驻内存集）的简单求和 |
| `free`       | 当前完全未使用的页面                     | Linux 会主动把空闲内存用于缓存，所以该值低不一定有问题                                                                                                              |
| `buff/cache` | 块设备缓冲和文件页缓存等                 | 很多页面在应用需要时可回收                                                                                                                                          |
| `available`  | 内核估计无需 swap 即可供新应用使用的容量 | 日常判断内存余量时优先看这一列                                                                                                                                      |
| `swap`       | Swap Space，交换空间                     | 本文三台实机均为 0；内存压力下没有磁盘交换缓冲                                                                                                                      |

CMA（Contiguous Memory Allocator，连续内存分配器）为需要连续物理页的设备准备内存。它由 Linux 管理，空闲 CMA 页面在满足迁移条件时仍可被普通可移动页面利用；因此本文把 `CmaTotal` 标成“包含在 `MemTotal` 中”，不再将其和固定 `reserved-memory` 重复相加。设备树中的 `reserved-memory` 则可能完全不进入 Linux 普通页分配器，NPU / TPU、视频和固件常从这里获得固定池。

单位也会造成视觉差异：`GB` / `MB` 是十进制单位，`GiB`（gibibyte，吉比字节）/ `MiB`（mebibyte，兆比字节）是二进制单位，`1 GiB = 1024 MiB = 2^30 bytes`。`free -h` 会自动选择二进制量级并四舍五入，例如精确的 1.151 GiB 会显示成约 1.2 GiB。判断差额时应读取 `/proc/meminfo` 的精确 KiB（kibibyte，千比字节）值，而不是反向计算表格中的一位小数。

### 1.3 三台实机的内存如何对账

以下 `MemTotal` 和 CMA 数字于 2026-07-16 复核；当前 `MemAvailable` 会动态变化，不放入固定对账表。

| 设备      | 标称内存 | 内核启动口径总量             | Linux `MemTotal` / `free -h total`                 | Linux 之外的主要固定用途                                               | CMA（已包含在 `MemTotal`） |
| --------- | -------- | ---------------------------- | -------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------- |
| RK3576    | 4 GB 档  | 4,175,872 KiB，约 3.98 GiB   | 3,990,508 KiB，约 3.81 GiB；`free -h` 显示 3.8 GiB | 约 181 MiB 的总量差额来自启动期和设备预留；未观察到巨大的固定 NPU heap | 48 MiB                     |
| 算能 7.2T | 4 GB 档  | 3,670,016 KiB，约 3.50 GiB   | 1,206,904 KiB，约 1.15 GiB；`free -h` 显示 1.2 GiB | NPU 768 MiB + VPP 1.5 GiB，另有固件和其他预留                          | 124 MiB                    |
| 算能 32T  | 16 GB 档 | 16,055,040 KiB，约 15.31 GiB | 6,427,708 KiB，约 6.13 GiB；`free -h` 显示 6.1 GiB | NPU 约 3.86 GiB + VPP 3 GiB + VPU 2 GiB，另有固件和其他预留            | 128 MiB                    |

所以“32T 标称 16 GB，但 `free -h` 只有 6.1 GiB”并不表示约 10 GB 被普通进程吃掉，也不等于内存条损坏；大部分差额在启动阶段已经划给 TPU/NPU 和视频模块，Linux 普通进程从一开始就看不到。反过来，`bm-smi` 或 ION debugfs 中的 `allocated` 表示专用池内部当前已经分出去的部分，不能再和 `free -h used` 相加后称为整机总使用量，否则容易重复或混合不同口径。

### 1.4 英文简称速查

| 简称                      | 英文全称或官方名称                                                                      | 中文和本文语境                                                                  |
| ------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| AI                        | Artificial Intelligence                                                                 | 人工智能                                                                        |
| Arm / AArch64             | Arm architecture / AArch64 execution state                                              | Arm 是处理器架构与品牌名；AArch64 是 Arm 架构的 64 位执行状态，不建议按字母硬拆 |
| SoC                       | System on Chip                                                                          | 片上系统，把 CPU、加速器和多媒体/外设控制器集成到一个芯片平台                   |
| CPU / GPU                 | Central Processing Unit / Graphics Processing Unit                                      | 中央处理器 / 图形处理器                                                         |
| NPU / TPU                 | Neural Processing Unit / Tensor Processing Unit                                         | 神经网络处理器 / 张量处理器                                                     |
| RAM / DRAM / VRAM         | Random-Access Memory / Dynamic RAM / Video RAM                                          | 随机存取存储器 / 动态内存 / 显存                                                |
| DDR / GDDR                | Double Data Rate / Graphics Double Data Rate                                            | 常见系统内存接口 / 面向图形和加速器的内存接口                                   |
| KiB / MiB / GiB           | kibibyte / mebibyte / gibibyte                                                          | 二进制容量单位，分别为 2^10 / 2^20 / 2^30 bytes                                 |
| ASIC                      | Application-Specific Integrated Circuit                                                 | 专用集成电路；设备树中的 `ASIC` 是芯片实现类型，不是整机型号                    |
| CMA / DMA                 | Contiguous Memory Allocator / Direct Memory Access                                      | 连续内存分配器 / 直接内存访问                                                   |
| ION                       | ION memory allocator                                                                    | Android/Linux 多媒体内存分配器的官方名称，没有通行的逐字母全称                  |
| ISP                       | Image Signal Processor                                                                  | 图像信号处理器，处理摄像头 sensor 原始图像                                      |
| VPU / JPU                 | Video Processing Unit / JPEG Processing Unit                                            | 视频处理单元 / JPEG 处理单元                                                    |
| VPP                       | Video Post-Processing                                                                   | 视频后处理，常做缩放、裁剪和色彩空间转换                                        |
| RGA                       | Raster Graphic Acceleration Unit                                                        | Rockchip 的二维图形加速单元                                                     |
| BMCV                      | BMCV library                                                                            | 算能计算机视觉加速库的官方名称，没有稳定的逐字母展开                            |
| OS / BSP                  | Operating System / Board Support Package                                                | 操作系统 / 板级支持包                                                           |
| SDK / API                 | Software Development Kit / Application Programming Interface                            | 软件开发工具包 / 应用程序编程接口                                               |
| RKNN / RKNPU              | Rockchip Neural Network / Rockchip Neural Processing Unit                               | Rockchip 模型格式与部署工具链 / NPU 硬件及驱动体系                              |
| MLIR                      | Multi-Level Intermediate Representation                                                 | 多层中间表示；TPU-MLIR 基于它完成模型编译                                       |
| ONNX                      | Open Neural Network Exchange                                                            | 开放神经网络交换格式                                                            |
| RTSP / NVR                | Real-Time Streaming Protocol / Network Video Recorder                                   | 实时流协议 / 网络视频录像机                                                     |
| PCIe / USB / SATA         | Peripheral Component Interconnect Express / Universal Serial Bus / Serial ATA           | 高速扩展总线 / 通用串行总线 / 存储设备接口                                      |
| GMAC                      | Gigabit Media Access Controller                                                         | 千兆以太网媒体访问控制器                                                        |
| eMMC                      | embedded MultiMediaCard                                                                 | 嵌入式闪存存储；它是磁盘，不是运行内存                                          |
| SSH / TCP                 | Secure Shell / Transmission Control Protocol                                            | 安全远程登录协议 / 传输控制协议                                                 |
| SKU / BOM                 | Stock Keeping Unit / Bill of Materials                                                  | 库存量单位（具体可售配置）/ 物料清单                                            |
| TOPS / TFLOPS             | Tera Operations Per Second / Tera Floating-Point Operations Per Second                  | 每秒万亿次操作 / 每秒万亿次浮点操作                                             |
| INT8 / FP16 / BF16 / FP32 | 8-bit Integer / 16-bit Floating Point / Brain Floating Point 16 / 32-bit Floating Point | 常见整数或浮点数据精度                                                          |
| RSS                       | Resident Set Size                                                                       | 进程当前驻留在物理内存中的页面总量                                              |
| NCHW / NHWC               | Number, Channel, Height, Width / Number, Height, Width, Channel                         | 神经网络张量的两种常见维度排列                                                  |
| RGB / BGR                 | Red, Green, Blue / Blue, Green, Red                                                     | 图像颜色通道顺序                                                                |
| NMS                       | Non-Maximum Suppression                                                                 | 非极大值抑制，目标检测常见后处理                                                |
| LLM / VLM                 | Large Language Model / Vision-Language Model                                            | 大语言模型 / 视觉语言模型                                                       |

`CV186AH`、`BM1688`、`BM1684X`、`RK3576` 和 Cortex-A53 / A72 是产品或核心型号，不是需要逐字母展开的通用术语；Linaro、SOPHGO、CVITEK 也是组织或品牌名。

### 1.5 其他容易混淆的口径

- TOPS（Tera Operations Per Second，每秒万亿次操作）：本文中的 6T、7.2T、16T、32T 均指对应芯片的标称 INT8 峰值算力。
- OverlayFS（Overlay Filesystem，叠加文件系统）：算能盒子的 `/` 使用 overlay，`df -hT` 中 `/media/root-ro`、`/media/root-rw` 和 `/` 不是三份独立存储，判断可写空间时以 overlay `/`、`/data` 和底层块设备为主。
- CV186AH / BM1688:7.2T 实机的 `bm-smi` 标识为 `CV186AH-SOC`，设备树 `model` 却返回 `Sophon. BM1688 ASIC. ARM64.`。这是同一台设备在不同固件接口中的识别差异，不应仅凭其中一个字符串推断成另一款芯片。

## 2. 登录信息

| 设备      | 地址             | 用户名   | 密码       | 2026-07-15 已验证访问路径 |
| --------- | ---------------- | -------- | ---------- | ------------------------- |
| RK3576    | `10.108.30.82`   | `whale`  | `Whale12!` | 经 32T 盒子跳转登录成功   |
| 算能 7.2T | `10.108.30.177`  | `whale`  | `Whale12!` | 经 32T 盒子跳转登录成功   |
| 算能 32T  | `192.168.110.79` | `linaro` | `linaro`   | 当前工作站直连登录成功    |

当前工作站到两个 `10.108.30.x` 地址的 TCP/22 可建立连接，但 SSH 在交换服务端 banner 前被中间网络关闭；从 32T 盒子转发后登录正常。因此当前已验证的登录命令如下：

```bash
# 32T：直连
ssh linaro@192.168.110.79

# RK3576：经 32T 跳板
ssh -J linaro@192.168.110.79 whale@10.108.30.82

# 7.2T：经 32T 跳板
ssh -J linaro@192.168.110.79 whale@10.108.30.177
```

使用 `-J` 时，首次连接可能依次询问 32T 跳板密码 `linaro` 和目标盒子密码 `Whale12!`。若工作站已位于能直接访问 `10.108.30.0/24` 的内网，可再尝试不带 `-J` 的直连方式；本轮当前网络路径下未验证直连成功。

以上凭据仅适合保留在本地、仅内网访问的私有 wiki 中，不应复制到公开仓库、公开工单或对外文档。

## 3. 实机参数

### 3.1 RK3576 盒子

| 维度            | 实机参数                                                                                                                |
| --------------- | ----------------------------------------------------------------------------------------------------------------------- |
| 主机 / 主板     | hostname `linaro-alip`；`Hugsun RK3576 EDGE V10 Board`                                                                  |
| OS / 内核       | Debian 12 (bookworm)；Linux `6.1.99`，构建日期 2025-04-17                                                               |
| CPU             | AArch64 八核：4× Cortex-A53，最高 2.016 GHz；4× Cortex-A72，最高 2.208 GHz；`ondemand` governor                         |
| AI 加速         | RK3576 NPU，厂商标称 6 TOPS INT8；实机 RKNPU 驱动 `0.9.8`；双 NPU core 负载接口                                         |
| NPU 频率        | 300–950 MHz，`rknpu_ondemand` governor；采样时 950 MHz                                                                  |
| 内存            | 标称 4 GB 档；`MemTotal` 3,990,508 KiB（约 3.81 GiB），`free -h` 显示 3.8 GiB；CMA 48 MiB，已包含在 `MemTotal`；无 swap |
| 存储            | 32 GB eMMC，`lsblk` 实际 29.1 GiB；`/` 14 GiB，使用 83%；`/userdata` 14.8 GiB，使用 69%；`/oem` 128 MiB                 |
| 网络接口        | `end0`：`10.108.30.82/24`，UP；`end1` DOWN；`wlan0` / `wlan1` DORMANT                                                   |
| 温度 / 负载快照 | SoC / CPU / DDR / NPU / GPU 约 36–38°C；NPU Core0 约 21–26%，Core1 0%                                                   |
| 主要能力        | 官方标称支持多种高速接口、三路异显、8K30 解码和 4K60 H.264 能力，适合边缘视觉推理与多媒体处理                           |

### 3.2 算能 7.2T 盒子

| 维度            | 实机参数                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 主机 / 芯片识别 | hostname `sophon`；设备树为 `Sophon. BM1688 ASIC. ARM64.`；`bm-smi` 为 `CV186AH-SOC`                                     |
| OS / 内核       | Ubuntu 20.04 LTS；Linux `5.10.4-tag-`，构建日期 2024-08-01                                                               |
| CPU             | AArch64，6× Cortex-A53；实机 `lscpu` 未提供可核实的 CPU 频率                                                             |
| AI 加速         | CV186AH，厂商标称 7.2 TOPS INT8；支持 INT4 / INT8 / FP16 / BF16 / FP32 混合精度                                          |
| 视频能力        | 厂商标称 8 路高清视频智能分析；16×1080P@30 H.264/H.265 硬解码；10×1080P@30 硬编码；JPEG 1080P 编解码各 480 fps           |
| 内存            | 标称 4 GB 档；`MemTotal` 1,206,904 KiB（约 1.15 GiB），`free -h` 显示 1.2 GiB；CMA 124 MiB，已包含在 `MemTotal`；无 swap |
| 硬件预留池      | NPU 768 MiB，采样时约 149.5 MiB allocated；VPP 1.5 GiB，采样时约 387.7 MiB allocated                                     |
| 存储            | 32 GB eMMC，实际 29.1 GiB；overlay `/` 8.7 GiB，使用 60%；`/data` 16.8 GiB，使用 64%                                     |
| 网络接口        | `eth0`：`10.108.30.177/24`，1 Gbps / Full Duplex / Link Up；`eth1` DOWN                                                  |
| SDK / 驱动      | `/opt/sophon/libsophon-0.4.9`；SDK / Driver `0.4.9`                                                                      |
| 温度 / 负载快照 | SoC 约 48.9°C；`bm-smi` 显示 TPU Active、采样时 900 MHz；load average 约 6.1–6.3（6 核）                                 |

### 3.3 算能 32T 盒子

| 维度            | 实机参数                                                                                                                    |
| --------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 主机 / 芯片识别 | hostname `bm1684`；`bm-smi` 为 `1684X-SOC`；该固件无可用的 `/proc/device-tree/model`                                        |
| OS / 内核       | Ubuntu 20.04 LTS；Linux `5.4.217-bm1684-g3d94d8648f81`，构建日期 2024-04-03                                                 |
| CPU             | AArch64，8× Cortex-A53，1.15–2.30 GHz；8 核均为 `performance` governor                                                      |
| AI 加速         | BM1684X，厂商标称 32 TOPS INT8 / 16 TFLOPS FP16、BF16 / 2 TFLOPS FP32                                                       |
| 视频能力        | 厂商标称 32 路高清视频智能分析；32 路高清硬解码；12 路高清硬编码                                                            |
| 内存            | 标称 16 GB 档；`MemTotal` 6,427,708 KiB（约 6.13 GiB），`free -h` 显示 6.1 GiB；CMA 128 MiB，已包含在 `MemTotal`；无 swap   |
| 硬件预留池      | NPU 约 3.86 GiB，采样时 100% allocated；VPP 3 GiB，约 627.5 MiB allocated；VPU 2 GiB，约 229.9 MiB allocated                |
| 存储            | 64 GB eMMC，实际 58.3 GiB；overlay `/` 16 GiB，使用 59%；`/data` 34.6 GiB，使用 99%，仅余约 353 MiB；`/opt` 2 GiB，使用 16% |
| 网络接口        | `eth0`：`192.168.110.79/24`，1 Gbps / Full Duplex / Link Up；`eth1` / `wlan0` DOWN                                          |
| SDK / 驱动      | `/opt/sophon/libsophon-0.4.9`；Lib / Driver `0.4.9 LTS`                                                                     |
| 温度 / 负载快照 | SoC 约 81°C，Board 约 60°C；内核 thermal cooling 状态持续切换；`bm-smi` 采样时 TPU Active、约 712 MHz                       |

## 4. AI Hub 平台与芯片背景知识（非实测）

本节来自厂商和开源项目的公开资料，用于解释 AI Hub 的技术栈，不是对上述三台盒子的实时采样。型号的标称能力应与第 3 节的实机配置、固件版本和运行状态分开理解。

### 4.1 AI Hub / AI Box 不等于某一颗芯片

在本文语境中，AI Hub 或 AI Box 指可交付的完整边缘设备；RK3576、CV186AH、BM1688、BM1684X 只是其中的计算 SoC。一个可运行算法的 AI Hub 通常包含以下层次：

| 层次           | 作用                                       | 本文中的例子                                  |
| -------------- | ------------------------------------------ | --------------------------------------------- |
| 产品 / 整机    | 机箱、供电、散热、网口、存储和交付形态     | RK3576、7.2T、32T 三台盒子                    |
| 主板 / SoC     | 提供 ARM CPU、AI 加速器、视频与外设能力    | RK3576、CV186AH、BM1688、BM1684X              |
| BSP / OS       | Linux 内核、设备树、启动链和板级驱动       | Debian / Ubuntu、厂商内核与设备树             |
| 驱动 / Runtime | 管理 NPU / TPU 并向应用提供推理 API        | RKNPU / RKNN Runtime、libsophon / TPU Runtime |
| 模型产物       | 针对目标芯片编译、量化后的可执行模型       | Rockchip `.rknn`、SOPHGO `.bmodel`            |
| AI 应用        | 视频接入、解码、预处理、推理、后处理和上传 | 检测、跟踪、ReID、属性识别等业务算法          |

因此，“这台盒子是 Linaro”“这台盒子是 BM1688 系统”之类说法通常不够精确。资产盘点至少要同时记录整机型号、SoC、OS/BSP、驱动/Runtime 和模型目标平台。

### 4.2 Linaro 是什么

Linaro 是面向 Arm 技术的软件工程组织和协作社区，自 2010 年起参与 Arm 生态中的开源软件协作、标准化和优化。它不是芯片型号，也不是 Rockchip 或 SOPHGO 的替代品牌。

在 ARM 盒子上看到 `linaro`，常见含义有三种：

- Linux 镜像制作者沿用了历史开发镜像的默认用户名，例如 `linaro`。
- BSP 或 SDK 使用了 Linaro 维护或发布的 AArch64 交叉编译工具链，工具链目录中会出现 `gcc-linaro-*`。
- hostname、用户 home 目录或构建信息保留了厂商开发阶段的命名。

这些名称只能说明软件镜像或工具链的来源线索，不能据此判断底层是 RK3576、CV186AH、BM1688 还是 BM1684X。本轮实机也印证了这一点：RK3576 的 hostname 是 `linaro-alip`，32T 的登录用户是 `linaro`，但两者的芯片平台完全不同。

### 4.3 RK3576、RKNPU 与 RKNN

RK3576 是 Rockchip 的通用型边缘 SoC，不只是一颗 NPU。官方产品页将它描述为八核 64 位 ARM 处理器，并集成 GPU、6 TOPS NPU、显示、视频编解码、音频和 PCIe / USB / SATA / GMAC 等外设能力。对 AI Hub 来说，它的优势是把通用计算、视频处理和中等规模 AI 推理集成在一颗 SoC 中。

几个容易混淆的名称：

- RKNPU：Rockchip NPU 硬件及其内核驱动体系；内核驱动负责与 NPU 硬件交互。
- RKNN：Rockchip Neural Network，既指 `.rknn` 模型格式，也常泛指模型转换和部署工具链。
- RKNN-Toolkit2：运行在开发电脑上的模型转换、推理验证和性能评估 SDK。
- RKNN-Toolkit-Lite2 / RKNN Runtime：运行在板端的 Python 或 C/C++ 推理接口。

典型部署链如下：

```text
PyTorch / ONNX 等训练模型
        ↓  在开发电脑上使用 RKNN-Toolkit2 转换、量化和验证
      .rknn
        ↓  在 RK3576 上由 RKNN-Toolkit-Lite2 或 RKNN Runtime 加载
   RKNPU 内核驱动
        ↓
      NPU 执行
```

这意味着把原始 ONNX 文件复制到 RK3576 并不等于已经完成 NPU 部署；模型算子、输入布局、量化方式和 Toolkit/Runtime 兼容性都需要在转换阶段确认。

### 4.4 CV186AH、BM1688 与 BM1684X 分别是什么

三者都出现在 SOPHGO 官网和 TPU-MLIR 目标平台列表中，但产品定位和能力档位不同。

| 芯片    | 官方定位                                               | CPU / 标称 AI 能力                                                          | 官方视频侧能力                                        | 适合的 AI Hub 档位                           |
| ------- | ------------------------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------- |
| CV186AH | 高集成智能视觉深度学习处理器，官网页面使用 CVITEK 品牌 | 6× Cortex-A53；7.2 TOPS INT8；支持混合精度                                  | 8 路高清视频智能分析；16 路解码、10 路编码；集成 ISP  | 低功耗、8 路级视觉分析盒子                   |
| BM1688  | 面向深度学习推理和计算机视觉的高集成边缘 TPU 处理器    | 8× Cortex-A53；16 TOPS INT8；支持混合精度                                   | 16 路高清视频智能分析；16 路解码、10 路编码；集成 ISP | 16 路级视觉分析及更高算力的边缘盒子          |
| BM1684X | 第四代张量处理器，强调更高推理密度和完整浮点精度       | 8× Cortex-A53 @ 2.3GHz；32 TOPS INT8 / 16 TFLOPS FP16、BF16 / 2 TFLOPS FP32 | 32 路高清视频智能分析；32 路解码、12 路编码           | 32 路级视频分析、复杂模型和部分边缘 LLM 场景 |

CV186AH 与 BM1688 不是同一个商品型号：公开规格中，前者为 6 核 / 7.2 TOPS / 8 路分析，后者为 8 核 / 16 TOPS / 16 路分析。两者拥有相近的视频编解码数量和工具链生态，可能导致 BSP、设备树或驱动字符串看起来相似，但不能据此认为模型、固件或性能预算可以无条件互换。

BM1684X 则是更高一档的张量处理器。它不仅 INT8 峰值更高，也保留 FP16 / BF16 / FP32 能力，因此更适合对模型精度、算子覆盖或模型规模要求较高的场景；代价通常是更高的内存、功耗和散热需求。

#### 7.2T 与 16T 是否“只是锁算力”

更准确的说法是：**CV186AH 与 BM1688 高度共享 TPU 架构和软件平台，CV186AH 很可能是同平台的低档 SKU；但“只有算力被软件锁住、其他完全相同”并不成立，“同一颗裸片通过 eFuse 或软件即可解锁”也没有公开证据。**

| 判断                                       | 结论               | 公开证据与边界                                                                                                                                                              |
| ------------------------------------------ | ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 两者共享 TPU 架构和编译后端                | 已坐实             | SOPHGO 的 TPU-MLIR 将内部目标 `CV186X`（CV186AH 所属目标族）归入 BM1688 family；两者实例化同一个 BM1688 backend，并使用同一个 PPL BM1688 后端                               |
| 7.2T 相比 16T 存在 TPU 核数/生成策略限制   | 已坐实到编译器层面 | TPU-MLIR 对 `cv186x` 强制按 1 个 TPU core 编译，而 BM1688 后端声明最多 2 个 core；这比“单纯降频”更符合公开代码                                                              |
| 两者只差 TPU 算力                          | 不成立             | 官方规格还存在 6 核与 8 核 Cortex-A53、8 路与 16 路视频分析，以及公开内存类型支持描述等差异                                                                                 |
| 7.2T 只是锁频                              | 无证据支持         | 当前 TPU-MLIR 架构参数对 BM1688 与 CV186X 都使用 900MHz；本机 7.2T 的 `bm-smi` 也采到 900MHz。该数值不能单独证明实际所有运行档位完全一致，但不支持“仅靠降频得到 7.2T”的说法 |
| 两者是完全相同的物理 die，可通过改固件解锁 | 未坐实             | 官方没有公开 die、eFuse、良率分档或解锁机制；公开代码只能证明软件架构关系，不能证明物理芯片完全相同或存在安全的解锁路径                                                     |

本机 7.2T 的 `bm-smi` 返回 `CV186AH-SOC`，设备树却返回 `Sophon. BM1688 ASIC. ARM64.`，进一步说明二者共享平台血缘；但设备树字符串可能来自共用 BSP，不能作为“同 die”或“可解锁”的证明。7.2 与 16 TOPS 也并非严格的 1:2，因此不能只根据单核/双核关系反推峰值。

资产和模型管理时仍应把 CV186AH 与 BM1688 当作不同目标；不要通过修改设备树、固件或运行时参数尝试“解锁”。低档 SKU 可能同时涉及硬件熔丝、良率分档、功耗和散热验证或厂商授权，错误配置可能造成推理结果异常、系统不稳定或硬件损伤。

### 4.5 SOPHGO 软件栈：TPU-MLIR、BModel 与 libsophon

- TPU-MLIR：基于 MLIR 的模型编译器，把 PyTorch、ONNX、TFLite、Caffe、Hugging Face 等来源模型转换、量化并编译为 `.bmodel`。编译时必须指定目标芯片，例如 `cv186ah`、`bm1688` 或 `bm1684x`。
- BModel：SOPHGO TPU 的编译后模型产物。它包含针对目标芯片完成的 lowering、量化和内存规划；即使网络结构相同，也不应假定为一个芯片生成的 BModel 能直接在另一芯片上运行。
- libsophon：算能芯片的底层驱动与运行时集合，包含 TPU / VPU / JPU / VPP 驱动、`bmlib`、TPU Runtime、BMCV 和辅助工具。
- `bm-smi`：libsophon 中的状态查看工具，用于观察芯片、频率和进程等信息；它不是模型编译器，也不是业务推理 API。

典型部署链如下：

```text
PyTorch / ONNX / TFLite / Caffe / Hugging Face 模型
        ↓  在开发环境使用 TPU-MLIR 转换、校准、量化和编译
  目标芯片专用 .bmodel
        ↓  在盒子上由 TPU Runtime / libsophon 加载
   SOPHGO 内核驱动
        ↓
      TPU 执行
```

### 4.6 视频模块和 AI 加速器如何配合

边缘视频 AI 一般不是把压缩视频直接送入 NPU / TPU，而是多个硬件模块协作：

- ISP：处理摄像头 sensor 的原始图像，包括曝光、白平衡、降噪和宽动态。如果 AI Hub 只从 NVR 读取已经编码的 RTSP 视频，通常不会直接使用 SoC 的 sensor ISP 链路。
- VPU / JPU：负责 H.264 / H.265 视频或 JPEG 图片的硬件编解码。
- VPP / BMCV / RGA：负责 resize、crop、色彩空间转换、padding 等图像预处理；Rockchip 常见 RGA，SOPHGO 常见 VPP/BMCV。
- NPU / TPU：执行检测、特征提取、分类、分割等神经网络推理。
- ARM CPU：负责协议接入、任务编排、轻量前后处理、业务规则、缓存和网络上传。

一个典型的 AI Hub 数据路径是：`RTSP → VPU 解码 → VPP/RGA 预处理 → NPU/TPU 推理 → CPU 后处理与上传`。只看 TOPS 无法判断整机能跑多少路，视频解码能力、预处理吞吐、内存带宽、模型输入尺寸和后处理开销同样可能成为瓶颈。

### 4.7 AI Hub 模型包应记录什么

为了避免“模型文件能复制但不能运行”，AI Hub 或算法仓库中的每个部署包至少应记录：

| 信息               | 为什么需要                                                          |
| ------------------ | ------------------------------------------------------------------- |
| 目标芯片           | 区分 `rk3576`、`cv186ah`、`bm1688`、`bm1684x`，决定编译后端和运行时 |
| 来源模型与版本     | 追溯原始 PyTorch / ONNX / Hugging Face 权重及算子图                 |
| 编译工具与版本     | 对齐 RKNN-Toolkit2 或 TPU-MLIR 的转换行为                           |
| 模型产物           | 明确 `.rknn` 或目标芯片专用 `.bmodel`，并保存校验值                 |
| 精度与量化信息     | 记录 FP32 / FP16 / BF16 / INT8 / INT4、校准集和精度回归结果         |
| 输入契约           | 固定尺寸或动态尺寸、NCHW/NHWC、RGB/BGR、归一化和 batch              |
| 前后处理           | resize、letterbox、色彩转换、NMS、坐标映射和类别表必须与模型一致    |
| Runtime / 驱动要求 | 防止模型编译版本与盒子上的 Runtime、驱动或固件不兼容                |
| 资源预算           | 模型内存、ION/NPU heap、视频路数、延迟和温度应有验收边界            |

## 5. 已实测巡检命令

以下命令均已在对应盒子上实际执行。标有 `sudo` 的命令会使用当前登录用户的密码。

### 5.1 三台通用基础信息

```bash
lscpu
free -h
lsblk -d -o NAME,SIZE,TYPE,MODEL
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
df -hT
ip -brief addr
```

区分 Linux 可管理总量、当前可用量、缓存、CMA 和 swap 时，使用以下已在三台设备复核的命令。`free -h` 适合快速阅读，`/proc/meminfo` 适合精确对账：

```bash
free -h
grep -E '^(MemTotal|MemFree|MemAvailable|Buffers|Cached|SReclaimable|Shmem|CmaTotal|CmaFree|SwapTotal|SwapFree):' \
  /proc/meminfo
```

RK3576 和 7.2T 可用以下命令读取主板字符串；32T 当前固件没有该节点：

```bash
cat /proc/device-tree/model | tr -d '\0'
printf '\n'
```

读取温度并同时保留 thermal zone 名称：

```bash
for z in /sys/class/thermal/thermal_zone*; do
  test -r "$z/type" || continue
  printf '%s=' "$(cat "$z/type")"
  cat "$z/temp"
done
```

温度原始单位通常为毫摄氏度，例如 `81000` 表示约 81°C。

### 5.2 RK3576 NPU

读取 NPU 实时负载：

```bash
sudo cat /sys/kernel/debug/rknpu/load
```

读取 NPU 频率范围、当前频率和 governor：

```bash
for d in /sys/class/devfreq/*npu*; do
  test -d "$d" || continue
  for f in name cur_freq min_freq max_freq available_frequencies governor; do
    test -r "$d/$f" && printf '%s=' "$f" && cat "$d/$f"
  done
done
```

查看 RKNPU 驱动初始化和物理内存口径：

```bash
sudo dmesg | grep -E 'RKNPU|27700000\.npu|Memory:' | tail -40
```

### 5.3 算能 TPU / SDK

`bm-smi` 默认是持续刷新的全屏 TUI。巡检脚本应使用以下单次采样命令，并单独执行，不要与后续命令共用同一个 here-document：

```bash
/opt/sophon/libsophon-current/bin/bm-smi --opmode=display -noloop
```

查看当前 libsophon 版本链接：

```bash
readlink -f /opt/sophon/libsophon-current
```

7.2T 查看启动时物理内存和 NPU / VPP 预留：

```bash
sudo dmesg | grep -E 'Memory:|npureserved|vppreserved'
```

32T 的 `dmesg` 环形缓冲区已被持续错误大量覆盖，应从本次启动的 journal 查询启动参数：

```bash
sudo journalctl -k -b --no-pager \
  | grep -E 'Memory:|npureserved|gmem\[' \
  | head -20
```

查看 7.2T ION heap 总量、当前分配量和峰值：

```bash
sudo sh -c 'grep -H . \
  /sys/kernel/debug/ion/cvi_*_heap_dump/total_mem \
  /sys/kernel/debug/ion/cvi_*_heap_dump/alloc_mem \
  /sys/kernel/debug/ion/cvi_*_heap_dump/peak'
```

查看 32T ION heap 总量、当前分配量和峰值：

```bash
sudo sh -c 'grep -H . \
  /sys/kernel/debug/ion/bm_*_heap_dump/total_mem \
  /sys/kernel/debug/ion/bm_*_heap_dump/alloc_mem \
  /sys/kernel/debug/ion/bm_*_heap_dump/peak'
```

旧文档中的 `/sys/kernel/debug/ion/cma` 在这两台算能固件上均不存在，不能作为通用检查路径。

## 6. 2026-07-15 审计结论

| 级别 | 设备   | 发现                                                                                              | 建议                                                                                              |
| ---- | ------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 高   | 32T    | NPU ION heap 约 3.86 GiB，当前 100% allocated；`algo` 持续触发 `ion_alloc failed(-12)` / `ENOMEM` | 优先核对算法是否重复加载模型、存在 ION 泄漏或超出 NPU heap 预算；处理前先保留进程、模型与分配快照 |
| 高   | 32T    | `/data` 99%，仅余约 353 MiB                                                                       | 尽快核对日志、缓存、抓拍和模型文件的保留策略，避免写满导致服务异常                                |
| 中   | 32T    | SoC 约 81°C，内核 thermal cooling 状态持续切换                                                    | 检查风扇、散热片、积尘、机箱风道和环境温度，并在业务峰值复测                                      |
| 中   | RK3576 | `/` 使用 83%                                                                                      | 清理或迁移增长型数据，优先把业务缓存放到 `/userdata`                                              |
| 中   | RK3576 | `sudo` 每次提示 `unable to resolve host linaro-alip`                                              | 核对 `/etc/hostname` 与 `/etc/hosts` 的 hostname 映射；本轮只读审计未修改系统                     |
| 中   | RK3576 | `lscpu` 报告 Spectre v2 为 `Vulnerable: Unprivileged eBPF enabled`                                | 结合厂商内核升级路径评估修复；至少限制非必要本地账号与不受信任代码执行                            |
| 中   | 7.2T   | 6 核设备 load average 约 6.1–6.3，处于接近满核负载的状态                                          | 在业务峰值连续采样 CPU、TPU 和视频处理负载，确认是否为持续饱和                                    |
| 提醒 | 全部   | 无 swap；密码认证已启用，且两台设备复用 `Whale12!`，32T 使用 `linaro/linaro`                      | 当前本地/内网边界下可接受明文记录；若网络边界扩大，应改密、改用密钥并收紧跳板访问                 |
| 信息 | 7.2T   | 设备树与 `bm-smi` 的芯片字符串不一致                                                              | 资产识别时同时记录 `bm-smi`、设备树、主机型号和 SDK 版本，不只依赖单一字段                        |

32T 可用以下已实测命令复核 ION 和 thermal 错误；输出量较大，建议保留 `tail`：

```bash
sudo journalctl -k -b --no-pager \
  | grep -E 'ion.*failed|thermal cooling' \
  | tail -100
```

## 7. 参考资料

- Rockchip RK3576 官方产品页。Accessed July 15, 2026. https://www.rock-chips.com/a/en/products/RK35_Series/2024/1212/2033.html
- Rockchip RKNN-Toolkit2 官方仓库。Accessed July 15, 2026. https://github.com/airockchip/rknn-toolkit2
- Rockchip librga 官方仓库。Accessed July 15, 2026. https://github.com/airockchip/librga
- Linaro About。Accessed July 15, 2026. https://www.linaro.org/about/
- SOPHGO CV186AH 官方产品页。Accessed July 15, 2026. https://www.sophgo.com/sophon-u/product/introduce/cv186ah.html
- SOPHGO CV186AH Product Brief V0.80 Public。Accessed July 15, 2026. https://sophon-assets.sophon.cn/sophon-prod-s3/productFile/2025/03/09/15/20/40/CV186AH_Product_Brief_V0.80_Public.pdf
- SOPHGO BM1688 官方产品页。Accessed July 15, 2026. https://www.sophgo.com/sophon-u/product/introduce/bm1688.html
- SOPHGO BM1688 Product Brief V0.80 Public。Accessed July 15, 2026. https://sophon-assets.sophon.cn/sophon-prod-s3/productFile/2025/03/09/15/19/05/BM1688_Product_Brief_V0.80_Public.pdf
- SOPHGO BM1684X 官方产品页。Accessed July 15, 2026. https://www.sophgo.com/sophon-u/product/introduce/bm1684x.html
- SOPHGO TPU-MLIR 官方仓库。Accessed July 15, 2026. https://github.com/sophgo/tpu-mlir
- SOPHGO TPU-MLIR 架构选择源码（BM1688 / CV186X）。Accessed July 15, 2026. https://github.com/sophgo/tpu-mlir/blob/master/lib/Backend/Arch.cpp
- SOPHGO TPU-MLIR 处理器分配源码（CV186X 单核策略）。Accessed July 15, 2026. https://github.com/sophgo/tpu-mlir/blob/master/lib/Dialect/Top/Transforms/ProcessorAssign.cpp
- SOPHGO TPU-MLIR BM1688 后端定义（最多双 core）。Accessed July 15, 2026. https://github.com/sophgo/tpu-mlir/blob/master/include/tpu_mlir/Backend/BM168x/BM1688.h
- SOPHGO TPU-MLIR 架构频率参数。Accessed July 15, 2026. https://github.com/sophgo/tpu-mlir/blob/master/include/tpu_mlir/Backend/Arch.h
- SOPHGO libsophon 官方仓库。Accessed July 15, 2026. https://github.com/sophgo/libsophon
- 三台内网设备的只读实机采样与命令验证，2026-07-15。
- Linux Kernel `/proc/meminfo` 字段说明。Accessed July 16, 2026. https://docs.kernel.org/filesystems/proc.html
- Linux Kernel CMA 配置说明与 DebugFS 接口。Accessed July 16, 2026. https://github.com/torvalds/linux/blob/master/mm/Kconfig ; https://docs.kernel.org/admin-guide/mm/cma_debugfs.html
- Devicetree Specification `/reserved-memory`。Accessed July 16, 2026. https://devicetree-specification.readthedocs.io/en/latest/chapter3-devicenodes.html#reserved-memory-node
- procps-ng `free(1)` 官方手册。Accessed July 16, 2026. https://gitlab.com/procps-ng/procps/-/raw/master/man/free.1
- 三台内网设备的内存口径只读复核，2026-07-16。
