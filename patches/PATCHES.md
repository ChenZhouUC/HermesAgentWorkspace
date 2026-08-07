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
> - **审计叙事不累积**：升级期外的运行态审计/修复可在 `## 当前版本` 节下以带日期段落临时记录，但只存续到下一次"最近一次升级"摘要重写——重写时把仍有价值的事实并入 README 当周 row 后删除该段落；同一事件的长期容器只有 README 周 row（详见 playbook Step 4 叙事段生命周期规则）。
> - `completions/_hermes` 类**工程外补丁**：由 `hermes-update.sh` Step 7 inline Python 在补全脚本生成后检测并修复；上游修好后脚本自动跳过、检测块保留为回归 sentinel（PATCH-ZSH-COMPLETION-SYNTAX 即此类）。

---

## 补丁管理机制

### 总体架构

所有针对 `hermes-agent/` 源码的补丁以**单一 unified diff replay bundle** 保存在 `local-patches.diff`，由 `hermes-update.sh` 全自动管理。语义补丁是独立的行为与吸收单元；replay bundle 只是原子回放载体。多个补丁共享 `adapter.py`、`gateway/run.py` 等文件，强拆物理 diff 会引入脆弱的 hunk 顺序依赖，因此当前保持一个回放包，但 Step 8b 对每个语义补丁分别设 gate。

四类补丁走不同管道：

| 类型                 | 代表                                   | 管理方式                                                                                                                                                                                                 |
| -------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **工程内补丁**       | 当前清单中标记为“未上游合并”的源码补丁 | 统一 replay bundle (`local-patches.diff`) + `PATCHED_FILES` + 每补丁独立 invariant gate；完整行为由 playbook Step 2c 回归证明                                                                            |
| **配置仓库用户插件** | `PATCH-FEISHU-GROUP-SANDBOX`           | 外层 Git 跟踪 `config.yaml` / `plugins/` / `my-skills/`；Step 8e 强制校验配置、真实 toolset、行为测试和运行时注册，失败则整次升级非零退出                                                                |
| **运行时补丁**       | `PATCH-NPM-DEPENDENCY-HYGIENE` 等      | 由 `hermes-update.sh` 的明确步骤重建并验证，不进入 replay bundle；事务/完整性 gate 失败必须令整轮非零，npm audit 被上游 lock/range 阻塞且不影响飞书主链路时归为 P2，保留明确 warning/action 并在摘要定性 |
| **已上游合并**       | 文末 Archive                           | 保留吸收来源和回归 sentinel；不计入活跃补丁清单                                                                                                                                                          |

### 更新生命周期（关键步骤）

```
Transaction: fixed upstream snapshot（PATCH-UPDATE-TRANSACTION-PIN）
  ├─ `--update`：仅在无未完成事务时允许一次 scoped official fetch
  ├─ fetch 写专用事务 ref 后立即固定 TARGET_SHA；失败/中断以 0600 状态文件持久化
  ├─ 官方 updater 经临时 Git 代理消费 TARGET_SHA（内置 fetch no-op，origin/main 被替换）
  ├─ 默认/`--reconcile`：只围绕 TARGET_SHA 做本地收敛，禁止网络获取
  ├─ 未完成事务存在时，即使再次传 `--update` 也只接管固定 SHA
  └─ 仅整支脚本 exit 0 删除事务状态；origin/main 后续前进留给下一次用户升级

Step 2: Save & Clean
  ├─ 要求 index 干净；若仅部分 PATCHED_FILES 有 diff，fail closed，不覆盖完整旧 bundle
  ├─ git diff --full-index HEAD -- PATCHED_FILES → .tmp
  ├─ .tmp 必须通过 cached 正向 + worktree 反向 replay check，才原子替换 local-patches.diff
  ├─ _restore_patched_files_to_head PATCHED_FILES  ← 逐路径还原且保护同名 untracked 文件
  └─ 设置 _PATCHES_REVERTED=true（包括接管“裸 worktree + 完整 bundle”的中断现场）

Step 3: acquire once or reconcile pinned target
  ├─ 先 stash PATCHED_FILES 之外的额外改动（含 untracked）
  ├─ 新事务 `--update`：在干净工作区上执行唯一一次 upstream update
  │   └─ 仅尚未取得目标 SHA 的早期 GitHub fetch transport 失败最多重试 3 次
  ├─ 未完成事务/`--reconcile`：校验或本地 fast-forward 到 TARGET_SHA，不 fetch/pull
  └─ 随后 pop 回额外改动；若冲突则保留 stash 供手动恢复

Step 4b: Skills 镜像同步
  └─ rsync -a --delete hermes-agent/skills/ → ~/.hermes/skills/
      ├─ 新增 skill：自动复制到本地
      ├─ 更新 skill：覆盖本地旧版本
      ├─ 删除 skill：清理上游已移除但本地残留的孤儿
      ├─ 排除 .bundled_manifest / .curator_state / .usage.json / .hub / .archive 等本地 runtime state
      └─ rsync 非零：FINAL_RC=1
      （my-skills/ 为独立目录，不受此步骤影响）

Step 8: Re-apply & Verify（核心）
  ├─ 8a. Apply saved diff
  │   ├─ 前置检查：patch 文件自身是否含 conflict marker → 含则跳过
  │   ├─ 尝试 1: git apply --check + git apply（干净 apply）
  │   ├─ 尝试 2: git apply --3way（上游改了同区域但无冲突）
  │   ├─ 3-way 成功后立即 restore --staged，终态 index 不干净也视为失败
  │   ├─ 失败: git restore --source=HEAD 回滚所有 PATCHED_FILES
  │   └─ 成功后: _has_conflict_markers() 扫描 → 含标记则回滚
  │
  ├─ 8b. Patch invariant gates（structural sentinels + smoke checks）
  │   ├─ PATCH-SKILL-CREATE-ROOT: Python import + 调用 _resolve_skill_dir()，检查返回路径
  │   ├─ PATCH-DOCTOR-ENABLED-TOOLSETS: grep _get_platform_tools in doctor.py（✅ 已上游合并 v0.18.0）
  │   ├─ PATCH-ZSH-COMPLETION-SYNTAX: Step 7 中对 `){-h,--help}` / `){-V,--version}` / `){-p,--profile}` 做回归检测（✅ 已上游合并 v0.13.0）
  │   ├─ PATCH-DASHBOARD-BUILD-CACHE: grep _web_ui_build_needed in main.py（✅ 已上游合并，仅验证）
  │   ├─ PATCH-DELEGATE-ACP-ROUTING: grep override_acp_command + copilot-acp（✅ 已上游合并，仅验证）
  │   ├─ PATCH-GEMINI-THOUGHT-SIGNATURE: grep ToolCall.extra_content + 对应回归测试（✅ 已上游合并，仅验证）
  │   ├─ PATCH-FEISHU-SOCKS-DEPENDENCY: Feishu extra 与 lazy deps 均声明 python-socks
  │   ├─ PATCH-OPENCLAW-TOKEN-MIGRATION: 迁移器不再生成废弃 gateway token
  │   ├─ PATCH-FEISHU-GROUP-ADMISSION: 群触发/上下文/当前发言人/显式 wiki 路径
  │   ├─ PATCH-FEISHU-MISSED-EVENT-BACKFILL: 断线/重连漏消息补偿与 quote 覆盖去重
  │   ├─ PATCH-FEISHU-GROUP-SCOPE: feishu_group capability namespace 与 DM 隔离
  │   ├─ PATCH-PLATFORM-CAPABILITY-SCOPE: 平台 skill allowlist + 只读 skill/file toolset
  │   ├─ PATCH-FEISHU-GROUP-APPROVAL: 群聊危险命令审批硬拦
  │   ├─ PATCH-FEISHU-NORMAL-REPLY: 普通引用回复，不进入 thread/topic lane
  │   ├─ PATCH-FEISHU-FINAL-ONLY: Feishu 默认只显示最终回复
  │   ├─ PATCH-LOCAL-PROFILES: 人物/群画像、来源保密与可见输出过滤
  │   ├─ PATCH-FEISHU-RESOURCE-ACCESS: 附件回看、合并转发完整引用、Drive/doc access
  │   ├─ PATCH-DOCUMENT-EXTRACTION: PDF/HTML/Office/OpenDocument 可信抽取（XLSX/DOCX/IPYNB 已上游）
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
      ├─ 每个 PATCHED_FILES 都必须有 live diff；部分/全部为零均阻断并要求吸收归类
      ├─ 用 --full-index 生成临时 bundle，自动执行逐字节/cached 正向/worktree 反向/index-clean 闭环
      ├─ 全绿后才原子写 local-patches.diff + .local-patches.base
      ├─ 干净但无 diff: 提示 "patches may have been absorbed" 并返回非零
      └─ apply / sentinel / conflict 任一失败: FINAL_RC=1

Step 8d: Gateway restart（post-patch）
  └─ 前提: _PATCH_APPLY_OK == true && transaction runtime_dirty == 1 && gateway 正在运行
      └─ 记录 old PID → drain-aware `hermes gateway restart`
          → 按 `gw_restart_wait_seconds()`（native exit-wait budget 优先、drain 回落，+30s）轮询 different new PID
          ├─ 成功后清 runtime_dirty；未替换或未恢复: FINAL_RC=1
          └─ HEAD/overlay 均未变化的 reconcile 明确跳过重启，不制造 PID
      （hermes update 在 step 3 重启 gateway 时补丁尚未 apply，
       Python 进程 sys.modules 缓存旧模块，需重启才能加载补丁代码；
       planned restart 给在途 agent run 完整排空预算；macOS stop 路径短宽限后
       会 SIGKILL，不能用来做常规重载，也不能把仍存活的 old PID 误认成加载成功）

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

所有写 `local-patches.diff` 的路径（Step 2 保存 + Step 8c 刷新）都先写 `file.tmp`；临时 bundle 通过 conflict-marker、cached 正向和 worktree 反向 replay check 后才 `mv -f` 替换 canonical 文件，Step 8c 还会复核 full-index live diff 逐字节一致与 index-clean。这样 `git diff` 中断、磁盘写失败或半套 overlay 都不会静默截断/降级已知完整的 replay bundle。

#### 3. Patch 文件毒化检测

Step 8a 开头先扫描 `local-patches.diff` 自身是否含 conflict marker（`^\+?(<<<<<<<|=======|>>>>>>>)`）。如果上一次脚本异常退出时 3-way merge 的冲突结果被误写入 diff 文件，这步会拦截，避免把冲突标记 apply 到源码里。

恢复方法：`cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff`

#### 4. EXIT trap 补丁恢复

Step 2 还原 patch 后设置 `_PATCHES_REVERTED=true`；接管“worktree 已经等于 HEAD、但完整 bundle 仍存在”的中断现场时也会重新武装该标志。恢复窗口覆盖 Step 2 之后直到 Step 8a 做出 apply 决策（成功重贴或有意回滚）为止：期间任何崩溃（含 Step 4–7 的裸树阶段）EXIT trap 都会自动尝试 clean/3-way replay；3-way 成功会清 staged index，失败或出现 conflict marker 会把所有受管路径恢复到确定的裸 upstream 状态，同时保留 canonical bundle 供下一轮 AI 重解，避免遗留半合并 index。Step 8a 决策后清除该标志，正常退出与失败回滚都不会重复 apply。

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

Step 2 若发现 canonical bundle 已存在、但只有部分 `PATCHED_FILES` 相对 HEAD 有 diff，会在写 bundle 前 fail closed，防止中断现场把完整包降级为残缺快照。Step 8c 对逐文件覆盖再做一次硬门禁：全部无差异表示补丁可能整体被吸收；只有部分无差异则逐条报告 zero-diff path，要求按语义块判断“完全吸收 / 部分吸收 / 补丁丢失”并同步 `PATCHED_FILES`/注册表后再刷新，不能静默把该文件从物理包里漏掉。

#### 8. 单次 upstream 快照与事务恢复

官方仓库获取和本地 patch 收敛使用两个不同入口：只有显式 `--update` 可以在新事务中执行一次 scoped fetch；获得 commit 后立即写专用事务 ref 和状态文件，再让官方 updater 通过临时 Git 代理只消费固定 SHA（其强制 fetch 变成成功 no-op，`origin/main` 参数被替换为 `TARGET_SHA`）。默认无参数和 `--reconcile` 均不得执行网络探测、fetch 或 pull。脚本不调用带隐式 update-check 的 `hermes --version`，而直接从 checkout 读取版本元数据。

失败/中断时，`.hermes-update-transaction` 保存 `old_sha`、`origin_before`、固定 `target_sha`、阶段和 `runtime_dirty`。文件用 temp + rename 原子发布、权限 `0600`、内容逐字段验证且永不 source。若进程在 fetch 更新专用 ref 后、正常状态发布之前退出，下一次从该 ref 重建目标；已有目标时任何复跑（包括误传 `--update`）都走 no-network reconcile。只有完整 exit 0 才删除状态与专用 ref。这样一轮升级面对的是不可变输入，远端后续提交不会让回归审计无限续跑。

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
    "website/i18n/zh-Hans/docusaurus-plugin-content-docs/current/guides/migrate-from-openclaw.md"
    "gateway/authz_mixin.py"
    "gateway/config.py"
    "gateway/display_config.py"
    "plugins/platforms/feishu/adapter.py"
    "skills/research/llm-wiki/SKILL.md"
    "gateway/platforms/base.py"
    "gateway/run.py"
    "gateway/slash_commands.py"
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
    "tools/read_extract.py"
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
    "tests/gateway/test_run_progress_topics.py"
    "tests/gateway/test_background_command.py"
    "tests/gateway/test_verbose_command.py"
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
    "tests/gateway/test_image_input_routing_runtime.py"
    "agent/replay_cleanup.py"
    "tests/agent/test_replay_cleanup.py"
    "tests/gateway/test_stale_confirmation_expiry.py"
    "native/fts5_cjk/build.sh"
)
```

> 以上为 `hermes-update.sh` 中数组的快照（64 文件，2026-08-07 与脚本核对一致）。**脚本数组是唯一权威来源**；增删补丁文件后请同步刷新本快照。机器读取请用 `bash ~/.hermes/hermes-update.sh --print-patched-files`，不要解析本快照。

### 手动恢复

```bash
cd ~/.hermes/hermes-agent && git apply ~/.hermes/patches/local-patches.diff
# 若有冲突（推荐）：git apply --3way 留下 <<<<<<< 标记逐处解决（多为"并存"型冲突），
#   然后 git add <冲突文件> && git restore --staged -- <冲突文件> 清索引，
#   再运行 bash ~/.hermes/hermes-update.sh --reconcile，固定 TARGET_SHA 走完整验证
#   （2026-07-13 轮实测流程；注意 git apply 输出别接 head 截断，SIGPIPE 会中断 apply）
# 或：git apply --reject && 手动解决 .rej，再运行 --reconcile

# 若 patch 文件自身已被 conflict marker 污染，可先恢复入库版本
cd ~/.hermes && git restore --source=HEAD -- patches/local-patches.diff

# 查看 patch 基于的上游版本
cat ~/.hermes/patches/.local-patches.base
```

---

## 当前版本：v0.20.0 (upstream `main` `863e31318553cda8ad61df681d08175364d4164b`，2026-08-06)

**活跃补丁**：当前共 30 个语义补丁。23 个工程内补丁由 Step 8b/8c 管理；`PATCH-NPM-DEPENDENCY-HYGIENE`、`PATCH-REPLAY-BUNDLE-FULL-INDEX`、`PATCH-UPDATE-GATE-EXIT-STATUS`、`PATCH-UPDATE-GIT-FETCH-RETRY`、`PATCH-UPDATE-TRANSACTION-PIN`、`PATCH-SKILLS-MIRROR-METADATA` 是运行时补丁，由对应 update step 管理；`PATCH-FEISHU-GROUP-SANDBOX` 是配置仓库用户插件补丁、由 Step 8e 管理。完整 ID 以本节 `### [PATCH-*]` 定义块和上方执行链清单为准；升级历史只提供事件背景，不构成 patch registry。

**最近一次升级（v0.20.0 → v0.20.0，+58 commits，basis `6564f319a` → `863e31318553cda8ad61df681d08175364d4164b`，2026-08-06）要点**：

- 上游主线：Dashboard/Web 增加 events WebSocket backoff reconnect（`fb402106f`）；脚本/评测新增 toolperf A/B harness（`ced8e3021`）；cache/compression 增加 durable prune runway 与 model-config merge helper（`bf6a210a` / `241605d1` / `565b2c42`）；模型侧新增 Actual Computer provider 与 setup skill/docs（`a9acb400` / `e79f16c` / `5aa798f`）；Gateway 修复 split-delivery final swallow、empty fallback deleted-head 计数、session-hygiene cooldown（`c46027b` / `392e3a8` / `68ebb19` / `c0d974b`）；sessions/CLI/utils 补 LIKE escaping 与 atomic write 权限边界（`1d2dabc` / `52a5fc0` / `67827dd` / `43fc865`）；read_file 上游扩展 anydoc 格式与 init/size cap（`b2598b4` / `997a913` / `ffdbc88` / `ff3793f`）；新增 Goals quality gates、Heartbeat、Refine（`6e041d` / `6518aa` / `8f2712`）；cron lifecycle guard 改为 ingestion sanitize + total path handling（`c8d48b8` / `863e313`）。
- patch apply / registry：62 个受管文件全部 clean apply，无 3-way 冲突。`PATCH-DOCUMENT-EXTRACTION` 被 `b2598b41e` 部分吸收 anydoc-only 格式、失败重试与 anydoc size cap；本地剩余 hunk 已收缩为 native PDF/HTML/PPTX/ODT、pypdf/PyMuPDF fallback、zip/文本上界、入站附件抽取与对应测试。接管时完整回归先暴露 `tests/tools/test_read_extract.py` 的陈旧断言（PDF/ODT 仍按 anydoc 缺失不可抽取），已改为 anydoc-only 与 native-overlap 分离；受影响文件 27 passed，完整动态 25 files **815 passed / 0 failed**。30 个活跃 PATCH 全部保留，无新增/归档；bundle/base/full-index、cached 正向、worktree 反向和 index-clean 闭环随 `--reconcile` 重新生成。
- 依赖：无 venv 重建；`python-socks==2.8.1` / `pypdf==6.14.2` / pytest 工具链 / `lark-oapi==1.6.8` 保持在位，无 `venv.stale.*` 或误建 `.venv` 残留。`npm audit fix` 仍非零并报告 4 high（brace-expansion、electron、undici，含下游 workspace 依赖），已归为 P2 上游 lock/range 阻挡，禁止 `--force`。Skills mirror 在测试后曾把源树 `__pycache__/` / `*.pyc` 同步成 `+70` 噪音；本轮已把字节码缓存加入 Step 4b 排除集合并清理误镜像缓存，后续以排除 metadata 与 bytecode 后的源码/runtime 内容一致为终态。
- 已知摩擦：本轮无 GitHub fetch retry；事务文件不存在时按接管规则只使用 no-network `--reconcile`，固定当前 HEAD `863e31318553`，未再次推进 upstream。脚本侧新增两项演进幂等修复：`_NPM_POLICY_ENV` 在 nounset + 空数组时使用安全展开，避免 npm<12 无 policy entry 时中断；Skills mirror 不再受测试/运行时 Python 字节码缓存影响，避免相同 SHA 因执行顺序不同产生 `+70` 假漂移。
- 配置漂移：`hermes doctor` 终态报告 Browser 2 high、Web 3 high 与 UI-TUI 1 high 三组 npm workspace/tooling advisory，均为 P2 上游阻挡且不影响飞书 gateway 主链路；未登录 provider / 未配置可选工具属 P3。Gateway planned restart 已完成并观察到 PID 替换，sandbox verifier 21 passed 绑定新 PID；owner Feishu DM 保持完整工具面，Feishu 群聊限制为结构化工具 + 只读 file/skill 工具。

**2026-08-07 逐补丁全量审计（升级期外，下次升级摘要重写时并入当周 README row 后删除本段）**：对 30 个活跃 PATCH 逐个核验上游吸收判断、hunk 冗余、哨兵判别力与验证覆盖，吸收判定全部维持（无新增归档；`PATCH-VERTEX-FALLBACK` 的上游 credential_pool 仍无 SA-file/project 语义，`PATCH-SKILL-CREATE-ROOT` 的 background-review guard 未扩大到 create）。修复三类问题：① **生产缺陷**——gateway 图片/视频路由 wrapper 的 `kind=` 接线断裂（TypeError 被吞、全部退化 text，视频补丁生产路径完全失效）、视频 buffer 缺每轮重置、群审批硬拦位于 yolo/allowlist/is_approved/smart 短路之后（配置漂移可绕过，现三入口早期硬地板 + ContextVar chat_type 防非规范 key fail-open）、vertex2/vertex-secondary 别名铸主账号凭据、backfill 启动节流在开机 30s 窗口内静默跳过、doctor 缺 vertex-fallback vendor-slug、zh-Hans 迁移文档残留 `HERMES_GATEWAY_TOKEN` 行；② **闸门判别力**——SKILL-CREATE-ROOT fail-open 析取、FTS5 `Ivendor` 无判别力、CAPABILITY-SCOPE 四个永真 grep、NORMAL-REPLY/MARKDOWN 补负向锚点、VIDEO 补接线锚点、SSRF/DOC-EXTRACTION/ADMISSION 补测试锚点、sandbox verifier 惰性导入计数收紧；③ **脚本演进**——fetch-retry 正则去死分支/限定 github/排除认证错误、8d 无 PID 时不再静默通过、210s 假 fallback 改 930、Step 2 显式 index-clean、skills 源目录缺失转事务失败、事务 self-test 补全字段与 symlink/篡改负例、npm allowlist 补 fsevents@2.3.2 并登记推导规则。受管文件 62 → 64（新增 zh-Hans 迁移文档、`test_image_input_routing_runtime.py`），补丁测试 25 → 26 文件，新写回归 12 条（含视频 buffer 每轮重置、doctor vertex-fallback slug、redactor DM 原样返回的补测），fetch-retry 正则另做 9 例隔离分类取证；终态 26 files **829 passed / 0 failed**。

> 仅保留最近一次升级摘要；历次升级的逐版本叙述见 `README.md` § 版本记录。

### [PATCH-SKILL-CREATE-ROOT] 自定义 skill 创建到用户目录

| 字段     | 内容                                                                    |
| -------- | ----------------------------------------------------------------------- |
| **文件** | `tools/skill_manager_tool.py`, `tests/tools/test_skill_manager_tool.py` |
| **状态** | 🟡 未上游合并（`_resolve_skill_dir()` 仍只用 `SKILLS_DIR / name`）      |

**问题**：`skill_manage(action='create')` 默认把新 skill 写到 `~/.hermes/skills/`（官方目录），而不是用户的 `my-skills/`。上游已支持 external skill 原地 edit/patch/delete，但 create 仍有测试要求写入官方 root，所以本地 patch 是有意定制。

**修复**：让 `_resolve_skill_dir()` 直接按配置顺序读取 `skills.external_dirs`，第一个非官方目录作为新 skill 的基准路径；即使目录尚不存在也由 create 建立，避免 discovery helper 只返回既存目录时错误回落官方 root。`_create_skill()` / `_delete_skill()` 同步适配，并加 `tests/tools/test_skill_manager_tool.py` 回归测试覆盖 external dir 路由、缺失目录创建与删除。

**验证**：Step 8b 用真实 Python import + 调用 `_resolve_skill_dir("_patch_test")`，**严格断言**返回路径 startswith `~/.hermes/my-skills/`（2026-08-07 审计修复：旧断言含 `or "/skills/_patch_test" not in result` 的 fail-open 分支，官方 skills root 改名时会把回落误报为 active，已删除）。行为回归 `test_create_uses_first_external_dir` + `test_delete_skill_created_in_external_dir`（2026-08-07 补齐 delete 侧缺口）。

**上游吸收判断**：仅当上游 create 路径已支持把首个 external skill root 作为默认写入目录，且对应创建/删除测试覆盖不存在目录时，才可移除本补丁；当前上游仍固定写入 `SKILLS_DIR / name`。**语义张力提示**（2026-08-03 审计）：post-26e0b1c 上游新增 `_background_review_write_guard()`，经 `is_external_skill_path()` 将 external_dirs 视为"externally owned、对自主 curation 只读"。该 guard 目前只作用于 background review fork，与本补丁的前台 create 不互斥；但上游把 external 当只读、本补丁把它当默认写入目标，方向相反——每轮升级须复核该 guard 的作用范围未扩大到 create 路径，若扩大则需与上游治理策略重新对齐而不是静默让 create 失败。

---

### [PATCH-NPM-DEPENDENCY-HYGIENE] npm 漏洞修复与 install-script policy

| 字段     | 内容                                                       |
| -------- | ---------------------------------------------------------- |
| **文件** | `hermes-update.sh` + `node_modules/`（gitignored）         |
| **状态** | 🟢 自动化（Step 3 scoped policy + Step 4 `npm audit fix`） |

**问题**：`hermes update` 用 `npm install --no-audit` 装 npm 依赖，不会自动修已知漏洞。例如 `basic-ftp ≤5.2.2` 的高危 DoS（GHSA-rp42-5vxx-qpwr），`hermes doctor` 会报 `Browser tools (agent-browser) has 1 npm vulnerability(ies)`。Node 26 / npm 12 进一步默认阻止未经审核的 dependency lifecycle scripts；本仓 update 的 root + ui-tui/web 安装会反复提示 `agent-browser@0.26.0`、`esbuild@0.28.1`、`fsevents@2.3.3`、`unicode-animations@1.0.3` 未被 `allowScripts` 覆盖。四个包当前产物实际可用，但每次升级重复告警；用 `dangerously-allow-all-scripts` 会把未来任意传递依赖也放行，不可接受。

**修复**：保留 Step 4 的 `npm audit fix --quiet`；同时在调用 `hermes update` 前为 npm ≥12 创建权限为 0600 的临时 global-config，仅写入已审核且**版本钉死**的 allow 条目——条目集合的推导规则是"`package-lock.json` 中 root+ui-tui/web 安装路径可达的全部 `hasInstallScript` 包"，不得凭记忆维护（2026-08-07 审计：root 的 fsevents 实为 2.3.2、tsx/vite 嵌套 2.3.3，allowlist 已同时钉两版；`electron`/`electron-winstaller`/`node-pty` 属 Desktop workspace、不在 `hermes update` 的安装路径内，明确排除不放行；本机 npm 11 时整个 policy 分支为待命状态，不影响行为），并通过 `NPM_CONFIG_GLOBALCONFIG` 只传给本轮 `hermes update` / audit，结束或异常退出均删除。不会修改 `~/.npmrc`，不会影响其他项目，也不会继承未来版本的脚本权限。`agent-browser` postinstall 只校验/准备对应平台 binary，`esbuild` 校验平台 binary，`fsevents` 提供 macOS native watcher，`unicode-animations` 在上游强制的 `CI=1` 环境中 no-op。audit 非零时完整输出进入升级日志，action 改为 `npm audit --json` 定性且明确禁止 `--force`；不再建议机械重跑刚刚失败的同一 fix 命令。上游 lock/range 暂无非破坏解且不影响飞书主链路时归为 P2，允许 warning + 落盘摘要收敛；命令未执行、产物缺失、影响飞书主链路或出现不可解释 drift 才是事务失败。

**验证**：以相同临时 policy 实跑 root `npm ci --workspaces=false` 与 ui-tui/web workspace `npm ci`，均无 `install scripts blocked` / `not covered by allowScripts`；随后 audit 恢复完整 workspace 产物，`agent-browser 0.26.0`、`esbuild 0.28.1`、`require("fsevents")`、`require("unicode-animations")` 全部可用，package.json / lockfile 无 tracked drift。隔离 fake 令 audit 非零时，日志必须保留原始诊断、action 只建议 `npm audit --json` 且包含 `do not use --force`，不得再次建议无条件 `npm audit fix`。

**上游吸收判断**：这是本地升级流程的依赖安全策略；只有上游升级器同时提供等价的 scoped install-script allowlist、自动清理临时配置和漏洞修复流程后，才可移除本补丁。

---

### [PATCH-REPLAY-BUNDLE-FULL-INDEX] replay bundle 使用稳定对象 ID

| 字段     | 内容                                         |
| -------- | -------------------------------------------- |
| **文件** | `hermes-update.sh`, `local-patches.diff`     |
| **状态** | 🟢 自动化（Step 2 / Step 8c `--full-index`） |

**问题**：`git diff` 默认按对象库规模自动决定 `index` 行的 SHA 缩写长度。bundle 生成后即使源码 hunk 完全不变，后续 fetch/apply 增加对象也可能让 live diff 从 9 位变成 10 位，导致 playbook 要求的逐字节 `cmp` 失败；只刷新一次默认缩写 bundle 仍会复发。

**修复**：Step 2 保存与 Step 8c 刷新统一使用 `git diff --full-index`，playbook 的 live-diff 核验也固定同一参数。bundle 的对象 ID 始终写完整 SHA，不再依赖仓库当前的自动缩写宽度。2026-08-06 收尾审计把原先仅由 playbook 人工执行的物理闭环下沉进两个 bundle 发布点：临时包必须通过 conflict-marker、index-clean（2026-08-07 起 Step 2 链内显式 `git diff --cached --quiet`，不再只依赖 preflight 继承）、cached 正向、worktree 反向检查，Step 8c 再与现场 full-index diff 逐字节比较；只有全绿才替换 canonical bundle/base。注意 8c 的 cmp 是"刷新输出 vs canonical 写入"的一致性闸，当 `_REFRESHED` 与 `PATCHED_FILES` 全等时两侧同源，不能替代 playbook Step 3 的独立现场复核。Step 2 另要求已有 bundle 时全部受管路径都有 live diff，禁止用中断产生的部分 overlay 覆盖完整旧包。

**验证**：`bash hermes-update.sh --print-patched-files` 输出必须与 bundle path 集合、live modified 集合一一相等；脚本 Step 2/8c 日志必须明确报告完整文件数，Step 8c 报 `refreshed and replay-verified`。独立复核时，`cmp -s <(git -C hermes-agent diff --full-index HEAD -- "${PATCHED_FILES[@]}") patches/local-patches.diff`、正向 cached、反向 worktree 与两次 index-clean check 必须同时通过。隔离构造 61/62 的部分 overlay 时 Step 2 必须在写 canonical bundle 前非零退出；Step 8c 的单个 zero-diff path 也必须阻断刷新并点名该路径。

**上游吸收判断**：这是外层 replay bundle 的本地持久化格式；只有未来迁移到不含动态缩写元数据的等价稳定格式，或不再维护本地 replay bundle 时，才可归档。

---

### [PATCH-UPDATE-GATE-EXIT-STATUS] 升级 gate 失败必须非零退出

| 字段     | 内容                                 |
| -------- | ------------------------------------ |
| **文件** | `hermes-update.sh`                   |
| **状态** | 🟢 自动化（Step 8 transaction gate） |

**问题**：旧脚本在 patch apply、Step 8b sentinel、冲突标记或意外空 diff 失败时只追加 warning/action 并跳过 Step 8c，没有设置 `FINAL_RC=1`。Step 8d 也只检查“存在任意 Gateway PID”：若 stop/start 没有真正替换旧进程，仍会把磁盘上已更新、运行时未加载的补丁误报为 active。即使后来补了 PID 替换门禁，macOS 的 `gateway stop` 仍会在短固定宽限后 SIGKILL，绕过 `agent.restart_drain_timeout`，本轮真实飞书任务因此被中断并进入恢复路径。结果既可能运行旧代码，也可能为了加载新代码破坏在途 turn，而脚本仍有机会把表面新 PID 当成功。可重入审计又发现四个同类缺口：把可执行脚本 `source` 后调用预算函数会直接启动整轮升级；3-way apply 失败后的单次批量 restore 会因任一上游已删除 path 令整个 pathspec 失败；3-way 成功隐式留下 staged index；以及接管“bundle 存在、worktree 已裸”的中断现场时没有重新武装 EXIT trap。更严重的是，Step 2 会把仅部分受管文件存在的 diff 当成新 canonical bundle，可能把完整本地不变量集合永久降级为残缺快照。

**修复**：Step 8c 总条件失败直接设置非零；条件通过后发现 conflict marker、部分或全部受管 diff 意外为空、byte/cached/reverse replay 任一失败也设置非零。Step 8d 仅在事务 `runtime_dirty=1` 时捕获旧 PID、走排空感知的 `hermes gateway restart`，等待预算优先取更新后运行时的 `_get_restart_exit_wait_budget()`（上游 `db3f7e4eb` 起原生覆盖 drain + after-turn 两段），旧运行时回落 `restart_drain_timeout`，再统一加 30 秒 supervisor 余量；只有命令成功且轮询到不同的新 PID 才确认 patched modules 已加载并清脏标记。旧 PID 未替换、Gateway 未恢复或 restart 非零都会设置 `FINAL_RC=1`，且不再建议 stop/start 强杀；`runtime_dirty=1` 但当前无 Gateway PID 时同样 `FINAL_RC=1` 并保留脏标记（2026-08-07 审计补：此前静默跳过整个 8d 块）；等待预算的解释器不可用 fallback 为 930s（本机 drain 900+30，2026-08-07 起替换与任何公式都不符的旧值 210）；HEAD/overlay 未变化的 reconcile 明确跳过重启。Step 7 补全脚本生成失败（sentinel 无法运行）同样设置非零。playbook Step 5b 再把同一规则设为所有后续代码/配置修复后的终态写屏障。脚本新增 side-effect-free `--print-restart-wait-seconds` / `--print-patched-files` / `--print-patched-tests` / `--transaction-status` 与隔离事务 self-test，并在任何状态变更前拒绝 bash/zsh source 及 dirty index；patch rollback 改为逐路径恢复，HEAD 已删除的受管文件只在 apply 确实把它放入 index 时才清除，遇到同名 untracked 文件 fail closed。自动 3-way 成功后立即清 staged index；EXIT trap 在裸树接管时保持武装，恢复失败会清理半合并态并保留 bundle。Step 2 对部分 overlay fail closed，只有完整且可正反向 replay 的临时包才允许替换 canonical bundle。具体 PATCH warning 继续保留用于定位，退出码成为可供自动化和下一轮 agent 信任的总闸门。

**验证**：静态检查 Step 8c 的总条件 `else`、conflict-marker、partial/empty `_REFRESHED` 和 replay-integrity 分支都包含 `FINAL_RC=1`；Step 8d 在 `runtime_dirty=1` 时必须调用 `hermes gateway restart`、不得调用 `gateway stop`，等待预算来自 `gw_restart_wait_seconds()`（native exit-wait budget 优先、drain 回落，+30s），并同时比较 `_GW_OLD_PID` / `_GW_NEW_PID`；`runtime_dirty=0` 必须跳过 PID churn。隔离执行脚本片段时，任一 gate 为 false、restart 非零、超时或返回相同 PID 都必须得到非零终态；全部 gate 为 true 且 PID 替换后才允许报告 patched modules active。所有只读入口只输出现场状态且不改变仓库/Gateway；bash/zsh source 和 dirty index 在任何 update mutation 前返回非零；逐路径 restore 的 present/deleted/untracked 三种路径分别恢复、删除 apply 产物、保护用户文件。另以临时 Git repo 覆盖完整 overlay、61/62 部分 overlay、裸树 + bundle、3-way staged/冲突清理及 bundle byte/cached/reverse gate。终态若发生 Step 8d 后的运行时修改，还必须按 playbook Step 5b 重启并让 verifier 绑定最终 PID。

**上游吸收判断**：这是外层升级 wrapper 的事务语义；只有 wrapper 被替换，且新入口能对 replay apply、全部 sentinel、冲突和空 bundle 提供等价非零总闸门时，才可归档。**排空子项已被上游替代并完成对接**（2026-08-03，本轮升级已跨过 `db3f7e4eb`）：`hermes gateway restart` 原生排空——SIGUSR1 先拒新 turn、按 `agent.restart_after_turn_timeout`（默认 21600s）等 in-flight 归零才 stop，`restart_drain_timeout` 收窄为 stop 内强杀预算。本地 `gw_restart_wait_seconds()` 经 `_get_restart_exit_wait_budget()` 读取原生合并预算（本轮实测 22545s = 900 + 21600 + 15 + 30），不再自建平行等待逻辑；本补丁剩余职责为退出码总闸门与 PID 替换硬校验。

---

### [PATCH-UPDATE-GIT-FETCH-RETRY] 升级 fetch 瞬时网络故障有界重试

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `hermes-update.sh`                                     |
| **状态** | 🟢 自动化（Step 3 早期 GitHub fetch 网络错误有界重试） |

**问题**：`hermes update` 在任何 checkout 或依赖变更前先 fetch `origin/main`，但本机到 GitHub 的直连与 LLM 专用代理都可能瞬时超时、TLS EOF 或 `SSL_ERROR_SYSCALL`。单次失败会让完整升级非零，即使下一次同一路径立即恢复；反过来无条件重跑整个 updater 又可能把认证、分叉、安装或迁移这类确定性错误重复三次，扩大副作用并掩盖根因。

**修复**：重试单元是首次 acquisition 的**裸 scoped fetch**（`git fetch --force origin main:refs/hermes-update/target`，`_acquire_upstream_target_with_retry`），不是整条 `hermes update`——官方 updater 在 PATCH-UPDATE-TRANSACTION-PIN 的固定 SHA 代理下运行、自身不做网络获取，因此无需也不得重试。仅当 fetch 日志命中 GitHub transport 特征（`Failed to connect to github.com`、`Could not resolve host: github.com`、同一行含 github.com 的 SSL/TLS EOF、Connection timed out/reset 等）且**不含**认证/权限特征（`Authentication failed`、`could not read Username`、`Permission denied (publickey)`、HTTP 401/403/407）时最多重试 3 次（2026-08-07 审计：删除只可能来自 Python CLI 的死分支 `Network error — cannot reach the remote repository`，并把裸 `Connection timed out|reset by peer` 收窄为须与 github.com 同行、新增认证负向前置过滤）。该失败点位于任何 checkout/venv/config 变更之前，动作可安全重入；一旦有效 SHA 写入专用 ref 即立刻固定、不再重试，后续错误只能进入 no-network reconcile。中间失败只显示简短 attempt 提示，远端 URL、Git config 和代理设置不在重试中持久修改。

**验证**：静态检查重试循环体只包含 `git fetch` + `rev-parse`、无 URL/config/代理写入；正则须含认证负向过滤（`! grep`）且不含上游 CLI 错误串。隔离验证可用 fake `git` 序列化：transport-fail → success 调用 2 次且 exit 0；连续 3 次 transport-fail 调用 3 次并保留非零；日志含 `Authentication failed` 时必须只调用 1 次。取得目标后再次执行必须走固定 SHA reconcile，fetch 计数不变（该场景已由 `--self-test-transaction` 的本地裸 remote 用例覆盖）。

**上游吸收判断**：当上游 `hermes update` 自身对 scoped Git fetch 提供等价的瞬时 transport 有界重试，且不会重试认证/安装/迁移错误时，可删除外层 Step 3 重试并归档。

---

### [PATCH-UPDATE-TRANSACTION-PIN] 单次升级固定 upstream 快照

| 字段     | 内容                                                                              |
| -------- | --------------------------------------------------------------------------------- |
| **文件** | `hermes-update.sh`, `.gitignore`, `hermes-update.md`, `README.md`, macOS 运维文档 |
| **状态** | 🟢 自动化（显式 `--update` 获取一次；默认/`--reconcile` 固定 SHA、no-network）    |

**问题**：旧 playbook 同时要求 Step 1 先 `git fetch origin main`、Step 2 再执行自带 fetch 的 `hermes update`，又规定任何 patch/gate/脚本修复后必须重跑完整 updater。上游 main 持续前进时，同一次审计会依次纳入新的 commit，既不断改变 patch 基线，也触发重复依赖安装和 Gateway 重启；所谓“幂等复跑”实际变成一串新升级，无法定义本轮完成。`hermes --version` 还会隐式执行 update-check/fetch，使只读预检也可能越过获取边界。

**修复**：把官方获取和本地收敛拆为两个脚本模式。只有显式 `--update` 能在没有未完成事务时执行一次 `git fetch --force origin main:refs/hermes-update/target`，立即把专用 ref 固定为 `TARGET_SHA`；随后官方 updater 仍负责 merge、依赖、迁移、skills 和原生 restart，但通过临时 Git 代理执行——其内置 `fetch origin main` 成功 no-op，命令参数中的 `origin/main` 被替换为固定 SHA，因此不会发生第二次网络获取或目标竞态。默认无参数和 `--reconcile` 只校验/本地 fast-forward 到固定 `TARGET_SHA`，绝不做网络探测、fetch 或 pull。`.hermes-update-transaction` 以原子写 + `0600` 保存阶段、`old_sha`、`origin_before`、`target_sha` 和 `runtime_dirty`，逐字段验证且永不 source；失败/中断保留，完整 exit 0 才删除状态与专用 ref。若进程在 fetch 更新 ref 后、状态发布前退出，下一轮从专用 ref 重建目标；已有未完成事务时，即使误传 `--update` 也只能接管已有 SHA。无变化 reconcile 跳过 Gateway restart；HEAD/overlay 改变或失败事务留下运行态脏证据时才执行排空重载。版本摘要直接读取 checkout 的 `hermes_cli/__init__.py`，消除 `hermes --version` 的隐藏 fetch。

**验证**：`bash -n hermes-update.sh` 与 `bash hermes-update.sh --self-test-transaction` 必须通过；self-test 在临时文件 round-trip **全部 7 个字段**（phase/old_sha/origin_before/target_sha/started_at/runtime_dirty + version 经 `_load_transaction` 校验）并断言权限 `0600`，另含两个 fail-closed 负例——symlink 状态文件与追加多余行的篡改文件都必须被 `_load_transaction` 拒绝（2026-08-07 补齐，此前仅断言 3 字段）；还用 fake real-git 证明 wrapper 的 fetch 不下传、`HEAD..origin/main` 被改写为固定 SHA。补充边界：pinned wrapper 只对精确的 `fetch origin main` no-op，带 `--depth` 的 fetch 或 fork 同步的 `fetch upstream main` 会命中 exit 97 阻断分支（fail-closed 而非静默放网络），本机 origin 为官方仓库、fork 路径不可达。`--transaction-status` 无状态输出 `none`，有状态只打印经校验字段。静态检查默认/`--reconcile` 分支不调用 acquisition fetch、curl 或 `hermes --version`；只有 `_ACQUIRE_UPSTREAM=true` 能写专用 ref。隔离 fake 覆盖：首次 `--update` 固定目标、失败保留状态、相同事务再次 `--update` 不增加 fetch 计数、`--reconcile` 在 remote-tracking ref 前进后仍保持原目标、exit 0 删除状态/ref、非法/符号链接状态 fail closed。现场 no-change reconcile 必须明确输出 `no fetch/pull` 与 restart skipped，且 HEAD/PID 不变。

**上游吸收判断**：这是外层升级事务边界。只有未来官方 updater/wrapper 原生支持“单次获取后返回不可变 target token、失败跨进程恢复、后续 no-network reconcile、成功清理事务、无变化不重启”，并且 playbook 不再需要本地状态层时，才可归档。

---

### [PATCH-SKILLS-MIRROR-METADATA] Skills 镜像保留本地 runtime 状态

| 字段     | 内容                                    |
| -------- | --------------------------------------- |
| **文件** | `hermes-update.sh`, `~/.hermes/skills/` |
| **状态** | 🟢 自动化（Step 4b rsync gate）         |

**问题**：Step 4b 原先用裸 `rsync -a --delete` 把上游 skills 镜像到运行目录，会删除源树中不存在的 `.bundled_manifest`、`.curator_state`、`.usage.json` / `.usage.json.lock`、`.hub` 和 `.archive` 等本地运行态。前者被迫反复重建，`.curator_state` 会丢失 curator 的 pause/run count/last-run 状态，`.usage.json` 会丢失每个 skill 的 usage、pin、sync 和 curator 生命周期记录；同时 `|| true` 吞掉 rsync 非零，复制失败也可能被显示成“已同步”。测试或运行时在 `hermes-agent/skills` 下生成的 `__pycache__/` / `*.pyc` 也会被误当作上游内容镜像到 runtime skills，导致同一 SHA 因执行顺序不同出现 `+70` 这类假漂移。

**修复**：从 delete 集合排除根级 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.curator_backups` / `.curator_suppressed` / `.hub` / `.archive`，并排除 `__pycache__/` / `*.pyc`，只镜像上游拥有的 skill 内容；显式捕获 rsync 退出码，失败时记录输出、设置 `FINAL_RC=1`，成功时继续报告 `+/~/-` 并确认 runtime state 与可再生 bytecode cache 保留/排除策略生效；bundled skills 源目录整体缺失同样 `FINAL_RC=1`（2026-08-07 审计补：属"命令未执行/产物缺失"级事务失败，此前仅 warn 且会连带静默跳过 Step 8c 的 llm-wiki 再播种）。（2026-08-06 并入）成功路径把 `--itemize-changes` 中每条新文件 `>f+++` 与删除 `*deleting` 分别以 `+ added:` / `- deleted:` 留存到升级日志：此前同日两轮各出现 `-94`、终态同 SHA 复跑又出现 `+70` 而无路径记录，事后无法判定具体变更集合；双向清单让下一位无状态 AI 能把批量消失/恢复与同期进程日志关联。

**验证**：在隔离临时目录预置完整 runtime state、一个待新增文件、一个上游孤儿和 `__pycache__` / `.pyc` 缓存，执行脚本同款 rsync 后必须保留 runtime state、复制新增项、删除孤儿、不复制 bytecode cache 并保持内容不变；把源目录改为不可读或传入无效 rsync 参数时必须走非零 gate。现场 dry-run 不得再出现删除 `.bundled_manifest` / `.curator_state` / `.usage.json` / `.usage.json.lock` / `.hub` / `.archive` 等本地状态，也不得把 `__pycache__` / `.pyc` 计入 `+/~/-`。清单分支以模拟 `>f+++` / `*deleting` 混合输出隔离验证：`_ADDED` / `_DELETED` 计数与逐行 `+ added:` / `- deleted:` 输出一致，updated/目录行不误报。

**上游吸收判断**：当上游同步器原生提供“官方 skill 内容镜像 + 本地 manifest/curator/usage/hub state 保留 + bytecode cache 排除 + 失败非零”的等价行为，外层不再需要 Step 4b wrapper 时可归档。

---

### [PATCH-FEISHU-SOCKS-DEPENDENCY] Feishu 代理依赖声明

| 字段     | 内容                                                                                                                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock`（feishu extra 的 requires-dist 行，与 PATCH-DOCUMENT-EXTRACTION 共享同一批 hunk） |
| **状态** | 🟡 未上游合并                                                                                                                       |

**问题**：`feishu` optional extra 和 `tools/lazy_deps.py` 的 `platform.feishu` 上游当前都只声明 `lark-oapi==1.6.8` + `qrcode==7.4.2`。代理网络下 `lark-oapi` 的 WebSocket 连接需要 SOCKS 支持，缺 `python-socks` 时 gateway 起来后报 `connecting through a SOCKS proxy requires python-socks` 并反复重连失败。

**修复**：在 `pyproject.toml` 的 `feishu` extra 和 `tools/lazy_deps.py` 的 `LAZY_DEPS["platform.feishu"]` 都加 `"python-socks==2.8.1"`。手动 `.[feishu]`、`.[all,feishu]`、和上游 lazy install 三条路径都能拿到 SOCKS。版本钉死风格与上游 2026-05-14 起 messaging extras `==X.Y.Z` 约定一致（避免 `>=2.0,<3` 被 `uv lock --check` 报漂移）。

**验证**：Step 8b grep `python-socks` 在 `pyproject.toml` 和 `tools/lazy_deps.py` 都存在。

**上游吸收判断**：当上游 `feishu` extra 与 `LAZY_DEPS["platform.feishu"]` 都显式声明兼容的 SOCKS 依赖，并通过代理连接回归后，才可移除本补丁；任一路径缺失都必须保留。

---

### [PATCH-OPENCLAW-TOKEN-MIGRATION] OpenClaw 迁移不写废弃 gateway token

| 字段     | 内容                                                                                                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`, `website/docs/guides/migrate-from-openclaw.md`, `website/i18n/zh-Hans/.../guides/migrate-from-openclaw.md` |
| **状态** | 🟡 未上游合并（上游仍写 `HERMES_GATEWAY_TOKEN`）                                                                                                                                         |

**问题**：旧 OpenClaw 的 `gateway.auth.token` 会被迁移到 `.env` 的 `HERMES_GATEWAY_TOKEN`，但当前 Hermes gateway 运行时不读这个变量，保留只会制造无效敏感字段和配置误导。

**修复**：迁移脚本仍归档完整 gateway 配置，但不再把 `gateway.auth.token` 写进 `.env`；英文迁移文档与 zh-Hans 翻译（2026-08-07 审计补齐——此前中文文档仍保留该映射行、且全树仅剩这一处引用）同步删除该字段映射行。

**验证**：Step 8b grep 确认迁移脚本、英文文档与 zh-Hans 文档都不再出现 `HERMES_GATEWAY_TOKEN` / `gateway.auth.token` / `Gateway 认证 token`。

**上游吸收判断**：当上游迁移脚本不再写入废弃的 `HERMES_GATEWAY_TOKEN`，且迁移文档同步移除该映射后，才可移除本补丁；当前上游两处仍未吸收。

---

### [PATCH-FEISHU-GROUP-ADMISSION] 群聊触发、上下文与当前发言人完整性

| 字段     | 内容                                                                                                                                                                                                                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `gateway/authz_mixin.py`, `gateway/run.py`（仅上游 `[New message]` 回归锚点，无本地 hunk）, `gateway/session.py`, `skills/research/llm-wiki/SKILL.md` 及对应 gateway 测试/文档 |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                              |

**问题**：群聊需要同时支持 `@bot` 与 `@配置本人账号` 触发、近期群消息回填和纯 @ 意图推断；共享 session 还必须防止 owner profile、引用内容、历史末位发言人或跨发送者 debounce 被误认成当前提问者。群授权也不能借通配符放开 DM。原纯 @ 分支硬编码排除 `p2p`，导致主会话里回复一条合并转发后只 @Bot 会在剥离 mention 后成为空文本并被静默丢弃。

**修复**：实现 assistant-user/configured-human 两类触发与身份说明、群历史回填、默认关闭且可配置的 `bare_mention_intent`、`FEISHU_GROUP_ALLOWED_CHATS` 群授权；把 bot mention 设为最高触发优先级，批处理合并判定纳入发送者（`_text_batch_is_compatible` 校验 user_id/user_id_alt/user_name；`_text_batch_key` 本身与上游一致），并在 system prompt 标注 current author（**user-turn 侧的 sender 前缀与 `[New message]` 拼接已被上游吸收**——d1afa160 起 `_prepare_inbound_message_text` 原生对 shared multi-user 会话做 `[sender]` 前缀与 channel-context 拼接，本地不再携带该 hunk，system prompt 的 current-author 块仍为本地）。开启 `bare_mention_intent` 后，群聊和 DM 中明确提及 bot 自身的纯 @ 都进入意图推断；引用消息时以引用内容为主题且只读取一次，未引用时使用既有会话历史，空文本但未 @Bot 仍丢弃。技术问题提示显式要求先读 `llm-wiki`，所有 wiki 文件调用必须携带 `~/.hermes/wiki` 路径，禁止用 terminal 探测；bundled skill 同步相同规则。

**验证**：Step 8b 独立 gate 检查 trigger/settings/history/bare-mention/wiki sentinels、DM 纯 @ 回归、group allowlist（含 `test_feishu_group_allowed_chats_wildcard_authorizes_groups_only`——wildcard 不放开 DM 的安全断言，2026-08-07 起入 gate）、current-author system prompt（本地）与 `[New message]` 上游 body-prefix 回归锚点、bot 优先级和跨发送者不合并测试。定向测试覆盖未 @ 静默、第三方 @本人代答、本人 @bot 不自我介绍、群聊与 DM 的纯 @ 引用/历史意图、DM 不被群 allowlist 放开，以及历史末位发言人与当前提问者不同时仍正确锚定当前作者。（2026-08-03 修正：旧哨兵 `_with_current_author_prefix` 在 v0.19.1 冲突解决轮已被重构移除，gate grep 一直误报 inactive；现改为真实锚点。）

**上游吸收判断**：上游同时具备等价的 Feishu 多触发 admission、群历史/纯 @ 意图、按发送者隔离的 batching 和多用户 current-author 契约后可归档；工具权限隔离不属于本补丁。body-prefix 子项已吸收（见修复段）；system prompt current-author 块与 Feishu admission 机制仍为本地。

---

### [PATCH-FEISHU-MISSED-EVENT-BACKFILL] Feishu 断线/重连漏消息补偿

| 字段     | 内容                                                                                                                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/config.py`, `tests/gateway/test_feishu.py`, `website/docs/user-guide/messaging/feishu.md`, `website/docs/user-guide/configuration.md`（本机 `config.yaml` 启用 6h 窗口与 60s/30s/10s WebSocket 恢复参数） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                             |

**问题**：Feishu `history_backfill` 只在 Hermes 已收到一条触发消息后补上下文，不能主动发现断网、睡眠或 stale WebSocket 期间漏掉的 `@Hermes` 触发事件。SDK 内部自动重连成功也不会通知 adapter 做补偿扫描，导致漏消息可能等 Feishu 服务端迟迟推送旧事件后才被回复；用户手动 quote 原消息再 @Hermes 触发回答后，旧事件晚到又会让 Hermes 重复回答同一问题。

**修复**：新增 `missed_event_backfill` 独立恢复路径：启动、gateway reconnect 和 Lark SDK `on_reconnected` 后，在主 asyncio loop 上调度一次有界扫描。扫描目标只来自 `missed_event_backfill_chats`、Feishu home channel、显式 `group_rules` 以及 `~/.hermes/groups.yaml`，不把通配符 `group_rules: "*"` 当作租户枚举来源；每个目标 chat 通过 `im.v1.message.list` 拉取最近窗口，按时间正序只重放未见且通过原 `_admit()` 的消息，随后进入同一 `_handle_message_event_data()` / `_process_inbound_message()` 管道。手动 quote/reply 已触发的消息在 dispatch 后把 `parent_id` / `upper_message_id` / `root_id` 标记为已覆盖，使后续 delayed push 或恢复扫描命中原消息 ID 时被 dedup 跳过。配置桥接同时支持 `missed_event_backfill*` 和 `ws_reconnect_*` / `ws_ping_*` 顶层 `feishu:` 键。已知并存（有意不动）：上游 `_fetch_last_message_in_thread` 仍有函数内局部 `ListMessageRequest` 导入，会遮蔽本补丁的懒加载全局——行为无差异，删除它要为纯整洁改写上游函数、扩大 diff 面，留待上游自行收敛。

**验证**：Step 8b 单独检查 missed-event runner、per-chat backfill、SDK reconnected hook、quote-covered dedup helper、`ListMessageRequest is not None` fallback、config 桥接、用户文档和三条回归测试。新增测试覆盖：已知群里的未见 @ 消息会在 backfill 中触发一次 dispatch；quote+@ 覆盖的 parent 后续 backfill 不再 dispatch；SDK `on_reconnected` hook 保留原 callback 并调度 backfill。规范 runner 结果：`tests/gateway/test_feishu.py` 132 passed / 0 failed，`tests/gateway/test_config.py` 57 passed / 0 failed（2026-08-05）。

**上游吸收判断**：上游 Feishu adapter 若提供等价的启动/重连后 missed trigger replay、SDK 内部 reconnect 通知接线、已 quote 触发回答的原消息 ID 覆盖去重、以及受控目标 chat 发现策略，可归档本补丁；单纯加强 WebSocket ping/reconnect 或上下文 `history_backfill` 不构成吸收。

---

### [PATCH-FEISHU-GROUP-SCOPE] 群聊独立 capability namespace

| 字段     | 内容                                                                                                                                                                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session_context.py`, `gateway/run.py`, `gateway/slash_commands.py`, `hermes_cli/tools_config.py`, `tests/gateway/test_session_env.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_verbose_command.py`, `tests/hermes_cli/test_tools_config.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                 |

**问题**：Feishu DM 与群聊原本都只解析 `platform=feishu`，无法对同一 bot 的 owner DM 和共享群配置不同 toolsets/skills。初版补丁虽然新增了 source-aware helper，并把 session context 正确写成 `feishu_group`，但主 `_run_agent_inner`、busy ack、最终 reasoning/footer、proxy streaming、background task 和 slash commands 仍直接用 `source.platform` / `event.source.platform` 取 key。结果静态配置和 sandbox verifier 都显示群策略正确，真实群 Agent 却拿到 DM 的 terminal/drive 工具面与 `tool_progress: new`：工具调用链被发送到群里，受控文档入口 `feishu_doc_manage` 没有进入 Agent schema，模型转而调用 `terminal` / `feishu_drive_add_comment` 再被 sandbox 拦截；群内 `/verbose` 等命令还可能读写 DM 配置。

**修复**：新增 `HERMES_SESSION_PLATFORM_CONFIG_KEY`；Feishu group/forum/channel/thread 映射到 `feishu_group`，DM 仍为 `feishu`。所有按具体会话解析 display、toolsets、busy ack、reasoning/footer、proxy streaming、background task 和 slash-command 配置的运行路径统一调用 `_platform_config_key_for_source()`；仅 helper 内部允许退回通用 `_platform_config_key(source.platform)`。平台工具解析和保存逻辑识别该独立 key；群工具面不被默认能力补宽的机制是 `platform_toolset_options.<key>.recover_platform_tools: false` 的显式短路（`feishu_group` 不在 `PLATFORMS` 注册表内，靠该开关而非独立分支阻断 native recovery）。

**验证**：Step 8b 单独检查 session context key、`return "feishu_group"`、`run.py` / `slash_commands.py` 所有 source/event consumer 不再绕过 source-aware helper、tool recovery 开关，以及 `test_set_session_env_sets_feishu_group_config_key` / `test_get_platform_tools_feishu_group_uses_independent_config`。`test_feishu_group_runtime_scope_hides_progress_and_uses_group_tools` 穿过真实 `_run_agent` 边界作 DM 正例和两个群负例：DM 仍收到 `new` 工具卡并包含 `terminal`，群聊零 send/edit 且 Agent toolsets 包含承载 `feishu_doc_manage` 的 `sandbox_group`、不含 `terminal`。`test_feishu_group_updates_group_scope_without_mutating_dm` 从 `/verbose` 写回边界证明群配置独立更新、DM 值保持不变。

**上游吸收判断**：上游提供等价的 per-chat-type capability namespace，且 Feishu DM/group 可以独立解析工具配置时可归档。

---

### [PATCH-PLATFORM-CAPABILITY-SCOPE] 平台级 skill allowlist 与只读工具集

| 字段     | 内容                                                                                                       |
| -------- | ---------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/skill_utils.py`, `agent/prompt_builder.py`, `tools/skills_tool.py`, `toolsets.py` 及对应 tests/docs |
| **状态** | 🟡 未上游合并                                                                                              |

**问题**：`skills.disabled` 不能表达“某平台只允许指定 skill”；完整 `skills` toolset 又同时暴露 `skill_manage`。文件工具也缺少只读组合，平台配置容易无意带入写能力。

**修复**：新增 `skills.platform_allowed.<platform>`，并让 prompt、list/view 和 config-var discovery 共用同一解析；增加 `skills_readonly`（list/view）与 `file_readonly`（read/search）内部工具集。分类 skill 的规范名按短名匹配 allowlist，避免 `productivity:feishu-docs` 被错误拒绝。两个通配语义随实现存在并有测试覆盖：`platform_allowed: ["*"]` 为显式 allow-all 逃生口，`platform_disabled: ["*"]` 为全禁（`test_platform_disabled_wildcard`）；本机配置均未使用。

**验证**：Step 8b 独立检查 `get_allowed_skill_names` 的三个调用面、qualified-name 回归，并用 venv python **精确断言**两个只读工具集的成员列表（`skills_readonly == [skills_list, skill_view]`、`file_readonly == [read_file, search_files]`；2026-08-07 审计修复：旧 gate 对四个工具名的裸 grep 全部能被上游既有 `skills`/`file` 工具集满足，永远不会失败）；测试覆盖空 allowlist、命名 allowlist、`feishu_group` 独立配置及只读工具集不被错误过滤。外层 `plugins/sandbox/verify.sh` 另做群工具面的成员/去写断言。

**上游吸收判断**：上游原生提供平台级 skill allowlist 和不含 manage/write 的只读 skill/file toolsets 后可归档。

---

### [PATCH-FEISHU-GROUP-APPROVAL] 群聊危险命令审批不可升级权限

| 字段     | 内容                                                   |
| -------- | ------------------------------------------------------ |
| **文件** | `tools/approval.py`, `tests/tools/test_approval.py`    |
| **状态** | 🟡 未上游合并；`PATCH-FEISHU-GROUP-SANDBOX` 的纵深防线 |

**问题**：旧群聊 terminal 路径曾进入 dangerous-command approval，群成员点击卡片后命令继续执行。即使当前群聊不再暴露 terminal，审批层若不区分 chat type，未来工具配置漂移仍可能重新形成提权路径。

**修复**：`_is_restricted_feishu_approval_session()` 对 Feishu group/forum/channel/thread 直接返回 `BLOCKED`，不通知、不入 pending queue、不发送审批卡；owner DM 继续走 manual approval。chat type 优先读 `HERMES_SESSION_CHAT_TYPE` ContextVar、仅在为空时回退解析 session key，使 cron/API/wake 等非规范 key 不会 fail-open。**2026-08-07 审计重排硬拦顺序**：此前硬拦位于 Phase 3，`is_approved()` 进程全局集（owner DM "always" 审批 + `command_allowlist`）、yolo/mode=off 与 smart approval 均在其前短路，配置漂移即可绕过；现改为三层——①主入口与 legacy 入口在 yolo/allowlist **之前**加早期硬地板（cheap `detect_dangerous_command`，危险即 `restricted_chat`）；②tirith 告警在受限会话不消费 `is_approved` 短路、smart approval 对受限会话整体跳过，使告警必达 Phase 3 既有硬拦；③`check_execute_code_guard` 第三入口同样无条件硬拦（整脚本审批卡同为提权面）。当前配置（manual + 空 allowlist）此前恰好兜住，现在不再依赖配置。

**验证**：Step 8b 检查 hard-block helper、`restricted_chat` 行为串、`hard floor` 注释锚点及五条测试：`test_feishu_group_dangerous_command_does_not_send_approval_card`（零通知零 queue）、`test_feishu_group_block_precedes_allowlist_and_prior_approvals`（approve_permanent + allowlist 双短路均不放行）、`test_feishu_group_block_skips_smart_approval`（smart 模式不询问 aux LLM 直接 BLOCKED）、`test_feishu_group_block_via_legacy_check_dangerous_command`、`test_feishu_group_execute_code_guard_blocked`、`test_feishu_group_chat_type_from_context_when_key_not_canonical`（非规范 key 走 ContextVar 不 fail-open）；Step 8e 再验证 owner DM 仍保留完整工具与人工审批策略。

**上游吸收判断**：上游 approval 原生按 chat type 禁止共享群创建或批准危险操作、同时不影响 owner DM 时可归档。

---

### [PATCH-FEISHU-NORMAL-REPLY] 回复始终留在普通聊天消息流

| 字段     | 内容                                                                  |
| -------- | --------------------------------------------------------------------- |
| **文件** | `plugins/platforms/feishu/adapter.py`, `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                                                         |

**问题**：`root_id`/generic `metadata.thread_id` 会让普通引用回复被 Feishu 当作 thread/topic 投递，甚至在无有效引用锚点时把 thread id 当 receive id。

**修复**：发送出口固定 `reply_in_thread=False`；引用目标只取显式 `reply_to`/`reply_to_message_id`；create-message 分支忽略 generic thread metadata，缺引用锚点时回退主聊天普通消息。

**验证**：Step 8b 单独检查 `reply_in_thread = False`、忽略 thread metadata 的实现和回归测试，并带两条**负向锚点**（`! grep 'reply_in_thread = bool'`、`! grep '_build_create_message_request("thread_id"'`，2026-08-07 起）——正向锚点只证明本地行存在，无法发现 3-way 把上游 metadata-driven lane 在注释下方重新合入的对撞形态；覆盖普通引用、文档回复和无引用锚点三条路径。

**上游吸收判断**：上游提供明确的普通引用/话题开关并保证 generic thread metadata 不改变 Feishu 投递 lane 后可归档。**对撞警示**（2026-08-03 审计）：post-26e0b1c 上游在同一 send/reply-body 区域走**相反语义**——`reply_in_thread = bool(metadata.thread_id)`（metadata 驱动投递 lane），与本补丁"固定 `reply_in_thread=False`、忽略 generic thread metadata"直接冲突。下次升级该区域的 3-way 结果**不可信任自动合并**：必须人工按本补丁不变量重解（普通引用回复永不进 thread lane），并以现有回归测试三条路径复验后才能刷新 bundle。

---

### [PATCH-FEISHU-FINAL-ONLY] Feishu 默认只展示最终回复

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                         |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/display_config.py`, `tests/gateway/test_display_config.py`, `tests/gateway/test_run_progress_topics.py`, `tests/gateway/test_verbose_command.py`（本机 `config.yaml` 按 DM/group 显式覆盖）。运行 consumer 的 source-aware 解析 hunk（`gateway/run.py` / `gateway/slash_commands.py`）归属 `PATCH-FEISHU-GROUP-SCOPE`，此处仅为依赖 |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                                                                                                                                |

**问题**：Feishu 默认 tool progress、streaming 和 interim bubbles 会把草稿、工具进度或思考式中间态暴露到群聊；这与消息是否进入 thread 无关，应独立控制。只验证 `display.platforms.feishu_group` 的静态值并不足够：运行 consumer 若错误使用 `feishu` key，群聊仍会继承 owner DM 的 `tool_progress: new`。

**修复**：Feishu 内置 display tier 默认关闭 tool progress、streaming、interim assistant messages、long-running notification 和 busy detail。当前本机有意让主会话 DM 使用 `tool_progress: new`（独立工具进度卡），群聊保持 `tool_progress: false`；两者都关闭 streaming/interim/thinking progress，最终 assistant 回复只走最终内容。所有运行时 display consumer 通过 `PATCH-FEISHU-GROUP-SCOPE` 的 source-aware key 解析，避免静态策略与实际发送分叉。若 provider 把 thought 错塞进 `message.content`，由 `PATCH-VERTEX-HIDDEN-THOUGHTS` 在请求侧抑制，不能误认为 display 层会自动识别并清洗正文。

**验证**：Step 8b 单独检查 Feishu display defaults 与 `test_feishu_defaults_to_final_only`；同文件另有两条本补丁携带的守护测试 `test_medium_tier_platforms` / `test_slack_defaults_tool_progress_off`（锁定其他平台的上游默认不被本地 tier 改动波及，2026-08-07 归属登记）；本机配置检查主会话 `tool_progress: new`、群聊 `tool_progress: false`，且两者的 `thinking_progress` / `interim_assistant_messages` 均为 false。真实 `_run_agent` 边界测试另证明 DM 会发工具进度，而两个 Feishu group 会话即使同用一个 bot 也不会产生任何 progress send/edit；`/verbose` 测试证明群聊命令只读写 `feishu_group`。

**上游吸收判断**：上游 Feishu 默认 final-only，或提供等价且默认安全的 display profile 后可归档。

---

### [PATCH-LOCAL-PROFILES] 本地人物/群画像与群聊输出保密

| 字段     | 内容                                                                                                                                                                 |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/session.py`, `gateway/run.py`, `gateway/stream_consumer.py`, `plugins/platforms/feishu/adapter.py` 及对应测试；`people.yaml` / `groups.yaml` 为配置仓库数据 |
| **状态** | 🟡 本地个性化功能，不预期上游直接吸收                                                                                                                                |

**问题**：模型只凭 open_id/显示名无法按用户维护的人物背景和群人设调整表达；画像私有字段、数据来源和 `people.yaml` 文件名又绝不能在群聊泄露。工具受限时也必须披露证据边界，不能把未验证内容包装成结论。

**修复**：按 mtime 热加载 people/group profile；人物画像采用公开白名单：只有 `name`、`role`、`department`、`address` 可对外，所有已知私密字段和未来手工新增字段都进入模型可读的保密块并纳入确定性出站过滤；open_id/user_id/union_id/id 和未与公开字段重合的 aliases 只用于匹配，同样不得输出。群画像只控制风格、介绍、能力口径和提示性服务时间。所有 group/channel 无条件注入来源保密和工具限制声明；非 DM 的最终、流式、fallback、临时 assistant 消息、流式 TTS 和 `/background` 完成/失败通知等可见/可听文本统一经过 `redact_private_person_profile_text`/`text_filter`，后台完成通知不回显 prompt；redactor 自身内置 DM 早退（2026-08-07 加固：所有调用方虽已在外部按 chat_type 分流，但未来新增调用方漏掉分流时按构造即安全——群不漏、DM 不被误遮；`test_private_profile_redactor_leaves_dm_text_untouched` 锁定 DM 原样返回）。loader 缺文件或坏 YAML 时安全降级，DM 不注入群画像规则。`people.yaml` 与 `groups.yaml` 保持普通可编辑文件，owner 始终拥有读写权限；两个热加载器和升级 Step 8b 都会将其收敛并验证为 `0600`，因此同账号 VSCode 可照常编辑，而其他本机账号不可读。

聊天历史（群聊回填与合并转发展开共用的 `_history_sender_label`）此前只渲染 `ou_xxx` 裸 id 或缓存显示名，缓存未命中时模型无法分辨发言人。现复用同一份 `_lookup_person` 索引（open_id/user_id/union_id/name/aliases）把发送者 join 到 people.yaml：命中则用画像 `name`，并只追加公开面中的 `role`/`department` 作为限定语。历史会被回显进群聊回复，因此限定语字段是白名单而非黑名单，公开四项以外（含 `employee_no`、保密备注等）一律不进入 label；join 失败或 people.yaml 缺失时安全降级为原有 id/显示名。

**验证**：Step 8b 检查 profile loaders/lookups、公开 `address`、未知字段 private-by-default、技术 ID/未公开别名过滤、来源保密常量、私有值/文件名字面量 redactor、stream/TTS filter、后台/临时消息出站测试、后台不回显 prompt 断言，以及 `people.yaml` / `groups.yaml` 的 owner-rw `0600` 权限与热加载自愈测试；另加历史发送者 join 的 `_history_sender_person`/`_history_person_qualifier` 与两个回归测试（公开字段命中 + 保密字段不泄露 / lookup 抛错时降级）。验证只归属于画像与输出过滤；旧 terminal/script-root allowlist 已被删除，不再作为本补丁的实现或测试。

**上游吸收判断**：若上游提供等价的本地 per-sender/per-group profile 注入与全出站路径隐私过滤，可重新评估；否则保持本地补丁。

---

### [PATCH-FEISHU-RESOURCE-ACCESS] 附件回看、Drive 链接与 tenant 文档读取

| 字段     | 内容                                                                                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `plugins/platforms/feishu/adapter.py`, `gateway/run.py`, `gateway/platforms/base.py`, `tools/feishu_doc_tool.py`, `tests/gateway/test_feishu.py`, `tests/tools/test_feishu_tools.py` |
| **状态** | 🟡 未上游合并                                                                                                                                                                        |

**问题**：群聊媒体与 @mention 常分成两条消息，引用里的 `/file/<token>` 也不是 IM 附件；普通 gateway 工具调用没有 comment thread-local client 时，tenant 凭据明明存在却无法读取飞书文档。旧附件补丁还只允许群 `trigger_kind == bot` 且非 command 的回填：DM 显式引用、群 `@配置本人账号`、Feishu command composer 遗留的单独 `/` 均会只留下缓存路径而不把图片/视频交给模型；显式再次引用同一资源又会被本应只约束滑动窗口的去重缓存错误抑制。另外，被引用的合并转发消息在 webhook payload 里不带子消息体，上游只把它归一化成 `[Merged forward message]` 占位符，因此群里"引用合并记录 + @Bot"只能看到占位符，而私聊直发同一条合并记录却能正常展开。初次补上展开后仍有第二层截断：Gateway 对所有 `reply_to_text` 硬编码 `[:500]`，真实卡片的 12 条子消息虽已全部从 Feishu API 取回，送模时却在第 6 条中间静默截断，导致机器人错误声称后续内容不存在。

**修复**：将显式引用恢复与群聊同发送者滑动窗口回看拆开：DM 和已准入的 `bot`/`assistant_user` 群触发可恢复引用附件（整条恢复链以 `history_backfill: true` 为总开关且触发消息自身不带媒体时才扫描——本机已启用该开关；上游默认 false 时显式引用恢复不生效，属有意搭载而非"无条件始终"），显式重复引用不受窗口去重限制；窗口扫描仍仅限群聊并保持有界去重。把单独 `/` 归一为无实际命令的 bare mention，使引用主题进入同一意图链。扫描正文/引用中最多三个 Drive file token，以 tenant 身份下载并保留 MIME/文件名（`_MAX_DRIVE_LINK_BYTES` 100 MB 上限为下载完成后的事后校验、非流式截断——tenant 侧文件由管理员控制，暂不做流式守卫，留观）；普通网页链接原文保留。`feishu_doc_read` 缺 comment client 时从 env/`.env` 构建 tenant client。引用目标是 `merge_forward` 时，`_fetch_message_text` 复用直发路径的 `_expand_merge_forward_message` 展开子消息；`_collect_reply_attachments` 同时接受 `upper_message_id` 指向引用目标的子消息，使转发记录内的图片/文件也被下载。Gateway 识别仅由该展开器生成的 `[Merged forwarded messages]` 内部标记，把 Feishu 引用上下文上限从通用 500 提高到有界 20,000 字符；普通 Feishu 引用与其他平台仍保持 500，避免无关扩权。该补丁只负责取得资源字节/API 文本并完整交给模型，不负责解析文件格式。2026-08-05 对上游 `b51c4e6a7` / `e80b7aeda` 融合时，保留其线程锁保护的 SDK 延迟导入与 None 判定，删除重复 loader 形状，只在上游 `_load_lark_oapi()`/None 初始化集合中增加本补丁独有的 `DownloadFileRequest` / `ListMessageRequest`；资源访问的 admission、下载、展开、上界与 tenant fallback 均未被吸收。

**验证**：Step 8b 单独检查 sender/reply backfill、显式重复引用不被去重、单独 `/`、DM/两类群触发、Drive URL/download、tenant client fallback、引用 merge_forward 展开（`is_forward_child` + `_fetch_message_text` 展开分支）、Gateway 20,000 字符专用上限、`gateway/platforms/base.py` 的 `.odt` MIME 映射锚点（2026-08-07 起——该文件此前列于 文件 行但无任何 gate 覆盖）及对应测试。`test_quoted_resource_matrix_reaches_event_across_dm_and_group_triggers` 从完整入站路由覆盖群图片、群视频、DM 网页链接和 DM Drive 链接；`test_explicit_requote_is_not_suppressed_and_media_video_is_preserved` 锁定重复引用与视频 MIME。`test_feishu_merge_forward_reply_context_is_not_cut_at_generic_500_chars` 同时证明 12 条长转发的尾条保留、普通引用仍在 500 截断。真实 API 卡片返回 13 items（1 parent + 12 children、正文 915 字符），修复前 DB turn 在第 6 条中间止于 500 字符，修复后完整文本落入 user turn。

**上游吸收判断**：上游同时支持分离消息附件回看、Drive 正文链接下载、引用合并转发的子消息展开及完整有界送模、无 comment-context 的 tenant doc client 时可归档；SDK 延迟导入本身不是该补丁的语义吸收条件。

---

### [PATCH-DOCUMENT-EXTRACTION] 可信文档文本抽取

| 字段     | 内容                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `gateway/run.py`, `tools/read_extract.py`, `pyproject.toml`, `tools/lazy_deps.py`, `uv.lock` 及对应 tests                     |
| **状态** | 🟡 部分吸收（XLSX/DOCX/IPYNB 抽取、`read_file` 接线和 anydoc-only 扩展已上游合并；native PDF/HTML/PPTX/ODT 与入站接线仍本地） |

**问题**：附件成功下载后，PDF/HTML/PPTX/ODT 等二进制仍只给模型路径；群聊又不能临时执行解析脚本。上游 `tools/read_extract.py` 已覆盖 IPYNB/DOCX/XLSX，并在 `b2598b41e` 后通过可选 anydoc 覆盖 legacy Office/ODF/RTF/EPUB/PDF，但这些路径依赖可选转换器且没有替代本地 native PDF/HTML/PPTX/ODT、pypdf pin 与 Gateway 入站抽取。

**修复**：在上游 `read_extract.py` 抽取层上扩展 PDF（pypdf，兼容 PyMuPDF 安装）、HTML（移除主动内容）、PPTX、ODT，并对每文件/每轮文本做上界；上游 `file_tools.py` 的 `read_file` 接线按 `EXTRACTABLE_EXTENSIONS` 自动获得新格式，无需本地改动 `read_file` 主路径。`gateway/run.py` 新增 `_extract_inbound_document` 在线程池中抽取入站附件，向模型明确内容是不可信参考数据；加密、扫描或损坏文档保留路径并返回可解释降级。依赖在 project extra、lazy deps 与 lockfile 中固定。设计留观：`pypdf` pin 落在 `LAZY_DEPS["platform.feishu"]` 而非 `tool.doc_extract`（后者上游仍 anydoc-only）——本机 Feishu 栈必装故等价；非 Feishu 部署走 `read_file` 读 PDF 时不会触发懒装，若上游重写 feishu extra 需把 pin 迁到 `tool.doc_extract`。

**2026-08-03 收缩**：上游在 26e0b1c 已自带 `read_extract.py`（XLSX/DOCX/IPYNB）并经 `file_tools.py` 接进 `read_file`，本地曾并存的 `file_operations.py` `_read_spreadsheet` 第二条 XLSX 路径成为死代码（抽取分支先行拦截），已连同其测试一并删除；`tools/file_operations.py`、`tests/tools/test_file_operations.py` 移出 `PATCHED_FILES`。**2026-08-06 收缩**：上游 `b2598b41e` / `997a913` / `ffdbc88` 吸收 anydoc-only 格式、失败重试和 anydoc size cap；本地测试已把 anydoc-only 可用性（RTF/EPUB/DOC）与 native-overlap 可用性（PDF/PPTX/ODT）分离，防止上游 anydoc 语义重新压住本地 native 抽取。

**验证**：Step 8b 单独检查 common extractors（`_extract_pdf` / `_extract_html_file`）、`_extract_inbound_document`、pypdf 双路径依赖和 `TestCommonDocumentExtraction`，并锚定两条 2026-08-06 收缩测试（`test_native_overlap_formats_remain_extractable_without_anydoc` / `test_anydoc_only_formats_not_extractable_without_anydoc`）与入站路径测试 `test_extract_inbound_html_without_terminal_access`（2026-08-07 起——此前 gate 对收缩语义与 `test_document_context_note.py` 均无锚点）；覆盖 PDF 页边界、HTML 清理、Office/OpenDocument 顺序、字符上界及不依赖 terminal。已知留观（P3，本机不可达）：native 抽取失败时不回落 anydoc——`.pdf` 等双集合扩展名在 pypdf 缺失 ∧ anydoc 存在的配置下会直接报缺包而非尝试 anydoc；本机 pypdf 由 feishu lazy 栈钉死安装、anydoc 未装，路径死代码，待上游动该区域时一并处理。

**上游吸收判断**：上游 `EXTRACTABLE_EXTENSIONS` 以 native 或同等无需 prompt 的依赖策略覆盖 PDF/HTML/PPTX/ODT，并提供等价的 Gateway 入站附件抽取接线、prompt 上界和错误降级后可归档；仅有 anydoc 可选转换不构成本地 native/inbound 语义吸收。资源获取能力独立留在 `PATCH-FEISHU-RESOURCE-ACCESS`。

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

**表格子分支（已退役 2026-07-25）**：旧版补丁曾在检出 GFM 表格时先调 `convert_table_to_bullets()` 转成 `**行标题**` + bullet 组，规避早年"含表格的 post/md 整条空白"的客户端 bug。上游 #52786（2026-07-24 轮吸收 `prefer_post` 时的冲突来源）声称新版客户端已原生渲染表格；2026-07-25 真机实测「含 GFM 表格的 post/md 消息」正常渲染（不空白、单元格加粗正常）后，按既定计划撤除该子分支：`_build_outbound_payload` 恢复上游表格直传原文，补丁自有测试 `test_build_outbound_payload_table_converts_to_bullets_and_posts` 删除；`test_feishu.py` 中的 `test_build_outbound_payload_uses_post_for_markdown_table` 为**本地补回**的直传断言（上游已在 `6b81590c5` 低价值测试清理中删除该名字；上游现存表格测试是未改动的 `test_feishu_table_markdown.py::test_markdown_table_uses_post_not_text`）。若老客户端再现空白表格，可从外层仓历史恢复该分支（见 git log patches/local-patches.diff）。

**验证**：Step 8b grep `adapter.py` 中存在 `def _promote_block_markdown`、`def _fix_strong_flanking` 且 **不存在** `convert_table_to_bullets`（2026-08-07 负向锚点，防 3-way 静默复活已退役子分支）；grep `test_feishu.py` 中存在 `test_promote_block_markdown_fixes_strong_flanking`；`tests/gateway/test_feishu.py` 全量 237 passed（2026-07-25，含新增 3 条 flanking 用例；表格退役后恢复上游直传断言；SSRF rebind 测试本次单文件跑亦通过）。flanking 修复上线前经真机三轮 A/B：真实失败样例（`**“端云通信协议”**` 等）复现失败 → 修复后写法（`“**端云通信协议**”`）实测正常渲染；近 21 天语料重放确认 84/445 条会被改写且全部改写结果 flanking 合法。

**上游吸收判断**：若上游为飞书 post/md 原生补齐标题 / 引用渲染，或将回复改走 interactive card markdown 元素，可归档本补丁的 promote 分支；flanking 分支（修复 ②）在上游对出站 markdown 做等价 flanking 归一化前保持活跃。表格转 bullets 子分支已于 2026-07-25 真机验证原生表格渲染后撤除（该部分现与上游 #52786 行为一致，见上文"表格子分支（已退役）"）。

---

### [PATCH-FEISHU-SSRF-TEST-SYSPROXY] SSRF rebind 测试对宿主系统代理 hermetic

| 字段     | 内容                           |
| -------- | ------------------------------ |
| **文件** | `tests/gateway/test_feishu.py` |
| **状态** | 🟡 未上游合并                  |

**问题**：上游 `test_download_remote_document_blocks_connect_time_rebind` 只把 6 个代理**环境变量** patch 成空串来构造"无代理直连"场景，但 httpx `trust_env` 的代理解析走 `urllib.request.getproxies()`——env 为空时在 macOS 回落到 **scutil 系统代理配置**（Windows 回落注册表）。宿主开着系统级代理（本机 Clash Verge，127.0.0.1:7897）时，请求实际经代理外发，direct-connect SSRF 守卫按设计把最终目标解析委托给代理（"proxy = trusted egress boundary"，见 `create_ssrf_safe_async_client` docstring），测试预期的 `SSRFConnectionBlocked` 永不触发，收到裸 `httpx.ConnectError`。后果：只要跑回归时 Clash 系统代理开着，规范 runner（`scripts/run_tests.sh`）必然 1 failed，升级 playbook 的 "0 failed" 完成标准无法达成。此前摩擦表把该现象误诊为"跨文件测试状态依赖、批量跑通过"——实际变量是**跑测试那一刻宿主系统代理的开关状态**，与文件组合方式无关（2026-07-29 以 probe 插件证实测试内 HERMES_HOME 隔离与 allow_private 缓存均正常，failing connect 目标为 `127.0.0.1:7897`）。

**修复**：测试的 `with` 块内在 `patch.dict(os.environ, proxy_vars)` 之后追加 `patch("httpx._utils.getproxies", return_value={})`（httpx 0.28 在 `_utils` 模块顶部 `from urllib.request import getproxies`，client 构造时经 `get_environment_proxies()` 调用），把系统代理回落一并掐断，使测试语义回到其本意（无任何代理、纯直连路径校验 connect-time rebind 拦截）。生产代码零改动；env 变量 blank 保留（防护其他读取路径）。

**验证**：Step 8b grep `tests/gateway/test_feishu.py` 存在 `httpx._utils.getproxies` 且目标测试 `test_download_remote_document_blocks_connect_time_rebind` 仍在（2026-08-07 起——仅锚 patch 串时，rebind 测试被整体删除也会误报 active）。`tests/gateway/test_feishu.py` 全量 237 passed / 0 failed（2026-07-29，Clash 系统代理**开启**状态下经规范 runner 复跑通过；修复前同条件 1 failed，且单 pytest 进程多文件组合同样失败，证伪旧"批量通过"结论）。

**上游吸收判断**：上游为该测试补上系统代理中和（patch `getproxies` / `trust_env=False` / mounts 显式置空任一等价手段）后可归档本补丁；届时同步删除摩擦表对应 row。

---

### [PATCH-VERTEX-HIDDEN-THOUGHTS] Vertex 保留 thinking 但隐藏 thought 文本

| 字段     | 内容                                                                                     |
| -------- | ---------------------------------------------------------------------------------------- |
| **文件** | `plugins/model-providers/vertex/__init__.py`, `tests/hermes_cli/test_vertex_provider.py` |
| **状态** | 🟡 未上游合并                                                                            |

**问题**：官方 `provider: vertex` 通过 Vertex OpenAI-compatible endpoint 调 Gemini 3.x 时，`reasoning_effort: high` 会映射到 `extra_body.google.thinking_config.include_thoughts=true`。实测 Vertex 这条 OpenAI-compatible 路径不会把 thought 拆成 Hermes 可隐藏的 `reasoning_content` 字段，而是把 thought text 直接拼进 `message.content`，飞书端会看到类似 `**Identifying Current Model**` 的思考段，即使 `display.show_reasoning=false`。

**（2026-07-07 修订·真实根因）**：初版把 `include_thoughts` 强制改 false 后返回 `{"extra_body": {"google": {...}}}`——**多包了一层 `extra_body` 键**。基类 `ProviderProfile.build_extra_body` 的约定是"返回值会被 merge 进 extra_body"，经 `_build_kwargs_from_profile` 后线上真正发出的是 `extra_body={"extra_body": {"google": {...}}}`；Vertex 不认这个顶层 `extra_body` 字段，直接忽略 → `include_thoughts` 回落默认 true → thought 仍进正文。初版的"真链路验证"用的是**手写单层** `extra_body={'google': {...}}`（未走 `build_kwargs` 组装），因此漏掉了这层 bug。飞书主会话据此泄漏大量 `**加粗标题** + "I'm diving into…"` 思考段。

**修复**：`build_extra_body` 改为返回**单层** `{"google": {"thinking_config": thinking_config}}`（与 qwen/nous 等 profile 的扁平返回约定一致），使线上 `api_kwargs["extra_body"]` 恰为 `{"google": {"thinking_config": {"include_thoughts": False, "thinking_level": "high"}}}`——Vertex 读到顶层 `google.thinking_config`，抑制生效。保留 `thinking_level=high` 让模型继续内部思考，只是不把 thought text 返回正文。附带 hunk：插件 alias 列表补 `"vertexai"`，与上游 `runtime_provider.py` 已收录的别名对齐（此前为未登记改动，2026-08-07 归属至此）。

**验证**：Step 8b grep `plugins/model-providers/vertex/__init__.py` 存在 `include_thoughts=true` 说明、`thinking_config["include_thoughts"] = False` 与**单层** `return {"google": {"thinking_config": thinking_config}}`；测试同时保留 profile 正反例，并以 `test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `ChatCompletionsTransport.build_kwargs()`，断言最终请求 kwargs 只有单层 `extra_body.google.thinking_config`。真链路 A/B 对比（`VERTEX_ACCESS_TOKEN`，同一 plan 类 prompt）：**A 单层 → 干净答案**；**B 双层（旧）→ `" Too simple, doesn't add value…"` 思考泄漏**。2026-08-03 主会话复测因 Google OAuth 链路瞬时 SSL EOF 自动回退到 Qwen，但仍证明出站最终 `content` 与隐藏 `reasoning` 分离；Vertex wire request 形状由规范 runner 的边界测试持续锁定。

**注**：`plugins/model-providers/gemini/__init__.py`（AI-Studio `gemini` provider）存在同构的双层写法，但本环境不走该 provider，暂不改动，待验证。

**上游吸收判断**：若上游能把 Vertex OpenAI-compatible 返回的 Gemini thoughts 解析并存入隐藏 reasoning 字段，或官方 Vertex profile 默认隐藏 thoughts 且保留 thinking level，可归档本补丁。**隐式合约依赖**：本补丁的单层返回形状依赖基类 `ProviderProfile.build_extra_body` 的"返回值 merge 进 extra_body"约定；每轮升级必须复核该基类合约未变（`test_vertex_transport_build_kwargs_hides_thoughts_on_wire` 穿过真实 `build_kwargs()` 锁定最终 wire 形状，合约变化会在该测试直接暴露）。2026-08-03 对 post-26e0b1c 上游复核：插件仍是双层包裹 bug 原样，未吸收。

---

### [PATCH-VERTEX-DOCTOR] Doctor 识别官方 Vertex provider

| 字段     | 内容                                                      |
| -------- | --------------------------------------------------------- |
| **文件** | `hermes_cli/doctor.py`, `tests/hermes_cli/test_doctor.py` |
| **状态** | 🟡 未上游合并                                             |

**问题**：切到官方 `model.provider: vertex` 后，实际 runtime provider 已能通过 `providers.get_provider_profile("vertex")` 和 `agent.vertex_adapter` 正常拿 OAuth token 调 Vertex OpenAI-compatible endpoint，但 `hermes doctor` 仍只看 auth/catalog provider 列表，不读 model-provider plugin registry，于是误报 `model.provider 'vertex' is not a recognised provider`。同时 `google/gemini-3.1-pro-preview` 这类 Vertex 官方 OpenAI-compatible 模型名被当作 OpenRouter 风格 vendor slug，额外误报应该切 openrouter 或去掉前缀。

**修复**：doctor 在校验 provider 时补充读取 `providers.get_provider_profile()`，将 plugin profile 的 canonical name 加入可接受 provider id 集合，并让 vendor-slug 策略同时考虑原始 provider、auth runtime provider、catalog provider 与 plugin canonical provider。`vertex` 与 `vertex-fallback`（2026-08-07 补：`model.provider: vertex-fallback` 时同样服务 `google/*` slug，缺失会复发 vendor-slug 误报）被加入允许 `vendor/model` 形态的 provider 集合；`.env` 健康检查同时识别 `GOOGLE_APPLICATION_CREDENTIALS` / `VERTEX_PROJECT_ID` / `VERTEX_LOCATION`，避免只配置官方 Vertex 凭据时被误判为没有 provider auth。

**验证**：Step 8b grep `hermes_cli/doctor.py` 中存在 `_get_provider_profile`、`GOOGLE_APPLICATION_CREDENTIALS` 与 `"vertex"`，并 grep `tests/hermes_cli/test_doctor.py` 中存在 `test_run_doctor_accepts_vertex_provider_and_google_model_slugs`（parametrize 覆盖 `vertex` / `google-vertex` / `vertex-fallback` 三个 provider 值，2026-08-07 起）。规范 runner 定向回归（2026-08-07 口径）：`test_doctor.py` 83 passed、`test_vertex_provider.py` 14 passed、`test_session.py` 167 passed，0 failed（历史 "23 passed" 计数来自 2026-07-29 的旧测试集合，上游 6b81590c5 测试清理后文件现存 14 条）。实际 `hermes doctor` 在当前 `provider: vertex` 配置下显示 `Config version up to date (v33)`，Vertex 配置检查通过；仅另报 web 8 high / ui-tui 7 high 的已知 build-tool advisory。

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
3. `agent/auxiliary_client.py`：`resolve_provider_client` 的 `auth_type=="vertex"` 分支内，按 **registry 条目的 canonical id**（`pconfig.id == "vertex-fallback"`，2026-08-07 修复——此前按原始 provider 串判定，`vertex2`/`vertex-secondary` 别名会静默铸出主账号凭据，恰是配额耗尽的那个账号）改用 `get_vertex_fallback_config` / `has_vertex_fallback_credentials`。
4. `plugins/model-providers/vertex/__init__.py`：用同一 `VertexProfile` 类再 `register_provider` 一个 `name="vertex-fallback"` 实例，使 `get_provider_profile("vertex-fallback")` 可解析（fallback 激活后 `_build_request_kwargs` 走 profile 路径拿到单层抑制）。
5. `hermes_cli/runtime_provider.py`（2026-07-29 补缺口）：网关 fallback 链（`gateway/run.py` `_try_resolve_fallback_provider`）解析条目走 `resolve_runtime_provider(requested=...)` 而**不是** `resolve_provider_client`；其 Vertex 分支只认主账号 5 个别名，`vertex-fallback` 静默落到 generic 尾部解析器，"成功"返回 `provider="openrouter"` + **空 api_key**——网关据此打出误导性的 `Fallback provider resolved: vertex-fallback` 日志并把坏 kwargs 交给 `AIAgent`；init 因空 key 走 router 路径，又因 `openrouter` 在豁免集合（`{auto, openrouter, custom}`）里跳过 explicit fail-fast 与 init-time fallback，最终抛 `No LLM provider configured`，用户在群聊/私聊看到 "Sorry, I encountered an unexpected error"；且链上后续条目（`alibaba/qwen3.6-plus`，NO_PROXY 直连、代理瞬断时本可救场）永远轮不到。修复：在主 vertex 分支之后新增 `("vertex-fallback", "vertex2", "vertex-secondary")` 分支，经 `get_vertex_fallback_config()` 铸 token 返回 `provider="vertex-fallback"`；凭据不可解析时抛类型化 `AuthError`，使 fallback 链前进到下一条目。触发场景：本机代理（127.0.0.1:7897）瞬断时 `oauth2.googleapis.com` token 刷新失败（"No route to host" / SSL EOF，见 `logs/agent.log*`），主 Vertex 解析抛 AuthError 进入 fallback 链。

配套（非工程内补丁）：`~/.hermes/.env` 加 `VERTEX_FALLBACK_CREDENTIALS_PATH` + `VERTEX_FALLBACK_PROJECT_ID`（第二账号 SA 文件 `~/.gemini/gen-lang-client-0217395804-…json`，project `gen-lang-client-0217395804`）；`~/.hermes/config.yaml` 把 `fallback_providers` 设为 `vertex-fallback/gemini-3.1-pro`，`fallback_model` 保留 `alibaba/qwen3.6-plus` 作末位兜底（有效链 = 二者 merge 去重）。

**验证**：Step 8b grep `agent/vertex_adapter.py` 存在 `def get_vertex_fallback_config` + `apply_global_project_override`；`hermes_cli/auth.py` 存在 `"vertex-fallback"`；`agent/auxiliary_client.py` 存在 `has_vertex_fallback_credentials`；`plugins/.../vertex/__init__.py` 存在 `name="vertex-fallback"`；`hermes_cli/runtime_provider.py` 存在 `"vertex-fallback", "vertex2", "vertex-secondary"` 分支；test 存在 `test_vertex_fallback_profile_registered` + `test_resolve_runtime_provider_vertex_fallback_mints_token` + `test_resolve_provider_client_alias_mints_fallback_credentials`（2026-08-07 新增：别名走 fallback 凭据、主账号铸 token 被断言不可达）。单测 14 passed / 0 failed（2026-08-07；含 7 条 fallback 回归）。真链路：`resolve_runtime_provider(requested='vertex-fallback')` 返回 `provider="vertex-fallback"`、base_url 锁定 `projects/gen-lang-client-0217395804`、api_key 为有效 OAuth token（修复前同调用返回 `provider="openrouter"` + 空 api_key）。真链路端到端：加载 `.env` 后 `get_vertex_fallback_config()` 返回 base_url 锁定 `projects/gen-lang-client-0217395804`（未被主 project 覆盖），`resolve_provider_client("vertex-fallback", model="google/gemini-3.1-pro-preview")` 返回可用 client 且真实调用返回干净答案（无 thought 段）。第二账号 SA 直连 Vertex `/v1`+`/v1beta1` global 均 200。

**上游吸收判断**：若上游为 Vertex/OAuth-token 类 provider 提供多凭证轮换池（credential pool），或让 fallback 条目原生携带 per-entry `credentials_path`/`project`，可归档本补丁改用原生机制。**候选替代已进入当前树**（2026-08-03，d1afa160 已含）：`agent/credential_pool.py`（`CredentialPool`/`PooledCredential`，支持 `AUTH_TYPE_OAUTH`，`hermes_cli/auth.py` 与 `runtime_provider.py` 已接入）提供同 provider 多凭证 failover，但按 token/api-key 条目存储，**尚无 per-entry SA 文件 + 独立 GCP project 语义**——本补丁"第二账号绕 per-project 配额"的需求暂不能直接表达，本轮判定为继续保留本地实现；后续每轮复核该池是否补齐 SA-file/project 语义，补齐即迁移。同时注意 `ca5ce1110` 已把 auxiliary-client 的 provider-key 读取改走 profile secret scope，与本补丁在 `auxiliary_client.py` 的改写区域重叠（本轮 3-way 已干净并存），后续冲突按 scoped-read 形式适配本地分支。

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

| 字段     | 内容                                                                                                                                 |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **文件** | `agent/image_routing.py`, `gateway/run.py`, `tests/agent/test_image_routing.py`, `tests/gateway/test_image_input_routing_runtime.py` |
| **状态** | 🟡 未上游合并；依赖 `PATCH-VERTEX-IMAGE-ROUTING` 的 Vertex/Gemini 识别                                                               |

**问题**：上游视频只注入本地 path note，期望模型自行用 ffprobe/ffmpeg；群聊没有 terminal，因而即使附件已缓存也看不到视频内容。图片能力不能直接等同视频能力，且视频没有缩图重试，必须使用更窄的白名单和大小边界。

**修复**：新增 `decide_video_input_mode`、独立 Vertex+Gemini 3.x 视频白名单、magic-byte/MIME 校验和 14 MB 内联上限。支持的视频转换为 `data:video/*;base64` content part；gateway 用 session buffer 把 native video paths 传给 content builder，超限/不支持视频保留原 path-note 降级。无需给群聊放开任何命令工具。**2026-08-07 审计修复两处接线缺陷**：① gateway wrapper `_decide_image_input_mode` 曾把 `kind=kind` 直传给不接受该参数的 `decide_image_input_mode`（本地=上游签名均无 `kind`），TypeError 被 fail-open except 吞掉后**所有**网关图片/视频路由静默退化为 `"text"`——视频补丁在生产路径完全失效、图片路由连带破坏（上游 `test_pre_turn_named_custom_provider_identity_selects_vision_override` 在 worktree 上 1 failed，该文件当时不在补丁测试清单故 815/0 未暴露）；现 wrapper 内按 kind 分流，`kind=="video"` 直连 `decide_video_input_mode`（无网络 I/O，同时消除 async handler 内的同步阻塞隐患），图片路径恢复上游原签名调用。② 视频 buffer 补齐与图片路径对称的**每轮重置**（`_consume_pending_native_video_paths(session_key)`），杜绝被中止 turn 的视频泄漏进同会话下一轮。

**验证**：Step 8b 单独检查 video decision、native-video session buffer、**gateway 接线**（`return decide_video_input_mode(` 与 per-turn consume 锚点，2026-08-07 起——此前四个锚点全部只锚定义与测试名，功能整体失效时 gate 仍报 active）和 data-URL 回归；`test_gateway_kind_video_routes_through_video_decision_table` 从 runner 边界证明 kind="video" 真正抵达视频决策表（vertex+gemini-3 → native、非白名单 → text）；`test_prepare_resets_stale_video_buffer_per_turn` 穿过真实 `_prepare_inbound_message_text` 证明陈旧视频 buffer 与图片 buffer 一同被每轮重置；测试另覆盖 Vertex primary/fallback、非视频模型、显式配置、MIME/大小守卫和实际 content parts。

**上游吸收判断**：上游提供通用 native video routing、明确的视频 capability 和等价 MIME/size safety 后可归档。

---

### [PATCH-HISTORY-RETENTION] 平台级回放历史保留窗

| 字段     | 内容                                                                                                                                                                                                                    |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `agent/replay_cleanup.py`, `gateway/run.py`, `tests/agent/test_replay_cleanup.py`, `tests/gateway/test_stale_confirmation_expiry.py`（配置键 `gateway.history_retention` 在 `~/.hermes/config.yaml`，非 PATCHED_FILES） |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                           |

**问题**：（2026-07-14 复盘 SpaceSight Tech Sharing Group 历史污染）共享群 session 每轮把**全量** transcript 回放给模型（`load_transcript` → `_build_gateway_agent_history`），唯一的历史收敛机制是按 token 触发的 hygiene/压缩——大上下文模型（Gemini 3.1 Pro）上 94 条消息远够不到 85% 阈值，从不触发；且压缩是摘要不是丢弃。结果是 7 月 10 日 随消息入库的一次性 `[Feishu assistant mode]` 指令块 + 模型照做的范例，在 7 月 14 日 第三方 @bot（零注入分支）轮次里仍然整段可见，模型据此模式补全出「我是琛哥的赛博小助手…琛哥可能在忙」的代答口吻。缺一个与 token 无关的、按**墙钟时间和条数**的回放上界。

**修复**：`agent/replay_cleanup.py` 新增 `apply_history_retention(history, now, max_age_seconds, max_messages)`（sentinel `history-retention`）：视图级过滤——state.db 完整保留（审计 / `/resume` / 搜索不受影响），只裁剪发给模型的回放。语义：切点只落在**轮边界**（普通 user 行，`_retention_turn_starts`），绝不切断 assistant(tool_calls)→tool 配对；时间窗按整轮的开头 user 行 `timestamp` 判断，无时间戳的行视为"新"（兼容旧转录与内存脚手架，防止配置误伤成批丢历史）；条数上限向轮边界**向上取整**；最新一轮无论多旧/多长永远保留；两个限制同时配置取更严格的切点；无 user 行的退化历史原样返回。`gateway/run.py` 新增 `_history_retention_limits_for_source()`：从 `gateway.history_retention.<platform-key>` 读取限额，platform-key 复用工具/skill 配置同款 chat-scope 拆分（飞书群=`feishu_group`、私聊=`feishu`），未配置或值非法一律 fail-open 返回 None。注入点在 `_run_agent_inner` 的 cached-agent 守卫（`_select_cached_agent_history`）**之后**，单点同时覆盖「盘上转录」与「内存活转录」两条路径。本机 `config.yaml` 配置 `feishu_group: {max_age_seconds: 21600, max_messages: 30}`（6 小时 / 30 条），私聊与 CLI 不配置、行为不变。

**验证**：Step 8b grep `agent/replay_cleanup.py` 中存在 `def apply_history_retention`、`def _retention_turn_starts`，grep `gateway/run.py` 中存在 `_history_retention_limits_for_source`、`_apply_history_retention`，并 grep `tests/agent/test_replay_cleanup.py` 中的 `test_retention_never_splits_tool_call_blocks`、`test_retention_newest_turn_always_kept_even_if_too_old` 与 `tests/gateway/test_stale_confirmation_expiry.py` 中的 `test_retention_feishu_dm_not_covered_by_group_key`。定向测试覆盖：时间窗丢整轮、条数向轮边界取整、tool-call 块不被切断、最新一轮超龄/超量仍保留、无时间戳视为新、时间 + 条数组合取更严、未配置/畸形配置 fail-open、DM 不受群键影响（`test_replay_cleanup.py` 21 passed + `test_stale_confirmation_expiry.py` 15 passed；周边 `test_session.py` 167 passed + `test_feishu.py` 237 passed）。

**上游吸收判断**：若上游为 gateway 回放历史提供原生的时间窗/条数保留配置（或给共享群 session 引入等价的 per-platform replay 上界机制），可归档本补丁。

---

### [PATCH-APPROVAL-DARWIN-TMP] Darwin verify-artifact 临时路径归一化

| 字段     | 内容                                                                                                                                                                                                                                      |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | `tools/approval.py`（仅 `_is_verification_artifact_cleanup` 的 `allowed_spellings` hunk）, `tests/tools/test_approval.py`（仅 `test_darwin_private_alias_accepts_raw_temp_spelling`）——两文件的其余 hunk 属 `PATCH-FEISHU-GROUP-APPROVAL` |
| **状态** | 🟡 未上游合并                                                                                                                                                                                                                             |

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

**验证**：Step 8b grep `build.sh` 锚定 **Darwin 分支本体**——`uname -s.*Darwin`、`LDFLAGS_EXTRA="-undefined dynamic_lookup"`、强制 `CFLAGS_EXTRA="-Ivendor"` 与链接行消费 `$LDFLAGS_EXTRA`（2026-08-07 修复：旧锚点 `Ivendor` 在裸上游的 Linux fallback 中同样存在、无判别力，丢失 Darwin 强制 vendored 头的部分回贴会通过旧 gate 并产出加载即段错误的扩展），并提示 `~/.hermes/lib/libfts5_cjk.so` 是否已构建。端到端（2026-07-25）：`load_fts5_cjk_extension()` 返回 True；`:memory:` 建 `tokenize='cjk_unicode61'` FTS5 表后二字中文词 `项目` 索引命中；`hermes sessions optimize-storage` 回填生产索引。

**上游吸收判断**：上游给 build.sh 加 Darwin 分支（或改用统一走 api 指针的构建方式）后，可归档本补丁。

---

### [PATCH-FEISHU-GROUP-SANDBOX] 群聊结构化 tmp 与固定文档动作边界

| 字段     | 内容                                                                                                                                                                                                                                                                                                                                                                                                                          |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件** | 配置仓库：`config.yaml`, `plugins/sandbox/{__init__.py,config.yaml,plugin.yaml,test_sandbox.py,verify.sh}`, `my-skills/productivity/feishu-docs/{SKILL.md,scripts/create_new_doc_from_md.py,scripts/download_feishu_file.py,scripts/feishu_common.py,scripts/read_docx_to_markdown.py,scripts/read_feishu_url.py}`, `memories/MEMORY.md`, `hermes-update.sh`, `hermes-update.md`, `README.md`（均不属于内层 `PATCHED_FILES`） |
| **状态** | 🟢 配置仓库用户插件补丁；升级保留，Step 8e 强制回归                                                                                                                                                                                                                                                                                                                                                                           |

**依赖**：`PATCH-FEISHU-GROUP-SCOPE` 提供 `feishu_group` namespace，并保证真实 Gateway consumer 使用该 key；`PATCH-PLATFORM-CAPABILITY-SCOPE` 提供只读工具集，`PATCH-FEISHU-GROUP-APPROVAL` 提供审批层纵深防线。依赖缺失时 Step 8b/8e 分别失败，不允许把插件显示为健康。

**问题**：旧版 sandbox 给 Feishu 群聊保留通用 `terminal`，再用命令字符串、脚本目录和下载目录 allowlist 约束用途。这个边界仍暴露 shell 解析面，无法从能力模型上禁止群成员创建脚本后执行，也无法限制被信任脚本及其子进程写入整个用户目录；`tmp` / `cache` 的用途和不同群之间的文件隔离也不明确。另一方面，群聊确实需要创建、追加、重建、删除和读取飞书文档，并需要一个可读写的临时数据区。主 Feishu DM 则必须继续获得默认完整工具面，危险命令走 owner 人工审批，不能被群聊策略误伤。

**修复**：从 `platform_toolsets.feishu_group` 删除 `terminal`，新增用户插件 toolset `sandbox_group`，仅暴露两个结构化入口：`group_cache` 在 `~/.hermes/tmp/group-workspaces/<chat-id-hash>/` 内执行文本文件 CRUD；`feishu_doc_manage` 将 `create/append/rebuild/delete/read_url/download_file` 六个 action 映射到管理员预装的固定脚本文件。模型不能提交 shell、脚本路径或原始 argv，工作区文件永远只作数据。工作区路径按群哈希隔离且校验相对路径、realpath 和 symlink containment；根目录权限为 `0700`。脚本以 argv + `shell=False` 执行，macOS `sandbox-exec` profile 由插件生成并由整个子进程树继承：允许读取/执行/联网，但只允许写当前群工作区；OS 进程沙箱不可用或配置加载失败时 fail closed。群聊下载限制为单文件 50 MB，`TMPDIR` 和原子更新备份都重定向到当前群工作区；stdout/stderr 回传前统一脱敏 Bearer token、Feishu app secret 与 tenant token，上传失败也切断会暴露 curl Authorization argv 的异常链。wiki 仅可直接读取 `~/.hermes/wiki`；`skills` / `my-skills` 只能经 `skills_readonly` 查看 allowlist 中的 `llm-wiki` 与 `feishu-docs`，不能直接写。`known_plugin_toolsets` 把 `sandbox_group` 标记为已知但只在 `feishu_group` 显式启用；普通 `feishu` 不配置平台覆盖，owner chat 又在 `pre_tool_call` 最前面无条件放行，因此主私聊保留 terminal、文件读写、代码执行、skill 管理、浏览器和 cron 等完整默认工具面。`tmp` 不整目录删除，因为 `scripts/nightly_greeting.py` 仍使用 `tmp/nightly_report`；群聊统一使用上述 tmp 子树，不改用 cache。

`read_url` 依赖链另有一处解释器耦合：`read_feishu_url.py` 只借用 `read_docx_to_markdown.py` 的纯渲染函数 `parse_blocks`，但后者在模块顶层 `import requests`，因此任何缺 `requests` 的解释器执行该链都会整条失败（现场表现为 `ModuleNotFoundError: No module named 'requests'`，可追至 2026-05-18，与 v0.19.0 升级无关）。根因是 `SKILL.md` 长期把 `uv run --with requests python` 作为这些脚本的规范调用方式：`~/.hermes` 下没有 `pyproject.toml` / `.venv` / `.python-version`，`uv run python` 会自行拉起一个与 hermes venv 无关的临时解释器（实测 uv 0.11.32 选到 CPython 3.13.14），其中并无 `requests`，只有 `--with requests` 才被临时注入；venv 解释器本身是 3.12.13 且 `requests==2.33.0` 为 pin 死的直接依赖。因此凡是漏掉 `--with requests`（如原 `SKILL.md:188` 的裸 `python ... append_md_to_doc.py`），或该链上任何模块在顶层 import requests 时，都会退化成 `ModuleNotFoundError`。`__pycache__` 中并存 `cpython-313` / `cpython-314` 字节码正是这些非 venv 解释器执行过的物证。配套修正 `SKILL.md`：`188` 行改为 venv 绝对路径，`232` 行依赖说明改为「首选 `~/.hermes/hermes-agent/venv/bin/python`（已 pin `requests`，无需 `--with`）」并写明裸 `uv run python` 为何不可用。修复把 `import requests` 下移进 `get_tenant_access_token()` 与 `download_doc_to_md()` 两个真正联网的函数，使纯渲染路径回到 stdlib-only；同时 `_handle_feishu_doc_manage` 的 start/end 日志补记 `python=<解释器路径>`，让后续同类故障可从 `agent.log` 直接判定实际解释器。

**验证**：`plugins/sandbox/verify.sh` 作为 `hermes-update.sh` Step 8e 的硬门槛：结构化解析根/插件 YAML，确认群策略保持 `open + require_mention`、审批为 `manual`、launchd 未启用 YOLO、owner Feishu 无 `platform_toolsets.feishu` 收窄、群聊 toolset 精确且固定脚本全部存在；通过真实 `discover_plugins()` + `_get_platform_tools()` 解析，断言 owner Feishu 仍含 terminal/process/read/write/patch/execute_code/skill_manage，群聊只含 `group_cache` / `feishu_doc_manage` 与只读工具；`PATCH-FEISHU-GROUP-SCOPE` 的 `_run_agent` 边界测试进一步证明真实 consumer 确实把群 toolset 交给 Agent，而不是只在独立解析器里得到正确结果；确认 hook 名、fire site、`ctx.register_tool()` 和 `/usr/bin/sandbox-exec`；运行 21 个插件回归，覆盖跨群隔离、路径穿越/symlink、无 terminal/直接写面、真实 owner ID 全量放行、固定 action/参数、argv 无 shell、凭据错误输出脱敏、50 MB 下载上限、真实进程沙箱外写拒绝、配置加载和工具注册；另有一条源码哨兵断言 `read_docx_to_markdown.py` 不在模块顶层 `import requests` 且两个联网函数的惰性导入**计数恰为 2**（2026-08-07 收紧：旧断言为 ≥1 存在性检查，删除其中一个惰性导入仍会通过），双向负例（提升到顶层／删除任一惰性导入）均会失败；`read_docx_to_markdown.py` 已列入 expected_scripts，使其缺失报友好错误而非裸 FileNotFoundError；最后要求注册日志的 PID 与当前 gateway PID 一致、`active=True` 且包含两个结构化工具。verifier 缺失、不可执行、配置/toolset 漂移、测试失败或 runtime trace 不匹配都会设置升级 `FINAL_RC=1`。本补丁由外层 Git 保存，`hermes update` 不覆盖；`local-patches.diff` 只监管 `PATCHED_FILES` 中的工程内语义补丁，并必须与 `hermes-agent` 实际 diff（排除已知 `package-lock.json` 噪音）逐字节一致。

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
