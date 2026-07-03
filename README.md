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
| `cron/jobs.json`             | Cron 任务定义（入库；运行输出和锁文件不入库）            |
| `patches/local-patches.diff` | hermes-agent 本地补丁 diff（更新时自动重新应用）         |
| `patches/PATCHES.md`         | 本地补丁详细记录（问题 / 根因 / 修复方案）               |
| `hermes-update.sh`           | 一键更新脚本（入库，随版本变更同步维护）                 |
| `scripts/`                   | Vertex token 刷新、Logi watchdog 等 LaunchAgent 助手脚本 |
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
├── scripts/               # Vertex token 刷新 / Logi watchdog 等 LaunchAgent 助手脚本（入库）
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
│   └── jobs.json          # Cron 任务定义（入库；output/lock/ticker 运行时文件忽略）
├── logs/                  # 日志（.gitignore 排除）
├── sessions/              # 会话历史（.gitignore 排除）
└── state.db               # 内部状态数据库（.gitignore 排除）
```

---

## 安装

### 前置条件

| 依赖   | 版本要求                                                                          | 安装方式                                           |
| ------ | --------------------------------------------------------------------------------- | -------------------------------------------------- |
| Python | 以 `hermes-agent/pyproject.toml` 的 `requires-python` 为准（当前上游为 `>=3.11`） | `pyenv` 或 Homebrew Python                         |
| uv     | 最新                                                                              | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| git    | 任意                                                                              | macOS 自带                                         |

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

| Extra             | 功能                                 | 主要依赖包                                                                                    | 说明                                                                      |
| ----------------- | ------------------------------------ | --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **feishu**        | 飞书 IM 集成（WebSocket 长连接）     | `lark-oapi`, `qrcode`, `python-socks`                                                         | **当前已安装** ✅ 。代理网络环境需 `python-socks`（PATCH-7）              |
| **cron**          | Cron 定时任务调度                    | `croniter`                                                                                    | Gateway 使用，不装则 `hermes cron` 不可用                                 |
| **messaging**     | Telegram + Discord + Slack + 飞书 QR | `python-telegram-bot`, `discord.py`, `aiohttp`, `slack-bolt`, `slack-sdk`, `qrcode`           | 全平台 IM 一把梭；若只用飞书可单独装 `feishu`                             |
| **slack**         | Slack 集成                           | `slack-bolt`, `slack-sdk`                                                                     | `messaging` 的子集                                                        |
| **matrix**        | Matrix 协议集成                      | `mautrix[encryption]`, `Markdown`, `aiosqlite`, `asyncpg`                                     | ⚠️ macOS 上 `python-olm` 构建可能失败                                     |
| **voice**         | 本地语音输入（STT）                  | `faster-whisper`, `sounddevice`, `numpy`                                                      | 需要麦克风权限；包含 `ctranslate2` 等重型依赖                             |
| **tts-premium**   | 高级语音合成（ElevenLabs）           | `elevenlabs`                                                                                  | 需 ElevenLabs API key；基础 TTS（Edge TTS）已在 base 中                   |
| **mcp**           | Model Context Protocol 支持          | `mcp`                                                                                         | 外部工具/数据源接入标准                                                   |
| **acp**           | Agent Client Protocol                | `agent-client-protocol`                                                                       | Agent 间委托通信协议                                                      |
| **cli**           | 交互式 TUI 选择器                    | `simple-term-menu`                                                                            | `hermes model` 等 TUI 选择器依赖                                          |
| **pty**           | 伪终端支持                           | `ptyprocess` (macOS/Linux) / `pywinpty` (Windows)                                             | 终端工具增强                                                              |
| **honcho**        | Honcho 外部记忆 Provider             | `honcho-ai`                                                                                   | 需配合 `hermes memory setup` 使用                                         |
| **modal**         | Modal 云端执行                       | `modal`                                                                                       | 远程沙箱执行                                                              |
| **daytona**       | Daytona 开发环境                     | `daytona`                                                                                     | 远程开发环境集成                                                          |
| **mistral**       | Mistral AI Provider                  | `mistralai`                                                                                   | 使用 Mistral 模型时需要                                                   |
| **bedrock**       | AWS Bedrock Provider                 | `boto3`                                                                                       | 使用 AWS 托管模型时需要                                                   |
| **dingtalk**      | 钉钉 IM 集成                         | `dingtalk-stream`, `alibabacloud-dingtalk`, `qrcode`                                          | 钉钉企业应用                                                              |
| **web**           | Web Dashboard + REST API             | `fastapi`, `uvicorn[standard]`                                                                | **当前已安装** ✅ 。`hermes dashboard` 命令依赖                           |
| **homeassistant** | Home Assistant 集成                  | `aiohttp`                                                                                     | 智能家居控制                                                              |
| **sms**           | SMS 消息支持                         | `aiohttp`                                                                                     | 短信通知                                                                  |
| **dev**           | 开发/测试工具                        | `debugpy`, `pytest`, `pytest-asyncio`, `pytest-xdist`, `mcp`                                  | 贡献代码或调试时使用                                                      |
| **termux**        | Android Termux 平台                  | Telegram + cron + cli + pty + mcp + honcho + acp                                              | 专为 Termux 环境裁剪，排除不兼容的 voice                                  |
| **rl**            | 强化学习实验                         | `atroposlib`, `tinker`, `fastapi`, `wandb`                                                    | 研究用途                                                                  |
| **yc-bench**      | YC Bench 评测                        | `yc-bench`                                                                                    | 需要 Python ≥ 3.12                                                        |
| **all**           | 上游 broad install 组合              | `cron`, `cli`, `dev`, `pty`, `mcp`, `homeassistant`, `sms`, `acp`, `google`, `web`, `youtube` | 当前不包含 Feishu、Telegram/Discord/Slack、voice、bedrock 等 lazy backend |

#### 当前环境已安装的 Extras

```
.[all,feishu]    ✅  ← 本次迁移恢复使用的安装组合
feishu           ✅  ← 飞书 WebSocket + SOCKS 代理（PATCH-7 覆盖 extra + lazy deps）
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
> 2. `BAILIAN_API_KEY=${BAILIAN_API_KEY}` — 自循环引用，需替换为实际 key 值（注：当前配置已改用内置 `alibaba` provider，`BAILIAN_API_KEY` 不再需要，仅迁移时需注意）

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

如果启用了 Vertex token 自动刷新，也要卸载对应的 LaunchAgent，避免旧机继续刷新 token 或自动重启 gateway：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist 2>/dev/null || true
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist 2>/dev/null || true
rm -f ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist \
      ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist
```

确认旧机已经没有 Hermes 相关进程：

```bash
launchctl list | grep -Ei 'hermes|vertex|feishu|gateway' || true
ps -axo pid=,ppid=,stat=,command= | grep -Ei 'hermes|vertex_wake|feishu|gateway|bot_feishu' | grep -v grep || true
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

如果使用官方 Vertex Provider，先确认 `.env` 里有服务账号 JSON 路径，且 `config.yaml` 使用 `provider: vertex`：

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
launchctl list | grep -Ei 'hermes|vertex'
```

官方 `provider: vertex` 会在 Hermes 进程内自动 mint/refresh OAuth token，不需要安装 Vertex token 自动刷新 / wake 后补刷 LaunchAgent。只有回滚到旧 `custom + VERTEX_ACCESS_TOKEN` 方案时，才运行 `~/.hermes/scripts/install_vertex_refresh_launchd`。

迁移完成后，旧机应保持 gateway 与 Vertex LaunchAgent 卸载状态；如果只是临时切换机器，回切前也按同样流程先停掉当前机器，再启动另一台。

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

| Provider                | 环境变量                                                     | 说明                                                                          |
| ----------------------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| Vertex Gemini（主模型） | `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_CREDENTIALS_PATH` | 官方 `vertex` provider 用 service account/ADC 自动 mint + refresh OAuth token |
| Gemini（可选直连）      | `GEMINI_API_KEY` / `GOOGLE_API_KEY`                          | 仅在切回内置 `gemini` provider 时使用                                         |
| Qwen（备用模型）        | `DASHSCOPE_API_KEY`                                          | 内置 `alibaba` provider 直接读取                                              |
| DashScope 国内端点      | `DASHSCOPE_BASE_URL`                                         | `https://dashscope.aliyuncs.com/compatible-mode/v1`                           |
| 飞书                    | `FEISHU_APP_ID` / `FEISHU_APP_SECRET`                        | 飞书开放平台获取                                                              |
| 飞书推送频道            | `FEISHU_HOME_CHANNEL`                                        | cron / 通知默认投递的群或会话 ID                                              |
| Gateway 访问控制        | `FEISHU_ALLOWED_USERS` / `GATEWAY_ALLOW_ALL_USERS=false`     | 默认使用飞书白名单；仅明确开放时才设为 `true`                                 |

**当前主模型的加载机制：**

当前配置使用 Hermes 官方 `vertex` provider 指向 Vertex AI 的 OpenAI 兼容端点：

1. `.env` 中的 `GOOGLE_APPLICATION_CREDENTIALS`（或 `VERTEX_CREDENTIALS_PATH`）指向 service-account JSON。
2. `config.yaml` 中的 `model.provider: vertex` 选择官方 provider；`vertex.project_id` / `vertex.region` 保存非机密路由配置。
3. Hermes 运行时用 `google-auth` mint 短期 OAuth token，并在接近过期或遇到 mid-session 401 时自动 refresh。

因此，当前主链路不再读取 `.env` 里的 `VERTEX_ACCESS_TOKEN`。该字段和本仓库的 refresh 脚本保留为旧 `custom` provider 方案的回滚备用；`GEMINI_API_KEY` 只在切回 Hermes 内置 `gemini` provider 时才会生效。

### config.yaml 主配置

**位置**：`~/.hermes/config.yaml`

关键配置节说明：

```yaml
# 主模型（官方 Vertex provider；OAuth token 由 Hermes 自动 mint/refresh）
model:
  provider: vertex
  default: google/gemini-3.1-pro-preview

vertex:
  project_id: wh-gemini-1
  region: global

# 备用模型（主模型失败时自动切换）
fallback_model:
  provider: alibaba
  model: qwen3.6-plus

# 压缩辅助模型（与主/备模型对齐到 1M 上下文，可统一使用同一个 threshold）
auxiliary:
  compression:
    provider: alibaba
    model: qwen3.6-plus
    extra_body:
      enable_thinking: true # qwen 系开启 thinking 模式，让压缩更聪明

# 上下文压缩门槛（主/fallback/压缩三方都是 1M context 时可放宽到 0.7）
compression:
  enabled: true
  threshold: 0.7 # 触发时机 ≈ 700k tokens
  target_ratio: 0.2
```

> **三方对齐建议**：当主模型、fallback、压缩模型上下文窗口一致时，可使用统一 threshold；如果压缩模型容量小于主模型（例如压缩用 qwen3-max 256k、主模型 1M），Hermes 会在每次会话临时下调 threshold 到压缩模型容量并打 warning。当前配置三方都是 1M，因此 0.7 即可，无 auto-lower 警告。

**常用配置项**：

| 配置项                                             | 默认值       | 说明                                                                       |
| -------------------------------------------------- | ------------ | -------------------------------------------------------------------------- |
| `agent.max_turns`                                  | 90           | 单次 session 最大轮数                                                      |
| `agent.gateway_timeout`                            | 1800s        | Gateway 会话超时（30 分钟）                                                |
| `agent.reasoning_effort`                           | high         | 主 agent 推理强度（none/low/medium/high/xhigh）                            |
| `delegation.reasoning_effort`                      | high         | 子 agent / orchestrator 推理强度（空字符串表示继承主 agent）               |
| `display.personality`                              | kawaii       | 显示风格                                                                   |
| `display.show_reasoning`                           | false        | 是否在 TUI / 飞书等前端展示 reasoning 内容（依赖模型返回 reasoning）       |
| `display.streaming`                                | true         | 控制 **CLI/TUI 终端**逐 token 流式（仅终端，不影响平台前端）               |
| `streaming.enabled`                                | false        | 控制**飞书等 IM 前端**逐 token edit 流式；当前关闭，避免 markdown 渲染失真 |
| `compression.threshold`                            | 0.7          | 上下文占主模型容量比例触发压缩                                             |
| `auxiliary.compression.model`                      | qwen3.6-plus | 压缩任务使用的辅助模型                                                     |
| `auxiliary.compression.extra_body.enable_thinking` | true         | 压缩走 qwen thinking 模式                                                  |
| `approvals.mode`                                   | manual       | 危险命令审批（manual/auto）                                                |

### Thinking / Reasoning 配置

当前 thinking/reasoning 配置与可见性：

| 位置                                      | 当前                  | 模型                           | TUI 可见 | 飞书可见                  |
| ----------------------------------------- | --------------------- | ------------------------------ | -------- | ------------------------- |
| 主 agent (`agent.reasoning_effort`)       | high                  | gemini-3.1-pro-preview         | 不展示   | 不展示                    |
| 子 agent (`delegation.reasoning_effort`)  | high                  | 默认继承主模型                 | 不展示   | 不展示                    |
| Fallback (`fallback_model`)               | —                     | qwen3.6-plus（reasoning=True） | 不展示   | 不展示                    |
| 压缩 (`auxiliary.compression.extra_body`) | enable_thinking: true | qwen3.6-plus                   | —        | —（后台任务，不前端展示） |
| 显示开关 (`display.show_reasoning`)       | false                 | —                              | —        | —                         |

**已知限制**：

- 主模型走官方 `model.provider: vertex` + Vertex OpenAI 兼容端点 (`aiplatform.googleapis.com/.../openapi`)。Hermes 会把 Vertex 视作 Gemini-family provider，模型 ID 保留 `google/gemini-*` 的点号，并通过 provider-specific 路径处理 OAuth token refresh 与 Gemini thinking 参数。
- Fallback 触发后切到 qwen3.6-plus 的对话本身仍可能返回 reasoning；但当前 `display.show_reasoning: false`，前端不展示 thinking 段落。若临时改回 `true`，会重新显示前缀 `💭 **Reasoning:**` 的内容。
- 若后续发现 Vertex thinking trace 在特定前端仍不可见，优先按官方 `vertex` provider 路径排查，不再回到旧 `custom + VERTEX_ACCESS_TOKEN` 识别补丁思路。

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

飞书 token 流式开启后会出现 markdown 渲染失真——根因是 `gateway/platforms/feishu.py` 的 `_build_outbound_payload()` 每次 edit 重新探测 markdown 痕迹（`_MARKDOWN_HINT_RE` 要求 `**bold**`、`1.`、` ``` ` 等成对/完整出现），但流式中间帧的 buffer 经常处在"半开"状态（如 `**Hel`、` ` ``hello `），探测失败 → 走 plain text → 飞书 `update_message` 不能切换 msg_type → 后续 edit 全部锁死成 text → 用户看到 markdown 原文。

要重新开启流式且不丢格式，需要本地 patch（暂未实现）：让 `edit_message` 路径强制 `msg_type=post`，绕过 buffer-stage detection。在该 patch 落地前，飞书侧维持非流式整段输出，保留加粗/序号/列表渲染。

### Vertex Provider

当前主模型走 Hermes 官方 `vertex` provider。凭据链路分成三层：

1. `.env` 中的 `GOOGLE_APPLICATION_CREDENTIALS`（或 `VERTEX_CREDENTIALS_PATH`）指向 service-account JSON；也可使用 ADC。
2. `config.yaml` 中 `model.provider: vertex`，并在 `vertex:` 下保存 `project_id` 与 `region`。
3. Hermes 通过 `agent.vertex_adapter` 使用 `google-auth` mint OAuth token，指向 `https://aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{region}/endpoints/openapi`，并自动 refresh。

#### 官方 provider 配置

当前配置形态：

```yaml
model:
  provider: vertex
  default: google/gemini-3.1-pro-preview

vertex:
  project_id: wh-gemini-1
  region: global
```

> `region: global` 是 Gemini 3.x preview 推荐/必要路径；regional endpoint 可能 404。

#### 旧 custom-provider refresh 方案（保留为回滚备用）

本仓库仍保留 `scripts/refresh_vertex_access_token`、`scripts/refresh_vertex_and_restart_gateway`、`scripts/install_vertex_refresh_launchd` 和 wake watcher。它们服务于旧配置：

```yaml
model:
  provider: custom
  default: google/gemini-3.1-pro-preview
  base_url: https://aiplatform.googleapis.com/v1/projects/wh-gemini-1/locations/global/endpoints/openapi
  api_key: ${VERTEX_ACCESS_TOKEN}
```

只有回滚到上述 `custom` provider 方案时，才需要定时刷新 `.env` 里的 `VERTEX_ACCESS_TOKEN` 并重启 gateway。官方 `vertex` provider 不需要这组 LaunchAgent。

#### 自动刷新（legacy / custom provider）

macOS 下可安装一组独立的 LaunchAgent（仅旧 `custom` provider 方案需要）：

- 定时执行“刷新 Vertex token -> 等待 gateway 空闲 -> 计划内重启 gateway”
- 监听系统从休眠恢复，并在 wake 后立即补跑一次刷新

```bash
~/.hermes/scripts/install_vertex_refresh_launchd

# 可选：改为每 45 分钟刷新一次（会更频繁触发计划内 gateway 重启，因此飞书里看到
# “Gateway restarting — Your current task will be interrupted” 属于正常现象）
~/.hermes/scripts/install_vertex_refresh_launchd --interval-seconds 2700
```

默认行为：

- 定时任务 Label：`ai.hermes.vertex-refresh`
- 唤醒监听 Label：`ai.hermes.vertex-wake`
- plist：
  `~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist`
  `~/Library/LaunchAgents/ai.hermes.vertex-wake.plist`
- 定时周期：`3000` 秒（50 分钟）
- `ai.hermes.vertex-refresh` 的 `RunAtLoad=true`，安装后会立即跑一次
- 日志：
  `~/.hermes/logs/vertex-refresh.log`
  `~/.hermes/logs/vertex-refresh.err.log`
  `~/.hermes/logs/vertex-wake.log`
  `~/.hermes/logs/vertex-wake.err.log`

定时任务和 wake watcher 触发时，都会先刷新 `VERTEX_ACCESS_TOKEN`（失败时自动重试最多 3 次，间隔 60 秒；3 次均失败会弹出 macOS 系统通知），然后：

- 若 `ai.hermes.gateway` 已安装为 launchd 服务，则先等待 gateway 空闲（默认最多 600 秒，每 5 秒检查一次），再对 gateway PID 发送 `SIGUSR1` 触发 Hermes 的计划内 service restart；若计划内重启失败，才退回 `hermes gateway restart` / `hermes gateway start`
- 若 gateway 尚未安装，则只刷新 token，不会替你安装 gateway

可通过环境变量调整等待策略：

```bash
HERMES_VERTEX_RESTART_IDLE_WAIT_SECONDS=900
HERMES_VERTEX_RESTART_IDLE_POLL_SECONDS=5
```

> **launchd 环境说明**：后台 LaunchAgent 不会自动继承你交互式 shell 里的环境变量。当前脚本会主动从 `~/.hermes/.env` 读取 `GOOGLE_APPLICATION_CREDENTIALS` 和 `VERTEX_LOCATION`，因此这两个值必须实际写入 `.env`，不能只存在于 `.zshrc` / `.bashrc`。

#### LaunchAgent 代理注入（Feishu / Vertex）

若需要让 **gateway + Vertex refresh + wake watcher** 统一走本地代理（例如 Clash mixed port `7897`），可使用辅助脚本。对于 mixed port，推荐按 **HTTP 代理** 注入：

```bash
~/.hermes/scripts/inject_launchd_proxy_env --proxy-url http://127.0.0.1:7897
```

它会先用 `curl` 通过代理探测连通性；**探测成功后**才会把 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / `NO_PROXY` 原子注入到以下 3 个 LaunchAgent 的 `EnvironmentVariables`，并重载服务：

- `ai.hermes.gateway`
- `ai.hermes.vertex-refresh`
- `ai.hermes.vertex-wake`

若中途任一步失败，脚本会自动回滚 3 个 plist 到原状，保证最终状态是“要么全部注入，要么全部不注入”。

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
- `gateway / vertex-refresh / vertex-wake` 三个 LaunchAgent 都完成 `bootout + bootstrap`

脚本成功时**通常不需要额外手动重启**，因为它已经在成功路径中完成了重载。

**建议的验证动作**：

```bash
# 查看 3 个 LaunchAgent 状态
launchctl print gui/$(id -u)/ai.hermes.gateway
launchctl print gui/$(id -u)/ai.hermes.vertex-refresh
launchctl print gui/$(id -u)/ai.hermes.vertex-wake

# 手动触发一次 Vertex refresh，验证刷新链路也能经代理走通
launchctl kickstart -k gui/$(id -u)/ai.hermes.vertex-refresh

# 观察日志
tail -f ~/.hermes/logs/vertex-refresh.log
tail -f ~/.hermes/logs/vertex-refresh.err.log
tail -f ~/.hermes/logs/gateway.log
```

> **说明**：`ai.hermes.vertex-refresh` 是定时任务，平时显示“不在运行”是正常的；关键是 `kickstart` 后日志没有代理相关报错，并且 gateway / 飞书链路能正常响应。

**原生回滚方式**（不使用额外 remove 脚本）：

```bash
# 1. 重新生成 gateway 官方 plist（覆盖掉已注入的代理环境变量）
hermes gateway install --force

# 2. 重新生成 Vertex refresh / wake 的官方 plist
~/.hermes/scripts/install_vertex_refresh_launchd
```

如果你希望回滚时**只重建 LaunchAgent，不立刻触发一次 Vertex refresh**，第二步可改为：

```bash
~/.hermes/scripts/install_vertex_refresh_launchd --no-run-now
```

常用检查命令：

```bash
launchctl print gui/$(id -u)/ai.hermes.vertex-refresh
launchctl print gui/$(id -u)/ai.hermes.vertex-wake
tail -f ~/.hermes/logs/vertex-refresh.log
tail -f ~/.hermes/logs/vertex-wake.log
```

#### 运维常用命令

以下命令只适用于旧 `custom + VERTEX_ACCESS_TOKEN` 回滚方案；当前官方 `provider: vertex` 主链路不需要手动刷新 token，也不需要安装 Vertex 自动刷新 LaunchAgent。

```bash
# 立即手动刷新一次 token，并计划内重启 gateway
~/.hermes/scripts/refresh_vertex_and_restart_gateway

# 通过 launchd 立刻触发一次后台任务
launchctl kickstart -k gui/$(id -u)/ai.hermes.vertex-refresh

# 查看后台任务状态
launchctl print gui/$(id -u)/ai.hermes.vertex-refresh
launchctl print gui/$(id -u)/ai.hermes.vertex-wake
launchctl print gui/$(id -u)/ai.hermes.gateway

# 卸载 Vertex 自动刷新 LaunchAgent
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist
rm -f ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist \
      ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist
```

#### 与 Hermes 后台自启动的关系

`hermes gateway install` 和上面的 legacy Vertex 自动刷新是两个独立的 LaunchAgent，职责不同：

- `hermes gateway install` 负责 Hermes gateway 常驻、自启动、维持飞书 WebSocket 和 cron
- 官方 `provider: vertex` 会在 Hermes 进程内自动 mint/refresh Vertex OAuth token，不需要 `install_vertex_refresh_launchd`
- `install_vertex_refresh_launchd` 只服务旧 `custom + VERTEX_ACCESS_TOKEN` 回滚方案：定时刷新 `.env` 里的 `VERTEX_ACCESS_TOKEN`，并在系统 wake 后补跑一次刷新，再计划内重启 gateway 让新 token 生效
- 只做“单次刷新”时，新的 token 只会被之后新启动的 Hermes 进程读取；已经在跑的 gateway 不会自动热更新

这些进程在 launchd 层面是**相互独立的兄弟服务**，不是长期父子关系：

```text
launchd
├─ ai.hermes.gateway        # Hermes gateway 常驻
├─ ai.hermes.vertex-wake    # 监听系统 wake 的常驻 watcher
└─ ai.hermes.vertex-refresh # 定时任务；触发一次就退出，平时显示 not running
```

只有在 **wake 事件发生的瞬间**，`ai.hermes.vertex-wake` 会临时拉起 `refresh_vertex_and_restart_gateway`，形成一次短暂的父子链；但 `gateway` 本身仍由 launchd 独立管理，重启后也不会挂在 watcher 下面长期存活。

当前官方 provider 推荐组合是：

1. `.env` 写入 `GOOGLE_APPLICATION_CREDENTIALS` 或 `VERTEX_CREDENTIALS_PATH`
2. `config.yaml` 使用 `model.provider: vertex` + `vertex.project_id/region`
3. 执行 `hermes gateway install`，确保后台服务可自启动

旧 `custom` provider 回滚方案才需要额外安装自动刷新 LaunchAgent。

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

> **每次更新 hermes 版本后必须重新执行 `hermes gateway install`**，因为 plist 文件中嵌入了版本路径。

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

**作用**：bot 同一个 Feishu 应用账号同时服务多个会话时，按 `chat_id` + `chat_type` 区分工具权限——配置中列出的 owner DM 拥有完整工具集，其他 Feishu DM 只能调用基础安全白名单；Feishu 群聊/频道可在基础白名单外追加群聊专用只读工具。非 Feishu 来源（CLI/TUI、cron 调度器、内部事件）一律放行不拦截。

**为什么需要它**：hermes 原生 toolset 粒度是 _平台级_（`platform_toolsets.feishu`），同一个 Feishu bot 下所有 chat 共享一份工具列表。若把 bot 拉进群或被别人加为联系人，对方可以直接让 bot 调 `terminal` / `read_file` 等危险工具。`allowed_chats` 白名单虽然能限制响应范围，但代价是其他会话完全得不到响应；要在"允许其他人聊天/搜索/问图"和"禁止其他人碰系统"之间取折衷，原生配置做不到。本插件通过官方 `pre_gateway_dispatch` + `pre_tool_call` 钩子做按会话裁剪，零源码修改。

**机制（要点）**：

- `pre_gateway_dispatch` 把入站消息的 `(platform, chat_id, chat_type)` 写入 `contextvars.ContextVar`，asyncio 会自动把该 context 传到所有后续 `await` / `create_task` 子任务里，所以下游每次工具调用都能看到当前会话身份。并发会话各自带自己的 context，不串扰。
- `pre_tool_call` 读取 ContextVar：若 `platform != "feishu"` 直接放行；若 `chat_id` 在 owner 白名单里直接放行；否则只允许 `allowed_tools_for_outsiders` 中的工具；当 `chat_type` 是群/频道/话题时，再额外允许 `allowed_tools_for_outsider_groups` 中的工具。若群聊调用 `read_file` / `search_files`，还必须落在 `allowed_read_roots_for_outsider_groups` 白名单目录内。其余返回 `{action: block, message: ...}`。
- 群聊放行 `skills_list` / `skill_view` 只打开“读 skill”这条通路；实际可读 skill 仍由 `skills.platform_allowed.feishu_group` 限制。当前配置只允许 `llm-wiki`，不开放 `skill_manage`。
- 群聊放行 `read_file` / `search_files` 只打开 `~/.hermes/wiki` 的只读知识库检索；不开放 `write_file`、`patch`、`terminal`，也不允许读取 wiki 目录之外的本机文件。
- 不用 `threading.local`（asyncio 多协程同线程会串），不用 `set_thread_tool_whitelist`（同样问题），坚持 ContextVar。

**配置**（`plugins/sandbox/config.yaml`）：

```yaml
owner_feishu_chat_ids:
  - oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx # 你和 bot 的主 DM chat_id；可填多个
allowed_tools_for_outsiders:
  - web_search
  - web_extract
  - vision_analyze
  - image_generate
allowed_tools_for_outsider_groups:
  - skills_list
  - skill_view
  - feishu_doc_read
  - read_file
  - search_files
allowed_read_roots_for_outsider_groups:
  - ~/.hermes/wiki
block_message: "本会话不支持该工具。当前会话仅开放：聊天问答 / 联网搜索 / 网页正文抓取 / 图片理解 / 图片生成；群聊额外开放只读知识库、飞书文档读取、以及 ~/.hermes/wiki 范围内的只读文件检索。"
```

获取自己主 DM 的 `chat_id`：在主 DM 里发送 `/whoami` 查看回执；或翻 `~/.hermes/sessions/session_*.json` 找 `platform: feishu` 的最近会话取其 `chat_id` 字段。

**首次部署**：

```bash
# 1. 编辑 owner_feishu_chat_ids 填入主 DM 的 chat_id
$EDITOR ~/.hermes/plugins/sandbox/config.yaml

# 2. 启用插件（仅首次需要）
hermes plugins enable sandbox

# 3. 重启 gateway
hermes gateway restart

# 4. 验证：查 agent.log 应有 sandbox: registered (active=True, owner_chats=[...], allowed=[...], group_allowed=[...])
grep "sandbox: registered" ~/.hermes/logs/agent.log | tail -1
```

`active=True` 且 `owner_chats` 非空表示生效；若 `active=False` 说明 `config.yaml` 没有有效的 owner，插件 fail-open（不拦截任何东西，等同未启用）。

**运维与扩展**：

- 增加特权会话：编辑 `config.yaml` 的 `owner_feishu_chat_ids` 数组追加新 chat_id，重启 gateway。
- 调整放行工具：编辑 `allowed_tools_for_outsiders`；群聊额外只读工具编辑 `allowed_tools_for_outsider_groups`。如果放行 `read_file` / `search_files`，同步维护 `allowed_read_roots_for_outsider_groups`，否则会被路径检查拦截。工具名见 `hermes tools` 或 `hermes-agent/toolsets.py` 的 `_HERMES_CORE_TOOLS`。
- 临时关闭：`hermes plugins disable sandbox && hermes gateway restart`，下次开启重新 `enable` 即可。
- 反面测试：临时把 `owner_feishu_chat_ids` 改成一个不存在的 chat_id 并重启，然后在主 DM 让 bot 跑 `terminal`——应该被拦下并回 `block_message`；验完改回去再重启。

**升级兼容性检查**：

插件依赖上游 `VALID_HOOKS` 中的 `pre_gateway_dispatch` 和 `pre_tool_call`，以及它们在 `gateway/run.py` / `model_tools.py` 中的触发点。若上游改名 / 改 kwargs 签名 / 改 fire site 文件位置，插件可能静默失效。配套脚本 `plugins/sandbox/verify.sh` 做三项硬/软检查：

```bash
bash ~/.hermes/plugins/sandbox/verify.sh
# 1. VALID_HOOKS 仍含两个钩子名（HARD FAIL if 改名）
# 2. fire site 在 gateway/run.py / model_tools.py 中仍可被 grep 到（SOFT WARN）
# 3. agent.log 最近一条 "sandbox: registered" 显示 active=True（HARD FAIL if active=False）
```

该脚本由 `hermes-update.sh` Step 8e 在每次官方更新后自动调用并汇总到最终摘要的 ACTS 区，无需手动跑。任何 HARD FAIL 都会在更新结束的状态摘要里以 action item 形式呈现，提示去检查/修补 `plugins/sandbox/__init__.py`。

**已知限制 / 注意点**：

- 用户插件在 `~/.hermes/plugins/`，与 `hermes-agent/` 源码完全分离，`hermes update` / 升级官方仓库**不会**影响插件。但官方若改动 `VALID_HOOKS` 的 kwargs 签名（大版本概率事件），插件需要同步小修——升级后看 Step 8e 的输出即可。
- 插件靠 ContextVar 跨 `await` 边界传 `chat_id`，hermes 当前 asyncio 单线程架构下安全。若上游改为把 agent 跑在 `loop.run_in_executor` worker 线程里且不显式 `copy_context()`，会失效；目前没有这种使用方式，但属于升级时要留意的"前提"。
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
- `scripts/` 下已有 vertex 系列双 LaunchAgent 模式（refresh + wake），命名空间 / 日志路径 / install 模式可直接复用
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

> **早期实现尝试过 `CGDisplayRegisterReconfigurationCallback`**（更精确的"显示重协商"事件），但在 launchd 启动的 `swift -interpret` 上下文里 CG 回调无法到达进程（缺乏 WindowServer bootstrap，即使加 `NSApplication.run()` 也不行）。改用 NSWorkspace 通知后稳定可工作 —— 这条机制跟 `vertex_wake_watcher.swift` 同源。

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
bash ~/.hermes/hermes-update.sh
```

脚本依次执行以下步骤，完成后显示状态摘要和待操作提示：

| 步骤 | 操作                                      | 说明                                                                                                                                                                                                              |
| ---- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | Preflight checks                          | 确认 hermes 可用、git 仓库存在、网络正常                                                                                                                                                                          |
| 2    | **Save & clean patches**                  | 将 hermes-agent 本地补丁另存至 `patches/local-patches.diff`，还原文件至 HEAD；PATCHED_FILES 之外的额外改动在 update 前用 `git stash push -u` 保护，避免 untracked 文件被清理                                      |
| 3    | `hermes update`                           | git pull · 关键文件语法校验/失败自动回滚 · uv pip install · Skills Hub 同步 · 配置迁移确认 · gateway 进程重启                                                                                                     |
| 4    | `npm audit fix`                           | 修复 hermes update 安装 npm 依赖后遗留的已知安全漏洞（PATCH-6）                                                                                                                                                   |
| 4b   | Skills 镜像同步                           | `rsync --delete` 使 `skills/` 完全镜像上游 `hermes-agent/skills/`：新增 skill 自动添加、上游删除的 skill 自动清理；用户自定义 skill 存于 `my-skills/`，不受影响                                                   |
| 5    | `hermes gateway install --force`（按需）  | 仅在 plist 未 bootstrap 时执行；已加载的 OnDemand 服务直接跳到步骤 6                                                                                                                                              |
| 6    | 确认 gateway 运行                         | 若 gateway 未运行则自动 start                                                                                                                                                                                     |
| 7    | `hermes completion zsh`                   | 重新生成 zsh 补全脚本；若上游回滚到坏的 `_arguments` 语法则自动重新应用 PATCH-3（v0.13.0 起上游已修复 commit `fe61d95b4`，detection 块作为回归 sentinel 保留），随后清除 zcompdump 缓存                           |
| 8    | **Re-apply & verify patches**             | 将 `patches/local-patches.diff` 重新应用（PATCH-1/7/9/10/11/12/13/14/15/16/17/18）；验证 PATCH-2/3/4/5 上游行为存活 + 本地补丁生效后才刷新 diff 文件；刷新时记录上游 base commit 到 `patches/.local-patches.base` |
| 8e   | **Verify user plugins**                   | 对 `plugins/*/verify.sh` 逐一执行：检查依赖的 `VALID_HOOKS` 钩子名仍在上游、fire site 仍存在、`agent.log` 里能找到 `<plugin>: registered (active=True, …)`。任一硬失败计入 ACTS                                   |
| 9    | `hermes doctor` + `hermes gateway status` | 验证更新结果；若 gateway 因 update / post-patch restart 处于未加载状态，脚本会自动补一次最终恢复（`install --force` / `start`）后再判定                                                                           |

> ⚠ **脚本维护提示**：若 hermes 上游大版本升级后更新流程发生变化（新增步骤、flags 变动、路径变更），需同步更新 `~/.hermes/hermes-update.sh`。脚本顶部有详细的"需关注场景"注释。

### 手动步骤参考

若脚本某步失败，可单独执行对应命令排查：

```bash
# 代码 + 依赖 + skills + gateway 重启
hermes update

# 刷新 launchd plist（版本升级后必须执行）
hermes gateway install --force

# zsh 补全脚本
hermes completion zsh > ~/.hermes/completions/_hermes
rm -f ~/.zcompdump*

# 验证
hermes --version
hermes doctor
hermes gateway status
```

---

## 本地补丁记录

本项目维护若干针对上游 `hermes-agent` 的本地补丁，以修复已知 Bug 或定制行为。完整记录（问题描述 / 根因 / 修复方案）见 [`patches/PATCHES.md`](patches/PATCHES.md)。当前补丁基线已刷新到上游 `88b720eb`（截至 2026-07-03 的 `main`，较 `30e947e0` 前进 57 commits，release tag 仍为 `v0.18.0 (2026.7.1)`）；PATCH-2（doctor issue-count 过报）已由上游 commit `6b21a935a` 合并并归档，当前共 13 条活跃补丁。本轮 `local-patches.diff` clean 回贴并刷新到新基线；PATCH-14 同步纳入 `address` 公开称呼、群聊私有画像脱敏与 streaming `text_filter` 防线，`hermes-update.sh` 的 `PATCHED_FILES` 与 sentinel 已覆盖新增文件。已知摩擦仍是 `platform.matrix` lazy backend 刷新失败、脚本末尾 gateway status 偶发报未运行，以及内层 `uv.lock` 作为额外 tracked 改动不纳入 `local-patches.diff`。

补丁由 `hermes-update.sh` 全自动管理：Step 2 存档并还原、Step 4 修复 npm 漏洞（PATCH-6）、Step 7 重新生成补全脚本并对旧坏格式做回归 sentinel 检测（PATCH-3 已于 v0.13.0 上游合并 commit `fe61d95b4`，正常情况下检测不命中、直接跳过；**v0.15.1 升级修复**：`rm -f ~/.zcompdump*` 撞到空目录残留时 `set -e` 中断脚本，已改用 `find` 只删文件）、Step 8 重新应用 `hermes-agent/` 内补丁并行为化验证（PATCH-1 skill 路由、PATCH-7 feishu python-socks 依赖、PATCH-9 OpenClaw 迁移不再写入废弃 gateway token、PATCH-10 Feishu 群聊提及/上下文/隔离、PATCH-11 平台级 skill allowlist 与只读 skill 工具集、PATCH-12 Feishu 回复不再创建话题（始终普通引用回复）、PATCH-13 群聊当前发言人身份锚定、PATCH-14 人物/群聊画像注入、PATCH-15 Feishu 附件回看、PATCH-16 Feishu 出站 markdown 渲染、PATCH-17 Vertex hidden thoughts、PATCH-18 Vertex doctor 识别；PATCH-2 / PATCH-4 / PATCH-5 已上游合并并退役，仅保留存在性 grep 验证；PATCH-8 于 v0.11.0 上游合并，仅保留文档记录），Step 8d 重启 gateway 使补丁代码生效。若 `local-patches.diff` 自身已带 conflict marker，或 apply 后文件含冲突标记，脚本会直接回滚 patched files 到上游 HEAD 并拒绝刷新 patch 文件。刷新成功时会同步写入 `patches/.local-patches.base`（上游 commit SHA + 时间戳），便于追溯 patch 基线。

手动恢复 `hermes-agent/` 内补丁：

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突：git apply --reject && 手动解决 .rej，再重跑 hermes-update.sh

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
hermes --skills devops

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
hermes sessions rename ID    # 重命名会话
hermes sessions export ID    # 导出会话
hermes sessions delete ID    # 删除会话
hermes sessions prune        # 清理旧会话
```

> **说明**：`hermes sessions delete` 会删除会话索引；如果你在排查飞书 fallback / 400 级联错误这类“旧会话污染”问题，建议连同 `~/.hermes/sessions/session_<ID>.json` 一起删除，并在完成后重启 gateway。

### 模型选择

```bash
hermes model                 # 交互式选择默认 provider 和模型（TUI 选择器）
hermes model list            # 列出可用模型
```

**会话内切换**：

| 命令                            | 说明                       |
| ------------------------------- | -------------------------- |
| `/model gemini-3.1-pro-preview` | 临时切换（仅当前会话）     |
| `/model qwen3-max --global`     | 切换并持久化到 config.yaml |

**通过 `hermes config set` 切换**（脚本化 / 非交互式）：

```bash
# 切换主模型
hermes config set model.provider alibaba
hermes config set model.default qwen3-max

# 切换 fallback 模型
hermes config set fallback_model.provider gemini
hermes config set fallback_model.model gemini-3.1-pro-preview
```

**直接编辑配置文件**：`hermes config edit`（用 `$EDITOR` 打开 config.yaml）。

> 💡 **fallback_model** 的配置说明见上方 [config.yaml 主配置](#configyaml-主配置) 节。

> ⚠️ **Thinking 模型注意**：`gemini-3.1-pro-preview` 等 thinking 模型在会话内通过 `/model` 切换后，thinking 标签可能污染上下文，引发 400 级联错误。

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
hermes skills list            # 列出 Skills Hub 可用的 skills
hermes skills install devops  # 手动安装指定 skill（首次或删后恢复）
hermes skills update          # 强制刷新全部 skills
```

#### 自定义 Skills

自定义 / Agent 生成的 skills 存放在 `~/.hermes/my-skills/`（随主仓库入库），通过 `config.yaml` 的 `external_dirs` 注册到 Hermes：

```yaml
skills:
  external_dirs:
    - ~/.hermes/my-skills
```

当前自定义 skills：

| Skill                   | 分类                 | 说明                                                              |
| ----------------------- | -------------------- | ----------------------------------------------------------------- |
| `feishu-docs`           | productivity         | 飞书文档读取（Bot API 绕过登录墙）与创建（Import API + 权限管理） |
| `hacker-news`           | feeds                | 通过 Firebase API 抓取 HN 技术新闻（绕过 CAPTCHA）                |
| `memory-management`     | —                    | 记忆工具报错处理指南（容量超限、状态异常等）                      |
| `agentic-demo-pipeline` | software-development | Codex + Copilot 双 Agent 自动化 Demo 开发流水线（调研→代码→文档） |

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
hermes cron enable JOB_ID    # 启用任务
hermes cron disable JOB_ID   # 禁用任务
hermes cron delete JOB_ID    # 删除任务
hermes cron run JOB_ID       # 立即执行一次
```

> Cron 任务由 Gateway 服务调度，**Gateway 必须运行**才能执行定时任务。

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

| 类型         | 存放位置                         | 加载时机                  | 适合内容                             |
| ------------ | -------------------------------- | ------------------------- | ------------------------------------ |
| 持久记忆     | `memories/MEMORY.md` + `USER.md` | 每次会话自动注入          | 高频偏好、环境事实                   |
| **LLM Wiki** | `~/wiki/`（可自定义）            | 按需检索，Agent 主动查询  | **长期知识积累、技术笔记、领域知识** |
| Skills       | `skills/<name>/`                 | 按需调用（`/skill-name`） | 操作手册、流程文档、领域知识         |
| 项目上下文   | 项目目录下 `AGENTS.md`           | 进入该目录时自动注入      | 项目架构、编码规范                   |
| 按需注入     | 任意路径，`@file:` / `@folder:`  | 手动在消息中触发          | 临时大文档、参考资料                 |
| 历史回溯     | `state.db`（自动）               | Agent 主动搜索时          | 所有历史会话内容                     |

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
~/wiki/
├── SCHEMA.md       # Wiki 的规则、领域范围、Tag 分类体系（Agent 每次先读这里）
├── index.md        # 所有页面的一行摘要目录（Agent 的导航地图）
├── log.md          # 所有操作的时间戳日志（追加写入，可回溯）
├── raw/            # 原始资料（不可修改）：文章、论文、会议记录
├── entities/       # 实体页：人物、公司、产品、工具
├── concepts/       # 概念页：技术原理、方法论
├── comparisons/    # 对比分析页
└── queries/        # 值得保存的深度查询结果
```

#### 配置

在 `~/.hermes/config.yaml` 中添加：

```yaml
skills:
  config:
    wiki:
      path: ~/wiki # 也可以指向 Obsidian vault 目录
```

不配置时默认使用 `~/wiki`。

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

> **首次启动**会自动构建前端（需要 `npm`），约需 10–20 秒；上游 `_web_ui_build_needed()`（commit `5b5a53a1`）会基于 `hermes_cli/web_dist/.vite/manifest.json` sentinel + 源码 mtime 判断是否需要重建，已构建且未过期时跳过 `npm install` 与 Vite build（替代了已退役的 PATCH-4）。`hermes update` 每次更新都会触发 `npm ci` 重新构建。

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

| 版本               | 日期       | 说明                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| v0.18.0            | 2026-07-03 | 基线滚动到上游 `88b720eb`（较 `30e947e0` 前进 **57 commits**，release tag 仍为 `v0.18.0 (2026.7.1)`）。上游主线：**Desktop** 修复更新提示图标、macOS Tahoe traffic lights、profile rail、remote attachments/artifacts 与 `/journey` memory graph；**Gateway/Webhook** 修复 delivery 结束关闭 session、session eviction `on_session_end` 覆盖与 idle cached agent 生命周期；**File tools / Config / Providers** 分别保留 Docker container paths、atomic writes owner、模型发现 extra headers；**Slack/Usage/Auth** 修复 rich list 空行/编号、捕获 `reasoning_tokens`、xAI device-code-only。patch apply：Step 8 **clean apply**，无 3-way、无冲突；PATCH-1/7/9/10/11/12/13/14/15/17/18 行为化 sentinel 全 OK，PATCH-2/4/5 上游吸收 sentinel OK；`local-patches.diff` 与 `.local-patches.base` 刷新到 `88b720eb`。本轮同步把 PATCH-14 的 `address` 公开称呼、私有画像脱敏与 streaming `text_filter` 纳入 patch 快照、`PATCHED_FILES` 和验证 sentinel；PATCHES.md 结构检查确认每个 PATCH 下同一类别仅一项。验证：`git apply --cached --check ../patches/local-patches.diff` clean；定向 pytest 覆盖 PATCH-14 与 streaming guard **43 passed**；`git diff --check` clean；sandbox plugin verify OK。依赖：`hermes-agent` editable 重装；npm root/ui-tui/web 依赖安装，web UI rebuilt；`npm audit` no vulnerabilities；Skills mirror **+0 / ~0 / -4**；lazy backend `platform.matrix` 刷新失败，保留旧版本。已知摩擦：脚本末尾 gateway status 在自动 recovery 后仍报未运行，需以升级后复查状态/日志为准；内层 `uv.lock` 仍为额外 tracked 改动，不纳入 `local-patches.diff`。配置漂移：doctor `Config version up to date (v33)`、`All checks passed`，仅保留 auth/optional tool/API key 与 Skills Hub 未初始化等可选提示。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| v0.18.0            | 2026-07-02 | 基线滚动到上游 `30e947e0`（较 `7cfa2fa1` 前进 **796 commits**，release tag 升至 `v0.18.0 (2026.7.1)`）。上游主线：**安全/Doctor** 合并 PATCH-2 等价修复 `6b21a935a`（disabled toolsets 不再进入 missing API-key issue summary）；**Gateway** 新增 per-session `/model` 持久化、per-channel model/system-prompt overrides、typing indicator、context breakdown、resume/compression/restart 多项修复；**Skills** 发布 fetchable metadata、review fork 写前读、严格路径 containment；**Desktop/Web** 大量终端、memory graph、pet roam、dashboard sidebar 与危险操作确认改进；**xAI** Imagine public URL、chaining、video edit/extend。patch apply：脚本 Step 8 首次整体回贴失败；手工 `git apply --3way` 后 **31/35 clean，4 文件冲突手动解决**（`gateway/session.py`、`hermes_cli/doctor.py`、`hermes_cli/tools_config.py`、`tests/gateway/test_session.py`），处理原则为保留上游 untrusted metadata / recover_platform_tools 新保护并恢复本地 people/group profile、skill/toolset 恢复与 quoted current-author 语义；PATCH-2 已归档至 `v0.18.0 archive` 并从 `PATCHED_FILES` 移除；`local-patches.diff` 与 `.local-patches.base` 刷新到 `30e947e0`。验证：`python -m py_compile` 覆盖冲突文件；`pytest tests/gateway/test_session.py tests/tools/test_skill_manager_tool.py tests/tools/test_skills_tool.py tests/hermes_cli/test_tools_config.py tests/hermes_cli/test_skills_config.py -q` **452 passed**；`git diff --check` clean；sandbox plugin verify OK。依赖：venv `aiohttp 3.13.4 → 3.14.1`、`hermes-agent 0.17.0 → 0.18.0`；`npm audit` no vulnerabilities；Skills mirror **+0 / ~0 / -4**；lazy backend `platform.matrix` 刷新失败，保留旧版本。已知摩擦：脚本 final gateway recovery 报未运行，需以升级后复查状态为准；内层 `uv.lock` 仍为升级脚本恢复的额外 tracked 改动，不纳入 `local-patches.diff`。配置漂移：后续已运行 `hermes doctor --fix`，`config.yaml` 迁移到 `_config_version: 33`；并新增 PATCH-18 让 doctor 识别官方 `provider: vertex` 与 `google/*` Vertex 模型名，当前 `hermes doctor` 在 Vertex 配置下通过（仅保留 auth/optional tool 未配置提示）。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| v0.17.0            | 2026-06-28 | 基线滚动到上游 `6f1a176b`（较 `e3db1ef9` 前进 **180 commits**，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代；本轮跨度大、未逐 commit 审计）。**本轮新增 PATCH-16**：Feishu post/md 块级语法补渲染——出站 `_build_outbound_payload` 已把 markdown 转 post 富文本，但 post/md 不渲染 ATX 标题 `#` 与引用 `>`（显示成裸符号）；新增纯函数 `_promote_block_markdown`（标题 `#`→`**加粗**`、引用 `>`→`▎` 前缀，复用围栏正则使代码块内 `#`/`>` 原样保留），接入 `_build_markdown_post_payload`，改 `plugins/platforms/feishu/adapter.py` + `tests/gateway/test_feishu.py`（+3 单测），表格仍走纯文本降级。配套 config-repo（非 hermes-agent）：`scripts/nightly_greeting.py` 新增 `is_chinese_workday`（`chinesecalendar` 离线判工作日，周末/法定节假日直接退出、不发日报不发 greeting）+ `--ignore-holiday` 开关，venv 装 `chinesecalendar==1.11.0`，不进 `local-patches.diff`。上游主线（180 commit，高层概述）：HEAD `fix(gateway/discord): REST liveness probe (#26656)`，含 discord 僵尸连接探活、session_key 改 contextvars 不写 `os.environ` 防并发互覆盖（#24100）、`platform_toolsets` 平台配置键 split 重构、MCP OAuth 元数据落盘、Desktop/Projects 等；本轮上游**触碰了本地补丁区域**。patch apply：**33/35 clean，2 处冲突手动 3-way 解决**——`git apply` 整体原子失败，逐文件定位仅 `gateway/run.py`（PATCH-10/11 与 #24100 session_key 重写重叠）、`tests/hermes_cli/test_tools_config.py`（与上游新增 vision picker 测试重叠）冲突，含 PATCH-16 在内其余 33 文件 clean；冲突按「采上游 #24100 去 os.environ + 留本地 `_platform_config_key_for_source` / 留上游 vision 测试 + 弃本地尾部空行删除」解决，重生成 `local-patches.diff` **200097→204956**（PATCH-16 净增 ~4.9KB），`.local-patches.base` 刷新到 `6f1a176b`。验证：还原到 `6f1a176b` 干净态后 `git apply --check local-patches.diff` **全 35 文件零冲突 CLEAN**、重应用无标记——幂等成立；`test_tools_config.py` + `test_feishu.py` 共 **321 passed**。依赖：venv 新增 `chinesecalendar==1.11.0`；`uv` clean；`npm audit` no vulnerabilities；Skills mirror **+0/~0/-2**。已知摩擦：脚本 Step8 patch 回贴整体失败（2 文件冲突拖垮全部 35）+ 结尾 gateway 未起，均为上游触碰补丁区的连带后果，手动解冲突 + `hermes gateway restart` 后恢复（PID 33026、launchd 监管、run.py import 自检 OK）。配置漂移：doctor 报 **Config version outdated (v30→v31)**（有新设置，非阻塞，本轮未自动 `--fix`）；Gateway running。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| v0.17.0            | 2026-06-26 | 基线滚动到上游 `e3db1ef9`（较 `0f81b0d4` 前进 28 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。**本轮新增 PATCH-15**：Feishu 群聊裸 @ 触发时回看同发送者最近 ~120s 的图片/文件消息并附到当轮（解决「图片/文件与 @ 分属两条、图片在 `_admit` 被丢、模型看不到」），改 `plugins/platforms/feishu/adapter.py`（已在 `PATCHED_FILES`）+ 新增 `_backfill_sender_attachments`/`_backfill_reply_attachments`/`_mark_attachment_backfilled`/`_backfilled_attachment_ids` LRU；同步 `hermes-update.sh` 加 PATCH-15 sentinel 验证并入 refresh gate。配套 config-repo 扩 `feishu-docs` skill：新增 `read_sheet.py`/`read_bitable.py`/`download_feishu_file.py`/`read_feishu_url.py`(分发器)/`feishu_render.py` + 更新 `SKILL.md`（统一入口、群沙箱须用 venv python、URL 加引号）。上游主线（28 commit）：**安全**——tirith 崩溃加 circuit breaker（#41400）、cron 不可见 unicode 对齐扫描器、停拦命名 `Praxis` 的 `SOUL.md`（#52925）；**配置**——非法 `platform_toolsets` 改显式报错（#38798，群聊工具集所在区、本仓 config 合法无影响）；**Gateway/Relay**——external drain + accept-gating、multi-platform-per-agent Phase1.5（#52830）、whatsapp reply-to 上下文（#52957）；**Auxiliary/MCP**——非法 provider 响应 fallback、Anthropic base_url host gate（#52608）、stale OAuth `invalid_client` 自恢复；**Dashboard**——socket drop 后 PTY 重连、dashboard-auth bearer/API-token；**Desktop/macOS**（与本地补丁无关）——clarify 重做（#52993）、gateway status 区分 launchd 监管 vs detached。patch apply：**全部 clean apply**——35 patched files 干净落到 `e3db1ef9`，PATCH-15 干净落新基线、无 3-way，`local-patches.diff` **187661→200097**（PATCH-15 净增），`.local-patches.base` 刷新到 `e3db1ef9`；PATCH-1/2/6/7/9/10/11/12/13/14 + 新增 PATCH-15 行为化验证全 OK。验证：refresh 后 `git diff HEAD` 与 `local-patches.diff` **逐字节一致**（200097 == 200097）——幂等成立；`test_session.py` + `test_feishu.py` + `test_feishu_bot_admission.py` 共 **382 passed**。依赖：`uv` clean 无 fallback；`npm audit` no vulnerabilities；Skills mirror **+0/~0/-3**。已知摩擦：脚本结尾 `✗ Gateway is not running` 系上游 `fix(macos)` 改 gateway status 判定后的 OnDemand 时序竞态，网关实际由 launchd 监管已起（PID 91165、feishu websocket connected），非真故障。配置漂移：无 schema migration，doctor `Config version up to date (v30)`、All checks passed；Gateway running、feishu connected。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| v0.17.0            | 2026-06-26 | 基线滚动到上游 `0f81b0d4`（较 `233ef98a` 前进 31 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**安全**——`fix(email)` 拒绝伪造 `From:` 头做授权（GHSA-rxqh-5572-8m77）、`fix(browser)` 强制 secret 脱敏；**Gateway/状态**——scale-to-zero arm-gate 修复、`_make_agent` init-time provider fallback、`fix(state)` 修复 FTS 写损坏丢历史；**Curator**——external-skill 写保护在后台 curation 时真正生效（护住 `my-skills/`）；**Desktop/TUI**（重头但与本地补丁无关）——宠物随光标缩放、WSL2 剪贴板/标题栏/GPU、stop 中断排队 turn；另有 telegram 重连保留 update 队列、interrupt 保留已流式产出、fuzzy-match 边界空格、agent stale-timeout 下限、kanban 解死锁。**本轮无 patch 变更**：10 条活跃补丁与 `PATCHED_FILES`/sentinel 全不变，本地改动均在 config-repo（群信息单一入口 `groups.yaml`、`nightly_greeting.py` 改读 `groups.yaml`、`feishu-groups` skill 去表、群聊 skill 白名单换装 `feishu-people-search`、`people.yaml` 补 aliases、新增 `feishu-people-search` skill），不进 `local-patches.diff`。patch apply：**全部 clean apply**——35 个 patched files 干净落到 `0f81b0d4`，无 3-way、无冲突（31 commit 未碰本地补丁区域，`local-patches.diff` 仅 `index`/`@@` 元数据 rebase、字节数仍 187661、**零语义漂移**）；PATCH-1/2/6/7/9/10/11/12/13/14 行为化验证全 OK；`local-patches.diff` 与 `.local-patches.base` 刷新到 `0f81b0d4`。验证：脚本 refresh 后 `git diff HEAD` 与已存 `local-patches.diff` **逐字节一致**——幂等成立；`test_session.py` + `test_feishu.py` + `test_feishu_bot_admission.py` 共 382 passed。依赖：`uv` clean 安装无 fallback；`npm audit` 报 no vulnerabilities；Skills mirror **+0 / ~0 / -3**。本轮无 lockfile stash 摩擦、无 Recommended actions。配置漂移：无 schema migration，doctor `Configuration is up to date`、All checks passed；Gateway 经 stop→start 重启加载补丁，service loaded、running、`LastExitStatus=0`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| v0.17.0            | 2026-06-26 | 基线滚动到上游 `233ef98a`（较 `a6a28ce3` 前进 104 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线以 **Desktop / Projects 子系统**为重头：backend-authoritative projects sidebar、git worktree + review IPC、Codex 风格 review pane、composer coding rail + worktree flow、file preview spot editor、终端面板 resize、background `delegate_task` 的 "will resume" 提示；配套 project workspace tools、authoritative project tree、sessions 记录 git workspace metadata、kanban 关联 worktree。另有 Gateway（cache cleanup 移出 lock #52197/#52761、user-turn 去重 #47237）、Compression（`in_place` 默认 True #38763）、Auxiliary fallback 链按 context-window/付费/容量错误兜底、Cron（partial job-loss #52144、per-run 保留 #52383）、Telegram（CLOSE-WAIT heartbeat、rich 表格 + topic）、MoA presets 虚拟模型（#46081）、MCP OSV preflight 移出 event loop（#29184）等。**本轮本地变更**：把 **PATCH-14** 从 people-profile 扩展为**人物 / 群聊画像注入**——新增 git 入库的 `~/.hermes/groups.yaml`（按 `chat_id`/`parent_chat_id`/`chat_id_alt`/`name`+aliases 匹配，注入 `style` 语言风格 / `capabilities` 能力栈 / `audience` / `intro` / `notes`，**只改表达层、沙箱各群一致**），并对所有 group/channel session 注入 `_GROUP_TOOL_LIMITATION_RULE`（工具/权限受限导致效果打折时产出必须明确声明、深入结论建议等琛哥确认）；新增 `TestGroupProfileInjection`（7 例），同步 `feishu-groups` skill 指针与 `hermes-update.sh` sentinel。patch apply：**全部 clean apply**——35 个 patched files 干净落到 `233ef98a`，无 3-way、无冲突（上游 104 commit 未碰本地补丁区域，仅行号漂移）；PATCH-1/2/6/7/9/10/11/12/13/14 行为化验证全 OK；`local-patches.diff` 与 `.local-patches.base` 刷新到 `233ef98a`。验证：经脚本 save→revert→reapply 往返 `gateway/session.py` 字节一致，幂等成立；`test_session.py` + `test_feishu.py` + `test_feishu_bot_admission.py` 共 382 passed。依赖：`uv` clean 安装无 fallback；`npm audit fix` 报 no vulnerabilities；Skills mirror **+0 / ~0 / -3**。已知摩擦：升级前 stash 的 `package-lock.json` + `uv.lock` 因上游同轮 bump 而 **auto-merge 失败，保留在 `stash@{0}`**，工作树 lockfile 已是上游新版。配置漂移：无 schema migration，doctor `Configuration is up to date`、All checks passed；Gateway 经 stop→start 重启加载补丁，service loaded、running、`LastExitStatus=0`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| v0.17.0            | 2026-06-26 | 基线滚动到上游 `a6a28ce3`（较 `d6269da7` 前进 1 commit，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游仅 1 个 CI commit `a6a28ce3`（`fix(ci): run CI on all PRs to anywhere`，只删 `.github/workflows/{ci,docker-publish}.yml` 各 1 行，不触及源码）。**本轮重点为本地新增 PATCH-14（people-profile 人物画像注入）**：`gateway/session.py` 读取 `~/.hermes/people.yaml`（mtime 缓存，按 user_id/user_id_alt/name+aliases 匹配）并在 session prompt 的 current-author 块后注入对方画像，渲染分**可公开段**（姓名 / 岗位 / 部门·团队）与**保密段**（工号 / 入职 / 司龄 / 上级 / 下属 / 称呼 / 职业背景 / 行为模式 / 态度 / 风险，尾附 `_PEOPLE_PROFILE_SECRECY` 强制保密指令——只调整应对、绝不外泄、防被群成员套话）；`redact_pii` 平台跳过，loader 吞异常不影响 prompt 路径。配套 `scripts/pull_feishu_people.py`（`pull`→`people.draft.yaml` / `merge [--apply]`，飞书通讯录客观字段每次刷新、人工主观字段只填空不覆盖，owner 置顶其余按工号排序），`people*.yaml` 全部 gitignore（组织 PII 不入库）。patch apply：**全部 clean apply**——35 个 patched files 从 `local-patches.diff` 干净落到 `a6a28ce3`，无 3-way、无冲突；PATCH-1/2/6/7/9/10/11/12/13/14 行为化验证全 OK；`local-patches.diff` 与 `.local-patches.base` 刷新到 `a6a28ce3`。验证：经脚本 save→revert→reapply 往返 `gateway/session.py` 字节一致，幂等成立；`tests/gateway/test_session.py` 96 passed（含 9 例 people-profile）。依赖：`uv` clean 安装无 fallback；`npm audit fix` 报 no vulnerabilities 但改动 tracked `hermes-agent/package-lock.json`（按设计不纳入 diff）；Skills mirror **+0 / ~0 / -1**。配置漂移：无 schema migration，doctor `Configuration is up to date`、All checks passed；Gateway 经 stop→start 重启加载补丁，service loaded、running。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| v0.17.0            | 2026-06-25 | 基线滚动到上游 `d6269da7`（较 `5ecf3bf0` 前进 239 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**Pets / Petdex（新子系统）**——`32f837add` prompt→atlas sprite 生成引擎、`3faf768cd` OpenRouter + Nous Portal 图像后端、`aab49f692` 生成 RPC + 非阻塞 gallery、`743985bf1` Pokédex 生成 UI（overlay / 动画蛋 / 孵化 FX）、`e92b5c6af` quality-first OpenRouter 模型链 + 全局生成通知、`5196575d4` remix 草稿，并新增 `hermes pets` CLI 与 petdex skill/catalog（`6fd839ac8`）；**Agent 验证门**——`2f1a47b90` 要求收尾编辑前先验证、`a5849917a` 识别 ad-hoc 验证脚本、`7ef0f360d` 暴露 coding verification status、`fcbdf3c35` 记录验证证据账本；**Gateway scale-to-zero**——`d1cac0e5e` idle 检测 + dormant-quiesce Phase 0、`96af4bec3` `go_dormant()` transport、`d6269da7f` 加固 dormancy guards（#52359）；**Cron**——`1b181724f` 可选把 cron 投递镜像进目标会话、`b693bee10` thread-preferred 可续投递、`7a65800fe` content-address `prompt_cache_key` 让循环 cron 复用 warm prefix（#52295）；**Relay 授权**——`72ae16325` 按 delivery 而非 source.platform 授权 relay 事件（#52306）、`d33516483` inbound 走 connector 强制 upstream authz；**/learn**——`e32ebc6aa` 从描述蒸馏可复用 skill（#51506）、`e62afaca6` 补全 CONTRIBUTING.md skill 标准（#52372）；**Providers / auth**——Z.AI endpoint picker、named custom providers + Z.AI 过载重试、`736e981ab` `NOUS_INFERENCE_BASE_URL` 覆盖（#52270）、`2ee6449fe` anthropic OAuth 改走 `platform.claude.com`。patch apply：**全部 clean apply**——35 个 patched files 从 `local-patches.diff` 干净落到新基线 `d6269da7`，无 3-way、无冲突；尽管上游给 `gateway/run.py` +331 行（scale-to-zero）、`session.py` +52、`prompt_builder.py` +19、`doctor.py` +12，本地 hunk 仅行号漂移；PATCH-1/2/6/7/9/10/11/12/13 仍活跃、PATCH-3 上游 completion 语法仍 canonical（no-fix）、PATCH-4/5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `d6269da7`。依赖：本轮 `uv` 未触发 python-path mismatch，clean 安装无 fallback；2 个 lazy backend 刷新（dingtalk、teams）；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `hermes-agent/package-lock.json`；Skills mirror **+0 / ~0 / -4**。已知摩擦：`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`（脚本已告警）。配置漂移：无 schema migration，doctor `Configuration is up to date`、All checks passed；Gateway 经 stop→start 重启加载补丁，service loaded，PID `26464`，`LastExitStatus=0`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| v0.17.0            | 2026-06-23 | 基线滚动到上游 `5ecf3bf0`（较 `bb7ff7dc` 前进 5 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**Agent / Gateway RPC**——`af7b7f632` 暴露 coding-context project facts 为结构化数据并新增 `project.facts` RPC（#51259），`211ba9c7d` 新增 one-shot LLM helper 与 `llm.oneshot` gateway RPC（#51261）；**Relay**——`45bc4fb37` 向 connector 声明 relevance policy，并补充 relay management plane contract 文档（#51248）；**Slack**——`219658416` 支持转录 Slack in-app voice message 的 `audio/mp4`，`5ecf3bf0e` 为重路由 voice clips 报告扩展名匹配出的 audio mimetype。patch apply：**全部 clean apply**——33 个 patched files 从 `local-patches.diff` 干净落到新基线 `5ecf3bf0`，无 3-way、无冲突；PATCH-1/2/7/9/10/11/12 行为化验证通过、PATCH-4/5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `5ecf3bf0`。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本显式 `--python venv/bin/python` fallback 自愈（日志中先失败 2 次）；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `hermes-agent/package-lock.json`；Skills mirror **+0 / ~0 / -3**。已知摩擦：`uv` python-path mismatch 每轮复发靠 fallback 兜底；`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`（脚本已告警）。配置漂移：无 schema migration，`config.yaml` 仍为 v30（doctor `Config version up to date`）；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效与若干可选 API key 未配置；Gateway 经 stop→start 重启加载补丁，service loaded，PID `76156`，`LastExitStatus=0`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| v0.17.0            | 2026-06-23 | 基线滚动到上游 `bb7ff7dc`（较 `f1e6d39a` 前进 52 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**安全 / Dashboard**——限制 dashboard plugin backend import 只能加载 bundled plugins（#43719）、集中非 bundled plugin source 常量、TUI/gateway approval prompt 发送前 redact 凭据（#48456）、media delivery 拒绝 root-level credential stores、git checkout/container 环境允许 dashboard updates（#51005）；**Desktop**——修 floating composer portal/clamp/out-of-bounds，新增长线程 timeline rail，tool preview 进入 composer status stack，补 preview rail toggle / open-in-browser，并柔化 inline code 与 expanded tool chrome；**computer-use**——新增 whole-screen/desktop capture target，cua-driver vision capture 改走 `get_window_state`，跨平台 preflight（win/linux）、macOS permission preflight 面板、`stdin=DEVNULL` 与 cua-driver >=0.5.x capture 修复；**Memory / Goals / Cron**——Honcho OAuth desktop + CLI connect/token refresh（#44335），no-agent memory char limit 与 `/memory approve` fresh-store 修复，`/goal` evidence-based completion contracts（#50501），background-review aux-model selector（#49252），cron profile execution 修复后又按 #51116 回退 job storage 到 per-profile；**工具 / 平台 / Skills**——`file_tools` 按 profile home 解析 `~`（#48552），新增 cloudflare-temporary-deploy optional skill（#50849），image/video schema delivery instruction 平台中性化（#51031），Telegram stale topic binding prune，Discord 100-command sync limit 清理，agent 最后一轮 final text 补全。patch apply：**全部 clean apply**——33 个 patched files 从 `local-patches.diff` 干净落到新基线 `bb7ff7dc`，无 3-way、无冲突；PATCH-1/2/7/9/10/11/12 行为化验证通过、PATCH-4/5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `bb7ff7dc`。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本显式 `--python venv/bin/python` fallback 自愈（日志中先失败 2 次）；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `hermes-agent/package-lock.json`；Skills mirror **+0 / ~0 / -3**。已知摩擦：`uv` python-path mismatch 每轮复发靠 fallback 兜底；`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`（脚本已告警）。配置漂移：无 schema migration，`config.yaml` 仍为 v30（doctor `Config version up to date`）；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效与若干可选 API key 未配置；Gateway 经 stop→start 重启加载补丁，service loaded，PID `46146`，`LastExitStatus=0`。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| v0.17.0            | 2026-06-23 | 基线滚动到上游 `f1e6d39a`（较 `b1b20270` 前进 5 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**computer_use**——`cua-driver` 遥测默认关闭、改为显式 opt-in（#50842）；**Slack**——尊重文档化的 `mention_patterns` 唤醒词、补 csv mention pattern fallback（salvaged fix + `AUTHOR_MAP`）；**Delegation**——高并发成本告警每进程只发一次（#50848）。5 个 commit 均未触及 Feishu / 本地 patch 区域。patch apply：**全部 clean apply**——28 个 patched files 从 `local-patches.diff` 干净落到新基线 `f1e6d39a`，无 3-way、无冲突。**本轮在升级前于本会话优化 PATCH-10 assistant-mode 文案**：身份统一为「琛哥的赛博小助手『木马牛』」；新增自我介绍节流——`_format_channel_context` 不再丢弃 bot 自身历史消息、改标注 `木马牛 (assistant, you)`，prompt 据此规定近 ~10 条 / ~5 分钟内已自我介绍则不再重复；新增风控话术——遇沙箱拦截/不允许操作时不以「能力不足」道歉，而是自然说明这是琛哥有意设计的安全边界（护机密、防照搬）并引导找琛哥。经脚本 save→revert→reapply 验证三处改动 reapply 后仍在——幂等成立；PATCH-1/2/7/9/10/11/12 行为化验证通过、PATCH-4/5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `f1e6d39a`，`tests/gateway/test_feishu.py` 207 passed。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本用 `--python venv/bin/python` fallback 自愈（"Install recovered via explicit --python fallback"）；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `package-lock.json`；Skills mirror **+0 / ~0 / -1**。已知摩擦：`uv` python-path mismatch 每轮复发靠 fallback 兜底；`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`（脚本已告警）。配置漂移：无 schema migration，`config.yaml` 仍为 v30（doctor `Config version up to date`）；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效与若干可选 API key 未配置；Gateway 经 stop→start 重启加载补丁，service loaded、running。                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| v0.17.0            | 2026-06-22 | 基线滚动到上游 `b1b20270`（较 `9bf9a9f1` 前进 81 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**Memory / Compaction**——`MemoryManager` 接口收口 write-mirror gating、write 结果不明时 fail-closed、mem0 v3 API（OSS mode + update/delete tools，#15624）、OpenViking memory write gating + `viking_forget` + shutdown drain mirror workers；compaction 阈值内预留 output tokens（#23767）、defer preflight compaction 到真实用量、token-only 压缩进度检测与 tail-budget 估算修正。**Gateway / Delivery**——approval prompt 发送前 redact 凭据（#48456）、chunking adapter flag 化并去掉 env-var knob、cron 输出截断可配置且 adapter-aware、Windows 安装态 gateway 更新后 cold-start（#50804）。**Desktop**——Windows 设 AppUserModelID 使通知生效（#50808）、chat 内 PR-style file diff（Shiki 高亮）、composer model picker 修复。**computer_use**——跨平台 cua-driver（macOS/Windows/Linux）+ 探测 cua-driver-rs release tag。**CLI / Cron / Relay**——`/goal wait <pid>`（#50503）、`/timestamps` 命令与 `/history` 时间戳（#50506）、cron per-job 叠加 enabled MCP servers/toolsets、relay self-provision 稳定 instance id 与 WS passthrough_forward；`fix(update)` 不再跨 shallow-clone 边界误算 commits-behind（#50784）。patch apply：**全部 clean apply**——28 个 patched files 从 `local-patches.diff` 干净落到新基线，无 3-way、无冲突；即便上游 `e9cd8c5bf fix(delivery)` 改了 `plugins/platforms/feishu/adapter.py`，与本地 hunk 不在同区域、锚点未漂移。**本轮新增 PATCH-12**（Feishu 回复不再创建话题、始终普通引用回复）于升级前在本会话加入，经脚本 save→revert→pull(81 commits)→reapply 全流程 clean apply，并由新加的 Step 8b sentinel（grep `reply_in_thread = False`）验证 active——幂等成立；PATCH-1/2/7/9/10/11/12 全部行为化验证通过、PATCH-4/5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `b1b20270`，`tests/gateway/test_feishu.py` 207 passed。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本 step 3 用 `--python venv/bin/python` fallback 自愈（"Install recovered via explicit --python fallback"）；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `package-lock.json`；Skills mirror **+1 / ~1 / -3**。已知摩擦：`uv` python-path mismatch 每轮复发靠 fallback 兜底；`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`（脚本已告警）；本轮 patch 全程 in-script clean apply，无需手工 remap。配置漂移：无 schema migration，`config.yaml` 仍为 v30（doctor `Config version up to date`）；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效与若干可选 API key 未配置；Gateway 经 Step 8d stop→start 重启加载补丁，service loaded，PID `62183`，`LastExitStatus=0`，Feishu WS 重新连上                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| v0.17.0            | 2026-06-22 | 基线滚动到上游 `9bf9a9f1`（较 `1b7b4d13` 前进 266 commits，release tag 维持 `v0.17.0 (2026.6.19)`，同 release 内迭代）。上游主线：**Gateway / 平台架构**——`refactor(gateway)` `560010547` 把 slack/dingtalk/whatsapp/matrix/**feishu**/telegram/wecom/email/sms 适配器整体迁移为 bundled plugins（`gateway/platforms/*.py` → `plugins/platforms/<p>/adapter.py`），并把 cron namespace-collision 修复推广到所有迁移适配器；新增 typed send-error 分类（`SendResult.error_kind`）、runtime `active_agents` 跟踪与 `/api/status` busy/drainable。**Kanban**——单写者 dispatch 锁防 orphan-dispatcher DB 损坏、reclaim claim-lock-aware、worktree 任务锚定/复用、task lifecycle plugin hooks、worker/orchestrator skill 折叠为注入式 guidance。**Compression**——最小上下文即触发 auto-compaction、`protect_first_n` 衰减、auth 失败中止而非降级轮换、跨轮 goal/platform/session 索引保留。**安全**——`HERMES_TIMEZONE` shell 注入封堵、smart approval guard 抗 prompt 注入、IPv6 scope / 空 WS peer fail-closed、snapshot restore 路径穿越校验、kanban payload secret redaction。**模型 / 接入**——新增原生 Antigravity OAuth provider（`google-antigravity` ProviderProfile）、mem0 self-hosted、`feat(delegation)` 后台 fan-out 并行子 agent、完整西班牙语 i18n；Telegram/Signal/WhatsApp/Desktop 大量投递与 UI 修复。patch apply：**关键**——上游 `560010547` 把 `gateway/platforms/feishu.py` 迁移为 `plugins/platforms/feishu/adapter.py`，脚本单体 diff 因该文件在 index 中 missing 整体 apply 失败、补丁被回退（脚本告警“Local patches were NOT applied”）；改为手工分步回贴——26 文件 `git apply --3way` clean，`tests/gateway/feishu_helpers.py` import 冲突解决（采上游新插件路径 `plugins.platforms.feishu.adapter` + 补 `gateway.config.Platform`），PATCH-10 的 19 个 feishu hunk 经路径改写后 `git apply` 干净落到 `adapter.py`，另修 5 处 PATCH-10 测试残留的旧 import；`PATCHED_FILES`、脚本 `FEISHU_PY` 与 `PATCHES.md` 文件清单同步把 `gateway/platforms/feishu.py` 改为 `plugins/platforms/feishu/adapter.py`；PATCH-1/2/7/9/10/11 全部行为化验证通过、PATCH-4/5 仍由上游 sentinel 覆盖；28 个 patched files 留在内层 `hermes-agent` modified，`local-patches.diff` 与 `.local-patches.base` 刷新到 `9bf9a9f1` 并通过 clean worktree apply 校验；重点回归 Feishu/config/session/skills 等 590 个测试通过。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本 step 3 用 `--python venv/bin/python` fallback 恢复；脚本结尾 doctor/gateway 阶段的 interrupted-install auto-recovery 仍走上游 uv 路径连报失败，手动 `venv/bin/python -m pip install -e ".[all]"` 成功后清掉 `.update-incomplete` marker；`npm audit fix` 报 no vulnerabilities 但仍改动 tracked `package-lock.json`；Skills mirror **+0 / ~6 / -19**。已知摩擦：本轮 in-script patch 回贴因平台→插件迁移整体失败、改为手工 remap（已写进 `PATCHES.md` PATCH-10）；`.update-incomplete` marker 的 auto-recovery 仍走 uv 老路复发，需手动 pip 兜底；`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`。配置漂移：`config.yaml` 仍为 v30（doctor `Config version up to date`）；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效与若干可选 API key 未配置；Gateway 已 stop→start 重启以加载手工回贴的 patch，service loaded，PID `77275`，`LastExitStatus=15`（restart stop 的上一轮退出码），Feishu WS 重新连上 |
| v0.17.0            | 2026-06-20 | 基线滚动到上游 `1b7b4d13`（较 `df4ca2c5` 前进 155 commits，release tag 跳到 `v0.17.0 (2026.6.19)`）。上游主线：Desktop/TUI 修 slash exec dispatch 与远程显示 GPU 提示，Desktop 增加 Restart gateway、日志可选择、notification resume 与 provider/account 目录统一；Gateway 增加 Raft/Teams/Signal 能力、Telegram topic rename、model picker 持久化、Windows restart 修复、session resume/restart loop 修复；Cron 引入 provider/Chronos/NAS fire webhook 与 env sanitize；MCP late-connecting tools、elicitation 与 short-TTL keepalive 修复；Managed scope 增加 config/env 覆盖与写保护；Dashboard 增加 session switcher、reasoning effort、sidecar session 隐藏；Skills 调整 creative-ideation v2.1，移除 html-artifact 并新增 sketch/architecture/concept-diagrams；模型/TTS 增加 xAI TTS 参数、speaker_id 与 `/model` 持久化。patch apply：脚本首次 apply 因上游 `session_context.py` 新增 `_SESSION_SOURCE` 导致 PATCH-10/11 相关 hunk 冲突，已用 `git apply --reject` 手工回贴；最终 28 个 patched files 全部在内层 `hermes-agent` 保持 modified，`local-patches.diff` 与 `.local-patches.base` 刷新到 `1b7b4d13`；重点回归 590 个相关测试通过。依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，脚本用 `uv pip install --python venv/bin/python -e ".[all,feishu]"` fallback 恢复；随后手动 `venv/bin/python -m pip install -e ".[all]"` 成功，`.update-incomplete` marker 已清理；`npm audit fix` changed 1 package 并改动 tracked `package-lock.json`（apps/desktop version `0.15.1 → 0.17.0` 及 peer 标记清理）；Skills mirror **+3 / ~6 / -18**。已知摩擦：`package-lock.json` 仍 dirty 且不纳入 `local-patches.diff`，脚本已告警。配置漂移：config 仍为 v30；doctor 剩 `ALIBABA_CODING_PLAN_API_KEY` 无效；Gateway 已重启并加载手工回贴的 patch，service loaded，PID 5680，`LastExitStatus=15`（restart stop 的上一轮退出码）                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| v0.16.0            | 2026-06-19 | 基线滚动到上游 `df4ca2c5`（较 `28d887ca` 前进 34 commits，release tag 维持 `v0.16.0 (2026.6.5)`，同 release 内迭代）。上游主线：Agent 对非重试 API 错误做摘要化并新增 model picker refresh；`image_generate` 支持 image-to-image / editing；Relay hosted gateway inbound/outbound round-trip 修复；gateway 进程内阻止调用 gateway 生命周期命令；TUI pending input 命令经 `command.dispatch`，hosted dashboard chat `/exit` / idle exit 修复；Slack allowed users setup 增加字段和 wildcard 校验；OpenViking structured sync / tool_input 扫描重构；backup 排除可再生依赖/cache；Nix npm deps 支持 hashless lock；新增 html-artifact skill 并合并 sketch / architecture-diagram / concept-diagrams。patch apply：28 个 patched files clean apply，PATCH-1/2/7/9/10/11 全部通过 Step 8b 验证，PATCH-4/PATCH-5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `df4ca2c5`，Feishu `file_readonly` / 群聊 wiki 只读能力仍可通过 patch 找回并通过 clean worktree apply 校验。依赖：`uv` python-path mismatch 仍由 `--python venv/bin/python` fallback 自愈；`python-multipart 0.0.20 → 0.0.27`；`npm audit fix` 报 no vulnerabilities 但仍修改 `package-lock.json`（`dompurify 3.4.10 → 3.4.11` 及 peer 标记清理）；Skills mirror **+13 / ~4 / -9**。已知摩擦：`package-lock.json` 仍是 dirty 且不进入 `local-patches.diff`，脚本已告警；Gateway 重启成功，PID 18156，`LastExitStatus=0`。配置漂移：无 schema migration，config v30；`display.show_reasoning=false` 仅关闭前端 thinking/reasoning 展示；`hermes doctor` 只剩 `ALIBABA_CODING_PLAN_API_KEY` 健康检查噪音                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| v0.16.0            | 2026-06-19 | 基线滚动到上游 `28d887ca`（较 `ef4b897a` 前进 51 commits，release tag 维持 `v0.16.0 (2026.6.5)`，同 release 内迭代）。上游主线：CLI 新增 Hermes worktree 锁与 session-store warning；Agent FTS 缺少 trigram tokenizer 时回退并重建 base FTS；Gateway/Relay 推进 WS-only inbound、self-provision、compression/resume/session-rotation 修复；Dashboard/Desktop/TUI 修 DS Button、chat TUI argv、Hindsight memory provider、session delete 幂等与 slash completion；Prompt 增加 per-platform hint override，Memory 增加 single-turn batch operations，新增 `/billing` TUI/CLI 与 Unreal Engine 5.8 MCP catalog；Skills rmtree guard 与 PowerShell/nix/install/cua-driver 安全修复。patch apply：28 个 patched files 从 `local-patches.diff` clean apply，PATCH-1/2/7/9/10/11 全部通过 Step 8b 验证，PATCH-4/PATCH-5 仍由上游 sentinel 覆盖；`local-patches.diff` 与 `.local-patches.base` 刷新到 `28d887ca`。依赖：`uv` python-path mismatch 仍由 `--python venv/bin/python` fallback 自愈；`npm audit fix` +1/-1/~2 packages，清掉 `ui-tui` 漏洞；Skills mirror **+0 / ~0 / -2**。已知摩擦：`npm audit fix` 修改 tracked `hermes-agent/package-lock.json`，但该文件不进入 `local-patches.diff`，脚本已新增显式告警，后续如要工作树完全干净需单独设计 lockfile 策略。配置漂移：无 schema migration；`hermes doctor` 只剩 `ALIBABA_CODING_PLAN_API_KEY` 健康检查噪音                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| v0.16.0            | 2026-06-18 | 基线滚动到上游 `ef4b897a`（较 `4eb0ff63` 前进 283 commits，release tag 维持 `v0.16.0 (2026.6.5)`，同 release 内迭代）。上游主线：**Gateway / Relay**——新增 relay adapter/transport、descriptor negotiation、signed HTTP inbound、token-less follow_up、`/stop` interrupt channel，并让 docker supervised gateway 用 `--replace` 接管 stale holder（#48147 #48242 #47555）；gateway 消息时间戳改为 opt-in、WhatsApp/email `send_image` 接受 metadata、Slack `/debug` 经 `/hermes` 路由。**Desktop / Dashboard**——composer model picker 移到 composer，per-model effort/fast presets，compact/scratch windows，subagent activity watch window，interleaved reasoning/content stream part coalescing，Electron 安装/打包自愈，dashboard file upload 改 multipart、Chat tab session end 后恢复、status profile scoping 修复（#46909 #47663 #47674 #48091）；二次收敛追加 desktop before-quit 时释放 open PTY sessions。**模型 / Auth**——xAI 默认切到 `grok-build-0.1` 并加入 `grok-composer-2.5-fast`，native web_search 只在 swap-only 场景启用；generic provider live+curated catalog merge 修复；Codex auth 429 retry 与 cache-routing headers 恢复；Minimax reasoning extra_body 走 profile；Anthropic OAuth MCP tool 名统一 `mcp__`。**Skills / Memory / Prompt**——skills 新增 user-modified bundled skill `list-modified` / `diff` 路径并清理 diff contract，shop skill 替换 shop-app，skill delete 防 tree-escape，OpenViking memory setup/权限/会话切换 race 大量修复；prompt context-file truncation limit 可配置并按模型窗口缩放。**安全 / 运维**——install-method stamp 限定到 code tree，hosted Docker install tree 防自修改，API request debug dump redact secrets，cron jobs.json 跨进程安全写，disk cleanup 避免 brittle protected walk；Langfuse trace state 按 turn/request scope 并限制非 finalizing turn 增长。**TUI / MCP**——二次收敛追加 MCP discovery 后刷新 tool snapshot、headline counts 仅统计 connected servers。patch apply：7 文件通过 3-way merge 回贴，**无冲突**；PATCH-1/2/7/9 仍活跃，PATCH-4/PATCH-5 继续由上游实现覆盖、仅保留 sentinel；`hermes_cli/doctor.py` 锚点 `2095 → 2096`，`pyproject.toml` `215 → 238`，`tools/skill_manager_tool.py` `269 → 343` / `527 → 611` / `708 → 816`，其余主要为 index hash 与行号漂移。依赖：`uv` 首次安装仍因 `/Users/chenzhou/.local/share/uv/python` 报 python-path mismatch，脚本用 `--python venv/bin/python` fallback 自愈；venv 回贴后 `python-multipart 0.0.29 → 0.0.20`、`websockets 16.0 → 15.0.1`；`npm audit fix` +106 / -236 / ~240 packages，doctor 中 web/ui-tui 漏洞清零；Skills mirror 首轮同步 **+0 / ~1 / -11**，二次收敛追加 **-1**。已知摩擦：升级前额外的 `hermes-agent/package-lock.json` 本地改动被脚本存为 `stash@{0}: hermes-update-extra-20260618-200048`，未自动合并，需另行判断是否恢复；`patches/.local-patches.base` 与 `local-patches.diff` 已刷新到新基线；Gateway 已重启，PID 43305，`LastExitStatus=0`。配置漂移：后续已运行 `hermes doctor --fix`，`config.yaml` 迁移到 `_config_version: 30`；`ALIBABA_CODING_PLAN_API_KEY` 仅用于 `provider: alibaba-coding-plan`，当前配置使用 `provider: alibaba` + `DASHSCOPE_API_KEY`，不依赖该 key，若不用 Coding Plan 可保留为未配置/健康检查噪音                                                                                                                  |
| v0.16.0            | 2026-06-15 | 基线滚动到上游 `4eb0ff63`（较 `d62979a6` 前进 223 commits，release tag 维持 `v0.16.0 (2026.6.5)`，同 release 内迭代）。上游主线：**安全收紧**——MCP stdio 配置在 probe 前先 block 可疑 / exfil 形态（#46083 #46112）、`cp/mv/install` 写入 `~/.ssh` / credential / shell-rc 全面 gate（`da28d5d1`）、`agent/gateway/doctor` 加 SSL CA bundle fail-fast guard 并在 provider 调用前 validate CA bundle 路径（`a218a0f1` / `af5b526`）。**Skills 加速 & 一致性**：skills util 共享 raw config 缓存（#46149）、global/platform disabled skills 在所有 resolution site 做 union（#46201 + `ce19fdb7`）、bundled-update backup 处理改 crash-safe / idempotent 并补回归测试（`3581131e` / `9a2b9763`）。**Gateway 鲁棒性**：early duplicate guard 缩到 pid file 级别（`7433d5f0`）、shell `gateway run` 在 service 已托管 profile 时拒启动（`14367930`）、interrupted replay 不再重放 tool-call 尾巴并自动 continue（`5191c1c2` / `2c174bce`）、agent-cache 在 cross-process session 写后失效（#45966）、每轮重新 baseline `message_count`（`3bc4a2ff`）、startup auto-resume 在 inbound 前串行化（`10bad2fa`）、reply 媒体附件被正确带上（#46107）。**Desktop**：native OS notifications + per-type toggle（`630a4ef`）、auto-compaction 期间显示 summarizing 指示器（`715b691`）、dashboard restart 去掉 `is_container` 检查（#46290）。**模型 picker**：Kimi K2.7 Code（#46309）、Z.AI GLM-5.2 + verified 1M ctx（`bff78a34`）。**Email**：465 端口走 `SMTP_SSL`、超时退回 IPv4（`cf7d5932` / `04d4471`）。**Web revert**：keyless Parallel search fallback 移除（#46350）。**Profile clone**：自动迁移 config（#46345）。patch apply：7 文件全部 clean apply / 3way 干净，**无冲突**——PATCH-2 `hermes_cli/doctor.py` 锚点 `2025 → 2095` 自动 rebase（`905ed413` / `a5e9b17c` 重写 npm audit 推荐 + `a218a0f1` 加 SSL CA bundle guard，把 PATCH-2 区域整体下移），PATCH-7 `pyproject.toml` 锚点 `214 → 215` 漂移。依赖：venv `hermes-agent` 重装 + `certifi 2026.4.22 → 2026.5.20`；`npm audit fix` 仍报 `web` / `ui-tui` 各 2 个 build-tool 高危（npm arborist crash 已知 bug，待上游 lockfile bump 自然清，doctor 已附说明）；Skills mirror 同步：+0 / ~2 / -3（上游趋稳）。`hermes doctor` 报 `Config version up to date (v29)`——上游 schema 无新增，无需 `--fix` 迁移。已知摩擦：`uv` python-path mismatch 仍触发两次，均由 `--python venv/bin/python` fallback 自愈；Gateway Step 6 首启 PID 45882 → Step 8d 重启 PID 50875，`LastExitStatus=0`，OnDemand=false，launchd `Bootstrap failed: 5` 不复现                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| v0.16.0            | 2026-06-12 | 基线滚动到上游 `d62979a6`（较 `d02a59b6` 前进 492 commits，release tag 维持 `v0.16.0 (2026.6.5)`，同 release 内迭代）。上游主线：Desktop App composer status stack / live subagent windows / editable prompts（#44630）；billing `/credits` 命令 + portal top-up handoff（#44776）+ `display.credits_notices` 节流（#44716）；CLI approval/clarify/sudo/secret modal 持久化到 scrollback（#44702）+ 改成直接绘制（#41098）；Photon 升级 spectrum-ts 3.0/3.1、agent-facing 表情反应、telemetry toggle、sidecar 复活；新增 `hermes sessions repair` 修 `state.db` 隐藏会话（#43149）；新增 `hermes whatsapp-cloud` WhatsApp Business Cloud API（#43921，含 review 跟进 #52c7976f4）；Yuanbao 支持 WeChat 转发；gateway 为 SimpleX/Email/Signal 文档类附件正确分类、PDF/DOCX 引导直读；**关键**：`fix(gateway): probe launchd domain instead of hardcoding user/<uid>`（#40831，commit `a8f404b29`）——彻底修掉 macOS 26 上 `hermes gateway restart` → `launchctl bootstrap exit 5` 反复刷 `vertex-refresh.err.log` 的报错，本次 update 后 vertex 50min 定时刷新链路（SIGUSR1 planned restart）一次跑通，不再走 launchctl bootout/bootstrap 兜底；refactor god-file Phase 3b/4：gateway 42 + CLI 32 slash-command handlers 抽进 mixin；end-of-turn memory sync 移出 turn 线程（#41945）；Honcho env fallback + `HERMES_MAX_ITERATIONS` ghost shadowing 检测/修复；nix cold-build / fix-lockfiles 流水线巩固。patch apply：7 文件全部 clean / 3way 干净，**无冲突**——PATCH-2 `hermes_cli/doctor.py` 锚点 `1971 → 2025` 自动 rebase（god-file Phase 4 抽方法），diff 仅 index hash 改动。依赖：venv 升级 `aiohttp 3.13.3 → 3.13.4`、`packaging 26.2 → 26.0`、`pyjwt 2.12.1 → 2.13.0`；`npm audit fix` +21/-14/~3 packages；Skills mirror 同步：+0 / ~16 / -42。`hermes doctor` 报 `Config version outdated (v28 → v29)`——上游新增 `agent.coding_context`、`auxiliary.{monitor,tts_audio_tags}`、`display.{persist_prompts,credits_notices}`、`tts.gemini`、`memory.write_approval`、`max_concurrent_sessions`，`hermes doctor --fix` 一键迁移完成                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| v0.16.0            | 2026-06-08 | 基线滚动到上游 `d02a59b6`（较 `a6b6afdff` 前进 699 commits，release tag 跳到 `v0.16.0 (2026.6.5)`，跨版本 v0.15.1 → v0.16.0）。上游主线：Hermes Desktop App 持续迭代（installer 改名「Hermes」做 launcher #37516、Codex OAuth 持久化路径对齐 #37517、renderer bundle 缺失时显式失败 #41729、asar 解包 dist/ 以让 dashboard 静态文件可被服务、sidebar drag 顺序持久化、Shift+click 状态栏 zap 切换 YOLO、collapsed sidebar hover-reveal 浮层 #41670、content-hash build stamp + `--build-only` / `--force-build` 标志）；dashboard nous-blue 主题 + bulk sessions + schedule picker（#37383）；observability NeMo-Relay 插件；packaging 全面迁移（PEP 639 SPDX `project.license`、`requires-python<3.14`、`UV_PYTHON` pin venv、locales/ i18n 打包入 wheel/sdist/Nix）；`Pillow` / `markdown` 提升为核心依赖（即装即用 rich 渲染 + vision 预先 cap 像素）；doctor 新增 Honcho env fallback + 检测/修复 `HERMES_MAX_ITERATIONS` ghost shadowing；api_server `/health` 报 hermes 版本；nix cold-build / fix-lockfiles 流水线。patch apply：7 文件全部 clean apply / 3way 干净，**无冲突**（`5a36f76a0` 触动 `_validate_file_path` 与 PATCH-1 `_resolve_skill_dir()` 是不同 hunk，3way 干净）；依赖：venv 重建后 `markdown==3.10.2`、`pathspec==1.1.1`、`pillow==12.2.0` pull 到 base，`npm audit fix` +109/-52/~13 packages；Skills mirror 同步 **+3 / ~16 / -168**（上游大规模收敛 skills 集合，本地通过 `rsync --delete` 自动跟齐）；`uv` python-path mismatch 仍由 `--python venv/bin/python` fallback 恢复。Gateway 在 launchd `Bootstrap failed: 5`（macOS 26.5 launchctl 退化）下回退到「直接 background python 子进程」启动成功；`hermes doctor` 报 `Config version outdated (v23 → v28)`，需运行 `hermes doctor --fix` 或 `hermes setup` 迁移                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| v0.15.1            | 2026-06-03 | 基线滚动到上游 `a6b6afdff`（较 `b288de8bf` 前进 823 commits，release tag 跳到 `v0.15.1 (2026.5.29)`，跨版本 v0.14.0 → v0.15.1）。上游主线：Hermes Desktop App 合入（PR #20059）+ first-launch install / session search / 模型管理重构；gateway streaming protocol 结构化 + per-platform 默认开关；docker s6 lifecycle 完整化（PID-1 守护、unprivileged user）；packaging 修复（CVE-2026-48710 Starlette `>=1.0.1`、`hermes_cli` 子包入 wheel、`mcp_serve` 入 py-modules）；dashboard 全功能化（Channels page、admin panel、refresh-token 旋转）+ TUI `/model` + Sessions overlay 统一；`MESSAGING_CWD` 弃用改 `terminal.cwd`。patch apply：5 文件 clean apply，1 文件 3way 干净，1 文件 3way 冲突手工合并（`migrate-from-openclaw.md`：上游 `119390a2a` 改 Working directory 行与 PATCH-9 删 Gateway auth token 行相邻冲突）；依赖：`starlette 1.0.0 → 1.0.1` + 新增 `setuptools==82.0.1`；`uv` python-path mismatch 仍由 `--python venv/bin/python` fallback 恢复；Skills mirror 同步 +0 / ~17 / -18；npm audit clean。**脚本修复**：Step 7 末尾 `rm -f ~/.zcompdump*` 撞到空目录残留时 `set -e` 中断脚本、导致 Step 8/9 全跳过，已改用 `find` 只删文件、忽略目录                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| v0.14.0            | 2026-05-25 | 基线滚动到上游 `b288de8bf`（较 `3bace071b` 前进 96 commits，版本字符串仍为 `v0.14.0 (2026.5.16)`）。上游重点：Docker / container runtime 迁移到 s6-overlay 监督并强化多架构/CI；credential 与 file-safety 继续收紧（OAuth、pairing、session capture 等）；CLI / gateway 修复 resume 编号选择、resume recap、Telegram topic/reconnect、Matrix E2EE、plugin extras 连接门控；TUI skinny status rule 修复。`hermes-update.sh` 成功走 uv `--python venv/bin/python` fallback；`local-patches.diff` 干净 apply 并刷新 7 个文件，PATCH-1/2/7/9 全部活跃；PATCH-3 sentinel 未触发；Skills mirror 同步 +1 / ~1 / -9；sandbox verify、doctor、gateway status 均通过                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| v0.14.0            | 2026-05-24 | 基线滚动到上游 `3bace071b`（较 `d61785889` 前进 177 commits，版本字符串仍为 `v0.14.0 (2026.5.16)`）。上游主线集中在三类修复：(a) Feishu / QQBot / Discord / MS Graph / Dingtalk / Svix 全面收紧 webhook 鉴权 (#30200/#30737-46/#30169 等)；(b) gateway 流式响应路径修复 `response_transformed` 传播，确保 plugin `transform_llm_output` hook 输出不被流式吞掉（与 `plugins/sandbox` 一致受益）；(c) state store 文件权限收紧 (`3bace071b`)、`pydantic` 钉为 2.13.4 防 pydantic-core 线程 segfault。`local-patches.diff` 干净 apply（无 3-way），PATCH-1/2/7 全部活跃；唯一触碰 patch 范围的上游 commit `d3c167b64`（PR #31290，cross-profile soft guard）与 PATCH-1 在 `skill_manager_tool.py` 不同区域，直接 clean apply。`_hermes` 补全新增 `portal` / `tasks promote` 子命令；skills mirror 同步：4 个移除 / 2 个更新                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| v0.14.0            | 2026-05-22 | 基线滚动到上游 `d61785889`（较 `6a6766fb8` 前进 112 commits，版本字符串仍为 `v0.14.0 (2026.5.16)`）。**新增 `hermes-update.sh` uv-pyenv 兼容性 fallback**：在 uv ≥ 0.11 + pyenv 环境下 `hermes update` 内部的 `uv pip install -e .` 会因找不到 uv 自管 Python（`~/.local/share/uv/python` 不存在）报错；脚本现在通过 `tee` 捕获输出，识别该错误后自动重试 `uv pip install --python venv/bin/python -e ".[all,feishu]"`，成功则把 UPDATE_RC 清零。本次 update 沿用 PATCH-1/2/7（PATCH-3 上游已修复仍保留 sentinel）；pydantic 2.12.5 → 2.13.4 / pydantic-core 2.41.5 → 2.46.4；上游裁掉了 22 个 skill。Step 8e 的 sandbox verify 全绿通过                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| v0.14.0            | 2026-05-22 | 新增 `plugins/sandbox` 用户插件：通过官方 `pre_gateway_dispatch` + `pre_tool_call` 钩子，按 Feishu `chat_id` 做工具沙盒——配置中的 owner DM 拥有完整工具集，其他 Feishu 会话只剩 `web_search` / `web_extract` / `vision_analyze` / `image_generate`，非 Feishu 来源（CLI/TUI、cron、内部事件）不拦截。零源码修改。配套 `plugins/sandbox/verify.sh` 检查上游 hook 名 / fire site / 运行时 `active=True` 三项，`hermes-update.sh` Step 8e 每次官方更新后自动调用                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| v0.14.0            | 2026-05-20 | 新机恢复时克隆最新官方 `main` 到 `6a6766fb8`；按 `pyproject.toml` 的 `requires-python >=3.11` 选择本机 pyenv `3.12.7` 重建 venv；安装 `.[all,feishu]`；PATCH-7 扩展到 `tools/lazy_deps.py` 以覆盖 Feishu lazy install 路径；`hermes-update.sh` 改为用 `git stash push -u` 保护额外 untracked 改动                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| v0.14.0            | 2026-05-19 | 基线滚动到 `f1254b1bc`（较 `a0bd11d02` 再前进 13 commits）；`hermes update` 新增 post-pull 关键文件语法校验/失败自动回滚；`local-patches.diff` 干净 apply 并刷新基线；PATCH-1/2/7 继续活跃，PATCH-3/4/5/8 维持已上游合并状态                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| v0.13.0            | 2026-05-14 | 基线滚动到 `26933c2f5`（v0.13.0，194 commits）；PATCH-7 因上游将 feishu extra 改为版本钉死（`lark-oapi==1.5.3` + `qrcode==7.4.2`）触发 3-way 冲突，重写为 `python-socks==2.8.1`；PATCH-1/2 干净 apply；PATCH-3/4/5/8 维持已上游合并状态                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| v0.13.0            | 2026-05-12 | 基线滚动到 `99ad2d1372`（v0.13.0 仍是当前 release，174 commits 全是补丁修复）；`local-patches.diff` 干净 apply（无 3-way），仅 hunk 锚点行号漂移；PATCH-1/2/3/4/5/7 状态全部维持，PATCH-7 hunk 117→121 行漂动                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| v0.13.0            | 2026-05-10 | 上游 `main` 同步到 `44cdf555a`（release `v2026.5.7`，490 commits），3-way merge 干净落地；PATCH-3 经上游 commit `fe61d95b4` 合并并退役；继续保留 PATCH-1/2/6/7 + PATCH-3 sentinel                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| v0.12.0            | 2026-05-07 | 上游 `main` 同步到 `49c3c2e0d`（release 仍 `v2026.4.30`），patch 基线刷新；继续保留 PATCH-1/2/3/6/7                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| v0.11.0            | 2026-04-23 | 上游升级，新增 Ink TUI / transport 层 / Bedrock / GPT-5.5 / Dashboard 主题扩展                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| v0.10.0            | 2026-04-22 | 上游升级，新增 hooks / plugins / orchestrator 等功能                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| v0.9.0 (2026.4.13) | 2026-04-14 | 初始安装，从 OpenClaw 迁移                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
