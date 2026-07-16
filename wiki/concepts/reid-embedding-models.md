---
title: ReID Embedding Models (行人 ReID 特征向量模型选型)
created: 2026-05-26
updated: 2026-07-16
type: concept
tags: [computer-vision, reid, architecture, paper]
sources: [_living/Whale-SpaceSight/ReID-Embedding-Models.md]
confidence: high
---

# ReID Embedding Models (行人 ReID 特征向量模型选型)

行人重识别（Person Re-Identification，**ReID**）特征模型接收行人裁剪图并输出固定维度的嵌入向量（embedding），用于 query-gallery 检索、相似度判定或下游 [[multi-stage-clustering|多层级聚合]]。它不负责行人检测、轨迹关联或跨帧 ID 分配。

详细的论文配置、损失函数、评测协议和作者标称性能以 ReID Embedding 模型选型与演进为准；本页只保留稳定的概念框架。^[[[_living/Whale-SpaceSight/ReID-Embedding-Models|ReID-Embedding-Models]]]

## 分类框架

ReID 演进不是单一模型链，需要区分以下对象：

- **方法或模型**：PCB、MGN、BoT、OSNet、TransReID、CLIP-ReID、SOLIDER、KPR、PersonViT；
- **主干网络**（backbone）：ResNet、OSNet、Vision Transformer（ViT）、Swin Transformer；
- **预训练资源或范式**：ImageNet 监督预训练、LUPerson 自监督预训练、LUPerson-NL 噪声标签预训练、CLIP 视觉 - 语言预训练；
- **工程框架**：FastReID。框架没有唯一的主干、损失或性能，必须绑定具体配置讨论。

```text
表征结构：全局 CNN
          ├─ 固定部件与多粒度：PCB/RPP → MGN
          ├─ 强全局训练配方：BoT
          ├─ ReID 专用轻量主干：OSNet
          ├─ 全局 - 局部 Transformer：TransReID
          └─ 关键点提示与遮挡建模：KPR

预训练信号：ImageNet 监督预训练
          ├─ 人体域自监督：LUPerson/MoCoV2 → TransReID-SSL
          │                 ├─ SOLIDER
          │                 └─ PersonViT
          ├─ 人体域噪声标签：LUPerson-NL → PNL
          └─ 视觉 - 语言预训练：CLIP → CLIP-ReID

目标域数据使用：direct transfer / DG；UDA / USL
工程实现层：FastReID
```

## 关键路线

### CNN 与局部表征

IDE（ID-discriminative Embedding，身份判别嵌入）以身份分类学习全局类别边界，triplet loss（三元组损失）则直接约束同身份和异身份样本的相对距离；二者通常联合使用，不是前后替代关系。

PCB（Part-based Convolutional Baseline，基于部件的卷积基线）在特征图上执行固定水平分区，RPP（Refined Part Pooling，精炼部件池化）再软分配不一致的局部向量；MGN（Multiple Granularity Network，多粒度网络）联合全局、二分区和三分区分支。水平条带依赖人体大致对齐，多分支拼接也会提高嵌入维度和检索成本。

BoT（Bag of Tricks，训练策略集合）把数据增强、BNNeck、分类和度量损失等策略组合成强全局基线，本身不是主干。OSNet（Omni-Scale Network，全尺度网络）则通过多感受野分支、输入相关的统一聚合门和轻量卷积设计 ReID 专用主干，适合资源受限部署。

### Transformer

TransReID 使用纯 ViT 主干：重叠 patch 保留更多相邻区域信息；JPM（Jigsaw Patch Module，拼图式 patch 模块）通过 shift、shuffle 和 regroup 学习多组局部特征；SIE（Side Information Embedding，侧信息嵌入）将 camera ID 或 viewpoint label 注入 token。全局和局部分支联合使用身份分类与 soft-margin triplet loss（软间隔三元组损失）。

重叠 patch 和全局 - 局部特征拼接会增加计算与嵌入维度；SIE 还要求训练和推理阶段提供语义一致的元数据。TransReID 是有监督下游方法，使用 LUPerson 自监督初始化的 TransReID-SSL 属于另一种预训练范式。

### 工程框架

FastReID 把数据与输入、backbone（主干）、pooling/head（池化/任务头）、loss（损失）、优化器、评测和模型导出组织为可配置组件。引用或部署时必须绑定具体配置与权重，并记录输入归一化、嵌入维度、BNNeck 前后特征、L2 normalization（L2 归一化）和运行时精度；“FastReID”本身没有唯一性能。

### 人体域预训练

人体域预训练（human-centric pre-training 或 person-domain pre-training）不是单一算法，而是一类领域专用预训练策略：预训练数据主要由人体裁剪图构成，学习目标围绕外观、人体局部、姿态和遮挡设计，再把所得主干权重迁移到具体 ReID 任务。这里的“人体域”不表示已经在目标门店上训练，也不等于目标域适配。

其标准流程是：

1. 从视频或图像中构建无标签、tracklet 弱标签或人工身份标注的人体裁剪数据；
2. 使用 MoCo、DINO、MIM 或噪声标签学习 ResNet、ViT、Swin 等主干；
3. 在下游 ReID 数据上用 ID loss、triplet loss、无监督聚类或 UDA（Unsupervised Domain Adaptation，无监督域适配）继续适配；
4. 在独立目标域按固定 query-gallery 协议验证，而不是把预训练权重直接视为零样本 ReID 模型。

LUPerson 是无人工身份标签的人体图像预训练数据集，不是嵌入模型。其原始工作使用针对 ReID 调整的 MoCoV2（Momentum Contrast v2，动量对比学习第二版）；TransReID-SSL 则在 LUPerson 上采用 DINO（Self-Distillation with No Labels，无标签自蒸馏）、ICS（IBN-based Convolution Stem，基于 IBN 的卷积 stem）和 CFS（Catastrophic Forgetting Score，灾难性遗忘评分）数据选择。LUPerson-NL 是由视频 tracklet 自动产生噪声伪身份的数据变体，对应 PNL（Pre-training with Noisy Labels，噪声标签预训练）方法，而不是 TransReID-SSL 的训练数据。

SOLIDER（Semantic cOntrollable seLf-supervIseD lEaRning，语义可控自监督学习）在 DINO 表示上增加 token 级人体语义监督和语义控制器；PersonViT 增加 patch-level MIM（Masked Image Modeling，掩码图像建模）以学习局部细粒度表示。两者都需要下游 ReID 微调，不能把自监督预训练等同于直接零样本检索。

### 自监督、语义增强与视觉 - 语言适配

这三者不是互斥的模型分支，而是描述不同维度：自监督说明预训练信号不依赖人工身份标签；语义增强说明模型额外学习人体结构或部位；视觉 - 语言适配说明初始化来自图文预训练，并通过 ReID 目标转换为身份判别表示。

- **SOLIDER**：人体域预训练 + DINO 自监督 + 人体伪语义约束；
- **PersonViT**：人体域预训练 + DINO 自监督 + patch-level MIM；
- **CLIP-ReID**：通用视觉 - 语言预训练 + 有监督 ID-specific prompt 和 ReID 微调；
- **KPR**：SOLIDER 初始化 + 关键点 prompt + 部件监督，属于遮挡专项下游方法。

CLIP-ReID 是 CLIP 初始化的**有监督 ReID 适配方法**。它需要源训练集身份标签学习 ID-specific prompt，再微调图像编码器；在没有新店身份标签时可以测试跨域直接迁移，但不能称为 zero-shot ReID 训练方法。

KPR（Keypoint Promptable Re-Identification，关键点可提示重识别）使用正负人体关键点指定检测框中的目标人物，并结合 SOLIDER 预训练的 Swin 主干处理多人同框和严重遮挡。它要求可靠的关键点输入或上游姿态模型。

### 跨域训练设置

- **Direct transfer（直接迁移）**：源域训练后固定参数，直接在未参与训练的目标域评测；它是评测设置，不等于专门的零样本训练方法。
- **DG（Domain Generalization，域泛化）**：训练时不使用目标域数据，目标是在不可见新域保持性能。
- **UDA（Unsupervised Domain Adaptation，无监督域适配）**：使用有标注源域和无身份标注目标域，通常通过聚类伪标签、教师 - 学生更新或对比学习得到目标域专用模型。
- **USL（Unsupervised Learning，无监督学习）**：不使用有标注 ReID 源域，直接在无身份标注目标域上学习，但仍可采用 ImageNet 或人体域预训练权重。

人体域预训练提供初始化，UDA/USL 负责具体目标域适配，两者可以串联。跨域报告必须说明源域、目标域、训练时是否使用目标域图像，并防止目标域测试身份标签参与选模或早停。

## 评价口径

- **CMC Rank-k**：Cumulative Matching Characteristic Rank-k，前 k 个结果至少包含一个真匹配的 query 比例；
- **mAP**：mean Average Precision，所有有效 query 的平均排序精度；
- **mINP**：mean Inverse Negative Penalty，关注最难正确匹配在排序中的位置；
- **re-ranking**：利用近邻关系进行重排序，通常提高 mAP，但增加延迟，不能与无重排序结果直接比较。

论文数字必须同时记录数据集、主干、输入尺寸、预训练权重、camera/view 信息、single-query 协议以及是否 re-ranking。生产阈值判定还应评估 TPR@FPR（True Positive Rate at a fixed False Positive Rate，固定误报率下的真正率）；开放集识别可评估 DIR@FAR（Detection and Identification Rate at a fixed False Alarm Rate，固定虚警率下的检测识别率）。`mCP` 不是 person ReID 通用标准指标。

## 选型边界

| 场景               | 候选                                                               | 关键限制                                                |
| ------------------ | ------------------------------------------------------------------ | ------------------------------------------------------- |
| 边缘端、低延迟     | OSNet、FastReID 的 ResNet-50/R50-IBN 配置                          | 必须在目标硬件测量端到端延迟、吞吐、显存和量化掉点。    |
| 云端、域内标注充分 | SOLIDER Swin、PersonViT、TransReID-SSL 初始化的 ViT                | 精度上限较高，训练和部署成本也更高。                    |
| 新店无身份标注     | 固定源域模型做 direct transfer 基线，再评估 UDA/USL 或伪标签自训练 | CLIP-ReID 可作为候选，但不能替代目标域验证。            |
| 多人同框、重遮挡   | KPR + SOLIDER                                                      | 依赖关键点 prompt，输入和推理链更复杂。                 |
| 快速工程基线       | FastReID + 明确配置名                                              | 不得只写“FastReID”，需记录 backbone、loss、尺寸和权重。 |

## 生产评测原则

学术基准主要是闭集 query-gallery 检索，与门店持续出现新身份的开放环境不同。私有评测应按门店、摄像头、月份和遮挡等级分层，防止同一轨迹泄漏到训练和测试两侧，并覆盖制服相似、强逆光、半身、多人同框、检测框偏移和低分辨率样本。

跨域评测必须固定同一个源域模型，再测试多个未参与训练的目标域。分别在每个数据集训练后比较测试数字，只能说明域内性能，不能证明 domain generalization（域泛化）。最终上线决策应同时考虑 Rank-1、mAP、业务阈值指标、延迟、吞吐、显存、模型体积和量化后的精度变化。
