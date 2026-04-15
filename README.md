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
- [记忆系统与个性化](#记忆系统与个性化)
  - [两个记忆文件](#两个记忆文件)
  - [记忆的工作原理](#记忆的工作原理)
  - [Agent 如何主动维护记忆](#agent-如何主动维护记忆)
  - [你能做什么：让它越用越懂你](#你能做什么让它越用越懂你)
  - [容量管理](#容量管理)
  - [Session Search：无限历史回溯](#session-search无限历史回溯)
  - [知识库存储层级](#知识库存储层级)
  - [SOUL.md：人格与语气](#soulmd人格与语气)
  - [外部记忆 Provider（进阶）](#外部记忆-provider进阶)
- [Web Search 工具](#web-search-工具)
- [Web Dashboard](#web-dashboard)
- [维护与排错](#维护与排错)

---

## 概述

[Hermes Agent](https://github.com/NousResearch/hermes-agent) 是 NousResearch 开发的本地 AI 助手，支持工具调用、飞书/Telegram/Discord 等 IM 平台接入，以及 Cron 定时任务。

本仓库存储的内容：

| 文件/目录             | 说明                                           |
| --------------------- | ---------------------------------------------- |
| `config.yaml`         | 主配置：模型、工具集、gateway 超时、显示风格等 |
| `.env.example`        | 密钥配置模板（实际 `.env` 不入库）             |
| `completions/_hermes` | zsh 补全脚本（#compdef 格式，通过 fpath 加载） |
| `memories/MEMORY.md`  | Agent 的结构化记忆（短期），自动注入每次会话   |
| `memories/USER.md`    | 用户画像（偏好、时区、语言等）                 |
| `SOUL.md`             | Agent 人格与语气配置                           |
| `README.md`           | 本文档                                         |

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
│   └── _hermes            # zsh 补全脚本（#compdef 格式，fpath 加载）
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
FEISHU_DOMAIN=feishu
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
| 飞书推送频道       | `FEISHU_HOME_CHANNEL`                   | cron / 通知默认投递的群或会话 ID                    |
| Gateway 访问控制   | `GATEWAY_ALLOW_ALL_USERS=true`          | 个人 bot 必须设置，否则拒绝所有用户                 |

**API Key 加载机制（官方设计）：**

Hermes 有两套独立的 key 读取路径：

1. **内置 Provider（gemini 等）**：Provider Registry 为每个内置 provider 定义了对应的环境变量名（`api_key_env_vars`），启动时直接从 `os.environ` 读取，**无需在 `config.yaml` 里引用**。把 key 写进 `.env` 即自动生效。
2. **自定义 Provider（`custom_providers`）**：需要在 `config.yaml` 里显式写 `api_key`。支持 `${VAR}` 插值——Hermes 解析配置时递归展开所有 `${VAR}` 为对应的环境变量值（变量不存在时保留字面量，调用会报鉴权错误）。

因此，`.env` 里写了但没出现在 `config.yaml` 里的变量（如 `GOOGLE_API_KEY`），仍然对内置 provider 完全有效。

> **双 key 说明**：gemini provider 按优先顺序读 `GOOGLE_API_KEY` → `GEMINI_API_KEY`，两者设为同值即可。`BAILIAN_API_KEY` 通过 `config.yaml` 的 `${BAILIAN_API_KEY}` 插值传给自定义 bailian provider；`DASHSCOPE_API_KEY` 用于 hermes doctor 健康检查，两者也应设为同值。

### config.yaml 主配置

**位置**：`~/.hermes/config.yaml`

关键配置节说明：

```yaml
# 主模型
model:
  provider: gemini # 内置 provider 名称（非 google）
  default: gemini-3.1-pro-preview

# 备用模型（主模型失败时自动切换）
fallback_model:
  provider: bailian # 对应 custom_providers 中的名称
  model: qwen3-max

# 自定义 provider（Qwen / DashScope）
custom_providers:
  - name: bailian
    base_url: ${DASHSCOPE_BASE_URL}
    api_key: ${BAILIAN_API_KEY}
    api_mode: chat_completions
```

**常用配置项**：

| 配置项                   | 默认值 | 说明                        |
| ------------------------ | ------ | --------------------------- |
| `agent.max_turns`        | 90     | 单次 session 最大轮数       |
| `agent.gateway_timeout`  | 1800s  | Gateway 会话超时（30 分钟） |
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
hermes completion zsh > ~/.hermes/completions/_hermes
rm -f ~/.zcompdump*

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

**会话内切换**：`/model gemini-3.1-pro-preview`

> ⚠️ **Thinking 模型注意**：`gemini-3.1-pro-preview` 等 thinking 模型在会话内通过 `/model` 切换后，thinking 标签可能污染上下文，引发 400 级联错误（hermes v0.9.0 已知 bug）。

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
我这台机器用 macOS + zsh，Python 用 pyenv 管理，现在的版本是 3.11
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
nano ~/.hermes/memories/MEMORY.md

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

| 类型       | 存放位置                         | 加载时机                  | 适合内容                     |
| ---------- | -------------------------------- | ------------------------- | ---------------------------- |
| 持久记忆   | `memories/MEMORY.md` + `USER.md` | 每次会话自动注入          | 高频偏好、环境事实           |
| Skills     | `skills/<name>/`                 | 按需调用（`/skill-name`） | 操作手册、流程文档、领域知识 |
| 项目上下文 | 项目目录下 `AGENTS.md`           | 进入该目录时自动注入      | 项目架构、编码规范           |
| 按需注入   | 任意路径，`@file:` / `@folder:`  | 手动在消息中触发          | 临时大文档、参考资料         |
| 历史回溯   | `state.db`（自动）               | Agent 主动搜索时          | 所有历史会话内容             |

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

**实际优先级**（按代码逻辑，存在多个 key 时取第一个）：
`Firecrawl` → `Parallel` → `Tavily` → `Exa`

> 建议：以 **Tavily** 作为每月免费保底，将 Exa key 也配置进去，在需要高质量技术搜索时注释掉 Tavily key 临时切换。

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

> **推荐策略**：先配置 Tavily（每月 1,000 次免费）作为保底，再申请 Exa 赠金并在 `.env` 中同时配置两个 key（Firecrawl 优先级最高，Tavily 最低，但都配置的话 Firecrawl 先被检测到）。
>
> **切换 provider**：在 `.env` 中注释掉不想用的 key，只留一个，hermes doctor 会自动识别当前激活的 provider。

---

## Web Dashboard

Hermes 内置本地 Web 控制台，运行在 `http://127.0.0.1:9119`，提供可视化配置、会话浏览、日志查看等功能。

### 启动

```bash
# 推荐：用 alias（自动激活 venv）
hermes-dashboard

# 或手动
cd ~/.hermes/hermes-agent && source venv/bin/activate && python -m hermes_cli.main dashboard

# 不自动打开浏览器
hermes-dashboard --no-open

# 自定义端口
hermes-dashboard --port 8080
```

> **首次启动**会自动构建前端（需要 `npm`），约需 10–20 秒，之后立即可用。

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

确认 `.env` 中设置了 `GATEWAY_ALLOW_ALL_USERS=true`，然后重启 gateway。

**会话出现 400 级联错误**：

通常由 thinking 模型污染 context 导致。删除问题会话后重新开始：

```bash
hermes sessions list
hermes sessions delete SESSION_ID
```

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
