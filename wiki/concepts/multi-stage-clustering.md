---
title: Multi-Stage Clustering (多阶段降维分治聚类)
created: 2026-05-25
updated: 2026-05-25
type: concept
tags: [computer-vision, reid, clustering, algorithm]
sources: [_living/AI-Applications-and-Ops/ReID-Pipeline-Architecture.md]
confidence: high
---

# Multi-Stage Clustering (多阶段降维分治聚类)

线下门店行人重识别场景下，单阶段 Embedding 聚类的全量门店上限受限、门店间方差极大。**多阶段降维分治** 是把聚合任务沿"在线/离线、严/松、嵌入/属性"维度切成四步，每步只解决最容易解决的那部分残余样本——逐级抬高总体聚合质量。它是 [[reid-pipeline]] 中的核心聚类策略。

## 核心思路

不要试图用一个阈值同时满足高精度与高召回，而是按**「由严到松、由在线到离线、由嵌入到属性」** 的顺序逐级处理：

- 早期轮次用高阈值收掉**最确信**的那部分（precision 接近上限，覆盖少量样本但绝对正确）；
- 中期轮次借助时间/轨迹结构补刀；
- 后期轮次启用人体属性等额外信号做硬约束；
- 末期用宽松阈值兜底召回碎片。

**核心经验**：每多一轮聚合，召回率单调上升。前序轮已大幅收敛搜索空间，后序可放宽匹配条件用较低 precision 换更高总 recall，不会污染全局结果——这是降维分治真正起作用的机制。^[[[_living/AI-Applications-and-Ops/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 四阶段拆解

### Stage 1：Online 高确信度聚合

- **频率**：高频次定时跑；
- **方法**：Single Linkage；
- **阈值**：高阈值；
- **目标**：保证准确率接近上限，先完成"最容易做对"的那部分去重。

### Stage 2：Offline 轨迹级聚合

- **频率**：闭店后离线；
- **方法**：优先匹配单条轨迹，结合「时长策略 + 综合相似度」对极相似 / 极短时差的残余配对；
- **阈值**：适中。

### Stage 3：属性约束增强

- **方法**：把"进店轨迹"的人体属性作为硬约束（**性别一般可用，年龄不太可用**），限制综合相似度阈值后对两组轨迹强制合并；
- **作用**：解决前两阶段无法靠纯 Embedding 区分的同/异性误合并。

### Stage 4：兜底召回

- **阈值**：宽松，扫尾剩余碎片轨迹；
- **作用**：把残余的边角样本捞回来，可接受 precision 下降。

## 出入口特殊场景：进出聚合一致性

部分场景（如不同出入口差异较明显的门店）下，店员多次规律进出会被老逻辑误识为多个不同顾客。新逻辑动态调整合并条件：

- **轨迹规律性**：进出交替、进出平衡；
- **摄像头一致性**：来源摄像头的分布比例。

该特殊聚合**默认关闭**，按店显式开启——它对"出入口差异显著"的门店才有效，普适开启反而引入误判。^[[[_living/AI-Applications-and-Ops/ReID-Pipeline-Architecture|ReID-Pipeline-Architecture]]]

## 与经典聚类范式的关系

该策略可视为 **Hierarchical Agglomerative Clustering (HAC)** 的工程化变体：

- 第 1 阶段类似 Single Linkage 的早停版本，只在最高密度区收敛；
- 第 2 阶段引入领域信号（时长、运动结构）做距离重定义；
- 第 3 阶段是属性硬约束下的强制合并，跳出纯几何距离；
- 第 4 阶段是覆盖兜底，类似 DBSCAN 的低密度噪声捕获。

它没有把"特征 + 距离 + 阈值"封死在一次聚类调用里，而是把这三者拆开，每一阶段单独定义距离函数与停止条件，工程上更容易调参与回归。

---

**相关概念**:

- [[reid-pipeline]]
- [[customer-flow-post-processing]]
