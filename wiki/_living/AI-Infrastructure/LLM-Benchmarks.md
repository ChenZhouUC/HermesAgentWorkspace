---
title: LLM Benchmarks
created: 2026-05-14
updated: 2026-05-15
---

# AI 大模型 Benchmark 系统性调研报告

本文整理常见大模型基准测试的定位、测试方式和厂商使用偏好。模型跑分变化很快，文中的分数和厂商倾向只适合作为 2026-04 左右的阶段性参考；如用于正式选型，应以各基准官网、论文和最新模型报告为准。

## 一、综合知识与逻辑推理

### 1. MMLU (Massive Multitask Language Understanding)

- 维护者 / 提供方：Dan Hendrycks 等学术研究者。
- 测试能力：覆盖 57 个学科的综合知识与语言理解能力。
- 题目数量：约 15,908 题，测试集常取 14,049 题。
- 题目类型：4 选项单选题，涵盖 STEM、人文、社科等学科。
- 测试方式：通常采用 5-shot 或 0-shot，通过计算模型输出选项 token 的概率分布判定准确率。
- 厂商使用：行业通用基准，OpenAI、Google、Anthropic、Meta、Mistral 及国内主流厂商都经常引用。
- 分数参考：满分 100%。截至本文整理时，前沿模型大多集中在 88-90% 左右。

### 2. MMLU-Pro

- 维护者 / 提供方：TIGER-AI-Lab 等。
- 测试能力：MMLU 的强化版，增加推理难度，减少单纯记忆型题目。
- 题目数量：约 12,000+ 题。
- 题目类型：10 选项单选题，随机猜测概率更低。
- 测试方式：通常结合 CoT（思维链）推理，强化多步逻辑能力评估。
- 厂商使用：Qwen、DeepSeek、GLM 等新模型报告较常引用。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 75-80% 区间。

### 3. GPQA (Google-Proof Q&A)

- 维护者 / 提供方：纽约大学（NYU）、Anthropic 等。
- 测试能力：博士级专业知识与推理能力，涵盖生物、物理、化学。
- 题目数量：448 题，其中 Diamond 子集 198 题。
- 题目类型：4 选项单选题。
- 测试方式：题目设计强调专业性和反搜索性，常采用 0-shot CoT 测试。
- 厂商使用：Anthropic、OpenAI、DeepSeek 等常用来展示前沿科学推理能力。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 70-75% 区间。

### 4. ARC-c (AI2 Reasoning Challenge - Challenge Set)

- 维护者 / 提供方：Allen Institute for AI (AI2)。
- 测试能力：小学到初中级别自然科学常识和推理。
- 题目数量：ARC 全集 7,787 题，Challenge 挑战集 2,590 题。
- 题目类型：单项选择题。
- 测试方式：从原始题库中提取简单算法不易猜对的题目，评估基础科学常识推理。
- 厂商使用：常作为轻量级模型和通用模型的基础智力基线。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 96-97% 区间。

### 5. AGIEval

- 维护者 / 提供方：微软等研究者。
- 测试能力：人类考试相关任务，如高考、司法考试、SAT 等。
- 题目数量：约 8,062 题。
- 题目类型：单选题、多选题、填空题混合。
- 测试方式：题目来源于高标准真实考试，支持 zero-shot 或 few-shot。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 80-85%+ 区间。

### 6. BBH (BIG-Bench Hard)

- 维护者 / 提供方：Google 等学术界联合。
- 测试能力：23 个高难度推理任务，关注早期模型表现不佳的任务类型。
- 题目数量：6,511 题。
- 题目类型：多项选择题与自由文本回答。
- 测试方式：从 BIG-Bench 中挑选困难任务，如布尔逻辑、导航规划等，通常使用 3-shot CoT。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 90-92% 区间。

## 二、数学能力

### 1. GSM8K (Grade School Math 8K)

- 维护者 / 提供方：OpenAI。
- 测试能力：小学级别数学应用题。
- 题目数量：约 8,500 题。
- 题目类型：自由回答，主要是计算题。
- 测试方式：要求模型生成解题步骤并给出最终数字，通常用 Exact Match 提取最终答案；常见设置是 8-shot CoT。
- 厂商使用：通用数学能力基线。由于许多现代模型分数已很高，区分度逐渐下降。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 96-98% 区间。

### 2. MATH / MATH-500

- 维护者 / 提供方：UC Berkeley Dan Hendrycks 团队等。
- 测试能力：高中到大学级别数学竞赛题。
- 题目数量：原集 12,500 题；MATH-500 是常用精简评测集。
- 题目类型：自由回答，覆盖代数、几何、数论等。
- 测试方式：要求输出标准数学答案，常用 Exact Match 或答案抽取评测。
- 厂商使用：DeepSeek、OpenAI、xAI、GLM、Qwen 等经常引用，用于展示数学推理能力。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 95-97% 区间。

## 三、代码与编程能力

### 1. HumanEval & MBPP

- 维护者 / 提供方：OpenAI（HumanEval）/ Google（MBPP）。
- 测试能力：函数级代码补全能力。
- 题目数量：HumanEval 164 题；MBPP 974 题。
- 题目类型：给定函数签名和注释，要求写出完整函数体。
- 测试方式：使用 Pass@1 或 Pass@k，通过执行沙盒中的单元测试判定。
- 现状：主流模型得分较高，已难以充分反映真实软件工程能力。
- 分数参考：满分 100%（Pass@1）。截至本文整理时，前沿模型约在 92-94% 区间。

### 2. SWE-bench

- 维护者 / 提供方：普林斯顿大学、芝加哥大学等。
- 测试能力：真实软件工程 bug 修复能力。
- 题目数量：完整版 2,294 题；Verified 子集 500 题。
- 题目类型：真实 GitHub 仓库 Issue 修复。
- 测试方式：模型进入真实代码库环境，根据 Issue 描述检索代码、定位 bug、生成补丁，并通过官方单元测试验证。
- 厂商使用：含金量较高，Anthropic、OpenAI、DeepSeek、Qwen、Meta、xAI 等都关注该基准。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 50-60% 区间，Qwen 2.5 Coder 等开源模型约可达 40-50%。

### 3. LiveCodeBench

- 维护者 / 提供方：学术界联合维护。
- 测试能力：算法编程能力与训练后新题泛化能力。
- 题目数量：动态更新，每月发布新题。
- 题目类型：LeetCode、AtCoder 等平台算法竞赛题。
- 测试方式：收集模型训练截止日期之后产生的新题，降低刷榜和数据污染风险。
- 厂商使用：DeepSeek、Qwen 等常用来展示代码泛化能力。
- 分数参考：满分 100%。因题目持续变化，截至本文整理时，前沿模型 Pass@1 大约在 45-60% 区间波动。

## 四、中文特化能力

### 1. C-Eval & CMMLU

- 测试能力：中文综合知识与多学科理解能力。
- 题目数量：C-Eval 13,948 题；CMMLU 11,528 题。
- 题目类型：中文 4 选项单选题，覆盖文理科和中国本土文化。
- 测试方式：类似 MMLU，采用 5-shot 或 0-shot 计算选项 token 概率。
- 厂商使用：百川、智谱、阿里通义、MiniMax 等国产模型报告常引用。
- 分数参考：满分 100%。截至本文整理时，头部模型约在 90-93% 区间。

### 2. AlignBench

- 维护者 / 提供方：清华大学（THUDM）。
- 测试能力：中文对话能力与价值观对齐。
- 题目数量：683 题。
- 题目类型：开放式问答，涵盖基本语言、高级理解、开放指令遵循等。
- 测试方式：不设标准答案，采用 LLM-as-a-Judge 给输出打 1-10 分。
- 厂商使用：Kimi、GLM 等常用于展示中文对话体验。
- 分数参考：满分 10 分。截至本文整理时，头部模型约在 8.5-9.0 分区间。

## 五、超长上下文能力

### 1. NIAH (Needle In A Haystack)

- 题目类型：文档 QA / 信息提取。
- 测试方式：将一句无关事实随机插入长文档不同深度位置，让模型检索并回答；结果通常表现为网格图。
- 厂商使用：Kimi、Claude、Gemini、GLM、MiniMax 等主打长文本模型常引用。
- 分数参考：满分 100%。该测试对模型长上下文召回能力有直观展示，但容易被专门优化，需结合更复杂任务评估。

### 2. RULER

- 维护者 / 提供方：NVIDIA 及联合学者。
- 测试能力：比 NIAH 更复杂的长文本理解，包含多针检索、信息提取、聚合计算等任务。
- 题目类型：长文本上下文理解基准。
- 测试方式：包含多跳追踪（Multi-hop）、信息聚合等 13 个任务，防止模型只记住位置而不理解长文逻辑。
- 厂商使用：DeepSeek、Qwen 等长文本技术报告较常引用。
- 分数参考：满分 100%。截至本文整理时，前沿模型在 128k 上下文中约可达 90-95%。

## 六、工具调用与智能体能力

### 1. BFCL (Berkeley Function Calling Leaderboard)

- 测试能力：评估模型是否能准确解析用户意图并生成正确 API JSON 调用。
- 题目数量：2,000+ 测试用例。
- 测试方式：测试模型在单轮或多轮对话中输出 API 参数的正确性，通过 AST 分析或真实 API 执行验证。
- 厂商使用：OpenAI、DeepSeek、GLM、Mistral 等都常强调 Function Calling 表现。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 90-93% 区间。

### 2. WebArena

- 测试能力：浏览器环境中的复杂任务执行能力。
- 题目数量：812 个真实网页任务。
- 题目类型：电商、论坛等网页环境任务。
- 测试方式：提供完整沙盒浏览器环境，模型输出点击、输入、滚动等动作指令完成闭环任务。
- 厂商使用：常用于评估 Agent 真实网页操作能力，Claude 等模型报告较常引用。
- 分数参考：满分 100%。截至本文整理时，前沿模型约在 35-45% 区间。

## 七、厂商常用基准偏好

- OpenAI：常用 GPQA、MATH-500、SWE-bench 展示科学推理、数学和工程能力。
- Anthropic：常用 SWE-bench、GPQA、WebArena 展示编码和 Agent 能力。
- Google：常展示 NIAH 等长上下文相关基准。
- DeepSeek：重视 LiveCodeBench、MATH、MMLU-Pro 等代码与数学基准。
- Kimi / Moonshot：重视 NIAH、AlignBench 等长文本和中文对话基准。
- Qwen / 通义千问：常用 MMLU-Pro、SWE-bench、C-Eval / CMMLU 等展示开源与中文能力。
- 智谱 AI：常用 AlignBench、C-Eval、MMLU 等展示中文综合能力与对齐体验。
- 百川智能：常引用中文和垂直领域 Benchmark。
- MiniMax：常强调多模态、语音和拟人化交互相关评测。
- Mistral AI：常通过 MMLU 等开源基准展示参数效率和 MoE 架构能力。
- xAI：偏好 MATH、MMLU 及自建实时数据相关基准。

## 八、核心大模型厂商与代表作

### 8.1 国内厂商

- 智谱 AI (Zhipu AI)：代表作 GLM-4 与 GLM-4V，开源 ChatGLM 系列在端侧部署和学术界有较高知名度。
- 深度求索 (DeepSeek)：代表作 DeepSeek-V2 / V3 / R1，主打性价比、开源 MoE 架构、代码与数学推理。
- 阿里通义 (Qwen)：代表作 Qwen 2.5 系列，覆盖小参数到大参数开源模型，是国内应用广泛的开源底座之一。
- 月之暗面 (Moonshot AI)：代表作 Kimi，主打长文本处理、文档解析和长链条逻辑。
- 百川智能 (Baichuan AI)：代表作 Baichuan 3，关注中文语境理解和垂直行业应用。
- 稀宇科技 (MiniMax)：代表作 abab6.5，在语音、多模态和角色交互场景中较活跃。

### 8.2 国际厂商

- OpenAI：代表作 GPT-4o / o1，在多模态实时交互和推理模型方向影响力较大。
- Anthropic：代表作 Claude 3.5 Sonnet / Opus，重视 AI 安全和代码能力。
- Google：代表作 Gemini 1.5 Pro / 2.0，重视长上下文和原生多模态能力。
- Meta：代表作 Llama 3 系列，是开源大模型生态的重要参与者。
- Mistral AI：代表作 Mistral / Mixtral，以高效模型结构和开源模型闻名。
- xAI：代表作 Grok-2 / 3，强调实时数据能力和开放权重策略。

## 参考文献

1. Hendrycks, Dan, et al. "Measuring Massive Multitask Language Understanding." arXiv preprint arXiv:2009.03300 (2020).
2. Chen, Mark, et al. "Evaluating Large Language Models Trained on Code." arXiv preprint arXiv:2107.03374 (2021).
3. Cobbe, Karl, et al. "Training Verifiers to Solve Math Word Problems." arXiv preprint arXiv:2110.14168 (2021).
4. Huang, Yuzhen, et al. "C-Eval: A Multi-Level Multi-Discipline Chinese Evaluation Suite for Foundation Models." arXiv preprint arXiv:2305.08322 (2023).
5. Zhong, Wanjun, et al. "AGIEval: A Human-Centric Benchmark for Evaluating Foundation Models." arXiv preprint arXiv:2304.06364 (2023).
6. Suzgun, Mirac, et al. "Challenging BIG-Bench Tasks and Whether Chain-of-Thought Can Solve Them." arXiv preprint arXiv:2210.09261 (2022).
