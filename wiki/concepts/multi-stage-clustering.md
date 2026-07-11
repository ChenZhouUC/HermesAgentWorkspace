---
title: Multi-Stage Clustering (轨迹相似度图的多层级连通分量聚合)
created: 2026-05-25
updated: 2026-07-11
type: concept
tags: [computer-vision, reid, clustering, algorithm]
sources: [_living/Whale-SpaceSight/ReID-Pipeline-Architecture.md]
confidence: high
---

# Multi-Stage Clustering (轨迹相似度图的多层级连通分量聚合)

线下门店行人重识别 (ReID) 场景下，单阶段 Embedding 聚类的全量门店上限受限、门店间方差极大。**多层级降维分治** 是把聚合任务切成多个独立 tier，每 tier 控制 _mask 范围_ + _相似度阈值_ + _合并模式_，把"匹配标准"几何化为图论问题。它是 [[hidalgo|HIDALGO]] 计算层在 [[reid-pipeline]] 中承担的核心聚类策略。

## 底层数学：相似度图上的连通分量

聚合的统一底座**不是经典 HAC 的 single linkage**，而是**相似度图上的传递闭包 / 连通分量**计算：

1. 构建一张稀疏相似度图：节点是轨迹，边是"满足条件的相似关系"；
2. 用动作方向掩码、摄像头一致性掩码、时间窗掩码裁剪这张图；
3. 在裁剪后的图上求连通分量——一个连通分量即一个行人。

每个 tier 调整的就是 _mask 配置_ + _相似度阈值_ + _合并模式（all / max / exclusive）_，把"是否合并"从"挑选 linkage 函数 + 阈值"的二维选择，升级为"在多重正交语义掩码下逐层放宽"的多维过滤。^[[[_living/Whale-SpaceSight/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 核心思路：由严到松、由同向到异向、由轨迹到批次

不要试图用一个阈值 + 一个图同时满足高精度与高召回，而是按以下顺序逐级处理：

- 早期 tier 用**严格 mask + 高阈值** 收掉"最确信"的那部分（精确率接近上限，覆盖少量样本但绝对正确）；
- 中期 tier 放宽 mask 让**同向多帧** 与 **异向成对**（一进一出同人）轨迹合并；
- 后期 tier 启用**时序与轨迹结构信号** 做补充召回；
- 末期 tier 用宽松阈值兜底召回剩余碎片。

**核心经验**：每多一层 tier，召回率单调上升。前序层已大幅收敛搜索空间，后序可放宽匹配条件用较低 precision 换更高总 recall，不会污染全局结果——这是分层分治真正起作用的机制。

## 三类主线 + 多档分级

### 出入口聚合（Entrance）

按"先确定再放宽"的顺序切分多 tier：

1. 同方向单体（confident solitary）；
2. 同方向聚合（confident moderate）；
3. 跨方向中期合并（midterm bridge）；
4. 异方向单体（hetero solitary，处理一进一出的成对轨迹）；
5. 异方向覆盖合并（hetero overlap，进出时间窗重叠）；
6. 异方向适配合并（hetero fitted，进出特征贴合）；
7. 总结兜底（finally summarize）。

每个 tier 内部还有**多轮阈值递减**机制——相同的判定条件下，阈值会从高到低衰减若干轮，让"确信度高的"先 lock-in、"边缘的"后逐步收敛。

### 店内轨迹组装（Interior）

按相似度档位（高 / 中高 / 中 / 中低 / 低）依次推进；同一组装目标可在不同档位接收新成员，直到无新增。

### 跨场景匹配（Coupling）

把店内轨迹挂载到出入口锚点时，分为：

1. **锚定（Anchor）**：最确信的店内轨迹绑定到一个出入口锚；
2. **匹配（Match）**：剩余轨迹按相似度逐个挂载；
3. **补充（Supplement）**：用次级信号（时长、共现摄像头）再扫一轮；
4. **补偿（Compensate）**：兜底召回，允许低阈值。

## 与经典聚类范式的关系

该策略可视为 **Hierarchical Agglomerative Clustering (HAC)** 的工程化变体：

- 把"特征 + 距离 + 阈值"封死在一次聚类调用里的传统做法，被拆成"分别定义每层的距离掩码 + 阈值 + 合并模式"；
- 每一 tier 单独定义相似度规则与停止条件，工程上更容易调参与回归；
- 连通分量替代 linkage 函数，把多个"局部松/紧"的判定融为一张可裁剪的图——支持任意复杂的领域约束（动作方向、摄像头、时间窗），而不被 linkage 的几何对称性限制。

下游的客流后处理见 [[customer-flow-post-processing]]，它消费的是这个分层聚合的最终输出。
