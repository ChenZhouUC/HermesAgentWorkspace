# 本地补丁记录

> 本文件集中记录所有相对上游 hermes-agent 的本地补丁，与 `local-patches.diff` 一一对应。
>
> **AI 维护规范**（详细工作流见 `~/.hermes/hermes-update.md` § Step 4）：
>
> - **每次升级后**重写 `## 当前版本：vX.Y.Z (upstream `main` `<SHA>`，YYYY-MM-DD)` header 与下方"最近一次升级"摘要；摘要遵循 5 段结构（上游主线 / patch apply / 依赖 / 已知摩擦 / 配置漂移）。
> - **新补丁**：在 `## 当前版本` 节下新增 `### [PATCH-N]` 块（2-row 表 `文件 / 状态` + 三段 `问题 / 修复 / 验证`），同步把文件加进 `hermes-update.sh` 的 `PATCHED_FILES`。
> - **上游合并某补丁**：把该 PATCH-N 块**整体移动**到一个新的 `## vX.Y.Z archive — PATCH-N 上游合并` 节（vX.Y.Z 为上游吸收所在的 release tag），归档块的表扩到 3-row（`文件 / 状态 / 适用版本`），状态改 `✅ 已上游合并（vX.Y.Z，commit `<SHA>`）`，并把"验证"段改为"上游追踪"段（记录吸收 commit + 是否保留 sentinel grep）；同步从 `PATCHED_FILES` 移除对应文件。
> - **每个 PATCH-N 块在整份 PATCHES.md 里仅出现一次**——要么在当前节、要么在某个 archive 节，**不复制**。
> - `completions/_hermes` 类**工程外补丁**：由 `hermes-update.sh` Step 7 inline Python 在补全脚本生成后检测并修复；上游修好后脚本自动跳过、检测块保留为回归 sentinel（PATCH-3 即此类）。

---

## 补丁管理机制

### 总体架构

所有针对 `hermes-agent/` 源码的补丁以**单一 unified diff** 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理。补丁本身入库于 `~/.hermes`（config repo），`hermes-agent/` 工作区始终保持 "上游 HEAD + diff apply" 状态，不做 commit。

两类补丁走不同管道：

| 类型           | 代表                   | 管理方式                                                                                                                                                                      |
| -------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁** | PATCH-1/2/7/9/10/11/12 | 统一 diff (`local-patches.diff`) + `PATCHED_FILES` 数组 + 行为化验证                                                                                                          |
| **工程外补丁** | PATCH-3                | `hermes-update.sh` Step 7 用 inline Python 检测坏格式后就地重写；上游修复后自动跳过                                                                                           |
| **运行时补丁** | PATCH-6                | `npm audit fix`，仅作用于 `node_modules/`（gitignored），每次 update 后重新执行                                                                                               |
| **已上游合并** | PATCH-3/4/5/8          | PATCH-5 于 v0.10.0 合并；PATCH-8 于 v0.11.0 合并；PATCH-4 于 v0.11.x 通过上游 commit `5b5a53a1` 合并；PATCH-3 于 v0.13.0 通过上游 commit `fe61d95b4` 合并；本地冗余代码已移除 |

### 更新生命周期（关键步骤）

```
Step 2: Save & Clean
  ├─ git diff HEAD -- PATCHED_FILES → local-patches.diff（原子写：先 .tmp 再 mv）
  ├─ git checkout HEAD -- PATCHED_FILES  ← 还原到干净状态
  └─ 设置 _PATCHES_REVERTED=true（EXIT trap 用）

Step 3: hermes update
  ├─ 先 stash PATCHED_FILES 之外的额外改动（含 untracked）
  ├─ 在干净工作区上跑 git pull + deps + web build + restart
  └─ update 后 pop 回额外改动；若冲突则保留 stash 供手动恢复

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
  │   ├─ PATCH-3: Step 7 中对 `){-h,--help}` / `){-V,--version}` / `){-p,--profile}` 做回归检测（✅ 已上游合并 v0.13.0）
  │   ├─ PATCH-4: grep _web_ui_build_needed in main.py（✅ 已上游合并，仅验证）
  │   ├─ PATCH-5: grep override_acp_command + copilot-acp（✅ 已上游合并，仅验证）
  │   ├─ PATCH-7: grep 'python-socks' in pyproject.toml + tools/lazy_deps.py
  │   ├─ PATCH-9: grep 确认 OpenClaw 迁移不再写入 HERMES_GATEWAY_TOKEN
  │   ├─ PATCH-10: grep Feishu group trigger/context/config/doc/xlsx sentinels
  │   ├─ PATCH-11: grep per-platform skill allowlist + read-only toolset sentinels
  │   ├─ PATCH-12: grep reply_in_thread = False
  │   └─ PATCH-13: grep current-author prompt + Feishu trigger/batching regression tests
  │
  └─ 8c. Refresh saved diff
      ├─ 前提: _PATCH_APPLY_OK && 全部 _*_PATCH_OK 为 true
      ├─ 再次 _has_conflict_markers() → 不干净则拒绝刷新
      ├─ 干净且有 diff: 原子写 local-patches.diff + 写 .local-patches.base
      └─ 干净但无 diff: 提示 "patches may have been absorbed"

Step 8d: Gateway restart（post-patch）
  └─ 前提: _PATCH_APPLY_OK == true && gateway 正在运行
      └─ stop → sleep 2 → start → 轮询 PID（最多约 12s）→ 确认存活
      （hermes update 在 step 3 重启 gateway 时补丁尚未 apply，
       Python 进程 sys.modules 缓存旧模块，需重启才能加载补丁代码；
       macOS launchd 在 stop 后可能短暂 unloaded，因此不能假设固定 3s 内必起）
```

### 安全机制（及设计原因）

#### 1. 冲突标记检测：`_has_conflict_markers()` 而非 `git diff --check`

`git diff --check` 同时报告冲突标记**和** trailing whitespace / indent 问题。上游代码风格变化（如多一个尾部空格）就会触发误报，导致功能完好的 patch 被回滚。

外层仓库用 `.gitattributes` 对 `patches/*.diff` 设置 `-whitespace`：unified diff 里的合法空白上下文行可能表现为 `+ ` / ` `，不应让 `git diff --check` 把 patch 文件自身误判为 trailing whitespace。patch 文件有效性仍以 `git apply --check`、冲突标记扫描和重新生成 diff 比较为准。

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

#### 5. 额外改动保护

Step 3 只负责 `PATCHED_FILES` 之外的临时改动。脚本会用 `git stash push -u` 保存这些额外改动（包含 untracked 文件），再运行 `hermes update`；如果 stash 失败，脚本直接停止且不执行清理，避免误删未跟踪文件。若 update 后 `stash pop` 与上游冲突，脚本保留 stash 并提示用 `git stash list` 手动恢复。

#### 6. 上游 base commit 追踪

每次 Step 8c 成功刷新 diff 后，将当前 `hermes-agent` 的 HEAD SHA + UTC 时间戳写入 `patches/.local-patches.base`。当下次 update 补丁 apply 失败时，可以对比这个 base 和新的 HEAD 来定位是哪些上游 commit 引入了冲突：

```bash
# 查看自上次 patch 刷新以来上游改了哪些相关文件
BASE=$(cut -d' ' -f1 ~/.hermes/patches/.local-patches.base)
cd ~/.hermes/hermes-agent && git log --oneline ${BASE}..HEAD -- tools/skill_manager_tool.py tests/tools/test_skill_manager_tool.py hermes_cli/doctor.py pyproject.toml tools/lazy_deps.py plugins/platforms/feishu/adapter.py gateway/run.py agent/skill_utils.py tools/skills_tool.py toolsets.py
```

#### 7. 上游吸收检测

Step 8c 中，如果所有 `PATCHED_FILES` 与上游 HEAD 无差异（`_REFRESHED` 为空），说明补丁可能已被上游合并。脚本会提示清理 `PATCHED_FILES` 列表和本文档中的对应条目，避免后续更新反复 apply 一个空 diff。

### 已知局限

| 局限                            | 说明                                                                                                                                                                                                                                                                                |
| ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **单体 diff，不支持逐文件降级** | 所有 patch 在一个 diff 中。如果 5 个文件中只有 1 个冲突，整体 apply 失败，其余 4 个也不会被应用。`git apply --3way` 覆盖了大部分上下文偏移的情况；真冲突时需要手动 `git apply --reject` 逐文件处理。未来如果冲突频繁，考虑拆成 per-file diff 或改用 Python 脚本做更细粒度的 apply。 |
| **行为化验证依赖特征字符串**    | PATCH-2/5 的验证是 grep 固定字符串。如果上游重构了函数但保留了行为，grep 会误报 "inactive"。PATCH-1 用了真实 Python import + 调用，是最稳的方式；其他 patch 条件允许时应向这个模式靠拢。                                                                                            |
| **工程外补丁无版本对齐**        | PATCH-3 的 inline Python 替换依赖 `hermes completion zsh` 输出的固定格式。如果上游改了补全生成逻辑但仍有 bug，替换可能失效。目前有 "skip if already correct" 逻辑兜底。                                                                                                             |

### 受 `PATCHED_FILES` 管理的文件

```bash
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "hermes_cli/doctor.py"
    "pyproject.toml"
    "tools/lazy_deps.py"
    "optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"
    "website/docs/guides/migrate-from-openclaw.md"
    "gateway/authz_mixin.py"
    "gateway/config.py"
    "plugins/platforms/feishu/adapter.py"
    "gateway/run.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/skill_utils.py"
    "tools/skills_tool.py"
    "tests/tools/test_skills_tool.py"
    "toolsets.py"
    "tools/feishu_doc_tool.py"
    "tests/tools/test_feishu_tools.py"
    "tools/file_operations.py"
    "tests/tools/test_file_operations.py"
    "tests/gateway/feishu_helpers.py"
    "tests/gateway/test_config.py"
    "tests/gateway/test_feishu.py"
    "tests/gateway/test_feishu_bot_admission.py"
    "tests/gateway/test_feishu_bot_auth_bypass.py"
    "tests/gateway/test_session.py"
    "tests/gateway/test_session_env.py"
    "tests/hermes_cli/test_skills_config.py"
    "tests/hermes_cli/test_tools_config.py"
    "website/docs/reference/environment-variables.md"
    "website/docs/user-guide/configuration.md"
    "website/docs/user-guide/messaging/feishu.md"
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

## 当前版本：v0.17.0 (upstream `main` `5ecf3bf0`，2026-06-23)

**活跃补丁**：PATCH-1 / PATCH-2 / PATCH-6 / PATCH-7 / PATCH-9 / PATCH-10 / PATCH-11 / PATCH-12 / PATCH-13（共 9 条）。

**最近一次升级（v0.17.0 同 release 内迭代，+5 commits，basis `bb7ff7dc` → `5ecf3bf0`）要点**：

- 上游主线（release tag 维持 `v0.17.0 (2026.6.19)`）：**Agent / Gateway RPC**——`af7b7f632` 暴露 coding-context project facts 为结构化数据并新增 `project.facts` RPC（#51259），`211ba9c7d` 新增 one-shot LLM helper 与 `llm.oneshot` gateway RPC（#51261）。**Relay**——`45bc4fb37` 向 connector 声明 relevance policy，并补充 relay management plane contract 文档（#51248）。**Slack**——`219658416` 支持转录 Slack in-app voice message 的 `audio/mp4`，`5ecf3bf0e` 为重路由 voice clips 报告扩展名匹配出的 audio mimetype。
- patch apply：**全部 clean apply**——33 个 `PATCHED_FILES` 从 `local-patches.diff` 干净回贴到新基线 `5ecf3bf0`，无 3-way、无冲突；`patches/local-patches.diff` 与 `.local-patches.base` 刷新到 `5ecf3bf0e0726b8b33682bb5c3aad9679b7b5be4`。本轮未发现 PATCH 被上游吸收，PATCH-10/11/12 仍活跃，PATCH-4/5 仍由上游 sentinel 覆盖。上游只轻触 `gateway/run.py`（relay policy session var）这一处 patch 管理文件，相关 hunk 仅行号从约 `8390 → 8396`、`9705 → 9711` 等小幅漂移；行为化验证全部 OK。
- 依赖：`uv` 仍触发 `/Users/chenzhou/.local/share/uv/python` mismatch，日志中先出现 2 次失败，随后脚本用 `--python venv/bin/python` fallback 自愈（"Install recovered via explicit --python fallback"）；`npm audit fix` 报 no vulnerabilities，但仍改动 tracked `hermes-agent/package-lock.json`，按设计不纳入 `local-patches.diff`。Skills mirror 同步 **+0 / ~0 / -3**。
- 已知摩擦：`uv` python-path mismatch 每轮复发，当前 fallback 可恢复；`hermes-agent/package-lock.json` 仍为 npm/audit 生成漂移，保持在补丁跟踪之外，脚本已提示单独 review；本轮 patch 全程 in-script clean apply，无需手工 remap。
- 配置漂移：本次无 schema migration，`config.yaml` 仍为 v30（`hermes doctor` 报 `Config version up to date`）；doctor 剩 1 个 issue：`ALIBABA_CODING_PLAN_API_KEY` 无效。Gateway 已由脚本重启并加载补丁，service loaded，PID `76156`，`LastExitStatus=0`。

> 仅保留最近一次升级摘要；历次升级的逐版本叙述见 `README.md` § 版本记录。

### [PATCH-1] tools/skill_manager_tool.py — 自定义 skill 创建路径

| 字段     | 内容                                                                    |
| -------- | ----------------------------------------------------------------------- |
| **文件** | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 未上游合并（`_resolve_skill_dir()` 仍只用 `SKILLS_DIR / name`）      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：让 `_resolve_skill_dir()` 读 `config.yaml` 的 `skills.external_dirs`，第一个非官方目录作为新 skill 的基准路径；`_create_skill()` / `_delete_skill()` 同步适配，并加 `tests/tools/test_skill_manager_tool.py` 回归测试覆盖 external dir 路由与删除。

**验证**：Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("dummy_unit_test_skill")`，断言返回路径 startswith `~/.hermes/my-skills/`。

---

### [PATCH-2] hermes_cli/doctor.py — issue count 过报

| 字段     | 内容                   |
| -------- | ---------------------- |
| **文件** | `hermes_cli/doctor.py` |
| **状态** | 🟡 未上游合并          |

**问题**：`hermes doctor` 把所有注册但缺 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中用 `_get_platform_tools` 过滤出用户实际启用的 toolset，只对它们报 issue。

**验证**：Step 8b grep `from hermes_cli.tools_config import _get_platform_tools, PLATFORMS` 在 doctor.py 中存在。

---

### [PATCH-6] npm audit fix — node_modules 已知漏洞自动修复

| 字段     | 内容                                              |
| -------- | ------------------------------------------------- |
| **文件** | `node_modules/`（gitignored，非 `PATCHED_FILES`） |
| **状态** | 🟢 自动化（`hermes-update.sh` Step 4）            |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。

**修复**：在 `hermes-update.sh` Step 4 里 `hermes update` 完成后跑 `npm audit fix --quiet`。`node_modules/` 是 gitignored，不进 `PATCHED_FILES` / `local-patches.diff`，每次 update 后重跑即可。

---

### [PATCH-7] feishu 依赖声明缺少 python-socks

| 字段     | 内容                                   |
| -------- | -------------------------------------- |
| **文件** | `pyproject.toml`, `tools/lazy_deps.py` |
| **状态** | 🟡 未上游合并                          |

**问题**：`feishu` optional extra 和 `tools/lazy_deps.py` 的 `platform.feishu` 上游都只声明 `lark-oapi==1.5.3` + `qrcode==7.4.2`。代理网络下 `lark-oapi` 的 WebSocket 连接需要 SOCKS 支持，缺 `python-socks` 时 gateway 起来后报 `connecting through a SOCKS proxy requires python-socks` 并反复重连失败。

**修复**：在 `pyproject.toml` 的 `feishu` extra 和 `tools/lazy_deps.py` 的 `LAZY_DEPS["platform.feishu"]` 都加 `"python-socks==2.8.1"`。手动 `.[feishu]`、`.[all,feishu]`、和上游 lazy install 三条路径都能拿到 SOCKS。版本钉死风格与上游 2026-05-14 起 messaging extras `==X.Y.Z` 约定一致（避免 `>=2.0,<3` 被 `uv lock --check` 报漂移）。

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在。

> **2026-05-14**：原 patch 是 `python-socks>=2.0,<3`，针对 `lark-oapi>=1.5.3,<2` 行追加。上游 `c1eb2dcda` + `3955aefce` 把 feishu 钉到 `==1.5.3`+`==7.4.2` 后 3way 在该 hunk 报冲突，手合时改 `==2.8.1`。
> **2026-05-20**：上游 `[all]` 瘦身后 Feishu 等平台改走 `tools/lazy_deps.py` 首次使用时安装，PATCH-7 新增 `tools/lazy_deps.py` hunk 避免 clean venv 经 lazy install 启用 Feishu 时漏装。

---

### [PATCH-9] OpenClaw 迁移不再写入废弃 gateway token

| 字段     | 内容                                                                                                                         |
| -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                             |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；迁移文档同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本和迁移文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token`。

> **v0.15.1 升级注**：上游 `119390a2a` 在迁移文档同一表格里把 Working directory 行从 `MESSAGING_CWD` 改写到 `terminal.cwd`，与本地删 token 行不真冲突但相邻 hunk 上下文重合，3way 报冲突。手合规则：保留上游新版 Working directory 行 + 删 Gateway auth token 行。

---

### [PATCH-10] Feishu 群聊提及触发、上下文回填与群聊配置隔离

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `gateway/run.py`, `gateway/session_context.py`, `gateway/authz_mixin.py`, `hermes_cli/tools_config.py`, `tools/feishu_doc_tool.py`, `tools/file_operations.py`, `tests/gateway/feishu_helpers.py`, `tests/gateway/test_config.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_feishu_bot_admission.py`, `tests/gateway/test_feishu_bot_auth_bypass.py`, `tests/gateway/test_session_env.py`, `tests/tools/test_feishu_tools.py`, `tests/tools/test_file_operations.py`, `website/docs/reference/environment-variables.md`, `website/docs/user-guide/configuration.md`, `website/docs/user-guide/messaging/feishu.md` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

**问题**：上游 Feishu 群聊主要按 `@bot` 触发，无法表达“@bot 或 @指定本人账号才回复；其他群消息静默”。同时群聊和私聊共用 `feishu` 平台工具配置，难以给群聊设置更窄工具面；被触发时也缺少最近群消息上下文，导致只能看当前消息，不能基于近 30 条群聊记录回复。代答身份也需要区分“别人 @琛哥，让木马牛先代答”和“琛哥本人直接 @Hermes/木马牛派活”：前者需要身份澄清，后者不应重复自我介绍。群聊/普通 gateway 工具调用中也没有 Feishu comment context 的 thread-local client，`feishu_doc_read` 即使有 tenant credentials 也会失败；飞书缓存目录里的 `.xlsx` 附件会被通用 `read_file` 判成二进制，无法读出表格内容。

**修复**：新增 `mention_triggers`、`assistant_user_ids`、`assistant_identity_label`，支持 `bot` 与 `assistant_users` 两类触发；第三方 `@配置本人账号` 时注入 assistant-mode 约束：明确自己是琛哥的赛博小助手「木马牛」、琛哥可能在忙、只能先尝试代答；配置本人账号作为发送者直接 `@bot` / `@Hermes` 时，注入 configured-human mention 指令，明确发送者已知道 Hermes/木马牛是谁，不自我介绍、直接回答；若配置本人账号触发 assistant-user 分支，也跳过自我介绍。技术问题按 `llm-wiki → web_search/web_extract → 模型通用知识` 优先级回答；使用 `llm-wiki` 时明确先 `skill_view` 读取说明，再用 `read_file` / `search_files` 读取 `~/.hermes/wiki` 的真实内容，不把缺少 terminal 误判为缺少 wiki 权限；不懂/不确定时直接说明需要琛哥确认；工作安排、责任归属、承诺类事项使用强势明确口吻，但不得替琛哥承诺、担责或定责。新增 Feishu group history backfill：`history_backfill_limit`、`history_backfill_seconds`、`history_backfill_max_chars`。Gateway session 新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`，Feishu 群聊映射到 `feishu_group`，私聊仍为 `feishu`。授权层新增 `FEISHU_GROUP_ALLOWED_CHATS`，可授权群 chat_id 或 `*`，但不放开 DM。`feishu_doc_read` 无 comment client 时可从 env / `~/.hermes/.env` 构建 tenant client；`read_file` 在二进制检测前识别 `.xlsx`，用标准库 zip/xml 抽取 sheet 文本，旧 `.xls` 明确提示需要转换器。

**验证**：Step 8b grep `assistant_user_ids`、`_sender_is_configured_assistant_user`、`_fetch_channel_context`、`HERMES_SESSION_PLATFORM_CONFIG_KEY`、`feishu_group`、`FEISHU_GROUP_ALLOWED_CHATS`、`history_backfill_max_chars`、`_client_from_env`、`_read_spreadsheet`、`test_process_inbound_message_owner_bot_mention_skips_self_intro`、`test_doc_read_builds_env_client_outside_comment_context`、`test_read_file_extracts_xlsx_as_text`。定向测试覆盖设置加载、群历史格式化、未 @ 静默、@bot 触发、第三方 @本人账号触发代答、本人账号 @bot 触发免自我介绍、`feishu_group` session key、群授权不放开 DM、无 comment context 时从 env 构建 Feishu client 读 doc，以及最小 `.xlsx` 文件被 `read_file` 抽取出 sheet 名、表头和数据行。

**上游吸收判断**：如果上游后续原生提供等价的 Feishu mention trigger、assistant-user trigger、配置本人账号直接 @bot 时免自我介绍、history backfill、per-group platform config key、group chat allowlist、Feishu doc tenant-client fallback 与 `.xlsx` 附件文本读取，可将本补丁归档；保留验证 grep 作为 sentinel，或改成上游行为测试。

> **2026-06-22（落点迁移，非归档）**：上游 `560010547` `refactor(gateway): migrate ... adapters to bundled plugins` 把 `gateway/platforms/feishu.py` 整体迁移为 bundled plugin `plugins/platforms/feishu/adapter.py`（约 5511 行单体）。本补丁的 feishu hunk 落点随之从 `gateway/platforms/feishu.py` 改为 `plugins/platforms/feishu/adapter.py`，19 个 hunk 内容不变、上下文锚点一致，改写路径后 `git apply` 干净落地；`feishu_helpers.py` 与 `test_feishu*.py` 中的 `FeishuAdapter` import 同步从 `gateway.platforms.feishu` 改为 `plugins.platforms.feishu.adapter`。`hermes-update.sh` 的 `PATCHED_FILES`、`FEISHU_PY` 与本块文件清单已同步。补丁功能未被上游吸收，仍为活跃补丁。

> **2026-06-23（assistant-mode 文案优化，非归档）**：仅改 `plugins/platforms/feishu/adapter.py` 与 `tests/gateway/test_feishu.py`，纯 prompt + 上下文可见性调整，无新增配置/字段。三处优化：
>
> 1. **身份措辞**统一为「琛哥的赛博小助手『木马牛』」（原为「赛博助手」）。
> 2. **自我介绍节流**：`_format_channel_context` 不再丢弃 bot 自身历史消息（原 `sender.id == _app_id` 直接 `continue`），改由 `_history_sender_label` 标注为 `木马牛 (assistant, you)`；assistant-mode prompt 据此规定——若近 ~10 条消息 / ~5 分钟内的频道上下文里已出现自我介绍，则不再重复介绍、直接自然作答（默认 backfill 窗口 20 条 / 1800s 足够覆盖）。属启发式（模型据可见历史判断），非硬编码计数。
> 3. **风控/沙箱话术**：遇沙箱拦截或不允许的操作时，不以「能力不足」道歉，而是自然、轻松、多变地说明这是琛哥**有意设计**的安全边界（保护其电脑上的机密、防止 setup 被照搬/逆向），并引导对方等琛哥有空当面问；prompt 给出可自由改写的中文示例，强调不照搬模板、不僵硬。
>
> 验证：`tests/gateway/test_feishu.py` 207 passed（`test_fetch_channel_context_formats_recent_group_messages` 断言已更新为包含 `[木马牛 (assistant, you)] prior self` 行）。Step 8b 既有 sentinel（`_fetch_channel_context` 等）不变仍覆盖。

> **2026-06-23（本人 @Hermes 免自我介绍，非归档）**：`plugins/platforms/feishu/adapter.py` 在群聊入站处理里新增 sender 身份判断：如果消息发送者本身就是 `assistant_user_ids` 中配置的琛哥账号，且本条消息是直接 `@bot` 触发，则注入短 prompt 明确“发送者已知道 Hermes/木马牛是谁，直接回答，不要自我介绍”；若别人 `@琛哥` 触发代答，仍保留 assistant-mode 的首次身份说明与节流逻辑。外层运行记忆 `memories/USER.md` 另行同步收窄全局自我介绍偏好，避免与该群聊分支冲突；该记忆文件不属于 `local-patches.diff` 管理范围。
>
> 验证：`venv/bin/python -m pytest tests/gateway/test_feishu_bot_admission.py -q`（66 passed）；`venv/bin/python -m pytest tests/gateway/test_feishu.py -q -k 'fetch_channel_context_detects_recent_self_intro or fetch_channel_context_formats_recent_group_messages'`（2 passed, 209 deselected）。

---

### [PATCH-11] 平台级 skill allowlist 与只读 skill 工具集

| 字段     | 内容                                                                                                                                                                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `agent/prompt_builder.py`, `tools/skills_tool.py`, `tests/tools/test_skills_tool.py`, `toolsets.py`, `tests/hermes_cli/test_skills_config.py`, `tests/hermes_cli/test_tools_config.py`, `website/docs/user-guide/configuration.md` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                              |

**问题**：`skills.disabled` 只能做全局/平台禁用，无法表达“群聊只允许少数安全 skill，但私聊保持不受限”。同时上游 `skills` toolset 同时包含 `skills_list`、`skill_view`、`skill_manage`；群聊只想读取 `llm-wiki` 时，如果直接启用 `skills`，会把写/改 skill 的 `skill_manage` 也暴露给群成员。

**修复**：新增 `skills.platform_allowed.<platform>` allowlist。未配置表示保持原行为；配置为空列表表示该平台禁用所有 skill；配置具体名称表示只允许这些 skill。`build_skills_system_prompt`、`skills_list`、`skill_view`、skill config var discovery 都遵守该 allowlist，并优先使用 `HERMES_SESSION_PLATFORM_CONFIG_KEY`，因此 Feishu 群聊能独立使用 `feishu_group` allowlist。新增内部工具集 `skills_readonly`，只包含 `skills_list` 与 `skill_view`，不包含 `skill_manage`。本地分类 skill 的 `category:skill` 规范名也按短名兜底匹配 allowlist，避免配置已允许 `feishu-docs` 时 `skill_view("productivity:feishu-docs")` 被误拒。

**验证**：Step 8b grep `get_allowed_skill_names` 在 `agent/skill_utils.py`、`agent/prompt_builder.py`、`tools/skills_tool.py` 中存在，并 grep `toolsets.py` 中存在 `skills_readonly`、`file_readonly`、`skills_list`、`skill_view`、`read_file`、`search_files`，另 grep `tests/tools/test_skills_tool.py` 中存在 `test_qualified_local_skill_allowed_by_bare_name`。定向测试覆盖空 allowlist 禁用全部 skill、命名 allowlist 只允许指定 skill、qualified 本地分类 skill 按短名通过、`feishu_group` 独立工具集配置，以及内部 `file_readonly` 工具集不会被平台配置过滤。

**本机当前配置**：`config.yaml` 中 `platform_toolsets.feishu_group` 使用 `[web, clarify, feishu_doc, skills_readonly, file_readonly]`，`skills.platform_allowed.feishu_group: [llm-wiki, feishu-docs, character-voices]`。`plugins/sandbox/config.yaml` 对非 owner Feishu 群聊额外放行 `skills_list`、`skill_view`、`feishu_doc_read`、`read_file`、`search_files`、`terminal`，但 skill 名单仍被 `feishu_group` allowlist 限制；文件读取/检索也被 `allowed_read_roots_for_outsider_groups` 限制到 wiki/cache/tmp 相关目录。因此群聊可读取允许的 skill、读取 Feishu 文档和已缓存/临时文件，但没有 `skill_manage`、`write_file`、`patch`、`todo`；Feishu 私聊未配置 `skills.platform_allowed.feishu`，保持 skill 不受群聊 allowlist 限制。

**上游吸收判断**：如果上游后续提供平台级 skill allowlist 与只读 skill 工具集，且能通过 `feishu_group` 或等价群聊上下文独立约束 skills，可归档本补丁。

---

### [PATCH-12] Feishu 回复不再创建话题（始终普通引用回复）

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：bot 在飞书里的回复会变成一个**话题（Thread）**，嵌在被回复消息下方、像评论而非主消息流里的正常回复。根因有两处叠加：入站处理 `adapter.py` 把 `thread_id = message.thread_id or message.root_id`——飞书普通群里只要消息处于「引用回复链」中 `root_id` 就有值，于是 `source.thread_id` 被填上并随 metadata 透传；出站 `_send_raw_message` 据此 `reply_in_thread = bool(metadata["thread_id"])`，飞书 `im.v1.message.reply` 接口在该标志为真时把回复挂成话题。结果任何引用链中的消息都触发话题化。

**修复**：在所有飞书发送的唯一出口 `_send_raw_message` 钉死 `reply_in_thread = False`，并把「引用目标」回退从依赖 `thread_id` 解耦（`effective_reply_to` 改为 `reply_to or metadata["reply_to_message_id"]`，不再要求 `thread_id` 存在）。这样无论普通群还是话题群，bot 都以**普通引用回复**（`message.reply` + `reply_in_thread=False`）跟在被回复消息后面发一条新消息，绝不开话题。入站 `thread_id`（含 `root_id` 回退）保留不动——它仍用于 `reply_to_message_id` 提取与 channel/session 路由，只是不再决定「是否开话题」。

**验证**：Step 8b grep `plugins/platforms/feishu/adapter.py` 中存在 `reply_in_thread = False`。定向测试覆盖：带 `thread_id` metadata 的回复 `reply_in_thread` 为 False、用 `metadata["reply_to_message_id"]` 作引用目标且不开话题、文档回复同样不开话题（`test_send_never_replies_in_thread_even_with_thread_metadata`、`test_send_uses_metadata_reply_target_without_threading`、`test_send_document_reply_never_uses_thread_flag`）；`tests/gateway/test_feishu.py` 全量 207 passed。

**上游吸收判断**：如果上游后续不再把 `root_id` 并入 `thread_id`、或为 Feishu 回复提供「普通引用 vs 话题」开关并默认普通引用，可归档本补丁。

---

### [PATCH-13] 群聊当前发言人身份锚定

| 字段     | 内容                                                                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_session.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_feishu_bot_admission.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                              |

**问题**：群聊里模型会把 `memories/USER.md` / profile 中的 owner 信息误当成当前说话人，尤其是全局记忆写着“周琛 / 琛哥”时；同时 Feishu 群消息触发逻辑先判断 `assistant_users` 再判断 `@bot`，一条消息同时提到 bot 和配置本人账号时会走错触发分支。另一个实际身份风险是 Feishu 文本/媒体 debounce 批处理只按会话和 reply/thread 上下文聚合，未显式要求发送者一致；在共享 session 或同线程场景里，短时间内不同人的消息可能被拼到第一条事件上，沿用第一条的 sender source。

**修复**：非 DM session prompt 把当前说话人从 `User` 改为 `Current message author`，并加入 `Current-author rule`：当前回答必须以本条消息作者为准，持久 profile/USER.md 只能描述 bot owner/default user，不能自动当成 speaker。Feishu 触发顺序改为直接 `@bot` 优先于 `assistant_users`。文本和媒体批处理新增 sender identity 匹配，要求 `user_id`、`user_id_alt`、`user_name` 一致才允许合并。

**验证**：Step 8b grep `gateway/session.py` 中存在 `Current message author`、`Current-author rule`、`do not treat it as the speaker`，并 grep 回归测试 `test_bot_mention_takes_priority_over_assistant_user_mention`、`test_text_batch_does_not_merge_different_senders` 与 session prompt 断言。定向测试覆盖群聊 prompt 不把 owner profile 当 speaker、直接 @bot 优先于 assistant-user trigger、不同发送者的 Feishu 文本批处理不会合并。

**上游吸收判断**：如果上游后续在多用户 session prompt 中原生区分 current author 与 persistent owner/profile，并保证 Feishu trigger priority 与 batching 都按 sender identity 隔离，可归档本补丁。

---

## v0.13.0 archive — PATCH-3 上游合并

### [PATCH-3] completions/\_hermes — Tab 补全无效（`_arguments` 无效参数语法）

| 字段         | 内容                                                                            |
| ------------ | ------------------------------------------------------------------------------- |
| **文件**     | `completions/_hermes`（工程外，不在 `PATCHED_FILES` 中）                        |
| **状态**     | ✅ 已上游合并（v0.13.0，commit `fe61d95b4`）                                    |
| **适用版本** | v0.9.0–v0.12.0 需要本地 patch；v0.13.0+ 上游 `hermes completion zsh` 输出已正确 |

**问题（历史）**：在任何新终端按 Tab 键补全 `hermes` 命令，提示符短暂出现 `...` 随即消失，无任何补全菜单。`hermes completion zsh` 生成的 `_arguments` 规格将互斥说明符 `(...)` 和替代语法 `{...}` 混用，是无效语法：

```zsh
# 无效：zsh _arguments 不支持 (...){...} 组合写法
'(-h --help){-h,--help}[Show help and exit]'
```

**上游修复**：commit `fe61d95b4`（`fix(completion): use valid zsh _arguments exclusion-group syntax`，关闭 issue #22686）将生成器改为：

```zsh
'(-)'{-h,--help}'[Show help and exit]'
'(-)'{-V,--version}'[Show version and exit]'
'(-)'{-p,--profile}'[Profile name]:profile:_hermes_profiles'
```

利用 zsh brace expansion 把一行展开成两个独立规格，`(-)` 表示出现时排除其他所有选项。

**本地处置**：`hermes-update.sh` Step 7 中针对旧坏格式的 `grep -q '){-h,--help}'`、`grep -q '){-V,--version}'`、`grep -q '){-p,--profile}'` 检测块作为回归 sentinel 保留。新格式不会触发匹配，脚本日志直接输出 `PATCH-3: upstream completion output already uses correct syntax — no fix needed`。如未来上游回滚到坏格式，inline Python rewrite 会自动重新介入。

---

## v0.11.x archive — PATCH-4 上游合并

### [PATCH-4] hermes_cli/main.py — `hermes dashboard` 每次启动重复 build

| 字段         | 内容                                                  |
| ------------ | ----------------------------------------------------- |
| **文件**     | `hermes_cli/main.py`                                  |
| **状态**     | ✅ 已上游合并（v0.11.x，commit `5b5a53a1`）           |
| **适用版本** | v0.9.0–v0.11.0 需要本地 patch；v0.11.x 之后已上游修复 |

**问题**：`hermes dashboard` 每次启动都在 `HERMES_WEB_DIST` 未设置时直接调用 `_build_web_ui()`；即使构建产物已存在，也会重复执行 `npm install + npm run build`，导致启动耗时数十秒。

**修复**：上游在 commit `5b5a53a155857e63ec7f7eeb373049ad224fc92f`（`fix(cli): check hermes_cli/web_dist/ not web/dist/ for build staleness`）中新增 `_web_ui_build_needed()` helper：以 `hermes_cli/web_dist/.vite/manifest.json`（fallback `index.html`）作 sentinel，并在 `_build_web_ui()` 内部判断 sentinel 是否新过所有 `.ts/.tsx/.js/.jsx/.css/.html/.vue` 源码及 `package.json/package-lock.json/vite.config.*` 等元数据；不需要重建直接早返。该实现比本地原 patch 更完整（额外覆盖 staleness），本地 PATCH-4 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：`hermes-update.sh` Step 8b 仍保留 grep `_web_ui_build_needed` 的存在性检查，用于在上游回滚时及时告警。

---

## v0.11.0 archive — PATCH-8 上游合并

### [PATCH-8] agent/transports/types.py — Gemini tool-call replay 丢失 thought_signature

| 字段         | 内容                                                                |
| ------------ | ------------------------------------------------------------------- |
| **文件**     | `agent/transports/types.py`, `tests/agent/transports/test_types.py` |
| **状态**     | ✅ 已上游合并（v0.11.0，commit `f5af6520`）                         |
| **适用版本** | v0.10.0 需要本地 patch；v0.11.0+ 已上游修复                         |

**问题**：Gemini 3.1 / Gemini 3 Flash 这类 thinking 模型在发出 tool call 后，下一轮 replay 必须把 tool call 上的 `thought_signature` 原样带回。当前版本已经把旧的 `_nr_to_assistant_message` shim 演进成 `ToolCall` dataclass + property 兼容层，但这里只暴露了 `call_id` / `response_item_id`，没有暴露 `extra_content`。于是 `run_agent.py` 中的 `getattr(tool_call, "extra_content", None)` 永远拿到 `None`，Gemini / Vertex 在 replay 下一轮直接返回 HTTP 400：`missing thought_signature`，然后触发 fallback 到 `qwen3-max`。

**修复**：上游在 commit `f5af6520d0bfac5b17c9ce460a5a06bf3249972c` 中给 `ToolCall` 增加了 `extra_content` 兼容属性，并补上了相应回归测试；本地 PATCH-8 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：最初的等价修复线索来自上游 PR `#14423`；最终关闭本 issue 的是 commit `f5af6520`。当前 `main` / v0.11.0 已包含该修复，因此本地只保留文档记录，不再维护源码 patch。

---

## v0.10.0 archive — PATCH-5 上游合并

### [PATCH-5] tools/delegate_tool.py — ACP 子进程路由缺失

| 字段         | 内容                                         |
| ------------ | -------------------------------------------- |
| **文件**     | `tools/delegate_tool.py`                     |
| **状态**     | ✅ 已上游合并（v0.10.0，commit hash 未记录） |
| **适用版本** | v0.9.0 需要本地 patch；v0.10.0+ 已上游修复   |

**问题**：`delegate_task(acp_command="copilot")` 传入 ACP 命令后，子 agent 的 `provider` 仍继承父 agent（如 `gemini`），未切换为 `"copilot-acp"`。`AIAgent` 构造时只在 `provider == "copilot-acp"` 时启用 ACP subprocess 通道，导致 `acp_command`/`acp_args` 被存储但从未使用，子 agent 直接走父 agent 的 API（如 Gemini），最终超时失败。

**修复**：在 `_build_child_agent()` 解析 `effective_acp_command` 之后，检测 `override_acp_command` 是否被显式设置：若是，强制 `effective_provider = "copilot-acp"`、`effective_base_url = "acp://copilot"`，确保 `AIAgent.__init__` 走 `CopilotACPClient` 子进程通道。

**上游追踪**：v0.10.0 合入等价修复（具体吸收 commit 未在本地记录），本地 PATCH-5 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。`hermes-update.sh` Step 8b 保留 grep `override_acp_command` + `copilot-acp` 的存在性检查，用于在上游回滚时及时告警。

---
