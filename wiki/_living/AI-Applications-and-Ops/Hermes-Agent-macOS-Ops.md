---
title: Hermes Agent macOS Ops
created: 2026-05-14
updated: 2026-05-27
---

# Hermes Agent macOS 安装与运维手册

> 适用系统：macOS 13+（Apple Silicon / Intel 均可）
> 主模型：公司 **Vertex AI**（service account 换 token，OpenAI 兼容端点）
> Fallback：**阿里云 Qwen / DashScope**（百炼）
> 适用版本：Hermes Agent **v0.14.0**（upstream `6a6766fb8` / latest `main` as of 2026-05-20）
> 本机 `~/.hermes` 使用官方 `hermes-agent` + `patches/local-patches.diff` 管理少量本地补丁；详见 `README.md` 与 `patches/PATCHES.md`
>
> 本文涵盖：准备工作 → 卸载旧版 OpenClaw → 安装 Hermes Agent → 配置 Vertex + Qwen → Vertex Token 自动刷新 → 飞书接入 → 内容迁移 → 日常运维

---

## 目录

1. [第一章：开始之前——准备工作](#第一章开始之前准备工作)
2. [第二章：卸载 OpenClaw（如适用）](#第二章卸载-openclaw如适用)
3. [第三章：安装 Hermes Agent](#第三章安装-hermes-agent)
4. [第四章：配置主模型与 Fallback](#第四章配置主模型与-fallback)
5. [第五章：Vertex Token 刷新（首次 + 定时）](#第五章vertex-token-刷新首次--定时)
6. [第六章：接入飞书机器人](#第六章接入飞书机器人)
7. [第七章：从 OpenClaw 迁移记忆与技能](#第七章从-openclaw-迁移记忆与技能)
8. [第八章：验证是否正常运行](#第八章验证是否正常运行)
9. [第九章：日常运维手册](#第九章日常运维手册)
10. [第十章：常见故障排查](#第十章常见故障排查)

---

## 第一章：开始之前——准备工作

在开始安装之前，请先确认以下条件齐备。缺少任何一样都会导致后续无法完成配置。

### 1.1 你需要提前拿到的东西

| 需要什么                             | 去哪里获取                                                                                                                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| **Vertex Service Account JSON**      | 公司管理员发放的 GCP 服务账号 JSON 文件（含 `private_key`、`client_email`、`project_id`，需具备 `aiplatform.endpoints.predict` 权限） |
| **GCP 项目 ID** 和 **Location**      | 通常即 SA JSON 中的 `project_id`；location 一般是 `global` 或区域（如 `us-central1`）                                                 |
| **DashScope（阿里云通义）API Key**   | 登录 [https://bailian.console.aliyun.com](https://bailian.console.aliyun.com) → API-KEY 管理，格式 `sk-xxxxxxxx`（fallback 用）       |
| **（可选）飞书 App ID / App Secret** | 飞书开放平台 [https://open.feishu.cn](https://open.feishu.cn) → 你的应用 → 凭证与基础信息                                             |
| **（可选）Tavily API Key**           | 注册 [https://app.tavily.com/home](https://app.tavily.com/home)，格式 `tvly-xxxx`，用于联网搜索                                       |

### 1.2 安装基础依赖

打开 **iTerm2**（Launchpad 中搜「iTerm」），逐步执行：

```bash
# Homebrew（已装会跳过）
command -v brew >/dev/null 2>&1 && echo "✓ Homebrew 已安装" || \
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Apple Silicon（M 系芯片）首次装 brew 后追加：

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc && source ~/.zshrc
```

继续装 Python 管理工具 / git / uv / ripgrep / Xcode CLT：

```bash
brew install pyenv git uv ripgrep
xcode-select --install 2>/dev/null || echo "✓ Xcode CLT 已安装"
```

> Hermes 的 Python 版本以 `hermes-agent/pyproject.toml` 的 `requires-python` 为准；当前上游 v0.14.0 为 `>=3.11`，本机恢复时使用 pyenv `3.12.7`。
> `uv` 是 Astral 出品的高速 Python 包管理器，`hermes update` 会用到。
> Xcode CLT 用于编译 Vertex 唤醒监听器（Swift 脚本）。

### 1.3 确保 `~/.local/bin` 在 PATH

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 第二章：卸载 OpenClaw（如适用）

> 如果你从未装过 OpenClaw，请直接跳到第三章。
>
> ⚠️ 卸载过程**不会删除** `~/.openclaw` 数据目录，历史记录、记忆、技能都会保留，第七章会迁移到 Hermes。

### 2.1 停止 OpenClaw 进程与服务

```bash
launchctl list 2>/dev/null | grep -i "openclaw\|claw" | awk '{print $3}' | grep -v '^-$' | \
  while read svc; do
    launchctl stop "$svc" 2>/dev/null
    launchctl remove "$svc" 2>/dev/null
    echo "✓ 已停止并移除服务：$svc"
  done
ls ~/Library/LaunchAgents/ 2>/dev/null | grep -i "openclaw\|claw" | \
  while read f; do
    rm -f ~/Library/LaunchAgents/"$f"
    echo "✓ 已删除：~/Library/LaunchAgents/$f"
  done
echo "✓ OpenClaw 进程和服务清理完成"
```

### 2.2 卸载 OpenClaw 安装包

```bash
npm uninstall -g openclaw-cli 2>/dev/null && echo "✓ npm 方式已卸载" || \
  (brew uninstall openclaw-cli 2>/dev/null && echo "✓ brew 方式已卸载") || \
  echo "✓ 未找到 OpenClaw 安装包（可能已卸载）"
```

### 2.3 确认数据目录保留

```bash
ls ~/.openclaw/ >/dev/null 2>&1 && echo "✓ ~/.openclaw 保留完好，后续可迁移" || echo "⚠️ 未找到 ~/.openclaw"
```

### 2.4 清理 launchd override 残留（重要）

卸载后建议额外确认 OpenClaw 是否还残留在 launchd 的 override 状态表里。这个残留通常不是正在运行的 runtime，也不是已加载的 LaunchAgent，但会在 `launchctl print-disabled` 中显示为：

```text
"ai.openclaw.gateway" => enabled
```

先确认是否存在真实进程或已加载服务：

```bash
pgrep -fil '[o]penclaw|ai\.[o]penclaw|open[-_ ]?claw' || echo "✓ 未发现 OpenClaw 进程"
launchctl print "gui/$(id -u)/ai.openclaw.gateway" 2>/dev/null || echo "✓ 未发现已加载的 ai.openclaw.gateway service"
launchctl print-cache | grep -i openclaw || echo "✓ launchd service cache 无 OpenClaw"
```

再检查 override 状态表：

```bash
launchctl print-disabled "user/$(id -u)" | grep -i openclaw || echo "✓ user domain 无 OpenClaw override"
launchctl print-disabled "gui/$(id -u)" | grep -i openclaw || echo "✓ gui domain 无 OpenClaw override"
```

如果仍看到 `ai.openclaw.gateway => enabled`，按下面步骤清理。这里会临时给 override plist 加 `uchg` 锁，目的是避免 launchd 在关机阶段把旧的内存态 override 表重新写回磁盘；重启后必须解除该锁。

```bash
uid="$(id -u)"
label="ai.openclaw.gateway"
db="/var/db/com.apple.xpc.launchd/disabled.${uid}.plist"
bak="${db}.openclaw-backup.$(date +%Y%m%d-%H%M%S)"

sudo cp -p "$db" "$bak"
sudo /usr/libexec/PlistBuddy -c "Delete :${label}" "$db" 2>/dev/null || echo "✓ ${label} 已不在磁盘 plist 中"
plutil -lint "$db"
plutil -p "$db" | grep -i openclaw || echo "✓ disk clean"

sudo chflags uchg "$db"
ls -lO "$db"
sudo reboot
```

重启并重新登录后，立即验证并解除临时锁：

```bash
uid="$(id -u)"
db="/var/db/com.apple.xpc.launchd/disabled.${uid}.plist"

launchctl print-disabled "user/${uid}" | grep -i openclaw || echo "✓ user domain clean"
launchctl print-disabled "gui/${uid}" | grep -i openclaw || echo "✓ gui domain clean"
plutil -p "$db" | grep -i openclaw || echo "✓ disk clean"

sudo chflags nouchg "$db"
ls -lO "$db"
```

> 不建议用 `launchctl enable/disable user/$(id -u)/ai.openclaw.gateway` 处理这个残留；它只会重新写入 override 状态，可能把孤儿 key 固化回来。

---

## 第三章：安装 Hermes Agent

### 3.1 克隆代码

```bash
mkdir -p ~/.hermes
git clone https://github.com/NousResearch/hermes-agent.git ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent
```

> 本手册当前基于 v0.14.0（upstream `6a6766fb8`）；如需固定到某个官方版本，可在 clone 后追加 `git checkout <tag-or-commit>`。

### 3.2 创建虚拟环境并安装依赖

```bash
rg '^requires-python' pyproject.toml
PYTHON_VERSION=3.12.7  # 示例：选择任意满足 requires-python 的本机 Python
uv venv --python "$PYTHON_VERSION" venv
source venv/bin/activate
uv pip install -e ".[all,feishu]"
```

> 这套安装组合覆盖：上游 `[all]` 的常用 CLI / Gateway / Web / MCP / PTY 能力，以及本机常驻需要的飞书集成。Python 版本不要写死，按当前 `pyproject.toml` 的 `requires-python` 与本机可用版本选择；2026-05-20 新机恢复使用的是 pyenv `3.12.7`。
> 想启用本地 STT / 语音消息时再追加 `voice` extra；想启用 Computer Use 时再追加 `computer-use`（需要后续 `hermes tools` 装 cua-driver）。
>
> **关于 `python-socks`（飞书 + 代理网络必装，PATCH-7）**：上游 v0.14.0 的 `feishu` extra 与 `tools/lazy_deps.py` 的 Feishu lazy backend 都未声明 `python-socks`。本机通过 PATCH-7 同时补到 `pyproject.toml` 和 `tools/lazy_deps.py`，因此不要再手动安装宽松区间约束；补丁固定为当前验证过的 `python-socks==2.8.1`。

### 3.3 暴露 hermes 命令

```bash
mkdir -p ~/.local/bin
ln -sf ~/.hermes/hermes-agent/venv/bin/hermes ~/.local/bin/hermes
deactivate
```

### 3.4 准备外围目录与凭据

```bash
mkdir -p ~/.hermes/credentials ~/.hermes/scripts ~/.hermes/logs ~/.hermes/tmp
cp /path/to/wh-gemini-1-service-account.json ~/.hermes/credentials/
chmod 600 ~/.hermes/credentials/*.json
```

> 把公司发的 SA JSON 放到 `~/.hermes/credentials/`；权限设 600。

### 3.5 修复 npm 依赖已知漏洞（等价于本地 PATCH-6）

`hermes` 在装 Node 工具时使用 `npm install --no-audit`，所以已知漏洞不会被自动修复。装完 / 每次更新代码后跑一次 `npm audit fix` 把可自动修复的全部解决（不能动的会输出"need force"提示，谨慎处理）：

```bash
cd ~/.hermes/hermes-agent
npm audit fix --quiet || true
cd -
```

> 历史背景：`basic-ftp ≤5.2.2` 曾报 GHSA-rp42-5vxx-qpwr（高危 DoS），`hermes doctor` 会显示 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。`npm audit fix` 会一次性升级到无漏洞版本。
> 这条做完不需要 commit 任何文件 —— `node_modules/` 是 gitignored，`hermes update` 也不会回滚它。

### 3.6 验证安装

```bash
hermes --version
hermes doctor
```

应能看到 `Hermes Agent v0.14.0 (2026.5.16)` 或更新版本；`hermes doctor` 此时会提示缺 token / fallback key（下一章解决）。

---

## 第四章：配置主模型与 Fallback

Hermes 的配置分两层：

- `~/.hermes/.env` —— 所有进程（gateway / cron / launchd）共享的密钥
- `~/.hermes/config.yaml` —— 模型、工具、记忆、UI 等行为开关

### 4.1 写入 `.env` 密钥

```bash
cat > ~/.hermes/.env <<'EOF'
# ── 主模型：Vertex AI（公司 SA） ─────────────────────────
GOOGLE_APPLICATION_CREDENTIALS=/Users/YOUR_USER/.hermes/credentials/wh-gemini-1-service-account.json
VERTEX_PROJECT_ID=wh-gemini-1
VERTEX_LOCATION=global
VERTEX_OPENAI_BASE_URL=https://aiplatform.googleapis.com/v1/projects/wh-gemini-1/locations/global/endpoints/openapi
VERTEX_ACCESS_TOKEN=
VERTEX_ACCESS_TOKEN_EXPIRES_AT=

# ── Fallback：阿里 Qwen / DashScope ─────────────────────
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# ── Hermes Gateway ─────────────────────────────────────
HERMES_GATEWAY_TOKEN=
GATEWAY_ALLOW_ALL_USERS=true

# ── 可选：飞书集成（第六章再开） ─────────────────────────
# FEISHU_APP_ID=cli_xxxxxxxxxxxx
# FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
# FEISHU_DOMAIN=feishu
# FEISHU_CONNECTION_MODE=websocket

# ── 可选：联网搜索 ──────────────────────────────────────
# TAVILY_API_KEY=tvly-xxxxxxxxxxxx
EOF
chmod 600 ~/.hermes/.env
```

> ⚠️ **必须用绝对路径**替换 `YOUR_USER`；launchd 后台不继承 shell 的 `$HOME`。
> SA JSON 文件名按你拿到的实际名替换；`VERTEX_PROJECT_ID` / `VERTEX_LOCATION` 与之保持一致。

### 4.2 配置 `config.yaml`

首次运行 Hermes 会自动生成默认 config，编辑：

```bash
hermes config edit
```

把下面这段填进去（只列关键字段，其它保留默认）：

```yaml
# 主模型：Vertex AI 的 OpenAI 兼容端点
model:
  provider: custom
  default: google/gemini-3.1-pro-preview # 按公司可用模型替换
  base_url: https://aiplatform.googleapis.com/v1/projects/wh-gemini-1/locations/global/endpoints/openapi
  api_key: ${VERTEX_ACCESS_TOKEN}

# Fallback：主模型失败 / 限流时自动接力
fallback_model:
  provider: alibaba
  model: qwen3.6-plus

providers: {}
fallback_providers: []

agent:
  max_turns: 90
  gateway_timeout: 1800
  reasoning_effort: high
  # Vertex token 每 50 min 刷新会触发 gateway restart；长 Gemini Pro 任务可跑 8-10 分钟。
  # drain 给到 900s（15 min）让 in-flight agent 自然完成，避免 SIGKILL 导致"会话重置"。
  # 安全上限：刷新间隔 3000s + token 寿命 ~3600s ⇒ drain ≤ 600s 是绝对安全的；
  # 选 900s 是因为 token 寿命 3600 - 刷新间隔 3000 = 600s 缓冲，外加 launchd 调度抖动一般 ≤ 300s。
  restart_drain_timeout: 900

memory:
  memory_enabled: true
  user_profile_enabled: true

checkpoints:
  enabled: true
  max_snapshots: 50

# 把上下文压缩（compression）路由到 qwen，避免与主模型抢 Vertex 配额
# （否则飞书长会话压缩时常见 429 Resource exhausted，导致只能插入 fallback context marker）。
auxiliary:
  compression:
    provider: alibaba
    model: qwen3.6-plus
    extra_body:
      enable_thinking: true # qwen3.6-plus 支持 thinking 模式，压缩质量更稳
```

> v0.12.x 的老手册建议把 `compression.threshold` 调到 0.35 提前触发压缩——那是因为压缩当时还在抢 Vertex 配额。
> 当前配置把压缩路由到 Qwen 后就**不再抢 Vertex 配额**，可以保留 `compression.threshold` 默认值 0.7。

也可以纯命令行：

```bash
hermes config set model.provider custom
hermes config set model.default google/gemini-3.1-pro-preview
hermes config set model.base_url 'https://aiplatform.googleapis.com/v1/projects/wh-gemini-1/locations/global/endpoints/openapi'
hermes config set model.api_key '${VERTEX_ACCESS_TOKEN}'
hermes config set fallback_model.provider alibaba
hermes config set fallback_model.model qwen3.6-plus
hermes config set agent.reasoning_effort high
hermes config set agent.restart_drain_timeout 900
hermes config set auxiliary.compression.provider alibaba
hermes config set auxiliary.compression.model qwen3.6-plus
hermes config set auxiliary.compression.extra_body.enable_thinking true
```

### 4.3 把 DashScope Key 登记到凭据池

让 `provider: alibaba` 自动认到 fallback key：

```bash
hermes auth add alibaba --label main --api-key "$(grep ^DASHSCOPE_API_KEY ~/.hermes/.env | cut -d= -f2)"
hermes auth list
```

### 4.4（可选）启用 Tavily 联网搜索

```bash
echo 'TAVILY_API_KEY=tvly-你的KEY' >> ~/.hermes/.env
hermes config set web.backend tavily
```

---

## 第五章：Vertex Token 刷新（首次 + 定时）

Vertex access token 寿命约 1 小时，必须周期续期。Hermes 上游本身**不带** token 刷新脚本——这一套是放在配套的 [HermesAgentWorkspace](https://github.com/ChenZhouUC/HermesAgentWorkspace) 仓库里维护的。

```bash
# 假设你已 clone 该仓库到 ~/code/HermesAgentWorkspace
cp ~/code/HermesAgentWorkspace/scripts/{refresh_vertex_access_token,refresh_vertex_access_token.py,refresh_vertex_and_restart_gateway,install_vertex_refresh_launchd,vertex_wake_watcher.swift,inject_launchd_proxy_env} ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/*
```

> 拷贝过来的 6 个脚本：
>
> - `refresh_vertex_access_token` / `.py` —— 用 SA JSON 换 1h token，写入 `.env`
> - `refresh_vertex_and_restart_gateway` —— 上面那一步 + SIGUSR1 通知 gateway reload
> - `install_vertex_refresh_launchd` —— 安装周期 + 唤醒两个 LaunchAgent
> - `vertex_wake_watcher.swift` —— 监听 macOS 唤醒事件触发补刷的 Swift watcher
> - `inject_launchd_proxy_env` —— 给三个 LaunchAgent 注入代理环境变量

### 5.1 首次手动刷新（验证通路）

```bash
~/.hermes/scripts/refresh_vertex_access_token \
  --credentials ~/.hermes/credentials/wh-gemini-1-service-account.json
```

成功后 `.env` 会出现：

```
VERTEX_ACCESS_TOKEN=ya29.c.xxxxxxx...
VERTEX_ACCESS_TOKEN_EXPIRES_AT=1761234567
```

> 想顺带重启 gateway 用 `~/.hermes/scripts/refresh_vertex_and_restart_gateway`。

### 5.2 安装定时刷新（launchd，推荐）

```bash
# 默认 50 分钟一次（3000s）；安装时立即跑一次（RunAtLoad=true）
~/.hermes/scripts/install_vertex_refresh_launchd

# 想改成 45 分钟一次
~/.hermes/scripts/install_vertex_refresh_launchd --interval-seconds 2700
```

会安装两个 LaunchAgent：

| Label                      | 作用                                           | plist                                                   |
| -------------------------- | ---------------------------------------------- | ------------------------------------------------------- |
| `ai.hermes.vertex-refresh` | 周期刷新 + 自动重启 gateway                    | `~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist` |
| `ai.hermes.vertex-wake`    | 监听系统从睡眠唤醒 → 立即补跑一次刷新（Swift） | `~/Library/LaunchAgents/ai.hermes.vertex-wake.plist`    |

**重试策略**：连续失败 3 次（每次间隔 60s），3 次都失败时弹 macOS 系统通知。

**日志位置**：

```
~/.hermes/logs/vertex-refresh.log / vertex-refresh.err.log
~/.hermes/logs/vertex-wake.log    / vertex-wake.err.log
```

### 5.3 Vertex 刷新运维命令

```bash
# 立刻手动触发一次（验证 / 排错）
launchctl kickstart -k gui/$(id -u)/ai.hermes.vertex-refresh

# 查看任务详情 + 退出码
launchctl print gui/$(id -u)/ai.hermes.vertex-refresh
launchctl print gui/$(id -u)/ai.hermes.vertex-wake

# 看 token 剩余寿命
exp=$(grep '^VERTEX_ACCESS_TOKEN_EXPIRES_AT=' ~/.hermes/.env | cut -d= -f2)
echo "expires at: $(date -r $exp '+%F %T %z')   in $(( (exp - $(date +%s)) / 60 )) min"

# 实时跟踪日志
tail -f ~/.hermes/logs/vertex-refresh.log

# 卸载（仅停掉自动刷新，gateway 不受影响）
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist
rm -f ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist \
      ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist

# 重装 / 覆盖
~/.hermes/scripts/install_vertex_refresh_launchd
```

### 5.4（可选）配合代理

公司网络若需要走 Clash / V2Ray：

```bash
~/.hermes/scripts/inject_launchd_proxy_env --proxy-url http://127.0.0.1:7897
```

它会原子地把 `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY` 注入 `gateway / vertex-refresh / vertex-wake` 三个 LaunchAgent 并自动重载。失败会回滚。

回滚命令：

```bash
hermes gateway install --force
~/.hermes/scripts/install_vertex_refresh_launchd
```

---

## 第六章：接入飞书机器人

> 只需要前台 `hermes chat` / 不接飞书的话，**可跳过本章**。

### 6.1 把飞书凭证写入 `.env`

```bash
open -a TextEdit ~/.hermes/.env
```

把第四章 `.env` 里注释掉的飞书段启用并填值：

```
FEISHU_APP_ID=cli_xxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxx
FEISHU_DOMAIN=feishu              # Lark 国际版填 lark
FEISHU_CONNECTION_MODE=websocket
GATEWAY_ALLOW_ALL_USERS=true
```

> `FEISHU_DOMAIN` 填 `feishu` / `lark`，**不要填网址**。
> `websocket` 长连接模式不需要公网 IP。

### 6.2 在飞书开放平台开通权限

在 [https://open.feishu.cn](https://open.feishu.cn) 你的应用「权限管理」中确认：

- `im:message`（接收消息）
- `im:message:send_as_bot`（发送消息）
- `im:chat:readonly`（获取群信息）
- `contact:user.id:readonly`（获取用户 ID）

有改动后记得点「发布版本」让权限生效。

### 6.3 安装并启动 Gateway

Gateway 是 Hermes 与飞书 / cron / dashboard 之间的常驻桥梁。

```bash
hermes gateway install        # 注册为 LaunchAgent，写入 HERMES_GATEWAY_TOKEN
hermes gateway start
hermes gateway status
```

### 6.4 推荐启动顺序（首次部署）

```bash
# 1) 先确保 Vertex token 有效
~/.hermes/scripts/refresh_vertex_and_restart_gateway

# 2) Gateway 自启动
hermes gateway install

# 3) Vertex 自动刷新
~/.hermes/scripts/install_vertex_refresh_launchd
```

### 6.5 验证飞书联通

`hermes gateway status` 应显示 Gateway running + Feishu connected；同时在飞书直接给 bot 发消息看是否回复。

### 6.6 忙时输入模式 (Busy Input Mode) 与连续对话机制

当用户连续发送多条消息（即在前一条消息尚未出最终回复时追加发送），Hermes 会根据配置的 **忙时输入模式 (Busy Input Mode)** 决定底层时序和排队策略。默认模式为 `interrupt`，可通过 `/busy [queue|steer|interrupt]` 热切换，或修改 `config.yaml`。

#### 1. 默认模式：打断 (interrupt)

- **机制**：如果 AI 正在执行耗时工具调用（如正在执行代码或搜索网页），立刻丢弃并终止正在运行的回合（Turn），并将最新到达的消息作为新的用户输入重新开始。
- **幻觉（看似并行/排队）**：如果用户极快地连续发送两句，第一句尚未触发耗时工具（仍在 Idle 状态），由于没有“正在跑的任务”可打断，底层保护机制会自动降级为 `queue` 模式，瞬间秒回第一句，再秒回第二句。这容易让用户误以为底层是并行或按顺序分别处理的。
- **适用场景**：发现前置指令写错、给错文件路径，强行叫停。

#### 2. 队列模式 (queue)

- **机制**：在首个回合彻底结束前，新收到的所有消息被安全地缓存在内存队列中。等第一个任务生成最终回复后，依次取出队头消息，开启下一轮全新回合。
- **适用场景**：一口气布置多个完全独立的异步任务（“查天气”、“建文件”），互不干扰。

#### 3. 引导合并模式 (steer)

- **机制**：插队式上下文合并。新消息不会打断当前任务，也不会进入下一轮回合，而是作为“引导注释”无缝注入到**下一个工具调用结束后的系统上下文**中。模型会在同一个回合的后续思考中直接看到这句补充。
- **优势**：不破坏提示词缓存（Prompt Caching），不消耗新的回合数（Turn）。
- **适用场景**：AI 正在写长代码或梳理数据，突然想补充要求（“顺便把输出存到桌面”、“改成全英文输出”）。
- **如何触发**：配置 `/busy steer` 后发普通文字，或在任意模式下强制前缀触发 `/steer 补充内容`。

---

## 第七章：从 OpenClaw 迁移记忆与技能

如果第二章保留了 `~/.openclaw/`，Hermes 内置工具可以一键迁移。

### 7.1 执行迁移

```bash
hermes claw migrate
```

迁移内容：

| OpenClaw 中的内容  | 迁移到 Hermes 的位置           |
| ------------------ | ------------------------------ |
| 历史记忆（memory） | `~/.hermes/memories/MEMORY.md` |
| 用户画像           | `~/.hermes/memories/USER.md`   |
| 技能（skills）     | `~/.hermes/skills/`            |

### 7.2 迁移完成后归档（可选）

```bash
hermes claw cleanup
```

将 `~/.openclaw/` 打包归档（不会真删）。

### 7.3 检查迁移结果

```bash
open -a TextEdit ~/.hermes/memories/MEMORY.md
open -a TextEdit ~/.hermes/memories/USER.md
ls ~/.hermes/skills/
```

---

## 第八章：验证是否正常运行

```bash
hermes doctor
hermes status
hermes gateway status
```

正常输出包含：

```
◆ Python Environment
  ✓ Python 3.11.x
  ✓ Virtual environment active

◆ Configuration Files
  ✓ ~/.hermes/.env file exists
  ✓ API key or custom endpoint configured
  ✓ ~/.hermes/config.yaml exists
  ✓ Config version up to date (v23)

◆ API Connectivity
  ✓ Alibaba/DashScope                ← fallback 通了
  ✓ Vertex / custom endpoint         ← 主模型通了

◆ Tool Availability
  ✓ memory / messaging / skills / web …
```

如果某项有 `✗`，按 `hermes doctor` 给出的修复建议处理。一行健康巡检：

```bash
hermes doctor && hermes gateway status && \
  echo "vertex token in $(( ($(grep ^VERTEX_ACCESS_TOKEN_EXPIRES_AT ~/.hermes/.env | cut -d= -f2) - $(date +%s)) / 60 )) min"
```

---

## 第九章：日常运维手册

### 9.1 Gateway 基本操作

```bash
hermes gateway start          # 启动
hermes gateway stop           # 停止
hermes gateway restart        # 重启（改完 config / 装新 extras 后必跑）
hermes gateway status         # 状态 + PID
hermes gateway uninstall      # 卸载 LaunchAgent
```

也可以走 launchd 原生：

```bash
launchctl start ai.hermes.gateway
launchctl stop  ai.hermes.gateway
```

### 9.2 对话与会话

```bash
hermes                        # 启动交互式 TUI
hermes chat "帮我..."         # 单轮 oneshot
hermes resume                 # 恢复最近一次会话
hermes sessions list          # 历史会话列表
hermes sessions delete <id>   # 删除某条
```

### 9.3 模型切换

```bash
hermes model                  # TUI 选主模型
hermes fallback list          # 当前 fallback 链
hermes fallback add           # TUI 增 fallback
hermes fallback clear         # 清空 fallback
```

### 9.4 凭据池

```bash
hermes auth list              # 所有 provider 凭据
hermes auth add alibaba --label main --api-key sk-xxx
hermes auth status alibaba    # 单 provider 状态
hermes auth reset alibaba     # 清除疲劳/限流标记
```

### 9.5 配置

```bash
hermes config show            # 打印当前生效配置
hermes config edit            # 编辑器打开 config.yaml
hermes config set <path> <value>
hermes doctor                 # 体检
hermes dump                   # 打包诊断信息（提 issue 用）
```

### 9.6 Web Dashboard

```bash
hermes dashboard              # 默认 http://127.0.0.1:5174
```

按 `Ctrl + C` 退出（不影响 gateway）。

### 9.7 日志

```bash
hermes logs                   # 实时滚动主日志
open ~/.hermes/logs/          # Finder 打开日志目录
```

| 文件                                | 内容                                   |
| ----------------------------------- | -------------------------------------- |
| `gateway.log` / `gateway.error.log` | Gateway 主日志 / 错误                  |
| `vertex-refresh.log` / `.err.log`   | Token 周期刷新                         |
| `vertex-wake.log` / `.err.log`      | 唤醒触发刷新                           |
| `agent.log`                         | 每轮 agent 推理详细记录（含 thinking） |

### 9.8 记忆管理

```bash
open -a TextEdit ~/.hermes/memories/MEMORY.md   # 自动学到的知识
open -a TextEdit ~/.hermes/memories/USER.md     # 用户画像
```

清空（谨慎）：

```bash
echo "" > ~/.hermes/memories/MEMORY.md
echo "" > ~/.hermes/memories/USER.md
```

### 9.9 Skills / Tools

```bash
hermes skills list
hermes skills install <repo>
hermes tools list
```

> 自定义 skill 可以放到独立目录（推荐 `~/.hermes/my-skills/`），然后在 `config.yaml` 的 `skills.external_dirs` 列表中声明。这样 `hermes update` 同步上游 skills 时不会污染你的自定义 skill。

### 9.10 升级 hermes-agent 到最新

日常升级优先使用本仓库封装脚本，而不是直接跑裸 `hermes update`。封装脚本会保存/恢复本地补丁、保护 PATCHED_FILES 之外的额外 untracked 改动、执行 `npm audit fix`、镜像同步 upstream skills、刷新补全并在补丁重放后重启 gateway。

```bash
bash ~/.hermes/hermes-update.sh
```

> 封装脚本会在 Step 8 验证 PATCH-7：`pyproject.toml` 和 `tools/lazy_deps.py` 都必须包含 `python-socks==2.8.1`，否则会提示重新应用补丁。
> `hermes update --backup` / `--no-backup` 控制是否做升级前快照；详见 `hermes update --help`。
> 升级后 Vertex token 仍有效；想立即跑一次刷新：`launchctl kickstart -k gui/$(id -u)/ai.hermes.vertex-refresh`。

### 9.11 回滚到指定版本

```bash
cd ~/.hermes/hermes-agent
git checkout <commit-sha>     # 或 git checkout v0.12.0
source venv/bin/activate
uv pip install -e ".[all,feishu]"
npm audit fix --quiet || true
deactivate
hermes gateway restart
```

### 9.12 API Key / SA 更换

**DashScope Key 更换**：

```bash
sed -i '' 's|^DASHSCOPE_API_KEY=.*|DASHSCOPE_API_KEY=sk-新key|' ~/.hermes/.env
hermes auth add alibaba --label main --api-key sk-新key
hermes gateway restart
```

**Vertex SA 更换**：

```bash
cp /path/to/new-sa.json ~/.hermes/credentials/
chmod 600 ~/.hermes/credentials/new-sa.json
sed -i '' "s|^GOOGLE_APPLICATION_CREDENTIALS=.*|GOOGLE_APPLICATION_CREDENTIALS=$HOME/.hermes/credentials/new-sa.json|" ~/.hermes/.env
launchctl kickstart -k gui/$(id -u)/ai.hermes.vertex-refresh
```

**飞书凭证更换**：编辑 `~/.hermes/.env` 中 `FEISHU_*`，然后 `hermes gateway restart`。

### 9.13 关键文件 / 目录速查

| 路径                                       | 作用                                                                |
| ------------------------------------------ | ------------------------------------------------------------------- |
| `~/.hermes/config.yaml`                    | 主配置（模型、agent、memory、UI 等）                                |
| `~/.hermes/.env`                           | 密钥（Vertex / DashScope / 飞书 / Tavily）                          |
| `~/.hermes/credentials/*.json`             | Vertex SA JSON                                                      |
| `~/.hermes/scripts/`                       | Token 刷新与 LaunchAgent 安装脚本（来自 HermesAgentWorkspace repo） |
| `~/.hermes/memories/MEMORY.md`             | 学到的事实与偏好                                                    |
| `~/.hermes/memories/USER.md`               | 用户画像                                                            |
| `~/.hermes/skills/`                        | 上游同步过来的 skills（`hermes update` 会 rsync）                   |
| `~/.hermes/my-skills/`                     | 自定义 skills（用 `skills.external_dirs` 注册，避免被 update 覆盖） |
| `~/.hermes/sessions/`                      | 会话历史                                                            |
| `~/.hermes/logs/`                          | 全部日志                                                            |
| `~/.hermes/hermes-agent/`                  | 上游源码 + venv                                                     |
| `~/Library/LaunchAgents/ai.hermes.*.plist` | 三个 LaunchAgent（gateway / vertex-refresh / vertex-wake）          |

### 9.14 完全卸载

```bash
hermes gateway uninstall 2>/dev/null
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-refresh.plist 2>/dev/null
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.vertex-wake.plist 2>/dev/null
rm -f ~/Library/LaunchAgents/ai.hermes.*.plist
rm -f ~/.local/bin/hermes
rm -rf ~/.hermes
```

---

## 第十章：常见故障排查

| 现象                                                                                         | 排查思路                                                                                                                                                                                                                                                                                     |
| -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `hermes chat` 报 401 / `Invalid Credentials`                                                 | `grep VERTEX_ACCESS_TOKEN ~/.hermes/.env` 看是否为空；跑 `~/.hermes/scripts/refresh_vertex_and_restart_gateway`                                                                                                                                                                              |
| Token 一直没刷新                                                                             | `launchctl print gui/$(id -u)/ai.hermes.vertex-refresh` 看 `LastExitStatus`；`tail ~/.hermes/logs/vertex-refresh.err.log`；常见：SA JSON 路径错 / 网络不通 / 权限不足                                                                                                                        |
| 系统从睡眠唤醒后 token 过期                                                                  | 确认 `ai.hermes.vertex-wake` 运行中：`launchctl list \| grep vertex-wake`；PID 为 `-` 表示 Swift watcher 异常退出，重跑 `install_vertex_refresh_launchd`                                                                                                                                     |
| 主模型挂了不切 fallback                                                                      | `hermes config show \| grep -A1 fallback_model` 检查；`hermes auth status alibaba` 看 DashScope key 是否生效                                                                                                                                                                                 |
| 飞书 bot 收到消息但不回复                                                                    | `hermes doctor`；`tail -50 ~/.hermes/logs/gateway.error.log`；检查模型 token / fallback 是否都失效                                                                                                                                                                                           |
| 提示 `API quota exceeded`                                                                    | DashScope 额度耗尽，登录 [百炼控制台](https://bailian.console.aliyun.com) 检查用量 / 充值                                                                                                                                                                                                    |
| 修改 `config.yaml` 后不生效                                                                  | 后台 gateway 必须 `hermes gateway restart`；前台 chat 用 `/reload`                                                                                                                                                                                                                           |
| 飞书任务跑到一半"突然没反应"/会话重置                                                        | 大概率是 Vertex 刷新触发 `gateway restart`，但 in-flight 长任务超过 `agent.restart_drain_timeout` 被 SIGKILL。看 `grep "drain timed out" ~/.hermes/logs/errors.log` 是否有命中。修复：把 `restart_drain_timeout` 调大到 900s（见第四章 agent 段示例），上限受 `(token 寿命 - 刷新间隔)` 约束 |
| 长会话报 `Compression summary failed: 429 Resource exhausted` / 插入 fallback context marker | 默认 `auxiliary.compression.provider=auto` 会复用主模型的 Vertex 配额。修复：`hermes config set auxiliary.compression.provider alibaba && hermes config set auxiliary.compression.model qwen3.6-plus && hermes gateway restart`，让压缩走 DashScope 独立配额                                 |
| 升级代码后 bot 无法启动（`ModuleNotFoundError`）                                             | `cd ~/.hermes/hermes-agent && source venv/bin/activate && uv pip install -e ".[all,feishu]" && deactivate && hermes gateway restart`；若缺的是 Feishu SOCKS 支持，先确认 PATCH-7 已应用到 `pyproject.toml` 和 `tools/lazy_deps.py`                                                           |
| 想限定特定飞书用户访问                                                                       | `.env` 注释掉 `GATEWAY_ALLOW_ALL_USERS=true`，改为 `FEISHU_ALLOWED_USERS=ou_用户ID1,ou_用户ID2`（用户 ID 在飞书开放平台「通讯录」查到）                                                                                                                                                      |
| `Found N issue(s) to address` 误报未启用的 toolset（如 moa / rl）                            | 本机 PATCH-2 已过滤未启用平台 toolset；若仍出现，先跑 `hermes doctor` 看是否是真缺凭据，再检查 `hermes_cli/doctor.py` 中 `_get_platform_tools` 补丁是否还在                                                                                                                                  |
| 飞书每 50min 收到 ⚠ Gateway restarting 通知                                                  | 这是 `vertex-refresh` 触发的 planned restart（默认 3000s 周期），属于预期行为。想降低提醒频率可 `--interval-seconds 3300` 拉长到 55min                                                                                                                                                       |
| 完全清理                                                                                     | 见 §9.14                                                                                                                                                                                                                                                                                     |

---

### 附录：进程拓扑

```
launchd
├─ ai.hermes.gateway        # 常驻主进程（飞书 / cron / dashboard / API）
├─ ai.hermes.vertex-refresh # 周期任务（默认 50 min）→ 刷 token → restart gateway
└─ ai.hermes.vertex-wake    # Swift watcher，监听睡眠唤醒 → 触发补刷
```

至此完成基础部署。后续遇到问题，先跑 `hermes doctor` 自检；定位不到的看对应模块日志。

---

_文档更新时间：2026-05-20_
_对应 Hermes Agent 版本：**v0.14.0**（upstream `6a6766fb8` / latest `main` as of 2026-05-20）_
_主模型：Vertex AI（公司 SA）Fallback：阿里云 Qwen / DashScope（`qwen3.6-plus`）_
_本机使用官方 `hermes-agent` + `patches/local-patches.diff` 管理少量本地补丁。_
