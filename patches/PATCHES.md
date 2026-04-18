# 本地补丁记录

> 本文件集中记录所有相对上游 hermes-agent 的本地补丁，与 `local-patches.diff` 一一对应。
>
> **AI 维护规范**：
>
> - 每次 `hermes update` 升级后，将该版本下新增的补丁条目移至对应版本节；若上游已合并某补丁，将状态改为 `✅ 已上游合并（vX.Y.Z）` 并从 `hermes-update.sh` 的 `PATCHED_FILES` 中移除对应文件。
> - 新补丁格式：在当前版本节下复制一个 `### [PATCH-N]` 块并填写各字段。
> - 版本升级时在顶部新增 `## vX.Y.Z（upstream COMMIT）` 节，未变化的补丁直接迁移过来。
> - `completions/_hermes` 类补丁（不在 `hermes-agent/` 下）在 `hermes-update.sh` Step 6 中用 inline python 处理，不通过 `PATCHED_FILES` 管理。

---

## 补丁管理机制

所有针对 `hermes-agent/` 的补丁以 unified diff 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理：

| 步骤                  | 操作                                                                                                                                                                 |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **更新前（第 2 步）** | `git diff HEAD -- <patched_files>` 另存至 `local-patches.diff`，然后 `git checkout HEAD` 还原文件，使 `git pull` 无需 stash                                          |
| **更新后（第 4 步）** | `npm audit fix` 修复 npm 依赖中的已知安全漏洞（PATCH-6）                                                                                                             |
| **更新后（第 7 步）** | 工程外补丁（如 `completions/_hermes`）在此步骤用 inline python 重写，自动检测是否仍需修复                                                                            |
| **更新后（第 8 步）** | `git apply local-patches.diff` 重新应用；行为化验证 PATCH-1（skill 路由）、PATCH-2（doctor issue count）、PATCH-5（delegate ACP 路由）是否存活；通过后刷新 diff 文件 |

**受 `PATCHED_FILES` 管理的文件**（`hermes-update.sh`）：

```bash
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "hermes_cli/doctor.py"
    "hermes_cli/main.py"
    "tools/delegate_tool.py"
)
```

手动恢复：

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突：git apply --reject && 手动解决 .rej，再重跑 hermes-update.sh
```

---

## v0.9.0 (upstream `00ff9a26`）

### [PATCH-1] tools/skill_manager_tool.py — 自定义 skill 创建路径

| 字段         | 内容                                                                    |
| ------------ | ----------------------------------------------------------------------- |
| **文件**     | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态**     | 🟡 未上游合并                                                           |
| **适用版本** | ≥ v0.9.0                                                                |

**问题**：`skill_manage(action='create')` 默认将新 skill 写入 `~/.hermes/skills/`（官方目录），而非用户的 `my-skills/`。

**修复**：添加 `_resolve_skill_dir()` 读取 `config.yaml` 中的 `skills.external_dirs`，将第一个非官方目录作为新 skill 的基准路径；`_create_skill()` 和 `_delete_skill()` 同步适配。

---

### [PATCH-2] hermes_cli/doctor.py — issue count 过报

| 字段         | 内容                   |
| ------------ | ---------------------- |
| **文件**     | `hermes_cli/doctor.py` |
| **状态**     | 🟡 未上游合并          |
| **适用版本** | ≥ v0.9.0               |

**问题**：`hermes doctor` 将所有注册但缺少 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，导致虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中，通过 `_get_platform_tools` 筛选出用户实际启用的 toolset，只对这些 toolset 报告 issue。

---

### [PATCH-3] completions/\_hermes — Tab 补全无效（`_arguments` 无效参数语法）

| 字段         | 内容                                                     |
| ------------ | -------------------------------------------------------- |
| **文件**     | `completions/_hermes`（工程外，不在 `PATCHED_FILES` 中） |
| **状态**     | 🟡 未上游合并                                            |
| **适用版本** | 已验证 v0.9.0；上游 `hermes completion zsh` 输出同样错误 |

**问题**：在任何新终端按 Tab 键补全 `hermes` 命令，提示符短暂出现 `...` 随即消失，无任何补全菜单。

**根因**：`hermes completion zsh`（即上游二进制）生成的 `_arguments` 规格将互斥说明符 `(...)` 和替代语法 `{...}` 混用，这是无效语法：

```zsh
# 无效：zsh _arguments 不支持 (...){...} 组合写法
'(-h --help){-h,--help}[Show help and exit]'
```

`_arguments` 解析时报 `invalid argument` 并立即退出，`$state` 未被设置，`case $state in` 块从未执行，函数返回零条补全。

**修复**：将三处无效规格拆为独立规格：`-h/--help/-V/--version` 改用 `(- :)` 模式（出现时排除所有其他补全），`-p/--profile` 拆为两条：

```zsh
'(- :)-h[Show help and exit]'
'(- :)--help[Show help and exit]'
'(- :)-V[Show version and exit]'
'(- :)--version[Show version and exit]'
'(-p --profile)-p[Profile name]:profile:_hermes_profiles'
'(-p --profile)--profile[Profile name]:profile:_hermes_profiles'
```

**升级处理**：`hermes-update.sh` Step 6 在重新生成补全脚本后自动检测并重新应用此修复；若上游已修正该语法，步骤自动跳过。

---

### [PATCH-4] hermes_cli/main.py — `hermes web` 每次启动重复 build

| 字段         | 内容                 |
| ------------ | -------------------- |
| **文件**     | `hermes_cli/main.py` |
| **状态**     | 🟡 未上游合并        |
| **适用版本** | ≥ v0.9.0             |

**问题**：`hermes web` 每次启动都无条件执行 `npm install + npm run build`，即使构建产物已存在，导致启动耗时数十秒。

**修复**：在 `cmd_dashboard()` 中检查 `hermes_cli/web_dist/index.html`（Vite 实际输出路径）是否存在，存在则跳过 build 直接启动；不存在时仍正常 build。`hermes update` 路径不受影响（每次 update 仍会重新 build）。

---

### [PATCH-5] tools/delegate_tool.py — ACP 子进程路由缺失

| 字段         | 内容                     |
| ------------ | ------------------------ |
| **文件**     | `tools/delegate_tool.py` |
| **状态**     | 🟡 未上游合并            |
| **适用版本** | ≥ v0.9.0                 |

**问题**：`delegate_task(acp_command="copilot")` 传入 ACP 命令后，子 agent 的 `provider` 仍继承父 agent（如 `gemini`），未切换为 `"copilot-acp"`。`AIAgent` 构造时只在 `provider == "copilot-acp"` 时启用 ACP subprocess 通道，导致 `acp_command`/`acp_args` 被存储但从未使用，子 agent 直接走父 agent 的 API（如 Gemini），最终超时失败。

**修复**：在 `_build_child_agent()` 解析 `effective_acp_command` 之后，检测 `override_acp_command` 是否被显式设置：若是，强制 `effective_provider = "copilot-acp"`、`effective_base_url = "acp://copilot"`，确保 `AIAgent.__init__` 走 `CopilotACPClient` 子进程通道。

---

### [PATCH-6] npm audit fix — node_modules 已知漏洞自动修复

| 字段         | 内容                                              |
| ------------ | ------------------------------------------------- |
| **文件**     | `node_modules/`（gitignored，非 `PATCHED_FILES`） |
| **状态**     | 🟢 自动化（`hermes-update.sh` Step 4）            |
| **适用版本** | ≥ v0.9.0                                          |

**问题**：`hermes update` 安装 npm 依赖时使用 `npm install --no-audit`，不会自动修复已知安全漏洞。例如 `basic-ftp ≤5.2.2` 存在高危 DoS 漏洞（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报告 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。

**修复**：在 `hermes-update.sh` Step 4 中，于 `hermes update` 完成后自动执行 `npm audit fix --quiet`。由于 `node_modules/` 被 gitignore，此修复不通过 `PATCHED_FILES` / `local-patches.diff` 管理，而是每次更新后重新执行。

---
