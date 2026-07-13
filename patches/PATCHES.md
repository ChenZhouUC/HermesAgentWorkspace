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

| 类型           | 代表                                            | 管理方式                                                                                                                                                                                                                           |
| -------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁** | PATCH-1/7/9/10/11/12/13/14/15/16/17/18/19/20/21 | 统一 diff (`local-patches.diff`) + `PATCHED_FILES` 数组 + 行为化验证                                                                                                                                                               |
| **工程外补丁** | PATCH-3                                         | `hermes-update.sh` Step 7 用 inline Python 检测坏格式后就地重写；上游修复后自动跳过                                                                                                                                                |
| **运行时补丁** | PATCH-6                                         | `npm audit fix`，仅作用于 `node_modules/`（gitignored），每次 update 后重新执行                                                                                                                                                    |
| **已上游合并** | PATCH-2/3/4/5/8                                 | PATCH-5 于 v0.10.0 合并；PATCH-8 于 v0.11.0 合并；PATCH-4 于 v0.11.x 通过上游 commit `5b5a53a1` 合并；PATCH-3 于 v0.13.0 通过上游 commit `fe61d95b4` 合并；PATCH-2 于 v0.18.0 通过上游 commit `6b21a935a` 合并；本地冗余代码已移除 |

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
  │   ├─ PATCH-2: grep _get_platform_tools in doctor.py（✅ 已上游合并 v0.18.0）
  │   ├─ PATCH-3: Step 7 中对 `){-h,--help}` / `){-V,--version}` / `){-p,--profile}` 做回归检测（✅ 已上游合并 v0.13.0）
  │   ├─ PATCH-4: grep _web_ui_build_needed in main.py（✅ 已上游合并，仅验证）
  │   ├─ PATCH-5: grep override_acp_command + copilot-acp（✅ 已上游合并，仅验证）
  │   ├─ PATCH-7: grep 'python-socks' in pyproject.toml + tools/lazy_deps.py
  │   ├─ PATCH-9: grep 确认 OpenClaw 迁移不再写入 HERMES_GATEWAY_TOKEN
  │   ├─ PATCH-10: grep Feishu group trigger/context/config/doc/xlsx sentinels
  │   ├─ PATCH-11: grep per-platform skill allowlist + read-only toolset + Feishu group approval hard-block sentinels
  │   ├─ PATCH-12: grep reply_in_thread=False + metadata.thread_id ignored + Feishu final-only display defaults
  │   ├─ PATCH-13: grep current-author prompt + Feishu trigger/batching regression tests
  │   ├─ PATCH-14: grep people-profile/_load_people_profiles/_lookup_person + group-profile/_load_group_profiles/_lookup_group/service_hours/_GROUP_TOOL_LIMITATION_RULE + TestPeopleProfileInjection/TestGroupProfileInjection/service-hours regression
  │   ├─ PATCH-15: grep _backfill_sender_attachments/_backfill_reply_attachments/_mark_attachment_backfilled + _FEISHU_BACKFILL_WINDOW_SECONDS/_backfilled_attachment_ids in adapter.py
  │   ├─ PATCH-17: grep Vertex include_thoughts=false + single-level {"google":…} + hidden-thoughts regression test
  │   ├─ PATCH-18: grep doctor Vertex provider/profile/env hints + google model slug regression test
  │   ├─ PATCH-19: grep get_vertex_fallback_config/apply_global_project_override + vertex-fallback in auth.py + has_vertex_fallback_credentials + name="vertex-fallback" + fallback regression test
  │   ├─ PATCH-20: grep _known_provider_model_supports_vision + vertex-fallback + decide_video_input_mode + _pending_native_video_paths_by_session (run.py) + gemini-3.1-pro-preview / video data-url routing regression tests
  │   └─ PATCH-21: grep Matrix lazy-feature identity anchor + shared-aiohttp regression test
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
| **行为化验证依赖特征字符串**    | PATCH-5 与已归档 PATCH 的 sentinel 验证是 grep 固定字符串。如果上游重构了函数但保留了行为，grep 会误报 "inactive"。PATCH-1 用了真实 Python import + 调用，是最稳的方式；其他 patch 条件允许时应向这个模式靠拢。                                                                     |
| **工程外补丁无版本对齐**        | PATCH-3 的 inline Python 替换依赖 `hermes completion zsh` 输出的固定格式。如果上游改了补全生成逻辑但仍有 bug，替换可能失效。目前有 "skip if already correct" 逻辑兜底。                                                                                                             |

### 受 `PATCHED_FILES` 管理的文件

```bash
PATCHED_FILES=(
    "tools/skill_manager_tool.py"
    "tests/tools/test_skill_manager_tool.py"
    "pyproject.toml"
    "uv.lock"
    "tools/lazy_deps.py"
    "optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py"
    "website/docs/guides/migrate-from-openclaw.md"
    "gateway/authz_mixin.py"
    "gateway/config.py"
    "plugins/platforms/feishu/adapter.py"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "gateway/stream_consumer.py"
    "hermes_cli/doctor.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/skill_utils.py"
    "tools/skills_tool.py"
    "tests/tools/test_skills_tool.py"
    "toolsets.py"
    "tools/feishu_doc_tool.py"
    "tests/tools/test_feishu_tools.py"
    "tools/file_operations.py"
    "tools/read_extract.py"
    "tests/tools/test_file_operations.py"
    "tests/tools/test_read_extract.py"
    "tests/gateway/feishu_helpers.py"
    "tests/gateway/test_config.py"
    "tests/gateway/test_feishu.py"
    "tests/gateway/test_document_context_note.py"
    "tests/gateway/test_feishu_bot_admission.py"
    "tests/gateway/test_feishu_bot_auth_bypass.py"
    "tests/gateway/test_session.py"
    "tests/gateway/test_session_env.py"
    "tests/gateway/test_stream_consumer_silence.py"
    "tests/hermes_cli/test_doctor.py"
    "tests/hermes_cli/test_skills_config.py"
    "tests/hermes_cli/test_tools_config.py"
    "website/docs/reference/environment-variables.md"
    "website/docs/user-guide/configuration.md"
    "website/docs/user-guide/messaging/feishu.md"
    "plugins/model-providers/vertex/__init__.py"
    "tests/hermes_cli/test_vertex_provider.py"
    "agent/vertex_adapter.py"
    "hermes_cli/auth.py"
    "agent/auxiliary_client.py"
    "agent/image_routing.py"
    "tests/agent/test_image_routing.py"
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

## 当前版本：v0.18.2 (upstream `main` `7acaff5e`，2026-07-11)

**活跃补丁**：PATCH-1 / PATCH-6 / PATCH-7 / PATCH-9 / PATCH-10 / PATCH-11 / PATCH-12 / PATCH-13 / PATCH-14 / PATCH-15 / PATCH-16 / PATCH-17 / PATCH-18 / PATCH-19 / PATCH-20 / PATCH-21（共 16 条）。

**最近一次升级（v0.18.2 main 滚动，+118 commits，basis `79f12748` → `7acaff5e`）要点**：

- 上游主线：Config/Agent 鲁棒性——CLI、Gateway、STT/TTS、Web、toolsets 对 null / scalar 配置统一 fail-safe（`bdecf0ab` / `46613071` / `50c66b2f` / `89371216` / `56932657` / `07271a6f`），tool-call 参数与 registry result contract 加固（`5e50f18b` / `f8361d29`）；Gateway/Cron/Memory——SessionStore 阻塞 I/O 全部移出 event loop、收敛 async boundary 与 save/reset races（`24c2a401` / `08e9dcf1` / `9d38a230` / `b3f77f5c` / `b196ce80`），cron profile store / webhook runtime 隔离、活跃 one-shot 与 claim heartbeat 防误清（`ec0227b4` / `f82c7139` / `9b72995a` / `dabae386`），holographic SQLite 连接按真实 DB 共享（`b5226caf` / `a8010466`）；Feishu——Channel signaling SDK 与 group @mention UA tag 落地，`lark-oapi` 升至 1.6.8（`949e4cb7` / `651e632b`）；Desktop/Dashboard/TUI——Hermes Cloud 登录发现、soft gateway switch、vibe hearts、chat zoom / draft / async session context 修复，以及 dashboard 粘贴/拖入图片（`c101207b` / `b3bde1fb` / `422d9da9` / `301acc9e` / `2afa92c7` / `7acaff5e`），TUI slash worker 支持 profile-local MCP（`623165a6`）；Providers/Tools/Security——custom catalog probe policy、Nous Portal 路由与共享 token 恢复（`5f00f36b` / `0629caac` / `3aeaf375` / `ca651354` / `0e67c723`），Windows MSYS path、web_extract 输入/顺序/短结果边界与确定性 tool-output risk（`3f8b2200` / `7ae9faec` / `459cf340` / `c2a40b2d` / `b9b463f3`）。
- patch apply：首轮 `git apply` / zero-context / 3-way 整体失败，逐文件确认仅 `pyproject.toml`、`tools/lazy_deps.py` 与 `tests/gateway/test_feishu.py` 因 Feishu SDK 版本及测试插入点漂移需 rebase；其余 46 文件可直接/带 offset 应用。锚点包括 `gateway/config.py 1211→1228`、`gateway/run.py` 多段 `+1/+5/+20/+29/+30`、`gateway/session.py +1`、`adapter.py 4861→4867`、`test_config.py 1029→1088`、`test_feishu.py 414→483`、`test_skills_config.py +28`；PATCH-1 另补齐“external dir 尚不存在也应创建”的真实回归。升级后新增 PATCH-21，以 `mautrix` identity anchor 阻断核心 aiohttp 对未启用 Matrix 的误激活，并把 `tests/tools/test_lazy_deps.py` 纳入监管。最终 50 files **clean apply**，PATCH-1/7/9/10/11/12/13/14/15/16/17/18/19/20/21 sentinel、PATCH-2/4/5 upstream guards 与 sandbox plugin verify 全 OK；无新退役。
- 依赖：release / editable 版本维持 `0.18.2 (2026.7.7.2)`；active lazy backend `platform.feishu` 随上游刷新到 `lark-oapi 1.6.8`，本地 `python-socks 2.8.1` 保留；npm root/ui-tui/web 重装并 rebuild web UI，`npm audit` no vulnerabilities；Skills mirror 首跑 `+0/~0/-4`。升级后 PATCH-21 让从未启用的 Matrix 不再进入 refresh，真实 active backend 15 项全部 current；PATCH-6 用临时、版本钉死、仅限 Hermes update 的 npm policy 覆盖 `agent-browser/esbuild/fsevents/unicode-animations`，实跑 root + ui-tui/web `npm ci` 无 blocked warning 且运行产物正常；本轮 `uv` 未触发 python-path fallback。
- 已知摩擦：首次回贴冲突按新上游锚点保守重放；`FEISHU_TEST_PY` 在 PATCH-12 检查前未赋值导致的 `set -u` 中止已修复。Matrix/python-olm 重复失败与 npm 四项 allowScripts 重复提示均已分别由 PATCH-21 / PATCH-6 规避；npm policy 使用精确版本 pin，上游若升级这些可执行脚本包会重新提示并要求复核，这是刻意保留的供应链安全 gate，不视为回归。最终完整 update exit 0、无 Recommended actions。
- 配置漂移：最终 `hermes doctor` 显示 `Config version up to date (v33)`、`All checks passed`；Gateway plist matches current install，launchd PID `61895` 已重启加载 patched modules；仅保留未登录 auth provider、未配置 optional tool/API key、Skills Hub 未初始化等可选提示。

> 仅保留最近一次升级摘要；历次升级的逐版本叙述见 `README.md` § 版本记录。

### [PATCH-1] tools/skill_manager_tool.py — 自定义 skill 创建路径

| 字段     | 内容                                                                    |
| -------- | ----------------------------------------------------------------------- |
| **文件** | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 未上游合并（`_resolve_skill_dir()` 仍只用 `SKILLS_DIR / name`）      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：让 `_resolve_skill_dir()` 直接按配置顺序读取 `skills.external_dirs`，第一个非官方目录作为新 skill 的基准路径；即使目录尚不存在也由 create 建立，避免 discovery helper 只返回既存目录时错误回落官方 root。`_create_skill()` / `_delete_skill()` 同步适配，并加 `tests/tools/test_skill_manager_tool.py` 回归测试覆盖 external dir 路由、缺失目录创建与删除。

**验证**：Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("dummy_unit_test_skill")`，断言返回路径 startswith `~/.hermes/my-skills/`。

---

### [PATCH-6] npm 依赖安全维护 — audit fix + install-script policy

| 字段     | 内容                                                       |
| -------- | ---------------------------------------------------------- |
| **文件** | `hermes-update.sh` + `node_modules/`（gitignored）         |
| **状态** | 🟢 自动化（Step 3 scoped policy + Step 4 `npm audit fix`） |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。Node 26 / npm 12 进一步默认阻止未经审核的 dependency lifecycle scripts；本仓 update 的 root + ui-tui/web 安装会反复提示 `agent-browser@0.26.0`、`esbuild@0.28.1`、`fsevents@2.3.3`、`unicode-animations@1.0.3` 未被 `allowScripts` 覆盖。四个包当前产物实际可用，但每次升级重复告警；用 `dangerously-allow-all-scripts` 会把未来任意传递依赖也放行，不可接受。

**修复**：保留 Step 4 的 `npm audit fix --quiet`；同时在调用 `hermes update` 前为 npm ≥12 创建权限为 0600 的临时 global-config，仅写入四个已审核且**版本钉死**的 allow 条目，并通过 `NPM_CONFIG_GLOBALCONFIG` 只传给本轮 `hermes update` / audit，结束或异常退出均删除。不会修改 `~/.npmrc`，不会影响其他项目，也不会继承未来版本的脚本权限。`agent-browser` postinstall 只校验/准备对应平台 binary，`esbuild` 校验平台 binary，`fsevents` 提供 macOS native watcher，`unicode-animations` 在上游强制的 `CI=1` 环境中 no-op。

**验证**：以相同临时 policy 实跑 root `npm ci --workspaces=false` 与 ui-tui/web workspace `npm ci`，均无 `install scripts blocked` / `not covered by allowScripts`；随后 audit 恢复完整 workspace 产物，`agent-browser 0.26.0`、`esbuild 0.28.1`、`require("fsevents")`、`require("unicode-animations")` 全部可用，package.json / lockfile 无 tracked drift。

---

### [PATCH-7] feishu 依赖声明缺少 python-socks

| 字段     | 内容                                   |
| -------- | -------------------------------------- |
| **文件** | `pyproject.toml`, `tools/lazy_deps.py` |
| **状态** | 🟡 未上游合并                          |

**问题**：`feishu` optional extra 和 `tools/lazy_deps.py` 的 `platform.feishu` 上游当前都只声明 `lark-oapi==1.6.8` + `qrcode==7.4.2`。代理网络下 `lark-oapi` 的 WebSocket 连接需要 SOCKS 支持，缺 `python-socks` 时 gateway 起来后报 `connecting through a SOCKS proxy requires python-socks` 并反复重连失败。

**修复**：在 `pyproject.toml` 的 `feishu` extra 和 `tools/lazy_deps.py` 的 `LAZY_DEPS["platform.feishu"]` 都加 `"python-socks==2.8.1"`。手动 `.[feishu]`、`.[all,feishu]`、和上游 lazy install 三条路径都能拿到 SOCKS。版本钉死风格与上游 2026-05-14 起 messaging extras `==X.Y.Z` 约定一致（避免 `>=2.0,<3` 被 `uv lock --check` 报漂移）。

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在。

---

### [PATCH-9] OpenClaw 迁移不再写入废弃 gateway token

| 字段     | 内容                                                                                                                         |
| -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                             |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；迁移文档同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本和迁移文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token`。

---

### [PATCH-10] Feishu 群聊提及触发、上下文回填与群聊配置隔离

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `gateway/run.py`, `gateway/session_context.py`, `gateway/authz_mixin.py`, `hermes_cli/tools_config.py`, `tools/feishu_doc_tool.py`, `tools/file_operations.py`, `tests/gateway/feishu_helpers.py`, `tests/gateway/test_config.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_feishu_bot_admission.py`, `tests/gateway/test_feishu_bot_auth_bypass.py`, `tests/gateway/test_session_env.py`, `tests/tools/test_feishu_tools.py`, `tests/tools/test_file_operations.py`, `website/docs/reference/environment-variables.md`, `website/docs/user-guide/configuration.md`, `website/docs/user-guide/messaging/feishu.md` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |

**问题**：上游 Feishu 群聊主要按 `@bot` 触发，无法表达“@bot 或 @指定本人账号才回复；其他群消息静默”。同时群聊和私聊共用 `feishu` 平台工具配置，难以给群聊设置更窄工具面；被触发时也缺少最近群消息上下文，导致只能看当前消息，不能基于近 30 条群聊记录回复。代答身份也需要区分“别人 @琛哥，让木马牛先代答”和“琛哥本人直接 @Hermes/木马牛派活”：前者需要身份澄清，后者不应重复自我介绍。群聊/普通 gateway 工具调用中也没有 Feishu comment context 的 thread-local client，`feishu_doc_read` 即使有 tenant credentials 也会失败；飞书缓存目录里的 `.xlsx` 附件会被通用 `read_file` 判成二进制，无法读出表格内容。此外，群聊里纯 `@bot`（剥离 mention 后文本为空、无媒体）被上游硬编码直接丢弃（`adapter.py` 空文本 guard，源自上游 `e86acad8f`），无法表达「@ 一下让你看上文 / 看我引用的这条消息」这类常见意图。

**修复**：新增 `mention_triggers`、`assistant_user_ids`、`assistant_identity_label`，支持 `bot` 与 `assistant_users` 两类触发；第三方 `@配置本人账号` 时注入 assistant-mode 约束：明确自己是琛哥的赛博小助手「木马牛」、琛哥可能在忙、只能先尝试代答；配置本人账号作为发送者直接 `@bot` / `@Hermes` 时，注入 configured-human mention 指令，明确发送者已知道 Hermes/木马牛是谁，不自我介绍、直接回答；若配置本人账号触发 assistant-user 分支，也跳过自我介绍。技术问题按 `llm-wiki → web_search/web_extract → 模型通用知识` 优先级回答；使用 `llm-wiki` 时明确先 `skill_view` 读取说明，再用 `read_file` / `search_files` 读取 `~/.hermes/wiki` 的真实内容，不把缺少 terminal 误判为缺少 wiki 权限；不懂/不确定时直接说明需要琛哥确认；工作安排、责任归属、承诺类事项使用强势明确口吻，但不得替琛哥承诺、担责或定责。新增 Feishu group history backfill：`history_backfill_limit`、`history_backfill_seconds`、`history_backfill_max_chars`。Gateway session 新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`，Feishu 群聊映射到 `feishu_group`，私聊仍为 `feishu`。授权层新增 `FEISHU_GROUP_ALLOWED_CHATS`，可授权群 chat_id 或 `*`，但不放开 DM。`feishu_doc_read` 无 comment client 时可从 env / `~/.hermes/.env` 构建 tenant client；`read_file` 在二进制检测前识别 `.xlsx`，用标准库 zip/xml 抽取 sheet 文本，旧 `.xls` 明确提示需要转换器。新增可配置开关 `bare_mention_intent`（默认关；关时保持上游"纯 @ 直接丢弃"、可一键回退）：开启后群聊里纯 `@bot` 不再被丢弃，而是合成一条意图 turn——若该 @ 是引用回复，则把被引用消息作为本轮主体（新 helper `_build_bare_mention_intent_text` + 复用已获取的 `reply_to_text`）；否则让模型基于 `_fetch_channel_context` 的近期群历史推测发问人意图、给出最佳回答或问一句简短澄清。发问者始终锚定为 `@` 发起人（复用 PATCH-13 的 current-author 规则，引用消息 / 频道历史仅作上下文），不混淆回复主体。守卫改造仅在「开关开 + 群聊 + `@bot` 触发」时生效，DM、开关关、非 bot 触发仍走上游丢弃；开关经 `gateway/config.py` 直通键与 `FeishuAdapterSettings.bare_mention_intent`（env `FEISHU_BARE_MENTION_INTENT`）落地。

**验证**：Step 8b grep `assistant_user_ids`、`_sender_is_configured_assistant_user`、`_fetch_channel_context`、`HERMES_SESSION_PLATFORM_CONFIG_KEY`、`feishu_group`、`FEISHU_GROUP_ALLOWED_CHATS`、`history_backfill_max_chars`、`_client_from_env`、`_read_spreadsheet`、`test_process_inbound_message_owner_bot_mention_skips_self_intro`、`test_doc_read_builds_env_client_outside_comment_context`、`test_read_file_extracts_xlsx_as_text`。定向测试覆盖设置加载、群历史格式化、未 @ 静默、@bot 触发、第三方 @本人账号触发代答、本人账号 @bot 触发免自我介绍、`feishu_group` session key、群授权不放开 DM、无 comment context 时从 env 构建 Feishu client 读 doc，以及最小 `.xlsx` 文件被 `read_file` 抽取出 sheet 名、表头和数据行。另 grep `bare_mention_intent`、`_build_bare_mention_intent_text` 与 `test_bare_mention_without_text_uses_channel_context_to_infer_intent` / `test_bare_mention_reply_uses_quoted_message_as_subject_locked_to_sender` / `test_bare_mention_dropped_when_toggle_disabled`（分别覆盖：开关默认关时纯 @ 仍丢弃、开关开时纯 @ 走频道历史意图推理、引用 @ 以被引用消息为主体且发问者仍锚定 @ 发起人）。

**上游吸收判断**：如果上游后续原生提供等价的 Feishu mention trigger、assistant-user trigger、配置本人账号直接 @bot 时免自我介绍、history backfill、per-group platform config key、group chat allowlist、Feishu doc tenant-client fallback 与 `.xlsx` 附件文本读取，可将本补丁归档；保留验证 grep 作为 sentinel，或改成上游行为测试。

---

### [PATCH-11] 平台级 skill allowlist、只读工具集与群聊审批硬拦

| 字段     | 内容                                                                                                                                                                                                                                                                                                            |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `agent/prompt_builder.py`, `tools/skills_tool.py`, `tests/tools/test_skills_tool.py`, `toolsets.py`, `tools/approval.py`, `tests/tools/test_approval.py`, `tests/hermes_cli/test_skills_config.py`, `tests/hermes_cli/test_tools_config.py`, `website/docs/user-guide/configuration.md` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                   |

**问题**：`skills.disabled` 只能做全局/平台禁用，无法表达“群聊只允许少数安全 skill，但私聊保持不受限”。同时上游 `skills` toolset 同时包含 `skills_list`、`skill_view`、`skill_manage`；群聊只想读取 `llm-wiki` 时，如果直接启用 `skills`，会把写/改 skill 的 `skill_manage` 也暴露给群成员。2026-07-10 复盘 Feishu 群聊视频测试时发现第二个边界洞：群聊 sandbox 虽会先拦非法 `terminal`（如 `ffprobe`、`python3 -c`、复合命令），但若某条群聊 terminal 调用进入 dangerous-command approval 流，`tools/approval.py` 只按“gateway session”发送审批卡，没有再区分 owner DM 与 group/channel。实际日志中 `AI 解放生产力` 群 session 出现 `Feishu button resolved 1 approval(s)`，且第一次 `once` 后 terminal 确实继续执行；这等于让群聊参与者用审批按钮升级群聊终端权限。

**修复**：新增 `skills.platform_allowed.<platform>` allowlist。未配置表示保持原行为；配置为空列表表示该平台禁用所有 skill；配置具体名称表示只允许这些 skill。`build_skills_system_prompt`、`skills_list`、`skill_view`、skill config var discovery 都遵守该 allowlist，并优先使用 `HERMES_SESSION_PLATFORM_CONFIG_KEY`，因此 Feishu 群聊能独立使用 `feishu_group` allowlist。新增内部工具集 `skills_readonly`，只包含 `skills_list` 与 `skill_view`，不包含 `skill_manage`。本地分类 skill 的 `category:skill` 规范名也按短名兜底匹配 allowlist，避免配置已允许 `feishu-docs` 时 `skill_view("productivity:feishu-docs")` 被误拒。审批层新增 `_is_restricted_feishu_approval_session()`：当当前平台是 Feishu 且 session key 的 chat_type 为 `group` / `forum` / `channel` / `thread` 时，dangerous-command approval 直接返回 `BLOCKED`，不调用 gateway notify、不入 pending queue、不发送 Feishu interactive card；owner DM 审批保持原行为。该硬拦同时接入旧 `check_dangerous_command` 与主路径 `check_all_command_guards`。

**验证**：Step 8b grep `get_allowed_skill_names` 在 `agent/skill_utils.py`、`agent/prompt_builder.py`、`tools/skills_tool.py` 中存在，并 grep `toolsets.py` 中存在 `skills_readonly`、`file_readonly`、`skills_list`、`skill_view`、`read_file`、`search_files`，另 grep `tests/tools/test_skills_tool.py` 中存在 `test_qualified_local_skill_allowed_by_bare_name`，grep `tools/approval.py` 中存在 `_is_restricted_feishu_approval_session`，grep `tests/tools/test_approval.py` 中存在 `test_feishu_group_dangerous_command_does_not_send_approval_card`。定向测试覆盖空 allowlist 禁用全部 skill、命名 allowlist 只允许指定 skill、qualified 本地分类 skill 按短名通过、`feishu_group` 独立工具集配置、内部 `file_readonly` 工具集不会被平台配置过滤，以及 Feishu group dangerous command 直接 `restricted_chat`、不发送审批卡、不入 approval queue。

**上游吸收判断**：如果上游后续提供平台级 skill allowlist 与只读 skill 工具集，且能通过 `feishu_group` 或等价群聊上下文独立约束 skills，并且 approval/terminal 权限按 chat_type 区分、群聊不能发 dangerous-command approval，可归档本补丁。

---

### [PATCH-12] Feishu 回复不再创建话题（始终普通引用回复）

| 字段     | 内容                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/display_config.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_display_config.py` |
| **状态** | 🟡 未上游合并                                                                                                                              |

**问题**：bot 在飞书里的回复会变成一个**话题（Thread）**，嵌在被回复消息下方、像评论而非主消息流里的正常回复。初始根因有两处叠加：入站处理 `adapter.py` 把 `thread_id = message.thread_id or message.root_id`——飞书普通群里只要消息处于「引用回复链」中 `root_id` 就有值，于是 `source.thread_id` 被填上并随 metadata 透传；出站 `_send_raw_message` 据此 `reply_in_thread = bool(metadata["thread_id"])`，飞书 `im.v1.message.reply` 接口在该标志为真时把回复挂成话题。2026-07-10 复盘 `AI 解放生产力` 群最近一次 ref 提问时发现老补丁仍有漏口：即使 `reply_in_thread=False` 已生效，gateway 的 streaming / status / interim 路径仍会把 `source.thread_id` 放进 `metadata.thread_id`；当没有有效 `reply_to` 或 reply fallback 时，Feishu adapter 后续 `createMessage` 分支会把该 `thread_id` 当成 `receive_id_type="thread_id"` 投递，仍然落入话题/评论 lane。另一个可见问题是 Feishu 的默认 display tier 会发送 tool progress / interim assistant bubbles；这些中间态可能包含 `_thinking`/草稿式内容，即便最终答案和 provider reasoning 已按 `display.show_reasoning=false` 隐藏。

**修复**：在所有飞书发送的唯一出口 `_send_raw_message` 钉死 `reply_in_thread = False`，并把「引用目标」回退从依赖 `thread_id` 解耦（`effective_reply_to` 改为 `reply_to or metadata["reply_to_message_id"]`，不再要求 `thread_id` 存在）。同时让 Feishu create-message 分支**忽略 generic `metadata.thread_id`**，永远按 `chat_id` / `open_id` / `feishu_user_id:` 投递；有 `metadata.reply_to_message_id` 时仍走普通引用回复，没有有效引用锚点时退回主聊天普通消息，绝不把 metadata thread 当 receive_id。入站 `thread_id`（含 `root_id` 回退）保留不动——它仍用于 `reply_to_message_id` 提取与 channel/session 路由，只是不再决定「是否开话题」。显示层把 Feishu 内置默认收敛为 final-only：`tool_progress=off`、`streaming=false`、`interim_assistant_messages=false`、`long_running_notifications=false`、`busy_ack_detail=false`，避免群聊里出现工具进度/思考草稿中间消息；当前本机 `config.yaml` 也显式加了 `display.platforms.feishu` 覆盖，防止全局 `interim_assistant_messages:true` 抢先级。

**验证**：Step 8b grep `plugins/platforms/feishu/adapter.py` 中存在 `reply_in_thread = False` 与 `Ignore generic thread metadata on Feishu`，grep `tests/gateway/test_feishu.py` 中存在 `test_send_ignores_thread_metadata_when_no_reply_anchor`，grep `gateway/display_config.py` 中存在 Feishu final-only defaults，grep `tests/gateway/test_display_config.py` 中存在 `test_feishu_defaults_to_final_only`。定向测试覆盖：带 `thread_id` metadata 的回复 `reply_in_thread` 为 False、用 `metadata["reply_to_message_id"]` 作引用目标且不开话题、无 reply anchor 但带 `metadata.thread_id` 时仍 `receive_id_type="chat_id"`、文档回复同样不开话题，以及 Feishu 默认不发 progress/interim/streaming（`test_send_never_replies_in_thread_even_with_thread_metadata`、`test_send_uses_metadata_reply_target_without_threading`、`test_send_ignores_thread_metadata_when_no_reply_anchor`、`test_send_document_reply_never_uses_thread_flag`、`test_feishu_defaults_to_final_only`）。定向测试：`tests/gateway/test_feishu.py` 225 passed，`tests/gateway/test_display_config.py` 53 passed。

**上游吸收判断**：如果上游后续不再把 `root_id` 并入 `thread_id`、或为 Feishu 回复提供「普通引用 vs 话题」开关并默认普通引用，且 generic thread metadata 不会被 Feishu adapter 当 topic receive_id，同时 Feishu 群聊默认不展示内部 progress/interim/thinking bubbles，可归档本补丁。

---

### [PATCH-13] 群聊当前发言人身份锚定

| 字段     | 内容                                                                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_session.py`, `tests/gateway/test_feishu.py`, `tests/gateway/test_feishu_bot_admission.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                              |

**问题**：群聊里模型会把 `memories/USER.md` / profile 中的 owner 信息误当成当前说话人，尤其是全局记忆写着“周琛 / 琛哥”时；同时 Feishu 群消息触发逻辑先判断 `assistant_users` 再判断 `@bot`，一条消息同时提到 bot 和配置本人账号时会走错触发分支。另一个实际身份风险是 Feishu 文本/媒体 debounce 批处理只按会话和 reply/thread 上下文聚合，未显式要求发送者一致；在共享 session 或同线程场景里，短时间内不同人的消息可能被拼到第一条事件上，沿用第一条的 sender source。

**修复**：非 DM session prompt 把当前说话人从 `User` 改为 `Current message author`，并加入 `Current-author rule`：当前回答必须以本条消息作者为准，且这个当前作者就是本轮回复对象和回复主角；持久 profile/USER.md 只能描述 bot owner/default user，不能自动当成 speaker；recent channel history 只能作为上下文，不能覆盖当前作者。Gateway 在非 DM 入站 user turn 正文层也幂等补上 `[当前作者] 当前问题`，即使 `group_sessions_per_user=true` 导致群成员各自独立 session，也能让当前作者紧贴 `[New message]` 下方的真实问题，避免 recent channel history 里最后一位发言人压过本轮发问者。Feishu 触发顺序改为直接 `@bot` 优先于 `assistant_users`。文本和媒体批处理新增 sender identity 匹配，要求 `user_id`、`user_id_alt`、`user_name` 一致才允许合并。

**验证**：Step 8b grep `gateway/session.py` 中存在 `Current message author`、`Current-author rule`、`main subject of your response`，grep `gateway/run.py` 中存在 `_with_current_author_prefix`，并 grep 回归测试 `test_bot_mention_takes_priority_over_assistant_user_mention`、`test_text_batch_does_not_merge_different_senders`、`test_group_turn_body_keeps_current_author_next_to_question` 与 session prompt 断言。定向测试覆盖群聊 prompt 不把 owner profile 当 speaker、直接 @bot 优先于 assistant-user trigger、不同发送者的 Feishu 文本批处理不会合并，以及 channel history 最后一条来自 Ethan 但当前问题来自 Songfen 时，最终 user turn 仍呈现 `[New message]\n[Songfen] ...`。

**上游吸收判断**：如果上游后续在多用户 session prompt 中原生区分 current author 与 persistent owner/profile，并保证 Feishu trigger priority 与 batching 都按 sender identity 隔离，可归档本补丁。

---

### [PATCH-14] 人物 / 群聊画像注入（people.yaml + groups.yaml → system prompt）

| 字段     | 内容                                                                                                                                                                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `gateway/run.py`, `gateway/stream_consumer.py`, `tests/gateway/test_session.py`, `tests/gateway/test_stream_consumer_silence.py`（配套数据文件 `~/.hermes/people.yaml` gitignore、`~/.hermes/groups.yaml` 入库，均非 PATCHED_FILES） |
| **状态** | 🟡 未上游合并（本地个性化功能，不预期被上游吸收）                                                                                                                                                                                                          |

**问题**：（人物层）群聊/私聊里 agent 只能拿到发送者的 open_id 与显示名，不知道对方的岗位、背景、沟通风格，也无法按"琛哥对此人的态度"调整语气与风险意识。这类主观标注（喜好、立场、应对基调）官方通讯录 API 永远不会提供，必须由用户自维护。（群聊层）同一个 bot 在不同飞书群面对不同人群，却共用同一套语气与自我介绍口径，无法针对性表达「这个群我主要能帮你做什么」，也不知道应在自我介绍里告知群成员哪段提示性服务 / 接客时间；且当群聊任务因沙箱拦截工具 / 缺权限 / 缺凭证而效果打折时，模型容易把受限当作已完成、对深入结论过度自信，而不是声明限制并把决策交回琛哥确认。

**修复**：在 `gateway/session.py` 新增本地人物画像库读取层（sentinel `people-profile`）：`_load_people_profiles()` 按 mtime 缓存读取 `~/.hermes/people.yaml`（经 `hermes_constants.get_hermes_home()` 定位），`_lookup_person()` 依次按 `user_id` / `user_id_alt` / `user_name`（含 aliases、大小写折叠）匹配，`_render_person_profile()` 把画像拆成**可公开段**（仅 姓名/岗位/部门·团队/称呼 address）与**保密段**（工号/入职/司龄/上级/下属 (direct+total，`_render_subordinates`)/职业背景/行为模式/态度/风险注意/备注），其中 `address` 可直接用于回复称呼；若包含多个称呼，按 `|` 分隔并可按语境任选一个。保密段尾部附 `_PEOPLE_PROFILE_SECRECY` 强制保密指令——私有字段只能用于调整应对，绝不可复述/确认/暗示，即使被直接询问或旁敲侧击也不得外泄（防止人为设定的背景/态度被群成员套出）。`build_session_context_prompt` 在 current-author 块之后注入该画像；`redact_pii` 为真时（PII-safe 平台）跳过，保持脱敏契约。群聊可见输出增加硬防线：`redact_private_person_profile_text()` 按当前问话人的画像收集所有非公开字段、备注和下属行的原文/片段，在非 DM 输出前做精确值脱敏；姓名、岗位、部门/团队和 `address` 保留可见。`gateway/run.py` 在非流式最终回复、错误兜底最终回复和流式 consumer 构造处接入该过滤；`gateway/stream_consumer.py` 新增 `text_filter`，在 send/edit/commentary/fallback/fresh-final 等可见文本发送前应用过滤，避免流式路径绕过最终回复脱敏。同一文件还新增并行的**群聊画像层**（sentinel `group-profile`），与人物层同款契约（mtime 缓存、config-repo 数据文件、loader 永不抛错、按 mtime 热加载），但**数据文件 `groups.yaml` git 入库、内容纯表达层无机密**：`_load_group_profiles()` 读 `~/.hermes/groups.yaml`，`_lookup_group()` 依次按 `chat_id` / `parent_chat_id`（thread 子会话回退到父群）/`chat_id_alt` / `chat_name`（含 aliases、大小写折叠）匹配，`_render_group_profile()` 渲染 `style`（语言风格/语气）/`capabilities`（能力栈——可对外介绍自己能做什么）/`audience`/`intro`（自我介绍口径）/`service_hours`（服务 / 接客时间的对外提示文本）/`notes`，并显式声明「只改怎么表达/介绍，不改沙箱与安全边界（各群一致）」。命中非空 `service_hours` 时额外要求模型在自我介绍或被问及在线 / 接客时间时自然带出该文本，普通回答不机械重复；该字段**不是调度、门禁或拒答规则**，时段外仍可照常回答，不得仅因时间拒答。`build_session_context_prompt` 仅对 `platform != LOCAL && chat_type in (group, channel)` 注入；命中画像才注入画像块，但**无论是否命中**都追加常量 `_GROUP_TOOL_LIMITATION_RULE`：工具不可用 / 权限被沙箱拦截 / 缺凭证 / 访问失败导致任务没完成或效果打折时，产出必须明确声明该限制与结论可信度边界、不得把受限当已验证；深入结论 / 判断 / 决策 / 对外承诺一律保守，建议等琛哥确认、不替琛哥拍板或担责。DM 既不注入画像也不注入声明规则。loader 全程吞异常——文件缺失或 YAML 损坏只降级为空索引，绝不让 prompt 路径抛错。数据文件刻意放在 config repo（`~/.hermes`），上游升级不覆盖，且改后按 mtime 在下一条消息自动热加载，无需重启。配套拉取脚本 `scripts/pull_feishu_people.py`（pull→draft / merge[--apply]，飞书通讯录客观字段刷新、主观字段保留）维护人物数据文件，非 hermes-agent 工程内补丁。

**验证**：Step 8b grep `gateway/session.py` 中存在 `people-profile`、`def _load_people_profiles`、`def _lookup_person`、`称呼/address`、`redact_private_person_profile_text`、`group-profile`、`def _load_group_profiles`、`def _lookup_group`、`service_hours`、`_GROUP_TOOL_LIMITATION_RULE`，grep `gateway/run.py` 中存在 `redact_private_person_profile_text`，grep `gateway/stream_consumer.py` 中存在 `text_filter`，并 grep `tests/gateway/test_session.py` 中的 `class TestPeopleProfileInjection`、`class TestGroupProfileInjection`、`test_service_hours_are_intro_hint_not_reply_gate`、`test_address_is_public_and_usable_for_reply`、`test_private_profile_redactor_keeps_public_fields` 以及 `tests/gateway/test_stream_consumer_silence.py` 中的 `test_text_filter_applies_before_stream_delivery`。定向测试覆盖：人物层 按 id / name·alias 命中、未知不注入、缺文件 / 坏 YAML 安全；`address` 位于公开段且可用于称呼；群聊输出保留公开字段并隐藏私有画像原文/片段；群聊层 按 chat_id / alias 命中、提示性服务时间在介绍时带出但不构成回复门禁、未命中仍保留声明规则、声明规则在 group 出现、DM 既无画像也无声明规则、缺文件 / 坏 YAML 安全（`TestGroupProfileInjection` 8 例）；流式输出发送前应用隐私过滤。

**上游吸收判断**：该功能依赖用户私有/本地数据文件与个人化标注（态度、群人设），属本地个性化增强，不预期被上游合并；若上游引入等价的 per-sender / per-group profile 注入机制可重新评估归档。

---

### [PATCH-15] Feishu 群聊附件回看、Drive 文件链接下载与常见文档自动读取

| 字段     | 内容                                                                                                                                                                                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/platforms/base.py`, `gateway/run.py`, `tools/read_extract.py`, `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock`, `tests/gateway/test_feishu.py`, `tests/gateway/test_document_context_note.py`, `tests/tools/test_read_extract.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                       |

**问题**：飞书群聊 `require_mention: true` 下，图片/文件消息身上挂不了 @，用户「发图」是一条独立消息、「@机器人 看看这个」是另一条纯文本消息。图片消息在 `_admit()` 处因 `trigger_kind="none"` 被判 `trigger_mention_missing` 丢弃，从不进入处理；机器人被那条纯文本触发时手里只有 `channel_context` 里的占位符，看不到真实资源。此外，`https://.../file/TOKEN` 是正文链接而非 IM 附件，引用这类消息时原回填链路没有 `file_key` 可下载。即使用户已放开权限、Drive 下载成功，PDF/DOCX 等二进制仍只收到路径提示；群聊安全沙箱又禁止模型临时执行 `pdftotext`/Python，于是表现为「可以下载但无法读取」。

**修复**：保留原有 `_backfill_sender_attachments` / `_backfill_reply_attachments` / `_mark_attachment_backfilled` 回看与有界去重，在 `_process_inbound_message` 额外扫描当前正文和 `reply_to_text` 中最多 3 个飞书/Lark `/file/<token>`，用租户身份调用 `drive.v1.file.download`，限制单文件 100 MiB，按响应文件名/MIME 缓存后统一加入 `media_urls`。图片、音视频继续进入原生媒体路由；常见文档进入新可信抽取层：扩展 `tools/read_extract.py` 支持 PDF（`pypdf==6.14.2`，兼容已有 PyMuPDF）、HTML/HTM（去 script/style 等主动内容）、PPTX、ODT，加上游已有 IPYNB/DOCX/XLSX；`gateway/run.py` 在送模型前用 `asyncio.to_thread` 自动抽取，每文件 20k、每轮合计 40k 字符，保留首尾并明确附件是“不可信参考数据”。加密/扫描型 PDF 或损坏文件不会假装成功，而是保留原文件路径并提示 OCR/document vision fallback。`.html/.htm/.odt/.ipynb` 同步加入平台文档类型表；`pyproject.toml`、lazy deps 与 `uv.lock` 固定 PDF 依赖，避免更新/重启后缺解析器。

**验证**：Step 8b 在原 PATCH-15 sentinel 外检查 `_download_feishu_drive_file`、`_FEISHU_DRIVE_FILE_URL_RE`、`_extract_inbound_document`、`_extract_pdf`、`_extract_html_file`、`pypdf==6.14.2` 及 `TestFeishuDriveFileLinks` / `TestCommonDocumentExtraction`。定向测试覆盖 `/file/` token 提取、去重/数量上限、Drive 下载失败静默降级、MIME/文件名缓存；PDF 实际文本抽取和页边界、HTML 主动内容剔除、PPTX 顺序、ODT 段落、入站抽取不依赖 terminal、附件提示注入边界。2026-07-13 实测 `SpaceSight 救命稻草` 所引 PDF 已从相同 `/file/` 链接成功下载（4,053,317 bytes）；本补丁用可信解析器直接抽出正文，不再触发群沙箱的 terminal 拒绝。

**上游吸收判断**：只有上游同时提供「附件与 @mention 分属两条消息」回看、Drive `/file/` 文本链接下载，以及入站 PDF/HTML/Office 文档可信自动抽取时，才可整体归档；若只吸收其中一层，应拆分后保留其余能力。

---

### [PATCH-16] Feishu 出站消息 markdown 完整渲染

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：飞书 post/md 元素能渲染行内标记（加粗 / 斜体 / 列表 / 链接 / 行内代码），但有两类格式无法渲染：①ATX 标题 `## heading` 与引用 `> quote` 以原始符号字面显示；②GFM 表格会导致整条消息在飞书客户端显示为空白，原有实现因此把含表格的回复整体降级为纯文本，连带列表、标题等可渲染格式也一并失效。

**修复**：两处改动，均在 `_build_outbound_payload` 出站路径：

1. **标题 / 引用**：新增 fence-aware 预处理器 `_promote_block_markdown(content)`，将 post/md 渲染不出的块级语法转成等价可渲染形式：`## heading` → `**heading**`，`> quote` → `▎ quote`；代码块内的 `#` / `>` 原样保留。

2. **表格**：有 `_MARKDOWN_TABLE_RE` 检出时，先调 `convert_table_to_bullets()`（`gateway.platforms.helpers`）把 GFM 表格转成 `**行标题**` + `• 字段: 值` bullet 组，再走 post/md 路由。GFM 表格语法消失后不再触发空白消息 bug，同时列表 / 标题等恢复原生渲染。

**验证**：Step 8b grep `adapter.py` 中存在 `def _promote_block_markdown`、`convert_table_to_bullets`；grep `test_feishu.py` 中存在 `test_build_outbound_payload_table_converts_to_bullets_and_posts`；`tests/gateway/test_feishu.py` 全量 216 passed。

**上游吸收判断**：若上游为飞书 post/md 原生补齐标题 / 引用渲染，或将回复改走 interactive card markdown 元素，可归档本补丁。

---

### [PATCH-17] Vertex thinking 保持开启但不把 thought 文本混入可见回复

| 字段     | 内容                                                                                     |
| -------- | ---------------------------------------------------------------------------------------- |
| **文件** | `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🟡 未上游合并                                                                            |

**问题**：官方 `provider: vertex` 通过 Vertex OpenAI-compatible endpoint 调 Gemini 3.x 时，`reasoning_effort: high` 会映射到 `extra_body.google.thinking_config.include_thoughts=true`。实测 Vertex 这条 OpenAI-compatible 路径不会把 thought 拆成 Hermes 可隐藏的 `reasoning_content` 字段，而是把 thought text 直接拼进 `message.content`，飞书端会看到类似 `**Identifying Current Model**` 的思考段，即使 `display.show_reasoning=false`。

**（2026-07-07 修订·真实根因）**：初版把 `include_thoughts` 强制改 false 后返回 `{"extra_body": {"google": {...}}}`——**多包了一层 `extra_body` 键**。基类 `ProviderProfile.build_extra_body` 的约定是"返回值会被 merge 进 extra_body"，经 `_build_kwargs_from_profile` 后线上真正发出的是 `extra_body={"extra_body": {"google": {...}}}`；Vertex 不认这个顶层 `extra_body` 字段，直接忽略 → `include_thoughts` 回落默认 true → thought 仍进正文。初版的"真链路验证"用的是**手写单层** `extra_body={'google': {...}}`（未走 `build_kwargs` 组装），因此漏掉了这层 bug。飞书主会话据此泄漏大量 `**加粗标题** + "I'm diving into…"` 思考段。

**修复**：`build_extra_body` 改为返回**单层** `{"google": {"thinking_config": thinking_config}}`（与 qwen/nous 等 profile 的扁平返回约定一致），使线上 `api_kwargs["extra_body"]` 恰为 `{"google": {"thinking_config": {"include_thoughts": False, "thinking_level": "high"}}}`——Vertex 读到顶层 `google.thinking_config`，抑制生效。保留 `thinking_level=high` 让模型继续内部思考，只是不把 thought text 返回正文。

**验证**：Step 8b grep `plugins/model-providers/vertex/__init__.py` 存在 `include_thoughts=true` 说明、`thinking_config["include_thoughts"] = False` 与**单层** `return {"google": {"thinking_config": thinking_config}}`；grep test 存在 `test_vertex_extra_body_preserves_disabled_reasoning`。单测 `venv/bin/python -m pytest tests/hermes_cli/test_vertex_provider.py -q` 19 passed。真链路 A/B 对比（`VERTEX_ACCESS_TOKEN`，同一 plan 类 prompt）：**A 单层 → 干净答案**；**B 双层（旧）→ `" Too simple, doesn't add value…"` 思考泄漏**。`build_kwargs(provider_profile=vertex)` 输出确认为单层结构。

**注**：`plugins/model-providers/gemini/__init__.py`（AI-Studio `gemini` provider）存在同构的双层写法，但本环境不走该 provider，暂不改动，待验证。

**上游吸收判断**：若上游能把 Vertex OpenAI-compatible 返回的 Gemini thoughts 解析并存入隐藏 reasoning 字段，或官方 Vertex profile 默认隐藏 thoughts 且保留 thinking level，可归档本补丁。

---

### [PATCH-18] Doctor 识别官方 Vertex provider 与 google/* 模型名

| 字段     | 内容                                                      |
| -------- | --------------------------------------------------------- |
| **文件** | `hermes_cli/doctor.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🟡 未上游合并                                             |

**问题**：切到官方 `model.provider: vertex` 后，实际 runtime provider 已能通过 `providers.get_provider_profile("vertex")` 和 `agent.vertex_adapter` 正常拿 OAuth token 调 Vertex OpenAI-compatible endpoint，但 `hermes doctor` 仍只看 auth/catalog provider 列表，不读 model-provider plugin registry，于是误报 `model.provider 'vertex' is not a recognised provider`。同时 `google/gemini-3.1-pro-preview` 这类 Vertex 官方 OpenAI-compatible 模型名被当作 OpenRouter 风格 vendor slug，额外误报应该切 openrouter 或去掉前缀。

**修复**：doctor 在校验 provider 时补充读取 `providers.get_provider_profile()`，将 plugin profile 的 canonical name 加入可接受 provider id 集合，并让 vendor-slug 策略同时考虑原始 provider、auth runtime provider、catalog provider 与 plugin canonical provider。`vertex` 被加入允许 `vendor/model` 形态的 provider 集合；`.env` 健康检查同时识别 `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT_ID` / `VERTEX_LOCATION`，避免只配置官方 Vertex 凭据时被误判为没有 provider auth。

**验证**：Step 8b grep `hermes_cli/doctor.py` 中存在 `_get_provider_profile`、`GOOGLE_APPLICATION_CREDENTIALS` 与 `"vertex"`，并 grep `tests/hermes_cli/test_doctor.py` 中存在 `test_run_doctor_accepts_vertex_provider_and_google_model_slugs`。单测 `venv/bin/pytest tests/hermes_cli/test_doctor.py tests/hermes_cli/test_vertex_provider.py tests/gateway/test_session.py -q` 193 passed；实际 `hermes doctor` 在当前 `provider: vertex` 配置下显示 `Config version up to date (v33)` 且 `All checks passed`。

**上游吸收判断**：若上游 doctor 原生读取 model-provider plugin registry，或官方 registry/catalog 把 `vertex` 与其 `google/*` OpenAI-compatible 模型名纳入健康检查策略，可归档本补丁。

---

### [PATCH-19] 第二个 Vertex 账号做 fallback（绕开单账号限额）

| 字段     | 内容                                                                                                                                                                   |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/vertex_adapter.py`, `hermes_cli/auth.py`, `agent/auxiliary_client.py`, `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                          |

**问题**：主模型 `google/gemini-3.1-pro-preview`（Vertex，project `wh-gemini-1`）频繁 `429 RESOURCE_EXHAUSTED`（单账号/单 project 配额），回退到 `alibaba/qwen3.6-plus`，行为与质量都跟主模型不一致。需求：fallback 换成**第二个 Vertex 账号**跑同一个 gemini-3.1-pro，行为与主模型一致，仅换账号绕开限额。两处架构约束使"同 provider 同模型换账号"无法直接配置：①`vertex` 不在 `hermes_cli.auth.PROVIDER_REGISTRY`（auto-extend 只收 `auth_type=="api_key"`），主模型靠 `resolve_runtime_provider()` 专门解析，而 **fallback 走 `resolve_provider_client()`，只从 `PROVIDER_REGISTRY.get()` 取 pconfig** → 现有 `auth_type=="vertex"` 分支对 fallback 是够不到的死代码；②fallback 去重（`chat_completion_helpers._try_activate_fallback`）对 `provider+model` 相同的条目直接跳过。此外 `get_vertex_credentials` 里 `_resolve_project_override()`（`VERTEX_PROJECT_ID`/config）会把任何账号的 token 重绑到主 project → 第二账号 403。

**修复**：新增独立 provider `vertex-fallback`，复用同一 `VertexProfile`（自动继承 PATCH-17 单层抑制 → 行为一致），只换凭证：

1. `agent/vertex_adapter.py`：新增 `get_vertex_fallback_config()` / `has_vertex_fallback_credentials()`，从 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（经 `_get_secret`）解析第二账号；给 `get_vertex_credentials`/`get_vertex_config` 加 `project_override`（显式项目优先）与 `apply_global_project_override=False`（不套用 `VERTEX_PROJECT_ID`），确保第二账号 token 锁在自己的 project；token 按 path 各自缓存 + 自动刷新（复用 `_creds_cache`）。
2. `hermes_cli/auth.py`：在 `PROVIDER_REGISTRY` 显式登记 `vertex-fallback`（`auth_type="vertex"`，别名 `vertex2`/`vertex-secondary`），使 `resolve_provider_client` 能取到 pconfig 并命中 vertex 分支。
3. `agent/auxiliary_client.py`：`resolve_provider_client` 的 `auth_type=="vertex"` 分支内，`provider=="vertex-fallback"` 时改用 `get_vertex_fallback_config` / `has_vertex_fallback_credentials`。
4. `plugins/model-providers/vertex/__init__.py`：用同一 `VertexProfile` 类再 `register_provider` 一个 `name="vertex-fallback"` 实例，使 `get_provider_profile("vertex-fallback")` 可解析（fallback 激活后 `_build_request_kwargs` 走 profile 路径拿到单层抑制）。

配套（非工程内补丁）：`~/.hermes/.env` 加 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（第二账号 SA 文件 `~/.gemini/gen-lang-client-0217395804-…json`，project `gen-lang-client-0217395804`）；`~/.hermes/config.yaml` 把 `fallback_providers` 设为 `vertex-fallback/gemini-3.1-pro`，`fallback_model` 保留 `alibaba/qwen3.6-plus` 作末位兜底（有效链 = 二者 merge 去重）。

**验证**：Step 8b grep `agent/vertex_adapter.py` 存在 `def get_vertex_fallback_config` + `apply_global_project_override`；`hermes_cli/auth.py` 存在 `"vertex-fallback"`；`agent/auxiliary_client.py` 存在 `has_vertex_fallback_credentials`；`plugins/.../vertex/__init__.py` 存在 `name="vertex-fallback"`；test 存在 `test_vertex_fallback_profile_registered`。单测 19 passed（含 4 条 fallback 回归）。真链路端到端：加载 `.env` 后 `get_vertex_fallback_config()` 返回 base_url 锁定 `projects/gen-lang-client-0217395804`（未被主 project 覆盖），`resolve_provider_client("vertex-fallback", model="google/gemini-3.1-pro-preview")` 返回可用 client 且真实调用返回干净答案（无 thought 段）。第二账号 SA 直连 Vertex `/v1`+`/v1beta1` global 均 200。

**上游吸收判断**：若上游为 Vertex/OAuth-token 类 provider 提供多凭证轮换池（credential pool），或让 fallback 条目原生携带 per-entry `credentials_path`/`project`，可归档本补丁改用原生机制。

---

### [PATCH-20] Vertex Gemini 3.x 附图/附视频自动走 native 多模态

| 字段     | 内容                                                                            |
| -------- | ------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `tests/agent/test_image_routing.py`, `gateway/run.py` |
| **状态** | 🟡 未上游合并                                                                   |

**问题**：（图片，2026-07-09）当前主模型走官方 `provider: vertex` + `google/gemini-3.1-pro-preview`，但 `agent.image_input_mode: auto` 依赖 `_lookup_supports_vision()` 判断主模型是否能原生接收图片。Vertex OpenAI-compatible endpoint 没有 `/models` discovery，`models.dev` 也可能尚未收录新的 Gemini 3.x preview slug，于是 capability 解析为 `None`，auto 路由退回 `text`。群聊/私聊/CLI 附图都会先调用 `vision_analyze` 做文本预分析；而当前安装只有 Vertex 凭据，没有可用 OpenRouter/Nous auxiliary vision backend，日志反复报 `No LLM provider configured for task=vision provider=auto`。（视频，2026-07-10）图片修好后视频依然"读不了"：上游对视频只有 path-note 流——`gateway/run.py` 把 `[The user sent a video attachment ... saved at <path>]` 注入文本，期望 agent 用自己的工具（ffprobe/ffmpeg）处理。DM 里有 terminal 权限还能凑合；群聊沙箱把 terminal/python 全拦掉（日志：`sandbox: blocked terminal args={'command': 'ffprobe ...'}`），模型手里只有路径、看不到内容，只能回复"无法读取视频"。PATCH-15 的回填/下载层其实工作正常（`Cached message video resource ... .mp4`），断点在送模型这一段。

**修复**：（图片）在 `agent/image_routing.py` 新增窄口径 fallback `_known_provider_model_supports_vision(provider, model)`：当 provider 是 `vertex` / `vertex-fallback` / Vertex 常见 alias，且模型名匹配 Gemini 3.x（`gemini-3` / `gemini-pro-3` / `gemini-flash-3`）时返回 `True`；其他 provider/model 仍返回 `None`，继续走现有 config override、models.dev、Ollama probe 逻辑。（视频）让视频与图片同路：Vertex OpenAI-compat endpoint 接受任意 GenerateContent MIME 的 `data:` URI 内联在 `image_url` part 中，Gemini 3.x 原生看视频。`image_routing.py` 新增 `decide_video_input_mode`（config 键 `agent.video_input_mode`，默认 auto；auto 下仅 `_known_provider_model_supports_video` 窄白名单 = Vertex + Gemini 3.x 走 native——图片 vision 能力**不可**作为视频能力的代理，且视频没有 shrink-on-reject 补救，故不做乐观默认）、视频 magic-bytes 嗅探（ftyp/EBML/RIFF/FLV/ASF/MPEG-PS，ISO-BMFF 图片 brand 留给图片嗅探器）、`_video_file_to_data_url`（file_safety 守卫 + `NATIVE_VIDEO_MAX_BYTES=14MB` 内联上限 + `_GEMINI_SUPPORTED_VIDEO_MIMES` 白名单，超限/不支持返回 None 走回退）；`build_native_content_parts` 增加 `video_paths` 参数，视频输出 `data:video/*;base64` 的 `image_url` part（shrink recovery 只改写 `data:image/*`，视频 part 天然跳过）+ `[Video attached at: <path>]` hint。`gateway/run.py`：`_decide_image_input_mode` 增加 `kind="video"` 分派；`_prepare_inbound_message_text` 中 `video_paths` 桶按 native/text 分流——native 且 `os.path.getsize ≤ 14MB` 的缓冲进新 session buffer `_pending_native_video_paths_by_session`（消费点与图片 buffer 一起传入 `build_native_content_parts`），超大/非 native 的保留原 path-note 流。群聊沙箱无需放开任何工具。

**验证**：Step 8b grep `agent/image_routing.py` 中存在 `def _known_provider_model_supports_vision`、`"vertex-fallback"`、`def decide_video_input_mode`，grep `gateway/run.py` 中存在 `_pending_native_video_paths_by_session`，grep `tests/agent/test_image_routing.py` 中存在 `gemini-3.1-pro-preview`、`test_auto_native_for_vertex_gemini_3_preview_without_catalog_entry`、`test_video_attached_as_data_url_part`。单测 `venv/bin/python -m pytest tests/agent/test_image_routing.py -q` 118 passed（视频新增 17）；`tests/agent/test_image_routing.py + tests/gateway/test_feishu.py + tests/gateway/test_config.py + tests/hermes_cli/test_doctor.py` 共 496 passed。真实配置验证：`decide_video_input_mode("vertex"/"vertex-fallback", "google/gemini-3.1-pro-preview", cfg) == "native"`；用群里实际缓存的 11MB `iShot_*.mp4` 构造 parts 成功（`data:video/mp4;base64,` 14.7MB data URL + hint）。真机：群聊引用视频/发视频后 @机器人，`logs/agent.log` 应出现 `Video routing: native ...` 且模型能描述视频内容。

**上游吸收判断**：若上游模型能力 catalog 原生覆盖 Vertex Gemini 3.x preview（含视频输入能力），或上游为用户附件提供通用的 native video 路由（等价 `video_input_mode`），可归档本补丁。

---

### [PATCH-21] lazy backend 激活锚点 — 避免未启用 Matrix 被重复刷新

| 字段     | 内容                                                  |
| -------- | ----------------------------------------------------- |
| **文件** | `tools/lazy_deps.py`, `tests/tools/test_lazy_deps.py` |
| **状态** | 🟡 未上游合并                                         |

**问题**：`active_features()` 原先只要某个 lazy feature 的**任一**声明依赖已安装，就把它视为“用户曾启用”并在 `hermes update` 中刷新。`platform.matrix` 为安全钉住核心共享依赖 `aiohttp==3.14.1`，而 aiohttp 在所有正常 Hermes venv 中都存在，因此从未配置 Matrix 的机器也会被误判 active。刷新随即拉取 `mautrix[encryption] → python-olm 3.2.16`；该包没有现代 macOS arm64 wheel，内嵌 libolm 在 macOS 26.5.2 / Apple Clang 21 编译时报 `cannot assign to variable 'other_pos' with const-qualified type 'T *const'`，导致每次真正更新都重复显示 `platform.matrix failed to refresh`。

**修复**：新增 `LAZY_FEATURE_ACTIVE_ANCHORS`，只为存在共享依赖误判的 Matrix 指定身份锚点 `mautrix`。其他 feature 仍保持上游“任一依赖存在即 active”的恢复语义；只有实际安装过 Matrix SDK 的环境才会进入 Matrix refresh。这里不伪装 `python-olm` 已满足、不移除 Matrix encryption，也不对 macOS 一刀切禁用，因此真实 Matrix 用户仍能看到依赖异常并选择 Linux/container 或维护自己的 native toolchain。

**验证**：新增两条回归：仅 `aiohttp` 存在时 `platform.matrix` 不 active，`mautrix` 存在时仍 active；`tests/tools/test_lazy_deps.py` 66 passed。真实 venv 调用 `active_features()` / `refresh_active_features()` 均不再包含 `platform.matrix`，其余 15 个既有 active backend 全部保持 `current`。`hermes-update.sh` Step 8b grep anchor 与回归测试名，并将 PATCH-21 纳入 patch refresh gate。

**上游吸收判断**：若上游用持久化 activation ledger 记录真正启用过的 lazy feature，或为 Matrix/其他含核心共享依赖的 feature 引入等价 identity anchor，即可归档本补丁。

---

## v0.18.0 archive — PATCH-2 上游合并

### [PATCH-2] hermes_cli/doctor.py — issue count 过报

| 字段         | 内容                                               |
| ------------ | -------------------------------------------------- |
| **文件**     | `hermes_cli/doctor.py`                             |
| **状态**     | ✅ 已上游合并（v0.18.0，commit `6b21a935a`）       |
| **适用版本** | v0.9.0–v0.17.0 需要本地 patch；v0.18.0+ 已上游修复 |

**问题（历史）**：`hermes doctor` 把所有注册但缺 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中用 `_get_platform_tools` 过滤出用户实际启用的 toolset，只对它们报 issue。

**上游追踪**：上游 commit `6b21a935a`（`fix(doctor): ignore disabled toolsets in missing-API-key summary`）合入等价逻辑，本地 `hermes_cli/doctor.py` 已从 `PATCHED_FILES` 移除。`hermes-update.sh` Step 8b 仍保留 grep `_get_platform_tools` 的存在性检查，用于在上游回滚时及时告警。

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
