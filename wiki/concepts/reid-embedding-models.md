---
title: ReID Embedding Models (行人 ReID 特征向量模型选型)
created: 2026-05-26
updated: 2026-05-26
type: concept
tags: [computer-vision, reid, architecture, paper]
sources: [_living/AI-Applications-and-Ops/ReID-Embedding-Models.md]
confidence: high
---

# ReID Embedding Models (行人 ReID 特征向量模型选型)

线下门店 ReID 系统中"行人特征向量提取模型"的技术谱系与选型方法学：从 2019 年 CNN 时代的 BoT/FastReid baseline，到 2021-2024 transformer + 大规模自监督预训练路线，再到 2023-2025 视觉 - 语言对齐的跨域泛化路线。本概念关注**特征提取器**这一环节；管线侧的架构见 [[reid-pipeline]]。

## 问题与边界

ReID 特征向量模型的职责单一：**给定一张行人裁剪图，输出固定维度向量**，使得"同一行人不同抓拍"的向量距离小、"不同行人"的距离大。它**不负责**行人检测、轨迹关联、跨帧 ID 分配——那些是上游目标检测与下游 [[multi-stage-clustering|多层级聚合]] 的职责。

衡量指标：

- **Rank-N** + **mAP**：检索质量；
- **跨域泛化**：在 A 域训练、在 B 域评测时的性能掉点幅度——线下零售场景与学术数据集差异巨大，这一项决定能否实战可用。^[[[_living/AI-Applications-and-Ops/ReID-Embedding-Models|ReID-Embedding-Models]]]

## 技术谱系：两根独立演进轴

把模型升级看成**预训练数据轴 × 主干架构轴**两条独立线并行推进，可独立替换、独立评估：

### 主干架构轴

```
ResNet (2015) ─▶ IBN-ResNet ─▶ ViT (2020) ─▶ Swin Transformer ─▶ CNN-Transformer 混合 (Next-ViT 类)
```

- **CNN 时代**：ResNet-50 + IBN/Non-local 增强，部署成熟、TensorRT 友好；
- **ViT 引入**：TransReID (ICCV 2021) 首次系统把 ViT 应用到 ReID，提出 JPM (Jigsaw Patch Module，强迫学局部细节) 与 SIE (Side Information Embedding，把摄像头/视角等元信息编进 token)；
- **CNN-Transformer 混合**：TRT-ViT / Next-ViT 早期阶段用卷积块、晚期阶段用 transformer 块，相同 TensorRT 延迟下精度高于纯 ResNet——是 ViT-ReID 边缘部署的优选。

### 预训练数据轴

```
ImageNet 监督 ─▶ LUPerson 自监督 (4M 图/200K id) ─▶ LUPerson-NL 噪声标签 (10M 图)
                                                ─▶ CLIP 视觉-语言 (400M 图文对)
                                                ─▶ MIM 自监督 (PersonViT)
```

ImageNet 与人体外观分布有巨大 gap；**领域内大规模无监督预训练**（LUPerson 系列）成为新的标准起点。CLIP 的视觉 - 语言对齐是另一条思路，强项是跨域泛化而非域内精度。^[[[_living/AI-Applications-and-Ops/ReID-Embedding-Models|ReID-Embedding-Models]]]

## 主要候选与定位

| 方案                           | 路线                                    | 强项                                                      | 弱项                                                 |
| ------------------------------ | --------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------- |
| **BoT / FastReid (2019-2020)** | CNN baseline + 一组训练 trick 工业化    | 部署成熟、训练管线完整、被 BoT-SORT 等 MOT 直接复用       | 主干已是 2020 年 SOTA，跨域泛化落后                  |
| **TransReID (2021)**           | ViT + JPM + SIE                         | 首个 ViT ReID，证明长距依赖建模有用                       | ImageNet 预训练，未充分发挥 ViT 潜力                 |
| **TransReID-SSL (2022)**       | ViT + LUPerson 自监督预训练             | 显著超过 ImageNet 预训练，确立"领域内自监督 + 微调"主线   | 需要标注微调                                         |
| **SOLIDER (2023)**             | Swin + LUPerson DINO 自蒸馏 + 语义可控  | 人本视觉任务通用底座，NVIDIA ReidentificationNet 即此路线 | 仍需领域内微调；遮挡场景需要叠加 Keypoint Promptable |
| **CLIP-ReID (2023)**           | CLIP ViT + 可学习文本 prompt 两阶段训练 | 跨域泛化优于纯视觉模型；CLIP-B 即可，无需 CLIP-L          | 两阶段训练繁琐；视频时序信息没用上                   |
| **PersonViT (2024)**           | MIM 自监督 + LUPerson + ViT             | Market/MSMT/Duke/Occluded-Duke 全面 SOTA                  | 计算成本高                                           |

**关键负面发现**：直接拿 DINOv2 零样本做 ReID 失败（mAP 仅 0.3%-4.7%）——纯视觉自监督预训练**不足以**应对身份匹配；CLIP-L (428M) 相对 CLIP-B (150M) 增益微弱——更大模型不自动等于更好的 ReID。

## 选型决策框架

需要在以下维度上做明确的取舍：

- **域泛化 vs 域内精度**：训练域 = 测试域 时优先纯精度；否则优先 CLIP-ReID 这类语言对齐模型；
- **主干算力**：CNN (ResNet/IBN) 比 ViT/Swin 部署友好；ViT 在长距依赖上更强——边缘盒子选 CNN，云推理选 ViT/Swin；
- **预训练数据**：ImageNet 通用 / LUPerson 领域内 / CLIP 跨模态——决定跨域泛化上限；
- **微调成本**：TransReID/SOLIDER 需要领域内标注；CLIP-ReID 可零样本起步——决定新场景上线周期；
- **遮挡 / 多人歧义**：门店出入口经常被门框、其他人体半遮挡，需要 Occluded-Duke / Keypoint Promptable 专项设计。

完整的横向对比表（含 Trade-offs 与 When-to-use 决策树）见 [[reid-embedding-model-families]]。

## 部署约束

学术 SOTA 的 mAP 数字 ≠ 生产可用：

- **Transformer 延迟劣势**：原版 ViT 在 TensorRT 上常**比 ResNet 慢**——FLOPs 不是好指标，要看真实硬件延迟；
- **改良路径**：CNN-Transformer 混合架构（TRT-ViT/Next-ViT）、注意力图引导剪枝（AMG）、知识蒸馏从 Swin/CLIP 教师压回 CNN 学生；
- **输入分辨率非对称**：人体裁剪是竖长方形，主流是 **256×128**（H×W），不是 224×224 方形——主流方案都遵循这个约定；
- **跨域掉点是常态**：测试显示 SOLIDER 在新场景上 mAP 可掉 50%+，CLIP-ReID 掉 38%+——**任何模型上线前都要在目标域抽样测试，不能信源域数字**。

## 评估方法学的局限

学术数据集（Market-1501 / MSMT17 / DukeMTMC）是**城市街景闭集**，与线下零售门店有几个根本差异：

- 同质化（类内方差有限，缺遮挡 / 半身 / 同色制服）；
- 不含店员/特殊角色（学术只评"顾客与顾客之间的辨别"，不评店员与顾客的区分——后者是真实业务的关键）；
- 闭集评测（学术 query/gallery 身份重叠，线下零售是开集）。

实战必须建**领域内私有评测集**：按店按月抽样、覆盖 hard cases（同人不同时段 / 店员日常 / 遮挡进出 / 假人嵌套）、同时评 mAP + 延迟 + 训练成本 + 跨域稳定性四象限。

输出后的下游消费见 [[customer-flow-post-processing]]。

---

**相关概念**:

- [[reid-pipeline]]
- [[multi-stage-clustering]]
- [[customer-flow-post-processing]]
- [[reid-embedding-model-families]]
