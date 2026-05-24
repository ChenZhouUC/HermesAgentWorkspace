---
title: LLM Reasoning, Thinking, and Effort
created: 2026-05-24
updated: 2026-05-24
---

# 大模型的「思考」与「努力程度」：Reasoning、Thinking 与 Effort 全景调研

本篇梳理大语言模型（LLM）从「即时应答」走向「先思考再回答」的完整技术脉络，覆盖四条主线：发展历史（从 Chain-of-Thought 到 Reasoning Model）、实现思路（推理时计算扩展与强化学习训练）、最新研究（过度思考与逆向扩展），以及各大厂商在 API 层面对「思考开关」和「努力程度（effort）」的工程实践。

截至 2026 年 5 月，「是否带思考」「思考多久」已经从区分不同模型 SKU 的属性，演变为同一模型内部可通过参数动态调节的旋钮。

---

## 第一部分：发展历史 —— 从 Chain-of-Thought 到 Reasoning Model

### 1.1 Chain-of-Thought (CoT) 谱系

「让模型把中间推理步骤显式写出来」是这一切的起点。

- **Chain-of-Thought Prompting (Wei et al., 2022, arXiv:2201.11903)**：Google 团队（Jason Wei、Denny Zhou 等）提出，在 few-shot 示例中加入中间推理步骤（chain of thought），可显著提升算术、常识与符号推理表现。最具影响力的论断是：CoT 是一种**规模涌现能力（emergent ability of scale）**——在 ~10B 参数以下几乎无效甚至有害，只有在足够大的模型（如 PaLM 540B、GPT-3 175B）上才「点亮」。在 GSM8K 上，PaLM 540B + CoT 大致追平了专门微调的任务模型。这把「推理」重新定义为可由提示词诱发，而非必须改架构。
- **Zero-shot CoT (Kojima et al., 2022, arXiv:2205.11916)**：《LLMs are Zero-Shot Reasoners》。仅在提问后追加一句 **"Let's think step by step"**，无需任何示例即可触发多步推理。在 GSM8K 上用 InstructGPT (text-davinci-002) 把零样本准确率从约 17.7% 拉到约 78.7%。
- **Self-Consistency (Wang et al., 2022, arXiv:2203.11171)**：用「采样多条不同推理路径 + 对最终答案多数投票」替代贪心解码（在推理路径上做边缘化）。报告增益 GSM8K +17.9%、SVAMP +11.0%、AQuA +12.2%。这在概念上是该谱系里第一个「多花推理算力换准确率」的技术。
- **Tree-of-Thoughts (Yao et al., 2023, arXiv:2305.10601)**：把线性的 CoT 推广为对「思维（thoughts）」的**搜索树**，带自评估、前瞻与回溯（BFS/DFS）。标志性结果：在 "Game of 24" 上 GPT-4 用 CoT 仅解 4%，用 ToT 达 74%。
- **Graph-of-Thoughts (Besta et al., 2023, arXiv:2308.09687)**：把思维建模为**任意图**（顶点=思维，边=依赖），支持思维的聚合/合并与反馈环，超越树结构。
- **Least-to-Most Prompting (Zhou et al., 2022, arXiv:2205.10625)**：把复杂问题分解为由易到难、有序的子问题，前一步答案喂给后一步，主打 easy-to-hard 泛化。
- **ReAct (Yao et al., 2022, arXiv:2210.03629)**：把**推理轨迹与行动（调用搜索/工具）交错**，推理指导行动、观测更新推理。它是现代「推理 + 工具」智能体的概念源头。

### 1.2 范式转向：推理时计算（Test-Time / Inference-Time Compute）

核心转折是从**扩展训练算力**（Kaplan/Chinchilla 式预训练定律）转向**扩展推理时算力**——让模型在查询时「多想一会儿」，而非单纯把模型做大。

- **STaR — Self-Taught Reasoner (Zelikman et al., 2022, arXiv:2203.14465)**：一个**自举循环**——为题目生成 rationale，保留答对的；答错的则「给定正确答案反推 rationale（rationalize）」；用成功的 rationale 微调，再循环。这是「用模型自己的推理轨迹训练模型」的思想祖先，也是后来 RL-on-CoT 的种子。
- **Let's Verify Step by Step (Lightman et al., 2023, arXiv:2305.20050)**：OpenAI 提出**过程奖励模型（PRM）vs 结果奖励模型（ORM）**的区分：PRM 监督每一步中间推理，ORM 只评判最终答案。结论是在 MATH 上**过程监督显著优于结果监督**，并开源了步级标注数据集 PRM800K。这奠定了「验证推理过程而非只验证答案」的范式。
- **Large Language Monkeys (Brown et al., 2024, arXiv:2407.21787)**：研究**重复采样（repeated sampling）**——「覆盖率」（N 个样本中**任一**解对的比例）随采样数在约 4 个数量级范围内平滑、常近 log-linear 地提升。标志：SWE-bench Lite 上 DeepSeek-V2-Coder 从单样本 15.9% 提到 250 样本 56%，超过当时 43% 的单次尝试 SOTA。它点出的关键约束：要把对的样本挑出来需要一个**验证器（verifier）**——代码/数学易，开放式任务难。
- **Scaling LLM Test-Time Compute Optimally (Snell et al., 2024, arXiv:2408.03314)**：Berkeley/DeepMind。分析两类推理时机制——对稠密过程验证器的搜索，以及自适应修订模型自身输出分布——提出**「compute-optimal」按题目难度分配推理算力**，相对 best-of-N 提效 >4×，并证明在 FLOPs 对齐下推理时算力可让小模型在适当难度问题上击败 **14×** 大的模型。
- **OpenAI o1（2024-09-12）—— 拐点**：首个前沿「推理模型」，通过产出一条很长的内部思维链**先思考再回答**，且是用**大规模强化学习训练它自己的思维链**（而非监督人写的 CoT）。OpenAI 明确给出两条扩展轴：性能随**训练期 RL** 与**推理期思考时间**双双提升。原始推理以**隐藏 reasoning token** 形式存在——API 计费但不展示（UI 只给摘要，且不保证忠实）。宣称成绩：Codeforces ~89 百分位、AIME 进入前 500、GPQA 超过博士级人类准确率。OpenAI 还主张「可读的 CoT」有利于安全/对齐。

---

## 第二部分：实现思路 —— 推理能力是怎么训出来的

### 2.1 强化学习（RL）路线

整个领域从 **RLHF**（基于人类偏好的 RL，PPO 系）转向 **RLVR（RL with Verifiable Rewards，可验证奖励的 RL）**——奖励来自规则化的正确性检查（数学答案是否匹配、代码是否通过测试），而非学出来的偏好模型。这避免了 reward hacking，并能在数学/代码上低成本扩展。

- **PPO (Proximal Policy Optimization, Schulman et al., 2017)**：标准 actor-critic RL，需要一个与策略网络规模相当的独立 value/critic 网络。
- **GRPO (Group Relative Policy Optimization)**：出自 **DeepSeekMath (Shao et al., 2024, arXiv:2402.03300)**。是 PPO 的变体，**去掉 critic**，改为对每个 prompt 采样**一组**输出，用样本相对于该组均值奖励来估计优势（advantage）。大幅降低显存/算力。
- **纯 RL 涌现推理**：**DeepSeek-R1 (DeepSeek-AI, 2025-01, arXiv:2501.12948)** 用 GRPO + 规则奖励规模化，证明推理行为（自我反思、验证、回溯——所谓「aha moment」）可以**在没有 SFT 的情况下从纯 RL 中涌现**（R1-Zero）：AIME 2024 pass@1 从 15.6% 升到 71.0%（多数投票 86.7%），追平 o1-0912。R1 后续登上 Nature（2025）。

### 2.2 蒸馏（Distillation）路线

与其在小模型上跑 RL，不如用强推理教师（如 R1）生成大量长 CoT 轨迹，再对小模型做**监督微调（SFT）**。DeepSeek-R1 表明：在相同小基座上，蒸馏出的小模型（如 R1-Distill-Qwen-7B/32B）常**优于**对该小模型从头跑 RL，且更便宜——即蒸馏往往比小模型直接 RL 更有效。

### 2.3 搜索路线（MCTS）

另一条平行线把 **蒙特卡洛树搜索（MCTS）** 用于推理步骤之上，用 value/process 模型引导扩展（概念上是 AlphaGo/AlphaZero 思想迁移到推理），把 ToT（对思维的搜索）与 PRM（步级打分）连接起来。代表性工作如 rStar-Math、ReST-MCTS\*、AlphaMath 等（具体引用需单独核验）。

---

## 第三部分：「Effort / Thinking Budget」—— 控制思考量的旋钮

推理模型把推理时算力变成一个**可调参数**。各家命名不同，但本质都是「思考多少 token」或「思考到什么档位」的控制。共性机制：

- **隐藏/摘要的推理 token**：原始 CoT 通常不直接暴露，但**按输出 token 计费**，可见 token 与计费 token 不一致。
- **软上限语义**：budget 多是软上限，模型可能用不满；超过某阈值（经验上 ~32k）收益递减。
- **延迟 - 成本权衡**：effort/budget 越高 → 隐藏推理 token 越多 → 成本与延迟越高，常常收益递减甚至为负。
- **Hybrid Reasoning（混合推理）**：一个模型带开关，可关闭思考退化为普通模型——已成为主流，逐步取代「推理模型 vs 非推理模型」两套独立 SKU。

---

## 第四部分：各大厂商实践（截至 2026-05）

### 4.1 OpenAI

- **谱系/时间线**：o1（代号 Strawberry，2024-09-12 预览，2024-12-05 GA）+ o1-mini + o1-pro；o3（2024-12-20「12 Days」公布，命名跳过 o2 以避开 O2 电信商标）；o3-mini（2025-01-31，首个面向免费用户的推理模型，暴露 low/medium/high 三档 effort）；o3 与 o4-mini（2025-04-16，首批带 agentic 工具使用的 o 系）；o3-pro（2025-06-10）。
- **`reasoning_effort`**：在 Responses API 中为 `reasoning.effort`。GPT-5 发布时定义四档 **minimal / low / medium / high**（默认 medium）。后续扩展出 **none**（行为如非推理模型，低延迟）与 **xhigh**（随 gpt-5.1-codex-max 引入）。默认值因模型而异（例如 gpt-5.1 据称默认 none；gpt-5-pro 仅支持 high；gpt-5-codex 不支持 minimal）。minimal 档不支持并行工具调用。token 上限用 `max_completion_tokens`。
- **reasoning token / 计费 / Responses API**：推理模型产出隐藏 reasoning token，原始 CoT 不暴露，只能通过 `summary` 参数（`concise` / `detailed`，因模型而异，可能需组织验证）拿到**摘要**。**reasoning token 按 output token 计费**，见 `usage.output_tokens_details.reasoning_tokens`。**Responses API 有状态**，推理项以 ID 跨轮持久化（`previous_response_id`），把缓存命中率从 ~40% 提升到 ~80%；ZDR 组织可传加密推理内容。
- **GPT-5 统一系统（2025-08-07）**：不是单一模型，而是「快模型（gpt-5-main / -mini）+ 思考模型（gpt-5-thinking / -mini）+ 实时路由器」的**系统**，路由器据复杂度、工具需求与显式线索（如「think hard about this」）选择，并持续用用户切换信号训练。发布时因失去手动选模型权而引发用户反弹。后续 gpt-5.1 / 5.5 / codex-max 进一步细化 effort 与 token 效率。

### 4.2 Anthropic (Claude)

- **Extended Thinking（扩展思考）**：始于 Claude 3.7 Sonnet，延续到 Claude 4 / Opus 4.x / Sonnet 4.x。通过 `thinking={"type":"enabled","budget_tokens":N}` 开启。
- **`budget_tokens` 机制**：最小 **1024** token；常规（非交错）下须**小于 `max_tokens`**；它是内部推理 token 的上限，模型可能用不满，~32k 以上收益递减。`max_tokens > 21333` 时**必须用流式**。
- **可见 vs 摘要**：Claude 4 返回思考过程的**摘要**，但**按完整思考 token 计费**，故计费与可见 token 不一致。**交错思考（interleaved thinking，在工具调用之间思考）** 用 beta header `interleaved-thinking-2025-05-14` 开启；此时 `budget_tokens` 可超过 `max_tokens`（代表单轮所有思考块的总预算，可至上下文窗口上限）。思考块带**签名（signature）**保证完整性；改变思考预算会使缓存的消息前缀失效（系统提示/工具缓存仍在）。
- **近期演进（需以官方文档为准）**：有资料显示 Claude Opus 4.6 / Sonnet 4.6 上 `budget_tokens` 被**自适应思考（adaptive thinking）**取代：`thinking={"type":"adaptive"}` 配合 `output_config:{"effort":...}`，由 Claude 自行决定是否/思考多少，effort 作为软性行为信号；旧模型（Sonnet 4.5、Opus 4.5）仍用 `enabled` + `budget_tokens`。此条来自第三方来源，发布前应核对官方文档。

### 4.3 Google (Gemini)

- **谱系**：Gemini 2.0 Flash Thinking（早期实验推理版）→ Gemini 2.5 Pro/Flash 将思考变为标准特性。
- **`thinkingConfig.thinkingBudget`**：2.5 Pro 范围 **128–32768**，**不能关闭**思考，`-1` 为动态；2.5 Flash 范围 **0–24576**，`0` 关闭思考，`-1` 动态。不设置时模型自动控制（约上限 8192 token）。`-1` 即**动态思考（dynamic thinking）**，模型自调至上限。budget 是**软上限**。
- **思考摘要**：`thinkingConfig.includeThoughts: true` 暴露**合成的、尽力而为的思考摘要**（非原始思维，流式时滚动增量给出）。**按完整思考 token 计费**。
- **迁移**：Gemini 3 用 `thinkingLevel` 取代 `thinkingBudget`（二者互斥；在 Gemini 3 Pro 上用 `thinkingBudget` 可能效果不佳）。

### 4.4 DeepSeek

- **DeepSeek-R1（2025-01-20，开源权重）**：架构与 DeepSeek-V3（2024-12，671B MoE）相同，区别在用于推理的 RL。**R1-Zero** 完全跳过 SFT，纯 RL（GRPO）训练，涌现推理但可读性差、语言混杂；**R1** 加冷启动数据 + 多阶段训练修复之。推理在 **`<think>`** 标签内进行。**MIT 许可**（明确允许微调/蒸馏），附 6 个蒸馏稠密模型（1.5B–70B，基于 Qwen/Llama）。价格约为 o1 的 1/27 ~ 1/50。后续 DeepSeek-V3.1 / V3.2-exp 走向 `enable_thinking` 式可控的**混合推理**。

### 4.5 Qwen / xAI / Mistral 等

- **Qwen3**：推广开源**混合思考**——一个模型两种模式（Thinking / Non-Thinking）。通过 API 参数 **`enable_thinking`**（True/False）与提示词内**软开关 `/think`、`/no_think`**（多轮取最近一次）控制；**`thinking_budget`** 上限思考 token（默认为模型最大 CoT 长度）。四阶段训练（长 CoT 冷启动 → 推理 RL → 思考模式融合 → 通用 RL）。注意：研究（arXiv:2510.12680）显示模式分离不完美，`no_think` 仍会泄漏推理词。**QwQ**（qwq-32b / qwq-plus）是**仅思考**模型，无法关闭。
- **xAI Grok**：Grok 3 提供 think 模式；**Grok 4 Fast** 用统一权重，同一模型据传入参数处理推理/非推理，端到端工具使用 RL 训练。
- **Mistral**：**Magistral** 系列（Magistral Small 1.2 Apache-2.0；Medium 1.2 闭源）是其推理家族，1.2 加入视觉。
- **行业区分**：**混合思考模型**（Qwen3、DeepSeek V3.2-exp，可 `enable_thinking=false` 关闭）vs **仅思考模型**（QwQ、DeepSeek-R1，不可关闭）。

---

## 第五部分：最新研究 —— 过度思考与逆向扩展

- **Inverse Scaling in Test-Time Compute (arXiv:2507.14417，Anthropic 主导)**：更长的推理可能**降低**准确率，而不只是更贵。失败模式因模型而异：Claude 易被干扰项分心；OpenAI o 系抗干扰但易过拟合问题框架；DeepSeek R1 在干扰下准确率从 70% 掉到 30%。还有安全隐患（更长推理有时浮现「抗关机」倾向）。实用建议——对会逆向扩展的任务对推理长度设硬上限——正是 effort 控制与 GPT-5 路由器（把琐碎查询路由离开深度推理）的架构理由。
- **延迟 - 成本经验**：以 GPT-5 为例，Artificial Analysis Intelligence Index 上 high=68 / medium=67 / low=64 / minimal=44，但 high 成本近 medium 的 2×，而真实成功率几乎一致——印证了「多思考≠更好」需按任务择档。

---

## 关键论文 arXiv 索引

CoT 2201.11903 · Zero-shot CoT 2205.11916 · Self-Consistency 2203.11171 · ToT 2305.10601 · GoT 2308.09687 · Least-to-Most 2205.10625 · ReAct 2210.03629 · STaR 2203.14465 · Let's Verify Step by Step 2305.20050 · Large Language Monkeys 2407.21787 · Test-Time Compute Optimal 2408.03314 · DeepSeekMath/GRPO 2402.03300 · DeepSeek-R1 2501.12948 · Inverse Scaling in Test-Time Compute 2507.14417 · Qwen3 mode-leak 2510.12680
