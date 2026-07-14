---
title: RuView (WiFi Sensing Platform)
created: 2026-05-14
updated: 2026-07-14
type: entity
tags: [edge-inference, edge-computing, algorithm]
sources: [_living/AI-Applications/RuView-Technical-Research-Deployment.md]
confidence: medium
---

# RuView (WiFi Sensing Platform)

RuView 是 [[wifi-csi-sensing|WiFi CSI 感知]]的应用层平台：它采集 WiFi 信道随人体和环境变化产生的 CSI 扰动，经信号处理与学习模型，输出存在检测、活动、姿态和生命体征等高层语义。它解决的是“拿到 CSI 后如何形成感知应用”，而不是相位同步阵列或信道探测硬件本身。^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]

## 能力链

1. ESP32 节点采集子载波级 CSI；没有 CSI 硬件时只能使用模拟数据或 RSSI fallback。
2. 预处理执行噪声过滤、窗口化、振幅处理、频谱/Doppler 提取和相位展开。
3. 时频特征进入学习模型，映射为人体关键点、活动类别、呼吸或心率等任务输出。
4. 服务层负责多节点融合、结果 API 和可视化。

## 部署定位

- 廉价 ESP32-S3 节点适合低成本采集和边缘侧预处理；多节点可以改善覆盖，但未共享时钟的节点不等同于相干天线阵列。
- macOS 常规 WiFi 接口通常只暴露 RSSI，不能获得完整子载波 CSI；RSSI 模式适合粗粒度存在检测，不应作为姿态或生命体征能力证明。
- 相位同步、已校准阵列可以为 AoA/ToA 与波束形成提供更高质量输入，但属于采集层增强，不是 RuView 默认链路的既有精度保证。

## 评估边界

RuView 的任务结果对房间布局、多径、节点数量、相位质量、训练数据和校准状态敏感。模拟演示、单节点结果、RSSI fallback 与真实多节点 CSI 必须分别标注；穿墙姿态、呼吸和心率等高难任务应在目标硬件与目标环境中独立验证，不能仅从处理链存在推导出部署精度。^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]
