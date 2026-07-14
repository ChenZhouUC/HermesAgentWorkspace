---
title: LLM Benchmark Methodology
created: 2026-05-14
updated: 2026-07-14
type: concept
tags: [benchmark, llm]
sources: [_living/AI-Infrastructure/LLM-Benchmarks.md]
confidence: medium
---

# LLM Benchmark Methodology

LLM benchmark 方法论的核心不是寻找一个“总分”，而是明确被测对象、固定评测协议，并把质量、稳定性、资源消耗与适用范围一起报告。同一个模型名在不同 prompt、推理预算、工具、scaffold 或执行环境下可以得到明显不同的结果。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

## 先定义被测对象

| 层级                         | 包含内容                                                    | 分数可以说明什么                                               |
| ---------------------------- | ----------------------------------------------------------- | -------------------------------------------------------------- |
| **Model-only**               | 固定 prompt、无外部工具、一次生成                           | 特定 snapshot 在固定协议下的模型表现                           |
| **Model + inference policy** | [[chain-of-thought                                          | CoT]]、reasoning effort、self-consistency、best-of-N、verifier | 模型与推理预算的组合能力 |
| **Agent system**             | scaffold、工具、浏览器/终端、memory、重试、上下文和停止策略 | 完整系统的任务成功率，而非底模裸能力                           |
| **Product experience**       | 系统提示、路由、多模型协作、搜索索引、缓存和安全策略        | 产品栈在特定用户流程中的综合表现                               |

因此，一条可比较结果至少要绑定模型 snapshot、benchmark version、prompt、推理预算和 harness。Agent、GUI、软件工程和研究任务应明确标成“系统 + 模型”结果。

## 指标语义不能混用

| 指标                      | 回答的问题                  | 常见陷阱                                  |
| ------------------------- | --------------------------- | ----------------------------------------- |
| Accuracy / Exact Match    | 固定答案是否正确            | 答案抽取和格式规则会改变结果              |
| Pass@1                    | 一次采样是否通过全部测试    | 温度、timeout 与测试覆盖度未固定          |
| Pass@k                    | k 个候选里是否至少一个成功  | 只衡量 coverage，不代表系统能选中正确候选 |
| Pass^k                    | 同一任务连续 k 次是否都成功 | 衡量可靠性，不能与 Pass@k 互换            |
| % Resolved / Task Success | Agent 最终是否完成任务      | 高度依赖环境、工具和 scaffold             |
| LLM-as-a-Judge            | 开放式输出是否符合 rubric   | judge 版本、位置、长度与风格偏差          |
| Pairwise Win Rate         | 相对对手池的偏好胜率        | 对手池、抽样与 tie 处理会改变结果         |
| Calibration Error         | 置信度是否匹配真实正确率    | 高 accuracy 不自动意味着校准良好          |

推理模型尤其需要固定或报告 [[reasoning-effort-control|reasoning effort]]、thinking token、采样次数与 verifier；否则是在比较不同 [[test-time-compute-scaling|test-time compute]] 档位，而不只是模型差异。^[[[_living/AI-Infrastructure/LLM-Benchmarks|LLM-Benchmarks]]]

## 最小报告契约

一份可复核的 benchmark 记录至少应包含：

1. **模型**：完整 snapshot/checkpoint、provider、量化和 serving 版本。
2. **数据**：benchmark 名称、release/version、split、过滤条件和评测日期。
3. **提示**：system/developer prompt、shot 设置、CoT 与答案格式。
4. **推理**：effort/budget/mode、temperature、top-p、最大输出、采样或投票次数。
5. **工具与 scaffold**：工具清单、检索源、框架、最大步数、重试和上下文策略。
6. **执行环境**：harness commit、容器或 VM、依赖、CPU/GPU、网络和 timeout。
7. **评分器**：判分脚本与版本；使用 judge 时还要记录 judge snapshot、prompt 和重跑规则。
8. **统计**：有效样本数、独立 run 数、均值/方差或置信区间。
9. **资源**：输入、输出和 reasoning token，wall-clock latency、工具调用数与成本。
10. **污染状态**：训练 cutoff，以及数据是否为 public、live、held-out 或 private split。

缺少这些字段时，结果可以用于线索发现，但不应进入严格横向排名。

## 结果证据状态

- **官方榜**：benchmark 维护方在明确协议下维护的当前榜单；动态榜必须绑定快照日期。
- **独立复测**：第三方用统一 harness 重跑多个模型，并公开复现实验口径。
- **历史结果**：榜单已停止更新的最后公开结果，只用于理解历史难度或回归。
- **无统一榜**：没有持续、同协议、可核验的当前排名；不能从不同厂商模型卡中挑最大值拼成 SOTA。

协议不同的结果不应只因 benchmark 同名而放进同一排序。

## 能力地图与当前社区声望

选择 benchmark 时应先按能力建立组合，而不是让单个经典榜单代表所有能力。常见能力面包括知识与科学推理、数学、代码与软件工程、事实性与检索、指令遵循、多语言、长上下文、多模态、工具/Web/GUI Agent、真实工作和安全稳健性。

以下每一个能力类别中均包含“当前社区声望”字段，用于提示 benchmark 在当前社区中的采用与引用频率：★★★ 表示经常被引用，★★ 表示普通、偶尔被引用，★ 表示已经过时、曾经被使用。该字段不代表题目难度或技术质量。

声望是随时间变化的采用信号，不是永久属性。高声望基准可能已饱和或受污染；低声望历史基准仍可能适合回归，但不应承担前沿区分任务。

## 组合与维护原则

- 每个关键能力至少使用两个机制不同的公开基准，并保留贴近真实用户分布的 private blind set。
- 公开静态集适合回归；live、held-out 或版本化榜单更适合当前区分，但必须记录快照和有效分母。
- 饱和或污染不会让经典基准完全失效，只会把它从“前沿排名”降为“历史锚点或回归门禁”。
- 选择题、开放生成、可执行测试、任务成功率和人工偏好分别测量不同东西，不能压成无解释的平均总分。
- 同时报告质量、Pass^k 稳定性、延迟、token/工具成本和失败类型；安全评测则应报告 harmful compliance、over-refusal、正常 utility 与攻击预算的 Pareto 面。
- 新 benchmark 只有在来源、题数、评分器、版本和可比结果都能说清时才进入主组合；没有可信统一榜时明确留空，不猜数字。
