---
name: hermes-agent-meta-ops
description: "Hermes Agent 的自我运维与错误排查指南：技能 (Skill) 治理、记忆系统恢复、Gateway 权限与会话沙箱、Python 执行环境选择。"
category: autonomous-ai-agents
version: 2026.06.08
author: Chen Zhou <chenzhou@uchicago.edu>
---

# Hermes Agent Meta-Ops

本技能用于 Hermes 自身的运维和故障排查。涵盖：技能治理、记忆系统恢复、Gateway 权限管理、以及 Python 执行环境选择。

## 一、技能治理 (Skill Organization)

**使用场景**：当用户要求"整理一下我的 skills"、"清理冗余技能"时。
**操作红线**：只能操作 `~/.hermes/my-skills/` 下的用户自定义技能，严禁动官方预置技能（`~/.hermes/skills/` 是上游 rsync 镜像）。

### 操作原则

1.  **聚合大于碎片**：将同领域的多个细碎技能（如专门针对某个小工具的 config 指南）合并为综合的大技能，减少 Token 开销。
2.  **清理沉旧 Fallback**：大模型基座更新很快，很多"因为原生工具坏了所以绕道去外部 API"的 Fallback 技能（如低端生图或爬虫）通常已过时，应果断判定删除。
3.  **直接操作文件系统**：通过 Bash 工具使用 `rm -rf` 删除冗余技能目录，使用 Read/Edit/Write 工具修改 SKILL.md 文件。遇到必须保留被删除技能中某一段逻辑时，务必将那段逻辑先追加到目标大技能中，然后再删除目录。
4.  **删除前先备份关键内容**：合并/删除前若怀疑某段逻辑可能有复用价值，先把它追加到目标 SKILL.md 中再 `rm`，避免事后找不回。

详细的偏好（脚本抽取、命名约定、原子操作）见 [`references/skill-maintenance-prefs.md`](references/skill-maintenance-prefs.md)。

### 识别自定义技能 (Identifying Custom Skills)

当被问及"哪些是我自定义的技能"时，不要直接凭感觉猜。
使用终端执行 `cd ~/.hermes/skills && git log --author="<User>" --name-only` 或检查 `git remote -v`。
由于该目录作为 `HermesAgentWorkspace.git` 的一部分受到版本控制，任何带有纯中文描述、特定硬件记录、私有服务（如飞书、元宝）绑定、或由用户账号提交的变更，均是识别用户私有技能的可靠依据。

---

## 二、记忆系统管理 (Memory Management)

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

## 三、Gateway 与权限管理 (Gateway & Authorization)

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

## 四、Python 执行环境选择 (`execute_code` vs `terminal`)

在 agent 内执行 Python 时，必须按依赖与权限故意选择执行通道。`execute_code` 跑在 Hermes 自带 venv 内，访问内部 `hermes_tools`；`terminal` 走 bash，能访问用户的 pyenv/uv/系统 Python。

完整对比、典型场景与陷阱见 [`references/execution-environments.md`](references/execution-environments.md)。
