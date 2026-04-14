# Hermes Agent — 本地配置仓库

> **这个仓库跟踪的是 `~/.hermes/` 下的个人配置文件，不包含官方源码（`hermes-agent/`）和密钥（`.env`）。**

---

## 目录

- [概述](#概述)
- [目录结构说明](#目录结构说明)
- [安装](#安装)
  - [前置条件](#前置条件)
  - [全新安装](#全新安装)
  - [从 OpenClaw 迁移](#从-openclaw-迁移)
- [配置](#配置)
  - [.env 密钥文件](#env-密钥文件)
  - [config.yaml 主配置](#configyaml-主配置)
  - [飞书集成](#飞书集成)
- [Gateway 服务](#gateway-服务)
- [Shell 集成](#shell-集成)
- [更新](#更新)
- [卸载](#卸载)
- [基础使用](#基础使用)
  - [对话（Chat）](#对话chat)
  - [会话管理](#会话管理)
  - [模型选择](#模型选择)
  - [Skills 技能包](#skills-技能包)
  - [Context References（@ 语法）](#context-references-语法)
  - [Cron 定时任务](#cron-定时任务)
- [知识库与记忆](#知识库与记忆)
- [维护与排错](#维护与排错)

---

## 概述

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是 NousResearch 开发的本地 AI 助手，支持工具调用、飞书/Telegram/Discord 等 IM 平台接入，以及 Cron 定时任务。

本仓库存储的内容：

| 文件/目录                | 说明                                           |
| ------------------------ | ---------------------------------------------- |
| `config.yaml`            | 主配置：模型、工具集、gateway 超时、显示风格等 |
| `.env.example`           | 密钥配置模板（实际 `.env` 不入库）             |
| `completions/hermes.zsh` | zsh 补全脚本                                   |
| `memories/MEMORY.md`     | Agent 的结构化记忆（短期），自动注入每次会话   |
| `memories/USER.md`       | 用户画像（偏好、时区、语言等）                 |
| `SOUL.md`                | Agent 人格与语气配置                           |
| `README.md`              | 本文档                                         |

**不跟踪的内容**：官方源码（`hermes-agent/`）、密钥（`.env`）、数据库（`state.db`）、日志、会话、Skills 包（171MB，按需重装）。

---

## 目录结构说明

```
~/.hermes/
├── hermes-agent/          # 官方源码 clone（独立 git repo，.gitignore 排除）
├── .env                   # 密钥（.gitignore 排除）
├── .env.example           # 密钥模板（入库）
├── config.yaml            # 主配置（入库）
├── SOUL.md                # Agent 人格（入库）
├── completions/
│   └── hermes.zsh         # zsh 补全脚本（入库）
├── memories/
│   ├── MEMORY.md          # 结构化记忆（入库）
│   └── USER.md            # 用户画像（入库）
├── skills/                # Skills Hub 包（.gitignore 排除，按需重装）
├── cron/                  # Cron 任务状态（运行时，.gitignore 排除）
├── logs/                  # 日志（.gitignore 排除）
├── sessions/              # 会话历史（.gitignore 排除）
└── state.db               # 内部状态数据库（.gitignore 排除）
```

---

## 安装

### 前置条件

| 依赖   | 版本要求 | 安装方式                                           |
| ------ | -------- | -------------------------------------------------- |
| Python | ≥ 3.11   | `brew install python@3.11` 或 `pyenv`              |
| uv     | 最新     | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| git    | 任意     | macOS 自带                                         |

### 全新安装

```bash
# 1. Clone 官方源码到 hermes-agent 子目录
mkdir -p ~/.hermes
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent

# 2. 创建虚拟环境（指定 Python 3.11）
uv venv --python 3.11 venv
source venv/bin/activate

# 3. 安装所有依赖
uv pip install -e ".[all]"

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

### 从 OpenClaw 迁移

Hermes 内置迁移工具，可自动导入 OpenClaw 的模型配置：

```bash
hermes claw migrate
```

> **已知 Bug（截至 v0.9.0）**：`hermes claw migrate` 对 `.env` 的写入有三处问题，迁移完成后**必须**手动校对：
>
> 1. `HERMES_GATEWAY_TOKEN` 会被写成 OpenClaw 内部序列化格式 `{'source': 'env', ...}`，需替换为实际 token 值
> 2. `GOOGLE_API_KEY=${GEMINI_API_KEY}` — dotenv 不展开变量，需替换为实际 key 值
> 3. `BAILIAN_API_KEY=${BAILIAN_API_KEY}` — 自循环引用，需替换为实际 key 值

**飞书迁移**（迁移工具不支持，需手动配置）：

```bash
# 将以下内容追加到 ~/.hermes/.env（从 ~/.openclaw/.env 复制实际值）
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=your_secret
FEISHU_DOMAIN=https://open.feishu.cn
FEISHU_CONNECTION_MODE=websocket
```

---

## 配置

### .env 密钥文件

**位置**：`~/.hermes/.env`（不入库，参考 `.env.example`）

```bash
# 从模板创建
cp ~/.hermes/.env.example ~/.hermes/.env
# 编辑并填入实际密钥
nano ~/.hermes/.env
```

当前使用的 provider 及其环境变量：

| Provider           | 环境变量                                | 说明                                                |
| ------------------ | --------------------------------------- | --------------------------------------------------- |
| Gemini（主模型）   | `GEMINI_API_KEY` / `GOOGLE_API_KEY`     | 两个变量需设为相同值                                |
| Qwen（备用模型）   | `BAILIAN_API_KEY` / `DASHSCOPE_API_KEY` | 两个变量需设为相同值                                |
| DashScope 国内端点 | `DASHSCOPE_BASE_URL`                    | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 飞书               | `FEISHU_APP_ID` / `FEISHU_APP_SECRET`   | 飞书开放平台获取                                    |
| Gateway 访问控制   | `GATEWAY_ALLOW_ALL_USERS=true`          | 个人 bot 必须设置，否则拒绝所有用户                 |

> **双 key 说明**：`GOOGLE_API_KEY` 是 hermes 内置 provider `gemini` 的识别变量；`GEMINI_API_KEY` 用于 doctor 检测。两者需保持同值。同理，`DASHSCOPE_API_KEY` 用于 doctor 检测，`BAILIAN_API_KEY` 用于 `custom_providers` 中的 `bailian` provider 引用。

### config.yaml 主配置

**位置**：`~/.hermes/config.yaml`

关键配置节说明：

```yaml
# 主模型
model:
  provider: gemini # 内置 provider 名称（非 google）
  default: gemini-2.5-pro

# 备用模型（主模型失败时自动切换）
fallback_model:
  provider: bailian # 对应 custom_providers 中的名称
  model: qwen3-max

# 自定义 provider（Qwen / DashScope）
custom_providers:
  - name: bailian
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key: "${BAILIAN_API_KEY}"
    api_mode: chat_completions
```

**常用配置项**：

| 配置项                   | 默认值 | 说明                        |
| ------------------------ | ------ | --------------------------- |
| `agent.max_turns`        | 90     | 单次 session 最大轮数       |
| `agent.gateway_timeout`  | 1800s  | Gateway 会话超时（30 分钟）  |
| `agent.reasoning_effort` | low    | 推理强度（low/medium/high） |
| `display.personality`    | kawaii | 显示风格                    |
| `approvals.mode`         | manual | 危险命令审批（manual/auto） |

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

## Shell 集成

zsh 补全脚本已生成在 `completions/hermes.zsh`。

**`.zshrc` 配置**（参考当前 `~/.zshrc`）：

```zsh
# Hermes Completion
if [[ -f "$HOME/.hermes/completions/hermes.zsh" ]]; then
  hermes_fpath="$HOME/.hermes/completions"
  if [[ -z "${fpath[(r)$hermes_fpath]}" ]]; then
    fpath=("$hermes_fpath" $fpath)
  fi
  autoload -Uz _hermes
fi
unset hermes_fpath
```

**更新补全脚本**（hermes 升级后）：

```bash
hermes completion zsh > ~/.hermes/completions/hermes.zsh
```

---

## 更新

```bash
# 1. 更新源码
cd ~/.hermes/hermes-agent
git pull

# 2. 更新 Python 依赖
source venv/bin/activate
uv pip install -e ".[all]"

# 3. 重新安装 gateway 服务（plist 嵌入版本路径，必须刷新）
hermes gateway install --force

# 4. 更新 zsh 补全脚本
hermes completion zsh > ~/.hermes/completions/hermes.zsh

# 5. 验证
hermes --version
hermes doctor
hermes gateway status
```

> **提示**：也可以使用内置命令 `hermes update`（需确认它支持从 git clone 安装的版本）。

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

### 模型选择

```bash
hermes model                 # 交互式选择默认模型
hermes model list            # 列出可用模型
```

**会话内切换**：`/model gemini-2.5-pro`

> ⚠️ **Thinking 模型注意**：`gemini-2.5-pro-preview` 等 thinking 模型在会话内通过 `/model` 切换后，thinking 标签可能污染上下文，引发 400 级联错误（hermes v0.9.0 已知 bug）。

### Skills 技能包

Skills 是 Hermes 的知识/工具扩展模块，按需加载，不常驻 context。

```bash
hermes skills list           # 列出 Skills Hub 中可用的 skills
hermes skills install devops # 安装 skill
hermes skills update         # 更新所有 skills

# 已安装的 skills（当前）：
# apple, autonomous-ai-agents, creative, data-science, devops,
# diagramming, dogfood, domain, email, feeds, gaming, gifs, github,
# inference-sh, leisure, media, mcp, mlops, note-taking, openclaw-imports,
# productivity, red-teaming, research, smart-home, social-media,
# software-development
```

**调用 Skill**：会话中输入 `/skill-name` 或启动时 `hermes --skills skill-name`。

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

## 知识库与记忆

Hermes 没有通用的 workspace 目录，而是按用途分层存储：

### 1. 短期记忆（自动注入）

- **位置**：`~/.hermes/memories/MEMORY.md`（配置/偏好，上限 2200 字符）
- **位置**：`~/.hermes/memories/USER.md`（用户画像，上限 1375 字符）
- **特点**：每次会话自动注入 system prompt，适合存储高频偏好和配置备忘
- **管理**：`hermes memory` 命令，或会话中直接叫 Agent 更新

### 2. Skills（按需知识库）

- **位置**：`~/.hermes/skills/<skill-name>/`
- **特点**：不常驻 context，只在调用时加载——**最适合存储操作手册、流程文档**
- **创建自定义 Skill**：在 `skills/` 目录下新建文件夹 + `DESCRIPTION.md` + 内容文件

### 3. 项目级上下文（自动发现）

- **位置**：项目目录下的 `AGENTS.md` / `.hermes.md` / `CLAUDE.md`
- **特点**：进入该目录时自动注入，支持多级目录逐层发现
- **上限**：20,000 字符，超出自动头尾截断

### 4. 按需注入（临时大文档）

- 对话中使用 `@file:` / `@folder:` / `@url:` 语法按需注入
- **不占用 system prompt**，适合大型参考文档

### 5. 全局人格（SOUL.md）

- **位置**：`~/.hermes/SOUL.md`
- **特点**：控制 Agent 人格与语气，每次会话加载

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

确认 `.env` 中设置了 `GATEWAY_ALLOW_ALL_USERS=true`，然后重启 gateway。

**会话出现 400 级联错误**：

通常由 thinking 模型污染 context 导致。参见 MEMORY.md 中的应急方案，或 `hermes sessions delete` 删除问题会话后重新开始。

**Skills Hub 初始化**：

```bash
hermes skills list   # 首次运行会初始化 Skills Hub 目录
```

**查看实时日志**：

```bash
hermes logs
tail -f ~/.hermes/logs/gateway.log
tail -f ~/.hermes/logs/hermes.log
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

| 版本               | 日期       | 说明                       |
| ------------------ | ---------- | -------------------------- |
| v0.9.0 (2026.4.13) | 2026-04-14 | 初始安装，从 OpenClaw 迁移 |
