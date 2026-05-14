# AI 边缘计算盒子调研：RK3576 与算能系列

本文记录三类边缘计算盒子的硬件参数、常用检测命令和现场排查方法，重点关注 RK3576、算能 CV186AH / BM1688 以及 BM1684X 系列。

## 1. 核心术语

- TOPS (Tera Operations Per Second)：每秒一万亿次操作，是衡量 AI 芯片算力的常用单位。“32T”通常指芯片在特定数据精度（多为 INT8）下最高可达到 32 TOPS。
- INT8 / FP16 / FP32：常见数据精度。INT8 常用于边缘端 AI 推理，速度快、功耗低；FP16 / FP32 精度更高，常用于训练或高精度推理，算力数值通常低于 INT8。
- NPU / TPU：Neural / Tensor Processing Unit，专门用于加速神经网络或张量计算的硬件模块。瑞芯微（Rockchip）通常称 NPU，算能（SOPHGO）通常称 TPU。
- BM1688 / CV186AH：BM1688 是算能的芯片平台之一；CV186AH 是基于同系列架构衍生的细分型号，主打高性价比边缘视觉网关。因此在 CV186AH 盒子里查看系统设备树时，底层可能仍显示 BM1688 ASIC。
- Linaro：ARM 架构开源软件优化组织。部分边缘盒子会采用 Linaro 相关 Linux 底座或工具链，因此默认用户名、系统版本描述中可能出现 `linaro` 字样。

## 2. 硬件参数与特性

| 设备                                    | 测试环境                             | 厂商               | CPU / 架构                                                        | 内存与存储                                                                                   | AI 算力                                                                 | 主要特性                                                                       |
| --------------------------------------- | ------------------------------------ | ------------------ | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| RK3576 盒子                             | 内网实验机（地址与凭据见本地凭据库） | Rockchip（瑞芯微） | 八核 ARM CPU（4 x Cortex-A72 @ 2.2GHz + 4 x Cortex-A53 @ 1.8GHz） | 4GB RAM + 32GB eMMC（`/` 分区约 14G，`/userdata` 约 15G）                                    | 6 TOPS (INT8)，支持 INT4 / INT8 / INT16 / FP16 / BF16 / TF32 等混合精度 | 发热和功耗控制较好，视频编解码能力强，适合泛安防、智能家居、IPC 等视觉推理场景 |
| 算能 7.2T 盒子（CV186AH / BM1688 系列） | 内网实验机（地址与凭据见本地凭据库） | SOPHGO（算能）     | ARM Cortex-A53，实测设备树标识为 `Sophon. BM1688 ASIC. ARM64.`    | 4GB RAM（OS 约 1.2G，TPU / VPU 硬预留约 2.8G）+ 32GB eMMC（`/` 分区约 8.7G，`/data` 约 17G） | 7.2 TOPS (INT8)                                                         | 高性价比智能视觉边缘网关，适合多路视频流并发处理和轻量级深度学习推理           |
| 算能 32T 盒子（BM1684X 系列）           | 内网实验机（地址与凭据见本地凭据库） | SOPHGO（算能）     | 高性能 ARM SoC + 第三代 TPU                                       | 16GB RAM（OS 约 6G，TPU 硬预留约 10G）+ 64GB eMMC（`/` 分区约 16G，`/data` 约 34G）          | 32 TOPS (INT8) / 16 TFLOPS (FP16 / BF16) / 2 TFLOPS (FP32)              | 浮点算力支持较完整，适合 LLM 边缘端部署和多路复杂视频分析                      |

## 3. 上机查看与测试方法

### 3.1 瑞芯微 RK3576

登录方式（使用本地凭据库中的地址与账号）：

```bash
ssh <rk3576-user>@<rk3576-private-host>
# 凭据：见本地凭据库 / 忽略文件中的私有配置
```

查看 CPU 架构与核心数：

```bash
lscpu
# 输出将显示 Cortex-A72 和 Cortex-A53 的组合。
```

查看内存容量与使用情况：

```bash
free -h
df -h
```

查看 NPU 驱动加载状态与使用率：

```bash
cat /sys/kernel/debug/rknpu/load
# 实时打印当前 NPU 利用率，例如 NPU load: 10%。

dmesg | grep npu
# 查看内核启动日志中的 NPU 频率或初始化信息。
```

### 3.2 算能 7.2T 和 32T 盒子

登录方式（使用本地凭据库中的地址与账号）：

```bash
ssh <sophon72-user>@<sophon72-private-host>
# 7.2T 凭据：见本地凭据库 / 忽略文件中的私有配置

ssh <sophon32-user>@<sophon32-private-host>
# 32T 凭据：见本地凭据库 / 忽略文件中的私有配置
```

查看 TPU / NPU 利用率、温度、功耗与内存：

```bash
/opt/sophon/libsophon-current/bin/bm-smi
```

`bm-smi` 类似 `nvidia-smi`，会显示 Board ID、Chip Name、TPU Util、NPU-Mem、TPU-Temp 和 Board Pwr 等核心参数。部分固件没有把该工具加入全局 PATH，因此建议使用绝对路径。

查看主板底层型号：

```bash
cat /proc/device-tree/model
# 例如 7.2T (BM1688) 盒子返回：Sophon. BM1688 ASIC. ARM64.
# 注意：32T (BM1684X) 的老内核系统可能没有该节点，建议直接用 bm-smi 查看。
```

查看 CPU 架构：

```bash
lscpu
# 算能 SoC 通常为多核 Cortex-A53。
```

### 3.3 探查硬件预留内存与真实存储

边缘计算盒子常见“硬件圈占内存（Hardware Reserved Memory）”和 OverlayFS 挂载重叠现象，导致 `free -h` 和 `df -h` 不一定能完整反映物理规格。可使用以下命令交叉确认。

探查物理总内存与 TPU / VPU 预留内存：

```bash
dmesg | grep -i "Memory:"
# 查看内核启动时识别到的真实物理总内存。

dmesg | grep -i "reserved" | grep -i "mem"
# 查看被底层硬件（如 TPU / 视频解码器）强制圈占的内存大小。

cat /sys/kernel/debug/ion/cma
# 算能盒子专属：查看系统底层 ION / CMA 内存池分配情况。
```

探查真实物理硬盘（eMMC）容量：

```bash
lsblk -d
# 绕过文件系统挂载，直接扫描硬件块设备容量。

df -h
# 对比查看各分区的实际划分，重点关注 /data 或 /userdata。
```

## 参考资料

- 高度依赖场景的边缘盒子，其竞争壁垒是什么？RFID 世界网，2024。Accessed May 12, 2026. https://m.rfidworld.com.cn/news/2406_574D5F0641B65278.html
- bq76940 芯片 - 抖音（Sophgo 7.2T-32T 参数信息）。Accessed May 12, 2026. https://www.douyin.com/search/%E8%8A%AF%E7%89%873072
