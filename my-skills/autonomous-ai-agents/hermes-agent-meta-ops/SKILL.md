---
name: hermes-agent-meta-ops
description: "Use when maintaining or debugging Hermes Agent itself: memory recovery, Gateway permissions/session sandboxing, Feishu approval troubleshooting, and Python execution environment choice. For custom skill governance under ~/.hermes/my-skills, use custom-skill-governance instead."
---

# Hermes Agent Meta-Ops

本技能用于 Hermes 自身的运维和故障排查。涵盖：记忆系统恢复、Gateway 权限管理、Feishu 审批排障、以及 Python 执行环境选择。

自定义技能治理、`my-skills` 收敛、冗余删除、重复合并和格式统一，请使用 `custom-skill-governance`。

---

## 一、记忆系统管理 (Memory Management)

**使用场景**：当 Claude Code 的 auto memory 系统中的记忆文件过多、内容冗余或冲突时。

### 排查与恢复步骤

1.  **诊断**：检查 `~/.claude/projects/-Users-chenzhou--hermes/memory/` 目录，查看记忆文件数量和内容质量。
2.  **筛选 (Triage)**：
    - **必须保留**：用户的刚性偏好、OS 环境的独特设定、极易踩坑的工具路径规范。
    - **必须删除**：历史任务的流水账、临时的 TODO 进度、长篇大论的报错日志。
    - **必须转移**：如果是复杂的跨步操作流（SOP），应该新建一个 Skill 存起来，而不是塞在记忆里。
3.  **重建**：
    - 使用 Read 工具读取记忆文件内容，评估其价值。
    - 使用 Bash 工具 `rm` 删除冗余记忆文件。
    - 使用 Write 工具创建精炼后的记忆文件，使用 Edit 工具修改现有记忆。
    - 更新 `MEMORY.md` 索引文件以反映变更。

### 🚨 绝对红线

**绝对不要盲目清空所有记忆！** 记忆中包含了诸如"Docker 环境是否用免密"、"Feishu 的特定 Quirks"等极其宝贵的系统排雷经验，盲目全删会导致后续反复掉坑。

---

## 二、Gateway 与权限管理 (Gateway & Authorization)

**使用场景**：当在 Feishu 中点击终端执行的审批卡片（Approval Cards）没有任何反应，或者尝试执行危险命令被静默拒绝时。

### 审批卡片无响应 (Terminal Approval Fails Silently)

1. **诊断**: 检查 `~/.hermes/logs/gateway.log`。如果看到 `[Feishu] Unauthorized approval click by ou_xxxx...`，说明点击卡片的用户不在网关的审批白名单中。
2. **根因**: Hermes 网关（Gateway）对高危操作把控极严，要求审批者的 Feishu `open_id` 必须明确配置。
3. **修复**:
   - 代理无法直接写入修改受保护的 `~/.hermes/.env` 系统凭证文件。
   - 必须引导用户**手动编辑**配置文件（例如 `nano ~/.hermes/.env`），添加 `FEISHU_ALLOWED_USERS=ou_xxxx...` (填入被拦截的实际 ID)。
   - 指导用户执行 `hermes gateway restart` 以使白名单生效。

完整调试流程见 [`references/feishu-approval-debugging.md`](references/feishu-approval-debugging.md)。

### 会话级工具沙箱 (Session-Level Tool Sandboxing)

让同一个 Hermes 实例在管理员私聊里保留 terminal/file 权限，但在公开群聊里只能纯 LLM 对话——通过 Gateway hook 在 `agent:start` 时按 `chat_id` 动态剥离 `enabled_toolsets`。

实现细节、hook 注册方式、handler 模板见 [`references/gateway-session-sandboxing.md`](references/gateway-session-sandboxing.md)。

---

## 三、Python 执行环境选择 (`execute_code` vs `terminal`)

在 agent 内执行 Python 时，必须按依赖与权限故意选择执行通道。`execute_code` 跑在 Hermes 自带 venv 内，访问内部 `hermes_tools`；`terminal` 走 bash，能访问用户的 pyenv/uv/系统 Python。

完整对比、典型场景与陷阱见 [`references/execution-environments.md`](references/execution-environments.md)。
