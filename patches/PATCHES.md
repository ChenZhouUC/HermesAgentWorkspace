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

### 总体架构

所有针对 `hermes-agent/` 源码的补丁以**单一 unified diff** 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理。补丁本身入库于 `~/.hermes`（config repo），`hermes-agent/` 工作区始终保持 "上游 HEAD + diff apply" 状态，不做 commit。

两类补丁走不同管道：

| 类型           | 代表          | 管理方式                                                                        |
| -------------- | ------------- | ------------------------------------------------------------------------------- |
| **工程内补丁** | PATCH-1/2/4/5 | 统一 diff (`local-patches.diff`) + `PATCHED_FILES` 数组 + 行为化验证            |
| **工程外补丁** | PATCH-3       | `hermes-update.sh` Step 7 用 inline Python 就地重写，不经过 diff                |
| **运行时补丁** | PATCH-6       | `npm audit fix`，仅作用于 `node_modules/`（gitignored），每次 update 后重新执行 |

### 更新生命周期（关键步骤）

```
Step 2: Save & Clean
  ├─ git diff HEAD -- PATCHED_FILES → local-patches.diff（原子写：先 .tmp 再 mv）
  ├─ git checkout HEAD -- PATCHED_FILES  ← 还原到干净状态
  └─ 设置 _PATCHES_REVERTED=true（EXIT trap 用）

Step 3: hermes update
  └─ 在干净工作区上跑 git pull + deps + web build + restart

Step 4b: Skills 镜像同步
  └─ rsync -a --delete hermes-agent/skills/ → ~/.hermes/skills/
      ├─ 新增 skill：自动复制到本地
      ├─ 更新 skill：覆盖本地旧版本
      └─ 删除 skill：清理上游已移除但本地残留的孤儿
      （my-skills/ 为独立目录，不受此步骤影响）

Step 8: Re-apply & Verify（核心）
  ├─ 8a. Apply saved diff
  │   ├─ 前置检查：patch 文件自身是否含 conflict marker → 含则跳过
  │   ├─ 尝试 1: git apply --check + git apply（干净 apply）
  │   ├─ 尝试 2: git apply --3way（上游改了同区域但无冲突）
  │   ├─ 失败: git restore --source=HEAD 回滚所有 PATCHED_FILES
  │   └─ 成功后: _has_conflict_markers() 扫描 → 含标记则回滚
  │
  ├─ 8b. Behavioral verification
  │   ├─ PATCH-1: Python import + 调用 _resolve_skill_dir()，检查返回路径
  │   ├─ PATCH-2: grep _get_platform_tools in doctor.py
  │   ├─ PATCH-4: grep _dist_index 签名 in main.py
  │   └─ PATCH-5: grep 'override_acp_command and effective_provider' in delegate_tool.py
  │
  └─ 8c. Refresh saved diff
      ├─ 前提: _PATCH_APPLY_OK && 全部 _*_PATCH_OK 为 true
      ├─ 再次 _has_conflict_markers() → 不干净则拒绝刷新
      ├─ 干净且有 diff: 原子写 local-patches.diff + 写 .local-patches.base
      └─ 干净但无 diff: 提示 "patches may have been absorbed"

Step 8d: Gateway restart（post-patch）
  └─ 前提: _PATCH_APPLY_OK == true && gateway 正在运行
      └─ stop → sleep 2 → start → sleep 3 → 确认存活
      （hermes update 在 step 3 重启 gateway 时补丁尚未 apply，
       Python 进程 sys.modules 缓存旧模块，需重启才能加载补丁代码）
```

### 安全机制（及设计原因）

#### 1. 冲突标记检测：`_has_conflict_markers()` 而非 `git diff --check`

`git diff --check` 同时报告冲突标记**和** trailing whitespace / indent 问题。上游代码风格变化（如多一个尾部空格）就会触发误报，导致功能完好的 patch 被回滚。

`_has_conflict_markers()` 只用 grep 精确匹配 `<<<<<<<`、`=======`、`>>>>>>>` 三种标记的标准格式，避免误判：

```bash
grep -qE '^(<<<<<<<($| )|=======$|>>>>>>>($| ))' "$_f"
```

> **历史教训**：v0.9.0 → v0.10.0 升级时，旧版脚本使用 `git diff --check` 导致 3-way merge 后因 whitespace 报错而回滚全部 patch，整个更新流程失败。

#### 2. 原子写入 patch 文件

所有写 `local-patches.diff` 的路径（Step 2 保存 + Step 8c 刷新）都走 `> file.tmp && mv -f file.tmp file`。原因：如果 `git diff` 过程中脚本被中断（Ctrl-C、OOM、磁盘满），直接 `>` 重定向会先截断文件再写入，导致 patch 文件被清空且无法恢复。

#### 3. Patch 文件毒化检测

Step 8a 开头先扫描 `local-patches.diff` 自身是否含 conflict marker（`^\+?(<<<<<<<|=======|>>>>>>>)`）。如果上一次脚本异常退出时 3-way merge 的冲突结果被误写入 diff 文件，这步会拦截，避免把冲突标记 apply 到源码里。

恢复方法：`cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff`

#### 4. EXIT trap 补丁恢复

Step 2 还原 patch 后设置 `_PATCHES_REVERTED=true`。若脚本在 Step 3 之前崩溃，EXIT trap 会自动尝试 `git apply` 恢复补丁，防止因脚本中途退出导致 hermes-agent 处于裸奔状态。Step 3 完成后清除该标志。

#### 5. 上游 base commit 追踪

每次 Step 8c 成功刷新 diff 后，将当前 `hermes-agent` 的 HEAD SHA + UTC 时间戳写入 `patches/.local-patches.base`。当下次 update 补丁 apply 失败时，可以对比这个 base 和新的 HEAD 来定位是哪些上游 commit 引入了冲突：

```bash
# 查看自上次 patch 刷新以来上游改了哪些相关文件
BASE=$(cut -d' ' -f1 ~/.hermes/patches/.local-patches.base)
cd ~/.hermes/hermes-agent && git log --oneline ${BASE}..HEAD -- tools/skill_manager_tool.py hermes_cli/doctor.py hermes_cli/main.py tools/delegate_tool.py
```

#### 6. 上游吸收检测

Step 8c 中，如果所有 `PATCHED_FILES` 与上游 HEAD 无差异（`_REFRESHED` 为空），说明补丁可能已被上游合并。脚本会提示清理 `PATCHED_FILES` 列表和本文档中的对应条目，避免后续更新反复 apply 一个空 diff。

### 已知局限

| 局限                            | 说明                                                                                                                                                                                                                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **单体 diff，不支持逐文件降级** | 所有 patch 在一个 diff 中。如果 5 个文件中只有 1 个冲突，整体 apply 失败，其余 4 个也不会被应用。`git apply --3way` 覆盖了大部分上下文偏移的情况；真冲突时需要手动 `git apply --reject` 逐文件处理。未来如果冲突频繁，考虑拆成 per-file diff 或改用 Python 脚本做更细粒度的 apply。 |
| **行为化验证依赖特征字符串**    | PATCH-2/4/5 的验证是 grep 固定字符串。如果上游重构了函数但保留了行为，grep 会误报 "inactive"。PATCH-1 用了真实 Python import + 调用，是最稳的方式；其他 patch 条件允许时应向这个模式靠拢。                                                                                          |
| **工程外补丁无版本对齐**        | PATCH-3 的 inline Python 替换依赖 `hermes completion zsh` 输出的固定格式。如果上游改了补全生成逻辑但仍有 bug，替换可能失效。目前有 "skip if already correct" 逻辑兜底。                                                                                                             |

### 受 `PATCHED_FILES` 管理的文件

```bash
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "hermes_cli/doctor.py"
    "hermes_cli/main.py"
    "tools/delegate_tool.py"
)
```

### 手动恢复

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突：git apply --reject && 手动解决 .rej，再重跑 hermes-update.sh

# 若 patch 文件自身已被 conflict marker 污染，可先恢复入库版本
cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff

# 查看 patch 基于的上游版本
cat ~/.hermes/patches/.local-patches.base
```

---

## v0.10.0 (upstream `b05d3041`）

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

| 字段         | 内容                                                      |
| ------------ | --------------------------------------------------------- |
| **文件**     | `completions/_hermes`（工程外，不在 `PATCHED_FILES` 中）  |
| **状态**     | 🟡 未上游合并                                             |
| **适用版本** | 已验证 v0.10.0；上游 `hermes completion zsh` 输出同样错误 |

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

### [PATCH-4] hermes_cli/main.py — `hermes dashboard` 每次启动重复 build

| 字段         | 内容                 |
| ------------ | -------------------- |
| **文件**     | `hermes_cli/main.py` |
| **状态**     | 🟡 未上游合并        |
| **适用版本** | ≥ v0.9.0             |

**问题**：`hermes dashboard` 每次启动都在 `HERMES_WEB_DIST` 未设置时直接调用 `_build_web_ui()`；即使构建产物已存在，也会重复执行 `npm install + npm run build`，导致启动耗时数十秒。

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
