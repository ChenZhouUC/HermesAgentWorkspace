---
title: 推理时计算扩展 (Test-Time Compute Scaling)
created: 2026-05-24
updated: 2026-05-24
type: concept
tags: [llm, reasoning, paper]
sources: [_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md]
confidence: high
---

# 推理时计算扩展 (Test-Time / Inference-Time Compute Scaling)

推理时计算扩展是当代「推理模型 (reasoning model)」的核心范式：从**扩展训练算力**（Kaplan/Chinchilla 式预训练定律）转向**扩展推理时算力**——让模型在查询时「多想一会儿」，而非单纯把模型做大。它把 [[chain-of-thought]] 从提示词技巧升级为可训练、可扩展的模型能力。

## 早期支撑性证据

- **STaR — Self-Taught Reasoner (Zelikman et al., 2022, arXiv:2203.14465)**：自举循环——生成 rationale，保留答对的；答错的「给定正确答案反推 rationale」；用成功的 rationale 微调再循环。这是「用模型自己的推理轨迹训练模型」的思想祖先。
- **Let's Verify Step by Step (Lightman et al., 2023, arXiv:2305.20050)**：OpenAI 提出**过程奖励模型 (PRM) vs 结果奖励模型 (ORM)** 的区分。PRM 监督每一步推理，ORM 只评判最终答案；在 MATH 上**过程监督显著优于结果监督**，并开源步级数据集 PRM800K。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]
- **Large Language Monkeys (Brown et al., 2024, arXiv:2407.21787)**：**重复采样**——「覆盖率」（N 样本中任一解对的比例）随采样数在约 4 个数量级内近 log-linear 提升。SWE-bench Lite 上 DeepSeek-V2-Coder 从单样本 15.9% 提到 250 样本 56%。关键约束：把对的样本挑出来需要一个**验证器 (verifier)**——代码/数学易，开放式任务难。
- **Scaling LLM Test-Time Compute Optimally (Snell et al., 2024, arXiv:2408.03314)**：提出**「compute-optimal」按题目难度分配推理算力**，相对 best-of-N 提效 >4×，并证明 FLOPs 对齐下推理时算力可让小模型在适当难度问题上击败 14× 大的模型。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 拐点：OpenAI o1

**OpenAI o1（2024-09-12）** 是首个前沿推理模型：通过产出一条很长的内部思维链**先思考再回答**，且用**大规模强化学习训练它自己的思维链**（而非监督人写的 CoT）。OpenAI 明确给出两条扩展轴——性能随**训练期 RL** 与**推理期思考时间**双双提升。原始推理以隐藏 reasoning token 形式存在（API 计费但不展示），这套「思考多少」的控制后续演化为 [[reasoning-effort-control]]。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 训练实现路线

- **RL 路线**：从 **RLHF**（基于人类偏好，PPO 系）转向 **RLVR（可验证奖励的 RL）**——奖励来自规则化正确性检查（数学答案匹配、代码通过测试），避免 reward hacking。
  - **PPO**：标准 actor-critic，需要与策略同规模的 critic 网络。
  - **GRPO (Group Relative Policy Optimization)**：出自 DeepSeekMath (Shao et al., 2024, arXiv:2402.03300)，**去掉 critic**，用一组采样输出相对该组均值奖励估计优势，大幅降显存。**DeepSeek-R1 (2025-01, arXiv:2501.12948)** 用它证明推理行为可在**无 SFT 的纯 RL** 中涌现（R1-Zero）。
- **蒸馏路线**：用强推理教师生成长 CoT 轨迹，对小模型做 SFT；常优于对小模型直接跑 RL，且更便宜。
- **搜索路线 (MCTS)**：把蒙特卡洛树搜索用于推理步骤，用 value/process 模型引导扩展，是 AlphaGo/AlphaZero 思想迁移到推理，把 [[chain-of-thought]] 的 ToT 与 PRM 连接起来。

## 局限与边界

推理时算力并非越多越好——存在过度思考与逆向扩展现象，详见 [[reasoning-effort-control]]。这一范式也改变了基准测试的计算口径：评测必须固定或报告推理预算才公平，相关方法学见 [[llm-benchmark-methodology]]。

---

**相关概念**:

- [[chain-of-thought]]
- [[reasoning-effort-control]]
- [[reasoning-model-apis]]
- [[llm-benchmark-methodology]]
