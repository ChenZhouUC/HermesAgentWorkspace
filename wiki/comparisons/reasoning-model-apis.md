---
title: 各厂商推理模型「思考/努力」API 对比 (Reasoning Model Thinking & Effort APIs)
created: 2026-05-24
updated: 2026-07-11
type: comparison
tags: [comparison, llm, reasoning]
sources: [_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort.md]
confidence: medium
---

# 各厂商推理模型「思考 / 努力」API 对比

横向对比截至 2026-05 各大厂商在 API 层面对**思考开关**与**努力程度 (effort)** 的工程实现。控制形态的概念分类见 [[reasoning-effort-control]]，底层范式见 [[test-time-compute-scaling]]。

> 注：标记「需核验」的条目来自第三方来源或处于快速演进中，发布前应对照官方文档确认。

## 控制参数对比表

| 厂商         | 代表模型                         | 控制参数                                                                           | 控制形态             | 思考可见性                                   | 能否关闭                    |
| ------------ | -------------------------------- | ---------------------------------------------------------------------------------- | -------------------- | -------------------------------------------- | --------------------------- |
| OpenAI       | o1/o3/o4-mini、GPT-5 系          | `reasoning.effort` (minimal/low/medium/high，扩展 none/xhigh)                      | 离散档位 + 系统路由  | 隐藏，仅 `summary`（concise/detailed）       | 可（none / 路由到快模型）   |
| Anthropic    | Claude 3.7 / 4 / Opus·Sonnet 4.x | `thinking.budget_tokens`（min 1024）；4.6 起 `type:adaptive`+`effort`（需核验）    | 连续预算 → 自适应    | 摘要（按完整思考计费）                       | 可（不开 thinking）         |
| Google       | Gemini 2.5 Pro/Flash、Gemini 3   | `thinkingConfig.thinkingBudget`（`0` 关 / `-1` 动态）；Gemini 3 改 `thinkingLevel` | 连续预算 → 档位      | 思考摘要 `includeThoughts`（按完整思考计费） | Flash 可（`0`）；Pro 不可关 |
| DeepSeek     | R1 / R1-Zero、V3.1 / V3.2-exp    | `<think>` 标签；后续 `enable_thinking`                                             | 标签 → 混合开关      | **完整可见**（开源权重）                     | R1 不可；V3.x 可            |
| Alibaba Qwen | Qwen3、QwQ                       | `enable_thinking`、提示词 `/think` `/no_think`、`thinking_budget`                  | 开关 + 软开关 + 预算 | 可见                                         | Qwen3 可；QwQ 不可          |
| xAI          | Grok 3 / Grok 4 Fast             | think 模式 / 统一权重参数                                                          | 开关                 | 部分可见                                     | 可                          |
| Mistral      | Magistral Small/Medium 1.2       | 推理家族（开源 Small）                                                             | 模型级               | 可见                                         | —                           |

## 各家要点

### OpenAI

`reasoning_effort` 默认 medium，后扩展 none（如非推理模型，低延迟）与 xhigh（随 gpt-5.1-codex-max）。reasoning token **按 output 计费**（见 `usage.output_tokens_details.reasoning_tokens`），原始 CoT 不暴露。Responses API 有状态，推理项以 ID 跨轮持久化，把缓存命中率从 ~40% 提到 ~80%。GPT-5（2025-08）是「快模型 + 思考模型 + 实时路由器」的统一系统而非单一模型。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

### Anthropic

Extended Thinking 始于 Claude 3.7 Sonnet。`budget_tokens` 最小 1024、常规下须 < `max_tokens`；`max_tokens > 21333` 须流式。交错思考（beta header `interleaved-thinking-2025-05-14`）下 budget 可超 `max_tokens`（代表单轮总预算）。思考块带签名；改预算使缓存消息前缀失效。4.6 起转向自适应思考（需核验）。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

### Google / DeepSeek / Qwen

Gemini 2.5 Pro 思考不可关（范围 128–32768），Flash 可关（`0`）；`-1` 为动态思考；Gemini 3 用 `thinkingLevel` 取代 budget。DeepSeek-R1（2025-01，MIT 开源）在 `<think>` 内推理、可完整观察，附 6 个蒸馏模型。Qwen3 推广开源混合思考（`enable_thinking` + `/think` `/no_think`），但研究（arXiv:2510.12680）显示 `no_think` 仍会泄漏推理词。^[[[_living/AI-Infrastructure/LLM-Reasoning-Thinking-and-Effort|LLM-Reasoning-Thinking-and-Effort]]]

## 行业趋势

**混合思考模型**（一个模型带开关）正取代「推理 vs 非推理」两套独立 SKU：Qwen3、DeepSeek V3.2-exp、Grok 4 Fast 统一权重、Claude 自适应思考、GPT-5 路由器都是其变体。这把 [[chain-of-thought]] 起源的「是否多想」从模型选型问题降维成单次请求的参数问题。

## 核心 Trade-offs

- **离散档位 vs 连续预算**：OpenAI 的 `effort` 档位简化了调参（开发者只选 low/medium/high），代价是失去对实际推理 token 数的精确控制；Anthropic/Google 的 `budget_tokens` 给予精确预算，代价是开发者要自行实验找到合适数值。
- **隐藏思考 vs 完整可见**：OpenAI/Anthropic 把推理 token 隐藏（仅暴露 summary，但仍按完整思考计费）——保护"思维链工艺"但客户难以审计；DeepSeek R1 完整暴露 `<think>` 块——便于学术研究与可观测性，代价是模型知识产权被开源出去。
- **关闭思考的能力**：Gemini 2.5 Pro 不可关、QwQ 不可关、R1 不可关——一旦上线就要为每次请求付推理 token；OpenAI/Anthropic/Qwen3/Gemini Flash 可关——允许在低延迟场景退化为常规模型，但需要业务侧主动判断何时关。
- **接口稳定性 vs 演进速度**：OpenAI 的 `effort` 自 o1 起保持兼容；Gemini 在 3 代版本中把 `thinkingBudget` 改为 `thinkingLevel`，DeepSeek 从 `<think>` 标签演进为 `enable_thinking`——接口频繁变动增加了多模型抽象层的维护成本。

## When to use A vs B (选型决策)

- **需要按业务复杂度细粒度调推理预算（如批处理与实时混合负载）**：选 **Anthropic** 或 **Google Gemini Pro**——连续 `budget_tokens` 允许动态分配。
- **需要简单的"标准/加强"两档心智模型、且不想自行调参**：选 **OpenAI** 的 `reasoning.effort` 档位。
- **需要在同一系统中混用"思考/不思考"模式以平衡延迟与质量**：优先选支持运行时关闭的厂商——**OpenAI、Anthropic、Qwen3、Gemini Flash**；避开 Gemini Pro / QwQ / R1 等不可关模型。
- **需要审计推理过程或做学术研究**：选 **DeepSeek R1** 或 **Qwen** 等完全暴露推理 token 的开源模型；闭源厂商的 `summary` 不足以做严格审计。
- **需要在低成本环境部署推理模型**：选 **DeepSeek、Qwen、Mistral Magistral** 等开源系——可自部署绕过 API 计费；闭源 reasoning token 按 output 计费，长思考的总成本远超非推理模型。
