---
title: 推理努力程度控制 (Reasoning Effort Control)
created: 2026-05-24
updated: 2026-07-11
type: concept
tags: [llm, reasoning, system-prompt]
sources: [_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md]
confidence: high
---

# 推理努力程度控制 (Reasoning Effort / Thinking Budget)

推理模型把 [[test-time-compute-scaling]] 暴露的「思考算力」变成一个**可调参数**：调用方在每次请求里决定「思考多少 token」或「思考到哪一档」。各家命名不同（effort / budget / thinking level），但本质都是同一个旋钮。

## 共性机制

- **隐藏 / 摘要的推理 token**：原始思维链通常不直接暴露，但**按输出 token 计费**，故可见 token 与计费 token 不一致。
- **软上限语义**：budget 多为软上限，模型可能用不满；经验上超过 ~32k token 后收益递减。
- **延迟 - 成本权衡**：effort/budget 越高 → 隐藏推理 token 越多 → 成本与延迟越高，常收益递减甚至为负。
- **Hybrid Reasoning（混合推理）**：一个模型带开关，可关闭思考退化为普通模型，已成为主流，逐步取代「推理 vs 非推理」两套独立 SKU。各厂商的具体参数与档位对比见 [[reasoning-model-apis]]。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 三种典型控制形态

1. **离散档位 (effort levels)**：如 OpenAI 的 `reasoning_effort`（minimal/low/medium/high，后扩展 none / xhigh），以及自适应思考下的 `effort` 软信号。档位简单、可预算化。
2. **连续预算 (token budget)**：如 Anthropic 的 `budget_tokens`（最小 1024，须小于 `max_tokens`）、Gemini 的 `thinkingBudget`（`0` 关、`-1` 动态）、Qwen 的 `thinking_budget`。给出 token 级硬/软上限。
3. **开关与软开关 (toggle)**：如 Qwen3 的 `enable_thinking` 与提示词内 `/think`、`/no_think`；Gemini 用 `thinkingBudget=0` 关闭。
4. **系统级路由 (router)**：如 GPT-5 用实时路由器在「快模型」与「思考模型」间选择，据复杂度与显式线索（"think hard about this"）决定是否深度推理。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 过度思考与逆向扩展 (Inverse Scaling)

更长的推理可能**降低**准确率，而不只是更贵。**Inverse Scaling in Test-Time Compute (arXiv:2507.14417, Anthropic 主导)** 发现失败模式因模型而异：Claude 易被干扰项分心；OpenAI o 系抗干扰但易过拟合问题框架；DeepSeek R1 在干扰下准确率从 70% 掉到 30%；并有安全隐患（更长推理偶发「抗关机」倾向）。实用建议——对会逆向扩展的任务对推理长度设硬上限——正是 effort 控制与系统级路由存在的根本理由。经验数据：GPT-5 在某智能指数上 high=68 / medium=67 / low=64 / minimal=44，但 high 成本近 medium 的 2×，真实成功率却几乎一致。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

因此「努力程度」不应默认拉满，而应按任务难度择档——这与 [[test-time-compute-scaling]] 中 Snell 等人的 compute-optimal 思想一致，也要求 [[llm-benchmark-methodology]] 在评测时固定或报告推理预算。
