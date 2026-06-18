---
title: AI Coding Agent Tooling Landscape
created: 2026-06-15
updated: 2026-06-17
review-date: 2026-09-15
sources: [cursor, devin, opencode, aider, cline, kilo, cline-kanban, vibe-kanban, github-api]
---

> **版本口径**：本文按 2026-06-15 的公开资料和 GitHub API 快照整理。AI Coding 工具变化极快，具体价格、模型、额度、插件和 CLI 参数应以官方文档为准。
>
> **排除口径**：本文不把已经在本机重点跟踪的 `claudecode`、`codexcli`、`qwencli`、`geminicli`、`copilotcli` 放入 Top2 候选。本文也不再单列“VS Code 插件 / 审查层”方向，因为这类能力正在被 IDE、CLI/TUI、Agent Runtime 和 Kanban 编排层吸收。

# AI Coding Agent 工具版图：四条主线与 Top2 跟踪对象

## 1. 总览结论

当前 AI Coding 工具可以先按“主入口”和“工作流控制层”分成四条线：

| 方向                                  | Top2 跟踪对象                    | 本质定位                                                                   | 为什么保留这一类                                                        |
| ------------------------------------- | -------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| AI IDE / VS Code forks                | Cursor、Devin Desktop / Windsurf | 把编辑器、代码理解、补全、Agent、云端执行和团队管理打包成一体化产品        | 这是最强的闭源产品化路线，适合观察商业化、团队协作和默认工作流如何演化  |
| CLI / TUI 强者                        | OpenCode、Aider                  | 以终端为主入口，让 Agent 直接读写仓库、运行命令、管理 Git                  | 更接近“terminal 是主战场”的方向，也最容易纳入个人 dotfiles 和自动化流程 |
| CLI 兼顾 IDE 插件的开源 Agent Runtime | Cline、Kilo Code                 | 同一 Agent 内核覆盖 IDE、CLI、SDK、云端或多 Agent 管理                     | 这是开源生态里最像“agentic engineering platform”的路线                  |
| Kanban / Agent 可视化管理方法论       | Cline Kanban、Vibe Kanban        | 用卡片、工作区、worktree、diff review、agent 状态监控来管理多个 Agent 任务 | 它不是单一工具，而是一套逐渐被各家采用的 Agent 工作方法                 |

一个简化判断：

- 如果要观察闭源 AI IDE 的产品力和商业化：看 Cursor 与 Devin Desktop。
- 如果要把本地终端作为核心控制台：看 OpenCode 与 Aider。
- 如果要找开源、可二开、跨 IDE/CLI/SDK 的 Agent Runtime：看 Cline 与 Kilo Code。
- 如果要同时启动、管理、监控多个 Agent 任务：看 Kanban 方法论，以及 Cline Kanban / Vibe Kanban 这类实现。

## 2. 选择口径

本文的“社区声量”不是单一指标。开源项目优先看 GitHub stars、forks、issue 活跃度、最近 push；闭源 IDE 不能用 GitHub stars 横向比较，因此看官方产品定位、用户规模公开口径、团队背景、生态讨论和商业化强度。

截至 2026-06-15 的 GitHub API 快照：

| 项目         | GitHub repo           |   Stars |  Forks | Open issues | 创建时间   | 最近 push  | License    |
| ------------ | --------------------- | ------: | -----: | ----------: | ---------- | ---------- | ---------- |
| OpenCode     | `anomalyco/opencode`  | 174,551 | 21,111 |       7,076 | 2025-04-30 | 2026-06-15 | MIT        |
| Aider        | `Aider-AI/aider`      |  46,218 |  4,583 |       1,619 | 2023-05-09 | 2026-05-22 | Apache-2.0 |
| Cline        | `cline/cline`         |  63,303 |  6,690 |       1,102 | 2024-07-06 | 2026-06-15 | Apache-2.0 |
| Kilo Code    | `Kilo-Org/kilocode`   |  20,092 |  2,652 |         876 | 2025-03-10 | 2026-06-15 | MIT        |
| Cline Kanban | `cline/kanban`        |   1,038 |    243 |         229 | 2026-03-09 | 2026-06-10 | Apache-2.0 |
| Vibe Kanban  | `BloopAI/vibe-kanban` |  27,007 |  2,854 |         532 | 2025-06-14 | 2026-04-24 | Apache-2.0 |

注意：

- Stars 对新项目容易失真，但能反映短期声量。
- Open issues 既可能代表活跃，也可能代表维护压力。
- 闭源 IDE 的“强”更多体现在产品集成、商业化、默认工作流和团队采用，而不是开源指标。
- BYOK 只作为前三类 Agent 工具内部的账号、成本、数据边界和模型选择权维度观察；Kanban 编排层不把 BYOK 当作自身能力比较。

## 3. 方向一：AI IDE / VS Code Forks

这一类的核心不是“插件”，而是“编辑器即 Agent 操作系统”。Cursor 和 Devin Desktop 都在弱化传统插件思路，把模型路由、代码索引、Agent、review、团队管理和云端执行合成一个产品体验。

| 对比项            | Cursor                                                                                                                                                                                                                                                                      | Devin Desktop / Windsurf                                                                                                                                                                           |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 当前定位          | AI-first coding agent / IDE。官方文档入口覆盖 Agent、Rules、MCP、Skills、CLI、模型、Teams / Enterprise。                                                                                                                                                                    | “Agent Command Center”。官方首页明确说 Devin Desktop 是 Windsurf 新名称，主打从一个界面管理 local 和 cloud agents。                                                                                |
| 开发团队          | Anysphere。公开资料显示 Cursor 背后是 Anysphere 团队，核心背景长期围绕 AI-first editor 和 coding agent。                                                                                                                                                                    | Cognition / Devin 团队。Windsurf 被 Cognition 收购后成为 Devin Desktop，继承 Windsurf IDE 基础并强化多 Agent 管理。                                                                                |
| 历史路径          | 2023 年前后从 VS Code fork / AI editor 路线起势，逐步从 Copilot 替代品变成 AI IDE 标杆。                                                                                                                                                                                    | Codeium -> Windsurf -> Devin Desktop。2025-07 Cognition 宣布收购 Windsurf，2026 官方口径转为 Devin Desktop。                                                                                       |
| 当前社区声量      | 闭源产品，无可比 GitHub stars。行业声量极高，是 AI IDE 默认参照物之一，尤其在 AI-first editor、Agent mode、Cloud Agent、Bugbot / review 和团队用量管理上被频繁讨论。                                                                                                        | 闭源产品，无可比 GitHub stars。当前热点来自 Windsurf 并入 Devin 后的“本地 IDE + 云/本地多 Agent 指挥中心”；Cognition 收购公告也披露了 Windsurf 当时的 ARR、企业客户和日活规模。                    |
| 火爆原因          | 把 VS Code 熟悉体验、Tab 补全、Agent、代码索引、模型路由、团队管理和云端能力做成相对低摩擦的一体化产品。用户不需要先理解 provider、MCP、worktree、agent loop 才能开始。                                                                                                     | 从“AI IDE”升级为“agent fleet manager”：Spaces、Kanban view、多 Agent 管理、local/cloud agent、ACP 这些概念使它更像 Agent 控制台，而不仅是编辑器。                                                  |
| 当前主攻方向      | Agent、Cloud、CLI、Review / Bugbot、Rules、Skills、MCP、Marketplace、Teams / Enterprise 管理。重点是把个人 IDE 变成组织级 AI 开发平台。                                                                                                                                     | Agent Command Center、Spaces、Kanban、多 Agent 协作、local/cloud handoff、SWE 系列自研模型、ACP、企业 agent 管理。                                                                                 |
| BYOK / 订阅模式   | 支持 BYOK，但商业主入口是 Cursor 账户、订阅套餐和 usage pools。官方 Models & Pricing 有 Auto + Composer pool、API pool、Pro / Pro Plus / Ultra、Teams 等；Teams 的非 Auto agent 请求还涉及 Cursor Token Rate，BYOK 请求也可能经过 Cursor 后端做 prompt building / routing。 | 官方当前页面更强调 Free / Pro / Max / Teams / Enterprise 计划、额度和 SWE 系列模型。BYOK 不是当前 Devin Desktop 首页和模型页的核心卖点，主推是 Cognition / Devin 账户、内置模型和额度 / ACU 体系。 |
| 主推接入方式      | Cursor 账户 + 内置模型路由 / Auto / Composer / Premium routing。BYOK 更像高级用户或团队合规选项。                                                                                                                                                                           | Devin / Cognition 账户 + Devin Desktop 内置模型和 local/cloud agent。                                                                                                                              |
| 与现有 CLI 的关系 | Cursor 自身有 CLI / headless 能力，但更像 IDE 产品的延伸。可以和 Claude Code、Codex CLI 等并存，但不是专门的本地多 CLI 管理面板。                                                                                                                                           | Devin Desktop 明确往“所有 agent 的 command center”走，理论上更贴近管理多个 Agent 的需求；但具体可接入哪些第三方 CLI 要按当前 ACP / agent integration 文档核验。                                    |
| 风险与观察点      | 闭源、价格与额度模型变化快；BYOK 也不等于完全绕过平台层；长期是否从 VS Code fork 走向更自研的 IDE 架构值得跟踪。                                                                                                                                                            | Windsurf -> Devin Desktop 的迁移期带来产品定位变化；品牌、计费、插件、企业支持和第三方 agent 接入边界需要持续核验。                                                                                |
| 适合场景          | 想要最顺手的一体化 AI IDE，愿意接受产品订阅和平台抽象。                                                                                                                                                                                                                     | 想观察“IDE + Kanban + agent fleet + cloud/local agents”的下一代开发控制台。                                                                                                                        |

判断：

- Cursor 是 AI IDE 的默认强者，代表“AI-first editor 产品化”的成熟路线。
- Devin Desktop 是最值得观察的变量，代表“IDE 不再只是编辑器，而是多 Agent 指挥中心”。

## 4. 方向二：CLI / TUI 强者

这一类以终端为主入口。它们更适合被纳入 dotfiles、shell workflow、Git hooks、CI、本地脚本和个人自动化体系，也更符合“以后可能是 terminal 的天下”的判断。

| 对比项            | OpenCode                                                                                                                                                                             | Aider                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| 当前定位          | The open source coding agent。官方文档称它可作为 terminal-based interface、desktop app 或 IDE extension 使用，但核心声量来自 TUI / terminal agent。                                  | AI pair programming in your terminal。核心是终端里和 LLM 结对编程，直接编辑本地 Git repo。                                                 |
| 开发团队          | Anomaly / SST 相关团队，GitHub org 为 `anomalyco`。同一生态还有 `models.dev`、`opentui` 等基础组件。                                                                                 | Aider-AI 社区，项目早期为 `paul-gauthier/aider`，Paul Gauthier 是核心作者之一。                                                            |
| 历史路径          | 2025-04 创建，短时间内获得极高 GitHub 声量，定位为 Claude Code / proprietary coding agents 的开源替代。                                                                              | 2023-05 创建，是早期 terminal pair programming 的代表，长期围绕 repo map、Git 集成、多文件编辑、模型适配演进。                             |
| 当前社区声量      | GitHub 174,551 stars、21,111 forks；官方站点也强调高 stars、contributors 和使用规模。短期增长非常强。                                                                                | GitHub 46,218 stars、4,583 forks；官网长期强调 installs、token usage 和 leaderboard。整体稳定，口碑偏工程实用。                            |
| 火爆原因          | 开源、终端优先、多 provider、隐私优先、可企业内网接入，且 TUI 体验更接近 Claude Code 这类强 Agent 工具。官方还支持 GitHub Copilot 登录、ChatGPT Plus/Pro 登录、OpenCode Zen 等入口。 | 心智模型简单：在本地 repo 里用自然语言请求修改，Aider 处理上下文、编辑文件、自动提交。Git-first 的工作方式让撤销、审查和 diff 都很自然。   |
| 当前主攻方向      | TUI、CLI、IDE / desktop 辅助面、provider 扩展、multi-session、LSP、share links、企业集中配置、内部 AI gateway、OpenCode Zen。                                                        | 稳定的本地 pair programming、repo map、Git 工作流、多模型支持、leaderboard / benchmark、IDE watch 模式、提示词和编辑格式优化。             |
| BYOK / 订阅模式   | 强 BYOK / provider-first。官方 providers 文档支持配置 `apiKey`、custom provider、OpenAI-compatible endpoint；也有可选 OpenCode Zen，登录后以 credits / per request 使用推荐模型。    | 强 BYOK。Aider 文档列出 OpenAI、Anthropic、Gemini、OpenRouter、Ollama、Bedrock、Vertex、OpenAI-compatible API 等；自身不主推托管模型订阅。 |
| 主推接入方式      | 默认是连接任意 provider 或已有账号；可选 OpenCode Zen；企业可走内部 AI gateway。                                                                                                     | 自己配置 provider key 或本地模型；把 Aider 当作本地 Git repo 的结对编程 CLI。                                                              |
| 与现有 CLI 的关系 | 可以作为 `claudecode`、`codexcli`、`geminicli` 等之外的独立终端 Agent。也可被 Kanban 类工具作为底层 agent runtime 启动。                                                             | 更像“稳定的编辑型 pair programmer”，不强调 fleet 管理，但适合在终端中长期使用。                                                            |
| 优势              | 声量极高、开发活跃、terminal-native、provider 弹性大、企业隐私叙事强。                                                                                                               | 成熟、简单、Git 友好、可解释、学习成本低，对本地代码库多文件编辑非常实用。                                                                 |
| 风险与观察点      | 项目增长过快，issue 压力和产品复杂度也会快速上升；需要观察长期维护质量和治理。                                                                                                       | 相对不追逐“全自治 agent fleet”，如果未来核心战场转向多 Agent 编排，Aider 需要依赖外层工具补足。                                            |
| 适合场景          | 想要开源版 Claude Code / Codex CLI 风格的 TUI Agent，并希望保留模型和部署自由度。                                                                                                    | 想要一个稳定、可控、Git-first 的终端结对编程工具。                                                                                         |

判断：

- OpenCode 代表新一代 terminal-native agent 的高增长路线。
- Aider 代表成熟、克制、Git-first 的 terminal pair programming 路线。

这两者并不完全互斥：OpenCode 更像“自治 Agent / TUI runtime”，Aider 更像“可靠编辑伙伴”。

## 5. 方向三：CLI 兼顾 IDE 插件的开源 Agent Runtime

这一类的重点不是“VS Code 插件”，而是“一个 Agent Runtime 同时提供 IDE、CLI、SDK、云端、团队、多 Agent 等多个入口”。Cline 和 Kilo Code 都在往“开源 agentic engineering platform”演进。

| 对比项            | Cline                                                                                                                                                                                                                                     | Kilo Code                                                                                                                                                                                                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 当前定位          | The open source coding agent in your IDE and terminal。repo 描述为 autonomous coding agent as SDK, IDE extension, or CLI assistant。                                                                                                      | All-in-one agentic engineering platform。官方首页强调 VS Code、JetBrains、CLI、Cloud、Slack、500+ models、Kilo Gateway。                                                                                                                                                 |
| 开发团队          | Cline / Cline Bot Inc。Saoud Rizwan 是创始人；项目早期与 Claude Dev 路线相关，后来形成 Cline 品牌。                                                                                                                                       | Kilo-Org / Kilo.ai。公开资料中强调 open-source orchestration environment for AI coding agents；README 显示 Kilo CLI 是 OpenCode fork，并被集成进 Kilo 平台。                                                                                                             |
| 历史路径          | 2024-07 repo 创建。最早的心智来自 VS Code 内的 Claude Dev / human-in-the-loop agent，后来扩展到 CLI、SDK、JetBrains、Kanban、多 Agent teams、scheduled agents。                                                                           | 2025-03 repo 创建。起初在 Cline/Roo 风格开源 IDE agent 生态里获得用户，随后把 CLI、Gateway、Cloud、Agent Manager、Kilo Pass 等产品线整合进 Kilo.ai。                                                                                                                     |
| 当前社区声量      | GitHub 63,303 stars、6,690 forks。官方博客和站点公开强调多平台安装量、企业版、Cline credits、SDK、MCP、Kanban。                                                                                                                           | GitHub 20,092 stars、2,652 forks。README 强调 Discord、Reddit、VS Code Marketplace、CLI、Gateway、Pricing、Kilo Pass。                                                                                                                                                   |
| 火爆原因          | 开源、BYOK、支持大量 provider、本地/企业可控、IDE 内 human-in-the-loop 做得早；Plan / Act、MCP、工具审批、diff review 是它的核心记忆点。                                                                                                  | 把“模型自由 + 平台入口 + Gateway + Agent Manager + 云端”包装得更完整。对想同时用 IDE、CLI、Cloud、Slack 的用户更像一站式平台。                                                                                                                                           |
| 当前主攻方向      | IDE + CLI + SDK 共用内核；MCP、Plugins、Rules、Skills、multi-agent teams、scheduled agents、Kanban、enterprise governance。                                                                                                               | VS Code / JetBrains / CLI / Cloud / Slack 多入口；500+ models；Kilo Gateway 零 markup；Auto Model；Agent command center；KiloClaw / OpenClaw 这类托管 agent。                                                                                                            |
| BYOK / 订阅模式   | 强 BYOK，同时有 Cline Provider / credits。官方 authorization 文档给出两条路：Cline Provider 推荐，登录后无 API key；BYOK 用自己的 provider credentials。Pricing 口径是开源版无订阅或 seat fee，主要按 inference credits 或自带 key 付费。 | 同时支持 Kilo 账户 / credits / Kilo Pass / Kilo Gateway 和 BYOK。官方 setup 文档说默认安装后会提示登录 Kilo account，也支持“using another API provider”；文档明确支持自己的 API key 或 existing subscription，并列 OpenRouter、Anthropic、OpenAI、ChatGPT Plus/Pro 等。 |
| 主推接入方式      | 新手主推 Cline Provider；高级用户和企业主推 BYOK / 自有 endpoint / 自有云 provider。                                                                                                                                                      | 新手主推 Kilo account / Kilo Gateway；高级用户可以 BYOK、existing subscription 或本地模型。                                                                                                                                                                              |
| 与现有 CLI 的关系 | Cline 自身已是 CLI / SDK / IDE runtime，也能被 Cline Kanban 作为 agent runtime 管理。可与 Claude Code、Codex、Gemini、OpenCode 等同列成为 Kanban 底层执行器。                                                                             | Kilo CLI 是平台的一部分，且 README 明确说 Kilo CLI fork 自 OpenCode。它更倾向把不同入口统一到 Kilo 账户、Gateway 和 agent command center。                                                                                                                               |
| 优势              | 开源、成熟、provider 弹性、MCP 生态、human-in-the-loop 体验强，适合可控地尝试高权限 Agent。                                                                                                                                               | 产品包装完整，模型选择和平台化能力强，Gateway / Cloud / CLI / IDE 一体化程度高。                                                                                                                                                                                         |
| 风险与观察点      | 功能面扩张很快，CLI、SDK、Kanban、JetBrains、Enterprise 是否能保持同等质量需要观察。                                                                                                                                                      | 平台化越强，越要区分“开源 runtime”和“Kilo 托管服务”；MIT repo 与官网不同页面的 license / open-source 表述也需以当前 repo 为准核验。                                                                                                                                      |
| 适合场景          | 想要开源、可控、BYOK、MCP 丰富，同时有 IDE/CLI/SDK 多入口。                                                                                                                                                                               | 想要更产品化的开源 agentic platform，并愿意尝试 Kilo Gateway / Kilo account / cloud agent。                                                                                                                                                                              |

判断：

- Cline 是这条线的开源 Agent Runtime 标杆。
- Kilo Code 是更激进的平台化竞争者，尤其值得观察其 Gateway、CLI、Cloud 和 Agent Manager。

## 6. 方向四：Kanban 作为方法论，而不是单一工具

Kanban 在 AI Coding 语境里首先是一种工作方法，不是某一个项目的专有名词。

它把传统“一个聊天窗口里让 Agent 做事”的方式，改造成“多个任务卡片 + 多个隔离工作区 + 多个 Agent 并行 + 人类集中 review”的流程：

1. 把大任务拆成卡片。
2. 每张卡片关联一个 branch / worktree / workspace。
3. 每张卡片可以启动一个或多个 CLI / TUI / cloud agent。
4. 面板持续显示 agent 状态、最近消息、工具调用、是否等待权限。
5. 人类在卡片里看 diff、运行测试、留 inline comments。
6. 通过 commit / PR / merge / cleanup 收尾。

这套方法论会越来越常见，因为软件工程的瓶颈正在从“手写代码”转向“规划、授权、监控、审查、回滚和合并 Agent 产物”。

| 对比项           | Cline Kanban                                                                                                                                 | Vibe Kanban                                                                                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 当前定位         | Cline 组织下的独立 repo / npm 包 `kanban`。README 标注为 research preview，定位是本地 web app，并行运行 CLI agents、审查 diffs。             | BloopAI 的开源 Kanban 项目，npm 包 `vibe-kanban`。README 定位是让 Claude Code、Gemini CLI、Codex、Amp 等 coding agents 发挥 10x。                      |
| 团队 / 维护者    | Cline Bot Inc / Cline 生态。                                                                                                                 | Bloop AI Limited。2026-04 官方公告称 bloop 公司关闭，Vibe Kanban 项目继续开源并由社区维护。                                                            |
| 历史路径         | 2026-03 repo 创建，Cline 主项目 README 已把 Kanban 列为核心产品面之一。                                                                      | 2025-06 repo 创建。早期在多 Agent Kanban、diff comments、live preview、remote access 方面声量很高；2026-04 后转向 open source / community maintained。 |
| 当前社区声量     | GitHub 1,038 stars、243 forks。声量不大，但背靠 Cline 生态，适合作为 Cline 产品线里 Kanban 方法的参考实现。                                  | GitHub 27,007 stars、2,854 forks。声量显著更高，但公司已 sunset，维护可持续性需要观察。                                                                |
| 支持 agent / CLI | README 说会检测已安装 CLI agent。开发文档当前 hook mappings 覆盖 Claude、Codex、Gemini、OpenCode、Droid；schema 中还可见 Cline 等 agent id。 | README 明确列出 Claude Code、Codex、Gemini CLI、GitHub Copilot、Amp、Cursor、OpenCode、Droid、CCR、Qwen Code 等 10+ coding agents。                    |
| 工作区模型       | 每张 task card 获得独立 terminal 和 ephemeral worktree；自动处理 worktree，并 symlink gitignored files 以减少重复 install。                  | 使用 kanban issues 规划，创建 workspace 给 agent 执行；每个 workspace 有 branch、terminal、dev server。                                                |
| 状态监控         | 通过 runtime hooks 显示最新 message / tool call，状态在 `in_progress` 与 `review` 等之间切换。                                               | 在 board / workspace 层显示任务状态，并支持 preview、devtools、device emulation 等面向应用开发的审查能力。                                             |
| Review / Ship    | 卡片内看 TUI 和 diff；可 checkpoint、点击行留评论并发回 agent；支持 Commit / Open PR / auto-commit / auto-PR / git interface。               | 支持 review diffs、inline comments、send feedback to agent、built-in browser preview、Create PR and merge。                                            |
| 主推接入方式     | `npx kanban` 或 `npm i -g kanban`，在 git repo 根目录运行，让它检测本机 CLI agents。Node 要求当前 npm 包为 `>=22`。                          | `npx vibe-kanban`，前提是先登录或配置好喜欢的 coding agent。Node 要求当前 npm 包为 `>=20.19.0`。                                                       |
| 火爆原因         | 与 Cline 的 CLI、SDK、IDE、Kanban 产品线自然连起来；强调 worktree、hooks、diff review、auto-commit/PR、dependency chains。                   | 更早把“agent planning + workspace + diff comments + live preview + 多 agent switching”做成完整产品体验，GitHub 声量很高。                              |
| 风险与观察点     | Research preview，依赖 CLI agent 的实验性 hooks 和权限绕过；适合学习和小心试用，不宜无审查地接入高风险 repo。                                | 公司已关闭，项目转社区维护；remote / cloud 功能会变化，适合本地使用和方法论学习，但生产依赖要谨慎。                                                    |
| 适合场景         | 已经关注 Cline / OpenCode / Codex / Gemini 等本地 CLI agent，想用一个本地任务板统一启动、观察、审查。                                        | 想体验成熟的 multi-agent Kanban workflow，尤其是多 agent、diff comments、preview 和 PR 工作流。                                                        |

判断：

- Kanban 不是 Cline 独有，也不是 Vibe 独有，而是“Agent 工作管理层”。
- Cline Kanban 更像 Cline 生态内的轻量研究预览。
- Vibe Kanban 声量更大、体验完整，但公司 sunset 后要把它视作社区维护项目。
- Devin Desktop 也在把 Kanban view、Spaces、多 Agent 管理做进 IDE，这说明 Kanban 方法正在变成产品主流能力，而不是独立小工具。

## 7. 四条线之间的关系

这四条线正在互相收敛：

- AI IDE 正在吸收 CLI、cloud agent、review、Kanban 和团队管理。
- CLI/TUI 正在补 IDE panel、desktop app、share links、enterprise config。
- 开源 Agent Runtime 正在从单插件变成 SDK、CLI、cloud、Kanban、多 Agent teams。
- Kanban 正在从独立工具变成 IDE / Runtime 的基础工作流。

因此选型时不要只问“哪个工具最强”，而要问：

1. 我的主入口是 IDE 还是 terminal？
2. 如果选择具体 Agent 工具，我是否需要 BYOK、local model、internal AI gateway？
3. 我是否需要同时跑多个 agent？
4. 我希望人类在哪个环节介入：prompt 前、工具调用前、diff review、commit / PR 前？
5. 我能接受多少平台锁定、用量不确定性和闭源黑盒？

## 8. 当前跟踪建议

### 8.1 最小跟踪组合

如果只想每条线跟两个对象：

| 方向               | 跟踪对象                  | 跟踪重点                                                                   |
| ------------------ | ------------------------- | -------------------------------------------------------------------------- |
| AI IDE             | Cursor、Devin Desktop     | 订阅/额度/BYOK 边界、Agent/Cloud/Review、是否成为多 Agent command center   |
| CLI/TUI            | OpenCode、Aider           | terminal UX、provider/BYOK、Git 工作流、企业内网可用性                     |
| Open Agent Runtime | Cline、Kilo Code          | CLI/IDE/SDK 共用内核、BYOK/Gateway、MCP/Plugins、Enterprise、Kanban        |
| Kanban 方法论      | Cline Kanban、Vibe Kanban | worktree 隔离、agent adapters、hooks、diff review、PR/commit、项目维护状态 |

### 8.2 后续观察点

- Cursor 的 BYOK、Auto、Composer、API pool、Cursor Token Rate 是否继续调整。
- Devin Desktop 的 ACP、Spaces、Kanban view 能否稳定接入非 Devin 的第三方 agent。
- OpenCode 的高增长能否转化为稳定治理和长期维护。
- Aider 是否继续保持“简单、Git-first”的优势，还是需要外层 Kanban / multi-agent 工具配合。
- Cline 是否能把 IDE、CLI、SDK、Kanban、Enterprise 做成一致的 runtime。
- Kilo Code 的 open-source runtime 与 Kilo Gateway / Kilo Pass / Cloud 的边界是否清晰。
- Vibe Kanban sunset 后社区维护能否持续。
- Kanban 层对 `claudecode`、`codexcli`、`qwencli`、`geminicli`、`copilotcli` 的接入是否标准化。

## 9. 主要来源

- Cursor official: https://cursor.com, https://cursor.com/docs, https://cursor.com/docs/models-and-pricing
- Devin Desktop official: https://devin.ai/desktop/, https://docs.devin.ai/desktop/getting-started, https://docs.devin.ai/desktop/models, https://devin.ai/pricing
- Cognition acquisition of Windsurf: https://cognition.ai/blog/windsurf
- OpenCode official: https://opencode.ai/, https://opencode.ai/docs/, https://opencode.ai/docs/providers/, https://opencode.ai/docs/zen/, https://github.com/anomalyco/opencode
- Aider official: https://aider.chat/, https://aider.chat/docs/llms.html, https://github.com/Aider-AI/aider
- Cline official: https://cline.bot/, https://docs.cline.bot/getting-started/authorizing-with-cline, https://cline.bot/pricing, https://github.com/cline/cline
- Kilo Code official: https://kilo.ai/, https://kilo.ai/docs/getting-started, https://kilo.ai/docs/getting-started/setup-authentication, https://github.com/Kilo-Org/kilocode
- Cline Kanban: https://github.com/cline/kanban, https://www.npmjs.com/package/kanban
- Vibe Kanban: https://github.com/BloopAI/vibe-kanban, https://vibekanban.com/docs, https://www.vibekanban.com/blog/shutdown
- GitHub API snapshots: `anomalyco/opencode`、`Aider-AI/aider`、`cline/cline`、`Kilo-Org/kilocode`、`cline/kanban`、`BloopAI/vibe-kanban`
