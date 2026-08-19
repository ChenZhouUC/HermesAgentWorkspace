# Hermes Agent — 本地配置仓库

> **这个仓库跟踪的是 `~/.hermes/` 下的个人配置文件，不包含官方源码（`hermes-agent/`）和密钥（`.env`）。**

---

## 目录

- [概述](#概述)
- [目录结构说明](#目录结构说明)
- [安装](#安装)
  - [前置条件](#前置条件)
  - [全新安装](#全新安装)
  - [可选依赖（Optional Extras）](#可选依赖optional-extras)
  - [从 OpenClaw 迁移](#从-openclaw-迁移)
  - [整机迁移：旧机停用，新机接管](#整机迁移旧机停用新机接管)
- [配置](#配置)
  - [.env 密钥文件](#env-密钥文件)
  - [config.yaml 主配置](#configyaml-主配置)
  - [Thinking / Reasoning 配置](#thinking--reasoning-配置)
  - [流式输出](#流式输出)
  - [Vertex Provider](#vertex-provider)
  - [飞书集成](#飞书集成)
- [Gateway 服务](#gateway-服务)
- [用户插件 (Plugins)](#用户插件-plugins)
- [Logi Options+ 看门狗 (可选)](#logi-options-看门狗-可选)
- [Shell 集成](#shell-集成)
- [更新](#更新)
- [本地补丁记录](#本地补丁记录)
- [卸载](#卸载)
- [基础使用](#基础使用)
  - [对话（Chat）](#对话chat)
  - [会话管理](#会话管理)
  - [模型选择](#模型选择)
  - [Skills 技能包](#skills-技能包)
  - [Context References（@ 语法）](#context-references-语法)
  - [Cron 定时任务](#cron-定时任务)
- [记忆系统与个性化](#记忆系统与个性化)
  - [两个记忆文件](#两个记忆文件)
  - [记忆的工作原理](#记忆的工作原理)
  - [Agent 如何主动维护记忆](#agent-如何主动维护记忆)
  - [你能做什么：让它越用越懂你](#你能做什么让它越用越懂你)
  - [容量管理](#容量管理)
  - [Session Search：无限历史回溯](#session-search无限历史回溯)
  - [知识库存储层级](#知识库存储层级)
  - [LLM Wiki：本地长期知识库（推荐）](#llm-wiki本地长期知识库推荐)
  - [SOUL.md：人格与语气](#soulmd人格与语气)
  - [外部记忆 Provider（进阶）](#外部记忆-provider进阶)
- [Web Search 工具](#web-search-工具)
- [Web Dashboard](#web-dashboard)
- [维护与排错](#维护与排错)

---

## 概述

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是 NousResearch 开发的本地 AI 助手，支持工具调用、飞书/Telegram/Discord 等 IM 平台接入，以及 Cron 定时任务。

本仓库存储的内容：

| 文件/目录                    | 说明                                                     |
| ---------------------------- | -------------------------------------------------------- |
| `config.yaml`                | 主配置：模型、工具集、gateway 超时、显示风格等           |
| `.env.example`               | 密钥配置模板（实际 `.env` 不入库）                       |
| `credentials/`               | 本地 service-account JSON 等凭据（不入库）               |
| `completions/_hermes`        | zsh 补全脚本（#compdef 格式，通过 fpath 加载）           |
| `memories/MEMORY.md`         | Agent 的结构化记忆（短期），自动注入每次会话             |
| `memories/USER.md`           | 用户画像（偏好、时区、语言等）                           |
| `my-skills/`                 | 自定义 Skills（随主仓库入库）                            |
| `plugins/`                   | 用户插件（每个子目录 = 一个插件，随主仓库入库）          |
| `cron/jobs.json`             | Cron live store（定义与运行状态混合；本地保留、不入库）  |
| `patches/local-patches.diff` | hermes-agent 本地补丁 diff（更新时自动重新应用）         |
| `patches/PATCHES.md`         | 本地补丁详细记录（问题 / 根因 / 修复方案）               |
| `hermes-update.sh`           | 一键更新脚本（入库，随版本变更同步维护）                 |
| `scripts/`                   | 日报/组织同步、代理注入、Logi watchdog、Wiki lint 等脚本 |
| `SOUL.md`                    | Agent 人格与语气配置                                     |
| `README.md`                  | 本文档                                                   |

**不跟踪的内容**：官方源码（`hermes-agent/`）、密钥（`.env`）、数据库（`state.db`）、日志、会话、Hub Skills（`skills/`，更新时自动镜像上游）。

---

## 目录结构说明

```
~/.hermes/
├── hermes-agent/          # 官方源码 clone（独立 git repo，.gitignore 排除）
├── .env                   # 密钥（.gitignore 排除）
├── .env.example           # 密钥模板（入库）
├── credentials/           # service-account JSON 等本地凭据（.gitignore 排除）
├── config.yaml            # 主配置（入库）
├── SOUL.md                # Agent 人格（入库）
├── scripts/               # 日报/组织同步、代理注入、Logi watchdog、Wiki lint 等脚本（入库）
├── completions/
│   └── _hermes            # zsh 补全脚本（#compdef 格式，fpath 加载）
├── memories/
│   ├── MEMORY.md          # 结构化记忆（入库）
│   └── USER.md            # 用户画像（入库）
├── skills/                # Hub 官方 Skills（.gitignore 排除，更新时由 rsync 镜像上游）
├── my-skills/             # 自定义 Skills（随主仓库入库）
├── plugins/               # 用户插件（入库；每个子目录 = 一个插件，走官方 register(ctx) API）
│   └── sandbox/           # 飞书会话级工具沙盒（主 DM 满血、群聊额外只读知识库/文档）
├── patches/               # hermes-agent 本地补丁（入库，供 hermes-update.sh 使用）
│   ├── local-patches.diff # 所有本地 patch 的 unified diff，更新时自动重新应用
│   └── PATCHES.md         # 补丁详细记录（问题 / 根因 / 修复方案）
├── hermes-update.sh       # 一键更新脚本（入库）
├── cron/
│   └── jobs.json          # Cron live store（不入库；用 hermes backup/import 迁移）
├── logs/                  # 日志（.gitignore 排除）
├── sessions/              # 会话历史（.gitignore 排除）
└── state.db               # 内部状态数据库（.gitignore 排除）
```

---

## 安装

### 前置条件

| 依赖   | 版本要求                                                                                | 安装方式                                           |
| ------ | --------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Python | 以 `hermes-agent/pyproject.toml` 的 `requires-python` 为准（当前上游为 `>=3.11,<3.14`） | `pyenv` 或 Homebrew Python                         |
| uv     | 最新                                                                                    | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| git    | 任意                                                                                    | macOS 自带                                         |

### 全新安装

```bash
# 1. Clone 官方源码到 hermes-agent 子目录
mkdir -p ~/.hermes
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent

# 2. 查看上游 Python 约束，并选择一个满足约束的本机 Python
rg '^requires-python' pyproject.toml
PYTHON_VERSION=3.12.7  # 示例：选择任意满足 requires-python 的本机版本
uv venv --python "$PYTHON_VERSION" venv
source venv/bin/activate

# 3. 安装本配置需要的依赖（当前上游 [all] 不包含飞书）
uv pip install -e ".[all,feishu]"

# 4. 创建 symlink（确保 ~/.local/bin 在 PATH 中）
mkdir -p ~/.local/bin
ln -sf ~/.hermes/hermes-agent/venv/bin/hermes ~/.local/bin/hermes

# 5. 验证
hermes --version
```

**激活虚拟环境（日常调试用）：**

```bash
source ~/.hermes/hermes-agent/venv/bin/activate
```

> **注意**：日常使用通过 symlink `~/.local/bin/hermes` 调用，无需每次激活 venv。

### 可选依赖（Optional Extras）

`hermes-agent` 的 `pyproject.toml` 定义了大量 optional extras，按需安装可以启用对应功能。**基础安装（无 extras）已包含核心对话、工具调用和 Skills 能力**，以下模块只在需要时才需安装。

#### 安装方式

```bash
# 激活 venv 后，用 uv pip install 按需追加
cd ~/.hermes/hermes-agent && source venv/bin/activate

# 安装单个 extra
uv pip install -e ".[feishu]"

# 同时安装多个 extras（逗号分隔）
uv pip install -e ".[feishu,cron,voice,mcp]"

# 安装上游 broad install 组合（不含多数 lazy backend，如 feishu/voice/bedrock）
uv pip install -e ".[all]"
```

> **注意**：`uv pip install -e ".[xxx]"` 会增量安装，不影响已有依赖。若不激活 `venv`，可改用 `uv pip install --python venv/bin/python -e ".[xxx]"`。当前上游把 Feishu、voice、bedrock、modal/daytona 等 opt-in 后端移到 `tools/lazy_deps.py` 首次使用时安装；本配置因 gateway 常驻飞书，仍显式安装 `feishu` extra。

#### Extras 一览

| Extra             | 功能                                 | 主要依赖包                                                                                    | 说明                                                                                 |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **feishu**        | 飞书 IM 集成（WebSocket 长连接）     | `lark-oapi`, `qrcode`, `python-socks`                                                         | **当前已安装** ✅ 。代理网络环境需 `python-socks`（`PATCH-FEISHU-SOCKS-DEPENDENCY`） |
| **cron**          | Cron 定时任务调度                    | `croniter`                                                                                    | Gateway 使用，不装则 `hermes cron` 不可用                                            |
| **messaging**     | Telegram + Discord + Slack + 飞书 QR | `python-telegram-bot`, `discord.py`, `aiohttp`, `slack-bolt`, `slack-sdk`, `qrcode`           | 全平台 IM 一把梭；若只用飞书可单独装 `feishu`                                        |
| **slack**         | Slack 集成                           | `slack-bolt`, `slack-sdk`                                                                     | `messaging` 的子集                                                                   |
| **matrix**        | Matrix 协议集成                      | `mautrix[encryption]`, `Markdown`, `aiosqlite`, `asyncpg`                                     | ⚠️ macOS 上 `python-olm` 构建可能失败                                                |
| **voice**         | 本地语音输入（STT）                  | `faster-whisper`, `sounddevice`, `numpy`                                                      | 需要麦克风权限；包含 `ctranslate2` 等重型依赖                                        |
| **tts-premium**   | 高级语音合成（ElevenLabs）           | `elevenlabs`                                                                                  | 需 ElevenLabs API key；基础 TTS（Edge TTS）已在 base 中                              |
| **mcp**           | Model Context Protocol 支持          | `mcp`                                                                                         | 外部工具/数据源接入标准                                                              |
| **acp**           | Agent Client Protocol                | `agent-client-protocol`                                                                       | Agent 间委托通信协议                                                                 |
| **cli**           | 交互式 TUI 选择器                    | `simple-term-menu`                                                                            | `hermes model` 等 TUI 选择器依赖                                                     |
| **pty**           | 伪终端支持                           | `ptyprocess` (macOS/Linux) / `pywinpty` (Windows)                                             | 终端工具增强                                                                         |
| **honcho**        | Honcho 外部记忆 Provider             | `honcho-ai`                                                                                   | 需配合 `hermes memory setup` 使用                                                    |
| **modal**         | Modal 云端执行                       | `modal`                                                                                       | 远程沙箱执行                                                                         |
| **daytona**       | Daytona 开发环境                     | `daytona`                                                                                     | 远程开发环境集成                                                                     |
| **mistral**       | Mistral AI Provider                  | `mistralai`                                                                                   | 使用 Mistral 模型时需要                                                              |
| **bedrock**       | AWS Bedrock Provider                 | `boto3`                                                                                       | 使用 AWS 托管模型时需要                                                              |
| **dingtalk**      | 钉钉 IM 集成                         | `dingtalk-stream`, `alibabacloud-dingtalk`, `qrcode`                                          | 钉钉企业应用                                                                         |
| **web**           | Web Dashboard + REST API             | `fastapi`, `uvicorn[standard]`                                                                | **当前已安装** ✅ 。`hermes dashboard` 命令依赖                                      |
| **homeassistant** | Home Assistant 集成                  | `aiohttp`                                                                                     | 智能家居控制                                                                         |
| **sms**           | SMS 消息支持                         | `aiohttp`                                                                                     | 短信通知                                                                             |
| **dev**           | 开发/测试工具                        | `debugpy`, `pytest`, `pytest-asyncio`, `pytest-xdist`, `mcp`                                  | 贡献代码或调试时使用                                                                 |
| **termux**        | Android Termux 平台                  | Telegram + cron + cli + pty + mcp + honcho + acp                                              | 专为 Termux 环境裁剪，排除不兼容的 voice                                             |
| **rl**            | 强化学习实验                         | `atroposlib`, `tinker`, `fastapi`, `wandb`                                                    | 研究用途                                                                             |
| **yc-bench**      | YC Bench 评测                        | `yc-bench`                                                                                    | 需要 Python ≥ 3.12                                                                   |
| **all**           | 上游 broad install 组合              | `cron`, `cli`, `dev`, `pty`, `mcp`, `homeassistant`, `sms`, `acp`, `google`, `web`, `youtube` | 当前不包含 Feishu、Telegram/Discord/Slack、voice、bedrock 等 lazy backend            |

#### 当前环境已安装的 Extras

```
.[all,feishu]    ✅  ← 本次迁移恢复使用的安装组合
feishu           ✅  ← 飞书 WebSocket + SOCKS 代理（`PATCH-FEISHU-SOCKS-DEPENDENCY` 覆盖 extra + lazy deps）
web              ✅  ← Dashboard 后端（fastapi + uvicorn，来自 [all]）
cron/cli/mcp/pty ✅  ← 常用 CLI / Gateway 能力（来自 [all]）
dev/google/youtube/acp/homeassistant/sms ✅  ← 来自 [all]
```

未主动安装的 opt-in backend（如 Telegram/Discord/Slack、voice、bedrock、modal/daytona、tts-premium）会按上游 lazy install 机制在首次使用时补装；也可以按上方安装方式提前安装。

#### 推荐安装组合

```bash
# 飞书用户日常推荐（已安装 feishu，追加常用模块）
uv pip install -e ".[feishu,cron,cli,mcp,pty]"

# 全平台 IM + 定时任务 + 语音
uv pip install -e ".[messaging,cron,voice,mcp,cli,pty]"

# 开发/调试
uv pip install -e ".[dev,web]"
```

### 从 OpenClaw 迁移

Hermes 内置迁移工具，可自动导入 OpenClaw 的模型配置：

```bash
hermes claw migrate
```

> **已知 Bug（截至 v0.9.0）**：`hermes claw migrate` 对 `.env` 的写入有三处问题，迁移完成后**必须**手动校对：
>
> 1. `GOOGLE_API_KEY=${GEMINI_API_KEY}` — dotenv 不展开变量，需替换为实际 key 值
> 2. `BAILIAN_API_KEY=${BAILIAN_API_KEY}` — 自循环引用，需替换为实际 key 值（当前配置已不使用 Bailian/Alibaba provider；该变量仅在迁移旧配置时需要辨认和清理）

**飞书迁移**（迁移工具不支持，需手动配置）：

```bash
# 将以下内容追加到 ~/.hermes/.env（从 ~/.openclaw/.env 复制实际值）
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=your_secret
FEISHU_DOMAIN=feishu
FEISHU_CONNECTION_MODE=websocket
```

### 整机迁移：旧机停用，新机接管

适用于把一台机器上已经正常运行的 Hermes 环境整体迁到另一台机器：先让旧机停止所有 Hermes 及相关后台进程，再把 `~/.hermes/` 整目录复制到新机，最后在新机重新安装/启动服务。

> ⚠️ `~/.hermes/` 里包含 `.env`、`credentials/`、会话、数据库、缓存等敏感或私有数据。只复制到你信任的新机器，并使用可信传输方式。

#### 1. 在旧机停止 Hermes 相关服务

先停止并卸载 gateway，避免飞书 WebSocket、cron 或 gateway 在两台机器上同时运行：

```bash
hermes gateway stop || true
hermes gateway uninstall || true
```

确认旧机已经没有 Hermes 相关进程：

```bash
launchctl list | grep -Ei 'hermes|feishu|gateway' || true
ps -axo pid=,ppid=,stat=,command= | grep -Ei 'hermes|feishu|gateway' | grep -v grep || true
```

如果仍看到残留进程，先记录 PID，再按 PID 停止：

```bash
kill -TERM <PID>
```

停止后可清理运行期 PID/lock 文件，避免把旧机的进程状态带到新机：

```bash
rm -f ~/.hermes/gateway.pid ~/.hermes/gateway.lock
```

#### 2. 复制 `~/.hermes/` 到新机

推荐用 `rsync` 保留目录结构和权限：

```bash
rsync -aH --delete ~/.hermes/ new-host:~/.hermes/
```

也可以用外置磁盘、局域网共享或其他可信方式复制；关键是目标路径保持为新机的 `~/.hermes/`。

#### 3. 在新机恢复可执行环境

先安装基础依赖（见“前置条件”），再重建虚拟环境。即使复制过来的 `venv/` 看起来存在，也建议在新机重建，避免 Python 版本、CPU 架构或动态库路径不一致：

```bash
cd ~/.hermes/hermes-agent
rm -rf venv
rg '^requires-python' pyproject.toml
PYTHON_VERSION=3.12.7  # 示例：选择任意满足 requires-python 的本机版本
uv venv --python "$PYTHON_VERSION" venv
source venv/bin/activate
uv pip install -e ".[all,feishu]"

mkdir -p ~/.local/bin
ln -sf ~/.hermes/hermes-agent/venv/bin/hermes ~/.local/bin/hermes
```

`PYTHON_VERSION` 不写死，按当前 `pyproject.toml` 的约束和本机已安装版本选择即可。2026-05-20 这次新机恢复使用的是本机 `pyenv` 的 `3.12.7`，满足当时上游 `requires-python = ">=3.11"`。

如果使用官方 Vertex Provider，先确认 `.env` 里有服务账号 JSON 路径，且 `config.yaml` 的主模型、fallback 或 auxiliary 路由中存在 `provider: vertex`：

```bash
rg '^(GOOGLE_APPLICATION_CREDENTIALS|VERTEX_CREDENTIALS_PATH)=' ~/.hermes/.env
sed -n '1,20p' ~/.hermes/config.yaml
```

最后安装并启动新机的后台服务：

```bash
hermes doctor
hermes gateway install --force
hermes gateway start

hermes gateway status
launchctl list | grep -Ei 'hermes'
```

Vertex OAuth token 由 Hermes 进程内 mint/refresh，不需要任何额外的 LaunchAgent。

迁移完成后，旧机应保持 gateway 卸载状态；如果只是临时切换机器，回切前也按同样流程先停掉当前机器，再启动另一台。

---

## 配置

### .env 密钥文件

**位置**：`~/.hermes/.env`（不入库，参考 `.env.example`）

```bash
# 从模板创建
cp ~/.hermes/.env.example ~/.hermes/.env
# 用文本编辑器填入实际密钥
open -a TextEdit ~/.hermes/.env
```

当前使用的 provider 及其环境变量：

| Provider                   | 环境变量                                                                 | 说明                                                                      |
| -------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| Azure Foundry（主模型）    | `AZURE_FOUNDRY_API_KEY` / `AZURE_FOUNDRY_BASE_URL`                       | 从 `codex-az` 使用的 `AZOPENAI_*` 映射，走 Responses wire                 |
| Bedrock Claude Opus 5      | `CLAUDE_AM_OPUS_ARN` / `AWS_REGION`                                      | 从 `claude-am` 的 application-inference-profile ARN 与 region 映射        |
| Vertex Gemini（末级/压缩） | `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT_ID` / `VERTEX_REGION` | 标准 `vertex` provider 用 service account 自动 mint + refresh OAuth token |
| 飞书                       | `FEISHU_APP_ID` / `FEISHU_APP_SECRET`                                    | 飞书开放平台获取                                                          |
| 飞书推送频道               | `FEISHU_HOME_CHANNEL`                                                    | cron / 通知默认投递的群或会话 ID                                          |
| Gateway 访问控制           | `FEISHU_ALLOWED_USERS` / `GATEWAY_ALLOW_ALL_USERS=false`                 | 默认使用飞书白名单；仅明确开放时才设为 `true`                             |

**当前主模型的加载机制：**

当前主模型是 `azure-foundry/gpt-5.5`。`~/.secrets` 仅作为人工取值来源：需要把 `AZOPENAI_*` 显式复制/映射到 Hermes 自己 `.env` 的 `AZURE_FOUNDRY_*`，Hermes 不继承 shell 中的同名或其它 provider 变量。

Fallback[0] 使用 `claude-am` 同源的 AWS Bedrock application inference profile：`.env` 只保存 `CLAUDE_AM_OPUS_ARN` 与 `AWS_REGION`，AWS 签名继续走标准 SDK credential chain。

Fallback[1] 与上下文压缩共同使用标准 Vertex：`GOOGLE_APPLICATION_CREDENTIALS` 必须在 Hermes `.env` 中填写展开后的 service-account JSON 绝对路径，`VERTEX_PROJECT_ID` / `VERTEX_REGION` 分别映射 project 与 location。Hermes 在进程内 mint/refresh OAuth token；不再读取用户 shell 中的 Gemini/DashScope 等旁路凭据。

### config.yaml 主配置

**位置**：`~/.hermes/config.yaml`

关键配置节说明：

```yaml
# 主模型
model:
  provider: azure-foundry
  default: gpt-5.5
  context_length: 1048576

# 备用链路（主模型报错时按顺序切换）
fallback_providers:
  - provider: bedrock
    model: ${CLAUDE_AM_OPUS_ARN}
  - provider: vertex
    model: google/gemini-3.5-flash

# Flash 作为末级恢复模型时同样使用 high reasoning
agent:
  reasoning_overrides:
    gemini-3.5-flash: high

# 压缩辅助模型（与主/备模型对齐到 1M 上下文，可统一使用同一个 threshold）
auxiliary:
  compression:
    provider: vertex
    model: google/gemini-3.5-flash
    extra_body:
      google:
        thinking_config:
          include_thoughts: false
          thinking_level: high

# 上下文压缩门槛（主/fallback/压缩三方都是 1M context 时可放宽到 0.7）
compression:
  enabled: true
  threshold: 0.7
  threshold_tokens: 700000 # 三档统一约 700k 触发，保留约 300k 余量
  target_ratio: 0.2
  tail_mode: legacy # 显式保持既有 verbatim-tail 语义；上游另提供 lean
  codex_gpt55_autoraise: false

# /model 只展示/允许切换上述主模型与 fallback；切换仅作用于当前 session。
# 如需新增模型，先手工修改 model / fallback_providers。
model_catalog:
  configured_only: true

# 不继承 shell / ~/.secrets 注入的已知 Hermes provider/tool 变量。
# ~/.hermes/.env 和显式配置的 Hermes secret sources 仍然有效。
secrets:
  ignore_ambient_credentials: true
```

> **三档统一策略**：GPT-5.5 / Claude Opus 5 / Gemini 3.5 Flash 的 context metadata 分别约 1.05M / 1M / 1.048576M。统一 `threshold=0.7` + `threshold_tokens=700000`，并关闭 GPT-5.5 的 85% autoraise，使 provider 切换后的 compressor 始终在约 700k 触发，给 system prompt、29 个工具 schema、输出预算与估算误差留下约 300k 余量。

> **主动切换与 fallback**：严格模式下 `/model` 只能在上述三条 route 间做 session-scoped 切换，`--global` 和链外模型会被拒绝。切到 Bedrock 时会跳过 fallback 链中重复的 Bedrock、保留 Vertex；切到 Vertex 时先回退 Bedrock、再跳过重复 Vertex。`auxiliary.compression` 始终优先 Vertex，不因主模型切换而改写；只有 Vertex 摘要失败时，备用摘要模型才随“当前主模型”变化。

> **多模态 native-first + sidecar**：三条 route 的图片能力均已验证并走原生输入：Azure GPT-5.5、Bedrock Claude Opus 5、Vertex Gemini 3.5 Flash 都直接接收像素。GPT-5.5 与 Opus 5 官方不支持视频/音频输入，不能伪装为 native；此时仅把当前音频/视频及最多 4,000 字 caption/引用交给 fallback 链中的 Gemini Flash sidecar，主会话模型与历史不切换。普通语音优先本地 STT，全部失败才旁路；PDF/纯文本优先本地可信抽取，抽取为空或 PDF 覆盖率探测发现扫描/图片页缺口时才旁路，DOCX/XLSX/PPTX 等未列入 Flash 原生 MIME 的格式不外发。成功的 native、抽取和 sidecar 结果不再向模型暴露宿主 cache 绝对路径；全部读取链失败时注入明确的 `FAILED` 状态并要求如实告知用户，不允许退化为“自行打开路径”。

#### Session override、fallback 与 compaction 生命周期

这里的“主模型”有两层含义：`config.yaml` 中的 `model` 是**新会话默认主模型**；在某个会话里执行 `/model` 后，该会话会有一个优先级更高的 **session override**。二者不会互相改写。

| 场景                                   | 主模型从哪里取            | fallback                                     | compaction                         | session / override 结果                                                |
| -------------------------------------- | ------------------------- | -------------------------------------------- | ---------------------------------- | ---------------------------------------------------------------------- |
| 新建会话                               | `config.model`            | 按 `fallback_providers` 顺序                 | 固定读取 `auxiliary.compression`   | 无 override                                                            |
| 当前会话执行 `/model`                  | 当前会话 override         | 仍读取配置链，并跳过与当前主模型重复的 route | 仍固定读取 `auxiliary.compression` | 只影响当前 `session_key`                                               |
| Gateway restart                        | 持久化的当前会话 override | 不变                                         | 不变                               | restart 不是新会话；override 会按 session 恢复，密钥重新从 `.env` 解析 |
| 正常 compaction                        | 当前会话 override         | 不变                                         | Vertex Gemini Flash                | 默认原地压缩，`session_id` 与 override 都不变                          |
| `/new`、`/reset`、`/resume` 或会话过期 | 回到 `config.model`       | 配置链                                       | 配置的压缩模型                     | 形成逻辑会话边界并清除旧 override                                      |

具体规则：

- `/model` 不修改 `config.yaml`。严格模式还禁用了 `--global`，所以只有手工编辑 `model` / `fallback_providers` 才会改变以后新建会话可用的模型集合和默认值。
- override 按 `session_key` 隔离。主私聊、不同群、不同 thread 互不影响；当前 `group_sessions_per_user: false`，普通群内所有成员共享该群的一个 session，thread 则拥有独立且默认由 thread 内成员共享的 session。主私聊切模型不会改变已有群会话的模型。
- fallback 链不会因为主动切换主模型而失效。默认 Azure 主模型按 `Bedrock → Vertex` 容灾；主动切到 Bedrock 后跳过重复 Bedrock、保留 Vertex；主动切到 Vertex 后保留 Bedrock 并跳过重复 Vertex。具体型号始终动态来自配置，不在补丁中写死。
- `auxiliary.compression` 是独立路由，不跟随 `/model` 改写。只有配置的压缩模型调用失败时，压缩器才可能使用当前会话主模型作恢复；这不会把会话永久切到压缩模型。
- 当前显式使用 `compression.tail_mode: legacy`：摘要后保留既有比例的最近原文 tail。上游新增的 `lean` 会把原文 tail 压到约 2.5%（10k–25k tokens），并依赖 digest、anchor index 与 `session_search` 恢复；切换它属于上下文策略变更，不能只因升级自动启用。
- 当前默认 `compression.in_place=true`。压缩会把旧 active 消息软归档为 `active=0, compacted=1`，再把摘要后的消息集写成新的 active 上下文；模型只重载 active 集合，旧消息仍保留在 `state.db`，并可由 `session_search` 找回。因此“会话没有新建”不等于每轮都把完整历史重新塞给模型。
- 兼容旧式 rotation 的路径即使产生新的 child `session_id`，仍属于同一个 `session_key` / 逻辑会话，override 会继续保留。只有无法继续压缩并进入 `compression_exhausted` 自动 reset 时，才会按真实会话边界清除 override。

当前会话时效与存储策略：

- `session_reset.mode: idle`、`idle_minutes: 1440`：连续 24 小时无活动后视为过期；后台 watcher 默认每 5 分钟检查一次，仍有后台任务运行的会话不会在任务中途过期。
- `compression.idle_compact_after_seconds: 1800` 不是会话过期。它只在下一条消息到来时检查：若已空闲至少 30 分钟，且估算上下文大于压缩目标下限（当前约 `700000 × 0.2 = 140000` tokens），会先做一次原地压缩再继续该轮。
- `sessions.auto_archive: true` / `auto_archive_days: 14` 只把 14 天未活动的会话标记归档；`sessions.auto_prune: false` 表示 `retention_days: 90` 当前不会自动删除数据库记录。实时上下文会被 compaction 控制，但 `state.db` 的可检索历史仍会增长，需要另行规划备份、prune 与 vacuum。

#### PDF / 文档在群聊中的读取边界

群聊中的“能读取 PDF 内容”和“能直接打开宿主缓存里的原始 PDF”是两件事：

- 对有文本层的 PDF、DOCX、XLSX、PPTX 等常见文档，Gateway 先在可信边界完成抽取，再以 `[Begin extracted attachment: ...]` / `[End extracted attachment]` 块注入**当前这一轮**。看到该块即代表模型已经拿到文档文本，不应再表述为“无法读取 PDF”。
- 群聊沙箱继续禁止 `read_file` 访问 `~/.hermes/cache/documents/...`，同时 Gateway 不再把该绝对路径写进模型可见提示。成功读取后模型只看到附件序号、抽取块或 sidecar 内容，不会再被诱导重复打开 cache。
- 若 PDF 为扫描件、图片型 PDF、本地可信抽取为空/失败，或覆盖率探测发现有意义的扫描/图片页缺口，Gateway 会把**当前这一个 PDF**交给 fallback 链中具备该 MIME 能力的 Gemini Flash sidecar，并把读取结果送回原会话；群聊不需要、也不会暴露 `vision_analyze`。
- 因此判断口径应是：有抽取块时可确认“已读取 PDF 的抽取文本”；同时存在 sidecar 读取时可进一步分析视觉内容；若两条链都失败，会看到明确的 `Attachment read status: FAILED` / `PDF visual coverage status: INCOMPLETE`，不得假装已经阅读。

Feishu 群里独立附件消息本身不能携带 @Hermes，因此当前配置允许同一发送者在 **300 秒**内补发 @Hermes，最多恢复 3 条消息 / 6 个图片、文件、视频或原生音频；显式回复附件并 @Hermes 优先且不受窗口去重抑制。恢复超时或下载失败会进入上述显式失败状态，不再静默只留下路径。

**常用配置项**：

| 配置项                                                    | 默认值                  | 说明                                                                       |
| --------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------- |
| `agent.max_turns`                                         | 90                      | 单次 session 最大轮数                                                      |
| `agent.gateway_timeout`                                   | 1800s                   | Gateway 会话超时（30 分钟）                                                |
| `agent.reasoning_effort`                                  | high                    | 主 agent 推理强度（none/low/medium/high/xhigh）                            |
| `agent.reasoning_overrides.gemini-3.5-flash`              | high                    | 末级 Flash fallback 使用高思考，与压缩模型保持一致                         |
| `delegation.reasoning_effort`                             | high                    | 子 agent / orchestrator 推理强度（空字符串表示继承主 agent）               |
| `display.personality`                                     | none（配置为空）        | 显示风格；如需恢复可在会话中执行 `/personality kawaii`                     |
| `display.show_reasoning`                                  | false                   | 是否在 TUI / 飞书等前端展示 reasoning 内容（依赖模型返回 reasoning）       |
| `display.streaming`                                       | true                    | 控制 **CLI/TUI 终端**逐 token 流式（仅终端，不影响平台前端）               |
| `streaming.enabled`                                       | false                   | 控制**飞书等 IM 前端**逐 token edit 流式；当前关闭，避免 markdown 渲染失真 |
| `compression.threshold`                                   | 0.7                     | 上下文占主模型容量比例触发压缩                                             |
| `compression.threshold_tokens`                            | 700000                  | 三档统一的绝对触发上限，保留约 300k 余量                                   |
| `compression.tail_mode`                                   | legacy                  | 保持既有原文 tail；`lean` 依赖摘要 digest/anchor/search 恢复               |
| `compression.codex_gpt55_autoraise`                       | false                   | 禁止 GPT-5.5 单独抬到 85%，避免切换 provider 后阈值分叉                    |
| `auxiliary.compression.model`                             | google/gemini-3.5-flash | 压缩任务与末级 fallback 使用同一 Vertex 模型                               |
| `auxiliary.compression.extra_body.google.thinking_config` | high / 不返回 thoughts  | 给摘要充分推理空间，同时避免输出内部思考占用正文预算                       |
| `approvals.mode`                                          | manual                  | 危险命令审批（manual/auto）                                                |

### Thinking / Reasoning 配置

当前 thinking/reasoning 配置与可见性：

| 位置                                     | 当前                | 模型                                      | TUI 可见 | 飞书可见                  |
| ---------------------------------------- | ------------------- | ----------------------------------------- | -------- | ------------------------- |
| 主 agent (`agent.reasoning_effort`)      | high                | gpt-5.5（Azure，Responses 路径）          | 不展示   | 不展示                    |
| 子 agent (`delegation.reasoning_effort`) | high                | 默认继承主模型                            | 不展示   | 不展示                    |
| Fallback[0] (`fallback_providers`)       | high                | bedrock/Claude Opus 5 application profile | 不展示   | 不展示                    |
| Fallback[1] (`fallback_providers`)       | reasoning: high     | vertex/google/gemini-3.5-flash            | 不展示   | 不展示                    |
| 压缩 (`auxiliary.compression`)           | high；隐藏 thoughts | vertex/google/gemini-3.5-flash            | —        | —（后台任务，不前端展示） |
| 显示开关 (`display.show_reasoning`)      | false               | —                                         | —        | —                         |

**已知限制**：

- 主模型 gpt-5.5 走 `azure-foundry`（codex-az 同源 Azure 端点，Codex Responses 路径），对话本身仍可能返回 reasoning；但当前 `display.show_reasoning: false`，前端不展示 thinking 段落。若临时改回 `true`，会重新显示前缀 `💭 **Reasoning:**` 的内容。
- Bedrock fallback 使用 `claude-am` 的 Opus 5 application-inference-profile ARN，Hermes 原生识别为 1M Claude 模型并走 Anthropic Bedrock SDK；Claude 3+ Haiku/Sonnet/Opus inference-profile ID 同时被识别为原生图片模型。
- 标准 `vertex` 保留 `google/gemini-*` 模型 ID，通过 provider-specific 路径处理 OAuth token refresh 与 Gemini thinking 参数；thought text 由 `PATCH-VERTEX-HIDDEN-THOUGHTS` 抑制。
- 从 Azure/Bedrock 会话 fallback 到 Gemini 时，历史工具调用没有 Gemini 原生 `thought_signature`；`PATCH-GEMINI-CROSS-PROVIDER-TOOL-HISTORY` 会在出站副本中注入官方兼容哨兵，避免末级 Vertex 立即 HTTP 400。

### 流式输出

Hermes 有**两套独立的流式机制**，配置项分别落在不同的 namespace 下：

| 配置                         | 控制对象                    | 当前值 | 说明                                                        |
| ---------------------------- | --------------------------- | ------ | ----------------------------------------------------------- |
| `display.streaming`          | CLI / TUI 终端逐 token 渲染 | true   | 仅影响终端展示，不影响 IM 平台                              |
| `streaming.enabled`          | 飞书等 IM 平台逐 token edit | false  | 通过 `update_message` API 增量编辑同一条消息                |
| `streaming.transport`        | 流式传输方式                | edit   | 当前仅 `edit`（progressive editMessageText）                |
| `streaming.edit_interval`    | 飞书消息 edit 最小间隔      | 1.0s   | 太低（< 0.4s）会触发飞书 API 限流；太高（> 1.5s）流畅度下降 |
| `streaming.buffer_threshold` | 累积多少字符强制 edit       | 40     | 与 `edit_interval` 互为兜底                                 |

**为什么飞书流式当前关闭**：

飞书 token 流式开启后会出现 markdown 渲染失真——根因是 `hermes-agent/plugins/platforms/feishu/adapter.py` 的 `_build_outbound_payload()` 每次 edit 重新探测 markdown 痕迹（`_MARKDOWN_HINT_RE` 要求 `**bold**`、`1.`、` ``` ` 等成对/完整出现），但流式中间帧的 buffer 经常处在"半开"状态（如 `**Hel`、` ` ``hello `），探测失败 → 走 plain text → 飞书 `update_message` 不能切换 msg_type → 后续 edit 全部锁死成 text → 用户看到 markdown 原文。

要重新开启流式且不丢格式，需要本地 patch（暂未实现）：让 `edit_message` 路径强制 `msg_type=post`，绕过 buffer-stage detection。在该 patch 落地前，飞书侧维持非流式整段输出，保留加粗/序号/列表渲染。

<a id="vertex-provider"></a>

### Vertex Provider（末级 fallback、压缩与多模态旁路）

主模型是 `azure-foundry/gpt-5.5`；标准 Vertex 承担四件事：

1. **fallback[1]** —— Azure 与 Bedrock 都失败后接管
2. **上下文压缩** —— `auxiliary.compression` 使用同一 Gemini 3.5 Flash
3. **音频/视频旁路** —— 前两档不支持这些原生输入时，由它只读取当前媒体并把结果交回主会话
4. **PDF 视觉兜底** —— 本地可信抽取为空或失败时读取 PDF；可正常抽取的文档仍留在本地处理

凭据链路：

1. `.env` 中的 `GOOGLE_APPLICATION_CREDENTIALS` 指向 service-account JSON，`VERTEX_PROJECT_ID` / `VERTEX_REGION` 指定 project/location。
2. Hermes 通过 `agent.vertex_adapter.get_vertex_config()` 用 `google-auth` mint OAuth token，指向
   `https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{region}/endpoints/openapi`，进程内自动 refresh。

```yaml
vertex:
  project_id: ""
  region: global
```

> `region: global` 是 Gemini 3.x preview 推荐/必要路径；regional endpoint 可能 404。

> OAuth token 由 `agent/vertex_adapter.py` 在进程内 mint/refresh，**不需要**任何外部刷新脚本或 LaunchAgent。
> （早期的 `provider: custom` + 定时刷新脚本方案已于 2026-08-11 删除；需要考古查 git 历史。）

#### LaunchAgent 代理注入（Feishu）

> **当前方案（2026-07-24 起）**：LLM 出站代理已改为写入 `~/.hermes/.env`（`HTTPS_PROXY` / `HTTP_PROXY` = `http://127.0.0.1:7897`，`NO_PROXY=127.0.0.1,localhost,feishu.cn,aliyuncs.com,pypi.org,files.pythonhosted.org,github.com,api.github.com,raw.githubusercontent.com`），由 `hermes_cli/env_loader.py` 在 gateway / cron / run_agent 全入口启动时以 `override=True` 载入 `os.environ`——OpenAI 兼容路径（`agent/process_bootstrap.py` 显式解析 proxy env）与 gemini-native 裸 `httpx.Client`（`trust_env` 默认）均生效；修改后 `hermes gateway restart` 生效。相比下述 plist 注入，`.env` 方案**不会**被 `hermes gateway install --force` 或升级期的 plist 自动重写（`hermes_cli/gateway.py` 的 `refresh_launchd_plist_if_needed()`）抹掉；`NO_PROXY` 保留飞书与 DashScope 国内直连，并让 PyPI 与 GitHub 的升级依赖/源码流量绕过只为 LLM 访问而启用的本机代理，避免 `hermes update` 因代理 TLS EOF 中断。下述 launchd 注入方式保留作为参考 / 备选（当前 plist 未注入代理环境变量）。

若需要让 **gateway** 走本地代理（例如 Clash mixed port `7897`），可使用辅助脚本。对于 mixed port，推荐按 **HTTP 代理** 注入：

```bash
~/.hermes/scripts/inject_launchd_proxy_env --proxy-url http://127.0.0.1:7897
```

它会先用 `curl` 通过代理探测连通性；**探测成功后**才会把 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / `NO_PROXY` 原子注入到以下 LaunchAgent 的 `EnvironmentVariables`，并重载服务：

- `ai.hermes.gateway`

若中途任一步失败，脚本会自动回滚 plist 到原状，保证最终状态是“要么全部注入，要么全部不注入”。

**默认注入的环境变量**：

```bash
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
ALL_PROXY=http://127.0.0.1:7897
NO_PROXY=127.0.0.1,localhost
```

**脚本成功的标志**：

- 退出码为 `0`
- 末尾打印 `Injected proxy into LaunchAgents:`
- `ai.hermes.gateway` 完成 `bootout + bootstrap`

脚本成功时**通常不需要额外手动重启**，因为它已经在成功路径中完成了重载。

**建议的验证动作**：

```bash
# 查看 LaunchAgent 状态
launchctl print gui/$(id -u)/ai.hermes.gateway

# 观察日志
tail -f ~/.hermes/logs/gateway.log
```

**原生回滚方式**（不使用额外 remove 脚本）：

```bash
# 重新生成 gateway 官方 plist（覆盖掉已注入的代理环境变量）
hermes gateway install --force
```

常用检查命令：

```bash
launchctl print gui/$(id -u)/ai.hermes.gateway
tail -f ~/.hermes/logs/gateway.log
```

#### 与 Hermes 后台自启动的关系

当前只有一个 Hermes LaunchAgent：

```text
launchd
└─ ai.hermes.gateway   # Hermes gateway 常驻
```

- `hermes gateway install` 负责 Hermes gateway 常驻、自启动、维持飞书 WebSocket 和 cron
- Vertex OAuth token 由 Hermes 进程内 mint/refresh（`agent.vertex_adapter`），**不需要**任何外部刷新
  LaunchAgent

当前推荐组合是：

1. `.env` 写入标准 Vertex 的 `GOOGLE_APPLICATION_CREDENTIALS` + `VERTEX_PROJECT_ID` + `VERTEX_REGION`
2. `fallback_providers[1]` 与 `auxiliary.compression` 都保持 `vertex/google/gemini-3.5-flash`
3. 执行 `hermes gateway install`，确保后台服务可自启动

### 飞书集成

1. 在[飞书开放平台](https://open.feishu.cn/)创建企业自建应用
2. 开启 **事件订阅 → 使用长连接接收事件**（WebSocket 模式，无需公网 IP）
3. 添加机器人能力，申请以下权限：
   - `im:message` / `im:message:send_as_bot`（发送消息）
   - `im:chat` / `im:resource`（读取群聊/文件）
   - `contact:user.id:readonly`（用户 ID）
   - 可选：`admin:app.info:readonly`（群聊 @mention 精确识别，否则只能 DM）
4. 将 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 写入 `.env`
5. 安装并启动 gateway（见下节）

> **已知 Warning**：`bot identity check failed: app.info:readonly`——这是权限不足导致的非阻塞警告，DM 模式正常工作，群聊 @mention 检测受影响。

---

## Gateway 服务

Gateway 是常驻后台服务，负责维持飞书 WebSocket 长连接和 Cron 调度。

> **如果主模型使用官方 `provider: vertex`**：`hermes gateway install` 只负责 gateway 常驻；Vertex OAuth token 由 Hermes 进程内自动 mint/refresh，不需要额外的 Vertex refresh LaunchAgent。

```bash
# 安装为 launchd 服务（macOS）
hermes gateway install

# 服务状态检查
hermes gateway status

# 启动 / 停止 / 重启
hermes gateway start
hermes gateway stop
hermes gateway restart

# 卸载服务
hermes gateway uninstall
```

> `hermes gateway start` 会在启动时比较并自愈过期 plist；完整升级仍推荐走 `hermes-update.sh`，它会在本地 patch 回贴后验证最终 service definition、launchd wrapper 和真实 Gateway 子进程，而不是在裸 upstream 窗口提前固化 plist。

**服务文件位置**：`~/Library/LaunchAgents/ai.hermes.gateway.plist`

**日志查看**：

```bash
hermes logs
# 或直接查看
tail -f ~/.hermes/logs/gateway.log
```

---

## 用户插件 (Plugins)

Hermes 内置插件系统支持四个发现源（详见 `hermes-agent/hermes_cli/plugins.py` 顶部 docstring）：

1. Bundled — `hermes-agent/plugins/<name>/`（随官方仓库分发）
2. **User — `~/.hermes/plugins/<name>/`**（本仓库管理，**入库**）
3. Project — `./.hermes/plugins/<name>/`（仅在 `HERMES_ENABLE_PROJECT_PLUGINS` 时启用）
4. Pip — 通过 entry-point `hermes_agent.plugins` 注册

后发现源覆盖前发现源（同名 user plugin 会替换 bundled）。本仓库的 `plugins/` 目录就是 User 这一层。

### 用户插件结构

每个插件必须包含 `plugin.yaml` 清单 + `__init__.py`（暴露 `register(ctx)` 函数）。通过 `ctx.register_hook(name, callback)` 挂载 `VALID_HOOKS` 里登记的生命周期钩子，常用的包括：

| 钩子                   | 触发时机                               | 返回值用途                                   |
| ---------------------- | -------------------------------------- | -------------------------------------------- |
| `pre_gateway_dispatch` | 每条入站消息（鉴权前）                 | `{action: skip/rewrite/allow}` 影响后续派发  |
| `pre_tool_call`        | 任意工具执行前                         | `{action: block, message: ...}` 拦截该次调用 |
| `post_tool_call`       | 工具执行后                             | 观察 / 副作用                                |
| `on_session_*`         | 会话生命周期（start / end / finalize） | 观察 / 副作用                                |

完整清单见 `hermes_cli/plugins.py` 中 `VALID_HOOKS`。

### 通用启用 / 禁用流程

用户插件**默认是"发现但不启用"**——`hermes plugins list` 会列出来但显示 `not enabled`，必须显式启用一次：

```bash
hermes plugins list                # 查看所有已发现的插件及启用状态
hermes plugins enable <name>       # 启用单个插件（一次性，状态会持久化）
hermes plugins disable <name>      # 禁用（保留代码，下次启动跳过）
hermes gateway restart             # 重启 gateway 加载插件
```

启用状态生效后，后续修改插件代码 / 配置只需 `hermes gateway restart`，不需要再 `enable`。

### sandbox：飞书会话级工具沙盒

**位置**：`plugins/sandbox/`（`plugin.yaml` + `__init__.py` + `config.yaml`）

**作用**：bot 同一个 Feishu 应用账号同时服务多个会话时，按 `chat_id` + `chat_type` 区分工具权限——配置中列出的 owner DM 拥有完整工具集，其他 Feishu DM 只能调用基础安全白名单；Feishu 群聊/频道额外拥有只读知识工具、按群隔离的临时文件工具，以及受控的飞书文档脚本入口。HyperTeX MCP 使用一条窄策略：owner DM 与群聊中显式配置的受信任内测账号可以调用，创建/迭代任务固定使用 `hermes` Contributor、`codex` 和 `deck`，本轮飞书附件经私有目录暂存后自动注入，不把宿主缓存路径暴露给模型；其他群成员即使能看见工具说明也会在调用期被拒绝。非 Feishu 来源（CLI/TUI、cron 调度器、内部事件）一律放行不拦截。

**为什么需要它**：hermes 原生 platform enum 只提供 `feishu`，同一个 Feishu bot 下所有 chat 原本共享一份工具列表。若把 bot 拉进群或被别人加为联系人，对方可以直接让 bot 调 `terminal` / `read_file` 等危险工具。`allowed_chats` 白名单虽然能限制响应范围，但代价是其他会话完全得不到响应；要在"允许其他人聊天/搜索/问图"和"禁止其他人碰系统"之间取折衷，原生配置做不到。本地 `PATCH-FEISHU-GROUP-SCOPE` 让真实 Gateway consumer 按 chat type 选择 `feishu` / `feishu_group` namespace，本插件再通过官方 `pre_gateway_dispatch` + `pre_tool_call` + `post_tool_call` 钩子做调用期纵深裁剪与本轮临时文件授权。

**机制（要点）**：

- `pre_gateway_dispatch` 把入站消息的 `(platform, chat_id, chat_type, user_id)`、当前附件缓存路径，以及**当前消息/明确引用消息**中的飞书资源 token 写入 `contextvars.ContextVar`，asyncio 会自动把该 context 传到所有后续 `await` / `create_task` 子任务里。历史回填 `channel_context` 不授予资源访问，避免后来的参与者复用旧群消息里的链接。
- `pre_tool_call` 读取 ContextVar：若 `platform != "feishu"` 直接放行；若 `chat_id` 在 owner 白名单里，普通工具直接放行，HyperTeX 的 4 个原始工具与协商生成的标准 Tasks utilities 则先固定边界：创建/迭代调用固定 Contributor / `codex` / `deck` 并把本轮附件复制到稳定私有目录后注入 `asset_paths`，后续状态查询使用 `mcp__hypertex__tasks_get`。每个入站 turn 最多放行一次 HyperTeX 调用：创建后同轮轮询、查询失败后同轮重试、list/get_case fallback 都在调用 MCP 前被拦截，避免本地 transport 异常占住主会话。群聊优先应用群专用 allowlist，不继承 outsider-DM 的 `vision_analyze` / `image_generate` 放行；HyperTeX 全工具面虽加入 `feishu_group`，但调用期还要求当前 `user_id` 位于 `trusted_feishu_user_ids_for_group_hypertex`。其他私聊才使用基础安全 allowlist。配置解析失败时对 Feishu fail closed。
- `post_tool_call` 只观察群聊 `web_extract`：长网页被截断并写入 `cache/web` 时，仅把**本群本轮刚产生的精确缓存文件**临时加入可读集合；不开放整个 cache，新消息到来即撤销，其他群不能复用。
- 群聊放行 `skills_list` / `skill_view` 只打开“读 skill”通路；实际可读 skill 仍由 `skills.platform_allowed.feishu_group` 限制。当前配置允许 `llm-wiki`、`feishu-docs` 与 `excel-processing`，不开放 `skill_manage`。放行的 skill 里若带 `scripts/`，群聊也只能「读」不能「跑」——群聊没有 `terminal` / `process`，`feishu_doc_manage` 只映射 `feishu_doc_scripts_root` 下的固定 action。
- `read_file` / `search_files` 只允许 `~/.hermes/wiki` 和当前群自己的工作区；`search_files` 省略 path 时安全重写到 wiki 根。`~/.hermes/tmp/group-workspaces/<chat-id-hash>/` 按群隔离，其他群工作区、`tmp/nightly_report`、全局 `cache`、`skills`、`my-skills` 均不能通过文件工具访问；唯一例外是上条本轮 web_extract 精确文件授权。
- 群聊不拥有 `terminal` / `process` / `write_file` / `patch` / `vision_analyze` / `image_generate`；图片、音频、视频和扫描 PDF 由 Gateway 入站 native/sidecar 链路自动处理。`group_cache` 用结构化参数完成当前群工作区内的读写、移动和删除；`feishu_doc_manage` 把固定 action 映射到管理员逐项批准的既有脚本。群成员只能读取当前消息/引用中明确出现的飞书资源；create/append/rebuild/delete 仅允许 `trusted_feishu_user_ids_for_group_mutations` 中的维护者，既有文档修改还必须在当前消息/引用中附目标链接。hook 与 handler 双层校验。
- `group_cache` / `feishu_doc_manage` 属于 Feishu group 的 deferred plugin tools；它们必须能通过 `tool_search` / `tool_describe` 被发现和描述，不能依赖模型猜 schema。`tool_search` / `tool_describe` 是只读工具目录桥，群聊显式放行；`tool_call` 会先按当前 `feishu_group` toolset 解包成底层工具再进 sandbox hook。`plugins/sandbox/verify.sh` 会用真实 `feishu_group` toolset 和 sandbox hook 锁住这一点，所以灰度群和其他群保持同一工具面。
- 既有脚本用 argv + `shell=False` 启动；macOS `sandbox-exec` profile 由插件生成并由子进程继承，整个进程树只允许写当前群工作区。若进程沙箱不可用，脚本工具 fail closed。工作区文件作为数据使用，永不作为脚本执行；stdout/stderr 回传前会脱敏 Bearer token、Feishu app secret 与 tenant token，上传 helper 也不会把含凭据的 curl argv 串进 traceback。
- 不用 `threading.local`（asyncio 多协程同线程会串），不用 `set_thread_tool_whitelist`（同样问题），坚持 ContextVar。

**配置**（`plugins/sandbox/config.yaml`）：

```yaml
owner_feishu_chat_ids:
  - oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 你和 bot 的主 DM chat_id；可填多个
hypertex_asset_staging_root: ~/.hermes/tmp/hypertex-assets
hypertex_max_asset_bytes: 50000000
hypertex_max_assets_per_turn: 6
hypertex_asset_staging_ttl_seconds: 86400
allowed_tools_for_outsiders:
  - web_search
  - web_extract
  - vision_analyze
  - image_generate
allowed_tools_for_outsider_groups:
  - clarify
  - web_search
  - web_extract
  - tool_search
  - tool_describe
  - skills_list
  - skill_view
  - feishu_doc_read
  - read_file
  - search_files
  - group_cache
  - feishu_doc_manage
trusted_feishu_user_ids_for_group_mutations:
  - ou_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 允许在群聊创建/修改飞书文档的维护者 user_id
allowed_read_roots_for_outsider_groups:
  - ~/.hermes/wiki
group_workspace_root: ~/.hermes/tmp/group-workspaces
allowed_feishu_script_actions_for_outsider_groups:
  - create
  - append
  - rebuild
  - delete
  - read_url
  - download_file
feishu_doc_scripts_root: ~/.hermes/my-skills/productivity/feishu-docs/scripts
python_executable: ~/.hermes/hermes-agent/venv/bin/python
group_max_download_bytes: 50000000
require_process_sandbox: true
```

`known_plugin_toolsets` 还需把 `sandbox_group` 标记为 `cli` / `feishu` / `feishu_group` 已知；只有 `platform_toolsets.feishu_group` 显式列出它，避免该插件工具集作为“新插件默认开启”出现在 CLI 或飞书私聊。

获取自己主 DM 的 `chat_id`：在主 DM 里发送 `/whoami` 查看回执；或翻 `~/.hermes/sessions/session_*.json` 找 `platform: feishu` 的最近会话取其 `chat_id` 字段。

**首次部署**：

```bash
# 1. 编辑 owner_feishu_chat_ids 填入主 DM 的 chat_id
$EDITOR ~/.hermes/plugins/sandbox/config.yaml

# 2. 启用插件（仅首次需要）
hermes plugins enable sandbox

# 3. 重启 gateway
hermes gateway restart

# 4. 验证：查 agent.log 应有 sandbox: registered (active=True, owner_chats=[...], group_allowed=[...])
grep "sandbox: registered" ~/.hermes/logs/agent.log | tail -1
```

`active=True` 且 `owner_chats` 非空表示生效；若 `active=False`，Feishu 工具调用 fail closed，先修复配置再恢复群聊能力。

**运维与扩展**：

- 增加特权会话：编辑 `plugins/sandbox/config.yaml` 的 `owner_feishu_chat_ids` 数组追加新 chat_id，重启 gateway。
- 调整 HyperTeX 附件边界：只改 `hypertex_asset_staging_*` / `hypertex_max_asset_*` 配置；不要把 Feishu cache 路径直接写进 skill 或提示词。暂存目录必须保持 owner-only，过期目录由下一次创建调用清理。
- 调整飞书文档脚本：只能在代码中的 action→固定文件映射和 `allowed_feishu_script_actions_for_outsider_groups` 两处显式加入，并为参数约束补测试；禁止改回目录级脚本 allowlist。
- 临时关闭：`hermes plugins disable sandbox && hermes gateway restart`，下次开启重新 `enable` 即可。
- 反面测试：临时把 `owner_feishu_chat_ids` 改成一个不存在的 chat_id 并重启，然后在主 DM 让 bot 跑 `terminal`——应该被拦下并回 `block_message`；验完改回去再重启。

**升级兼容性检查**：

插件依赖上游 hooks、`ctx.register_tool()` 和 toolset 注册机制。配套脚本 `plugins/sandbox/verify.sh` 会检查 hooks/fire sites、根配置与插件配置、真实平台 toolset 解析、fixed script 映射、`sandbox-exec`、插件单测，以及与当前 gateway PID 匹配的最新运行日志：

```bash
bash ~/.hermes/plugins/sandbox/verify.sh
# 1. VALID_HOOKS 仍含 pre_gateway_dispatch / pre_tool_call / post_tool_call（HARD FAIL if 改名）
# 2. fire site 在 gateway/run.py / model_tools.py 中仍存在（HARD FAIL）
# 3. YAML 契约、固定脚本、open group policy、manual approval 与 owner/group 配置无漂移；launchd 无 YOLO
# 4. 真实解析 owner Feishu 完整工具面、群聊受限工具面，并由 Gateway 边界回归证明 consumer 没有把群重新映射成 DM
# 5. 运行插件安全回归（当前 32 tests），并检查当前 gateway PID 的 runtime 注册日志
```

该脚本由 `hermes-update.sh` Step 8e 在每次官方更新后自动调用，无需手动跑。verifier 缺失、不可执行或任一检查失败都会设置 `FINAL_RC=1`，整次升级以非零退出并在 action item 中提示修复；不能再出现 sandbox 已失效但升级仍显示成功。

**已知限制 / 注意点**：

- 用户插件在 `~/.hermes/plugins/`，与 `hermes-agent/` 源码完全分离，`hermes update` / 升级官方仓库**不会**影响插件。但官方若改动 `VALID_HOOKS` 的 kwargs 签名（大版本概率事件），插件需要同步小修——升级后看 Step 8e 的输出即可。
- 插件靠 ContextVar 跨 `await` 边界传 `chat_id`，hermes 当前 asyncio 单线程架构下安全。若上游改为把 agent 跑在 `loop.run_in_executor` worker 线程里且不显式 `copy_context()`，会失效；目前没有这种使用方式，但属于升级时要留意的"前提"。
- `tmp` 不能整目录删除：`scripts/nightly_greeting.py` 仍用 `tmp/nightly_report` 保存状态和锁。群工作区目前不自动按时间清理；50 MB 单文件下载上限只防单次大文件，不代替后续的数据保留/总配额策略。
- block 是工具级别的，模型回复里仍然可以聊天/搜网/看图/画图——这是设计预期，不是 bug。

---

## Logi Options+ 看门狗 (可选)

本仓库提供两个互补的 LaunchAgent，处理 Logi Options+ 在外接显示器场景下的两种故障模式。**默认不安装**，一次安装两个：`~/.hermes/scripts/install_logi_watchdog_launchd`。

| 组件       | 文件                                          | LaunchAgent Label                | 负责故障模式                                   |
| ---------- | --------------------------------------------- | -------------------------------- | ---------------------------------------------- |
| 轮询看门狗 | `scripts/logi_options_watchdog`（bash）       | `ai.hermes.logi-watchdog`        | **真死掉** —— Logi agent 进程消失              |
| 显示反应器 | `scripts/logi_display_reactor.swift`（Swift） | `ai.hermes.logi-display-reactor` | **假活着** —— 进程在跑但内部状态被显示事件搞坏 |

### 适用场景

外接显示器通过 Dock / Hub 接 Mac 时，每次 Amphetamine session 结束（或其他释放系统级电源 assertion 的场景）会触发 macOS 对外接显示器的 DP Alt Mode 重协商：表现为屏幕黑屏 1-2 秒。重协商过程中 Logi Options+ 的后台 daemon (`logioptionsplus_agent`) 会以两种方式出问题：

1. **真死掉**：进程崩溃消失。Logi 自带的 `KeepAlive`（`com.logi.cp-dev-mgr`，`SuccessfulExit: false`）大多数时候能恢复，但 launchd 节流或 crashpad 走 exit 0 路径时会失效。
2. **假活着**：进程没崩，但内部状态机被显示事件打乱（丢失蓝牙会话、按键映射上下文等）。表现为蓝牙鼠标退回 macOS 原生 HID 驱动，Smooth Scrolling、按键映射等高级功能失效，但 `pgrep` 看进程还在。

> **根因不可治**：黑屏来自 macOS 协议层 DP Alt Mode 重协商，无法消除；Logi 崩溃/状态错乱是上游 daemon bug。本插件只缩短失效窗口（**目标 3 秒内恢复**），不修复根因。

### 为什么放在 Hermes 配置仓库

- 触发场景（Amphetamine session）都是为 Hermes 工作开的，与 Hermes 使用习惯绑定
- `scripts/` 已有 launchd 辅助脚本与安装器，可复用相同的命名空间、日志路径和幂等安装模式
- 这两个 LaunchAgent 都是 OS 服务，生命周期独立于 Hermes 进程（Hermes 不在时也照常工作）

### 安装

```bash
~/.hermes/scripts/install_logi_watchdog_launchd

# 可选：调轮询间隔（默认 1s）或反应器去抖时长（默认 3s）
~/.hermes/scripts/install_logi_watchdog_launchd --interval-seconds 2 --debounce-seconds 5
```

默认行为：

- LaunchAgent labels：`ai.hermes.logi-watchdog` + `ai.hermes.logi-display-reactor`
- plist 路径：
  - `~/Library/LaunchAgents/ai.hermes.logi-watchdog.plist`
  - `~/Library/LaunchAgents/ai.hermes.logi-display-reactor.plist`
- 轮询间隔（Layer 2）：1s
- 去抖窗口（Layer 3）：30s
- 业务日志（两个共享）：`~/.hermes/logs/logi-watchdog.log` —— 启动 / 重启动作 / 显示事件触发都写在这里
- launchd 捕获的 stdout/stderr：
  - `logi-watchdog.stdout.log` + `logi-watchdog.err.log`
  - `logi-display-reactor.stdout.log` + `logi-display-reactor.err.log`

### 工作机制

#### 三层防御

```
Logi 出问题
   ├─ Layer 1: com.logi.cp-dev-mgr KeepAlive（Logi 自带，毫秒级，干净崩溃时）
   ├─ Layer 2: ai.hermes.logi-watchdog（1s 轮询，PID 视角；处理 Layer 1 节流/失效）
   └─ Layer 3: ai.hermes.logi-display-reactor（显示事件触发，处理"进程活着但状态坏"）
```

#### Layer 2: 轮询看门狗

bash 长驻循环，每个间隔执行 `pgrep -f "logioptionsplus_agent --launchd"`：

- 存在 → 静默继续
- 不存在 → 依次尝试 `launchctl kickstart -k gui/<uid>/com.logi.cp-dev-mgr` → `open -a` fallback → 失败记 `restart attempts failed`

1s 检测 + 1-2s 重启 = 2-3s 恢复。CPU 负载 < 0.5%。

#### Layer 3: 显示反应器

Swift 进程订阅 macOS `NSWorkspace.didWakeNotification` 和 `DistributedNotificationCenter` 上的 `com.apple.screenIsUnlocked`，捕获屏幕唤醒事件后**直接 SIGKILL** `logioptionsplus_agent`，让 Layer 1 + Layer 2 接力把它拉回来。

关键设计：

- **只 kill 不 restart**：反应器只负责"破"，"立"留给 Layer 1/2 —— 责任清晰，不重复
- **双信号源**：`screenIsUnlocked` 在解锁瞬间最早触发，`didWake` 几十秒后由系统电源管理器补一发；订阅两个保证一定能捕获到
- **去抖（debounce）**：默认 30 秒。同一次唤醒会发出 `screenIsUnlocked` + `didWake` 两条通知（时差可达 30 秒），统一视为一次事件，只 kill 一次。这个参数与"恢复延迟"无关 —— Logi 永远在 SIGKILL 后 1-2 秒被拉回，debounce 只是阻止冗余 kill
- **空闲 CPU 占用 0%**：完全事件驱动，不轮询

> **早期实现尝试过 `CGDisplayRegisterReconfigurationCallback`**（更精确的"显示重协商"事件），但在 launchd 启动的 `swift -interpret` 上下文里 CG 回调无法到达进程（缺乏 WindowServer bootstrap，即使加 `NSApplication.run()` 也不行）。改用 NSWorkspace 通知后稳定可工作 —— 这条机制与已移除的 Vertex wake watcher 同源（见 git 历史）。

### 运维常用命令

```bash
# 状态检查（两个都看）
launchctl print gui/$(id -u)/ai.hermes.logi-watchdog | head
launchctl print gui/$(id -u)/ai.hermes.logi-display-reactor | head

# 实时跟所有 Logi 相关动作（共享日志）
tail -f ~/.hermes/logs/logi-watchdog.log

# 看反应器自己的启动日志（与跳屏事件对应）
tail -f ~/.hermes/logs/logi-display-reactor.stdout.log

# 手动验证 Layer 2 (轮询) 恢复时长
date +%s.%N ; pkill -9 -f "logioptionsplus_agent --launchd"
while ! pgrep -f "logioptionsplus_agent --launchd" >/dev/null; do : ; done
date +%s.%N

# 手动触发 Layer 3 (反应器)：让屏幕睡眠 1 秒再唤醒
pmset displaysleepnow ; sleep 2 ; caffeinate -u -t 1
# 几秒后日志应该多出 'screenIsUnlocked → SIGKILL Logi agent' 一行

# 调整参数（重新运行 installer 即可，会自动 bootout + bootstrap 两个 agent）
~/.hermes/scripts/install_logi_watchdog_launchd --interval-seconds 2 --debounce-seconds 5

# 卸载（installer 末尾也会打印这三行）
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.logi-watchdog.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.logi-display-reactor.plist
rm -f ~/Library/LaunchAgents/ai.hermes.logi-watchdog.plist \
      ~/Library/LaunchAgents/ai.hermes.logi-display-reactor.plist
```

日志里典型行：

| 日志行                                                  | 含义                                                                |
| ------------------------------------------------------- | ------------------------------------------------------------------- |
| `watchdog started (interval=1s)`                        | Layer 2 启动                                                        |
| `logi-display-reactor started (debounce=30s, mode=...)` | Layer 3 启动                                                        |
| `screenIsUnlocked → SIGKILL Logi agent`                 | Layer 3 在解锁瞬间触发                                              |
| `didWake → SIGKILL Logi agent`                          | Layer 3 在系统唤醒事件触发（如果 30s 内已被 unlock 触发，则被去抖） |
| `restarted via launchctl kickstart`                     | Layer 2 检测到进程消失并拉回（Layer 1 没接住）                      |
| `restarted via open -a`                                 | Layer 2 kickstart 失败、退而 fallback 启 .app                       |
| `restart attempts failed`                               | 两条路径都失败 —— 检查 Logi 安装是否完整                            |

### 与 Logi 自带 LaunchAgent 的关系

`com.logi.cp-dev-mgr`（Logi 自带）、`ai.hermes.logi-watchdog`、`ai.hermes.logi-display-reactor` 是三个独立 LaunchAgent，互不替代、互不冲突：

- Logi 自带负责正常启动和绝大多数干净崩溃的 KeepAlive（毫秒级）
- 轮询看门狗作为**外层兜底**，在 Logi KeepAlive 节流或被判为「成功退出」时补救
- 显示反应器主动**触发**重启，处理 Logi 进程没崩但状态坏掉的情况

`launchctl kickstart` 和 `pkill` 对同一个 service / 进程都是幂等的，不会产生重复进程。

### 已知限制

- 跳屏本身不能消除 —— 仅缩短 Logi 失效窗口
- 反应器对 Logi 状态损坏的判定是**保守的**（只要解锁/唤醒就 kill），代价是每次唤醒都强制一次 Logi 重启（1-2s）。如果你的环境唤醒频繁且 Logi 其实没坏，可以把 debounce 调大或卸载 Layer 3 保留 Layer 2。
- 30 秒去抖窗口内若发生第二次独立的唤醒事件（罕见，例如 30s 内主动让屏幕睡眠后又唤醒），会被静默吞掉一次 —— 万一 Logi 在那次坏掉，得等到 Layer 2 / 下次唤醒救
- pgrep 模式匹配依赖 `logioptionsplus_agent --launchd` 命令行，Logi 升级如改了启动参数需同步更新 `scripts/logi_options_watchdog` 中的 `AGENT_PATTERN`
- 反应器需要进程在 GUI session（Aqua）中才能订阅 CG 回调；plist 已 bootstrap 到 `gui/$(id -u)` domain，正常使用无须额外配置

---

## Shell 集成

zsh 补全脚本存放在 `completions/_hermes`（`#compdef` 格式，须通过 `fpath` 加载，**不能 `source`**）。

**`.zshrc` 正确配置方式**：在 `source "$ZSH/oh-my-zsh.sh"` **之前**加入：

```zsh
# Hermes completions — must be added to fpath BEFORE oh-my-zsh sources compinit
if [[ -f "${HOME}/.hermes/completions/_hermes" ]]; then
    fpath+=("$HOME/.hermes/completions")
fi
```

配置好后清除缓存生效：

```bash
rm -f ~/.zcompdump* && exec zsh
```

> **常见错误**：直接 `source completions/_hermes` 不会注册补全，因为 `#compdef` 文件不是普通脚本，必须通过 fpath + compinit 机制加载。

**更新补全脚本**（hermes 升级后）：

```bash
hermes completion zsh > ~/.hermes/completions/_hermes
rm -f ~/.zcompdump* && exec zsh
```

---

## 更新

推荐使用 `hermes-update.sh` 一键完成完整更新流程：

```bash
# 每次用户明确发起的新升级：唯一一次官方 fetch/pull
bash ~/.hermes/hermes-update.sh --update

# 同一轮后续冲突修复、脚本调整和回归收敛：固定 SHA，不访问上游
bash ~/.hermes/hermes-update.sh --reconcile
```

`--update` 会执行唯一一次 scoped official fetch，把结果写入专用 Git ref 并立即固定本轮 `TARGET_SHA`；随后官方 updater 通过临时 Git 代理只消费该 SHA，其内置 fetch 被置为 no-op。失败或中断时，`.hermes-update-transaction` 以 `0600` 保留目标和运行态恢复信息；后续即使再次误传 `--update`，也只会接管原目标，不会重新追逐 `origin/main`。只有整支脚本 exit 0 才删除事务状态与专用 ref。默认无参数等同 `--reconcile`，因此日常复验不会 fetch/pull，也不会在 HEAD/patch 未变化时制造 Gateway 新 PID。

脚本依次执行以下步骤，完成后显示状态摘要和待操作提示：

| 步骤 | 操作                                      | 说明                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ---- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Preflight + transaction                   | 确认 hermes 可用、git 仓库存在、index 干净；`--update` 仅在无未完成事务时开放一次官方获取，默认/`--reconcile` 固定当前事务 SHA 且不做网络探测。staged 用户改动在任何 mutation 前 fail closed                                                                                                                                                                                                                                                                                                                                      |
| 2    | **Save & clean patches**                  | 用 full-index 临时包保存完整 overlay；已有 bundle 时若仅部分 `PATCHED_FILES` 有 diff 会拒绝覆盖，临时包通过 cached 正向 + worktree 反向检查后才原子发布，再还原文件至 HEAD。PATCHED_FILES 之外的额外改动在 update 前用 `git stash push -u` 保护，避免 untracked 文件被清理；接管“裸 worktree + 完整 bundle”时 EXIT trap 仍保持武装                                                                                                                                                                                                |
| 3    | 单次 acquire / 固定 SHA reconcile         | 新事务 `--update` 执行一次 scoped official fetch 并立即固定专用 ref；仅在尚未取得目标 SHA 的早期 GitHub transport 错误做最多 3 次有界重试。随后官方 updater 的 Git 访问被代理约束到 `TARGET_SHA`，其内置 fetch no-op；目标一经取得，后续执行只校验或从本地对象 fast-forward，绝不再次访问远端。认证、分叉、安装与迁移错误不重试                                                                                                                                                                                                   |
| 4    | `npm audit fix`                           | 修复 hermes update 安装 npm 依赖后遗留的已知安全漏洞；非零时把完整输出留进日志并要求 `npm audit --json` 定性，禁止机械重跑/`--force`。若只剩上游 lock/range 无法非破坏修复，且经依赖链确认不影响飞书主链路，则归为 P2 上游阻挡，以 warning + 当前周摘要留案（`PATCH-NPM-DEPENDENCY-HYGIENE`）                                                                                                                                                                                                                                     |
| 4b   | Skills 镜像同步                           | `rsync --delete` 镜像上游拥有的 skill 内容，保留本地 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.hub` / `.archive` 等 runtime state；新增 skill 自动添加、上游孤儿自动清理，rsync 失败令整轮非零；`my-skills/` 不受影响（`PATCH-SKILLS-MIRROR-METADATA`）                                                                                                                                                                                                                                                          |
| 5    | Gateway plist 前置快照                    | patch 尚未回贴时只记录 plist 是否 stale/loaded，不在裸 upstream 窗口改写定义；权威刷新延后到 Step 8                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 6    | Gateway 运行态前置检查                    | 若此时未运行也暂缓启动，避免用未回贴的 `gateway.py` 生成最终 service command；Step 8 回贴后统一恢复                                                                                                                                                                                                                                                                                                                                                                                                                               |
| 7    | `hermes completion zsh`                   | 重新生成 zsh 补全脚本；若上游回滚到坏的 `_arguments` 语法则自动重新应用 PATCH-ZSH-COMPLETION-SYNTAX（v0.13.0 起上游已修复 commit `fe61d95b4`，detection 块作为回归 sentinel 保留），随后清除 zcompdump 缓存                                                                                                                                                                                                                                                                                                                       |
| 8    | **Re-apply & verify patches**             | 原子回放 `patches/local-patches.diff`（3-way 成功后自动清 staged index），再按 `PATCHES.md` 中每个语义补丁分别验证 gate；74/74 live diff 覆盖、full-index 逐字节一致、cached 正向、worktree 反向和 index-clean 全部通过后才刷新 replay bundle/base。回贴后再用最终 `gateway.py` 验证/刷新 plist，必须同时得到 current definition、launchd wrapper PID 与真实 Gateway 子进程；Step 8d 仅在事务 `runtime_dirty=1` 时排空重启并要求 PID 替换，无变化 reconcile 不制造 PID。`llm-wiki` 随后同步到 runtime mirror 并重建 manifest 基线 |
| 8e   | **Verify user plugins**                   | 强制验证 `PATCH-FEISHU-GROUP-SANDBOX` 等配置仓库用户插件：verifier 必须存在且可执行；结构化检查 YAML/固定脚本，真实解析 owner/group toolset，运行行为测试；launchd wrapper 健康由 status 证明，插件注册 trace 绑定 `gateway.status.get_running_pid()` 返回的真实 Gateway 子进程 PID。任一失败令整次升级非零退出                                                                                                                                                                                                                   |
| 9    | `hermes doctor` + `hermes gateway status` | 验证更新结果；若 gateway 因 update / post-patch restart 处于未加载状态，脚本会自动补一次最终恢复（`install --force` / `start`）后再判定                                                                                                                                                                                                                                                                                                                                                                                           |

> ⚠ **脚本维护提示**：若 hermes 上游大版本升级后更新流程发生变化（新增步骤、flags 变动、路径变更），需同步更新 `~/.hermes/hermes-update.sh`。脚本顶部有详细的"需关注场景"注释。

### 手动步骤参考

若脚本某步失败，可单独执行对应命令排查：

```bash
# 新的官方更新事务（仅调用一次）
bash ~/.hermes/hermes-update.sh --update

# 同一事务后续修复与回归（固定 SHA、无网络）
bash ~/.hermes/hermes-update.sh --reconcile

# 刷新/启动 launchd 服务；会自愈 stale plist
hermes gateway start

# zsh 补全脚本
hermes completion zsh > ~/.hermes/completions/_hermes
rm -f ~/.zcompdump*

# 验证（事务内不要用带隐式 update-check 的 `hermes --version`）
sed -nE '/^__(version|release_date)__/p' ~/.hermes/hermes-agent/hermes_cli/__init__.py
hermes doctor
hermes gateway status
```

---

## 本地补丁记录

本项目维护 38 个按职责命名的活跃语义补丁：31 个工程内补丁、6 个升级期运行时补丁和 1 个外层配置仓库插件补丁。完整责任边界、依赖、验证 gate 和上游吸收条件见 [`patches/PATCHES.md`](patches/PATCHES.md)。工程内改动仍以单一 full-index `local-patches.diff` 作为原子 replay bundle，但每个语义补丁在 Step 8b 独立验收；`PATCH-UPDATE-TRANSACTION-PIN` 保证一次升级只取得一个 upstream snapshot，后续围绕固定 SHA reconcile；`PATCH-LAUNCHD-WRAPPER-SUPERVISOR` 保证 launchd stderr wrapper 启动的真实 Gateway 子进程保留受监管身份；`PATCH-ENV-AMBIENT-CREDENTIAL-ISOLATION` 阻止 shell/`~/.secrets` 凭据越界进入 Hermes；`PATCH-MODEL-CONFIGURED-ONLY` 让 `/model` 只展示并切换 config 中的主模型/fallback；`PATCH-DOCTOR-TEST-NETWORK-ISOLATION` 让 doctor 单测不再继承宿主网络与凭据；`PATCH-MCP-TASKS-ASYNC-HANDOFF` 让标准 MCP task handle 确定性回执并结束当前 turn；`PATCH-FEISHU-GROUP-SANDBOX` 不进入内层 diff，由 Step 8e 强制 verifier 管理。当前基线为上游 `8ad055414bcae75486952c5080d366679e074c1b`，84 个受管文件的内层 diff 与外层 bundle（排除已知 `package-lock.json` 噪音）逐字节一致；最近完整回归结果见本周版本记录，sandbox verifier 同时证明 launchd wrapper 健康并把插件注册 trace 绑定真实 Gateway 子进程 PID。

补丁由 `hermes-update.sh` 全自动管理：事务层由 `PATCH-UPDATE-TRANSACTION-PIN` 区分唯一一次 `--update` 和任意次 no-network `--reconcile`；Step 2/8c 以 full-index 保存 replay bundle，并在 canonical bundle/base 发布前强制完整受管集合、逐字节、cached 正向、worktree 反向和 index-clean 闭环；Step 3/4 执行 `PATCH-NPM-DEPENDENCY-HYGIENE`，Step 4b 执行 `PATCH-SKILLS-MIRROR-METADATA`，Step 7 保留已上游合并的 completion 回归 sentinel，Step 8 回放工程内 diff 并逐个验证语义 gate，Step 8d 仅在运行态脏时排空在途任务、重启 gateway 并要求 PID 替换，无变化 reconcile 不重启；Step 8e 强制回归 `PATCH-FEISHU-GROUP-SANDBOX`。若 Step 8d 后又修了运行时代码/配置，`hermes-update.md` Step 5b 要求再次执行同样的终态运行屏障并把 verifier 绑定到最终 PID。`PATCH-UPDATE-GATE-EXIT-STATUS` 保证 staged/部分 overlay、apply、sentinel、冲突、部分或空 bundle、replay integrity、runtime sync、Gateway 未实际重载或外层 verifier 任一失败都令升级非零且不得误报成功；常规更新禁止用短宽限 `stop/start` 强杀来换取新 PID。

手动恢复 `hermes-agent/` 内补丁：

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突：git apply --reject && 手动解决 .rej，再运行 hermes-update.sh --reconcile

# 若 patch 文件自身已被 conflict marker 污染，可先恢复入库版本
cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff
```

---

## 卸载

```bash
# 1. 停止并卸载 gateway 服务
hermes gateway stop
hermes gateway uninstall

# 2. 使用官方卸载命令（清理 launchd、配置等）
hermes uninstall

# 3. 手动清理（如果官方卸载不彻底）
rm -rf ~/.hermes/hermes-agent/venv  # 删除虚拟环境
rm ~/.local/bin/hermes              # 删除 symlink

# 4. 保留配置（可选）
# ~/.hermes/ 目录保留供参考；如需彻底清理：
# rm -rf ~/.hermes/

# 5. 清理 zshrc（手动删除 Hermes Completion 块）
```

---

## 基础使用

### 对话（Chat）

```bash
# 启动交互式对话
hermes

# 或显式调用 chat 子命令
hermes chat

# 继续上次会话
hermes --continue

# 继续指定名称的会话
hermes --continue "session-name"

# 恢复指定 session ID
hermes --resume SESSION_ID

# 预加载特定 Skill
hermes --skills network-diagnostics

# 跳过所有危险命令确认（谨慎使用）
hermes --yolo
```

**会话内斜杠命令**：

| 命令            | 说明                         |
| --------------- | ---------------------------- |
| `/help`         | 查看所有斜杠命令             |
| `/model`        | 切换当前会话的模型           |
| `/skill <name>` | 加载一个 Skill               |
| `/context`      | 查看当前 context 大小        |
| `/compact`      | 手动触发 context 压缩        |
| `/cron`         | 管理 Cron 定时任务           |
| `/checkpoint`   | 创建当前会话快照             |
| `/clear`        | 清空当前会话（重置 context） |

### 会话管理

```bash
hermes sessions list         # 列出所有历史会话
hermes sessions rename ID "新标题"                                # 重命名会话
hermes sessions export --session-id ID --format md session-export # 导出指定会话
hermes sessions delete ID    # 删除会话
hermes sessions prune        # 清理旧会话
```

> **说明**：`hermes sessions delete` 会删除会话索引；如果你在排查飞书 fallback / 400 级联错误这类“旧会话污染”问题，建议连同 `~/.hermes/sessions/session_<ID>.json` 一起删除，并在完成后重启 gateway。

### 模型选择

```bash
hermes model                          # 交互式选择默认 provider 和模型（TUI 选择器）
hermes config get model               # 查看当前主模型
hermes config get fallback_providers  # 查看当前 fallback 链
```

**会话内切换**：

| 命令                                               | 说明                                 |
| -------------------------------------------------- | ------------------------------------ |
| `/model`                                           | 展示当前配置允许的三条 route         |
| `/model gpt-5.5 --provider azure-foundry`          | 当前会话切回默认主模型               |
| `/model google/gemini-3.5-flash --provider vertex` | 当前会话切到配置中的 Vertex fallback |

当前启用了 `model_catalog.configured_only: true`：会话内 `/model` 只能在 `config.model + fallback_providers` 构成的集合中切换，且 `/model --global` 会被拒绝。需要改变允许集合或以后新会话的默认模型时，显式编辑配置：

```bash
hermes config edit
hermes config get model
hermes config get fallback_providers
```

修改顶层 `model` / `fallback_providers` 后重启 Gateway，使飞书等后台新会话使用新配置。旧的单项 `fallback_model` 仅用于兼容迁移，不应再作为当前配置入口：

```bash
hermes gateway restart
```

> Vertex thinking、跨 provider 工具历史与隐藏 thought 文本的当前边界见上方 [Thinking / Reasoning 配置](#thinking--reasoning-配置) 与 [Vertex Provider](#vertex-provider)。

### Skills 技能包

Skills 是 Hermes 的知识/工具扩展模块，按需加载，不常驻 context。

#### 两类 Skills

| 类型                | 存放位置               | 管理方式                                          |
| ------------------- | ---------------------- | ------------------------------------------------- |
| **Hub 官方 Skills** | `~/.hermes/skills/`    | Hermes 自动管理，每次启动时同步更新               |
| **自定义 Skills**   | `~/.hermes/my-skills/` | 手动维护，随主仓库入库，通过 `external_dirs` 加载 |

#### Hub 官方 Skills 更新机制

官方 Skills 目录 `~/.hermes/skills/` 通过两层机制与上游保持同步：

1. **运行时同步**（`hermes` 每次启动时）：自动运行 `sync_skills`，将新 skill 复制到本地、更新已变更的 skill。但此机制**只增不删**——上游移除的 skill 会作为孤儿残留在本地（显示为 `local` 而非 `builtin`）。
2. **更新时镜像**（`hermes-update.sh` Step 4b）：使用 `rsync --delete` 将 `hermes-agent/skills/` 完整镜像到 `~/.hermes/skills/`，确保新增、更新、删除三向同步。运行后 `skills/` 与上游 100% 一致，不会遗留孤儿。

自定义 skill 存放于 `~/.hermes/my-skills/`（通过 `external_dirs` 注册），不在 `skills/` 目录下，因此镜像同步**不会触及**自定义 skill。

```bash
hermes skills list                # 列出当前已安装的 builtin / local / hub skills
hermes skills install SKILL_NAME  # 从已配置 registry 安装指定 skill
hermes skills update              # 强制刷新全部 hub skills
```

#### 自定义 Skills

自定义 / Agent 生成的 skills 存放在 `~/.hermes/my-skills/`（随主仓库入库），通过 `config.yaml` 的 `external_dirs` 注册到 Hermes：

```yaml
skills:
  external_dirs:
    - ~/.hermes/my-skills
```

当前共有 18 个 local skills；以 `hermes skills list` 和 `my-skills/*/*/SKILL.md` 为权威来源：

| 分类                 | 当前 local skills                                                                                                                                                         |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| autonomous-ai-agents | `custom-skill-governance`, `hermes-agent-meta-ops`                                                                                                                        |
| creative             | `character-voices`, `vector-graphics`                                                                                                                                     |
| database             | `postgres-manager`                                                                                                                                                        |
| devops               | `network-diagnostics`, `system-hardware-diagnostics`                                                                                                                      |
| media                | `video-analysis`                                                                                                                                                          |
| productivity         | `educational-doc-writing`, `excel-processing`, `feishu-docs`, `feishu-groups`, `feishu-people-search`, `hypertex-mcp`, `technical-investor-docs`, `technical-translation` |
| red-teaming          | `agent-reconnaissance`                                                                                                                                                    |
| research             | `wiki-content-extraction`                                                                                                                                                 |

新增自定义 skill：在 `~/.hermes/my-skills/` 下创建目录，写 `SKILL.md`；随主仓库提交即可生效（无需重启）。

**调用 Skill**：会话中输入 `/skill-name` 或启动时 `hermes --skills skill-name`。

> 本地补丁对 skill 相关行为有所修改，详见 [`patches/PATCHES.md`](patches/PATCHES.md)。

### Context References（@ 语法）

在消息中直接引用外部内容，按需注入，不占用系统 prompt：

```bash
# 注入文件
@file:path/to/file.py
@file:src/main.py:10-25     # 指定行范围

# 注入目录树
@folder:src/components

# 注入 git 变更
@diff            # 未暂存的变更
@staged          # 已暂存的变更
@git:5           # 最近 5 条 commit + patch

# 注入 URL
@url:https://example.com
```

### Cron 定时任务

```bash
hermes cron list             # 列出所有定时任务
hermes cron create           # 创建新任务（交互式）
hermes cron resume JOB_ID    # 恢复任务
hermes cron pause JOB_ID     # 暂停任务
hermes cron delete JOB_ID    # 删除任务
hermes cron run JOB_ID       # 立即执行一次
```

> Cron 任务由 Gateway 服务调度，**Gateway 必须运行**才能执行定时任务。

`~/.hermes/cron/jobs.json` 是 Hermes 持续读写的 live store，不是稳定的声明式配置：除任务定义外还包含 `last_run_at`、`next_run_at`、执行状态、投递错误和 claim 等运行字段，因此本仓库将它保留在本机并通过 `.gitignore` 排除。需要迁移或备份 Cron 任务时使用 `hermes backup --quick` / `hermes backup` 和 `hermes import`，不要依赖 Git 同步该文件。

当前 `日报和晚安问候` 任务由 `scripts/nightly_greeting.py` 以 no-agent 模式执行。任务首先按中国工作日历判断：周末和法定休息日直接跳过整个流程（调休补班日照常执行），只有显式传入 `--ignore-holiday` 才会绕过；工作日固定顺序为：① 同步飞书组织架构；② 从当日 Hermes 会话提取日报素材并提交日报；③ 向 `groups.yaml` 中未关闭 `nightly_greeting` 的群发送晚安词。组织同步与后两阶段严格隔离：飞书可提供的在职人员、岗位、部门、上级等字段以最新完整快照为准，离职人员移除；aliases、称谓、背景、沟通偏好及其它飞书无法提供的自定义字段继续保留。同步成功或失败都会单独通知 sandbox 配置中的 owner 私聊；成功只报告新增/移除人员，没有人员变化时也会明确说明同步成功，失败则报告原因。同步失败不会阻断日报和晚安，也不会把同步结果注入日报素材或群发内容；通知首轮发送失败会在日报/晚安阶段后再补发，补发仍失败则将该次 cron 标为失败，不再静默记为成功。dry-run 只写新增/移除人员预览，不覆盖 `people.yaml`。

可选参数遵循固定优先级：非工作日守卫最先执行且仅 `--ignore-holiday` 可绕过；`--skip-org-sync`、`--skip-report`、`--skip-greeting` 显式关闭对应阶段，并优先于同阶段的 force 参数；`--force-report`、`--force-greeting` 只绕过当天成功标记；`--dry-run` / `--dryrun` / 位置参数 `dryrun`（或 `dry-run`）只做组织预览并将日报/晚安预览发送到主私聊，不覆盖人员文件、不提交日报、不群发；`--force-dry-run` / `--force-dryrun` 在已有当天预览标记时重新发送；`--date YYYY-MM-DD` 统一决定工作日判断、会话范围和状态键。

---

## 记忆系统与个性化

这是 Hermes "越用越懂你"的核心机制。理解它的工作方式，可以有意识地引导它向你期望的方向进化。

### 两个记忆文件

| 文件                 | 用途                                             | 字符上限                    | 对应概念              |
| -------------------- | ------------------------------------------------ | --------------------------- | --------------------- |
| `memories/MEMORY.md` | Agent 的工作笔记：环境事实、项目约定、学到的经验 | 2,200 字符（约 800 tokens） | "我记得这台机器上..." |
| `memories/USER.md`   | 用户画像：你的偏好、沟通风格、身份背景           | 1,375 字符（约 500 tokens） | "我了解这个用户..."   |

两个文件都存储在 `~/.hermes/memories/`，**每次会话开始时自动注入 system prompt**，是 Agent 在整个对话过程中始终携带的"底层认知"。

### 记忆的工作原理

```
会话开始
  └─ 从磁盘读取 MEMORY.md + USER.md
  └─ 作为"冻结快照"注入 system prompt（本次会话不再更新）

会话中途
  └─ Agent 通过 memory 工具 add/replace/remove 条目
  └─ 变更立即写入磁盘
  └─ 但本次会话的 system prompt 不受影响（下次会话才生效）

下次会话开始
  └─ 读取最新文件，看到上次写入的变更
```

**关键细节**：记忆是"冻结快照"模式——本次会话中 Agent 学到的东西，下次才能生效。这是 Hermes 为了保持 LLM prefix cache 稳定、降低成本的有意设计。

### Agent 如何主动维护记忆

Agent 会**无需你要求、自动判断**何时该更新记忆，包括：

| 触发场景       | 写入目标                 | 示例                                  |
| -------------- | ------------------------ | ------------------------------------- |
| 你表达偏好     | `USER.md`                | "我更喜欢用 poetry 而不是 pip"        |
| 你纠正它的行为 | `USER.md` 或 `MEMORY.md` | "不要帮我自动 push，每次问我"         |
| 发现环境事实   | `MEMORY.md`              | 机器的 Python 版本、项目路径          |
| 发现项目约定   | `MEMORY.md`              | 代码风格、测试命令、部署流程          |
| 完成重要任务   | `MEMORY.md`              | "2026-04-14 迁移了 OpenClaw → Hermes" |
| 遇到工具 quirk | `MEMORY.md`              | 某个 API 的特殊限制、已知 bug         |

记忆条目使用 `§` 分隔符，每条尽量紧凑（多个相关事实合为一条比分散成多条更好）。

### 你能做什么：让它越用越懂你

**✅ 主动纠正**：发现它做了你不喜欢的事，直接说出来。

```
以后帮我写代码时，函数命名用下划线而不是驼峰
以后回复我时，代码块前先说一句话解释你要做什么
```

**✅ 显式告知偏好**：不用等它猜，直接说"记住……"。

```
记住，我的数据库在 10.168.0.176，用户名是 echo_user
记住，这个项目用 pnpm，不要用 npm
```

**✅ 给反馈**：它回复太长、太短、格式不对——说出来，它会更新 USER.md。

**✅ 告诉它你的环境**：第一次使用新机器或新项目时，简单介绍一下。

```
我这台机器用 macOS + zsh，Python 用 pyenv 管理；Hermes venv 的版本按 hermes-agent/pyproject.toml 的 requires-python 选择
```

**✅ 定期检查**：记忆空间有限（2200 + 1375 字符），条目多了会被压缩合并。偶尔看一眼是否有过时内容：

```bash
cat ~/.hermes/memories/MEMORY.md
cat ~/.hermes/memories/USER.md
```

**❌ 不适合放进记忆的**：

- 大段代码、日志、数据表（太占空间，用 `@file:` 按需注入）
- 临时性的调试上下文（会话结束就不需要了）
- 网上随时可以查到的通用知识

### 容量管理

记忆容量固定，system prompt 每次都会显示使用率：

```
══════════════════════════════════════════════
MEMORY [45% — 990/2,200 chars]
══════════════════════════════════════════════
```

当使用率超过约 80%，Agent 会在添加新条目前自动合并相关条目。你也可以手动清理：

```bash
# 直接编辑文件（简单直接）
open -a TextEdit ~/.hermes/memories/MEMORY.md

# 或者在会话中告诉 Agent
"帮我清理一下 MEMORY.md，删掉已经过时的条目"
```

### Session Search：无限历史回溯

记忆文件有上限，但**所有会话历史**都永久存储在 `~/.hermes/state.db`（SQLite + FTS5 全文检索）。

Agent 可以主动搜索历史会话（使用 `session_search` 工具），用法示例：

```
你记得我们上次怎么配置那个 webhook 的吗？
上周我们讨论过 PostgreSQL 那个慢查询，帮我找一下
```

| 对比维度 | MEMORY.md / USER.md        | Session Search       |
| -------- | -------------------------- | -------------------- |
| 容量     | ~1,300 tokens（固定）      | 无限（全部历史）     |
| 速度     | 即时（已在 system prompt） | 需要搜索 + LLM 总结  |
| 适合场景 | 高频、关键、需要每次都用   | 偶尔回溯特定历史对话 |
| 管理方式 | Agent 主动维护             | 全自动，无需管理     |

### 知识库存储层级

除记忆文件外，Hermes 按用途提供其他知识存储方式：

| 类型         | 存放位置                                       | 加载时机                  | 适合内容                             |
| ------------ | ---------------------------------------------- | ------------------------- | ------------------------------------ |
| 持久记忆     | `memories/MEMORY.md` + `USER.md`               | 每次会话自动注入          | 高频偏好、环境事实                   |
| **LLM Wiki** | `~/.hermes/wiki/`（可自定义）                  | 按需检索，Agent 主动查询  | **长期知识积累、技术笔记、领域知识** |
| Skills       | `skills/<name>/` 或 `my-skills/<分类>/<name>/` | 按需调用（`/skill-name`） | 操作手册、流程文档、领域知识         |
| 项目上下文   | 项目目录下 `AGENTS.md`                         | 进入该目录时自动注入      | 项目架构、编码规范                   |
| 按需注入     | 任意路径，`@file:` / `@folder:`                | 手动在消息中触发          | 临时大文档、参考资料                 |
| 历史回溯     | `state.db`（自动）                             | Agent 主动搜索时          | 所有历史会话内容                     |

**各层的分工**：MEMORY.md 放「每次对话都用得到的高频事实」，LLM Wiki 放「需要长期积累和检索的领域知识」，Session Search 负责「翻历史记录」。三层互补，不重叠。

### LLM Wiki：本地长期知识库（推荐）

基于 [Andrej Karpathy 的 LLM Wiki 模式](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。

**核心理念**：不同于 RAG（每次从原始文档临时检索），Wiki 由 Agent 一次性编译、持续维护一套已交叉引用、去矛盾、有摘要的 Markdown 文件库。知识是**复利增长的**——每次新增内容时自动与已有知识交叉链接，越用越强。

#### 为什么适合"和 Hermes 共同成长"

- **无向量数据库**：纯 Markdown 文件，零额外依赖，本地全文检索秒级响应
- **Agent 主动维护**：Hermes 会自动把新知识归档、更新已有页面、标记矛盾、维护索引
- **你随时可读**：所有文件是普通 Markdown，用任何编辑器直接打开
- **与 Obsidian 原生兼容**：Wiki 目录本身就是 Obsidian vault，`[[wikilinks]]`、图谱视图、Dataview 插件全部可用

#### 目录结构

```
~/.hermes/wiki/
├── SCHEMA.md       # 单一权威规则：Layer、frontmatter、链接、生命周期与 lint
├── index.md        # Active Layer 2 节点注册表
├── log.md          # 结构性维护的按日合并日志
├── _living/        # Layer 1：用户维护、持续更新的私有活体文档
├── raw/            # Layer 1：带公开版本属性的外部文章、论文等原始材料
├── entities/       # Active Layer 2：实体节点
├── concepts/       # Active Layer 2：概念节点
├── comparisons/    # Active Layer 2：横向对比节点
├── queries/        # Active Layer 2：问题驱动指南
├── _archive/       # 可选：不再 active、但仍有历史价值的归档节点
└── .obsidian/      # Obsidian vault 的本地载体配置与插件
```

#### 配置

默认目录是当前 `HERMES_HOME` 下的 `wiki/`；标准安装即 `~/.hermes/wiki/`。如需自定义，在 `~/.hermes/.env` 中设置：

```bash
WIKI_PATH=/absolute/path/to/wiki
```

Feishu 群聊的沙箱当前只放行 `~/.hermes/wiki`。如果修改 `WIKI_PATH`，必须同步更新 `plugins/sandbox/config.yaml` 的 `allowed_read_roots_for_outsider_groups`；群聊查询使用 `read_file` / `search_files`，不能用 `terminal` 探测。`read_file` 需要显式文件路径；`search_files.path` 省略、为空或为 `.` 时，sandbox 会安全重写到首个允许的 wiki 根目录。

#### 基本使用

Hermes 会在你使用 `llm-wiki` 技能时自动激活该工作流。

**导入一篇文章/网页**：

```
把这篇文章整理进我的 Wiki：https://example.com/article
```

Hermes 会自动：抓取内容 → 存入 `raw/` → 创建或更新相关页面 → 补充交叉链接 → 更新 index + log。

**查询 Wiki 中的内容**：

```
根据我的 Wiki，XXX 技术和 YYY 技术有什么区别？
```

**整理一段对话/会议记录**：

```
帮我把刚才讨论的内容整理进 Wiki 的「架构决策」分类
```

**定期健康检查**（检查孤立页面、断链、过期内容）：

```
帮我 lint 一下 Wiki，看看有没有需要清理的内容
```

#### 与外部记忆 Provider 的关系

| 对比维度   | LLM Wiki                                 | 外部记忆 Provider（Hindsight 等）       |
| ---------- | ---------------------------------------- | --------------------------------------- |
| 知识来源   | **你主动喂进去**的内容（文章/论文/笔记） | **对话的副产品**，从聊天中自动提取      |
| 写入方式   | 你发指令，Agent 执行                     | 自动，无需干预                          |
| 知识边界   | 任何你想存入的外部内容                   | 仅限你和 Hermes 聊过的东西              |
| 召回方式   | Agent 检索 Markdown 文件（关键词）       | 向量语义搜索 / **知识图谱实体关系查询** |
| 可读性     | 完全透明，本地 Markdown 直接打开         | 半透明，存在 provider 内部              |
| 你的参与度 | 主动策划                                 | 被动积累                                |

> **注意**：外部 Provider（尤其是 Hindsight）也支持知识图谱和跨 session 推理合成——它不只是"记住习惯"，而是对话经历的结构化沉淀。两者本质区别在于**知识的来源和控制权**：Provider 沉淀你们对话的结晶，LLM Wiki 主动整理你策划的外部知识。同时使用是最完整的方案。

**推荐组合**：LLM Wiki（主动策划的外部知识）+ Hindsight 本地（对话沉淀的知识图谱）+ 内置 MEMORY.md（高频偏好）+ Session Search（历史回溯）。

### SOUL.md：人格与语气

**位置**：`~/.hermes/SOUL.md`

控制 Agent 的全局人格、语气和沟通风格。每次会话加载，修改后下次会话生效。

- 内容注入到 system prompt 的固定位置（slot #1）
- 仅从 `HERMES_HOME`（即 `~/.hermes/`）加载，不受项目目录影响
- 文件为空时等于使用默认人格

**修改建议**：在默认文本末尾追加个性化要求，而不是替换整段，避免丢失内置安全指令。

### 外部记忆 Provider（进阶）

Hermes 提供 8 个外部记忆 provider 插件，运行在内置 MEMORY.md / USER.md **之上**（不替换），提供知识图谱、语义搜索、自动事实提取等能力。同时只能激活一个外部 provider。

```bash
hermes memory setup      # 交互式选择并配置 provider
hermes memory status     # 查看当前状态
hermes memory off        # 禁用外部 provider
```

#### Provider 横向对比与推荐

> 评分维度：免费程度 · 存储效果 · 召回效率 · 容量 · 中文友好 · 技术工作者适配

| Provider        | 托管            | 费用                 | 中文  | 主要特色                                                                               | 推荐星级   |
| --------------- | --------------- | -------------------- | ----- | -------------------------------------------------------------------------------------- | ---------- |
| **Hindsight**   | 本地 / 云端     | 本地免费，云端付费   | ★★★   | 知识图谱 + 实体关系 + `hindsight_reflect` 跨记忆推理合成；自动保留对话；多策略检索     | ⭐⭐⭐⭐⭐ |
| **OpenViking**  | 自托管          | 免费 (AGPL-3.0)      | ★★★★★ | 字节跳动出品，CJK 支持最佳；文件系统层级浏览；分层检索（摘要→概览→全文）；6 类自动提取 | ⭐⭐⭐⭐   |
| **ByteRover**   | 本地 / 可选云   | 本地免费             | ★★★   | 压缩前预提取（防止有价值上下文被压缩丢弃）；层级知识树；CLI 工具链，开发者友好         | ⭐⭐⭐     |
| **Holographic** | 本地 SQLite     | 完全免费             | ★★★   | 零外部依赖；HRR 代数实体查询；矛盾检测；信任评分机制                                   | ⭐⭐⭐     |
| **Honcho**      | 云端 / 可自托管 | 云端付费，自托管免费 | ★★    | 辩证式用户建模；跨 session 上下文对齐；多 profile 支持                                 | ⭐⭐⭐     |
| **Mem0**        | 云端            | 付费                 | ★★★   | 全自动 LLM 事实提取；语义搜索 + 重排序；自动去重                                       | ⭐⭐       |
| **Supermemory** | 云端            | 付费                 | ★★★   | 图谱级 session 摄入；多容器隔离；context fencing 防递归污染                            | ⭐⭐       |
| **RetainDB**    | 云端            | $20/月               | ★★    | 混合检索（向量 + BM25 + 重排序）；Delta 压缩；7 种记忆类型                             | ⭐⭐       |

**推荐理由**

- ⭐⭐⭐⭐⭐ **Hindsight（本地模式）**：免费，知识图谱 + 实体关系 + `hindsight_reflect` 跨记忆推理是同类中的独有能力，自动保留每次对话，多策略检索。适合技术工作者长期积累结构化知识。本地模式需要一个 LLM API key 用于提取（Gemini/OpenRouter 均可）。

  ```bash
  hermes memory setup    # 选择 "hindsight" → 选择 "local"
  ```

- ⭐⭐⭐⭐ **OpenViking**：字节跳动开源产品，对中文内容的自然语言理解最优；分层检索节省 token；6 类自动分类（偏好、实体、事件、案例、模式等）结构化程度高；文件系统式浏览直观。需要在本地持续运行 server 进程。

  ```bash
  pip install openviking
  openviking-server          # 持续运行，建议设为 LaunchAgent 开机自启
  hermes memory setup        # 选择 "openviking"
  ```

- ⭐⭐⭐ **ByteRover**：开发者友好 CLI，本地免费；压缩前预提取特性可防止有价值的上下文在 context 压缩时丢失，适合长对话密集的技术工作者。

- ⭐⭐⭐ **Holographic**：零依赖，最简单的本地选项；HRR 代数矛盾检测独特，但不支持语义搜索（仅 FTS5 关键词），适合轻量使用。

> **个人建议**：日常先用内置记忆 + Session Search；想要更深的知识积累时，优先尝试 **Hindsight 本地模式**；若中文知识管理需求较高，选 **OpenViking**。

---

## Web Search 工具

Hermes 的 `web_search` / `web_extract` 工具（`web` toolset）支持 4 个后端 provider，通过 `.env` 中的对应 API key 自动激活。

**当前配置**：`config.yaml` 中已明确指定 `web.backend: tavily`，Hermes 直接使用 Tavily，不走自动检测逻辑。

**自动检测优先级**（未指定 `web.backend` 时，存在多个 key 取第一个）：
`Firecrawl` → `Parallel` → `Tavily` → `Exa`

> 切换 provider：修改 `config.yaml` 中的 `web.backend` 值（`tavily` / `exa` / `firecrawl` / `parallel`），或删除该行改回自动检测模式（注释掉不用的 key）。

```bash
# 查看当前 web search 工具状态
hermes doctor

# 会话内查看/切换 toolset
/tools list
/tools enable web

# 查看可用 toolset 及工具列表
hermes tools
```

#### Web Search Provider 横向对比与推荐

> 评分维度：免费额度 · 定期刷新 · 中文搜索质量 · 技术内容深度 · 速度

| Provider      | 环境变量            | 免费额度                        | 定期刷新    | 付费价格          | 中文支持 | 技术内容 | 推荐星级   |
| ------------- | ------------------- | ------------------------------- | ----------- | ----------------- | -------- | -------- | ---------- |
| **Tavily**    | `TAVILY_API_KEY`    | 1,000 次/月                     | ✅ 每月刷新 | $0.008/次（按量） | ★★★★     | ★★★★     | ⭐⭐⭐⭐⭐ |
| **Parallel**  | `PARALLEL_API_KEY`  | 16,000 次（一次性）             | ❌ 用完付费 | $0.005/10 条结果  | ★★★      | ★★★★★    | ⭐⭐⭐⭐   |
| **Exa**       | `EXA_API_KEY`       | 创业/教育 $1,000 赠金（一次性） | ❌ 一次性   | $7/1k 次          | ★★★      | ★★★★★    | ⭐⭐⭐⭐   |
| **Firecrawl** | `FIRECRAWL_API_KEY` | 500 次（一次性）                | ❌ 用完付费 | $16/月起          | ★★★★     | ★★★      | ⭐⭐⭐     |

**推荐理由**

- ⭐⭐⭐⭐⭐ **Tavily**：唯一提供**每月定期刷新**免费额度（1,000 次/月）的方案，无需信用卡即可申请，专为 RAG/AI Agent 优化，延迟低，中文内容召回质量不错。对个人用户来说是最稳定的"零成本"选择。

  注册：[app.tavily.com](https://app.tavily.com)

- ⭐⭐⭐⭐ **Parallel**：16,000 次一次性免费额度（AI 原生搜索 API，专为 agent tool call 设计），SOC2 认证，延迟 < 5 秒，技术内容质量高。注册后相当于可以白嫖很长时间，适合密集使用期间消耗。

  注册：[parallel.ai](https://www.parallel.ai)

- ⭐⭐⭐⭐ **Exa**：技术内容质量最高（专门索引 GitHub、学术论文、Stack Overflow、技术文档），延迟 180ms～1s（最快），有创业/教育计划可免费领取 $1,000 赠金。日常无每月免费额度，但付费后性价比高（$7/1k 次）。适合有技术文档/代码搜索需求时使用。

  注册：[exa.ai](https://exa.ai)，申请赠金：[exa.ai/startup-grants](https://exa.ai/startup-grants)

- ⭐⭐⭐ **Firecrawl**：强项在**网页内容提取**（PDF/URL → Markdown）而非搜索本身；500 次一次性免费额度用完需付费（$16/月起），不适合作为主力搜索 provider。

> **推荐策略**：先配置 Tavily（每月 1,000 次免费）作为保底，再申请 Exa 赠金。需要切换时修改 `config.yaml` 的 `web.backend` 字段，无需改动 `.env`（保留多个 key 均可）。

---

## Web Dashboard

Hermes 内置本地 Web 控制台，运行在 `http://127.0.0.1:9119`，提供可视化配置、会话浏览、日志查看等功能。

### 启动

> **前置条件**：需安装 `web` extra（`fastapi` + `uvicorn`），见 [可选依赖](#可选依赖optional-extras)。`hermes update` 会尝试安装 `.[all]`（含 web），一般无需手动处理；如果 `.[all]` 安装失败回退到逐个 extra，且 `web` 也失败，需手动执行：
>
> ```bash
> cd ~/.hermes/hermes-agent && source venv/bin/activate && uv pip install -e ".[web]"
> ```

```bash
# 直接启动（推荐）
hermes dashboard

# 不自动打开浏览器
hermes dashboard --no-open

# 自定义端口
hermes dashboard --port 8080
```

> **首次启动**会自动构建前端（需要 `npm`），约需 10–20 秒；上游 `_web_ui_build_needed()`（commit `5b5a53a1`）会基于 `hermes_cli/web_dist/.vite/manifest.json` sentinel + 源码 mtime 判断是否需要重建，已构建且未过期时跳过 `npm install` 与 Vite build（替代了已退役的 PATCH-DASHBOARD-BUILD-CACHE）。`hermes update` 每次更新都会触发 `npm ci` 重新构建。

### 功能页面

| 页面      | 功能                                                   |
| --------- | ------------------------------------------------------ |
| Status    | Gateway 状态、活跃 session 数、版本信息（5s 自动刷新） |
| Config    | 可视化编辑 `config.yaml`，支持导入/导出                |
| API Keys  | 管理 `.env` 中的密钥，按类别分组（LLM / 工具 / 平台）  |
| Sessions  | 浏览/搜索会话历史，查看消息详情，删除会话              |
| Logs      | 实时日志，支持按级别/组件过滤                          |
| Analytics | Token 用量与费用统计图表                               |
| Cron      | 定时任务管理（增删改查 + 立即触发）                    |
| Skills    | 技能启用/禁用                                          |

### ⚠️ Dashboard 不是持久化服务

**Dashboard 是按需启动的工具进程，不会随系统开机或 gateway 启动自动运行。** 设计上如此，原因：

- Dashboard 可读写 `.env`（含所有 API key），长期暴露在端口上存在安全风险
- 日常运营只需 gateway 常驻，dashboard 按需打开即可
- 如确实需要持久化，可参考 gateway 的 launchd 方案自行封装（不推荐）

用完关闭浏览器标签后，进程仍在后台运行；若要彻底停止：

```bash
lsof -ti :9119 | xargs kill
```

### REST API

Dashboard 同时暴露 REST API，可用于自动化：

```bash
# 查看 gateway 状态
curl http://127.0.0.1:9119/api/status

# 列出最近 session
curl http://127.0.0.1:9119/api/sessions

# 查看日志（最近 50 行）
curl "http://127.0.0.1:9119/api/logs?file=gateway&lines=50"
```

---

## 维护与排错

### 健康检查

```bash
hermes doctor          # 检查所有组件状态
hermes doctor --fix    # 自动修复可修复的问题
hermes status          # 快速状态概览
hermes dump            # 输出完整诊断信息（提交 bug 用）
```

### 常见问题

**飞书 WebSocket 断连**：

```bash
hermes gateway restart
hermes gateway status
```

**Gateway 拒绝所有消息（日志出现 `unauthorized user`）**：

确认 `.env` 中的 `FEISHU_ALLOWED_USERS` 包含实际发送者 ID；如果确实要开放所有用户，清空平台白名单并设置 `GATEWAY_ALLOW_ALL_USERS=true`，然后重启 gateway。

**会话出现 400 级联错误**：

通常表现为旧上下文被污染，或某个异常 session 反复触发后续问题。推荐按“索引 + transcript + gateway”三段式清理：

```bash
hermes sessions list
hermes sessions delete --yes SESSION_ID
rm -f ~/.hermes/sessions/session_SESSION_ID.json
hermes gateway restart
```

清理后，建议在飞书里**新开一个线程**，或至少先发一次 `/new` 再继续。

**批量清理全部旧 Feishu session（谨慎使用）**：

适合排查“新会话也疑似继承旧问题”的场景。下面这段会同时清理：

- `state.db` 里的 Feishu session 索引
- `~/.hermes/sessions/` 里的 Feishu transcript JSON
- 最后重启 gateway，清空进程内会话映射

```bash
cd ~/.hermes
python3 - <<'PY'
import glob
import json
import os
import sqlite3
import subprocess

ids = set()

conn = sqlite3.connect("state.db")
cur = conn.cursor()
try:
    ids.update(
        row[0]
        for row in cur.execute("SELECT id FROM sessions WHERE source = 'feishu'")
        if row and row[0]
    )
finally:
    conn.close()

for path in glob.glob("sessions/session_*.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        continue
    if data.get("platform") == "feishu":
        session_id = data.get("session_id")
        if session_id:
            ids.add(session_id)
        os.remove(path)

for session_id in sorted(ids):
    subprocess.run(
        ["hermes", "sessions", "delete", "--yes", session_id],
        check=False,
    )
PY
hermes gateway restart
```

如果做完这套清理后，**新 Feishu 会话仍然 fallback**，那就基本可以判断：问题不在旧 session，而在当前版本的模型调用链路本身。

**Skills Hub 初始化**：

```bash
hermes skills list   # 首次运行会初始化 Skills Hub 目录
```

**查看实时日志**：

```bash
hermes logs
tail -f ~/.hermes/logs/gateway.log
tail -f ~/.hermes/logs/agent.log
```

### 备份与恢复

```bash
# 备份整个 hermes home（含配置、会话、skills）
hermes backup
# 输出：~/.hermes/hermes_backup_YYYYMMDD_HHMMSS.zip

# 恢复
hermes import hermes_backup_YYYYMMDD_HHMMSS.zip
```

---

## 版本记录

> 版本记录按 ISO 自然周（周一至周日）聚合，每周最多一条。版本与日期取该周最后一次升级，说明汇总周内 upstream 范围、PATCH 生命周期事件、最终验证和重大摩擦；所有剩余告警按 P0 主链路阻断、P1 本地可修、P2 上游阻挡非主链路、P3 可选缺口分级后写入。同周后续升级更新既有 row，不新增 row。

| 版本               | 日期       | 周摘要                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| v0.20.1            | 2026-08-18 | **2026-W34**：upstream 保持 `8ad055414`，本周做本地语义 PATCH 收敛。新增 `PATCH-MCP-TASKS-ASYNC-HANDOFF`：Hermes 通用协商 `io.modelcontextprotocol/tasks`，按 server capability 注册 `tasks_get/update/cancel`，标准 task handle 在 tool result 持久化后直接生成确定性回执并结束 turn，不再等第二次 LLM；HyperTeX owner-DM sandbox 同步收缩到 3 个原始工具 + 标准 Tasks utilities，附件仍经 0700 私有暂存目录注入。PATCH 终态 **38 活跃 / 31 工程内**，受管集合 **84 files / 38 tests**；同轮修复 replay 对 upstream 不存在或 ignored managed-new 文件的 81/84 误判，改用临时 index 产生完整 full-index bundle。规范回归 **38 files / 1342 passed / 0 failed / 3 skipped**，sandbox **36 passed**，Step 8b/8e、bundle/base、cached 正向、worktree 反向、index-clean 全绿。配置仍为 v37，Gateway 受 launchd 监管；剩余 6 high 均为 Electron/postcss/nanoid 上游 lock/range 阻挡的 Desktop/Web build-chain P2，不影响飞书主链路，未使用 `--force`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| v0.20.1            | 2026-08-16 | **2026-W33**：upstream `cd9fbf9f1 → 8ad055414`（周内 +1805 commits）。主线：周初完成 CVE、v34 personality、Gateway route/session、Browser Use、provider/compression 与 Desktop 收敛；随后补齐 `/model`/resume、secrets redaction、Slack streaming、updater 事务/排空和组织同步。本轮新增 compression `tail_mode`、digest/anchor/watermark 与并发 tail 修复，Gateway finalize 离主循环、durable row id、Codex/Claude session import/resume、terminal breadcrumbs，hooks `modify`、computer-use 授权、MCP OAuth DCR secret 和 Desktop Skills/session UI 继续演进。PATCH：周内 **+9 / 2 归档 / 0 收缩**，终态 **37 活跃**；新增 launchd supervisor、ambient credential isolation、configured-only model、三档图片 native、通用音视频/PDF sidecar、附件 path-free/显式失败、群聊 sandbox provenance/mutation/artifact grant，以及 `PATCH-DOCTOR-TEST-NETWORK-ISOLATION`。本轮 74-file bundle clean apply，upstream 仅与 5 个受管文件正交重叠，既有 PATCH **0 吸收 / 0 归档 / 0 收缩**；doctor 单测由 >300s flake 降到 13.7s。最终 **34 files / 1219 passed / 0 failed / 3 skipped**、sandbox **32 passed**，full-index/cached/reverse/index-clean 全绿。配置链保持 `azure-foundry/gpt-5.5 → bedrock/Claude Opus 5 → vertex/google/gemini-3.5-flash`，compression 仍用 Vertex、统一 cap 700k，并显式 `tail_mode: legacy` 保持既有 tail 语义；v37 无迁移。首次 HTTPS acquisition 失败后按 pending-transaction recovery 走进程级 SSH 443 rewrite 固定 `8ad055414`，remote 未改、临时 prompt 文件已清理。官方更新 16 个 bundled skills；npm 仍 6 high，均为 Desktop/web build 链 P2，不影响飞书主链路，禁止 `--force`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| v0.20.0            | 2026-08-08 | **2026-W32**：upstream `26e0b1c → cd9fbf9f1`（周内 +1087 commits，中继 `863e3131`；主线：secrets/profile scope、排空重启、Gateway SSE/Relay 生命周期与 turn-lease/unclean-exit 恢复、State/SQLite/CJK、模型与 tool observability、Desktop session/tab 与 file/tool/skill 性能、anydoc 文档抽取扩展与 bytes 边界抽取 + 扫描版 PDF 覆盖率警告、terminal/ACP 结果脱敏与自仓 git 变更硬拦、doctor DB 健康统计与 `--live` 探针、`hermes pause/resume` 急停）。PATCH 生命周期：周中新增 `PATCH-UPDATE-GIT-FETCH-RETRY`、`PATCH-FEISHU-MISSED-EVENT-BACKFILL`、`PATCH-UPDATE-TRANSACTION-PIN`（一次升级固定一个 upstream snapshot；失败 0600 持久化、仅 exit 0 清除），活跃 28 → 30、无归档；`PATCH-DOCUMENT-EXTRACTION` 经 `b2598b41e` 部分吸收 anydoc-only，08-08 复核上游新增 bytes API/覆盖率警告与本地 hunk 正交并存；`PATCH-NPM-DEPENDENCY-HYGIENE` 的 install-script policy 片段经上游 `package.json.allowScripts` 吸收而退役（本机 npm 11→12 暴露覆盖关系），audit-fix 片段保留。08-07 逐补丁全量审计：修复图片/视频路由 `kind=` 接线断裂、视频 buffer 每轮重置、群审批硬拦重排为三入口早期硬地板（+ContextVar chat_type 防 fail-open）、vertex 别名铸主凭据、backfill 开机窗节流等生产缺陷，并收紧十余处闸门判别力与脚本演进项；受管文件 62 → 64，新增回归 12 条。08-08 将主会话 DM 回放并入 `PATCH-FEISHU-MISSED-EVENT-BACKFILL`：修复 `oc_` 前缀误判 chat_type 的盲区，`get_chat_info` 补采 `chat_mode`（实测 DM=`p2p`）、失败 fail-closed 按群准入，DM quote 覆盖去重自动继承，新增 3 条 DM 回归。真实冲突：08-06 轮 Feishu lazy SDK import 与 approval 增量按既定融合原则处理；08-08 轮仅 `read_extract.py` import 块/函数插入点两处并存型，两侧全保留。周末终态：26 files **847 passed / 0 failed**（+15 为上游 test_read_extract 扩展），bundle/base/full-index 正反向与 index-clean 闭环全绿，gateway 排空重启至 PID 68781、sandbox verifier 21 passed 绑定终态 PID；清除 08-06 官方 updater 遗留 autostash（可恢复 `e2919ebad`）。摩擦：npm audit 残余 8 advisories（Browser 2H、Web 3H 含新增 Mermaid CSS-injection、UI-TUI 1H1M）属 P2 上游 lock/range 阻挡、不影响飞书主链路，禁止 `--force`；Skills mirror 字节码缓存噪音已入排除集，本周仅余 llm-wiki 固定振荡；裸补丁窗口 doctor 出现 vendor-slug 对 vertex 的一次性误报，回贴后消失。 |
| v0.19.1            | 2026-08-02 | **2026-W31**：upstream `eb527605 → 26e0b1c`（+2148 commits），周内发布 v0.19.1 / `v2026.7.30`；Gateway/session、Voice/STT、Desktop/Photon、模型观测和安全工具继续演进，`PATCH-LAZY-ACTIVATION` 经裸 upstream 验证完全吸收并归档。solvepatch 中断后接管遗漏 import，随后 `41a07f5b → 26e0b1c`（+971）再次 3-way 解冲突并修复 5 个测试失败。收尾审计新增 full-index bundle、gate 非零退出、Skills metadata 保留 3 个运行时 PATCH，终态 60 files clean apply、27 个活跃 PATCH、23 files **793 passed / 0 failed**、七层闭环与 sandbox verifier 全绿；19 个 active backend 全 current，npm audit **0 vulnerabilities**。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| v0.19.0            | 2026-07-26 | **2026-W30**：upstream `c48d5341 → eb527605`（+1913 commits），跨入 v0.19.0。上游集中推进 State/SQLite、Gateway、Vertex/Gemini、SSRF、安全、Desktop、Skills 与压缩；Feishu Markdown 冲突按语义重解。本周新增/收敛 `PATCH-VERTEX-IMAGE-ROUTING`、`PATCH-VERTEX-VIDEO-ROUTING`、`PATCH-APPROVAL-DARWIN-TMP`、`PATCH-FTS5-CJK-DARWIN`，并演进 `PATCH-FEISHU-MARKDOWN`。E-949 runtime repair 曾重建 venv，缺失 lazy/dev 依赖已全部自愈；周末 60 files clean apply，23 files **1909 passed / 0 failed**。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| v0.18.2            | 2026-07-18 | **2026-W29**：upstream `7acaff5e → c48d5341`（+942 commits）。上游重点为 multiplex profile、State/SQLite、Cron、Compaction、Codex/MCP、Desktop 与安全。真实冲突集中在 `gateway/run.py`、`gateway/session.py`、`hermes_cli/doctor.py` 和 session tests，均按“上游增强 + 本地不变量并存”解决；59 files clean apply，无 PATCH 吸收或归档。周末回归 **1767 passed / 1 failed**，唯一失败为后来由 `PATCH-APPROVAL-DARWIN-TMP` 修复的裸 upstream Darwin realpath bug。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| v0.18.2            | 2026-07-11 | **2026-W28**：upstream `95fc3c6b → 7acaff5e`（+642 commits），周内 v0.18.0 → v0.18.2。新增 `PATCH-VERTEX-FALLBACK`，修正 `PATCH-VERTEX-HIDDEN-THOUGHTS`；补齐 `PATCH-PLATFORM-CAPABILITY-SCOPE` / `PATCH-FEISHU-GROUP-APPROVAL` 执行链，并新增 `PATCH-LAZY-ACTIVATION`、扩展 `PATCH-NPM-DEPENDENCY-HYGIENE`。Feishu SDK、skill create 和测试锚点漂移均已适配，终态 50 files clean apply、**1653 passed**，Doctor 与 sandbox verifier 全绿。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| v0.18.0            | 2026-07-05 | **2026-W27**：upstream `7cfa2fa1 → 95fc3c6b`（+1069 commits），升级到 v0.18.0。上游吸收 `PATCH-DOCTOR-ENABLED-TOOLSETS` 后裸 upstream 举证并归档；新增 `PATCH-VERTEX-DOCTOR`，演进 `PATCH-LOCAL-PROFILES` 与 Feishu Markdown。四文件大跨度冲突及随后 `gateway/run.py` caller-threading 冲突均按语义合并，最终 bundle 可正向回放、反向描述现状，定向回归 **1062 passed**。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| v0.17.0            | 2026-06-28 | **2026-W26**：upstream 从 `1b7b4d13` 连续推进到 `6f1a176b`。集中建立 Feishu 本地能力栈：新增 `PATCH-FEISHU-GROUP-ADMISSION`、`PATCH-FEISHU-GROUP-SCOPE`、`PATCH-FEISHU-NORMAL-REPLY`、`PATCH-FEISHU-FINAL-ONLY`、`PATCH-LOCAL-PROFILES`、`PATCH-FEISHU-RESOURCE-ACCESS`、`PATCH-DOCUMENT-EXTRACTION` 与 `PATCH-FEISHU-MARKDOWN`。插件适配、附件回填、文档抽取和 Markdown 渲染均完成脚本/注册表/bundle 同步，周末定向回归 **321 passed**。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| v0.17.0            | 2026-06-20 | **2026-W25**：upstream `d62979a6 → 1b7b4d13`，周内 v0.16.0 → v0.17.0。上游引入 Relay、Desktop、Skills、Memory、TUI/MCP 等大改；Feishu 从内置平台迁移到插件 adapter，本地 hunk 按新路径重映射。`PATCH-DASHBOARD-BUILD-CACHE`、`PATCH-DELEGATE-ACP-ROUTING` 继续由上游实现和 sentinel 监管；uv fallback 自愈，package-lock 漂移维持 bundle 外，Gateway 恢复加载 patch。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| v0.16.0            | 2026-06-12 | **2026-W24**：upstream `a6b6afdff → d62979a6`。跨入 v0.16.0，上游集中推进 Desktop、Dashboard、packaging、memory、provider 与安全；`PATCH-SKILL-CREATE-ROOT` 随 skill-manager 重构完成 rebase，`PATCH-DOCTOR-ENABLED-TOOLSETS` 继续保留。uv Python 路径 fallback 自愈，launchd 启动兼容问题在新基线上收敛。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| v0.15.1            | 2026-06-03 | **2026-W23**：upstream `b288de8bf → a6b6afdff`。升级到 v0.15.1，适配工具、Gateway、Desktop 与 provider 变化；新增 `PATCH-OPENCLAW-TOKEN-MIGRATION`，阻止迁移器写入已废弃的 gateway token。补丁 clean apply，依赖与 Gateway 恢复完成。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| v0.14.0            | 2026-05-25 | **2026-W22**：upstream `3bace071b → b288de8bf`。持续跟进 v0.14.0 的 Gateway、Skills、TUI 与工具演进，补丁回放与依赖恢复正常；Zsh completion 继续由生成后修复/回归 sentinel 管理。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| v0.14.0            | 2026-05-24 | **2026-W21**：周内连续跟进 v0.14.0，最终到 `3bace071b`。建立 `PATCH-FEISHU-SOCKS-DEPENDENCY`，并让 `PATCH-SKILL-CREATE-ROOT` 在 external skill root 下正确创建/删除；Zsh completion 语法进入持续回归监管。补丁经 3-way/clean apply 收敛，sandbox 用户插件边界同步成形。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| v0.13.0            | 2026-05-14 | **2026-W20**：升级到 v0.13.0；针对 uv/pyenv 环境增加升级 fallback，Feishu SOCKS 依赖完成声明与恢复，sandbox 插件通过官方 hooks 建立 owner DM 与其他会话的工具隔离。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| v0.13.0            | 2026-05-10 | **2026-W19**：周内 v0.12.0 → v0.13.0。上游吸收 Zsh completion 语法修复，`PATCH-ZSH-COMPLETION-SYNTAX` 移入 Archive 并保留生成输出 sentinel；其余补丁随上游完成 3-way 回放。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| v0.11.0            | 2026-04-23 | **2026-W17**：周内 v0.10.0 → v0.11.0。上游先引入 hooks/plugins/orchestrator，再加入 Ink TUI、transport、Bedrock、GPT-5.5 与 Dashboard 主题扩展；本地升级流程开始围绕插件与补丁回放演进。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| v0.9.0 (2026.4.13) | 2026-04-14 | **2026-W16**：初始安装，从 OpenClaw 迁移，建立后续 upstream 升级与本地 patch 持久化的起点。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
