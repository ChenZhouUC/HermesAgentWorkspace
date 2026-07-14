---
title: WiFi CSI Sensing
created: 2026-07-14
updated: 2026-07-14
type: concept
tags: [edge-inference, algorithm, statistics]
sources: [_living/AI-Applications/RuView-Technical-Research-Deployment.md]
confidence: medium
---

# WiFi CSI Sensing

WiFi CSI 感知利用 OFDM 子载波级的 Channel State Information（CSI）推断环境或人体状态。与只给出一个信号强度标量的 RSSI 不同，CSI 保留各子载波的复数信道响应，也就是随频率和时间变化的振幅与相位；人体运动、呼吸和多径变化会在这些响应中留下可分析的扰动。^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]

## 从信道响应到语义

一条通用处理链可分为四段：

1. **采集与同步**：接收每个子载波的 I/Q 或复数 CSI，并记录天线、时间戳、带宽和包级元数据。
2. **校准与降噪**：处理 AGC、载波/采样偏移、子载波缺口、随机相位旋转和相位跳变，再做时域或频域滤波。
3. **物理特征提取**：从振幅、相位差、Doppler/PSD、AoA、ToA 或协方差结构中提取运动与空间特征。
4. **任务推断**：使用规则、经典阵列算法或学习模型，输出存在检测、活动分类、位置、姿态或生命体征等任务结果。

这一链路不能把“采到 CSI”与“得到可靠人体语义”视为同一件事。输出质量同时受采集硬件、同步方式、环境校准、特征算法、训练域和任务评测协议影响。

## 硬件决定可观测性

| 采集条件             | 能可靠利用的信息                       | 主要限制                                 |
| -------------------- | -------------------------------------- | ---------------------------------------- |
| RSSI-only            | 粗粒度存在或强度变化                   | 没有子载波级振幅与相位，不能替代真实 CSI |
| 单天线或独立节点 CSI | 时间变化、Doppler、部分振幅/相位统计   | 节点间相位不一致，绝对空间定位能力有限   |
| 多节点但非相干同步   | 多视角融合与覆盖改善                   | 时间戳对齐不能自动提供阵列级相位一致性   |
| 共享时钟、已校准阵列 | 相干 AoA/ToA、波束形成和更细空间分辨率 | 成本、部署和持续校准复杂度更高           |

MUSIC、Root-MUSIC 和 MVDR 等算法依赖阵列几何、相位一致性和可信协方差估计。把它们直接移到未同步的廉价节点上，只能作为待验证近似，不能默认获得相干阵列的精度。^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]

## 评测与部署边界

- **环境迁移**：墙体、家具、人员位置和多径结构变化都会造成 domain shift；应在目标房间与目标硬件上留出独立测试集。
- **任务口径**：存在检测、活动识别、姿态、呼吸和心率的信号尺度不同，不能由单一演示或模拟数据外推全部能力。
- **同步与校准**：应记录采样率、带宽、天线布局、时钟关系、校准过程和校准失效条件。
- **基线区分**：模拟 CSI、RSSI fallback 与真实 CSI 结果必须分别报告。
- **隐私与安全**：无摄像头不代表无隐私风险；穿墙或无感知能力仍需要用途限制、告知、授权和数据留存策略。

## 具体实现关系

[[ruview|RuView]] 是这一方法的应用层实例：它把廉价节点采集的 CSI 经过滤波、频谱/Doppler 特征和学习模型，映射为姿态、活动与生命体征等高层语义。专用相干阵列则更偏向高质量采集、相位校准和 AoA/ToA 估计；两者位于感知链的不同层次，可以互补，但不能把采集硬件的理论上限直接当作应用平台的实测能力。^[[[_living/AI-Applications/RuView-Technical-Research-Deployment|RuView-Technical-Research-Deployment]]]
