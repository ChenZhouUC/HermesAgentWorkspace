---
title: LLM Reasoning, Thinking, and Effort
created: 2026-05-24
updated: 2026-07-14
---

# 大模型的「思考」与「努力程度」：Reasoning、Thinking 与 Effort

本文梳理大语言模型从显式 Chain-of-Thought（CoT）提示，到推理模型、推理时计算扩展，以及 API 层 effort / budget / mode / toggle 的演进。文中厂商接口以 **2026-07-13** 的官方文档为快照；这些参数高度依赖具体模型和 API，使用前仍须核对目标模型页。

## 一、先区分几个容易混用的概念

| 概念                          | 含义                                                                                   | 是否通常可见                                                                |
| ----------------------------- | -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Chain-of-Thought / rationale  | 模型生成的自然语言中间步骤；既可由提示词诱发，也可由训练形成                           | 取决于模型和接口                                                            |
| internal reasoning / thinking | 模型在最终回答前或工具调用之间进行的内部计算；不保证等同于一段忠实、完整的自然语言 CoT | 通常不可见或只给摘要，但也有 API 返回 `reasoning_content` / thinking chunks |
| reasoning / thought tokens    | 厂商用于统计内部思考计算的 token 口径                                                  | 通常只在 usage 中给数量                                                     |
| reasoning summary             | 对内部思考生成的摘要，不是原始推理轨迹，也不应视为可审计的因果解释                     | 可按参数请求或由模型默认返回                                                |
| effort / thinking level       | 离散档位，对模型“投入多少推理”的软性指导                                               | 请求参数可见                                                                |
| thinking budget               | 以 token 数表达的预算或上限；是否为硬上限、能否关闭思考均依模型而定                    | 请求参数可见                                                                |
| reasoning mode                | 与 effort 正交的执行模式，例如 standard / pro                                          | 仅部分厂商和模型支持                                                        |
| reasoning state / signature   | 用于跨工具调用或跨轮续接内部推理的 opaque / encrypted item                             | 可传递但通常不可读                                                          |

一个常见误区是把 reasoning、thinking 和 CoT 视为同义词。更准确地说，**reasoning / thinking 通常指模型在回答前的内部推理计算；CoT / rationale 是这种推理被自然语言外显出来的一种形式**。模型可以进行 internal thinking 却不返回原始 CoT；API 返回的 reasoning summary 也只是摘要，不等于可审计的真实推理轨迹。厂商确实会用 reasoning、thinking、effort、budget 等不同名称控制或展示相关能力，但这些字段在可见性、计费口径、预算语义、续接机制和忠实性上并不统一。

### 1.1 Thinking 与正式输出如何分隔

模型本体看到的通常仍是 token 序列，并不会天然拥有“这是思考、那是正式答案”的语义边界；边界来自 **训练数据中的格式约定、chat template / special token、API content block 类型，以及服务端解析与隐藏策略** 的组合。常见实现有三类：

1. **文本标签式分隔**：开源模型和部分 serving stack 会使用 `<think>...</think>`、`reasoning_content`、`Final:` 等模式。模型通过训练学会先生成思考段，再切换到答案段；宿主再按标签或字段解析、隐藏或展示。
2. **结构化 content block**：部分 API 不把 thinking 当作普通 assistant 文本，而是以 typed thinking chunks、reasoning items、summary 或 signature 的形式传输。此时“思考”和“正式输出”的边界主要由 API 协议和服务端实现维护。
3. **完全隐藏的内部推理**：有些商业 reasoning 模型只暴露最终答案、usage 中的 reasoning token 计数，或二次生成的 summary。调用方看不到原始轨迹，因此不能把 summary 当作真实 CoT。

因此，`<think>` 或 XML 风格标签更像是**可学习的格式约定**，不是安全边界。模型可能漏写、提前闭合、把答案写进 thinking，或把 thinking 泄漏到 final；生产系统需要由宿主层解析、过滤、schema 校验和权限控制来兜底。更一般的文本协议问题见 `wiki/_living/AI-Infrastructure/Text-Format-Protocol-for-LLMs.md`。

这也引出本文的关键结论：**“更多思考”不是一个跨厂商统一量纲**。同名的 `high` 不代表相同 token、延迟或算力，token budget 也不等价于实际消耗；公平比较必须同时固定模型快照、API、提示、工具、采样参数和推理预算。

## 二、技术脉络：从提示词到推理时计算

本章主线是 **test-time compute**：在一次请求中，如何通过额外推理时计算提高答案质量。**2.1 关注候选推理轨迹的生成**，也就是如何通过提示、采样、分解、搜索和工具交互让模型展开更多或更结构化的思路；**2.2 关注候选轨迹的选择与计算分配**，也就是如何从大量候选中选出可部署答案，并把预算分配给更值得的题目。由于 verifier、reward model 和过程监督通常需要训练，2.2 会自然过渡到第三章；但会更新模型权重或训练辅助模型的内容，统一放在第三章讨论。

### 2.1 CoT、采样与搜索

- **Chain-of-Thought Prompting（Wei et al., 2022）**：在 few-shot 示例中加入中间推理步骤，显著改善部分算术、常识和符号推理任务。原论文观察到收益主要出现在足够大的模型上，但没有给出可泛化到所有架构的固定参数阈值；不宜简化成“超过 10B 就涌现”。
- **Zero-shot CoT（Kojima et al., 2022）**：追加“Let's think step by step”即可在不提供示例时诱发多步推理。原论文中 `17.7% -> 78.7%` 是 **MultiArith**；GSM8K 对应的是 `10.4% -> 40.7%`（text-davinci-002）。
- **Self-Consistency（Wang et al., 2022）**：采样多条推理路径，再对最终答案做多数投票或边缘化。它把额外推理时计算用于“多样化候选 + 聚合”，但前提是任务存在可稳定归一化的最终答案。
- **Least-to-Most（Zhou et al., 2022）**：把复杂问题拆成由易到难的子问题，前一步答案进入后一步。
- **Tree of Thoughts（Yao et al., 2023）**：在 thought 节点上显式搜索、评估和回溯；论文报告 GPT-4 在 Game of 24 上从 CoT 的 4% 提升到 ToT 的 74%。**Graph of Thoughts（Besta et al., 2023）**进一步允许合并和循环依赖。
- **ReAct（Yao et al., 2022）**：把 reasoning、action 和 observation 交错，是后来“思考 - 工具调用 - 观察 - 继续思考”智能体循环的重要前身。

这些方法至少包含三种不同的 test-time compute：延长单条轨迹、并行采样多条轨迹、在候选空间中搜索。把它们都压缩成“多生成一些 CoT token”会丢掉核心差异。

### 2.2 候选选择、过程验证与计算最优分配

如果说 2.1 主要处理“生成哪些候选”，2.2 处理的是“如何选择候选、何时继续搜索、预算花到哪里”。多采样带来的 pass@k / coverage 只有在存在可靠 verifier 时才能转化为部署成功率；固定 best-of-N 往往也不是计算最优，因为简单题和难题对额外推理预算的边际收益不同。

- **过程验证器（PRM）**：相对只评最终答案的结果奖励模型（ORM），过程奖励模型（PRM）能给中间步骤打分，因此可以把 ToT、MCTS 或 best-of-N 的候选选择从“最终答案投票”推进到“逐步筛选”。PRM 如何训练属于第三章的问题；这里的重点是它在运行时如何支撑搜索和候选选择。
- **Large Language Monkeys（Brown et al., 2024）**：重复采样的 pass@k / coverage 可随样本数继续上升；论文在 SWE-bench Lite 上报告 DeepSeek-Coder-V2-Instruct 从单样本 15.9% 到 250 样本覆盖率 56%。但 coverage 不是可直接部署的成功率：必须有足够好的 verifier 从大量候选中选出正确解。
- **Scaling LLM Test-Time Compute Optimally（Snell et al., 2024）**：比较基于过程验证器的搜索和自适应修订，强调应按题目难度分配计算，而不是对所有题固定 best-of-N。论文在特定模型、任务和 FLOPs 口径下报告了相对 best-of-N 超过 4 倍的效率提升，以及小模型在合适难度区间击败 14 倍大模型的结果；这些数字不应外推为通用比例。
- **OpenAI o1 系列（2024-09，首发 o1-preview / o1-mini）**：把“训练期强化学习 + 推理期内部思考时间”作为两条扩展轴，并在产品 API 中引入隐藏 reasoning tokens，成为前沿推理模型产品化的重要转折点；正式命名的 o1 在 2024-12 才发布。

## 三、推理能力如何训练

第二章讨论的是“请求来了以后如何多花计算”；第三章讨论的是“模型或辅助模型如何被训练得更会推理”。这里的边界是是否更新参数：自举、过程监督、RLVR 和蒸馏会改变模型或 verifier / reward model；而 best-of-N、ToT、MCTS 等搜索方法本身是运行时策略，但经常依赖这些训练产物。

### 3.1 训练信号从哪里来

推理训练的关键不是抽象地让模型“学会思考”，而是先明确 **GT / reward / verifier 从哪里来**。不同任务能提供的真值强度差异很大：数学、代码和形式化证明等任务可以提供可验证的最终答案或执行结果；过程监督需要人工或程序化地标注中间步骤；蒸馏和自举则常使用强模型或模型自身生成的轨迹，但这些轨迹通常只是 pseudo-label，必须依赖最终答案、测试、proof checker、人工标注或 learned verifier 过滤。

| 训练信号                        | 典型来源                                       | 主要用途                             | 主要限制                                          |
| ------------------------------- | ---------------------------------------------- | ------------------------------------ | ------------------------------------------------- |
| 最终答案 GT                     | 题库答案、选择题标签、标准数学答案             | SFT、结果奖励、候选筛选              | 只能判断最终结果，不能保证中间推理正确或忠实      |
| 可执行评价函数                  | 单元测试、编译器、proof checker、环境成功条件  | RLVR、代码 / 形式化数学 / agent 任务 | 覆盖不完整时会被 reward hacking；开放式任务难构造 |
| 过程级标注                      | 人工逐步标注、可验证子状态、形式化 proof state | PRM、过程监督、搜索过程打分          | 标注成本高，跨领域一致性难                        |
| 教师或自举伪标签                | 强模型 CoT、模型自身成功轨迹、多样本投票结果   | 蒸馏、STaR、自举 SFT                 | 不是独立真值；需要 verifier 或人工过滤错误轨迹    |
| Learned verifier / reward model | ORM、PRM、LLM judge、偏好模型                  | best-of-N rerank、搜索、RL           | 本身会犯错，也可能被策略模型利用                  |

因此，reasoning 训练的核心瓶颈通常不是“能不能生成长 CoT”，而是“有没有足够可靠、可扩展的信号判断哪些答案或步骤值得学习”。

### 3.2 Thinking / final 格式如何训练

thinking 与 final 的分隔通常不是单独训练一个“格式分类器”，而是在同一个生成模型里同时学习**内容能力**和**输出协议**。典型做法包括：

- **格式化 SFT**：把训练样本序列化成目标 chat template，例如“用户问题 -> assistant thinking 段 -> final 段”。损失可以覆盖全部 token，也可以按实现对部分 reasoning token 做 mask；关键是模型在大量样本中看到“先推理、再给答案”的边界模式。
- **蒸馏轨迹**：强模型或搜索系统生成带 thinking/final 分隔的长轨迹，经最终答案、测试、verifier 或人工过滤后，用同样格式训练 student。student 学到的不只是解题步骤，也包括何时结束 thinking、如何切换到 final。
- **RL / RLVR 约束格式**：奖励通常来自最终答案、测试或环境成功，但系统可以把“格式可解析”“final 中不泄漏隐藏思考”“工具调用字段合法”等作为硬解析条件或奖励 / 惩罚项。这样模型会同时优化任务正确性和输出协议。
- **过程监督**：PRM 或人工步级标注可以给 thinking 段中的中间步骤打分，但它评的是步骤质量，不等于证明这段文本就是模型真实内部因果过程。

公开模型常把格式显式写进 chat template 或训练数据；商业模型则可能把 reasoning 通道、summary、signature 和加密续接项做成服务端协议。两者都依赖训练和解码时的协议约束，但可见性和可审计性不同。

### 3.3 自举与过程监督

- **STaR（Zelikman et al., 2022）**：生成 rationale，保留能导出正确答案的样本；对错误样本可给定答案再 rationalize，然后用成功轨迹微调并迭代。这是“用模型自己的成功推理进行自举训练”的早期代表，但筛选仍依赖题库答案或 verifier：模型自己生成的是 rationale，不是真值。
- **Let's Verify Step by Step（Lightman et al., 2023）**：区分过程奖励模型（PRM）和结果奖励模型（ORM），并发布 PRM800K。论文在其 MATH 候选选择设置中发现过程监督优于结果监督；这不是“所有任务上 PRM 必然优于 ORM”的普遍定理。训练好的 PRM 既可以作为训练信号，也可以在运行时作为 verifier 支撑 2.2 中的候选选择。

### 3.4 RLVR 与 GRPO

**RLVR（Reinforcement Learning with Verifiable Rewards）**使用可程序验证的结果作为奖励，例如数学最终答案或代码测试。它减少了对 learned preference / reward model 的依赖，适合答案可验证的任务；但它**不会自动消除 reward hacking**，错误测试、答案抽取漏洞、代理指标和分布外泛化仍可能被利用，对开放式任务也缺少天然 verifier。

- **PPO** 是常见 actor-critic 方法。实现通常需要 value function，但 critic 是否与策略同规模取决于具体系统，不能写成硬性要求。
- **GRPO（Group Relative Policy Optimization）**由 DeepSeekMath 系统化使用：对同一 prompt 采样一组输出，按组内奖励归一化估计相对优势，从而不训练单独的 value model。
- **DeepSeek-R1-Zero（2025-01）**从 DeepSeek-V3-Base 出发，不做面向 reasoning 的 SFT，使用规则奖励和 GRPO 训练，出现自检、回溯和更长推理等行为。它不是“无预训练、从零开始的纯 RL”。DeepSeek-R1 随后加入冷启动数据和多阶段训练，以改善可读性、语言混杂和通用能力。

### 3.5 蒸馏与搜索生成数据

- **蒸馏**：用强推理模型生成长轨迹，对较小基座做 SFT。教师轨迹是 pseudo-label，不是严格 GT；更可靠的蒸馏通常会用最终答案、测试、verifier 或人工检查过滤。DeepSeek-R1 论文给出的受控对照中，DeepSeek-R1-Distill-Qwen-32B 在所列五项指标上均高于对 Qwen2.5-32B-Base 进行超过 10K 步 RL 得到的 Qwen2.5-32B-Zero；这个单组 32B 对照不能外推成“蒸馏通常优于 RL”的普遍规律。
- **搜索生成训练数据**：Tree of Thoughts、MCTS、best-of-N 和过程奖励搜索本身是运行时策略；放到训练章时，重点是用 verifier 从搜索候选中筛出高质量轨迹，再用于 SFT、蒸馏或后续 RL。代码和形式化数学较容易构造外部验证器；开放问答、价值判断和长期 agent 任务的 verifier 更难可靠。

## 四、API 控制面：截至 2026-07-13

### 4.1 共性与非共性

1. **effort / level 通常是软信号**：模型可按题目难度自适应，档位不直接承诺 token 数。
2. **budget 才以 token 表达**，但可能是软预算，模型可少用或在实现允许时溢出 / 下溢。
3. **并非所有推理模型都能关闭思考**；有的提供 hybrid toggle，有的始终推理，有的拆成独立 Instruct / Thinking checkpoint。
4. **原始 CoT 并非一律隐藏**：OpenAI 通常只给摘要；Anthropic / Gemini 主要给摘要和签名；DeepSeek、Qwen 或 Mistral 的部分接口会返回 `reasoning_content` 或 typed thinking chunks。
5. **思考 token 的计费和上下文口径不同**。常见做法是按输出 token 计费并占用输出 / 上下文预算，但必须以目标模型价格页为准。

### 4.2 厂商快照

| 厂商              | 当前主要控制                                                                                                                                                                                                                                          | 可见性与续接                                                                                                                                                                  | 重要边界                                                                                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenAI**        | Responses API 使用 `reasoning.effort`；GPT-5.6 支持 `none / low / medium / high / xhigh / max`。另有独立的 `reasoning.mode: standard / pro`                                                                                                           | 原始 reasoning tokens 不返回；`reasoning.summary: auto` 请求摘要。`reasoning.context` 和 reasoning items 可在支持的模型上跨轮续接；ZDR / `store:false` 可传 encrypted content | 档位、默认值和 `reasoning.context` 支持均依模型。Responses API 总生成上限字段是 `max_output_tokens`，不是 Chat Completions 的 `max_completion_tokens` |
| **Anthropic**     | 新模型推荐 `thinking: {type: "adaptive"}` + `output_config.effort`；支持的 `low / medium / high / xhigh / max` 依模型。旧模型使用 `enabled + budget_tokens`                                                                                           | thinking block 可设 `display: summarized / omitted`，signature 用于续接；adaptive 自动支持工具间 interleaved thinking                                                         | `budget_tokens` 在 Opus / Sonnet 4.6 已弃用，在更新模型上可能直接不支持；有些 Claude 5 型号始终开启 adaptive thinking，不能 `disabled`                |
| **Google Gemini** | Interactions API 使用 `generation_config.thinking_level`；当前 Gemini 3.5 Flash 等 3.x 型号常见 `minimal / low / medium / high`，支持集和默认值依型号。旧 GenerateContent API 用 `thinkingConfig.thinkingLevel`；Gemini 2.5 原生使用 `thinkingBudget` | Interactions API 用 first-class thought steps、summary 和 signature；stateful 模式可由服务保存，stateless 模式必须原样回传。GenerateContent 可用 `includeThoughts` 请求摘要   | 2.5 Pro 的思考不能关闭；3.x 的 `minimal` 也不保证完全不推理。3.x 仅为向后兼容接受 `thinkingBudget`，官方推荐 level，并警告 budget 可能导致异常表现    |
| **DeepSeek**      | 当前 V4 API 用 `thinking.type: enabled / disabled`；effort 为 `high / max`                                                                                                                                                                            | 返回 `reasoning_content`，工具链和多轮续接需要保留相关字段                                                                                                                    | 默认开启 thinking；兼容输入中的 `low / medium` 映射为 `high`，`xhigh` 映射为 `max`，不是四个独立算力档                                                |
| **Qwen**          | 原始 Qwen3 hybrid checkpoint 支持模板级 `enable_thinking` 与 `/think`、`/no_think`；后续也发布过分离的 Instruct-only / Thinking-only checkpoint。当前 Model Studio 已列 Qwen3.6 / 3.7 系列，部分型号支持 thinking preservation，具体开关以模型卡为准  | 开源部署常以 `reasoning_content` 或 `<think>` 解析；是否保留跨轮思考取决于 chat template 和 serving stack                                                                     | `thinking_budget` 不是所有 Qwen 模型、Model Studio API 或推理框架的统一稳定字段；不要把 Qwen3 某一代的 hybrid 行为外推到全系列                        |
| **xAI**           | 当前 Grok 4.5 reasoning 模型使用 `reasoning_effort: low / medium / high`，默认 high                                                                                                                                                                   | 支持 reasoning summaries / encrypted reasoning                                                                                                                                | 当前 reasoning 型号不能完全关闭思考；已退役的 Grok 4 Fast 不应再当作现行 API 示例                                                                     |
| **Mistral**       | Magistral Small / Medium 2507（1.1）是当前公开推理系列，API 没有统一 effort / budget 旋钮                                                                                                                                                             | API 可返回 typed thinking chunks                                                                                                                                              | “Magistral 1.2 加入视觉”缺乏官方依据，可能是与 Mistral Small 3.2 混淆；不能据此写入                                                                   |

### 4.3 控制面演进趋势：以 OpenAI 为例

上表已经覆盖各厂商的主要接口差异；这里单列 OpenAI 不是因为只有它代表 reasoning API，而是因为它把几个容易混淆的控制维度集中暴露在同一套 Responses API 中，适合作为“控制面从单一旋钮走向多轴状态”的例子。GPT-5.6 把控制面从单一 effort 扩展为三层：

- `reasoning.effort` 决定 standard 或 pro 模式内的推理投入；
- `reasoning.mode` 决定 standard / pro 执行路径，二者彼此独立；
- `reasoning.context` 决定是否允许兼容的历史 reasoning items 进入后续采样。

因此，“模型多想一点”不再只是增加当前轮 token，也可能涉及不同执行模式和跨轮 reasoning state。调用方应同时记录这三项，不能只记录模型名。

## 五、研究边界：更多思考不保证更正确

### 5.1 Inverse scaling 是存在性结果，不是普遍定律

**Inverse Scaling in Test-Time Compute（Gema et al., 2025，TMLR 2025-12）**构造了四类任务，观察到延长推理会降低准确率，并归纳出干扰项、问题框架过拟合、虚假相关、复杂约束失焦和潜在风险行为放大等失败模式。它证明“test-time compute 单调提升性能”不是普遍规律，但不等于所有真实任务都应设置同一个硬上限，也不能反推某个产品路由器就是为该论文结论而设计。

### 5.2 推理文本不等于忠实解释

**Language Models Don't Always Say What They Think（Turpin et al., 2023）**表明，模型的 CoT 可能受偏置特征影响却不在解释中承认。再加上商业 API 常返回的是二次生成的 summary，工程上应把 reasoning text / summary 当作调试线索，而不是唯一的审计证据、事实来源或安全证明。

### 5.3 实际选档原则

- 先用代表性任务建立 `quality / latency / total tokens / cost / tool success` 基线，再比较相邻 effort；不要默认拉满。
- 对简单检索、分类、格式转换，先测低档或关闭思考；对复杂规划、代码调试、数学和长程 agent，再逐档提高。
- 对同一模型同时报告模型 snapshot、API、effort / budget / mode、最大输出、工具和采样次数。
- 对多轮工具调用，按厂商要求原样保留 reasoning items、thinking blocks 或 signatures；丢失它们可能让模型重复思考或降低工具链质量。
- 若任务可能出现 inverse scaling，直接用该任务的验证集画出“预算 - 成功率 - 成本”曲线；不要用通用榜单代替工作负载评测。

## 参考资料

### 论文

- [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (2201.11903)](https://arxiv.org/abs/2201.11903)
- [Large Language Models are Zero-Shot Reasoners (2205.11916)](https://arxiv.org/abs/2205.11916)
- [Self-Consistency Improves Chain of Thought Reasoning (2203.11171)](https://arxiv.org/abs/2203.11171)
- [Least-to-Most Prompting (2205.10625)](https://arxiv.org/abs/2205.10625)
- [ReAct (2210.03629)](https://arxiv.org/abs/2210.03629)
- [Tree of Thoughts (2305.10601)](https://arxiv.org/abs/2305.10601)
- [Graph of Thoughts (2308.09687)](https://arxiv.org/abs/2308.09687)
- [STaR (2203.14465)](https://arxiv.org/abs/2203.14465)
- [Let's Verify Step by Step (2305.20050)](https://arxiv.org/abs/2305.20050)
- [Large Language Monkeys (2407.21787)](https://arxiv.org/abs/2407.21787)
- [Scaling LLM Test-Time Compute Optimally (2408.03314)](https://arxiv.org/abs/2408.03314)
- [DeepSeekMath / GRPO (2402.03300)](https://arxiv.org/abs/2402.03300)
- [DeepSeek-R1 (2501.12948)](https://arxiv.org/abs/2501.12948)
- [Inverse Scaling in Test-Time Compute (2507.14417)](https://arxiv.org/abs/2507.14417)
- [Language Models Don't Always Say What They Think (2305.04388)](https://arxiv.org/abs/2305.04388)

### 官方接口与模型文档（访问于 2026-07-13）

- [OpenAI Reasoning models](https://developers.openai.com/api/docs/guides/reasoning)；[Using GPT-5.6](https://developers.openai.com/api/docs/guides/latest-model.md)
- [Anthropic Adaptive thinking](https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking)；[Extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)；[Effort](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Gemini Thinking](https://ai.google.dev/gemini-api/docs/thinking)
- [DeepSeek Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode)
- [Qwen3.6 official repository](https://github.com/QwenLM/Qwen3.6)；[Alibaba Model Studio deep thinking and model matrix](https://www.alibabacloud.com/help/en/model-studio/deep-thinking)
- [xAI Reasoning](https://docs.x.ai/developers/model-capabilities/text/reasoning)
- [Mistral Reasoning](https://docs.mistral.ai/docs/capabilities/reasoning)
