---
title: RuView Technical Research Deployment
created: 2026-05-14
updated: 2026-05-15
---

# RuView 技术调研与部署手册

> 调研日期：2026-04-20  
> 项目地址：https://github.com/ruvnet/RuView  
> 当前版本：v0.7.0 (Beta)  
> License: MIT

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心原理](#2-核心原理)
3. [系统架构](#3-系统架构)
4. [硬件适配分析](#4-硬件适配分析)
5. [部署方案一：MacBook M 系列（开发环境）](#5-部署方案一macbook-m系列开发环境)
6. [部署方案二：Nvidia T4 服务器（推理服务）](#6-部署方案二nvidia-t4-服务器推理服务)
7. [部署方案三：Nvidia Jetson TX1（边缘节点）](#7-部署方案三nvidia-jetson-tx1边缘节点)
8. [无硬件快速验证](#8-无硬件快速验证)
9. [关键限制与注意事项](#9-关键限制与注意事项)
10. [ESPARGOS/pyespargos 技术参考与对比分析](#10-espargospyespargos-技术参考与对比分析)
11. [参考资料](#11-参考资料)

---

## 1. 项目概述

### 1.1 一句话总结

RuView 是一个 **WiFi 感知平台**，利用 WiFi 信号的 Channel State Information (CSI) 实现：

- 穿墙人体检测与姿态估计
- 非接触式生命体征监测（呼吸、心率）
- 活动识别、人数统计、睡眠监测
- 环境指纹与物体检测

**核心卖点**：不需要摄像头、不需要可穿戴设备，仅靠普通 WiFi 信号的物理扰动即可完成感知。

### 1.2 项目定位

| 维度     | 说明                                                         |
| -------- | ------------------------------------------------------------ |
| 学术源头 | Carnegie Mellon University 论文 "DensePose From WiFi" (2022) |
| 当前阶段 | Beta，API 和固件可能变动                                     |
| 核心硬件 | ESP32-S3 ($9/节点) 作为 CSI 采集器                           |
| 运行环境 | 纯边缘运行，无需云服务                                       |
| 推理性能 | Rust pipeline: ~54,000 fps; Python pipeline: 较慢但功能完整  |
| 模型大小 | 4-bit 量化后仅 8KB，可部署在 ESP32 SRAM 中                   |

### 1.3 能力边界（诚实矩阵）

| 能力       | 单节点 ESP32 | 3 节点 Mesh | 6 节点 Mesh | 仅 RSSI (笔记本 WiFi) |
| ---------- | ------------ | ----------- | ----------- | --------------------- |
| 存在检测   | Good         | Excellent   | Excellent   | 可用 (90-95%)         |
| 粗粒度运动 | Good         | Excellent   | Excellent   | 可用 (85-90%)         |
| 房间级定位 | 无           | Good        | Excellent   | 不可用                |
| 呼吸检测   | Marginal     | Good        | Good        | 不可用                |
| 心率检测   | Poor         | Poor        | Marginal    | 不可用                |
| 多人计数   | 无           | Marginal    | Good        | 不可用                |
| 姿态估计   | 无           | Poor        | Marginal    | 不可用                |

**重要**：没有 ESP32 硬件时，可以用模拟数据跑通整个流水线，验证信号处理算法的正确性。

---

## 2. 核心原理

### 2.1 WiFi CSI 感知基础

**Channel State Information (CSI)** 是 WiFi OFDM 子载波级别的信道响应信息，比传统 RSSI 丰富得多：

```
RSSI: 1个标量值 (信号强度)
CSI:  N个子载波 × 每个子载波的振幅+相位 (复数矩阵)
```

在 802.11n/ac 中，一帧 CSI 数据包含 52-256 个子载波的复数响应 H(f)：

```
H(f, t) = |H(f,t)| · e^{jφ(f,t)}
```

当人体移动时，多径传播改变，CSI 矩阵随之变化。RuView 的核心就是从这种变化中提取有意义的信息。

### 2.2 信号处理 Pipeline

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│ Raw CSI I/Q │───▶│ Noise Filter │───▶│ Hamming      │───▶│ Amplitude  │
│ (Complex)   │    │ (Butterworth)│    │ Windowing    │    │ Normalize  │
└─────────────┘    └──────────────┘    └──────────────┘    └────────────┘
                                                                  │
                                                                  ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│ Feature     │◀───│ PSD (Power   │◀───│ FFT-based    │◀───│ Phase      │
│ Vector      │    │ Spectral     │    │ Doppler      │    │ Unwrapping │
│             │    │ Density)     │    │ Extraction   │    │            │
└─────────────┘    └──────────────┘    └──────────────┘    └────────────┘
```

关键处理步骤：

1. **噪声滤波**: Butterworth 带通滤波器去除环境噪声
2. **Hamming 加窗**: 减少频谱泄漏
3. **幅度归一化**: 消除距离衰减影响
4. **相位展开 (Phase Unwrapping)**: 消除 2π 跳变，恢复连续相位
5. **FFT Doppler 提取**: 时间维度 FFT 提取多普勒频移，反映运动速度
6. **PSD 计算**: 功率谱密度用于区分不同类型的活动

### 2.3 DensePose 神经网络

项目使用 **WiFlow 架构** 将 CSI 特征映射到人体姿态：

```
CSI 特征 (64×20 时频矩阵)
        │
        ▼
┌─────────────────────────┐
│ TCN (Temporal Conv Net) │  ← 时序特征提取
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Axial Attention         │  ← 空间注意力机制
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Pose Decoder            │  ← 输出 17 个 COCO 关键点
└─────────────────────────┘
```

模型规格：

| 预设   | 参数量 | 大小   |
| ------ | ------ | ------ |
| lite   | 189K   | ~100KB |
| small  | 474K   | ~250KB |
| medium | 800K   | ~400KB |
| full   | 7.7M   | ~4MB   |

### 2.4 生命体征检测原理

- **呼吸检测**: 对 CSI 信号进行 0.1-0.5 Hz 带通滤波，通过过零检测计算呼吸频率 (6-30 BPM)
- **心率检测**: 对 CSI 信号进行 0.8-2.0 Hz 带通滤波，提取微小胸腔运动引起的相位变化 (40-120 BPM)

### 2.5 Fresnel Zone 穿墙模型

WiFi 信号穿墙能力基于菲涅尔区理论：

```
r_n = √(n·λ·d₁·d₂ / (d₁ + d₂))
```

其中 λ 是波长 (2.4GHz ≈ 12.5cm, 5GHz ≈ 6cm)。低频段穿墙能力更强，RuView 通过多频段跳频（6 个信道）融合来提高穿墙检测能力。

---

## 3. 系统架构

### 3.1 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        RuView System                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────┐    ┌─────────────┐    ┌──────────────────────┐      │
│  │ ESP32-S3│    │ Aggregator  │    │   Inference Engine   │      │
│  │  Nodes  │───▶│ (UDP 5005)  │───▶│  (Python/Rust/WASM) │      │
│  │ CSI采集  │    │ 特征融合      │    │  姿态/活动/生命体征    │      │
│  └─────────┘    └─────────────┘    └──────────┬───────────┘      │
│       ×3-6           ×1                        │                  │
│                                                ▼                  │
│                                    ┌──────────────────────┐      │
│                                    │     API Server       │      │
│                                    │  (FastAPI / Axum)    │      │
│                                    │  REST + WebSocket    │      │
│                                    └──────────┬───────────┘      │
│                                                │                  │
│                                                ▼                  │
│                                    ┌──────────────────────┐      │
│                                    │  3D Visualization    │      │
│                                    │  (Three.js Browser)  │      │
│                                    └──────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 代码结构

```
RuView/
├── v1/                          # Python pipeline (v1)
│   ├── src/
│   │   ├── api/                 # FastAPI REST + WebSocket
│   │   ├── sensing/             # RSSI 采集 + 特征提取 + 分类
│   │   ├── core/                # 信号处理核心
│   │   ├── models/              # 神经网络模型
│   │   └── hardware/            # 硬件接口抽象
│   ├── data/proof/              # 确定性验证数据
│   └── requirements-lock.txt    # 锁定依赖（保证哈希可复现）
│
├── rust-port/wifi-densepose-rs/ # Rust pipeline (v2, ~810x faster)
│   └── crates/
│       ├── wifi-densepose-signal/   # 信号处理 (FFT, Doppler)
│       ├── wifi-densepose-nn/       # NN推理 (ONNX/candle/tch)
│       ├── wifi-densepose-api/      # Axum HTTP/WS 服务
│       ├── wifi-densepose-hardware/ # 硬件适配器
│       ├── wifi-densepose-wasm/     # WebAssembly
│       └── wifi-densepose-cli/      # CLI
│
├── firmware/esp32-csi-node/     # ESP32-S3 固件 (ESP-IDF C)
├── ui/                          # Three.js 3D 可视化
├── docker/                      # Docker 部署
├── scripts/                     # 工具脚本 (训练/采集/分析)
└── docs/                        # 文档 + 79个 ADR
```

### 3.3 两条技术路径

| 路径                  | 语言        | 性能        | 适用场景                     |
| --------------------- | ----------- | ----------- | ---------------------------- |
| Python Pipeline (v1/) | Python 3.9+ | ~66 fps     | 快速原型、研究、API 服务     |
| Rust Pipeline (v2)    | Rust 1.85+  | ~54,000 fps | 生产部署、边缘设备、实时处理 |

---

## 4. 硬件适配分析

### 4.1 你的硬件清单

| 设备              | 架构                  | GPU               | 显存/内存       | 适合角色                        |
| ----------------- | --------------------- | ----------------- | --------------- | ------------------------------- |
| MacBook M 系列    | ARM64 (Apple Silicon) | Metal/MPS         | 8-64GB 统一内存 | 开发环境 + Rust 编译 + 轻量推理 |
| Nvidia T4 服务器  | x86_64                | Turing, 2560 CUDA | 16GB GDDR6      | GPU 推理服务 + Docker 全栈      |
| Nvidia Jetson TX1 | ARM64 (aarch64)       | Maxwell, 256 CUDA | 4GB LPDDR4      | 边缘部署聚合器                  |

### 4.2 适配方案总结

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  MacBook M  │         │  T4 Server  │         │ Jetson TX1  │
│             │         │             │         │             │
│ • 开发调试   │         │ • 训练模型    │         │ • 边缘聚合器  │
│ • Rust编译   │  ────▶  │ • GPU推理    │  ────▶  │ • 信号处理   │
│ • 单元测试   │  模型    │ • API服务    │  轻量    │ • 存在检测   │
│ • 3D可视化   │  部署    │ • Docker全栈 │  推理    │ • UDP接收    │
└─────────────┘         └─────────────┘         └─────────────┘
```

### 4.3 关于 ESP32 替代方案

**你没有 ESP32，但可以：**

1. **模拟模式运行**: Docker 镜像内置 CSI 数据模拟器
2. **RSSI 感知 (MacBook)**: macOS 可通过 `airport` 工具获取 RSSI，做粗粒度存在检测
3. **录制回放**: 项目提供 `data/recordings/*.csi.jsonl` 格式的离线数据
4. **确定性验证**: `./verify` 命令用固定参考信号验证整个信号处理链

> 💡 **建议**: 如果后续想体验完整 CSI 能力，购买 3 块 ESP32-S3-DevKitC-1 (约 ¥70×3 = ¥210) 即可组建最小 Mesh。

---

## 5. 部署方案一：MacBook M 系列（开发环境）

### 5.1 角色定位

- 主要开发机，代码编写、调试、单元测试
- Rust pipeline 编译（M 系列芯片编译速度极快）
- 3D 可视化前端展示
- 本地 API 服务器运行

### 5.2 环境准备

```bash
# 0. 确认系统版本
sw_vers  # macOS 13+ 推荐

# 1. 安装 Homebrew（如果没有）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2. 安装基础工具
brew install python@3.11 rust node git cmake openblas pkg-config

# 3. 安装 Rust (如果 brew 安装的版本不够新)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup update
rustup target add aarch64-apple-darwin  # M系列原生target
```

### 5.3 克隆项目

```bash
cd ~/Projects  # 或你喜欢的目录
git clone --recursive https://github.com/ruvnet/RuView.git
cd RuView
```

### 5.4 Python Pipeline 部署

```bash
# 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate

# 安装最小验证依赖（推荐先跑通）
pip install -r v1/requirements-lock.txt

# 验证信号处理链正确性
./verify --verbose

# 如果通过，安装完整依赖
pip install -r requirements.txt

# 注意：macOS M系列安装 PyTorch 用 MPS 后端
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
# 或者如果想用 MPS 加速 (macOS 12.3+)：
pip install torch torchvision  # 默认 pip 版本已含 MPS 支持
```

### 5.5 启动 API 服务器

```bash
# 开发模式（热重载）
uvicorn v1.src.api.main:app --host 0.0.0.0 --port 8000 --reload

# 验证
curl http://localhost:8000/health
curl http://localhost:8000/docs  # OpenAPI 文档
```

### 5.6 Rust Pipeline 编译

```bash
# 进入 Rust 工作区
cd rust-port/wifi-densepose-rs

# 安装 OpenBLAS (ndarray-linalg 需要)
brew install openblas
export OPENBLAS_DIR=$(brew --prefix openblas)

# 编译 release 版本
cargo build --release

# 运行测试（107个测试用例）
cargo test --workspace

# 运行 benchmark
cargo bench --package wifi-densepose-signal

# M系列预期结果：
#   CSI Preprocessing (4x64): ~3-5 us
#   Full Pipeline: ~10-18 us
#   Throughput: ~54,000+ fps
```

### 5.7 3D 可视化

```bash
# 方法1: 直接打开
open ui/viz.html

# 方法2: HTTP 服务（推荐，避免 CORS 问题）
python3 -m http.server 3000 --directory ui
# 然后浏览器打开 http://localhost:3000/viz.html

# 可视化会自动连接 ws://localhost:8000/ws/pose
# 如果 API 服务器未运行，会 fallback 到 demo 模式
```

### 5.8 Docker 模拟模式（无硬件体验完整功能）

```bash
# 拉取预构建镜像（支持 arm64）
docker pull ruvnet/wifi-densepose:latest

# 运行（模拟 CSI 数据）
docker run -p 3000:3000 -p 3001:3001 ruvnet/wifi-densepose:latest

# 浏览器打开 http://localhost:3000 即可看到实时 3D 姿态
```

---

## 6. 部署方案二：Nvidia T4 服务器（推理服务）

### 6.1 角色定位

- 主要推理服务器，承载 GPU 加速的 DensePose 模型
- Docker 全栈部署（API + PostgreSQL + Redis + Prometheus + Grafana）
- 模型训练（如果需要 fine-tune）
- 多节点 ESP32 数据的中心处理

### 6.2 环境准备

```bash
# 确认 GPU 驱动
nvidia-smi
# 应显示 Tesla T4, 16GB, CUDA 11.x/12.x

# 确认 CUDA 版本
nvcc --version

# 安装 Docker + NVIDIA Container Toolkit
# (如果尚未安装)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 验证 GPU 对 Docker 可用
docker run --rm --gpus all nvidia/cuda:12.2-base nvidia-smi
```

### 6.3 Docker 全栈部署

```bash
git clone --recursive https://github.com/ruvnet/RuView.git
cd RuView

# 配置环境变量
cp example.env .env
# 编辑 .env，关键修改：
#   ENVIRONMENT=production
#   DEBUG=false
#   SECRET_KEY=<生成一个强密钥>
#   MOCK_HARDWARE=true  (没有ESP32时)
#   POSE_MODEL_PATH=/app/models/  (模型路径)

# 启动开发栈（含 Postgres + Redis + Prometheus + Grafana）
docker compose up -d

# 查看日志
docker compose logs -f wifi-densepose

# 服务端口：
#   API:        http://<server-ip>:8000
#   API Docs:   http://<server-ip>:8000/docs
#   Prometheus: http://<server-ip>:9090
#   Grafana:    http://<server-ip>:3000 (admin/admin)
```

### 6.4 GPU 加速推理配置

```bash
# 修改 docker-compose.yml 或 docker-compose.override.yml
# 添加 GPU 支持：
cat > docker-compose.override.yml << 'EOF'
version: "3.9"
services:
  wifi-densepose:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - CUDA_VISIBLE_DEVICES=0
      - TORCH_DEVICE=cuda
EOF

docker compose up -d
```

### 6.5 直接部署（非 Docker）

```bash
# 系统依赖
sudo apt-get update && sudo apt-get install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential gfortran libopenblas-dev pkg-config \
  postgresql redis-server

# Python 环境
python3.11 -m venv venv
source venv/bin/activate

# 安装 PyTorch with CUDA
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 安装项目依赖
pip install -r requirements.txt

# 启动 API 服务（4 workers 利用多核）
uvicorn v1.src.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
```

### 6.6 Rust Pipeline 编译（T4 服务器）

```bash
# 安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 系统依赖
sudo apt-get install -y build-essential gfortran libopenblas-dev pkg-config

# 编译
cd rust-port/wifi-densepose-rs
cargo build --release

# Rust API 服务器（Axum，极高性能）
cargo run --release --package wifi-densepose-api

# 如果需要作为 ESP32 聚合器
cargo run --release --package wifi-densepose-hardware -- \
  --mode esp32-aggregator --port 5005
```

### 6.7 模型训练（利用 T4 GPU）

```bash
# 下载预训练模型
pip install huggingface_hub
huggingface-cli download ruv/ruview --local-dir models/

# 如果有自己的数据，可以重新训练：
# (需要 Node.js)
sudo apt-get install -y nodejs npm

# ruvllm 训练 pipeline（对比学习 + 任务头 + LoRA + 量化）
node scripts/train-ruvllm.js --data data/recordings/pretrain-*.csi.jsonl

# WiFlow 姿态训练
node scripts/train-wiflow.js --data data/recordings/*.csi.jsonl

# Benchmark
node scripts/benchmark-ruvllm.js --model models/csi-ruvllm
```

---

## 7. 部署方案三：Nvidia Jetson TX1（边缘节点）

### 7.1 角色定位

- 边缘聚合器：接收 ESP32 UDP 数据流
- 轻量推理：运行量化后的模型 (8KB 4-bit)
- 信号处理：Rust 编译的 ARM64 二进制
- 存在检测 + 基础活动识别

### 7.2 TX1 硬件约束

| 参数    | 值                      | 影响                                  |
| ------- | ----------------------- | ------------------------------------- |
| CPU     | 4-core ARM Cortex-A57   | 编译慢，运行时够用                    |
| GPU     | 256 CUDA Maxwell        | 能跑 PyTorch 但显存小                 |
| RAM     | 4GB LPDDR4 (共享)       | **限制因素**，不能同时跑大模型 + 服务 |
| 存储    | 16GB eMMC               | 需要 SD 卡扩展                        |
| JetPack | 4.x (基于 Ubuntu 18.04) | 软件版本较老                          |

### 7.3 环境准备

```bash
# 确认 JetPack 版本
cat /etc/nv_tegra_release
# 推荐 JetPack 4.6+ (L4T 32.6.1+)

# 确认 CUDA
nvcc --version  # 应为 CUDA 10.2

# 基础工具
sudo apt-get update && sudo apt-get install -y \
  python3-pip python3-venv \
  build-essential cmake pkg-config \
  libopenblas-dev gfortran

# 扩展存储（如果 eMMC 空间不足）
# 挂载 SD 卡到 /opt/ruview
sudo mkdir -p /opt/ruview
sudo mount /dev/mmcblk1p1 /opt/ruview  # 根据实际设备调整
```

### 7.4 方案 A：Rust 编译部署（推荐）

Rust 编译后的二进制在 TX1 上运行极其高效，内存占用小。

```bash
# 选项1: 在 TX1 上直接编译（耗时较长，约30-60分钟）
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

cd /opt/ruview
git clone --recursive https://github.com/ruvnet/RuView.git
cd RuView/rust-port/wifi-densepose-rs

# 仅编译需要的 crate（节省时间和空间）
cargo build --release --package wifi-densepose-signal
cargo build --release --package wifi-densepose-hardware

# 选项2: 在 MacBook/T4 上交叉编译（更快）
# 在 MacBook 上：
rustup target add aarch64-unknown-linux-gnu
# 需要交叉编译工具链
brew install filosottile/musl-cross/musl-cross  # 或使用 Docker 交叉编译

# 在 T4 服务器上（更简单，同为 Linux）：
sudo apt-get install -y gcc-aarch64-linux-gnu
rustup target add aarch64-unknown-linux-gnu

cat >> ~/.cargo/config.toml << 'EOF'
[target.aarch64-unknown-linux-gnu]
linker = "aarch64-linux-gnu-gcc"
EOF

cd rust-port/wifi-densepose-rs
cargo build --release --target aarch64-unknown-linux-gnu \
  --package wifi-densepose-signal \
  --package wifi-densepose-hardware \
  --package wifi-densepose-cli

# 将二进制 scp 到 TX1
scp target/aarch64-unknown-linux-gnu/release/wifi-densepose-cli \
  user@jetson-tx1:/opt/ruview/
```

### 7.5 方案 B：Python 轻量部署

```bash
# TX1 上的 Python 部署（仅信号处理+存在检测）
python3 -m venv /opt/ruview/venv
source /opt/ruview/venv/bin/activate

# 安装最小依赖
pip install numpy==1.26.4 scipy==1.14.1

# 验证
cd /opt/ruview/RuView
python3 v1/data/proof/verify.py

# 安装 API 依赖（精简版，不含 torch）
pip install fastapi uvicorn pydantic pydantic-settings websockets

# 运行 sensing 服务（RSSI 模式或模拟模式）
python3 -m v1.src.sensing.ws_server
```

### 7.6 作为 ESP32 聚合器运行

```bash
# Rust 版本（推荐，低内存）
/opt/ruview/wifi-densepose-cli --mode esp32-aggregator --port 5005

# 或 Python 版本
# 监听 UDP 5005，接收 ESP32 CSI 特征帧
python3 -c "
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('0.0.0.0', 5005))
print('Listening for ESP32 CSI data on UDP 5005...')

while True:
    data, addr = sock.recvfrom(4096)
    frame = json.loads(data.decode())
    print(f'Node {frame.get(\"node_id\")}: {len(frame.get(\"features\", []))} features')
"
```

### 7.7 TX1 性能优化

```bash
# 切换到最大性能模式
sudo nvpmodel -m 0  # MAXN mode (所有核心全速)
sudo jetson_clocks   # 锁定最高频率

# 禁用桌面 GUI（节省 ~500MB 内存）
sudo systemctl set-default multi-user.target
sudo reboot

# 监控资源
tegrastats  # Jetson 专用性能监控
```

---

## 8. 无硬件快速验证

即使完全没有 ESP32，也可以验证核心算法的正确性。

### 8.1 确定性验证（5 分钟上手）

```bash
# 任何机器上（MacBook/T4/TX1 均可）
git clone https://github.com/ruvnet/RuView.git
cd RuView

# 安装最小依赖
pip install numpy==1.26.4 scipy==1.14.1

# 一键验证
./verify --verbose
```

这会：

1. 加载 `v1/data/proof/sample_csi_data.json` (确定性参考信号)
2. 通过完整信号处理链
3. 计算输出的 SHA-256 哈希
4. 与发布的 expected hash 对比
5. 扫描生产代码中是否有随机数（确保确定性）

### 8.2 Docker 模拟体验

```bash
# 拉取并运行（自动使用模拟 CSI 数据）
docker run -p 3000:3000 -p 3001:3001 ruvnet/wifi-densepose:latest

# 浏览器打开 http://localhost:3000
# 可以看到实时的 3D 人体姿态渲染（模拟数据驱动）
```

### 8.3 WebSocket 测试

```python
# test_ws.py - 连接 WebSocket 查看实时数据
import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:3001"  # 或 8000 取决于哪个服务
    async with websockets.connect(uri) as ws:
        for i in range(10):
            msg = await ws.recv()
            data = json.loads(msg)
            print(f"Frame {i}: {data.keys()}")

asyncio.run(main())
```

---

## 9. 关键限制与注意事项

### 9.1 硬件限制

| 问题                      | 说明                     | 解决方案                      |
| ------------------------- | ------------------------ | ----------------------------- |
| 没有 ESP32 = 没有真实 CSI | 只能用模拟数据或 RSSI    | 花 ¥210 买 3 块 ESP32-S3      |
| TX1 内存仅 4GB            | 不能跑完整 PyTorch 模型  | 用量化模型 (8KB) 或 Rust 推理 |
| TX1 JetPack 版本老        | Python 3.6, CUDA 10.2    | 用 Docker 或交叉编译          |
| MacBook 无法获取 CSI      | macOS 不暴露子载波级数据 | 只能做 RSSI 级别感知          |

### 9.2 ESP32 型号注意

⚠️ **仅支持 ESP32-S3**，以下型号不支持：

- ESP32-C3: 单核，不够 CSI DSP
- 原版 ESP32: 单核，不够
- ESP32-S2: 无蓝牙，功能受限

### 9.3 项目成熟度

- Beta 阶段，API 可能变动
- 79 个 ADR 表明架构决策经过深思熟虑
- 1,463 个测试通过
- 确定性验证保证信号处理核心的正确性
- 但实际部署经验有限，社区较小

### 9.4 安全考虑

生产环境部署务必：

- 修改 `SECRET_KEY`
- 启用 `ENABLE_AUTHENTICATION=true`
- 启用 `ENABLE_RATE_LIMITING=true`
- 限制 `ALLOWED_HOSTS` 和 `CORS_ORIGINS`
- 关闭 `ENABLE_TEST_ENDPOINTS`

### 9.5 推荐测试路径

```
Phase 1: 验证 (0 成本, 30分钟)
  └── ./verify --verbose
  └── Docker 模拟模式
  └── 浏览器查看 3D 可视化

Phase 2: 开发 (0 成本, 半天)
  └── MacBook 上编译 Rust pipeline
  └── 运行 benchmark，对比官方数据
  └── API 服务器 + WebSocket 联调

Phase 3: 部署 (0 成本, 1天)
  └── T4 服务器 Docker 全栈部署
  └── TX1 交叉编译 + 边缘验证

Phase 4: 真实感知 (¥210, 1-2天)
  └── 购买 3x ESP32-S3-DevKitC-1
  └── 刷固件 + 配网 + 聚合器联调
  └── 真实环境存在检测验证
```

---

## 10. ESPARGOS/pyespargos 技术参考与对比分析

> 项目地址：https://github.com/ESPARGOS/pyespargos  
> License: LGPLv3  
> 硬件：ESPARGOS 2×4 相位同步天线阵列

### 10.1 两个项目的本质关系

RuView 和 ESPARGOS/pyespargos 是两个独立项目，解决的是 WiFi CSI 感知链路上 **不同层次的问题**：

**ESPARGOS** → 解决 **"如何高质量地获取 CSI 数据"**（硬件采集层）

它是一套硬件 + 驱动方案：一块专用 PCB 上焊了 8 颗 ESP32 组成 2×4 相位同步天线阵列，共享 40MHz 参考时钟。pyespargos 是它的 Python 客户端，负责数据采集、相位校准、以及经典阵列信号处理算法（MUSIC AoA、Root-MUSIC ToA、MVDR 波束成形）。本质上它是一台 **WiFi 信道探测仪（Channel Sounder）**——被动监听空间中的 WiFi 帧，输出精确的、相位一致的多天线 CSI 矩阵。

**RuView** → 解决 **"拿到 CSI 数据后如何感知人体"**（AI 应用层）

它是一套端到端的感知应用平台：从廉价的单节点 ESP32-S3 采集 CSI，经过信号处理流水线（滤波、FFT、PSD），再送入神经网络（TCN + Axial Attention），最终输出 17 个人体关键点坐标、呼吸/心率、活动分类等高层语义。本质上它是一个 **WiFi 感知 AI 应用（Sensing Application）**——把原始物理层数据翻译成"谁在哪里、在做什么"。

**类比：**

```
ESPARGOS ≈ 高精度麦克风阵列（硬件采集层）
RuView   ≈ 语音识别系统（AI 应用层）
```

两者没有代码依赖关系，但技术上互补——如果用 ESPARGOS 硬件替代 RuView 默认的单节点 ESP32 采集，CSI 的相位精度和空间分辨率会大幅提升，理论上能显著改善姿态估计精度。

### 10.2 维度对比

与 RuView 的关键差异：

| 维度         | RuView                     | ESPARGOS                           |
| ------------ | -------------------------- | ---------------------------------- |
| **硬件定位** | 商品级 ESP32-S3 ($9/节点)  | 专用 PCB 天线阵列（学术级）        |
| **CSI 采集** | 单天线逐节点独立采集       | 2×4 阵列相位同步采集               |
| **相位精度** | 软件级相位校准（误差较大） | 硬件时钟同步 + PCB 走线补偿        |
| **空间分辨** | 多节点 Mesh 融合近似       | MUSIC/MVDR 超分辨算法精确 AoA      |
| **典型应用** | 人体姿态估计、活动识别     | 精确 AoA/ToA 定位、信道建模        |
| **部署成本** | 极低 (¥60-200)             | 中等（需定制 PCB）                 |
| **数据通路** | ESP32 → WiFi → 聚合器      | ESP32 → SPI → 控制器 → UDP/WS → PC |

### 10.3 硬件架构深度解析

#### 10.3.1 相位同步机制

ESPARGOS 实现相位同步的核心设计：

```
                    ┌──────────────┐
                    │ 40MHz Master │  (共享参考时钟)
                    │    Clock     │
                    └──────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │  ESP32 #0 │    │  ESP32 #1 │    │  ESP32 #n │
    │ (Row 0)   │    │ (Row 0)   │    │ (Row 1)   │
    │ PLL Lock  │    │ PLL Lock  │    │ PLL Lock  │
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │ Antenna 0 │    │ Antenna 1 │    │ Antenna n │
    └───────────┘    └───────────┘    └───────────┘
```

**关键参数：**

- 天线间距：`d = 0.06m`（约半波长 @ 2.4GHz，满足空间 Nyquist 采样定理）
- 阵列结构：2 行 × 4 列 = 8 天线
- 频率同步：所有 ESP32 共享 40MHz 参考时钟（PLL 锁相环锁定）
- 相位同步：通过已知信道（PCB 校准走线）进行 PLL 相位对齐

#### 10.3.2 射频开关 (RF Switch) 机制

每个天线端口有 4 种状态切换：

```python
class rfswitch_state_t(IntEnum):
    SENSOR_RFSWITCH_ISOLATION = 0   # 隔离态（不接收）
    SENSOR_RFSWITCH_REFERENCE = 1   # 接参考校准信号
    SENSOR_RFSWITCH_ANTENNA_R = 2   # 右旋圆极化 (RHCP)
    SENSOR_RFSWITCH_ANTENNA_L = 3   # 左旋圆极化 (LHCP)
    SENSOR_RFSWITCH_ANTENNA_RANDOM = 4  # 随机 R/L 切换
```

这使得 ESPARGOS 支持 **双极化测量**，可以分离信号的 R/L 极化分量，获取完整的 Jones 矩阵信息。

#### 10.3.3 Jones 矩阵与极化

ESPARGOS 的天线为椭圆极化，使用 Jones 矩阵将线极化 (H/V) 转换为馈电极化 (R/L)：

```python
# 简化 Jones 矩阵 (线极化 → 馈电极化)
J_simple = √2/2 × [[-1, 1], [1, 1]]

# 实测交叉极化校正
J_crosspol = [[0.33, 0.05+0.05j], [0.05+0.05j, 0.33]] / ‖·‖_F

# 总有效 Jones 矩阵
J = J_simple @ J_crosspol
```

当多个 2×4 子阵列旋转组合时，需要对每个天线的 Jones 矩阵施加旋转校正：

```
J_eff = J_base^{-1} · R(θ)
```

其中 `R(θ)` 是子阵列物理旋转角对应的 2D 旋转矩阵。

### 10.4 CSI 数据格式与 WiFi 前导码

#### 10.4.1 三种 CSI 前导码格式

| 格式                                   | 子载波数      | 带宽  | 应用场景                   |
| -------------------------------------- | ------------- | ----- | -------------------------- |
| **L-LTF** (Legacy Long Training Field) | 53            | 20MHz | 最基本，所有 802.11 帧都有 |
| **HT20-LTF** (HT Long Training Field)  | 57            | 20MHz | 802.11n/ac HT 模式         |
| **HT40-LTF**                           | 117 (57+3+57) | 40MHz | 信道绑定模式，分辨率最高   |

#### 10.4.2 子载波物理意义

```
WiFi 子载波间距: Δf = 312.5 kHz
2.4GHz Channel 1 中心频率: 2.412 GHz
信道间距: 5 MHz

HT40 子载波布局 (117个):
┌──── Primary 57 ────┐ ┌3 gap┐ ┌── Secondary 57 ──┐
│ -28..+28 subcarriers│ │ 0s  │ │ -28..+28         │
└────────────────────┘ └─────┘ └──────────────────┘
```

每个子载波的 CSI 值是一个复数 `H[k] = I + jQ`，表征该频率上的信道传递函数。

#### 10.4.3 CSI 数据解析（C 结构体级别）

pyespargos 直接用 `ctypes` 解析 ESP32 SPI 缓冲区的二进制数据：

```c
// ESP32 PHY V3 (ESP32-C5/C61) CSI 包结构 (384 bytes)
struct serialized_csi_v3_t {
    uint32_t type_header;       // 版本标识
    uint8_t  rx_ctrl[64];       // wifi_pkt_rx_ctrl_t (RSSI, rate, CFO, 噪声底等)
    uint8_t  source_mac[6];     // 发射端 MAC
    uint8_t  dest_mac[6];       // 目标 MAC
    uint16_t seq_ctrl;          // 序列号 (12bit seg + 4bit frag)
    uint32_t timestamp;         // 本地时间戳
    bool     is_calib;          // 是否为校准帧
    bool     first_word_invalid;// 首字无效标志
    int8_t   buf[256];          // CSI I/Q 数据 (128 个复数)
    uint64_t global_timestamp_us; // 全局微秒时间戳
    uint16_t csi_len;           // CSI 有效长度
    bool     acquire_force_lltf;
    uint8_t  acquire_val_scale_cfg;
    uint32_t rfswitch_state;    // RF 开关状态
    bool     is_radar;          // 雷达模式标志
    uint8_t  antid;             // 天线 ID
    bool     acquire_lltf_bit_mode;
    uint32_t crc32;             // 校验
};
```

与 RuView 对比：RuView 通过 WiFi 传输 JSON 格式的 CSI 数据（简化但有开销），ESPARGOS 通过 SPI 直接读取原始二进制（零开销，但需要专用硬件）。

### 10.5 核心算法详解

#### 10.5.1 MUSIC 空间谱估计 (Angle of Arrival)

MUSIC (MUltiple SIgnal Classification) 是 ESPARGOS 的核心算法，用于超分辨角度估计：

**数学原理：**

1. **阵列信号模型**：假设 M 个天线接收 D 个信号源

   ```
   x(t) = A·s(t) + n(t)
   ```

   其中 `A = [a(θ₁), ..., a(θ_D)]` 是导向矩阵，`a(θ) = [1, e^{-jπsinθ}, e^{-j2πsinθ}, ...]ᵀ`

2. **协方差矩阵估计**：

   ```
   R = E[x·xᴴ] ≈ (1/N) Σ x(t)·x(t)ᴴ
   ```

3. **特征分解**：

   ```
   R = U·Λ·Uᴴ
   分离为：U_s (信号子空间，D 个大特征向量) + U_n (噪声子空间，M-D 个小特征向量)
   ```

4. **MUSIC 伪谱**：
   ```
   P_MUSIC(θ) = 1 / ‖U_nᴴ · a(θ)‖²
   ```
   在真实 DoA 方向上，`a(θ)` 与噪声子空间正交 → 分母趋于零 → 谱峰

**ESPARGOS 实现（from music-spectrum.py demo）：**

```python
# 扫描角度：-90° 到 +90°
scanning_angles = np.linspace(-π/2, π/2, 180)

# 均匀线阵 (ULA) 导向矢量
# d = λ/2 时，相位差 = π·sin(θ) 每天线
steering_vectors = np.exp(-1j * np.outer(
    π * np.sin(scanning_angles),
    np.arange(ANTENNAS_PER_ROW)  # 4 天线
))

# 协方差矩阵 (对所有子载波求和获得空间相关)
csi_los = np.sum(csi_backlog, axis=-1)  # 子载波求和
R = np.einsum("dbri,dbrj->ij", csi_los, np.conj(csi_los))

# 特征分解
eig_val, eig_vec = np.linalg.eig(R)
order = np.argsort(eig_val)[::-1]

# 噪声子空间 (去掉最大特征值对应的信号子空间)
Qn = eig_vec[:, order][:, 1:]  # 假设 1 个信号源

# MUSIC 伪谱
spatial_spectrum = 1 / ‖Qnᴴ · steering_vectors‖  (对每个角度)
spatial_spectrum_dB = 20 * log10(spatial_spectrum)
```

**信号源数估计 (Rissanen MDL 准则)：**

```python
# Minimum Description Length criterion for Forward-Backward Correlation Matrix
for k in range(L):
    mdl[k] = -M*(L-k) * (Σlog(λ_i)/(L-k) - log(Σλ_i/(L-k)))  # 似然项
            + (1/4)*k*(2L-k+1)*log(M)                            # 惩罚项

source_count = argmin(mdl)
```

#### 10.5.2 Root-MUSIC (ToA 估计)

Root-MUSIC 是 MUSIC 的多项式求根变体，用于精确 Time-of-Arrival 估计：

```python
# 1. 构建 CSI 分块协方差矩阵
#    将 N 个子载波分成 chunkcount 块，每块 chunksize 个
R = einsum("dbrmci,dbrmcj->brmij", csi_chunked, conj(csi_chunked))

# 2. Forward-Backward 平滑
R = (R + flip(conj(R))) / 2

# 3. 特征分解，取噪声子空间
Qn = eigvec[:, source_count:]

# 4. 构造多项式 C = Qn·Qnᴴ
C = Qn @ Qn.H
coeffs = [trace(C, offset=diag) for diag in range(1, len(C))]

# 5. 求根
roots = np.roots(coeffs)
roots = roots[abs(roots) < 1]  # 保留单位圆内的根

# 6. 从根的角度提取延迟
toa = -angle(root) / (2π · Δf)  # Δf = 312.5 kHz
```

**延迟分辨率**：HT40 模式下 (40MHz 带宽)，理论时间分辨率 ≈ 25ns，对应距离分辨率 ≈ 7.5m。Root-MUSIC 超分辨可突破此限制。

#### 10.5.3 MVDR (Capon) 波束成形

作为 MUSIC 的补充，MVDR 提供更稳健但分辨率稍低的谱估计：

```python
# 自适应波束成形器
P_MVDR(θ) = 1 / (aᴴ(θ) · R⁻¹ · a(θ))

# 实现（用 solve 代替 inv 提高数值稳定性）
R_inv_a = np.linalg.solve(R, steering_vectors)
P_mvdr = 1 / real(einsum("it,brmit->brmt", conj(steering_vectors), R_inv_a))
```

#### 10.5.4 CSI 相位校准流程

ESPARGOS 的校准是其核心竞争力：

```
校准流程:
1. RF Switch → REFERENCE 状态（接入已知参考信道）
2. 采集所有天线对参考信号的 CSI
3. 计算 PCB 走线传播延迟补偿:
     group_delay = cable_length / (c × velocity_factor)
     phase_correction = exp(-j2π × delay × f_subcarrier)
4. 存储校准值（每天线×每子载波一个复数）
5. 应用时: CSI_calibrated = CSI_raw × exp(-j·angle(calib_value))
```

**关键细节：**

- 仅校准相位，不校准幅度（幅度差异来自 AGC，每帧独立）
- 需要同时校准 L-LTF、HT20、HT40 三种格式
- 多板组合时需额外补偿板间同步线缆长度差异

#### 10.5.5 CSI 插值算法

用于从多次不完全相干的测量中提取稳定 CSI：

**迭代相位对齐插值**：

```python
# 目标：从 N 次测量中提取最佳平均 CSI
# 每次测量有随机相位偏移 φ_n (由 oscillator 噪声引起)
for iteration in range(10):
    # 加权平均 (补偿相位偏移)
    w = Σ weights[n] × exp(-jφ_n) × csi[n]
    # 重新估计相位偏移
    φ_n = angle(conj(w) · csi[n])
```

**主特征向量插值**：

```python
# 构建空间协方差矩阵
R = Σ w_n × csi[n] × csi[n]ᴴ
# 主特征向量即最优 CSI 估计
csi_best = eigvector_of_max_eigenvalue(R)
```

#### 10.5.6 符号定时偏移 (STO) 消除

WiFi 接收端存在符号定时不确定性，导致 CSI 有线性相位斜率：

```python
# STO 表现为子载波维度上的线性相位旋转
# H_observed[k] = H_true[k] × exp(j·ω·k), ω 与 STO 成正比

# 估计相位斜率 ω
phase_slope = angle(Σ H[k+1] × conj(H[k]))  # 相邻子载波相位差的角度

# 校正
subcarrier_indices = arange(-N/2, N/2) + 1
correction = exp(-j × phase_slope × subcarrier_indices)
H_corrected = H × correction
```

### 10.6 对 RuView 的技术启示

#### 10.6.1 可直接借鉴的技术

| 技术           | ESPARGOS 实现            | RuView 适配方案                             |
| -------------- | ------------------------ | ------------------------------------------- |
| MUSIC AoA      | 4 天线 ULA               | 3 节点 ESP32 间构建虚拟阵列（但相位不同步） |
| STO 消除       | `remove_mean_sto()`      | 可直接移植到 CSI 预处理流程                 |
| CSI 插值       | 迭代 / 特征向量          | 用于降噪，替代简单时域平均                  |
| DC 子载波插值  | L-LTF/HT20/HT40 gap 处理 | 处理 ESP32 CSI 中的 null 子载波             |
| Root-MUSIC ToA | 多项式求根法             | 适用于多径分离（区分人体反射和墙壁反射）    |

#### 10.6.2 不可直接移植的技术

| 技术         | 原因             | 替代方案                            |
| ------------ | ---------------- | ----------------------------------- |
| 硬件相位同步 | 需要共享时钟 PCB | RuView 用软件时间戳对齐 + 差分相位  |
| 极化测量     | 需要 RF 开关硬件 | RuView 仅用单极化，依赖机器学习弥补 |
| 多板精确组合 | 需要线缆长度补偿 | RuView 用 RSSI 加权融合             |

#### 10.6.3 ESPARGOS 启发的改进方向

1. **CSI 降噪**：在 RuView 现有 Butterworth 滤波之外，增加 ESPARGOS 的子载波级 STO 校正和 DC 插值
2. **虚拟阵列**：利用已知 ESP32 节点位置，结合多节点 CSI 构建虚拟天线阵列（牺牲时间分辨率换空间分辨率）
3. **多径分离**：用 Root-MUSIC 算法分离人体反射路径和静态环境路径，提高信噪比
4. **校准流程**：即使没有硬件同步，也可以通过已知参考位置的信标（另一个 ESP32 在固定位置）进行软件校准

### 10.7 如何在你的硬件上实验 pyespargos 算法

即使没有 ESPARGOS 硬件，也可以用模拟数据验证算法：

```python
# simulate_music.py - 在 MacBook/T4 上验证 MUSIC 算法
import numpy as np

# 参数
M = 4              # 天线数 (模拟 ESPARGOS 2×4 阵列的一行)
d = 0.06           # 天线间距 (m)
f = 2.412e9        # 2.4GHz WiFi Channel 1
c = 3e8
lam = c / f        # 波长 ≈ 0.124m
theta_true = 30    # 真实 AoA (度)

# 生成模拟信号
N = 100            # 快拍数
theta_rad = np.deg2rad(theta_true)
# 导向矢量
a = np.exp(-1j * 2 * np.pi * d / lam * np.sin(theta_rad) * np.arange(M))
# 接收信号 (1 信号 + 噪声)
signal = np.random.randn(N) + 1j * np.random.randn(N)
noise = 0.1 * (np.random.randn(N, M) + 1j * np.random.randn(N, M))
X = np.outer(signal, a) + noise

# MUSIC
R = X.T @ np.conj(X) / N
eigval, eigvec = np.linalg.eigh(R)
Qn = eigvec[:, :-1]  # 噪声子空间 (M-1 列)

# 扫描
angles = np.linspace(-90, 90, 361)
spectrum = np.zeros(len(angles))
for i, ang in enumerate(angles):
    a_scan = np.exp(-1j * 2*np.pi*d/lam * np.sin(np.deg2rad(ang)) * np.arange(M))
    spectrum[i] = 1 / np.linalg.norm(Qn.T.conj() @ a_scan)**2

print(f"真实角度：{theta_true}°")
print(f"MUSIC 估计：{angles[np.argmax(spectrum)]:.1f}°")
# 预期输出：30.0° (完美匹配)
```

### 10.8 ESPARGOS 硬件采购参考

如果后续预算允许，ESPARGOS 硬件可以大幅提升 CSI 质量：

| 方案                 | 预算          | 能力                       |
| -------------------- | ------------- | -------------------------- |
| 3× ESP32-S3 (RuView) | ¥210          | 基础存在检测，软件级 CSI   |
| 1× ESPARGOS 板       | €200-400 (估) | 精确 AoA，单方向 120° 扫描 |
| 2× ESPARGOS 板 组合  | €400-800 (估) | 2D AoA + ToA，精确 3D 定位 |

> 注：ESPARGOS 为学术项目，硬件可能需通过其团队 (espargos.net) 获取。

---

## 11. 参考资料

### 学术论文

- [DensePose From WiFi](https://arxiv.org/abs/2301.00250) - Carnegie Mellon University, 2022
- [WiFi-based Human Pose Estimation](https://arxiv.org/abs/2010.01011) - 相关工作
- ESP32 CSI: [Espressif CSI Guide](https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-guides/wifi.html#channel-state-information)
- [MUSIC Algorithm](<https://en.wikipedia.org/wiki/MUSIC_(algorithm)>) - MUltiple SIgnal Classification 超分辨算法
- [GAN-based Massive MIMO Channel Model Trained on Measured Data](https://arxiv.org/abs/2205.02678) - CSI 迭代插值算法来源
- Xinrong Li, Kaveh Pahlavan: "Super-resolution TOA estimation with diversity for indoor geolocation" - Rissanen MDL 准则参考

### 项目文档

- [RuView User Guide](https://github.com/ruvnet/RuView/blob/main/docs/user-guide.md)
- [RuView Build Guide](https://github.com/ruvnet/RuView/blob/main/docs/build-guide.md)
- [Architecture Decisions (79 ADRs)](https://github.com/ruvnet/RuView/tree/main/docs/adr)
- [ESP32 Firmware README](https://github.com/ruvnet/RuView/blob/main/firmware/esp32-csi-node/README.md)
- [pyespargos GitHub](https://github.com/ESPARGOS/pyespargos) - ESPARGOS Python 客户端库
- [ESPARGOS 官网](https://espargos.net) - 硬件信息与论文

### 硬件购买

- ESP32-S3-DevKitC-1: [乐鑫官方](https://www.espressif.com/zh-hans/products/devkits/esp32-s3-devkitc-1) / 淘宝搜索
- Cognitum Seed (可选): [cognitum.one](https://cognitum.one)

### 关键命令速查

```bash
# 验证
./verify --verbose --audit

# Python API
uvicorn v1.src.api.main:app --host 0.0.0.0 --port 8000 --reload

# Rust 编译
cd rust-port/wifi-densepose-rs && cargo build --release

# Rust 测试
cargo test --workspace

# Rust benchmark
cargo bench --package wifi-densepose-signal

# Docker 模拟
docker run -p 3000:3000 ruvnet/wifi-densepose:latest

# 3D 可视化
python3 -m http.server 3000 --directory ui

# ESP32 固件刷写 (有硬件时)
cd firmware/esp32-csi-node && idf.py build flash monitor
```

---

_文档结束。如有疑问请联系项目维护者或提 Issue。_
