---
title: LMM Input Mechanics
created: 2026-05-15
updated: 2026-07-13
type: concept
tags: [vlm, architecture, transformer]
sources: [_living/AI-Infrastructure/LMM-Input-Mechanics.md]
confidence: high
---

# 多模态大模型输入机制

多模态输入不是把图片、音频或视频文件直接送进文本 tokenizer，而是一条分层变换链：

$$
\text{有序 API 内容块}
\rightarrow\text{字节解码与预处理}
\rightarrow\text{模态编码器}
\rightarrow\text{连接器/重采样器}
\rightarrow\text{排列与融合}
\rightarrow\text{语言模型}
$$

API 层表达用户给出的逻辑顺序；预处理决定模型实际可见的像素、采样点、帧和页面；编码器提取连续特征；连接器对齐特征维度并可能压缩序列；融合拓扑决定文本与媒体在哪些注意力层相互作用。^[[[_living/AI-Infrastructure/LMM-Input-Mechanics|LMM-Input-Mechanics]]]

## “Token”不是一个单义词

多模态系统至少混用四种概念：

1. **文本 Token**：tokenizer 产生的离散词表 ID。
2. **媒体 Token/latent**：编码器产生的连续向量，通常没有文本词表 ID。
3. **序列位置**：参加 self-attention 或 cross-attention 的一行表示。
4. **计量 Token**：provider 用于上下文限制、速率和计费的单位。

因此，“图片占 1000 Token”不推出内部恰有 1000 个视觉向量。计量规则可以按 Patch、Tile、分辨率档位或时长换算，闭源服务的计量也不能唯一反推出内部架构。

## 从媒体到连续表示

图像经方向修正、缩放、裁剪和归一化后，常被分为 $P\times P$ Patch。若输入尺寸为 $H\times W$，加入边界填充后的 Patch 数为：

$$
N=\left\lceil\frac{H}{P}\right\rceil
  \left\lceil\frac{W}{P}\right\rceil
$$

视觉编码器输出 $Z_v\in\mathbb{R}^{N\times d_v}$。连接器用线性层或 MLP 把宽度对齐到语言维度 $d_l$：

$$
H_v=Z_vW_c+b_c,
\qquad W_c\in\mathbb{R}^{d_v\times d_l}
$$

逐位置投影改变特征宽度，不减少 $N$。局部 Token merge 可把长度近似降为 $N/r^2$；带 $M$ 个可学习查询的 resampler/Q-Former 则把任意长度视觉序列压成固定 $M$ 个表示，但形成信息瓶颈。

音频可以先经 STFT 和 log-Mel 变成时频矩阵，也可以由波形编码器直接产生连续 latent，或经神经 Codec 量化成独立音频码本 ID。视频增加时间轴：逐帧 Patch 的长度约为 $FS$，tubelet 则同时在时间与空间下采样。PDF 往往需要文本抽取与页面渲染双通道，因为纯文本会丢版面，纯图像又会增加成本并降低小字精度。

## 排列与拼接必须说明轴

设文本嵌入 $T\in\mathbb{R}^{L_t\times d_l}$，投影后的媒体表示 $H_m\in\mathbb{R}^{L_m\times d_l}$。

**沿序列轴拼接**：

$$
X=[T;H_m]_{\mathrm{seq}}
\in\mathbb{R}^{(L_t+L_m)\times d_l}
$$

它增加 self-attention 的序列边长；若使用全注意力，主要矩阵项随 $(L_t+L_m)^2$ 增长。

**沿特征轴拼接**要求两侧序列长度相同：

$$
[A\|B]_{\mathrm{feat}}
\in\mathbb{R}^{L\times(d_1+d_2)}
$$

它不增加序列长度，增加的是 Q/K/V 投影和 MLP 的宽度计算。把两种操作都简称“拼接”会直接导致复杂度分析错误。

## Early fusion 与 cross-attention

Early fusion 把软媒体 Token 插入 decoder 序列；媒体通常在答案之前，因此后续答案位置可通过 causal self-attention 读取它们。另一类架构保留独立媒体 memory $Z_m$，在语言层使用 cross-attention：

$$
\operatorname{CrossAttn}(H_l,Z_m)
=\operatorname{softmax}\left(
\frac{(H_lW_Q)(Z_mW_K)^\top}{\sqrt{d_h}}+M_{tm}
\right)(Z_mW_V)
$$

此时文本 self-attention 约为 $O(L_t^2d)$，额外媒体访问约为 $O(L_tL_md)$。若先把媒体重采样到固定 $M$，后一项变为 $O(L_tMd)$。实际模型也可以先 resample，再做序列插入，或只在部分语言层启用 cross-attention；“端到端多模态”不限定某一种拓扑。

## 内容块顺序的正确含义

输入 `[text A, image B, text C]` 通常保留 A-B-C 的**逻辑语义顺序**，但服务可能把 B 展开成多个 Tile、加入边界标记，或放入独立媒体 memory。应用不应假设未公开的内部 Token 偏移。

把局部说明放在媒体附近、使用“图 A”“页面 3”“音频片段 B”等稳定 ID，通常能降低指代歧义；但“物理相邻必然提高注意力并减少幻觉”不是通用定理。效果取决于训练分布、位置编码、mask、融合拓扑与任务，应通过顺序消融实验验证。

Markdown 图片语法通常只给文本模型一个 alt text 和路径字符串。只有 UI 或 Agent Harness 解析路径、读取并校验文件，再构造显式媒体内容块，模型才实际获得媒体。[[markdown-llm-protocol|文本格式协议]]负责这类消息外壳、标签和输出契约；本页描述媒体进入模型后的张量变换与融合，两者不能混为一层。

## Agent 的 Provider 无关表示

应用应先维护有序中间表示，再由适配器映射到不同 provider：

```typescript
type ContentPart =
  | { kind: "text"; text: string }
  | { kind: "image"; id: string; source: MediaSource }
  | { kind: "audio"; id: string; source: MediaSource; timeRange?: [number, number] }
  | { kind: "video"; id: string; source: MediaSource; timeRange?: [number, number] }
  | { kind: "document"; id: string; source: MediaSource; pages?: number[] };
```

IR 至少保存稳定 ID、逻辑位置、来源哈希、MIME、尺寸/时长/页数，以及缩放、裁剪、FPS 和时间区间等预处理记录。上传和转码可并行，但最终序列化必须按 `partIndex` 恢复用户顺序；完成先后不能成为排列依据。

## 质量、成本与复现

一次请求的近似上下文预算可写为：

$$
L_{\mathrm{est}}=L_{\mathrm{text}}
+\sum_iL_{\mathrm{image},i}
+r_aT_a+r_vT_v+L_{\mathrm{document}}+L_{\mathrm{special}}
$$

图片的分辨率、裁剪和压缩，视频的 FPS 与时间区间，PDF 的页数与渲染 DPI，都会改变质量、成本和延迟。优化目标应是受预算约束的任务质量，而不是单独追求最少 Token。

可复现实验应记录 provider、endpoint、model、内容块顺序、媒体实际尺寸/时长、预处理参数、文件哈希、usage、延迟和任务评分，并分别做顺序、空间分辨率、时间采样与融合策略消融。原文件相同但预处理不同，模型实际输入也不同。
