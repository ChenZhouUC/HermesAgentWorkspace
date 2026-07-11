---
title: LLM Benchmark Methodology
created: 2026-05-14
updated: 2026-07-11
type: concept
tags: [benchmark, llm]
sources: [_living/AI-Infrastructure/LLM-Benchmarks.md]
confidence: medium
---

# LLM Benchmark Methodology

大模型基准测试的系统性方法学。**跑分极易波动**，本页分数仅作 2026-04 左右的阶段性参考，正式选型须以各基准官网、论文与最新模型报告为准。

## 评测方法学原语 (Evaluation Primitives)

理解基准，关键不在分数本身，而在**怎么测**——同一模型在不同评测协议下分数可差很多：

- **Shot 设置**：0-shot / few-shot（如 MMLU 常用 5-shot，GSM8K 常用 8-shot CoT，BBH 用 3-shot CoT）。是否允许 [[chain-of-thought|思维链]] 对推理类基准影响极大。
- **打分方式**：
  - _选项 token 概率_：选择题对各选项 token 概率取 argmax（MMLU、C-Eval）。
  - _Exact Match / 答案抽取_：自由回答题抽取最终数字或标准式（GSM8K、MATH）。
  - _Pass@k + 沙盒执行_：代码题在沙盒跑单元测试（HumanEval、SWE-bench）。
  - _LLM-as-a-Judge_：开放式问答无标准答案，由裁判模型 1-10 打分（AlignBench）。
- **数据污染与动态基准**：静态基准易被「刷榜」/训练集污染；LiveCodeBench 等只收模型训练截止日之后的新题以降污染。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

## 基准分类法 (Taxonomy by Capability)

### 综合知识与逻辑推理

- **MMLU**：57 学科、约 14,049 测试题、4 选项；行业通用基线，前沿模型已挤在 88-90%，区分度下降。
- **MMLU-Pro**：10 选项强化版，减记忆题、增推理，常配 CoT；前沿约 75-80%。
- **GPQA**：博士级生物/物理/化学、448 题（Diamond 198），强反搜索性、常用 0-shot CoT；前沿约 70-75%。
- **ARC-c**、**AGIEval**（高考/司法考/SAT）、**BBH**（23 个高难推理任务，3-shot CoT）。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

### 数学

- **GSM8K**：小学应用题、8-shot CoT、Exact Match；前沿 96-98%，已近饱和。
- **MATH / MATH-500**：竞赛级数学，MATH-500 为常用精简集；前沿约 95-97%。

### 代码

- **HumanEval / MBPP**：函数级补全、Pass@1；前沿约 92-94%，区分度趋弱。
- **SWE-bench**：真实 GitHub Issue 修复（完整 2,294 / Verified 500），含金量高；前沿约 50-60%。
- **LiveCodeBench**：动态更新的算法竞赛题，抗污染；Pass@1 约 45-60% 波动。

### 中文特化

- **C-Eval / CMMLU**：中文多学科选择题（13,948 / 11,528 题）；头部约 90-93%。
- **AlignBench**（THUDM）：中文对话与价值观对齐，LLM-as-Judge 满分 10 分；头部约 8.5-9.0。

### 超长上下文

- **NIAH（大海捞针）**：长文档插入无关事实做检索，直观但易被专门优化。
- **RULER**（NVIDIA）：13 个任务含多跳追踪/信息聚合，比 NIAH 更难；128k 上下文前沿约 90-95%。

### 工具调用与智能体

- **BFCL**：Function Calling 正确性（2,000+ 用例，AST 或真实 API 验证）；前沿约 90-93%。
- **WebArena**：沙盒浏览器 812 个真实网页任务，评估 Agent 闭环操作；前沿仅约 35-45%，是当前的难关。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

## 厂商基准偏好

基准选择本身带有叙事性——各家挑能展示自身强项的榜单：OpenAI 偏 GPQA/MATH-500/SWE-bench；Anthropic 偏 SWE-bench/GPQA/WebArena；Google 主打 NIAH 等长上下文；DeepSeek 重 LiveCodeBench/MATH/MMLU-Pro；Moonshot(Kimi) 重 NIAH/AlignBench；Qwen 用 MMLU-Pro/SWE-bench/C-Eval；Mistral/xAI 偏 MMLU/MATH。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

## 方法学新挑战：推理模型的「思考预算」

推理模型引入了早期评测没有的混淆变量：分数取决于模型被允许「想多久」，因此评测必须**固定或报告推理预算**才有可比性，否则就是拿不同算力档位的结果横向比。详见 [[test-time-compute-scaling]] 与 [[reasoning-effort-control]]。理论侧关于「多步推理为何必要」的边界分析见 [[llm-computational-complexity]]。
