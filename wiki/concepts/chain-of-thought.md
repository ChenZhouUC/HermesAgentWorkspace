---
title: 思维链 (Chain-of-Thought)
created: 2026-05-24
updated: 2026-07-11
type: concept
tags: [llm, reasoning, paper]
sources: [_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md]
confidence: high
---

# 思维链 (Chain-of-Thought, CoT)

思维链是「让模型把中间推理步骤显式写出来再给答案」的提示词技术族，是大模型从「即时应答」走向「先思考再回答」的概念起点。它把推理重新定义为**可由提示词诱发的行为**，而非必须修改架构的能力。

## 起源与涌现论断

- **CoT Prompting (Wei et al., 2022, arXiv:2201.11903)**：在 few-shot 示例中加入中间推理步骤即可显著提升算术、常识与符号推理。最具影响力的论断是 CoT 为**规模涌现能力 (emergent ability of scale)**——在约 10B 参数以下几乎无效甚至有害，只有在足够大的模型（PaLM 540B、GPT-3 175B）上才「点亮」。在 GSM8K 上 PaLM 540B + CoT 大致追平专门微调的任务模型。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]
- **Zero-shot CoT (Kojima et al., 2022, arXiv:2205.11916)**：仅追加一句 **"Let's think step by step"**，无需示例即可触发多步推理；在 GSM8K 上把 InstructGPT 零样本准确率从约 17.7% 拉到约 78.7%。

## 从「链」到「树」与「图」

CoT 的拓扑结构被不断推广，本质都是用更复杂的搜索结构换取更高的推理质量：

- **Self-Consistency (Wang et al., 2022, arXiv:2203.11171)**：采样多条推理路径 + 对最终答案多数投票（在路径上做边缘化）。这是该谱系里**第一个「多花推理算力换准确率」**的技术，是 [[test-time-compute-scaling]] 的雏形。
- **Tree-of-Thoughts (Yao et al., 2023, arXiv:2305.10601)**：把线性链推广为对「思维」的搜索树，带自评估、前瞻与回溯（BFS/DFS）。在 "Game of 24" 上 GPT-4 用 CoT 仅解 4%，用 ToT 达 74%。
- **Graph-of-Thoughts (Besta et al., 2023, arXiv:2308.09687)**：把思维建模为任意图，支持思维的聚合/合并与反馈环。
- **Least-to-Most (Zhou et al., 2022, arXiv:2205.10625)**：把复杂问题分解为由易到难的有序子问题，主打 easy-to-hard 泛化。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 推理 + 行动：ReAct

- **ReAct (Yao et al., 2022, arXiv:2210.03629)**：把推理轨迹与行动（调用搜索/工具）交错，推理指导行动、观测更新推理。它是现代「推理 + 工具」智能体的概念源头，与 [[agent-frameworks]] 的工具调用范式直接相关。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 与后续范式的关系

CoT 是**提示词层面**的推理诱发；其思想被后续的**推理模型**内化——不再依赖人工提示，而是通过强化学习让模型自发产出长思维链，详见 [[test-time-compute-scaling]]。这条「让模型多想」的算力也成为可调旋钮，详见 [[reasoning-effort-control]]。从计算复杂性角度看，显式中间步骤等价于给模型更长的「草稿纸」，与 [[llm-computational-complexity]] 中关于 Transformer 表达力随计算步数变化的分析相呼应。
