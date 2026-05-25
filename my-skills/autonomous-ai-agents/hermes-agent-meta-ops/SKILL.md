---
name: hermes-agent-meta-ops
description: "Hermes Agent 的自我运维与错误排查指南：涵盖技能 (Skill) 整理与碎片化管理，以及记忆系统超载/冲突时的恢复策略。"
category: autonomous-ai-agents
---

# Hermes Agent Meta-Ops

本技能用于 Hermes 自身的运维和故障排查。包含两大核心板块：**技能治理 (Skill Organization)** 与 **记忆系统恢复 (Memory Management)**。

## 一、技能治理 (Skill Organization)

**使用场景**：当用户要求“整理一下我的 skills”、“清理冗余技能”时。
**操作红线**：只能操作 `~/.hermes/my-skills/` 下的用户自定义技能，严禁动官方预置技能。

### 操作原则

1.  **聚合大于碎片**：将同领域的多个细碎技能（如专门针对某个小工具的 config 指南）合并为综合的大技能，减少 Token 开销。
2.  **清理沉旧 Fallback**：大模型基座更新很快，很多“因为原生工具坏了所以绕道去外部 API”的 Fallback 技能（如低端生图或爬虫）通常已过时，应果断判定删除。
3.  **使用标准工具**：使用 `skill_manage(action='delete')` 删除冗余技能，使用 `action='patch'` 修改。遇到必须保留被删除技能中某一段逻辑时，务必将那段逻辑先追加到目标大技能中，然后再删除。

### 识别自定义技能 (Identifying Custom Skills)

当被问及“哪些是我自定义的技能”时，不要直接凭感觉猜。
使用终端执行 `cd ~/.hermes/skills && git log --author="<User>" --name-only` 或检查 `git remote -v`。
由于该目录作为 `HermesAgentWorkspace.git` 的一部分受到版本控制，任何带有纯中文描述、特定硬件记录、私有服务（如飞书、元宝）绑定、或由用户账号提交的变更，均是识别用户私有技能的可靠依据。

---

## 二、记忆系统管理 (Memory Management)

**使用场景**：当执行 `memory(action='add' / 'replace')` 报错提示超出字符限制（Memory Char Limit），或报错“旧文本未找到 (old_text not found)”。

### 排查与恢复步骤

1.  **诊断**：遇到 Memory Char Limit (默认约 2200 字符)，说明当前长期记忆已经堆满垃圾。
2.  **筛选 (Triage)**：
    - **必须保留**：用户的刚性偏好、OS 环境的独特设定、极易踩坑的工具路径规范。
    - **必须删除**：历史任务的流水账、临时的 TODO 进度、长篇大论的报错日志。
    - **必须转移**：如果是复杂的跨步操作流（SOP），应该新建一个 Skill 存起来，而不是塞在记忆里。
3.  **重建**：
    - 先调用 `memory(action='remove')` 把冗长的垃圾清理掉。
    - 再把提炼压缩后的、高度精炼的指令重新存回去。

### 🚨 绝对红线

**绝对不要盲目清空所有记忆！** 记忆中包含了诸如“Docker 环境是否用免密”、“Feishu 的特定 Quirks”等极其宝贵的系统排雷经验，盲目全删会导致后续反复掉坑。

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
