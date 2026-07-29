# 本地补丁记录

> 本文件集中记录所有本地补丁。`hermes-agent/` 工程内语义补丁统一汇总到 `local-patches.diff` replay bundle；`~/.hermes` 配置仓库用户插件补丁单独标注，由外层 Git 与 `hermes-update.sh` Step 8e verifier 管理。
>
> **AI 维护规范**（详细工作流见 `~/.hermes/hermes-update.md` § Step 4）：
>
> - **每次升级后**重写 `## 当前版本：vX.Y.Z (upstream `main` `<SHA>`，YYYY-MM-DD)` header 与下方"最近一次升级"摘要；摘要遵循 5 段结构（上游主线 / patch apply / 依赖 / 已知摩擦 / 配置漂移）。
> - **新补丁**：使用稳定的语义 ID（`PATCH-<DOMAIN>-<INVARIANT>`），在 `## 当前版本` 节下新增一块 2-row 表（`文件 / 状态`）和 `问题 / 修复 / 验证 / 上游吸收判断` 四段。编号不表达顺序，禁止用 A/B 子编号承载不同吸收单元。
> - **边界判定**：一个补丁只能有一个可独立说明的责任边界、一个对应生命周期 gate（Step 3/4/7/8b/8e）和一个上游吸收条件。能被不同上游 PR 分别吸收的能力必须拆开；只有必须一起回滚、一起验收、一起吸收的改动才能合并。
> - **上游合并某补丁**：把该补丁块整体移动到对应 archive 节，记录吸收 commit 和保留的回归 sentinel；同步更新 `PATCHED_FILES`、验证 gate 和 replay bundle。
> - **每个语义 ID 的定义块在整份 PATCHES.md 里仅出现一次**——要么活跃、要么归档；依赖、验证和历史摘要可以引用 ID，但不得复制定义块。
> - `completions/_hermes` 类**工程外补丁**：由 `hermes-update.sh` Step 7 inline Python 在补全脚本生成后检测并修复；上游修好后脚本自动跳过、检测块保留为回归 sentinel（PATCH-ZSH-COMPLETION-SYNTAX 即此类）。

---

## 补丁管理机制

### 总体架构

所有针对 `hermes-agent/` 源码的补丁以**单一 unified diff replay bundle** 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理。语义补丁是独立的行为与吸收单元；replay bundle 只是原子回放载体。多个补丁共享 `adapter.py`、`gateway/run.py` 等文件，强拆物理 diff 会引入脆弱的 hunk 顺序依赖，因此当前保持一个回放包，但 Step 8b 对每个语义补丁分别设 gate。

两类补丁走不同管道：

| 类型                 | 代表                                   | 管理方式                                                                                                                                  |
| -------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁**       | 当前清单中标记为“未上游合并”的源码补丁 | 统一 replay bundle (`local-patches.diff`) + `PATCHED_FILES` + 每补丁独立行为 gate                                                         |
| **配置仓库用户插件** | `PATCH-FEISHU-GROUP-SANDBOX`           | 外层 Git 跟踪 `config.yaml` / `plugins/` / `my-skills/`；Step 8e 强制校验配置、真实 toolset、行为测试和运行时注册，失败则整次升级非零退出 |
| **运行时补丁**       | `PATCH-NPM-DEPENDENCY-HYGIENE`         | Step 3 scoped install-script policy + Step 4 `npm audit fix`，每次 update 重建运行时状态                                                  |
| **已上游合并**       | 文末 Archive                           | 保留吸收来源和回归 sentinel；不计入活跃补丁清单                                                                                           |

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
  │   ├─ PATCH-SKILL-CREATE-ROOT: Python import + 调用 _resolve_skill_dir()，检查返回路径
  │   ├─ PATCH-DOCTOR-ENABLED-TOOLSETS: grep _get_platform_tools in doctor.py（✅ 已上游合并 v0.18.0）
  │   ├─ PATCH-ZSH-COMPLETION-SYNTAX: Step 7 中对 `){-h,--help}` / `){-V,--version}` / `){-p,--profile}` 做回归检测（✅ 已上游合并 v0.13.0）
  │   ├─ PATCH-DASHBOARD-BUILD-CACHE: grep _web_ui_build_needed in main.py（✅ 已上游合并，仅验证）
  │   ├─ PATCH-DELEGATE-ACP-ROUTING: grep override_acp_command + copilot-acp（✅ 已上游合并，仅验证）
  │   ├─ PATCH-GEMINI-THOUGHT-SIGNATURE: grep ToolCall.extra_content + 对应回归测试（✅ 已上游合并，仅验证）
  │   ├─ PATCH-FEISHU-SOCKS-DEPENDENCY: Feishu extra 与 lazy deps 均声明 python-socks
  │   ├─ PATCH-OPENCLAW-TOKEN-MIGRATION: 迁移器不再生成废弃 gateway token
  │   ├─ PATCH-FEISHU-GROUP-ADMISSION: 群触发/上下文/当前发言人/显式 wiki 路径
  │   ├─ PATCH-FEISHU-GROUP-SCOPE: feishu_group capability namespace 与 DM 隔离
  │   ├─ PATCH-PLATFORM-CAPABILITY-SCOPE: 平台 skill allowlist + 只读 skill/file toolset
  │   ├─ PATCH-FEISHU-GROUP-APPROVAL: 群聊危险命令审批硬拦
  │   ├─ PATCH-FEISHU-NORMAL-REPLY: 普通引用回复，不进入 thread/topic lane
  │   ├─ PATCH-FEISHU-FINAL-ONLY: Feishu 默认只显示最终回复
  │   ├─ PATCH-LOCAL-PROFILES: 人物/群画像、来源保密与可见输出过滤
  │   ├─ PATCH-FEISHU-RESOURCE-ACCESS: 附件回看、Drive 链接与 tenant doc client
  │   ├─ PATCH-DOCUMENT-EXTRACTION: XLSX/PDF/HTML/Office/OpenDocument 可信抽取
  │   ├─ PATCH-FEISHU-MARKDOWN: 标题/引用提升与 strong flanking 归一化
  │   ├─ PATCH-FEISHU-SSRF-TEST-SYSPROXY: SSRF rebind 测试对宿主系统代理 hermetic
  │   ├─ PATCH-VERTEX-HIDDEN-THOUGHTS: Vertex thought 文本不进入可见内容
  │   ├─ PATCH-VERTEX-DOCTOR: doctor 识别官方 Vertex profile
  │   ├─ PATCH-VERTEX-FALLBACK: 第二 Vertex 账号作为独立 fallback provider
  │   ├─ PATCH-VERTEX-IMAGE-ROUTING: Gemini 3.x 图片 native routing
  │   ├─ PATCH-VERTEX-VIDEO-ROUTING: Gemini 视频 native routing
  │   ├─ PATCH-LAZY-ACTIVATION: 上游首项依赖身份锚点回归 sentinel（✅ 已归档）
  │   ├─ PATCH-HISTORY-RETENTION: 平台级回放时间窗/条数上界
  │   ├─ PATCH-APPROVAL-DARWIN-TMP: Darwin 临时路径别名归一化
  │   └─ PATCH-FTS5-CJK-DARWIN: Darwin CJK FTS 扩展构建/加载
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

Step 8e: User-plugin verification
  ├─ verifier 文件必须存在且可执行
  ├─ PATCH-FEISHU-GROUP-SANDBOX: YAML 契约 + owner/group 真实 toolset + 21 个行为测试 + 当前 gateway PID runtime trace
  └─ 任一 verifier 非零 → FINAL_RC=1，整次升级不得报告成功
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
| **行为化验证依赖特征字符串**    | PATCH-DELEGATE-ACP-ROUTING 与已归档 PATCH 的 sentinel 验证是 grep 固定字符串。如果上游重构了函数但保留了行为，grep 会误报 "inactive"。PATCH-SKILL-CREATE-ROOT 用了真实 Python import + 调用，是最稳的方式；其他 patch 条件允许时应向这个模式靠拢。                                  |
| **工程外补丁无版本对齐**        | PATCH-ZSH-COMPLETION-SYNTAX 的 inline Python 替换依赖 `hermes completion zsh` 输出的固定格式。如果上游改了补全生成逻辑但仍有 bug，替换可能失效。目前有 "skip if already correct" 逻辑兜底。                                                                                         |

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
    "gateway/display_config.py"
    "plugins/platforms/feishu/adapter.py"
    "skills/research/llm-wiki/SKILL.md"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/session.py"
    "gateway/session_context.py"
    "gateway/stream_consumer.py"
    "hermes_cli/doctor.py"
    "hermes_cli/tools_config.py"
    "agent/prompt_builder.py"
    "agent/skill_utils.py"
    "tools/approval.py"
    "tests/tools/test_approval.py"
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
    "tests/gateway/test_display_config.py"
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
    "hermes_cli/runtime_provider.py"
    "agent/auxiliary_client.py"
    "agent/image_routing.py"
    "tests/agent/test_image_routing.py"
    "agent/replay_cleanup.py"
    "tests/agent/test_replay_cleanup.py"
    "tests/gateway/test_stale_confirmation_expiry.py"
    "native/fts5_cjk/build.sh"
)
```

> 以上为 `hermes-update.sh` 中数组的快照（60 文件，2026-07-29 与脚本核对一致）。**脚本数组是唯一权威来源**；增删补丁文件后请同步刷新本快照。

### 手动恢复

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突（推荐）：git apply --3way 留下 <<<<<<< 标记逐处解决（多为"并存"型冲突），
#   然后 git add <冲突文件> && git reset 清索引，再重跑 hermes-update.sh 走完整验证
#   （2026-07-13 轮实测流程；注意 git apply 输出别接 head 截断，SIGPIPE 会中断 apply）
# 或：git apply --reject && 手动解决 .rej，再重跑 hermes-update.sh

# 若 patch 文件自身已被 conflict marker 污染，可先恢复入库版本
cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff

# 查看 patch 基于的上游版本
cat ~/.hermes/patches/.local-patches.base
```

---

## 当前版本：v0.19.0 (upstream `main` `41a07f5b`，2026-07-29)

**活跃补丁**：当前共 24 个语义补丁。22 个工程内补丁由 Step 8b/8c 管理，`PATCH-NPM-DEPENDENCY-HYGIENE` 由 Step 3/4 管理，`PATCH-FEISHU-GROUP-SANDBOX` 是配置仓库用户插件补丁、由 Step 8e 管理。完整 ID 以本节 `### [PATCH-*]` 定义块和上方执行链清单为准；升级历史只提供事件背景，不构成 patch registry。

**最近一次升级（v0.19.0 → v0.19.0，+903 commits，basis `d71033a4` → `41a07f5b`）要点**：

- 上游主线（903 commits，间隔 2 天，release tag 维持 v0.19.0 (2026.7.20)，无新 release）：**Gateway / Sessions**——关停前 flush 内存消息与待写 memory（`23e44a284` / `5cc5c58e`）、生命周期 ledger 检测非正常退出（`9c76c133b`）、多平台 webhook dual-stack（`2c771be40`）；**Voice / STT / 媒体**——STT 工具与 GUI 完整可配置（`96bf65a6f`）、Gemini SSE + xAI WebSocket 流式 TTS（`bc4dcb1b0`）、飞书原生语音正确分类（`1ca1deb7f`）；**Desktop / Photon / Web**——browser backend readiness（`2319dbb01`）、Photon zombie stream 恢复（`709dd3282`）、原生 poll 与链接预览（`fe95194c5` / `cf550c086`）、session 过滤（`cb0049555`）；**模型 / 观测**——Gemini 默认值推进到 3.6 Flash（`63fc810b9`）、Relay 运行时与 metrics pipeline（`3bd338d2a`）；**安全 / Tools**——voice subprocess 凭据脱敏（`24a6fb644`）、MCP 工具名冲突拒绝（`20de37d40`）、cron 对 env 注入凭据的端到端契约回归（`41a07f5b`）。
- patch apply / registry：首轮 `d71033a4` → `5cc5c58e` 在 solvepatch 解冲突后中断；接管检查确认无 conflict marker、index 干净、bundle 正反向 apply check 均通过，但 `tools/skill_manager_tool.py` 为保留 `PATCH-SKILL-CREATE-ROOT` 而补回的 `os` import 尚未捕获进 bundle。完整重跑将该冲突修复纳入 replay bundle，并在新增 1 个 upstream commit 后 clean apply 到 `41a07f5b`。逐块读取上游吸收条件并以裸 `HEAD` 功能特征复核：24 个活跃 PATCH 全部仍需保留，无新增、部分吸收或归档。终态 60 files **clean apply**，22 个活跃工程内 gate、5 个 Step 8b Archive sentinel、Step 7 completion sentinel 与 Step 8e sandbox verifier 全 OK。Step 3 七层闭环成立：60/60 文件有 diff、bundle 与 overlay 逐字节一致、正向 cached / 反向 worktree apply check 通过、base=`41a07f5b`、index 干净、注册表/执行链唯一、外层插件未混入 bundle；额外内层改动仅有 bundle 外 `package-lock.json` 归一化。功能回归按动态集合为 23 files **1852 passed / 0 failed**，较期中基准 1850/0 增加 2 条上游测试。锚点漂移 `d71033a4` → `41a07f5b`。
- 依赖：本轮**无 venv 重建**，uv 仅重装新 checkout 的 editable Hermes；补丁态 `refresh_active_features()` 报告 19 个 active backend 全部 current，`python-socks 2.8.1`、`pypdf 6.14.2`、pytest/dev 工具链均存在，无 `.venv` / `venv.stale.*` 残留。根 `npm install` 恢复 `agent-browser 0.26.0`；doctor 提示的根级 `npx playwright` 在 npm workspace 布局下找不到 CLI，改用同一已安装包的 `apps/desktop/node_modules/.bin/playwright install chromium` 恢复 Chromium，doctor 两项均转 ✓。npm 12 仅将 bundle 外 `package-lock.json` 中 26 个 `peer` 标记归一化删除，无版本变动。`npm audit fix` 被 ui-tui `eslint@9` / `eslint-plugin-react@7.22` peer 冲突阻断；全 workspace audit 剩 1 low / 26 high / 1 critical，其中 critical 为 Electron builder 开发链间接 `tar 7.5.17`，需上游 lockfile/版本升级，未使用 `--force` 引入破坏性大版本。Skills mirror `+0/~0/−3`，Step 8c 后 llm-wiki 回同步补丁版并 re-baseline。
- 已知摩擦：中断的 solvepatch 结果与当时 bundle 仅差必要的 `os` import，已由 Step 2 重新捕获并完成全流程验证；`npm audit fix` 的 ERESOLVE 是上游 ui-tui 工作区 peer 冲突，实际 lock drift 已审查且保持 bundle 外；doctor 的 Playwright 修复命令与 workspace CLI 位置不一致，已用真实 CLI 自愈。`uv --python venv/bin/python` fallback 0 次，E-949 runtime repair 未复发。
- 配置漂移：`hermes doctor` 显示 `Config version up to date (v33)`，无需 `--fix`；doctor 只保留 web 8 high / ui-tui 7 high 构建工具 advisory，未登录 provider、未配置可选工具不属于升级缺口。Gateway plist matches current install；该轮 launchd 监管 PID `69391`，sandbox verifier 对照同一 PID 通过。owner Feishu DM 保持 terminal/process/read/write/patch/code/skill-manage 完整工具面，群聊仍严格限制为 `group_cache` / `feishu_doc_manage` + 只读 file/skill 工具。

> 仅保留最近一次升级摘要；历次升级的逐版本叙述见 `README.md` § 版本记录。

### [PATCH-SKILL-CREATE-ROOT] 自定义 skill 创建到用户目录

| 字段     | 内容                                                                    |
| -------- | ----------------------------------------------------------------------- |
| **文件** | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 未上游合并（`_resolve_skill_dir()` 仍只用 `SKILLS_DIR / name`）      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：让 `_resolve_skill_dir()` 直接按配置顺序读取 `skills.external_dirs`，第一个非官方目录作为新 skill 的基准路径；即使目录尚不存在也由 create 建立，避免 discovery helper 只返回既存目录时错误回落官方 root。`_create_skill()` / `_delete_skill()` 同步适配，并加 `tests/tools/test_skill_manager_tool.py` 回归测试覆盖 external dir 路由、缺失目录创建与删除。

**验证**：Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("dummy_unit_test_skill")`，断言返回路径 startswith `~/.hermes/my-skills/`。

**上游吸收判断**：仅当上游 create 路径已支持把首个 external skill root 作为默认写入目录，且对应创建/删除测试覆盖不存在目录时，才可移除本补丁；当前上游仍固定写入 `SKILLS_DIR / name`。

---

### [PATCH-NPM-DEPENDENCY-HYGIENE] npm 漏洞修复与 install-script policy

| 字段     | 内容                                                       |
| -------- | ---------------------------------------------------------- |
| **文件** | `hermes-update.sh` + `node_modules/`（gitignored）         |
| **状态** | 🟢 自动化（Step 3 scoped policy + Step 4 `npm audit fix`） |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。Node 26 / npm 12 进一步默认阻止未经审核的 dependency lifecycle scripts；本仓 update 的 root + ui-tui/web 安装会反复提示 `agent-browser@0.26.0`、`esbuild@0.28.1`、`fsevents@2.3.3`、`unicode-animations@1.0.3` 未被 `allowScripts` 覆盖。四个包当前产物实际可用，但每次升级重复告警；用 `dangerously-allow-all-scripts` 会把未来任意传递依赖也放行，不可接受。

**修复**：保留 Step 4 的 `npm audit fix --quiet`；同时在调用 `hermes update` 前为 npm ≥12 创建权限为 0600 的临时 global-config，仅写入四个已审核且**版本钉死**的 allow 条目，并通过 `NPM_CONFIG_GLOBALCONFIG` 只传给本轮 `hermes update` / audit，结束或异常退出均删除。不会修改 `~/.npmrc`，不会影响其他项目，也不会继承未来版本的脚本权限。`agent-browser` postinstall 只校验/准备对应平台 binary，`esbuild` 校验平台 binary，`fsevents` 提供 macOS native watcher，`unicode-animations` 在上游强制的 `CI=1` 环境中 no-op。

**验证**：以相同临时 policy 实跑 root `npm ci --workspaces=false` 与 ui-tui/web workspace `npm ci`，均无 `install scripts blocked` / `not covered by allowScripts`；随后 audit 恢复完整 workspace 产物，`agent-browser 0.26.0`、`esbuild 0.28.1`、`require("fsevents")`、`require("unicode-animations")` 全部可用，package.json / lockfile 无 tracked drift。

**上游吸收判断**：这是本地升级流程的依赖安全策略；只有上游升级器同时提供等价的 scoped install-script allowlist、自动清理临时配置和漏洞修复流程后，才可移除本补丁。

---

### [PATCH-FEISHU-SOCKS-DEPENDENCY] Feishu 代理依赖声明

| 字段     | 内容                                   |
| -------- | -------------------------------------- |
| **文件** | `pyproject.toml`, `tools/lazy_deps.py` |
| **状态** | 🟡 未上游合并                          |

**问题**：`feishu` optional extra 和 `tools/lazy_deps.py` 的 `platform.feishu` 上游当前都只声明 `lark-oapi==1.6.8` + `qrcode==7.4.2`。代理网络下 `lark-oapi` 的 WebSocket 连接需要 SOCKS 支持，缺 `python-socks` 时 gateway 起来后报 `connecting through a SOCKS proxy requires python-socks` 并反复重连失败。

**修复**：在 `pyproject.toml` 的 `feishu` extra 和 `tools/lazy_deps.py` 的 `LAZY_DEPS["platform.feishu"]` 都加 `"python-socks==2.8.1"`。手动 `.[feishu]`、`.[all,feishu]`、和上游 lazy install 三条路径都能拿到 SOCKS。版本钉死风格与上游 2026-05-14 起 messaging extras `==X.Y.Z` 约定一致（避免 `>=2.0,<3` 被 `uv lock --check` 报漂移）。

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在。

**上游吸收判断**：当上游 `feishu` extra 与 `LAZY_DEPS["platform.feishu"]` 都显式声明兼容的 SOCKS 依赖，并通过代理连接回归后，才可移除本补丁；任一路径缺失都必须保留。

---

### [PATCH-OPENCLAW-TOKEN-MIGRATION] OpenClaw 迁移不写废弃 gateway token

| 字段     | 内容                                                                                                                         |
| -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                             |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；迁移文档同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本和迁移文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token`。

**上游吸收判断**：当上游迁移脚本不再写入废弃的 `HERMES_GATEWAY_TOKEN`，且迁移文档同步移除该映射后，才可移除本补丁；当前上游两处仍未吸收。

---

### [PATCH-FEISHU-GROUP-ADMISSION] 群聊触发、上下文与当前发言人完整性

| 字段     | 内容                                                                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `gateway/authz_mixin.py`, `gateway/run.py`, `gateway/session.py`, `skills/research/llm-wiki/SKILL.md` 及对应 gateway 测试/文档 |
| **状态** | 🟡 未上游合并                                                                                                                                                                              |

**问题**：群聊需要同时支持 `@bot` 与 `@配置本人账号` 触发、近期群消息回填和纯 @ 意图推断；共享 session 还必须防止 owner profile、引用内容、历史末位发言人或跨发送者 debounce 被误认成当前提问者。群授权也不能借通配符放开 DM。

**修复**：实现 assistant-user/configured-human 两类触发与身份说明、群历史回填、默认关闭且可配置的 `bare_mention_intent`、`FEISHU_GROUP_ALLOWED_CHATS` 群授权；把 bot mention 设为最高触发优先级，批处理 key 纳入发送者，并在 system prompt 和最终 user turn 相邻位置双重标注 current author。技术问题提示显式要求先读 `llm-wiki`，所有 wiki 文件调用必须携带 `~/.hermes/wiki` 路径，禁止用 terminal 探测；bundled skill 同步相同规则。

**验证**：Step 8b 独立 gate 检查 trigger/settings/history/bare-mention/wiki sentinels、group allowlist、current-author prompt/body prefix、bot 优先级和跨发送者不合并测试。定向测试覆盖未 @ 静默、第三方 @本人代答、本人 @bot 不自我介绍、纯 @ 引用/历史意图、DM 不被群 allowlist 放开，以及历史末位发言人与当前提问者不同时仍正确锚定当前作者。

**上游吸收判断**：上游同时具备等价的 Feishu 多触发 admission、群历史/纯 @ 意图、按发送者隔离的 batching 和多用户 current-author 契约后可归档；工具权限隔离不属于本补丁。

---

### [PATCH-FEISHU-GROUP-SCOPE] 群聊独立 capability namespace

| 字段     | 内容                                                                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session_context.py`, `gateway/run.py`, `hermes_cli/tools_config.py`, `tests/gateway/test_session_env.py`, `tests/hermes_cli/test_tools_config.py` |
| **状态** | 🟡 未上游合并                                                                                                                                              |

**问题**：Feishu DM 与群聊原本都只解析 `platform=feishu`，无法对同一 bot 的 owner DM 和共享群配置不同 toolsets/skills。

**修复**：新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`；Feishu group/forum/channel/thread 映射到 `feishu_group`，DM 仍为 `feishu`。平台工具解析和保存逻辑识别该独立 key，并允许显式关闭 platform-native tool recovery，防止配置过的群工具面被默认能力补宽。

**验证**：Step 8b 单独检查 session context key、`return "feishu_group"`、tool recovery 开关，以及 `test_set_session_env_sets_feishu_group_config_key` / `test_get_platform_tools_feishu_group_uses_independent_config`。

**上游吸收判断**：上游提供等价的 per-chat-type capability namespace，且 Feishu DM/group 可以独立解析工具配置时可归档。

---

### [PATCH-PLATFORM-CAPABILITY-SCOPE] 平台级 skill allowlist 与只读工具集

| 字段     | 内容                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `agent/prompt_builder.py`, `tools/skills_tool.py`, `toolsets.py` 及对应 tests/docs |
| **状态** | 🟡 未上游合并                                                                                              |

**问题**：`skills.disabled` 不能表达“某平台只允许指定 skill”；完整 `skills` toolset 又同时暴露 `skill_manage`。文件工具也缺少只读组合，平台配置容易无意带入写能力。

**修复**：新增 `skills.platform_allowed.<platform>`，并让 prompt、list/view 和 config-var discovery 共用同一解析；增加 `skills_readonly`（list/view）与 `file_readonly`（read/search）内部工具集。分类 skill 的规范名按短名匹配 allowlist，避免 `productivity:feishu-docs` 被错误拒绝。

**验证**：Step 8b 独立检查 `get_allowed_skill_names` 的三个调用面、只读工具集成员和 qualified-name 回归；测试覆盖空 allowlist、命名 allowlist、`feishu_group` 独立配置及只读工具集不被错误过滤。

**上游吸收判断**：上游原生提供平台级 skill allowlist 和不含 manage/write 的只读 skill/file toolsets 后可归档。

---

### [PATCH-FEISHU-GROUP-APPROVAL] 群聊危险命令审批不可升级权限

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `tools/approval.py`, `tests/tools/test_approval.py`    |
| **状态** | 🟡 未上游合并；`PATCH-FEISHU-GROUP-SANDBOX` 的纵深防线 |

**问题**：旧群聊 terminal 路径曾进入 dangerous-command approval，群成员点击卡片后命令继续执行。即使当前群聊不再暴露 terminal，审批层若不区分 chat type，未来工具配置漂移仍可能重新形成提权路径。

**修复**：`_is_restricted_feishu_approval_session()` 对 Feishu group/forum/channel/thread 直接返回 `BLOCKED`，不通知、不入 pending queue、不发送审批卡；owner DM 继续走 manual approval。旧入口与主 command-guard 路径都接入硬拦。

**验证**：Step 8b 单独检查 hard-block helper 和 `test_feishu_group_dangerous_command_does_not_send_approval_card`，覆盖 `restricted_chat`、零通知、零 queue；Step 8e 再验证 owner DM 仍保留完整工具与人工审批策略。

**上游吸收判断**：上游 approval 原生按 chat type 禁止共享群创建或批准危险操作、同时不影响 owner DM 时可归档。

---

### [PATCH-FEISHU-NORMAL-REPLY] 回复始终留在普通聊天消息流

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：`root_id`/generic `metadata.thread_id` 会让普通引用回复被 Feishu 当作 thread/topic 投递，甚至在无有效引用锚点时把 thread id 当 receive id。

**修复**：发送出口固定 `reply_in_thread=False`；引用目标只取显式 `reply_to`/`reply_to_message_id`；create-message 分支忽略 generic thread metadata，缺引用锚点时回退主聊天普通消息。

**验证**：Step 8b 单独检查 `reply_in_thread = False`、忽略 thread metadata 的实现和回归测试；覆盖普通引用、文档回复和无引用锚点三条路径。

**上游吸收判断**：上游提供明确的普通引用/话题开关并保证 generic thread metadata 不改变 Feishu 投递 lane 后可归档。

---

### [PATCH-FEISHU-FINAL-ONLY] Feishu 默认只展示最终回复

| 字段     | 内容                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/display_config.py`, `tests/gateway/test_display_config.py`（本机 `config.yaml` 有显式同值覆盖） |
| **状态** | 🟡 未上游合并                                                                                            |

**问题**：Feishu 默认 tool progress、streaming 和 interim bubbles 会把草稿、工具进度或思考式中间态暴露到群聊；这与消息是否进入 thread 无关，应独立控制。

**修复**：Feishu 内置 display tier 默认关闭 tool progress、streaming、interim assistant messages、long-running notification 和 busy detail，只发送最终回复。

**验证**：Step 8b 单独检查 Feishu display defaults 与 `test_feishu_defaults_to_final_only`。

**上游吸收判断**：上游 Feishu 默认 final-only，或提供等价且默认安全的 display profile 后可归档。

---

### [PATCH-LOCAL-PROFILES] 本地人物/群画像与群聊输出保密

| 字段     | 内容                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `gateway/run.py`, `gateway/stream_consumer.py` 及对应测试；`people.yaml` / `groups.yaml` 为配置仓库数据 |
| **状态** | 🟡 本地个性化功能，不预期上游直接吸收                                                                                         |

**问题**：模型只凭 open_id/显示名无法按用户维护的人物背景和群人设调整表达；画像私有字段、数据来源和 `people.yaml` 文件名又绝不能在群聊泄露。工具受限时也必须披露证据边界，不能把未验证内容包装成结论。

**修复**：按 mtime 热加载 people/group profile；人物画像拆为公开字段与保密字段，群画像只控制风格、介绍、能力口径和提示性服务时间。所有 group/channel 无条件注入来源保密和工具限制声明；非 DM 的最终、流式、fallback 等可见输出统一经过 `redact_private_person_profile_text`/`text_filter`。loader 缺文件或坏 YAML 时安全降级，DM 不注入群画像规则。

**验证**：Step 8b 检查 profile loaders/lookups、公开 `address`、来源保密常量、私有值/文件名字面量 redactor、stream filter 和两组 profile tests。验证只归属于画像与输出过滤；旧 terminal/script-root allowlist 已被删除，不再作为本补丁的实现或测试。

**上游吸收判断**：若上游提供等价的本地 per-sender/per-group profile 注入与全出站路径隐私过滤，可重新评估；否则保持本地补丁。

---

### [PATCH-FEISHU-RESOURCE-ACCESS] 附件回看、Drive 链接与 tenant 文档读取

| 字段     | 内容                                                                                                                                                               |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/platforms/base.py`, `tools/feishu_doc_tool.py`, `tests/gateway/test_feishu.py`, `tests/tools/test_feishu_tools.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                      |

**问题**：群聊媒体与 @mention 常分成两条消息，引用里的 `/file/<token>` 也不是 IM 附件；普通 gateway 工具调用没有 comment thread-local client 时，tenant 凭据明明存在却无法读取飞书文档。

**修复**：按同发送者和引用链有界回看附件、去重并回填；扫描正文/引用中最多三个 Drive file token，以 tenant 身份下载并保留 MIME/文件名。`feishu_doc_read` 缺 comment client 时从 env/`.env` 构建 tenant client。该补丁只负责取得资源字节或 API 文本，不负责解析文件格式。

**验证**：Step 8b 单独检查 sender/reply backfill、去重窗口、Drive URL/download、tenant client fallback 及对应测试；覆盖失败静默降级、数量上限和 DM/group 通用 doc client。

**上游吸收判断**：上游同时支持分离消息附件回看、Drive 正文链接下载和无 comment-context 的 tenant doc client 时可归档。

---

### [PATCH-DOCUMENT-EXTRACTION] 可信文档文本抽取

| 字段     | 内容                                                                                                                                  |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/run.py`, `tools/file_operations.py`, `tools/read_extract.py`, `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock` 及对应 tests |
| **状态** | 🟡 未上游合并                                                                                                                         |

**问题**：附件成功下载后，PDF/DOCX/XLSX 等二进制仍只给模型路径；群聊又不能临时执行解析脚本。通用 `read_file` 也会在二进制检测前拒绝 `.xlsx`。

**修复**：`read_file` 原生抽取 XLSX sheet 文本；可信解析层支持 PDF、HTML、PPTX、ODT、IPYNB、DOCX、XLSX，移除 HTML 主动内容并对每文件/每轮文本做上界。`gateway/run.py` 在线程池中抽取，向模型明确内容是不可信参考数据；加密、扫描或损坏文档保留路径并返回可解释降级。依赖在 project extra、lazy deps 与 lockfile 中固定。

**验证**：Step 8b 单独检查 spreadsheet reader、common extractors、`_extract_inbound_document`、pypdf 双路径依赖和测试类；覆盖 PDF 页边界、HTML 清理、Office/OpenDocument 顺序、字符上界及不依赖 terminal。

**上游吸收判断**：上游提供等价的可信常见文档抽取和 XLSX `read_file` 支持后可归档；资源获取能力独立留在 `PATCH-FEISHU-RESOURCE-ACCESS`。

---

### [PATCH-FEISHU-MARKDOWN] Feishu 出站 Markdown 归一化

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：飞书 post/md 元素能渲染行内标记（加粗 / 斜体 / 列表 / 链接 / 行内代码），但有两类格式无法渲染：①ATX 标题 `## heading` 与引用 `> quote` 以原始符号字面显示；②（2026-07-25 新增）飞书 md 解析器严格执行 CommonMark emphasis flanking 规则——`**` 内侧是标点且外侧紧贴文字时加粗不成立（如 `到**“端云通信协议”**的`，中文引号与文字间无空格是 CJK 排版常态），星号原样显示。真机 A/B 实测确认：`到 **“x”** 的`（外侧空格）、`**x：**`（行边界）、`，**x**。`（外侧标点）、`****x****`（嵌套）均正常渲染，唯独"外侧贴字 + 内侧标点"失败；近 21 天 445 条出站消息中 84 条中招，遍布主会话与各群。

**修复**：两处改动，均在 `_build_outbound_payload` 出站路径：

1. **标题 / 引用**：新增 fence-aware 预处理器 `_promote_block_markdown(content)`，将 post/md 渲染不出的块级语法转成等价可渲染形式：`## heading` → `**heading**`，`> quote` → `▎ quote`；代码块内的 `#` / `>` 原样保留。

2. **行内加粗 flanking**（2026-07-25）：`_promote_block_markdown` 逐行（跳过代码块与行内代码 span）调用 `_fix_strong_flanking`：按 CommonMark 规则（标点=Unicode P*/S* 类）检测无法 open/close 的 `**span**`，仅把违规一侧的边缘标点连续段移出标记（`到**“x”**的` → `到“**x**”的`），字符序列不变；全标点 span 无法挽救时去掉标记。刻意不做"对称搬移"——那会把与 span 中部配对的括号也拽出粗体，产生更差的观感。合法 span（外侧为空白/标点/行边界，或内侧为文字）一律不动；内容无变化时保持返回原对象（fast path 身份语义不变）。

**表格子分支（已退役 2026-07-25）**：旧版补丁曾在检出 GFM 表格时先调 `convert_table_to_bullets()` 转成 `**行标题**` + bullet 组，规避早年"含表格的 post/md 整条空白"的客户端 bug。上游 #52786（2026-07-24 轮吸收 `prefer_post` 时的冲突来源）声称新版客户端已原生渲染表格；2026-07-25 真机实测「含 GFM 表格的 post/md 消息」正常渲染（不空白、单元格加粗正常）后，按既定计划撤除该子分支：`_build_outbound_payload` 恢复上游表格直传原文，补丁自有测试 `test_build_outbound_payload_table_converts_to_bullets_and_posts` 删除，上游 `test_build_outbound_payload_uses_post_for_markdown_table` 恢复上游原断言（表格原样直传）。若老客户端再现空白表格，可从外层仓历史恢复该分支（见 git log patches/local-patches.diff）。

**验证**：Step 8b grep `adapter.py` 中存在 `def _promote_block_markdown`、`def _fix_strong_flanking`；grep `test_feishu.py` 中存在 `test_promote_block_markdown_fixes_strong_flanking`；`tests/gateway/test_feishu.py` 全量 237 passed（2026-07-25，含新增 3 条 flanking 用例；表格退役后恢复上游直传断言；SSRF rebind 测试本次单文件跑亦通过）。flanking 修复上线前经真机三轮 A/B：真实失败样例（`**“端云通信协议”**` 等）复现失败 → 修复后写法（`“**端云通信协议**”`）实测正常渲染；近 21 天语料重放确认 84/445 条会被改写且全部改写结果 flanking 合法。

**上游吸收判断**：若上游为飞书 post/md 原生补齐标题 / 引用渲染，或将回复改走 interactive card markdown 元素，可归档本补丁的 promote 分支；flanking 分支（修复 ②）在上游对出站 markdown 做等价 flanking 归一化前保持活跃。表格转 bullets 子分支已于 2026-07-25 真机验证原生表格渲染后撤除（该部分现与上游 #52786 行为一致，见上文"表格子分支（已退役）"）。

---

### [PATCH-FEISHU-SSRF-TEST-SYSPROXY] SSRF rebind 测试对宿主系统代理 hermetic

| 字段     | 内容                           |
| -------- | ------------------------------ |
| **文件** | `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                  |

**问题**：上游 `test_download_remote_document_blocks_connect_time_rebind` 只把 6 个代理**环境变量** patch 成空串来构造"无代理直连"场景，但 httpx `trust_env` 的代理解析走 `urllib.request.getproxies()`——env 为空时在 macOS 回落到 **scutil 系统代理配置**（Windows 回落注册表）。宿主开着系统级代理（本机 Clash Verge，127.0.0.1:7897）时，请求实际经代理外发，direct-connect SSRF 守卫按设计把最终目标解析委托给代理（"proxy = trusted egress boundary"，见 `create_ssrf_safe_async_client` docstring），测试预期的 `SSRFConnectionBlocked` 永不触发，收到裸 `httpx.ConnectError`。后果：只要跑回归时 Clash 系统代理开着，规范 runner（`scripts/run_tests.sh`）必然 1 failed，升级 playbook 的 "0 failed" 完成标准无法达成。此前摩擦表把该现象误诊为"跨文件测试状态依赖、批量跑通过"——实际变量是**跑测试那一刻宿主系统代理的开关状态**，与文件组合方式无关（2026-07-29 以 probe 插件证实测试内 HERMES_HOME 隔离与 allow_private 缓存均正常，failing connect 目标为 `127.0.0.1:7897`）。

**修复**：测试的 `with` 块内在 `patch.dict(os.environ, proxy_vars)` 之后追加 `patch("httpx._utils.getproxies", return_value={})`（httpx 0.28 在 `_utils` 模块顶部 `from urllib.request import getproxies`，client 构造时经 `get_environment_proxies()` 调用），把系统代理回落一并掐断，使测试语义回到其本意（无任何代理、纯直连路径校验 connect-time rebind 拦截）。生产代码零改动；env 变量 blank 保留（防护其他读取路径）。

**验证**：Step 8b grep `tests/gateway/test_feishu.py` 存在 `httpx._utils.getproxies`。`tests/gateway/test_feishu.py` 全量 237 passed / 0 failed（2026-07-29，Clash 系统代理**开启**状态下经规范 runner 复跑通过；修复前同条件 1 failed，且单 pytest 进程多文件组合同样失败，证伪旧"批量通过"结论）。

**上游吸收判断**：上游为该测试补上系统代理中和（patch `getproxies` / `trust_env=False` / mounts 显式置空任一等价手段）后可归档本补丁；届时同步删除摩擦表对应 row。

---

### [PATCH-VERTEX-HIDDEN-THOUGHTS] Vertex 保留 thinking 但隐藏 thought 文本

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

### [PATCH-VERTEX-DOCTOR] Doctor 识别官方 Vertex provider

| 字段     | 内容                                                      |
| -------- | --------------------------------------------------------- |
| **文件** | `hermes_cli/doctor.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🟡 未上游合并                                             |

**问题**：切到官方 `model.provider: vertex` 后，实际 runtime provider 已能通过 `providers.get_provider_profile("vertex")` 和 `agent.vertex_adapter` 正常拿 OAuth token 调 Vertex OpenAI-compatible endpoint，但 `hermes doctor` 仍只看 auth/catalog provider 列表，不读 model-provider plugin registry，于是误报 `model.provider 'vertex' is not a recognised provider`。同时 `google/gemini-3.1-pro-preview` 这类 Vertex 官方 OpenAI-compatible 模型名被当作 OpenRouter 风格 vendor slug，额外误报应该切 openrouter 或去掉前缀。

**修复**：doctor 在校验 provider 时补充读取 `providers.get_provider_profile()`，将 plugin profile 的 canonical name 加入可接受 provider id 集合，并让 vendor-slug 策略同时考虑原始 provider、auth runtime provider、catalog provider 与 plugin canonical provider。`vertex` 被加入允许 `vendor/model` 形态的 provider 集合；`.env` 健康检查同时识别 `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT_ID` / `VERTEX_LOCATION`，避免只配置官方 Vertex 凭据时被误判为没有 provider auth。

**验证**：Step 8b grep `hermes_cli/doctor.py` 中存在 `_get_provider_profile`、`GOOGLE_APPLICATION_CREDENTIALS` 与 `"vertex"`，并 grep `tests/hermes_cli/test_doctor.py` 中存在 `test_run_doctor_accepts_vertex_provider_and_google_model_slugs`。规范 runner 定向回归：`test_doctor.py` 83 passed、`test_vertex_provider.py` 23 passed、`test_session.py` 167 passed（合计 273 passed / 0 failed）。实际 `hermes doctor` 在当前 `provider: vertex` 配置下显示 `Config version up to date (v33)`，Vertex 配置检查通过；仅另报 web 8 high / ui-tui 7 high 的已知 build-tool advisory。

**上游吸收判断**：若上游 doctor 原生读取 model-provider plugin registry，或官方 registry/catalog 把 `vertex` 与其 `google/*` OpenAI-compatible 模型名纳入健康检查策略，可归档本补丁。

---

### [PATCH-VERTEX-FALLBACK] 第二 Vertex 账号作为独立 fallback

| 字段     | 内容                                                                                                                                                                                                     |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/vertex_adapter.py`, `hermes_cli/auth.py`, `hermes_cli/runtime_provider.py`, `agent/auxiliary_client.py`, `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                            |

**问题**：主模型 `google/gemini-3.1-pro-preview`（Vertex，project `wh-gemini-1`）频繁 `429 RESOURCE_EXHAUSTED`（单账号/单 project 配额），回退到 `alibaba/qwen3.6-plus`，行为与质量都跟主模型不一致。需求：fallback 换成**第二个 Vertex 账号**跑同一个 gemini-3.1-pro，行为与主模型一致，仅换账号绕开限额。两处架构约束使"同 provider 同模型换账号"无法直接配置：①`vertex` 不在 `hermes_cli.auth.PROVIDER_REGISTRY`（auto-extend 只收 `auth_type=="api_key"`），主模型靠 `resolve_runtime_provider()` 专门解析，而 **fallback 走 `resolve_provider_client()`，只从 `PROVIDER_REGISTRY.get()` 取 pconfig** → 现有 `auth_type=="vertex"` 分支对 fallback 是够不到的死代码；②fallback 去重（`chat_completion_helpers._try_activate_fallback`）对 `provider+model` 相同的条目直接跳过。此外 `get_vertex_credentials` 里 `_resolve_project_override()`（`VERTEX_PROJECT_ID`/config）会把任何账号的 token 重绑到主 project → 第二账号 403。

**修复**：新增独立 provider `vertex-fallback`，复用同一 `VertexProfile`（自动继承 `PATCH-VERTEX-HIDDEN-THOUGHTS` 的单层抑制 → 行为一致），只换凭证：

1. `agent/vertex_adapter.py`：新增 `get_vertex_fallback_config()` / `has_vertex_fallback_credentials()`，从 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（经 `_get_secret`）解析第二账号；给 `get_vertex_credentials`/`get_vertex_config` 加 `project_override`（显式项目优先）与 `apply_global_project_override=False`（不套用 `VERTEX_PROJECT_ID`），确保第二账号 token 锁在自己的 project；token 按 path 各自缓存 + 自动刷新（复用 `_creds_cache`）。
2. `hermes_cli/auth.py`：在 `PROVIDER_REGISTRY` 显式登记 `vertex-fallback`（`auth_type="vertex"`，别名 `vertex2`/`vertex-secondary`），使 `resolve_provider_client` 能取到 pconfig 并命中 vertex 分支。
3. `agent/auxiliary_client.py`：`resolve_provider_client` 的 `auth_type=="vertex"` 分支内，`provider=="vertex-fallback"` 时改用 `get_vertex_fallback_config` / `has_vertex_fallback_credentials`。
4. `plugins/model-providers/vertex/__init__.py`：用同一 `VertexProfile` 类再 `register_provider` 一个 `name="vertex-fallback"` 实例，使 `get_provider_profile("vertex-fallback")` 可解析（fallback 激活后 `_build_request_kwargs` 走 profile 路径拿到单层抑制）。
5. `hermes_cli/runtime_provider.py`（2026-07-29 补缺口）：网关 fallback 链（`gateway/run.py` `_try_resolve_fallback_provider`）解析条目走 `resolve_runtime_provider(requested=...)` 而**不是** `resolve_provider_client`；其 Vertex 分支只认主账号 5 个别名，`vertex-fallback` 静默落到 generic 尾部解析器，"成功"返回 `provider="openrouter"` + **空 api_key**——网关据此打出误导性的 `Fallback provider resolved: vertex-fallback` 日志并把坏 kwargs 交给 `AIAgent`；init 因空 key 走 router 路径，又因 `openrouter` 在豁免集合（`{auto, openrouter, custom}`）里跳过 explicit fail-fast 与 init-time fallback，最终抛 `No LLM provider configured`，用户在群聊/私聊看到 "Sorry, I encountered an unexpected error"；且链上后续条目（`alibaba/qwen3.6-plus`，NO_PROXY 直连、代理瞬断时本可救场）永远轮不到。修复：在主 vertex 分支之后新增 `("vertex-fallback", "vertex2", "vertex-secondary")` 分支，经 `get_vertex_fallback_config()` 铸 token 返回 `provider="vertex-fallback"`；凭据不可解析时抛类型化 `AuthError`，使 fallback 链前进到下一条目。触发场景：本机代理（127.0.0.1:7897）瞬断时 `oauth2.googleapis.com` token 刷新失败（"No route to host" / SSL EOF，见 `logs/agent.log*`），主 Vertex 解析抛 AuthError 进入 fallback 链。

配套（非工程内补丁）：`~/.hermes/.env` 加 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（第二账号 SA 文件 `~/.gemini/gen-lang-client-0217395804-…json`，project `gen-lang-client-0217395804`）；`~/.hermes/config.yaml` 把 `fallback_providers` 设为 `vertex-fallback/gemini-3.1-pro`，`fallback_model` 保留 `alibaba/qwen3.6-plus` 作末位兜底（有效链 = 二者 merge 去重）。

**验证**：Step 8b grep `agent/vertex_adapter.py` 存在 `def get_vertex_fallback_config` + `apply_global_project_override`；`hermes_cli/auth.py` 存在 `"vertex-fallback"`；`agent/auxiliary_client.py` 存在 `has_vertex_fallback_credentials`；`plugins/.../vertex/__init__.py` 存在 `name="vertex-fallback"`；`hermes_cli/runtime_provider.py` 存在 `"vertex-fallback", "vertex2", "vertex-secondary"` 分支；test 存在 `test_vertex_fallback_profile_registered` + `test_resolve_runtime_provider_vertex_fallback_mints_token`。单测 23 passed（2026-07-29，含 6 条 fallback 回归：新增 runtime_provider 铸 token 与 AuthError 前进两条）。真链路：`resolve_runtime_provider(requested='vertex-fallback')` 返回 `provider="vertex-fallback"`、base_url 锁定 `projects/gen-lang-client-0217395804`、api_key 为有效 OAuth token（修复前同调用返回 `provider="openrouter"` + 空 api_key）。真链路端到端：加载 `.env` 后 `get_vertex_fallback_config()` 返回 base_url 锁定 `projects/gen-lang-client-0217395804`（未被主 project 覆盖），`resolve_provider_client("vertex-fallback", model="google/gemini-3.1-pro-preview")` 返回可用 client 且真实调用返回干净答案（无 thought 段）。第二账号 SA 直连 Vertex `/v1`+`/v1beta1` global 均 200。

**上游吸收判断**：若上游为 Vertex/OAuth-token 类 provider 提供多凭证轮换池（credential pool），或让 fallback 条目原生携带 per-entry `credentials_path`/`project`，可归档本补丁改用原生机制。

---

### [PATCH-VERTEX-IMAGE-ROUTING] Gemini 3.x 图片原生路由

| 字段     | 内容                                                          |
| -------- | ------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `tests/agent/test_image_routing.py` |
| **状态** | 🟡 未上游合并                                                 |

**问题**：Vertex OpenAI-compatible endpoint 没有可靠 `/models` discovery，模型目录也可能尚未收录 Gemini 3.x preview slug；`image_input_mode:auto` 因能力未知退回 auxiliary `vision_analyze`，而 Vertex-only 安装没有该辅助凭据。

**修复**：新增窄口径 `_known_provider_model_supports_vision(provider, model)`，仅对 Vertex/vertex-fallback 常见别名和 Gemini 3.x 命名返回 `True`；其他组合继续走 config override、模型目录和原有 probe，不做泛化乐观判断。

**验证**：Step 8b 单独检查 known-provider helper、vertex-fallback、Gemini preview slug 和 `test_auto_native_for_vertex_gemini_3_preview_without_catalog_entry`。

**上游吸收判断**：上游 capability catalog 或 provider profile 稳定声明 Vertex Gemini 3.x 图片能力后可归档。

---

### [PATCH-VERTEX-VIDEO-ROUTING] Gemini 视频原生路由

| 字段     | 内容                                                                            |
| -------- | ------------------------------------------------------------------------------- |
| **文件** | `agent/image_routing.py`, `gateway/run.py`, `tests/agent/test_image_routing.py` |
| **状态** | 🟡 未上游合并；依赖 `PATCH-VERTEX-IMAGE-ROUTING` 的 Vertex/Gemini 识别          |

**问题**：上游视频只注入本地 path note，期望模型自行用 ffprobe/ffmpeg；群聊没有 terminal，因而即使附件已缓存也看不到视频内容。图片能力不能直接等同视频能力，且视频没有缩图重试，必须使用更窄的白名单和大小边界。

**修复**：新增 `decide_video_input_mode`、独立 Vertex+Gemini 3.x 视频白名单、magic-byte/MIME 校验和 14 MB 内联上限。支持的视频转换为 `data:video/*;base64` content part；gateway 用 session buffer 把 native video paths 传给 content builder，超限/不支持视频保留原 path-note 降级。无需给群聊放开任何命令工具。

**验证**：Step 8b 单独检查 video decision、native-video session buffer 和 data-URL 回归；测试覆盖 Vertex primary/fallback、非视频模型、显式配置、MIME/大小守卫和实际 content parts。

**上游吸收判断**：上游提供通用 native video routing、明确的视频 capability 和等价 MIME/size safety 后可归档。

---

### [PATCH-HISTORY-RETENTION] 平台级回放历史保留窗

| 字段     | 内容                                                                                                                                                                                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/replay_cleanup.py`, `gateway/run.py`, `tests/agent/test_replay_cleanup.py`, `tests/gateway/test_stale_confirmation_expiry.py`（配置键 `gateway.history_retention` 在 `~/.hermes/config.yaml`，非 PATCHED_FILES） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                           |

**问题**（2026-07-14 复盘 SpaceSight Tech Sharing Group 历史污染）：共享群 session 每轮把**全量** transcript 回放给模型（`load_transcript` → `_build_gateway_agent_history`），唯一的历史收敛机制是按 token 触发的 hygiene/压缩——大上下文模型（Gemini 3.1 Pro）上 94 条消息远够不到 85% 阈值，从不触发；且压缩是摘要不是丢弃。结果是 7 月 10 日 随消息入库的一次性 `[Feishu assistant mode]` 指令块 + 模型照做的范例，在 7 月 14 日 第三方 @bot（零注入分支）轮次里仍然整段可见，模型据此模式补全出「我是琛哥的赛博小助手…琛哥可能在忙」的代答口吻。缺一个与 token 无关的、按**墙钟时间和条数**的回放上界。

**修复**：`agent/replay_cleanup.py` 新增 `apply_history_retention(history, now, max_age_seconds, max_messages)`（sentinel `history-retention`）：视图级过滤——state.db 完整保留（审计 / `/resume` / 搜索不受影响），只裁剪发给模型的回放。语义：切点只落在**轮边界**（普通 user 行，`_retention_turn_starts`），绝不切断 assistant(tool_calls)→tool 配对；时间窗按整轮的开头 user 行 `timestamp` 判断，无时间戳的行视为"新"（兼容旧转录与内存脚手架，防止配置误伤成批丢历史）；条数上限向轮边界**向上取整**；最新一轮无论多旧/多长永远保留；两个限制同时配置取更严格的切点；无 user 行的退化历史原样返回。`gateway/run.py` 新增 `_history_retention_limits_for_source()`：从 `gateway.history_retention.<platform-key>` 读取限额，platform-key 复用工具/skill 配置同款 chat-scope 拆分（飞书群=`feishu_group`、私聊=`feishu`），未配置或值非法一律 fail-open 返回 None。注入点在 `_run_agent_inner` 的 cached-agent 守卫（`_select_cached_agent_history`）**之后**，单点同时覆盖「盘上转录」与「内存活转录」两条路径。本机 `config.yaml` 配置 `feishu_group: {max_age_seconds: 21600, max_messages: 30}`（6 小时 / 30 条），私聊与 CLI 不配置、行为不变。

**验证**：Step 8b grep `agent/replay_cleanup.py` 中存在 `def apply_history_retention`、`def _retention_turn_starts`，grep `gateway/run.py` 中存在 `_history_retention_limits_for_source`、`_apply_history_retention`，并 grep `tests/agent/test_replay_cleanup.py` 中的 `test_retention_never_splits_tool_call_blocks`、`test_retention_newest_turn_always_kept_even_if_too_old` 与 `tests/gateway/test_stale_confirmation_expiry.py` 中的 `test_retention_feishu_dm_not_covered_by_group_key`。定向测试覆盖：时间窗丢整轮、条数向轮边界取整、tool-call 块不被切断、最新一轮超龄/超量仍保留、无时间戳视为新、时间 + 条数组合取更严、未配置/畸形配置 fail-open、DM 不受群键影响（`test_replay_cleanup.py` 21 passed + `test_stale_confirmation_expiry.py` 15 passed；周边 `test_session.py` 167 passed + `test_feishu.py` 237 passed）。

**上游吸收判断**：若上游为 gateway 回放历史提供原生的时间窗/条数保留配置（或给共享群 session 引入等价的 per-platform replay 上界机制），可归档本补丁。

---

### [PATCH-APPROVAL-DARWIN-TMP] Darwin verify-artifact 临时路径归一化

| 字段     | 内容                                                |
| -------- | --------------------------------------------------- |
| **文件** | `tools/approval.py`, `tests/tools/test_approval.py` |
| **状态** | 🟡 未上游合并                                       |

**问题**：上游 `0c8bcd339` 的 `_is_verification_artifact_cleanup` 给 verify/ad-hoc 临时脚本的 `rm -f` 清理开豁免（不走审批），但实现只对 `tempfile.gettempdir()` 做 `realpath` 而不动 operand：Darwin 上 temp 路径全在 `/private` 别名后（`/tmp` → `/private/tmp`、`/var/folders/…` → `/private/var/folders/…`），运行时用 `gettempdir()` 原样拼出的清理命令**永远匹配不上**，豁免恒不生效、清理仍走审批（行为等同该修复落地前）；上游自带测试 `test_nonrecursive_verification_artifact_cleanup_is_not_dangerous` 在 macOS 恒失败（Linux CI 上 raw==canonical 测不出来）。同时上游另一测试 `test_symlinked_temp_dir_only_exempts_canonical_target` 锁定「一般 symlink temp 目录只豁免 canonical 拼写」，简单放开 raw 拼写会破坏该 fail-closed 语义。

**修复**：`_is_verification_artifact_cleanup` 中 operand 的合法拼写从「仅 canonical」扩展为 `allowed_spellings` 列表：canonical 拼写恒可；**仅当** `realpath(gettempdir()) == "/private" + gettempdir()`（即 Darwin 的 `/private` 系统别名，逐字符前缀判定）时才追加 raw 拼写。其余 symlink 场景（用户自建链接等）不放行，保持 fail-closed；后续的 operand realpath 包含性检查与 `hermes-(verify|ad-hoc)-` basename 正则不变。Linux 上 `realpath == raw`，条件不触发，行为与上游逐字节等价。

**验证**：Step 8b grep `tools/approval.py` 中存在 `f"/private{raw_temp_dir}"`、`allowed_spellings`，grep `tests/tools/test_approval.py` 中存在 `test_darwin_private_alias_accepts_raw_temp_spelling`。新增回归测试 `test_darwin_private_alias_accepts_raw_temp_spelling`（mock gettempdir + realpath 模拟 `/private` 别名，平台无关）：raw 与 canonical 拼写均豁免、`nested/..` 变体仍判危险；上游三件套全部转绿——`test_nonrecursive_verification_artifact_cleanup_is_not_dangerous`（macOS 上由恒败转过）、`test_symlinked_temp_dir_only_exempts_canonical_target`（fail-closed 语义保持）、`test_verification_cleanup_exemption_rejects_broader_deletions`（13 个越界变体全拒）。`tests/tools/test_approval.py` 全量 **316 passed / 0 failed**（2026-07-29；修复前 312 passed / 1 failed）。

**上游吸收判断**：上游对比较两侧统一 realpath（或等价归一化）并使其自带测试在 Darwin 通过后，可归档本补丁；届时同步删除摩擦表中 `test_approval.py` realpath row。

---

### [PATCH-FTS5-CJK-DARWIN] CJK FTS 扩展 Darwin 构建与加载

| 字段     | 内容                       |
| -------- | -------------------------- |
| **文件** | `native/fts5_cjk/build.sh` |
| **状态** | 🟡 未上游合并              |

**问题**：上游 fts5_cjk 扩展（PR #65544，中文/CJK 二元分词索引，修 1-2 字中文词在会话搜索里退化为 LIKE 全表扫）的 `build.sh` 是 Linux 写法，Darwin 上两连败：① 裸 `gcc -shared` 链接被 ld 拒绝（SQLite loadable extension 的 `sqlite3_*` 符号应由宿主进程在加载时提供，macOS 需显式 `-undefined dynamic_lookup`）；② 即使加了 dynamic_lookup，Apple SDK 的 `sqlite3ext.h` 宏映射不全，7 个 `sqlite3_*` 调用（step/prepare_v2/bind_pointer/finalize/malloc/free/mprintf）落成直连符号——而 uv-managed CPython 的 SQLite 是静态编入且**不导出**任何 `sqlite3_*` 符号，直连符号绑空指针，`load_extension` 时**段错误**。

**修复**：`build.sh` 增加 Darwin 分支：强制使用 vendored amalgamation 头（`-Ivendor`，使全部调用走 extension API 指针，`nm -u` 验证 0 个未定义 `sqlite3_*`）+ `-undefined dynamic_lookup` 链接。Linux 路径原逻辑不变。构建产物 `~/.hermes/lib/libfts5_cjk.so` 在仓库外，升级不受影响；仅上游改动 `fts5_cjk.c` 时需重跑 build.sh。

**验证**：Step 8b grep `build.sh` 中存在 `dynamic_lookup`、`Ivendor`（并提示 `~/.hermes/lib/libfts5_cjk.so` 是否已构建）。端到端（2026-07-25）：`load_fts5_cjk_extension()` 返回 True；`:memory:` 建 `tokenize='cjk_unicode61'` FTS5 表后二字中文词 `项目` 索引命中；`hermes sessions optimize-storage` 回填生产索引。

**上游吸收判断**：上游给 build.sh 加 Darwin 分支（或改用统一走 api 指针的构建方式）后，可归档本补丁。

---

### [PATCH-FEISHU-GROUP-SANDBOX] 群聊结构化 tmp 与固定文档动作边界

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | 配置仓库：`config.yaml`, `plugins/sandbox/{__init__.py,config.yaml,plugin.yaml,test_sandbox.py,verify.sh}`, `my-skills/productivity/feishu-docs/{SKILL.md,scripts/create_new_doc_from_md.py,scripts/download_feishu_file.py,scripts/feishu_common.py,scripts/read_docx_to_markdown.py,scripts/read_feishu_url.py}`, `memories/MEMORY.md`, `hermes-update.sh`, `hermes-update.md`, `README.md`（均不属于内层 `PATCHED_FILES`） |
| **状态** | 🟢 配置仓库用户插件补丁；升级保留，Step 8e 强制回归                                                                                                                                                                                                                                                                                                                                                                           |

**依赖**：`PATCH-FEISHU-GROUP-SCOPE` 提供 `feishu_group` namespace，`PATCH-PLATFORM-CAPABILITY-SCOPE` 提供只读工具集，`PATCH-FEISHU-GROUP-APPROVAL` 提供审批层纵深防线。依赖缺失时 Step 8b/8e 分别失败，不允许把插件显示为健康。

**问题**：旧版 sandbox 给 Feishu 群聊保留通用 `terminal`，再用命令字符串、脚本目录和下载目录 allowlist 约束用途。这个边界仍暴露 shell 解析面，无法从能力模型上禁止群成员创建脚本后执行，也无法限制被信任脚本及其子进程写入整个用户目录；`tmp` / `cache` 的用途和不同群之间的文件隔离也不明确。另一方面，群聊确实需要创建、追加、重建、删除和读取飞书文档，并需要一个可读写的临时数据区。主 Feishu DM 则必须继续获得默认完整工具面，危险命令走 owner 人工审批，不能被群聊策略误伤。

**修复**：从 `platform_toolsets.feishu_group` 删除 `terminal`，新增用户插件 toolset `sandbox_group`，仅暴露两个结构化入口：`group_cache` 在 `~/.hermes/tmp/group-workspaces/<chat-id-hash>/` 内执行文本文件 CRUD；`feishu_doc_manage` 将 `create/append/rebuild/delete/read_url/download_file` 六个 action 映射到管理员预装的固定脚本文件。模型不能提交 shell、脚本路径或原始 argv，工作区文件永远只作数据。工作区路径按群哈希隔离且校验相对路径、realpath 和 symlink containment；根目录权限为 `0700`。脚本以 argv + `shell=False` 执行，macOS `sandbox-exec` profile 由插件生成并由整个子进程树继承：允许读取/执行/联网，但只允许写当前群工作区；OS 进程沙箱不可用或配置加载失败时 fail closed。群聊下载限制为单文件 50 MB，`TMPDIR` 和原子更新备份都重定向到当前群工作区；stdout/stderr 回传前统一脱敏 Bearer token、Feishu app secret 与 tenant token，上传失败也切断会暴露 curl Authorization argv 的异常链。wiki 仅可直接读取 `~/.hermes/wiki`；`skills` / `my-skills` 只能经 `skills_readonly` 查看 allowlist 中的 `llm-wiki` 与 `feishu-docs`，不能直接写。`known_plugin_toolsets` 把 `sandbox_group` 标记为已知但只在 `feishu_group` 显式启用；普通 `feishu` 不配置平台覆盖，owner chat 又在 `pre_tool_call` 最前面无条件放行，因此主私聊保留 terminal、文件读写、代码执行、skill 管理、浏览器和 cron 等完整默认工具面。`tmp` 不整目录删除，因为 `scripts/nightly_greeting.py` 仍使用 `tmp/nightly_report`；群聊统一使用上述 tmp 子树，不改用 cache。

`read_url` 依赖链另有一处解释器耦合：`read_feishu_url.py` 只借用 `read_docx_to_markdown.py` 的纯渲染函数 `parse_blocks`，但后者在模块顶层 `import requests`，因此任何缺 `requests` 的解释器执行该链都会整条失败（现场表现为 `ModuleNotFoundError: No module named 'requests'`，可追至 2026-05-18，与 v0.19.0 升级无关）。根因是 `SKILL.md` 长期把 `uv run --with requests python` 作为这些脚本的规范调用方式：`~/.hermes` 下没有 `pyproject.toml` / `.venv` / `.python-version`，`uv run python` 会自行拉起一个与 hermes venv 无关的临时解释器（实测 uv 0.11.32 选到 CPython 3.13.14），其中并无 `requests`，只有 `--with requests` 才被临时注入；venv 解释器本身是 3.12.13 且 `requests==2.33.0` 为 pin 死的直接依赖。因此凡是漏掉 `--with requests`（如原 `SKILL.md:188` 的裸 `python ... append_md_to_doc.py`），或该链上任何模块在顶层 import requests 时，都会退化成 `ModuleNotFoundError`。`__pycache__` 中并存 `cpython-313` / `cpython-314` 字节码正是这些非 venv 解释器执行过的物证。配套修正 `SKILL.md`：`188` 行改为 venv 绝对路径，`232` 行依赖说明改为「首选 `~/.hermes/hermes-agent/venv/bin/python`（已 pin `requests`，无需 `--with`）」并写明裸 `uv run python` 为何不可用。修复把 `import requests` 下移进 `get_tenant_access_token()` 与 `download_doc_to_md()` 两个真正联网的函数，使纯渲染路径回到 stdlib-only；同时 `_handle_feishu_doc_manage` 的 start/end 日志补记 `python=<解释器路径>`，让后续同类故障可从 `agent.log` 直接判定实际解释器。

**验证**：`plugins/sandbox/verify.sh` 作为 `hermes-update.sh` Step 8e 的硬门槛：结构化解析根/插件 YAML，确认群策略保持 `open + require_mention`、审批为 `manual`、launchd 未启用 YOLO、owner Feishu 无 `platform_toolsets.feishu` 收窄、群聊 toolset 精确且固定脚本全部存在；通过真实 `discover_plugins()` + `_get_platform_tools()` 解析，断言 owner Feishu 仍含 terminal/process/read/write/patch/execute_code/skill_manage，群聊只含 `group_cache` / `feishu_doc_manage` 与只读工具；确认 hook 名、fire site、`ctx.register_tool()` 和 `/usr/bin/sandbox-exec`；运行 21 个插件回归，覆盖跨群隔离、路径穿越/symlink、无 terminal/直接写面、真实 owner ID 全量放行、固定 action/参数、argv 无 shell、凭据错误输出脱敏、50 MB 下载上限、真实进程沙箱外写拒绝、配置加载和工具注册；另有一条源码哨兵断言 `read_docx_to_markdown.py` 不在模块顶层 `import requests` 且两个联网函数仍保留惰性导入，双向负例（提升到顶层／删除惰性导入）均已确认会失败；最后要求注册日志的 PID 与当前 gateway PID 一致、`active=True` 且包含两个结构化工具。verifier 缺失、不可执行、配置/toolset 漂移、测试失败或 runtime trace 不匹配都会设置升级 `FINAL_RC=1`。本补丁由外层 Git 保存，`hermes update` 不覆盖；`local-patches.diff` 只监管 `PATCHED_FILES` 中的工程内语义补丁，并必须与 `hermes-agent` 实际 diff（排除已知 `package-lock.json` 噪音）逐字节一致。

**上游吸收判断**：如果上游原生提供按会话隔离的可写工作区、无 shell 的固定动作工具、子进程写范围沙箱和 owner-DM/group 独立工具面，可迁移到上游能力并归档本补丁；在此之前不得恢复群聊通用 terminal。

---

## Archive — PATCH-LAZY-ACTIVATION（上游 v0.19.0）

### [PATCH-LAZY-ACTIVATION] lazy backend 激活锚点

| 字段         | 内容                                                  |
| ------------ | ----------------------------------------------------- |
| **文件**     | `tools/lazy_deps.py`, `tests/tools/test_lazy_deps.py` |
| **状态**     | ✅ 已上游合并（v0.19.0，commit `2a55f3348`）          |
| **适用版本** | `2a55f3348` 之前需要本地 patch；之后由上游实现        |

**问题**：`active_features()` 原先只要某个 lazy feature 的任一声明依赖已安装，就把它视为“用户曾启用”并在 `hermes update` 中刷新。核心共享依赖会误激活未配置的 Matrix，反复拉取当前 macOS arm64 无法构建的 `python-olm`。

**修复**：上游 commit `2a55f3348` 将所有 lazy feature 的第一项声明依赖统一作为身份锚点；`platform.matrix` 第一项是 `mautrix[encryption]`，因此 `aiohttp`、`asyncpg` 等共享依赖不再造成误激活。该实现覆盖原本地专用 map，并对其他多依赖 feature 提供同一规则，本地源码 hunk 已删除。

**验证**：上游 `test_shared_dependency_does_not_activate_feature` 覆盖仅共享依赖存在时 Matrix 不 active；`hermes-update.sh` Step 8b 保留“首项依赖探测 + 上游回归测试”sentinel，并继续纳入 8c 总闸门。`tests/tools/test_lazy_deps.py` 仍由上游测试集覆盖，但不再属于本地 `PATCHED_FILES`。

**上游吸收判断**：已由 commit `2a55f3348` 完全吸收；若上游未来移除首项身份锚点或对应回归测试，Step 8b 必须阻断 bundle 刷新并重新评估补丁。

---

## Archive — PATCH-DOCTOR-ENABLED-TOOLSETS（上游 v0.18.0）

### [PATCH-DOCTOR-ENABLED-TOOLSETS] Doctor 只统计已启用工具集

| 字段         | 内容                                               |
| ------------ | -------------------------------------------------- |
| **文件**     | `hermes_cli/doctor.py`                             |
| **状态**     | ✅ 已上游合并（v0.18.0，commit `6b21a935a`）       |
| **适用版本** | v0.9.0–v0.17.0 需要本地 patch；v0.18.0+ 已上游修复 |

**问题（历史）**：`hermes doctor` 把所有注册但缺 API key 的 toolset（含用户从未启用的 `moa`、`rl`）计入 issue，虚报 `Found 1 issue(s) to address`。

**修复**：在 "Count disabled tools with API key requirements" 块中用 `_get_platform_tools` 过滤出用户实际启用的 toolset，只对它们报 issue。

**上游追踪**：上游 commit `6b21a935a`（`fix(doctor): ignore disabled toolsets in missing-API-key summary`）合入等价逻辑，本地 `hermes_cli/doctor.py` 已从 `PATCHED_FILES` 移除。`hermes-update.sh` Step 8b 仍保留 grep `_get_platform_tools` 的存在性检查，用于在上游回滚时及时告警。

---

## Archive — PATCH-ZSH-COMPLETION-SYNTAX（上游 v0.13.0）

### [PATCH-ZSH-COMPLETION-SYNTAX] Zsh completion `_arguments` 语法

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

**本地处置**：`hermes-update.sh` Step 7 中针对旧坏格式的 `grep -q '){-h,--help}'`、`grep -q '){-V,--version}'`、`grep -q '){-p,--profile}'` 检测块作为回归 sentinel 保留。新格式不会触发匹配，脚本日志直接输出 `PATCH-ZSH-COMPLETION-SYNTAX: upstream completion output already uses correct syntax — no fix needed`。如未来上游回滚到坏格式，inline Python rewrite 会自动重新介入。

---

## Archive — PATCH-DASHBOARD-BUILD-CACHE（上游 v0.11.x）

### [PATCH-DASHBOARD-BUILD-CACHE] Dashboard 避免无效重复构建

| 字段         | 内容                                                  |
| ------------ | ----------------------------------------------------- |
| **文件**     | `hermes_cli/main.py`                                  |
| **状态**     | ✅ 已上游合并（v0.11.x，commit `5b5a53a1`）           |
| **适用版本** | v0.9.0–v0.11.0 需要本地 patch；v0.11.x 之后已上游修复 |

**问题**：`hermes dashboard` 每次启动都在 `HERMES_WEB_DIST` 未设置时直接调用 `_build_web_ui()`；即使构建产物已存在，也会重复执行 `npm install + npm run build`，导致启动耗时数十秒。

**修复**：上游在 commit `5b5a53a155857e63ec7f7eeb373049ad224fc92f`（`fix(cli): check hermes_cli/web_dist/ not web/dist/ for build staleness`）中新增 `_web_ui_build_needed()` helper：以 `hermes_cli/web_dist/.vite/manifest.json`（fallback `index.html`）作 sentinel，并在 `_build_web_ui()` 内部判断 sentinel 是否新过所有 `.ts/.tsx/.js/.jsx/.css/.html/.vue` 源码及 `package.json/package-lock.json/vite.config.*` 等元数据；不需要重建直接早返。该实现比本地原 patch 更完整（额外覆盖 staleness），本地 PATCH-DASHBOARD-BUILD-CACHE 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：`hermes-update.sh` Step 8b 仍保留 grep `_web_ui_build_needed` 的存在性检查，用于在上游回滚时及时告警。

---

## Archive — PATCH-GEMINI-THOUGHT-SIGNATURE（上游 v0.11.0）

### [PATCH-GEMINI-THOUGHT-SIGNATURE] Gemini tool replay 保留 thought signature

| 字段         | 内容                                                                |
| ------------ | ------------------------------------------------------------------- |
| **文件**     | `agent/transports/types.py`, `tests/agent/transports/test_types.py` |
| **状态**     | ✅ 已上游合并（v0.11.0，commit `f5af6520`）                         |
| **适用版本** | v0.10.0 需要本地 patch；v0.11.0+ 已上游修复                         |

**问题**：Gemini 3.1 / Gemini 3 Flash 这类 thinking 模型在发出 tool call 后，下一轮 replay 必须把 tool call 上的 `thought_signature` 原样带回。当前版本已经把旧的 `_nr_to_assistant_message` shim 演进成 `ToolCall` dataclass + property 兼容层，但这里只暴露了 `call_id` / `response_item_id`，没有暴露 `extra_content`。于是 `run_agent.py` 中的 `getattr(tool_call, "extra_content", None)` 永远拿到 `None`，Gemini / Vertex 在 replay 下一轮直接返回 HTTP 400：`missing thought_signature`，然后触发 fallback 到 `qwen3-max`。

**修复**：上游在 commit `f5af6520d0bfac5b17c9ce460a5a06bf3249972c` 中给 `ToolCall` 增加了 `extra_content` 兼容属性，并补上了相应回归测试；本地 PATCH-GEMINI-THOUGHT-SIGNATURE 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。

**上游追踪**：最初的等价修复线索来自上游 PR `#14423`；最终关闭本 issue 的是 commit `f5af6520`。当前 `main` / v0.11.0 已包含该修复，因此本地不再维护源码 patch；`hermes-update.sh` Step 8b 保留 `ToolCall.extra_content` + `test_extra_content_getattr_pattern` 回归 gate，并将其纳入 8c 刷新前提。

---

## Archive — PATCH-DELEGATE-ACP-ROUTING（上游 v0.10.0）

### [PATCH-DELEGATE-ACP-ROUTING] Delegate ACP 子进程路由

| 字段         | 内容                                         |
| ------------ | -------------------------------------------- |
| **文件**     | `tools/delegate_tool.py`                     |
| **状态**     | ✅ 已上游合并（v0.10.0，commit hash 未记录） |
| **适用版本** | v0.9.0 需要本地 patch；v0.10.0+ 已上游修复   |

**问题**：`delegate_task(acp_command="copilot")` 传入 ACP 命令后，子 agent 的 `provider` 仍继承父 agent（如 `gemini`），未切换为 `"copilot-acp"`。`AIAgent` 构造时只在 `provider == "copilot-acp"` 时启用 ACP subprocess 通道，导致 `acp_command`/`acp_args` 被存储但从未使用，子 agent 直接走父 agent 的 API（如 Gemini），最终超时失败。

**修复**：在 `_build_child_agent()` 解析 `effective_acp_command` 之后，检测 `override_acp_command` 是否被显式设置：若是，强制 `effective_provider = "copilot-acp"`、`effective_base_url = "acp://copilot"`，确保 `AIAgent.__init__` 走 `CopilotACPClient` 子进程通道。

**上游追踪**：v0.10.0 合入等价修复（具体吸收 commit 未在本地记录），本地 PATCH-DELEGATE-ACP-ROUTING 已退役，不再通过 `PATCHED_FILES` / `local-patches.diff` 管理。`hermes-update.sh` Step 8b 保留 grep `override_acp_command` + `copilot-acp` 的存在性检查，用于在上游回滚时及时告警。

---
