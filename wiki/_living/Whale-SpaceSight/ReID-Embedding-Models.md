---
title: ReID Embedding Models
created: 2026-05-26
updated: 2026-07-16
---

# ReID Embedding 模型选型与演进

本文记录线下门店行人重识别（Person Re-Identification，**ReID**）系统中特征嵌入模型的技术谱系、代表方法、评测口径与部署选型。ReID 系统本体见 `ReID-Pipeline-Architecture.md`；本文不讨论行人检测、轨迹关联、跨帧 ID 分配或聚类策略。

## 1. 问题定义

ReID 特征模型接收一张行人裁剪图，输出固定维度的嵌入向量（embedding）。训练目标是提高类内紧致性（同一身份的向量更接近）与类间可分性（不同身份的向量更远离）。推理时通常使用余弦距离或欧氏距离完成 query-gallery 检索、相似度判定或下游聚类。

这里需要区分四类对象：

- **方法或模型**：PCB、MGN、BoT、OSNet、TransReID、CLIP-ReID、SOLIDER、KPR、PersonViT；
- **主干网络**（backbone）：ResNet、OSNet、Vision Transformer、Swin Transformer；
- **预训练数据或范式**：ImageNet 监督预训练、LUPerson 自监督预训练、LUPerson-NL 噪声标签预训练、CLIP 视觉 - 语言预训练；
- **工程框架**：FastReID。框架本身没有唯一的主干、损失函数或性能数字，必须绑定具体配置讨论。

## 2. 术语与评价指标

### 2.1 模型与训练术语

| 术语                                 | 解释                                                                                                                                                                                                                                                              |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CNN**                              | Convolutional Neural Network，卷积神经网络。ResNet、OSNet 属于 CNN 主干。                                                                                                                                                                                         |
| **ViT**                              | Vision Transformer，将图像划分为 patch token 后用 Transformer 编码。                                                                                                                                                                                              |
| **Swin Transformer**                 | Shifted Window Transformer，使用分层特征图与移位窗口注意力的视觉 Transformer。                                                                                                                                                                                    |
| **IDE**                              | ID-discriminative Embedding，身份判别嵌入；以训练身份分类任务学习全局特征的经典 ReID 范式。                                                                                                                                                                       |
| **PCB / RPP**                        | Part-based Convolutional Baseline / Refined Part Pooling，基于部件的卷积基线 / 精炼部件池化。                                                                                                                                                                     |
| **MGN**                              | Multiple Granularity Network，多粒度网络；联合学习全局、二分区和三分区特征。                                                                                                                                                                                      |
| **BoT**                              | Bag of Tricks，训练策略集合；这里特指 2019 年的 ReID strong baseline。                                                                                                                                                                                            |
| **OSNet**                            | Omni-Scale Network，全尺度网络；以多分支卷积和动态聚合学习不同感受野。                                                                                                                                                                                            |
| **ID loss / CE loss**                | Identity classification loss / Cross-Entropy loss，把训练集中的每个身份视为一个类别进行交叉熵监督；推理时通常丢弃分类器。                                                                                                                                         |
| **Triplet loss**                     | 三元组损失，用 anchor、positive、negative 约束同身份距离小于异身份距离；batch-hard 表示在批次内选择最难正样本和最难负样本。                                                                                                                                       |
| **Center loss**                      | 中心损失，学习每个训练身份的特征中心并惩罚样本到对应中心的距离。                                                                                                                                                                                                  |
| **BNNeck**                           | Batch Normalization Neck，在嵌入与 ID 分类器之间加入批归一化层，使度量学习特征与分类特征承担不同约束。                                                                                                                                                            |
| **IBN**                              | Instance-Batch Normalization，在通道维混合 Instance Normalization 与 Batch Normalization，以兼顾外观不变性和身份判别性。                                                                                                                                          |
| **GeM**                              | Generalized Mean Pooling，广义均值池化，可学习地调节平均池化与最大池化之间的聚合方式。                                                                                                                                                                            |
| **SSL**                              | Self-Supervised Learning，自监督学习，在没有人工身份标签的预训练数据上构造监督信号。                                                                                                                                                                              |
| **DINO**                             | Self-Distillation with No Labels，一种无标签教师 - 学生自蒸馏方法，教师参数由学生参数的指数移动平均更新。                                                                                                                                                           |
| **MIM**                              | Masked Image Modeling，掩码图像建模，通过预测被遮蔽 patch 的表示学习局部结构。                                                                                                                                                                                    |
| **CLIP**                             | Contrastive Language-Image Pre-training，利用图文对进行对比式视觉 - 语言预训练。                                                                                                                                                                                    |
| **JPM**                              | Jigsaw Patch Module，TransReID 中通过 shift、shuffle 和 regroup 生成局部 patch 组的模块。                                                                                                                                                                         |
| **SIE**                              | Side Information Embedding，把 camera ID 或 viewpoint label 等非视觉侧信息编码进 token；它缓解摄像头或视角偏差，但要求相应元数据可用。                                                                                                                            |
| **OLP**                              | Overlapping Patches，以小于 patch size 的步长提取重叠 patch，从而提高空间分辨率并增加计算量。                                                                                                                                                                     |
| **CFS**                              | Catastrophic Forgetting Score，TransReID-SSL 用于选择与下游域更相关的预训练图像的数据评分。                                                                                                                                                                       |
| **DG / UDA / USL**                   | Domain Generalization / Unsupervised Domain Adaptation / Unsupervised Learning，域泛化 / 无监督域适配 / 无监督学习。DG 在训练时不接触目标域；UDA 使用有标注源域和无身份标注目标域；ReID 文献中的 USL 通常不使用有标注 ReID 源域，而直接在无身份标注目标域上学习。 |
| **Direct transfer**                  | 直接迁移；在源域完成训练后固定模型参数，直接到未参与训练的目标域评测。它是一种评测设置，不等同于专门的 zero-shot（零样本）训练方法。                                                                                                                              |
| **MoCo / InfoNCE**                   | Momentum Contrast / Information Noise-Contrastive Estimation，使用动量编码器和对比目标学习无标签表示的框架及其常用损失。                                                                                                                                          |
| **PNL**                              | Pre-training with Noisy Labels，利用自动 tracklet 噪声标签进行预训练的方法。                                                                                                                                                                                      |
| **SOLIDER**                          | Semantic cOntrollable seLf-supervIseD lEaRning，语义可控自监督学习框架。                                                                                                                                                                                          |
| **KPR / BIPO**                       | Keypoint Promptable Re-Identification / Batch-wise Inter-Person Occlusion，关键点可提示重识别 / 批次级人物间遮挡增强。                                                                                                                                            |
| **PK sampling**                      | 每个 mini-batch 采样 P 个身份、每个身份 K 张图像的身份均衡采样。                                                                                                                                                                                                  |
| **SGD / Adam**                       | Stochastic Gradient Descent / Adaptive Moment Estimation，随机梯度下降 / 自适应矩估计优化器。                                                                                                                                                                     |
| **Query / gallery**                  | Query 是待检索样本，gallery 是候选样本库；标准 ReID 评测会按协议过滤无效的同摄像头同身份样本。                                                                                                                                                                    |
| **Tracklet**                         | 同一目标在一段连续视频帧中的短轨迹及对应图像序列；自动生成的 tracklet ID 可能包含身份切换或轨迹断裂。                                                                                                                                                             |
| **Prompt**                           | 提示信息；CLIP-ReID 使用可学习文本 token，KPR 使用人体关键点，二者不是同一种提示形式。                                                                                                                                                                            |
| **Random erasing / label smoothing** | 随机擦除 / 标签平滑；前者遮挡随机图像区域，后者降低 one-hot 分类目标的过度置信。                                                                                                                                                                                  |
| **SBS**                              | Stronger Baseline，FastReID 在 BoT 之上加入 GeM、Non-local、CircleSoftmax 等组件的增强基线配置。                                                                                                                                                                  |
| **Head / L2 normalization**          | Head 是连接主干特征与训练目标或输出嵌入的任务头；L2 normalization（L2 归一化）将向量除以其二范数，使其具有单位长度。                                                                                                                                              |
| **ONNX / FP16 / INT8**               | Open Neural Network Exchange / 16-bit floating point / 8-bit integer，开放神经网络交换格式 / 16 位浮点精度 / 8 位整数精度。                                                                                                                                       |

### 2.2 评价指标与报告约定

- **CMC Rank-k**：Cumulative Matching Characteristic Rank-k；对每个 query，统计前 k 个检索结果中是否至少包含一个有效真匹配，再对全部 query 求比例。Rank-1 是最常用的识别率。
- **AP / mAP**：Average Precision / mean Average Precision；AP 衡量单个 query 的完整排序质量，mAP 是全部有效 query 的 AP 均值。
- **mINP**：mean Inverse Negative Penalty；关注每个 query 最后一个正确匹配出现的位置，对困难正样本更敏感。
- **Single-query**：每张 query 独立检索，不把同身份、同摄像头下的多张 query 特征预先聚合。
- **Re-ranking**：重排序；利用初始近邻关系重新计算排序。它通常显著提高 mAP，但会增加延迟，且其结果不能与无重排序结果直接比较。
- **SOTA**：State of the Art，仅表示在论文发表时、指定数据集和指定协议下的最佳公开结果，不代表跨域或生产性能。

本文的性能表统一写成 **mAP / Rank-1（%）**。除非单独说明，均引用作者报告的 single-query、without re-ranking 结果；这些数字没有在本项目环境中复现。不同主干、输入尺寸、预训练数据、camera ID 使用方式和实现框架仍可能影响可比性。

生产环境若涉及阈值判定或开放集识别，还应补充 TPR@FPR（True Positive Rate at a fixed False Positive Rate）或 DIR@FAR（Detection and Identification Rate at a fixed False Alarm Rate）。`mCP` 不是 person ReID 的通用标准指标，除非项目内部另行给出严格定义，否则不应作为学术对标指标。

## 3. 正确的技术演进谱系

ReID 的演进不是单一模型链。主干结构、局部建模、预训练信号、目标域数据使用方式和工程框架属于不同维度，可以组合在同一个系统中：

```text
表征结构：全局 CNN（IDE、batch-hard triplet）
          ├─ 固定部件与多粒度：PCB/RPP → MGN
          ├─ 强全局训练配方：BoT
          ├─ ReID 专用轻量主干：OSNet
          ├─ 全局 - 局部 Transformer：TransReID
          └─ 关键点提示与遮挡建模：KPR

预训练信号：ImageNet 监督预训练
          ├─ 人体域自监督：LUPerson/MoCoV2 → TransReID-SSL
          │                 ├─ 语义可控表示：SOLIDER
          │                 └─ patch 级 MIM：PersonViT
          ├─ 人体域噪声标签：LUPerson-NL → PNL
          └─ 通用视觉 - 语言预训练：CLIP → CLIP-ReID

目标域数据使用：direct transfer / DG
          ├─ 有标注源域 + 无标注目标域：UDA
          └─ 无标注目标域学习：USL

工程实现层：FastReID，独立承载不同主干、head（任务头）、loss（损失）和训练配方
```

图中的箭头只表示同一维度内的代表性演进或派生关系，不表示后一方法全面取代前一方法。例如 BoT 是训练配方，OSNet 是主干网络，FastReID 是工程框架；三者可以组合，而不是同层级竞争模型。

### 3.1 全局、局部与多粒度 CNN

早期深度 ReID 通常采用 ID-discriminative embedding（IDE，身份判别嵌入），把训练集中的每个身份视为一个分类类别。身份分类交叉熵学习全局类别边界；triplet loss 则直接约束 anchor、positive 和 negative 在嵌入空间中的相对距离。二者不是前后替代关系：batch-hard mining（批内难样本挖掘）推动 triplet loss 成为主流度量学习配置后，ID loss 与 triplet loss 的联合训练逐渐成为强基线的常见做法。

PCB 在卷积特征图上执行固定水平分区，并为各分区设置身份分类监督；RPP 再把与原分区不一致的列向量按相似度软分配到更合适的部件。MGN 则在 ResNet-50 后段建立一条全局分支和二分区、三分区局部分支，测试时拼接多路特征。它们说明局部线索可以补充全局外观，但也隐含人体大致对齐的假设：检测框偏移、姿态变化或遮挡会使水平条带对应到错误部位；多分支和特征拼接还会增加训练显存、嵌入维度及检索存储成本。

2019 年形成两条不同的工程路线。BoT 不是新主干，而是把 warm-up（学习率预热）、random erasing、label smoothing、last stride（末阶段下采样步长）、BNNeck、ID loss、triplet loss 和 center loss 等策略组织为可复现的 ResNet-50 强基线；BNNeck 让分类目标和度量目标作用于不同表示，缓解二者对特征空间的约束冲突。OSNet 则设计 ReID 专用的 omni-scale CNN（全尺度卷积网络）：不同卷积分支覆盖不同感受野，unified aggregation gate（统一聚合门）根据输入生成通道级权重，再用 pointwise/depthwise convolution（逐点卷积/逐通道卷积）控制参数量。BoT 代表训练配方优化，OSNet 代表轻量主干设计；二者都不自动解决目标域偏移。

### 3.2 工程框架：FastReID

FastReID 是可配置的 ReID 研究与部署框架，不是 BoT 的下一代单一模型。它把数据、网络、损失、优化、评测和导出组织为可替换组件，使研究者可以在相同代码路径中复现 BoT、SBS、MGN 等配方，并切换 ResNet、IBN、OSNet、ViT 等主干。

一个可复现的 FastReID 模型至少应记录以下配置层：

| 配置层                          | 必须记录的内容                                                         | 对结果或部署的影响                                             |
| ------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------- |
| 数据与输入                      | 数据划分、采样器、输入尺寸、归一化、数据增强                           | 决定训练分布，也必须与推理预处理保持一致。                     |
| 主干与预训练                    | backbone、last stride、IBN、Non-local（非局部块）、预训练权重          | 决定特征图、参数量和初始化，不兼容权重不能直接替换。           |
| Pooling 与 head（池化与任务头） | pooling、embedding dimension（嵌入维度）、BNNeck、neck feature         | 决定最终向量的维度和语义；必须明确导出 BNNeck 前还是后的特征。 |
| 损失与优化                      | 分类头、ID/metric loss、hard mining、优化器和学习率计划                | 同一主干可以因训练配方不同产生显著性能差异。                   |
| 评测与后处理                    | 距离函数、L2 normalization（将向量除以其二范数）、过滤协议、re-ranking | 决定论文数字和线上相似度是否可比。                             |
| 导出与运行时                    | Caffe/ONNX/TensorRT、静态或动态 batch、FP32/FP16/INT8                  | 影响算子兼容性、吞吐、延迟及量化精度。                         |

因此，引用 FastReID 的性能必须绑定配置和权重，例如 `SBS(R50-IBN)`。官方仓库提供 Caffe、ONNX、TensorRT 转换示例，只说明存在部署路径，不保证所有自定义主干、head 和算子都能无差异导出；部署前仍需比较原框架与目标运行时的嵌入向量和检索结果。

### 3.3 Transformer: TransReID

TransReID 是首批成功将纯 ViT 系统用于对象 ReID 的代表工作。ViT 将图像切分为 patch token，并通过 self-attention（自注意力）建模远距离区域关系；相较只依赖局部卷积核的 CNN，这种结构更容易直接建立上衣、鞋、随身物品等远隔区域之间的关系。ViT-B/16 权重来自 ImageNet-21K 预训练并在 ImageNet-1K 微调，DeiT-B/16 则使用 ImageNet-1K 预训练。

TransReID 在分类 ViT 基线之上增加三个与 ReID 直接相关的设计：

| 组件                                          | 工作方式                                                                                 | 作用与限制                                                                                     |
| --------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Overlapping Patches（重叠 patch）             | patch 提取步长（stride）小于 patch size，使相邻 token 共享部分像素                       | 减少非重叠切块导致的邻域信息断裂，但 token 数增加会提高注意力计算量。                          |
| JPM（Jigsaw Patch Module，拼图式 patch 模块） | 对 patch token 执行 shift、shuffle 和 regroup，再通过共享 Transformer 层学习多组局部特征 | 让局部分支覆盖不同人体区域并保留全局判别信息；拼接全局和局部特征会提高嵌入维度与检索成本。     |
| SIE（Side Information Embedding，侧信息嵌入） | 将 camera ID、viewpoint label 等可学习嵌入与 patch、位置嵌入共同送入编码器               | 缓解摄像头和视角偏差，但训练和推理必须提供语义一致的元数据；跨门店 camera 编码不能无条件复用。 |

全局分支和 JPM 局部分支均采用 ID cross-entropy loss 与 soft-margin triplet loss（软间隔三元组损失）联合训练，论文的最佳组合不使用 label smoothing。TransReID 本身是有监督下游方法，不应与使用 LUPerson 自监督初始化的 TransReID-SSL 混为同一训练范式。它也说明纯 ViT 对初始化和局部结构设计较敏感，从而自然引出后续人体域自监督预训练。论文所称 MSMT17 和 DukeMTMC-reID 的 `+5.5/+2.1 mAP` 是相对当时公开最佳方法，而不是相对统一 CNN baseline。

### 3.4 人体域预训练

人体域预训练（human-centric pre-training 或 person-domain pre-training）**不是一种具体算法，而是一类领域专用预训练策略**。这里的“人体域”表示预训练数据主要由行人检测框或人体裁剪图构成，数据分布与下游 ReID 更接近；它不表示模型已经在目标门店数据上完成训练，也不等同于 target-domain adaptation（目标域适配）。

通用 ImageNet 预训练主要学习物体类别之间的差异，常使用接近方形的自然图像；人体域预训练则持续接触竖长人体裁剪、服装颜色、随身物品、身体局部、姿态、视角和遮挡等细粒度线索。它试图缩小 pre-training domain 与 ReID domain 之间的数据和任务差异，使主干网络在下游微调前就具备更适合身份区分的表示。

典型流程如下：

| 阶段            | 主要操作                                            | 可用监督信号                                          | 产物                                     |
| --------------- | --------------------------------------------------- | ----------------------------------------------------- | ---------------------------------------- |
| 1. 人体数据构建 | 从街景、视频或业务数据中检测并筛选人体裁剪图        | 无标签、视频时序、自动 tracklet 或人工身份标签        | LUPerson、LUPerson-NL 或私有人体预训练集 |
| 2. 领域预训练   | 用对比学习、教师 - 学生自蒸馏、MIM 或噪声标签学习主干 | 同图不同增强、动量教师、被遮蔽 patch、tracklet 伪身份 | ResNet、ViT 或 Swin 的人体域预训练权重   |
| 3. ReID 适配    | 在具体 ReID 数据集上训练 embedding head 和主干      | ID CE、triplet loss、无监督聚类或 UDA 伪标签          | 可用于检索的 ReID 嵌入模型               |
| 4. 目标域验证   | 固定模型，在未参与训练的门店或数据集上测试          | query-gallery 标注或相似对标注                        | Rank-1、mAP、TPR@FPR 和跨域下降幅度      |

人体域预训练包含多种实现，不应把它们写成同一个“LUPerson 模型”：

| 代表路线          | 预训练数据                        | 核心预训练方法                         | 主要特征                                                                      |
| ----------------- | --------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------- |
| LUPerson + MoCoV2 | 无标签 LUPerson                   | 实例级对比学习                         | 面向 ResNet，强调服装颜色和实例区分；去除 color jitter，加入 random erasing。 |
| LUPerson-NL + PNL | 带噪声 tracklet ID 的 LUPerson-NL | 分类、原型对比、标签引导对比和标签校正 | 利用视频时序作为弱监督，但需要处理身份切换和轨迹断裂噪声。                    |
| TransReID-SSL     | 无标签 LUPerson                   | DINO + CFS + ICS                       | 面向 ViT，兼顾自蒸馏、数据筛选和 ReID 专用卷积 stem。                         |
| SOLIDER           | 无标签 LUPerson                   | DINO + token 级伪语义监督              | 在外观表示之外加入人体部位语义，并通过控制器调节语义比例。                    |
| PersonViT         | 无标签 LUPerson                   | DINO + patch-level MIM                 | 强化局部 patch 和被遮挡人体部位的细粒度表示。                                 |

该策略的主要收益是减少通用图像预训练与 ReID 之间的 domain gap，并提高小规模标注集上的微调效率。其限制也很明确：预训练本身计算成本高；网络结构、输入归一化和预训练权重必须兼容；人体预训练数据仍可能带来场景或人群偏差；最重要的是，**人体域预训练权重仍需下游适配和目标域验证，不能直接视为生产可用的零样本 ReID 模型**。

LUPerson 包含 4,180,243 张无人工身份标注的行人图像，论文估计覆盖 20 万以上人物。原始工作使用针对 ReID 调整的 MoCoV2：移除会破坏服装颜色线索的 color jitter，加入 random erasing，并调整对比损失温度。LUPerson 是数据资源；“LUPerson 方法”的性能必须同时注明下游网络，例如 LUPerson 预训练的 MGN。

LUPerson-NL 从原始视频 tracklet 自动构造 10,683,716 张图像和约 433,997 个噪声 tracklet ID。这里的 ID 是自动跟踪产生的伪身份，不等价于跨摄像头人工身份标注。对应的 PNL（Pre-training with Noisy Labels）联合分类、原型对比、标签引导对比和标签校正进行预训练。

TransReID-SSL 使用的是无标签 LUPerson，而不是 LUPerson-NL。它比较 MoCoV3、MoBY 和 DINO 后选择 DINO，引入 CFS 数据选择与 ICS（IBN-based Convolution Stem，基于 IBN 的卷积 stem）。这条路线说明人体域自监督预训练对 ViT 尤其重要。

### 3.5 监督信号与表示约束：自监督、语义增强与视觉 - 语言适配

自监督、语义增强和视觉 - 语言适配不是三种互斥的主干架构，也不是严格按时间前后替代的模型分支。它们描述的是三个不同问题：**预训练监督从哪里来、希望表示保留什么信息、如何把预训练知识适配到身份检索**。同一个项目可以同时使用其中多个维度。

| 维度               | 核心问题                             | 常见监督或目标                                            | 代表项目                                           | 对 ReID 的作用与限制                                                                                   |
| ------------------ | ------------------------------------ | --------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **自监督预训练**   | 没有人工身份标签时如何学习表示       | 同图不同增强的一致性、教师 - 学生自蒸馏、MIM                | LUPerson+MoCoV2、TransReID-SSL、PersonViT、SOLIDER | 学习外观不变性和局部结构；“自监督”只描述预训练阶段，下游仍可采用有监督 ID loss 和 triplet loss。       |
| **语义增强**       | 如何显式学习人体结构和部位对应关系   | 伪部位标签、人体解析标签、part prediction                 | SOLIDER、KPR                                       | 有助于局部对齐、遮挡和多人歧义；人体语义并不等于身份信息，语义权重过高可能削弱服装纹理等身份判别线索。 |
| **视觉 - 语言适配**  | 如何迁移大规模图文预训练知识         | 图文对比、可学习文本 prompt、image-to-text classification | CLIP-ReID                                          | 引入服装、物品等通用语义先验；ReID 身份是索引而非自然语言类别，因此仍需身份标签完成任务适配。          |
| **提示式目标消歧** | 一个框中出现多人时如何指定待识别目标 | 正负关键点 prompt、部件可见性、遮挡增强                   | KPR                                                | 直接解决 multi-person ambiguity；依赖可靠姿态关键点，属于下游输入与结构设计，不是独立预训练范式。      |

按照这个分类，几个容易混淆的项目可以概括为：

- **SOLIDER = 人体域预训练 + 自监督 DINO + 人体伪语义约束**。它在 LUPerson 上以 DINO 为基础，增加 token-level semantic classification（token 级语义分类）和连续语义控制器。ReID 更依赖外观差异，因此下游使用较低语义权重；属性识别、人体解析等任务可以提高语义权重。
- **PersonViT = 人体域预训练 + 自监督 DINO + patch-level MIM**。它不依赖人工部位标签，而是通过恢复被遮蔽 patch 的教师表示强化局部细粒度建模。
- **CLIP-ReID = 通用视觉 - 语言预训练 + 有监督 ReID 适配**。CLIP 提供初始化，ID-specific prompt 和下游 ReID 损失负责把通用语义空间转成身份判别空间。
- **KPR = SOLIDER 人体域初始化 + 关键点提示 + 部件监督**。它是遮挡 ReID 的专项下游方法，不应与 DINO、MIM 或 CLIP 作为同层级预训练算法并列。

CLIP-ReID 不是零样本 ReID 方法。第一阶段冻结 CLIP 图像编码器和文本编码器，利用训练集身份标签为每个 ID 学习 prompt token；第二阶段冻结文本侧和 prompt，仅微调图像编码器。未经目标域标注的直接迁移属于 cross-domain direct transfer（跨域直接迁移），任何 ReID 模型都可以这样测试，但不能据此把 CLIP-ReID 称为无监督或零样本训练方法。

KPR（Keypoint Promptable Re-Identification，关键点可提示重识别）使用正负人体关键点明确同一检测框中的目标人物，专门解决 multi-person ambiguity（多人歧义）和严重遮挡。它要求可靠的关键点输入或上游姿态模型，因此部署成本和输入契约都不同于普通单图 ReID 编码器。

### 3.6 域泛化与目标域适配

人体域预训练解决“如何获得更适合 ReID 的初始化”，而域泛化与目标域适配解决“模型如何从源场景迁移到具体目标场景”。这些术语描述训练数据可用条件和评测协议，不是某一种固定主干或损失函数。

| 设置                | 有标注 ReID 源域     | 训练时使用无标注目标域 | 典型做法                                             | 正确解释                                                                           |
| ------------------- | -------------------- | ---------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------- |
| **Direct transfer** | 是                   | 否                     | 源域监督训练后固定模型，直接评测目标域               | 最基本的跨域基线；只是评测设置，不能单凭该结果把模型称为零样本方法。               |
| **DG**              | 是，通常可有多个源域 | 否                     | 跨源域不变性、风格扰动、元学习或域特定归一化         | 目标是在训练时不可见的新域保持性能；必须固定源域训练模型比较多个目标域。           |
| **UDA**             | 是                   | 是                     | 聚类伪标签、教师 - 学生更新、对比学习和相机感知校正    | 产生目标域专用模型；因为使用了目标域图像，不能称为 target-free（目标域无关）泛化。 |
| **USL**             | 否                   | 是                     | 在目标域反复进行特征提取、聚类、伪标签训练和噪声抑制 | 不使用人工身份标签，但通常仍可使用 ImageNet 或人体域预训练权重。                   |

这几种设置可以共享同一主干和预训练权重。例如，一个 SOLIDER 预训练的 Swin 可以先在有标注源域监督微调，再做 direct transfer，也可以继续使用无标注目标门店数据进行 UDA。其完整链路应写成“预训练初始化 → 源域或目标域下游训练 → 固定协议评测”，不能只用模型名称推断监督条件。

UDA 和 USL 的主要风险来自聚类伪标签噪声：错误近邻会在迭代训练中被强化，摄像头、时间和服装偏差也可能被模型当成身份线索。目标域测试身份标签只能用于最终评测，不能参与伪标签筛选、超参数选择或早停；否则会形成 test-set leakage（测试集泄漏）。跨域结果还必须同时注明源域、目标域、是否使用目标域训练图像，以及是否重新训练分类 head（分类任务头）。

## 4. 代表项目配置与标称性能

数据集缩写：`M` = Market-1501，`MS` = MSMT17，`D` = DukeMTMC-reID，`O` = Occluded-Duke。DukeMTMC-reID 仅作为历史学术基准理解。

| 代表项目                                                                             | 类型与主干模型                            | 训练策略                                                                                                                                                                          | 损失函数                                                                                                            | 评价指标                        | 作者标称性能（mAP / Rank-1，%）                                     |
| ------------------------------------------------------------------------------------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------- |
| [PCB+RPP (ECCV 2018)](https://arxiv.org/abs/1711.09349)                              | 方法；ImageNet 预训练 ResNet-50           | `384×128`；特征图水平六分区；PCB 训练 60 epochs，再用 10 epochs 进行 RPP 诱导训练                                                                                                 | 各部件 ID cross-entropy loss 之和                                                                                   | CMC Rank-1、mAP                 | M `81.6 / 93.8`；D `69.2 / 83.3`                                    |
| [MGN (ACM MM 2018)](https://arxiv.org/abs/1804.01438)                                | 方法；ResNet-50 三分支                    | `384×128`；全局分支、二分区分支、三分区分支；PK sampling；SGD 80 epochs                                                                                                           | ID softmax CE + margin triplet loss                                                                                 | CMC Rank-1、mAP                 | M `86.9 / 95.7`；D `78.4 / 88.7`                                    |
| [BoT (CVPRW 2019)](https://arxiv.org/abs/1903.07071)                                 | 强基线；ImageNet 预训练 ResNet-50         | `256×128`；PK sampling、random erasing、label smoothing、last stride=1、BNNeck；Adam 120 epochs；warm-up 后分段衰减                                                               | ID CE + batch-hard triplet（margin 0.3）+ center loss                                                               | CMC Rank-1、mAP                 | M `85.9 / 94.5`；D `76.4 / 86.4`；原论文未报告 MS                   |
| [OSNet (ICCV 2019)](https://arxiv.org/abs/1905.00953)                                | ReID 专用轻量 CNN；OSNet-x1.0             | omni-scale residual block 与统一聚合门；可从头训练或 ImageNet 微调；下列结果采用 ImageNet 预训练、AMSGrad（Adam 变体）微调 150 epochs                                             | 带 label smoothing 的 ID CE；原论文主结果未使用 triplet loss                                                        | CMC Rank-1、mAP                 | M `84.9 / 94.8`；MS `52.9 / 78.7`；D `73.5 / 88.6`                  |
| [FastReID SBS (2020)](https://github.com/JDAI-CV/fast-reid/blob/master/MODEL_ZOO.md) | 框架配置；以官方 `SBS(R50-IBN)` 为代表    | ResNet-50-IBN、Non-local（非局部块）、GeM、CircleSoftmax（带尺度和间隔的相似度分类头）；`384×128`；AutoAugment（自动数据增强）；冻结主干起步；Adam + cosine annealing（余弦退火） | 带 label smoothing 的 CE + hard-mining soft-margin triplet                                                          | CMC Rank-1、mAP、mINP           | M `89.3 / 95.7`；MS `60.6 / 83.9`；D `81.2 / 90.8`                  |
| [LUPerson + MGN (CVPR 2021)](https://arxiv.org/abs/2012.03753)                       | 预训练数据与方法；ResNet-50，MGN 下游     | LUPerson 上改造的 MoCoV2；去除 color jitter、加入 random erasing、temperature=0.07；下游监督微调                                                                                  | 预训练 InfoNCE-style contrastive loss；下游 MGN 的 ID CE + triplet                                                  | CMC Rank-1、mAP                 | M `91.0 / 96.4`；MS `65.7 / 85.5`；D `82.1 / 91.0`                  |
| [TransReID (ICCV 2021)](https://arxiv.org/abs/2102.04378)                            | 方法；ViT-B/16                            | overlapping patches、JPM、SIE；SGD + cosine annealing（余弦退火）；下列结果为 `256×128`、使用 camera ID 的 overlapping-patch 变体                                                 | 全局和局部特征上的 ID CE（无 label smoothing）+ soft-margin triplet                                                 | CMC Rank-1、mAP                 | M `88.9 / 95.2`；MS `67.4 / 85.3`；D `82.0 / 90.7`；O `59.2 / 66.4` |
| [TransReID-SSL (2021)](https://arxiv.org/abs/2111.12084)                             | 预训练方法；ViT-I-S/16，即带 ICS 的 ViT-S | 8×V100、LUPerson 上 DINO 预训练 100 epochs；CFS 选择 50% 数据；`256×128`；下游采用不含 JPM/SIE 的 TransReID baseline                                                              | 预训练 DINO self-distillation loss；下游 ID CE + triplet                                                            | CMC Rank-1、mAP；另报告 UDA/USL | 监督微调：M `91.3 / 96.2`；MS `68.1 / 86.1`                         |
| [LUPerson-NL / PNL (CVPR 2022)](https://arxiv.org/abs/2203.16533)                    | 噪声标签预训练；ResNet-50，MGN 下游       | 8×V100、90 epochs、batch 1536；动量编码器、动态原型与伪标签校正                                                                                                                   | 分类 CE + prototype contrastive loss + label-guided contrastive loss                                                | CMC Rank-1、mAP                 | M `91.9 / 96.6`；MS `68.0 / 86.0`；D `84.3 / 92.0`                  |
| [CLIP-ReID (AAAI 2023)](https://arxiv.org/abs/2211.13977)                            | 有监督适配方法；CLIP ViT-B/16             | 两阶段 ID-specific prompt learning；下列为加入 SIE 和 OLP 的增强变体；全部结果无重排序                                                                                            | 阶段一 image-to-text + text-to-image contrastive loss；阶段二 ID CE + triplet + image-to-text CE                    | CMC Rank-1、mAP                 | M `90.5 / 95.4`；MS `75.8 / 89.7`；D `83.1 / 90.8`；O `60.3 / 67.2` |
| [SOLIDER (CVPR 2023)](https://arxiv.org/abs/2303.17602)                              | 人体域预训练；Swin-T/S/B                  | LUPerson 上先训练 DINO 100 epochs，再以较小学习率训练 SOLIDER 10 epochs；下列为 Swin-B、`384×128` 下游结果                                                                        | 预训练 DINO loss + token-level semantic CE；下游 ID CE + soft-margin triplet                                        | CMC Rank-1、mAP                 | M `93.9 / 96.9`；MS `77.1 / 90.7`                                   |
| [KPR (ECCV 2024)](https://arxiv.org/abs/2407.18112)                                  | 遮挡专项方法；SOLIDER 预训练 Swin-B       | 正/负关键点 prompt、MSF（Multi-Stage Feature Fusion，多阶段特征融合）、PBH（Part-based Head，部件头）、BIPO 增强；120 epochs、batch 64、cosine annealing（余弦退火）              | `L_ReID + 0.3 L_PP`；ReID 部分为 ID loss + batch-hard triplet，PP（Part Prediction，部件预测）为 token-wise part CE | CMC Rank-1、mAP                 | M `93.2 / 96.6`；O `75.1 / 84.3`；Occluded-PoseTrack `81.2 / 90.6`  |
| [PersonViT (2024 preprint)](https://arxiv.org/abs/2408.05398)                        | 自监督预训练；ViT-S/16、ViT-B/16          | LUPerson 上 DINO teacher-student + patch-level MIM，训练计划 300 epochs、主要结果选择约 240 epochs 权重；下列 ViT-B 结果来自大批量配置；下游 BoT 式微调                           | 预训练 `L_DINO + L_MIM`；下游 ID CE + triplet + BNNeck                                                              | CMC Rank-1、mAP                 | M `95.0 / 97.6`；MS `80.8 / 92.0`；D `88.1 / 93.8`；O `72.2 / 79.8` |

## 5. 如何解释这些数字

### 5.1 不能横向忽略的实验变量

- **输入尺寸**：PCB/MGN 常用 `384×128`；BoT/OSNet 常用 `256×128`；TransReID 同时报告两种尺寸；SOLIDER 最佳 ReID 结果使用 `384×128`。
- **侧信息**：TransReID 和 CLIP-ReID 的部分最佳结果使用 camera ID。生产环境若 camera ID 缺失、含义变化或配置错误，结果不能直接复现。
- **预训练规模**：ImageNet-1K、ImageNet-21K、LUPerson、LUPerson-NL 和 CLIP 的数据规模与监督信号完全不同。
- **后处理**：with re-ranking 与 without re-ranking 必须分开报告。本文主表只采用无重排序结果。
- **实现差异**：FastReID 对 MGN、BoT 等方法的复现结果可能高于原论文，不能把框架复现值标成原论文值。

### 5.2 跨域证据的正确表述

CLIP 或 DINOv2 的通用预训练不自动等于可用的 ReID 特征。2026 年一项 11 模型、9 数据集的预印本报告，未经 ReID 微调的 DINOv2 在其 zero-shot 协议下只有 `0.3%-4.7% mAP`，原始 CLIP 也只有约 `0.1%-2.7% mAP`；该结果只说明“直接拿通用编码器做身份检索”效果差，不能否定经过人体域预训练和 ReID 微调的视觉自监督方法。该研究中 CLIP-B 与 CLIP-L 的比较同样针对原始 CLIP，不应外推为 CLIP-ReID 的模型尺寸结论。来源：[Person Re-ID in 2025: Supervised, Self-Supervised, and Language-Aligned. What Works?](https://arxiv.org/abs/2601.20598)。

跨域比较应固定同一个源域训练模型，再在多个未参与训练的目标域上评测。分别在每个数据集训练后再比较其测试集数字，只能说明域内性能，不能证明 domain generalization（域泛化）。

## 6. 生产选型建议

| 场景                   | 优先候选                                                                             | 选择依据与限制                                                                   |
| ---------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| 边缘端、低延迟         | OSNet、FastReID BoT/SBS 的 ResNet-50 或 R50-IBN 配置                                 | CNN 部署链成熟；仍需在目标硬件测量延迟、显存、吞吐和功耗。                       |
| 云端、域内标注充分     | SOLIDER Swin、PersonViT、TransReID-SSL 初始化的 ViT                                  | 人体域预训练提高上限；训练和推理成本更高。                                       |
| 新店无身份标注         | 先做 cross-domain direct transfer（跨域直接迁移）基线，再评估 UDA/USL 或伪标签自训练 | CLIP-ReID 可作为候选初始化，但它本身是有监督方法，不能用“零样本”替代目标域验证。 |
| 多人同框或严重遮挡     | KPR + SOLIDER                                                                        | 需要可靠的正负关键点 prompt 或上游姿态模型；增加输入、标注与推理复杂度。         |
| 快速建立可复现工程基线 | FastReID + 明确配置名                                                                | 必须记录 backbone、loss、输入尺寸、预训练权重、数据划分和导出版本。              |

Transformer 是否慢于 CNN 不能只由 FLOPs（Floating-Point Operations，浮点运算量）推断。上线前应在目标硬件上测量端到端延迟，包括预处理、模型推理、特征归一化、数据传输与批处理等待。ONNX（Open Neural Network Exchange，开放神经网络交换格式）、TensorRT、FP16（16-bit floating point，16 位浮点）或 INT8（8-bit integer，8 位整数）只是部署手段，不保证所有主干获得相同收益；量化后必须重新评估检索质量。

## 7. 私有评测集与上线门槛

学术数据集仍有明显限制：Market-1501 和 DukeMTMC-reID 主要来自校园或街景；MSMT17 场景、光照和摄像头更多，但仍不是零售门店；Occluded-Duke 强调遮挡，但不覆盖所有多人同框、制服相似和店员长期出现问题。query 与 gallery 在测试阶段共享身份，属于闭集检索协议；生产系统通常还包含未登录身份和持续变化的 gallery。

私有评测至少应做到：

- 按门店、摄像头、月份和遮挡等级分层，严格避免同一轨迹片段同时进入训练集与测试集；
- 建立固定的 query-gallery 协议，并记录同摄像头过滤、时间窗口和合法匹配规则；
- 同时报告 Rank-1、mAP、可选 mINP，以及阈值判定下的 TPR@FPR；开放集识别再报告 DIR@FAR；
- 单独统计同服装、店员制服、强逆光、半身、多人同框、检测框偏移和低分辨率样本；
- 报告相对于固定源域模型的跨域绝对性能和下降幅度，不把不同源域训练结果混为一组；
- 将精度、延迟、吞吐、显存、模型体积、量化掉点和训练成本共同纳入上线门槛。

## 8. 演进原则

模型演进可以从四个维度管理，但它们不是完全独立、可无条件互换的轴：

- **主干与局部建模**：ResNet/OSNet → ViT/Swin；全局特征 → 水平分区、多粒度、JPM 或关键点提示；
- **预训练与监督信号**：ImageNet 监督 → LUPerson 自监督 → LUPerson-NL 噪声标签 → CLIP 视觉 - 语言初始化；
- **下游域设置**：不使用目标域训练图像的 direct transfer / DG；使用无标注目标域的 UDA / USL；
- **工程与部署**：训练复现 → 模型导出 → 硬件实测 → 量化与回归评估。

更换主干通常会同时改变输入归一化、位置编码、优化器、学习率、嵌入维度和导出算子；更换预训练权重也必须保证网络结构与预处理兼容。每次升级应只改变一个可验证因素，并在统一私有评测协议下与当前生产模型做消融比较。
