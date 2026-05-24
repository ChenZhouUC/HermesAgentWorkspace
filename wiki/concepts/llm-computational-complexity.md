---
title: LLM Computational Complexity
created: 2026-05-14
updated: 2026-05-24
type: concept
tags: [tcs, complexity, llm, proof]
sources: [_living/TCS-and-Math/LLM-Computational-Complexity.md]
confidence: high
---

# LLM Computational Complexity

在理论计算机科学（TCS）与纯数学视角下，LLM 的「涌现能力」被转化为计算复杂性理论的边界问题。相比经验性 Benchmark 跑分（见 [[llm-benchmark-methodology]]），理论研究更关注严格的**下界（Impossibility）**与精确的**能力刻画（Exact Characterization）**。核心议题是：单次前向传播的 Transformer 能算什么，以及 [[chain-of-thought|思维链（CoT）]] 如何改变这个能力边界。

## 1. Transformer 表达能力的复杂度类刻画

**The Expressive Power of Transformers with Chain of Thought**（Merrill & Sabharwal, 2023, arXiv:2310.07923）把神经网络能力映射到经典电路复杂性：

- 无 CoT 的 Transformer 可被刻画为 $\text{TC}^0$（常数深度、多项式大小的阈值逻辑电路）。
- 接入多项式步数的 CoT 后，表达能力可达多项式时间可解问题类 **P**。
- 即：CoT 不是「锦上添花」，而是**实打实地把模型从一个并行常数深度电路类提升到串行多项式时间类**。^[[[_living/TCS-and-Math/LLM-Computational-Complexity|LLM-Computational-Complexity]]]

作者 William Merrill（NYU CDS）、Ashish Sabharwal（AI2）长期研究 Transformer 计算能力与形式化推理。

## 2. 有限精度下的串行问题下界

**Chain of Thought Empowers Transformers to Solve Inherently Serial Problems**（Zhiyuan Li et al., ICLR 2024）强调有限精度约束（多数图灵完备性论证依赖无限精度实数这一过强假设）：

- 有限精度下，常数深度 Transformer 难以解决模幂、排列组合等**固有串行问题（Inherently Serial Problems）**。
- CoT 可理解为给浅层并行电路补上一个**自回归外循环**，把中间状态显式写到上下文里——这正是 [[test-time-compute-scaling|推理时计算]] 在复杂性理论上的对应物。^[[[_living/TCS-and-Math/LLM-Computational-Complexity|LLM-Computational-Complexity]]]

## 3. 组合泛化与多步推理的退化

**Faith and Fate: Limits of Transformers on Compositionality**（Dziri et al., NeurIPS 2023）用计算图论把逻辑推理任务（多位数乘法、动态规划）转化为图上路径计算：

- 当计算图深度超过常数级、且未通过 CoT 显式保存中间节点时，多步组合推理能力**快速退化**。
- 结论：单纯扩大参数量 ≠ 获得无限多步推理能力。^[[[_living/TCS-and-Math/LLM-Computational-Complexity|LLM-Computational-Complexity]]]

## 4. 自注意力的形式语言限制

**Theoretical Limitations of Self-Attention in Neural Sequence Models**（Hahn, TACL 2020）是该领域早期代表作：从形式语言角度证明，在层数/注意力头数不随输入长度增长时，标准自注意力难以精确建模某些层级结构与周期性的正则语言（Regular Languages）。这解释了单次前向模型在部分基础逻辑任务上的结构性限制。^[[[_living/TCS-and-Math/LLM-Computational-Complexity|LLM-Computational-Complexity]]]

## 小结：理论与工程的会合点

四篇论文共同指向一个结论——**推理深度受限于计算步数**，而 CoT / 推理时算力是突破该限制的关键机制。这把 [[chain-of-thought]] 这一经验技巧、[[test-time-compute-scaling]] 这一工程范式，与电路复杂性这一硬数学边界统一了起来。理论侧的「应该多想几步」恰好为工程侧的推理预算控制提供了第一性原理依据。

---

**Related:**

- [[set-theory]]
- [[llm-benchmark-methodology]]
- [[chain-of-thought]]
- [[test-time-compute-scaling]]
